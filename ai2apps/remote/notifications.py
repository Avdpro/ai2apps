"""Owner notification producer. The outbox, never the memory bus, owns replay.

Trusted business services can enqueue inside their own PlatformDatabase transaction.
Only negotiated, validated presentation snapshots and opaque references are persisted; never credentials.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from contextlib import suppress
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)
KINDS = {
    'task.completed': ('task_completed', 'task'),
    'task.failed': ('task_failed', 'task'),
    'action.required': ('action_required', 'task'),
    'message.received': ('message_received', 'conversation'),
    'system.notice': ('system_notice', 'system_notice'),
    'intelligence.updated': ('intelligence_updated', 'intelligence_channel'),
}


INTELLIGENCE_CAPABILITY = {
    'kind': 'intelligence.updated', 'template': 'intelligence_updated',
    'target_type': 'intelligence_channel', 'app_id': 'ai2apps.intelligence',
    'template_params': ['channel_name', 'new_article_count', 'headlines', 'refresh_status'],
    'metadata': ['run_id', 'system_task_id'], 'version': 1,
}


class NotificationProducer:
    def __init__(self, remote):
        logger.info("Notification producer contract 1.3.0 loaded from %s", __file__)
        self.remote = remote
        self.database = remote.repository.database
        self._task = None
        self._lock = asyncio.Lock()
        self._policy_checked = 0.0
        self._policy_identity = None
        self._policy_value = None
        self._sources = []
        self._delivery_guards = []

    def register_source(self, source):
        """Register a trusted synchronous business reconciler, not client code."""
        self._sources.append(source)

    def register_delivery_guard(self, guard):
        """Trusted owner guard: recheck queued references before sending/retrying."""
        self._delivery_guards.append(guard)

    def identity(self):
        repo = self.remote.identity_repository
        installation = repo.get_installation() if repo else None
        if not installation or installation.status != 'active':
            raise ValueError('请先将此 Desktop 绑定到 Cloud 账户')
        device = self.remote.require_device(installation.cloud_device_id)
        if device.status != 'active':
            raise ValueError('Desktop 设备凭据不可用，请重新登录或绑定')
        return {
            'installation_id': installation.id,
            'device_id': device.device_id,
            'owner_id': installation.core_user_id,
            'access_epoch': installation.access_epoch,
            'device_epoch': device.access_epoch,
            'credential_version': device.credential_version,
            'cloud_origin': self.remote.cloud.base_url,
        }

    @staticmethod
    def _encoded(value):
        return json.dumps(value, sort_keys=True, separators=(',', ':'))

    def enqueue(self, *, event_id, kind, target_id, app_id=None, result_count=None,
                connection=None, expected_owner_id=None, template_params=None, metadata=None):
        """Only trusted host services may call this; their resource ACL comes first.

        Pass the business transaction's connection for atomic terminal-event/outbox
        commit. A stable event_id makes retries idempotent, including after restart.
        """
        if not isinstance(event_id, str) or not re.fullmatch(r'[-a-zA-Z0-9_.:]{1,160}', event_id):
            raise ValueError('Invalid notification event id')
        if kind not in KINDS:
            raise ValueError('Invalid notification kind')
        for value, maximum in [(target_id, 256), (app_id, 160)]:
            if value is None and maximum == 160:
                continue
            if not isinstance(value, str) or not 1 <= len(value) <= maximum or re.search(r'[\x00-\x1f\x7f]', value):
                raise ValueError('Invalid opaque notification reference')
        if result_count is not None and (type(result_count) is not int or not 0 <= result_count <= 1000000):
            raise ValueError('Invalid result count')
        if kind == 'intelligence.updated':
            if not self.supports_intelligence() or app_id != 'ai2apps.intelligence' or result_count is not None:
                raise ValueError('Intelligence notification capability unavailable')
            if not isinstance(template_params, dict) or set(template_params) != {'channel_name', 'new_article_count', 'headlines', 'refresh_status'}:
                raise ValueError('Invalid intelligence parameters')
            def plain(value, maximum):
                return isinstance(value, str) and 1 <= len(value) <= maximum and value.strip() and not re.search(r'[<>\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]', value)
            if (not plain(template_params['channel_name'], 80)
                    or type(template_params['new_article_count']) is not int
                    or not 1 <= template_params['new_article_count'] <= 1000000
                    or template_params['refresh_status'] not in ('completed', 'partial', 'failed')
                    or not isinstance(template_params['headlines'], list)
                    or len(template_params['headlines']) > 2
                    or not all(plain(v, 100) for v in template_params['headlines'])):
                raise ValueError('Invalid intelligence parameters')
            if not isinstance(metadata, dict) or set(metadata) - {'run_id', 'system_task_id'} or not all(plain(v, 160 if k == 'run_id' else 256) for k, v in metadata.items()):
                raise ValueError('Invalid intelligence references')
        elif template_params is not None or metadata is not None:
            raise ValueError('Unexpected notification parameters')
        current_identity = self.identity()
        if expected_owner_id is not None and current_identity['owner_id'] != expected_owner_id:
            raise ValueError('Notification resource does not belong to the Installation Owner')
        identity = self._encoded(current_identity)
        target = {'type': KINDS[kind][1], 'id': target_id}
        if app_id is not None:
            target['app_id'] = app_id
        static = {'schema_version': 1, 'event_id': event_id, 'kind': kind,
                  'target': target, 'template': KINDS[kind][0],
                  'metadata': {} if result_count is None else {'result_count': result_count}}
        if kind == 'intelligence.updated':
            static['template_params'] = template_params
            static['metadata'] = metadata
        return self._enqueue_static(static, connection=connection, expected_owner_id=expected_owner_id)

    def enqueue_custom(self, *, event_id, content, target, group_key=None, metadata=None,
                       connection=None, expected_owner_id=None):
        """Trusted host only: caller registration/ACL must be checked before this method."""
        from .custom_notifications import fields
        if not isinstance(event_id,str) or not re.fullmatch(r'[-a-zA-Z0-9_.:]{1,160}',event_id):
            raise ValueError('Invalid notification event id')
        normalized = fields(content,target,group_key,metadata)
        static = {'schema_version':1,'event_id':event_id,'kind':'app.custom',**normalized}
        # Existing events remain replayable without current capability negotiation.
        if connection is not None:
            exists = connection.execute('SELECT 1 FROM notification_producer_outbox WHERE event_id=?',(event_id,)).fetchone()
        else:
            with self.database.transaction() as c:
                exists = c.execute('SELECT 1 FROM notification_producer_outbox WHERE event_id=?',(event_id,)).fetchone()
        if not exists and not self.supports_custom(normalized['target']['type']):
            raise ValueError('Custom notification capability unavailable')
        return self._enqueue_static(static,connection=connection,expected_owner_id=expected_owner_id)

    def supports_custom(self, target_type):
        from .custom_notifications import supports
        try:
            current = self._encoded(self.identity())
        except (ValueError,RuntimeError):
            return False
        policy = self._policy_value or {}
        return (self._policy_identity==current and time.time()-self._policy_checked<120
                and policy.get('enabled') is True
                and any(supports(c,target_type) for c in policy.get('event_capabilities',[])))

    def _enqueue_static(self, static, *, connection=None, expected_owner_id=None):
        current_identity = self.identity()
        if expected_owner_id is not None and current_identity['owner_id']!=expected_owner_id:
            raise ValueError('Notification resource does not belong to the Installation Owner')
        identity = self._encoded(current_identity)
        event_id = static['event_id']
        def insert(c):
            old = c.execute('SELECT identity_json,body_json FROM notification_producer_outbox WHERE event_id=?', (event_id,)).fetchone()
            if old:
                original = json.loads(old['body_json'])
                if old['identity_json'] != identity or (set(original)-{'occurred_at','expires_at'} != set(static) or any(original.get(k) != v for k, v in static.items())):
                    raise ValueError('Notification event id already belongs to another event or identity')
                return event_id
            now = time.time()
            count = c.execute("SELECT count(*) FROM notification_producer_outbox WHERE state IN ('queued','retry','authorization_required','credentials_required')").fetchone()[0]
            if count >= 1000:
                raise ValueError('通知队列已满，请先处理待发送通知')
            iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            body = {**static, 'occurred_at': iso(now), 'expires_at': iso(now + 86400)}
            if len(json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > 32768:
                raise ValueError('Notification request too large')
            paused = c.execute("SELECT state,error_code FROM notification_producer_outbox WHERE identity_json=? AND state IN ('authorization_required','credentials_required') ORDER BY created_at DESC LIMIT 1", (identity,)).fetchone()
            c.execute('INSERT INTO notification_producer_outbox(event_id,identity_json,body_json,expires_at,created_at,state,error_code) VALUES (?,?,?,?,?,?,?)',
                      (event_id, identity, self._encoded(body), now + 86400, now,
                       paused['state'] if paused else 'queued', paused['error_code'] if paused else None))
            return event_id
        if connection is not None:
            return insert(connection)
        with self.database.transaction(write=True) as c:
            return insert(c)

    def has_event(self, event_id, owner_id):
        identity = self.identity()
        if identity['owner_id'] != owner_id:
            return False
        with self.database.transaction() as c:
            row = c.execute('SELECT identity_json FROM notification_producer_outbox WHERE event_id=?', (event_id,)).fetchone()
        return bool(row and all(json.loads(row['identity_json']).get(k) == identity[k]
                               for k in ('owner_id', 'installation_id', 'device_id', 'cloud_origin')))

    def supports_intelligence(self):
        try:
            current = self._encoded(self.identity())
        except (ValueError, RuntimeError):
            return False
        policy = self._policy_value or {}
        return (self._policy_identity == current and time.time() - self._policy_checked < 120
                and policy.get('enabled') is True
                and INTELLIGENCE_CAPABILITY in policy.get('event_capabilities', []))

    def status(self):
        try:
            identity = self.identity()
            error = None
        except (ValueError, RuntimeError) as exc:
            identity, error = None, str(exc)
        with self.database.transaction() as c:
            rows = [] if identity is None else c.execute('SELECT event_id,state,attempts,next_attempt,created_at,notification_id,error_code FROM notification_producer_outbox WHERE identity_json=? ORDER BY created_at DESC LIMIT 20', (self._encoded(identity),)).fetchall()
        return {'installation_id': identity['installation_id'] if identity else None,
                'device_id': identity['device_id'] if identity else None,
                'ready': identity is not None, 'error': error,
                'producer_policy': self._policy_value if identity and self._policy_identity == self._encoded(identity) else None,
                'items': [dict(row) for row in rows]}

    def resume(self):
        identity = self._encoded(self.identity())
        with self.database.transaction(write=True) as c:
            c.execute("UPDATE notification_producer_outbox SET state='queued',next_attempt=0,error_code=NULL WHERE identity_json=? AND state IN ('authorization_required','credentials_required')", (identity,))

    async def _send(self, identity, body):
        device = self.remote.require_device(identity['device_id'])
        if device.credential_expires_at.timestamp() <= time.time():
            return 401, {}, None
        secret = self.remote.secret_backend.load(device.secret_backend_key)
        # Independent cookie-free transport: Device auth never inherits browser sessions.
        async with httpx.AsyncClient(base_url=self.remote.cloud.base_url, timeout=20,
                                    follow_redirects=False, transport=self.remote.cloud.transport) as client:
            response = await client.post('/api/v1/notifications/events', json=body, headers={
                'Authorization': f'Device {device.device_id}.{secret}',
                'Idempotency-Key': body['event_id'], 'Accept': 'application/json'})
            try:
                data = response.json()
            except ValueError:
                data = {}
            return response.status_code, data if isinstance(data, dict) else {}, response.headers.get('retry-after')

    async def _policy(self, identity):
        device = self.remote.require_device(identity['device_id'])
        secret = self.remote.secret_backend.load(device.secret_backend_key)
        async with httpx.AsyncClient(base_url=self.remote.cloud.base_url, timeout=20,
                                    follow_redirects=False, transport=self.remote.cloud.transport) as client:
            response = await client.get('/api/v1/notifications/producer-policy', headers={
                'Authorization': f'Device {device.device_id}.{secret}', 'Accept': 'application/json'})
            if response.status_code != 200:
                return None
            try:
                value = response.json()
            except ValueError:
                return None
            return value if isinstance(value, dict) else None

    async def refresh_policy(self, *, force=False):
        try:
            current = self.identity()
        except (ValueError, RuntimeError):
            return
        encoded = self._encoded(current)
        now = time.time()
        if self._policy_identity == encoded and now - self._policy_checked < 120:
            return
        with self.database.transaction() as c:
            candidates = c.execute("SELECT event_id,identity_json FROM notification_producer_outbox WHERE expires_at>? AND state IN ('queued','retry','authorization_required','credentials_required')", (now,)).fetchall()
        # Normal sends already receive server policy enforcement. Only discover
        # capability when something is paused or credentials changed.
        if not candidates and not force:
            return
        with self.database.transaction() as c:
            needed = c.execute("SELECT 1 FROM notification_producer_outbox WHERE expires_at>? AND (state IN ('authorization_required','credentials_required') OR (state IN ('queued','retry') AND identity_json<>?)) LIMIT 1", (now, encoded)).fetchone()
        if not needed and not force:
            return
        self._policy_checked, self._policy_identity = now, encoded
        self._policy_value = None
        try:
            policy = await self._policy(current)
        except (httpx.HTTPError, KeyError):
            return
        if not policy or type(policy.get('policy_version')) is not int or policy['policy_version'] < 2:
            return
        if (policy.get('automatic_owner_publish') is not True
                or policy.get('installation_id') != current['installation_id']
                or policy.get('account_id') != current['owner_id']
                or policy.get('credential_version') != current['credential_version']
                or policy.get('access_epoch') != current['access_epoch']):
            return
        # Re-read after network I/O; a late policy response cannot cross identity.
        try:
            if self._encoded(self.identity()) != encoded:
                return
        except (ValueError, RuntimeError):
            return
        self._policy_value = {key: policy.get(key) for key in ('policy_version', 'contract_version', 'event_capabilities', 'automatic_owner_publish', 'enabled', 'reason')}
        if policy.get('enabled') is not True:
            return
        for row in candidates:
            old = json.loads(row['identity_json'])
            if any(old.get(key) != current[key] for key in ('installation_id','device_id','owner_id','cloud_origin')):
                continue
            same = row['identity_json'] == encoded
            rotated = (old.get('credential_version', 0) < current['credential_version']
                       and old.get('access_epoch', 0) <= current['access_epoch']
                       and old.get('device_epoch', 0) <= current['device_epoch'])
            if same or rotated:
                with self.database.transaction(write=True) as c:
                    c.execute("UPDATE notification_producer_outbox SET identity_json=?,state='queued',error_code=NULL WHERE event_id=? AND identity_json=? AND expires_at>? AND state IN ('queued','retry','authorization_required','credentials_required')",
                              (encoded, row['event_id'], row['identity_json'], now))

    async def drain_once(self):
        async with self._lock:
            if self.remote.cloud.offline_mode():
                return
            await self.refresh_policy()
            for source in tuple(self._sources):
                try:
                    await asyncio.to_thread(source)
                except Exception as error:
                    logger.warning('Notification source reconciliation failed (%s)', type(error).__name__)
            now = time.time()
            with self.database.transaction(write=True) as c:
                c.execute("UPDATE notification_producer_outbox SET state='expired' WHERE expires_at<=? AND state IN ('queued','retry','authorization_required','credentials_required')", (now,))
                c.execute("DELETE FROM notification_producer_outbox WHERE created_at<? AND state NOT IN ('queued','retry')", (now - 38 * 86400,))
                rows = c.execute("SELECT * FROM notification_producer_outbox WHERE state IN ('queued','retry') AND next_attempt<=? ORDER BY created_at LIMIT 1", (now,)).fetchall()
            for row in rows:
                try:
                    current = self.identity()
                except (ValueError, RuntimeError):
                    self._finish(row, 'credentials_required', 'identity_unavailable')
                    continue
                if self._encoded(current) != row['identity_json']:
                    old = json.loads(row['identity_json'])
                    same_owner = all(old.get(key) == current[key] for key in ('installation_id','device_id','owner_id','cloud_origin'))
                    if same_owner and old.get('credential_version', 0) < current['credential_version']:
                        self._finish(row, 'credentials_required', 'rotation_policy_pending')
                    else:
                        self._finish(row, 'cancelled', 'identity_changed')
                    continue
                body = json.loads(row['body_json'])
                try:
                    allowed = all([await asyncio.to_thread(guard, body) for guard in tuple(self._delivery_guards)])
                except Exception:
                    self._finish(row, 'retry', 'target_check_unavailable', next_attempt=now + 60)
                    continue
                if not allowed:
                    self._finish(row, 'cancelled', 'target_no_longer_pending')
                    continue
                attempts = row['attempts'] + 1
                try:
                    code, data, retry_after = await self._send(current, body)
                except KeyError:
                    code, data, retry_after = 401, {}, None
                except httpx.HTTPError:
                    code, data, retry_after = 503, {}, None
                if code == 202:
                    try:
                        notification_id = str(UUID(data['notification_id']))
                    except (ValueError, KeyError, TypeError, AttributeError):
                        code = 502
                    else:
                        self._finish(row, 'submitted', None, notification_id=notification_id, attempts=attempts)
                        continue
                if code in (401, 403):
                    state = 'credentials_required' if code == 401 else 'authorization_required'
                    # Stop the whole identity's queue; never probe grant state by spamming events.
                    with self.database.transaction(write=True) as c:
                        c.execute("UPDATE notification_producer_outbox SET state=?,error_code=? WHERE identity_json=? AND state IN ('queued','retry')", (state, f'http_{code}', row['identity_json']))
                    self._finish(row, state, f'http_{code}', attempts=attempts)
                elif code == 429 or code >= 500:
                    delay = min(3600, 5 * 2 ** min(attempts, 10))
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            with suppress(ValueError, TypeError, OverflowError):
                                delay = max(delay, parsedate_to_datetime(retry_after).timestamp() - now)
                    self._finish(row, 'retry' if attempts < 12 else 'failed', f'http_{code}',
                                 attempts=attempts, next_attempt=now + delay)
                    # Respect account/Installation Retry-After for other pending events too.
                    with self.database.transaction(write=True) as c:
                        c.execute("UPDATE notification_producer_outbox SET next_attempt=max(next_attempt,?) WHERE identity_json=? AND state IN ('queued','retry')", (now + delay, row['identity_json']))
                else:
                    self._finish(row, 'conflict' if code == 409 else 'failed', f'http_{code}', attempts=attempts)

    def _finish(self, row, state, error, *, notification_id=None, attempts=None, next_attempt=0):
        with self.database.transaction(write=True) as c:
            c.execute('UPDATE notification_producer_outbox SET state=?,error_code=?,notification_id=?,attempts=?,next_attempt=? WHERE event_id=?',
                      (state, error, notification_id, row['attempts'] if attempts is None else attempts, next_attempt, row['event_id']))

    def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name='ai2apps-notification-producer')

    async def _run(self):
        while True:
            try:
                await self.drain_once()
            except Exception as error:
                # Never log request objects, auth headers, or arbitrary Cloud body text.
                logger.warning('Notification producer iteration failed (%s)', type(error).__name__)
            await asyncio.sleep(2)

    async def stop(self):
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
