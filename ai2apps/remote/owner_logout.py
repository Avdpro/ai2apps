"""Durable logout outbox in the instance-scoped secret backend.

No proof is written to logs, public state, or the browser. An unreadable outbox
is an authority failure, never an empty outbox.
"""
import asyncio
import json
from uuid import UUID

from .security import RemoteTokenError

KEY = 'owner-home-logout-outbox-v1'


class LogoutOutbox:
    def __init__(self, manager):
        self.manager = manager
        self.lock = asyncio.Lock()
        self.task = None

    def read(self):
        try:
            raw = self.manager.secret_backend.load(KEY)
        except KeyError:
            return {}
        except Exception:
            raise RemoteTokenError('Owner logout storage unavailable') from None
        try:
            entries = json.loads(raw)
            if not isinstance(entries, dict):
                raise ValueError()
            for sid, entry in entries.items():
                if str(UUID(sid)) != sid or str(UUID(entry['deviceId'])) != entry['deviceId']:
                    raise ValueError()
                proof = entry['refreshToken']
                if not isinstance(proof, str) or len(proof) != 43:
                    raise ValueError()
            return entries
        except Exception:
            raise RemoteTokenError('Owner logout storage unavailable') from None

    def write(self, entries):
        try:
            self.manager.secret_backend.store(KEY, json.dumps(entries))
        except Exception:
            raise RemoteTokenError('Owner logout could not be saved') from None

    def pending(self):
        try:
            return bool(self.read())
        except Exception:
            return True

    async def drain(self):
        entries = self.read()
        for sid, entry in list(entries.items()):
            device = self.manager.require_device(entry['deviceId'])
            await self.manager._request('POST', f'/v1/internal/owner-home/sessions/{sid}/revoke',
                device=device, json={'refreshToken': entry['refreshToken']})
            del entries[sid]
            self.write(entries)  # A failed write keeps the idempotent request pending.

    def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.retry())

    async def retry(self):
        delay = 5
        while True:
            await asyncio.sleep(delay)
            try:
                async with self.lock:
                    await self.drain()
                return
            except Exception:
                delay = min(delay * 2, 60)

    async def barrier(self):
        # Caller holds lock. Even a successful drain invalidates handoffs issued
        # before delivery, so this request must not continue with its old handoff.
        if self.pending():
            self.start()
            raise RemoteTokenError('Owner logout is pending; reconnect after confirmation')

    def close(self):
        if self.task:
            self.task.cancel()
            self.task = None
