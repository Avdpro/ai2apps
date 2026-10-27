"""Client SDK for native BiDi window leases; never a substitute for native support.

DOM/article reads do not enter this module. Legacy hosts keep their existing
rendering policy. The native TTL bounds lost responses and ungraceful disconnects.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, nullcontext
from functools import wraps
import logging
import uuid
import weakref

log = logging.getLogger(__name__)
log.info("WebAgent native rendering SDK=window-leases-v1 loaded from %s", __file__)
_pools = weakref.WeakKeyDictionary()


async def capture_screenshot(page, params, *, timeout=15):
    leases = getattr(page.connection, 'rendering_leases', None)
    async with leases.hold(page, 'capture') if leases is not None else nullcontext():
        return await page.connection.command('browsingContext.captureScreenshot', params, timeout=timeout)


def native_rendered(purpose):
    def decorate(fn):
        @wraps(fn)
        async def wrapped(page, *args, **kwargs):
            async with page.rendering_lease(purpose):
                return await fn(page, *args, **kwargs)
        return wrapped
    return decorate


class RenderingLeases:
    def __init__(self, connection):
        self.connection = connection
        self.capability = None
        self.active = {}
        self.events = []
        self.holder = 'sdk:' + uuid.uuid4().hex
        self.closing = False

    def record(self, event, context, purpose, **values):
        value = dict(event=event, context=context, purpose=purpose, **values)
        self.events.append(value)
        del self.events[:-64]
        log.info('WebAgent rendering lease %s', value)

    async def probe(self, context):
        if self.capability is None:
            try:
                result = await self.connection.command(
                    'browsingContext.getRenderingLeaseCapabilities', {'context': context}, timeout=5)
            except RuntimeError as error:
                # Only explicit protocol unsupported is compatible with a legacy
                # engine. Transport errors and invalid context are real failures.
                if not any(code in str(error).lower() for code in ('unknown command', 'unknown method', 'unsupported operation')):
                    raise
                result = {'version': 0, 'scope': 'unavailable'}
            if result.get('version') not in (0, 1):
                raise RuntimeError('Invalid native rendering lease capability')
            self.capability = result
        return self.capability

    def capture_pool(self):
        loop = asyncio.get_running_loop()
        pools = _pools.setdefault(loop, {})
        # Endpoint PID is a non-secret host identity, set by the authenticated
        # transport. Different instances never share a rendering quota.
        host = getattr(self.connection, 'host_pid', id(self.connection))
        return pools.setdefault(host, asyncio.Semaphore(2))

    async def renew(self, entry):
        try:
            while True:
                await asyncio.sleep(20)
                await self.connection.command('browsingContext.renewRenderingLease',
                    {'context': entry['context'], 'lease': entry['lease']}, timeout=5)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.record('renewal_unconfirmed_ttl', entry['context'], entry['purpose'])

    async def release(self, key, entry):
        self.active.pop(key, None)
        heartbeat = entry.get('heartbeat')
        if heartbeat:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
        try:
            result = await self.connection.command('browsingContext.releaseRenderingLease',
                {'context': entry['context'], 'lease': entry['lease']}, timeout=5)
            self.record('released', entry['context'], entry['purpose'], task=entry.get('task'), released=result.get('released'))
        except Exception:
            self.record('release_unconfirmed_ttl', entry['context'], entry['purpose'])
            # Never replay content input or claim that resource release succeeded.

    @asynccontextmanager
    async def hold(self, page, purpose):
        context = page.context_id
        key = (asyncio.current_task(), context, purpose)
        if key in self.active:
            entry = self.active[key]
            entry['depth'] += 1
            try:
                yield
            finally:
                entry['depth'] -= 1
            return
        capability = await self.probe(context)
        if capability['version'] == 0:
            self.record('unsupported_existing_policy', context, purpose)
            yield
            return
        if self.closing:
            raise RuntimeError('Browser rendering lease transport is closing')
        pool = self.capture_pool() if purpose == 'capture' else None
        if pool:
            await pool.acquire()
        entry = None
        try:
            # Page ownership/access is checked by the executor before admission.
            # Task is attribution only and never grants access to another page.
            task = str(getattr(page, 'run_id', self.holder))[:80]
            receipt = await self.connection.command('browsingContext.acquireRenderingLease',
                {'context': context, 'purpose': purpose, 'holder': task + ':' + self.holder[-32:], 'ttlMs': 60000}, timeout=5)
            entry = dict(receipt, context=context, purpose=purpose, task=task)
            if not receipt.get('lease') or receipt.get('context') != context or receipt.get('scope') != 'window':
                raise RuntimeError('Invalid native rendering lease receipt')
            entry.update(depth=1, purpose=purpose, context=context)
            self.active[key] = entry
            entry['heartbeat'] = asyncio.create_task(self.renew(entry), name='native-rendering-lease-renewal')
            self.record('acquired', context, purpose, task=task, scope=entry['scope'],
                        permanent_safeguard=capability.get('permanentSafeguard'))
            yield
        finally:
            try:
                if entry and entry.get('lease'):
                    # TTL bounds ungraceful disconnects; never end a shared session.
                    await asyncio.shield(self.release(key, entry))
            finally:
                if pool:
                    pool.release()

    async def close(self):
        self.closing = True
        for key, entry in list(self.active.items()):
            await self.release(key, entry)
