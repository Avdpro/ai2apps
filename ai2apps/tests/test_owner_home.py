"""Offline acceptance of the Cloud 1.62 scoped Owner lease contract."""
import asyncio
import base64
import json
import time
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from ai2apps.remote import owner_home as oh
from ai2apps.remote.security import RemoteTokenError
from ai2apps.web.owner_home_gateway import leased_response


def enc(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


class OwnerLeaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = int(time.time())
        self.mono = 1000
        self.clock = patch.object(oh, 'time', SimpleNamespace(time=lambda: self.now, monotonic=lambda: self.mono))
        self.clock.start()
        self.ready = patch.object(oh, 'READY', True)
        self.ready.start()
        self.key = Ed25519PrivateKey.generate()
        self.jwks = {'keys':[dict(kid='test', kty='OKP', crv='Ed25519', use='sig', alg='EdDSA',
            x=enc(self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)))]}
        self.claims = {key: str(uuid4()) for key in oh.IDS}
        self.claims.update({key: 1 for key in oh.EPOCHS})
        self.claims.update(iss='ai2apps-cloud', scope='owner-home:apps', role='core', organization_type='household')
        self.claims.update(actor_user_id=self.claims['sub'], owner_user_id=self.claims['sub'],
            cloud_device_id=self.claims['device_id'])
        self.device = SimpleNamespace(device_id=self.claims['device_id'], enabled=True, status='active', credential_version=1, access_epoch=1)
        self.installation = SimpleNamespace(id=self.claims['installation_id'], core_user_id=self.claims['sub'],
            organization_id=self.claims['organization_id'], organization_type=SimpleNamespace(value='household'), billing_account_id=str(uuid4()))
        self.calls = []
        self.failure = None
        self.idle = self.now+1800
        self.absolute = self.now+28800
        async def request(method, path, **kwargs):
            self.calls.append((method, path, kwargs))
            if path.endswith('/refresh') and self.failure:
                raise self.failure
            if path.endswith('jwks.json'):
                return self.jwks
            if path.endswith('/revoke'):
                return {}
            return self.result()
        self.manager = SimpleNamespace(require_device=lambda _:self.device, _request=request,
            space=SimpleNamespace(installation=lambda _:self.installation, running=lambda _:True))
        self.service = oh.OwnerHome(self.manager)
        self.manager.owner_home = self.service

    async def asyncTearDown(self):
        task = self.service.task
        self.service.clear()
        if task:
            await asyncio.gather(task, return_exceptions=True)
        self.ready.stop()
        self.clock.stop()

    def token(self, audience, changes=None):
        claims = dict(self.claims, aud=audience, iat=self.now, nbf=self.now, exp=self.now+60)
        claims.update(changes or {})
        body = enc(json.dumps({'alg':'EdDSA','kid':'test'}).encode())+'.'+enc(json.dumps(claims).encode())
        return body+'.'+enc(self.key.sign(body.encode()))

    def result(self):
        return dict(protocol=oh.PROTOCOL, sessionId=self.claims['session_id'], refreshToken='s'*43,
            accessToken=self.token('ai2apps-installation-member-v1'), leaseToken=self.token('ai2apps-owner-home-lease-v1'),
            absoluteExpiresAt=stamp(self.absolute), idleExpiresAt=stamp(self.idle), leaseExpiresAt=stamp(self.now+60))

    async def exchange(self):
        return await self.service.exchange(self.device, 'oh1.'+str(uuid4())+'.'+'x'*43)

    async def test_independent_cookie_no_local_session_and_replay(self):
        cookie, record = await self.exchange()
        self.assertNotEqual(cookie, record.refresh_token)
        self.assertNotIn(cookie, self.service.sessions)
        self.assertEqual(await self.service.authorize(cookie), record)
        self.assertEqual(self.service.principal(record).authentication_type, 'owner_home_lease')
        self.assertNotIn(record.refresh_token, repr(record))
        with self.assertRaises(RemoteTokenError):
            await self.exchange()

    async def test_disabled_receiver_does_not_exchange(self):
        with patch.object(oh, 'READY', False), self.assertRaises(RemoteTokenError):
            await self.exchange()
        self.assertEqual(self.calls, [])

    async def test_old_handoff_protocol_rejected(self):
        with self.assertRaises(RemoteTokenError):
            await self.service.exchange(self.device, 'old-mobile-handoff')
        self.assertEqual(self.calls, [])

    def test_claims_fail_closed(self):
        invalid = [('aud','ai2apps-personal-space-v1'), ('scope','personal-space:visit'), ('role','member'),
            ('sub',str(uuid4())), ('device_id',str(uuid4())), ('iat',self.now+1), ('nbf',self.now+1),
            ('exp',self.now), ('exp',self.now+61), ('iss','other')]
        invalid += [(name, True) for name in oh.EPOCHS]
        invalid += [(name, 'invalid') for name in oh.IDS]
        for name, value in invalid:
            with self.subTest(name=name, value=value), self.assertRaises(RemoteTokenError):
                oh.verify(self.token('ai2apps-owner-home-lease-v1', {name:value}), self.jwks,
                    audience='ai2apps-owner-home-lease-v1', now=self.now)

    def test_invalid_signature(self):
        token = self.token('ai2apps-owner-home-lease-v1')
        token = token.rsplit('.',1)[0]+'.'+enc(b'x'*64)
        with self.assertRaises(RemoteTokenError):
            oh.verify(token,self.jwks,audience='ai2apps-owner-home-lease-v1',now=self.now)

    async def test_refresh_omits_activity_and_120_seconds_does_not_end_owner(self):
        _, record = await self.exchange()
        for _ in range(6):
            self.now += 30
            self.mono += 30
            await self.service.refresh(record)
            self.service.valid(record)
        self.assertEqual(record.absolute, self.absolute)
        self.assertEqual(record.idle, self.idle)
        requests = [call for call in self.calls if call[1].endswith('/refresh')]
        self.assertEqual(len(requests),6)
        self.assertTrue(all(set(call[2]['json']) == {'refreshToken'} for call in requests))

    async def test_activity_sent_once(self):
        _, record = await self.exchange()
        record.activity = self.now
        await self.service.refresh(record)
        self.assertIn('lastActivityAt',self.calls[-2][2]['json'])
        await self.service.refresh(record)
        self.assertNotIn('lastActivityAt',self.calls[-2][2]['json'])

    async def test_network_failure_cannot_extend_lease(self):
        _, record = await self.exchange()
        old = record.deadline
        self.failure = httpx.ConnectError('offline')
        with self.assertRaises(httpx.ConnectError):
            await self.service.refresh(record)
        self.assertEqual(record.deadline, old)
        self.now = old
        with self.assertRaises(RemoteTokenError):
            self.service.valid(record)

    async def test_monotonic_deadline_survives_wall_clock_rollback(self):
        _, record = await self.exchange()
        self.now -= 1000
        self.mono += 60
        with self.assertRaises(RemoteTokenError):
            self.service.valid(record)

    async def test_expired_short_lease_can_recover_only_online(self):
        cookie, record = await self.exchange()
        self.now += 61
        self.mono += 61
        self.assertIs(await self.service.authorize(cookie), record)

    async def test_idle_deadline_is_terminal(self):
        cookie, record = await self.exchange()
        self.now = record.idle
        with self.assertRaises(RemoteTokenError):
            await self.service.authorize(cookie)
        self.assertTrue(record.revoked)

    async def test_absolute_deadline_is_terminal_despite_activity(self):
        cookie, record = await self.exchange()
        record.idle = record.absolute + 1800
        self.now = record.absolute
        record.activity = self.now
        with self.assertRaises(RemoteTokenError):
            await self.service.authorize(cookie)
        self.assertTrue(record.revoked)

    async def test_permanent_refresh_rejection_ends_current_lease(self):
        from ai2apps.remote import RemoteAccessError
        for status in (401,403,409):
            self.claims['session_id'] = str(uuid4())
            _, record = await self.exchange()
            self.failure = RemoteAccessError(status,'REVOKED','Access revoked')
            with self.assertRaises(RemoteAccessError):
                await self.service.refresh(record)
            self.assertTrue(record.revoked)
            self.failure = None

    async def test_revoke_and_device_changes_are_terminal(self):
        _, record = await self.exchange()
        self.device.access_epoch += 1
        with self.assertRaises(RemoteTokenError):
            await self.service.refresh(record)
        self.assertTrue(record.revoked)
        self.assertEqual(self.service.sessions,{})

    async def test_refresh_binding_change_rejected(self):
        _, record = await self.exchange()
        self.claims['account_session_epoch'] += 1
        with self.assertRaises(RemoteTokenError):
            await self.service.refresh(record)
        self.assertTrue(record.revoked)

    async def test_revoke_during_refresh_cannot_resurrect(self):
        _, record = await self.exchange()
        old_request = self.manager._request
        async def revoke_while_waiting(method,path,**kwargs):
            if path.endswith('/refresh'):
                self.service.drop(record)
            return await old_request(method,path,**kwargs)
        self.manager._request = revoke_while_waiting
        with self.assertRaises(RemoteTokenError):
            await self.service.refresh(record)
        with self.assertRaises(RemoteTokenError):
            self.service.valid(record)
        self.assertFalse(self.service.sessions)

    async def test_wrong_device_receiver_rejected(self):
        wrong = SimpleNamespace(device_id=str(uuid4()))
        with self.assertRaises(RemoteTokenError):
            await self.service.exchange(wrong, 'oh1.'+str(uuid4())+'.'+'x'*43)
        self.assertFalse(self.service.sessions)


class StreamDeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_silent_stream_producer_cancelled_on_expiry(self):
        record = SimpleNamespace(deadline=time.time()+.05)
        cancelled = asyncio.Event()
        messages = []
        def valid(_):
            if time.time() >= record.deadline:
                raise RemoteTokenError('expired')
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.set()
        async def send(message): messages.append(message)
        async def receive(): return {'type':'http.request','body':b''}
        await asyncio.wait_for(leased_response(app,{'type':'http'},receive,send,SimpleNamespace(valid=valid),record),1)
        self.assertTrue(cancelled.is_set())
        self.assertEqual(messages[-1], {'type':'http.response.body','body':b'','more_body':False})

    async def test_revoked_response_cannot_send_private_bytes(self):
        record = SimpleNamespace(deadline=time.time()+60, revoked=False)
        messages = []
        def valid(_):
            if record.revoked:
                raise RemoteTokenError('revoked')
        async def app(scope,receive,send):
            await send({'type':'http.response.start','status':200,'headers':[]})
            record.revoked = True
            await send({'type':'http.response.body','body':b'private'})
        async def send(message): messages.append(message)
        async def receive(): return {'type':'http.request','body':b''}
        await leased_response(app,{'type':'http'},receive,send,SimpleNamespace(valid=valid),record)
        self.assertFalse(any(message.get('body') == b'private' for message in messages))
        self.assertEqual(messages[-1]['more_body'],False)
