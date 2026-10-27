"""Owner App authority. Short signed leases; never a Local login session."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlencode
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.identity import MemberRole, RequestPrincipal
from .security import RemoteTokenError, _decode
from .owner_logout import LogoutOutbox
from .owner_exchange import ExchangeRequests
import httpx
from .mobile_unified import BINDINGS as MOBILE_BINDINGS, PROTOCOL as MOBILE_PROTOCOL, validate_claims, ready as unified_ready, negotiated

PROTOCOL = 'owner-open-home-v1'
APP_HANDOFF_PROTOCOL = 'desktop-mobile-app-handoff-v1'
COOKIE = '__Secure-ai2apps_owner_home'
READY = True
IDS = ('sub','actor_user_id','owner_user_id','device_id','cloud_device_id','installation_id',
       'organization_id','session_id','cloud_session_id','jti')
EPOCHS = ('membership_epoch','access_epoch','account_session_epoch','local_session_epoch',
          'mapping_revision','capability_revision','organization_authorization_version',
          'organization_policy_version','credential_version')
APP_BINDINGS = ('app_handoff_protocol','app_handoff_connection_id','app_handoff_agent')
BINDINGS = tuple(key for key in IDS if key != 'jti') + EPOCHS + ('role','organization_type','scope') + APP_BINDINGS + MOBILE_BINDINGS


def verify(token, jwks, *, audience, now):
    stage = 'token structure'
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError()
        header, claims = [json.loads(_decode(value)) for value in parts[:2]]
        if header.get('alg') != 'EdDSA' or not isinstance(header.get('kid'), str):
            raise ValueError()
        key = next(key for key in jwks['keys'] if key.get('kid') == header['kid'])
        if any(key.get(k) != v for k,v in {'kty':'OKP','crv':'Ed25519','use':'sig','alg':'EdDSA'}.items()):
            raise ValueError()
        stage = 'signature'
        Ed25519PublicKey.from_public_bytes(_decode(key['x'])).verify(_decode(parts[2]), '.'.join(parts[:2]).encode())
        stage = 'identity claims'
        for key in IDS:
            if str(UUID(claims[key])) != claims[key]:
                raise ValueError()
        stage = 'unified Mobile claims'
        validate_claims(claims)
        stage = 'epoch claims'
        for key in EPOCHS:
            # Device-bound paired sessions do not consult the primary mapping.
            paired_mapping=(key=='mapping_revision' and (claims.get('app_handoff_protocol')==APP_HANDOFF_PROTOCOL or claims.get('mobile_access_protocol')==MOBILE_PROTOCOL) and claims[key]==0)
            if type(claims[key]) is not int or (claims[key] < 1 and not paired_mapping):
                raise ValueError()
        stage = 'App handoff claims'
        if any(k in claims for k in APP_BINDINGS):
            if (claims.get('app_handoff_protocol')!=APP_HANDOFF_PROTOCOL or
                str(UUID(claims.get('app_handoff_connection_id','')))!=claims.get('app_handoff_connection_id') or
                type(claims.get('app_handoff_agent')) is not int or claims['app_handoff_agent'] not in (0,1)):
                raise ValueError()
        stage = 'time claims'
        for key in ('iat','nbf','exp'):
            if type(claims[key]) is not int:
                raise ValueError()
        stage = 'scope, binding or lifetime'
        if (claims['iss'] != 'ai2apps-cloud' or claims['aud'] != audience
                or claims['scope'] != 'owner-home:apps' or claims['role'] not in ('core','owner')
                or claims['organization_type'] not in ('household','business')
                or claims['sub'] != claims['actor_user_id'] or claims['sub'] != claims['owner_user_id']
                or claims['device_id'] != claims['cloud_device_id']
                or not 0 < claims['exp'] - claims['iat'] <= 60
                or claims['iat'] > now or claims['nbf'] > now or claims['exp'] <= now):
            raise ValueError()
        return claims
    except Exception as error:
        raise RemoteTokenError('Owner Home assertion rejected: ' + stage) from error


def timestamp(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise RemoteTokenError('Invalid Owner Home deadline')
    try:
        return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (ValueError, OverflowError) as error:
        raise RemoteTokenError('Invalid Owner Home deadline') from error


@dataclass
class LeaseSession:
    claims: dict
    refresh_token: str = field(repr=False)
    deadline: float
    absolute: float
    idle: float
    monotonic_deadline: float
    next_refresh: float
    activity: float | None = None
    revoked: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class OwnerHome:
    def __init__(self, manager):
        self.manager = manager
        self.sessions = {}
        self.urls = {}
        self.capabilities = {}
        self.task = None
        self.logout_outbox = LogoutOutbox(manager)
        self.exchange_requests = ExchangeRequests(manager)

    def current(self, record):
        if record.revoked:
            raise RemoteTokenError('Owner Home session ended')
        device = self.manager.require_device(record.claims['device_id'])
        installation = self.manager.space.installation(device)
        c = record.claims
        if (not device.enabled or device.status != 'active' or not self.manager.space.running(device)
                or device.credential_version != c['credential_version']
                or installation.core_user_id != c['sub'] or installation.id != c['installation_id']
                or installation.organization_id != c['organization_id']
                or installation.organization_type.value != c['organization_type']
                or device.access_epoch != c['access_epoch']):
            raise RemoteTokenError('Owner Home authority changed')
        return device, installation

    def valid(self, record):
        self.current(record)
        if (time.time() >= min(record.deadline, record.absolute, record.idle)
                or time.monotonic() >= record.monotonic_deadline):
            raise RemoteTokenError('Owner Home lease expired')
        return record

    def principal(self, record):
        self.valid(record)
        _, installation = self.current(record)
        c = record.claims
        return RequestPrincipal(actor_user_id=c['sub'], installation_id=c['installation_id'],
            organization_id=c['organization_id'], billing_account_id=installation.billing_account_id,
            role=MemberRole(c['role']), membership_epoch=c['membership_epoch'],
            authentication_type='owner_home_lease', client_scope='owner-home')

    def resume_url(self, device_id):
        """A navigation hint only, enabled by Cloud's explicit recovery contract."""
        if self.logout_outbox.pending():
            return None
        if self.capabilities.get(device_id, {}).get('ownerLoginResumeProtocol') != 'owner-login-resume-v1':
            return None
        device = self.manager.require_device(device_id)
        installation = self.manager.space.installation(device)
        origin = urlsplit(device.public_origin)
        if (origin.scheme != 'https' or origin.username or origin.password or origin.port
                or not re.fullmatch(r'device-[0-9a-f]{32}\.ai2apps\.com', origin.netloc)
                or origin.path or origin.query or origin.fragment):
            return None
        return 'https://coder.ai2apps.com/u/' + str(installation.core_user_id) + '?' + urlencode({
            'entry': 'owner-home', 'resume': '1', 'device_origin': device.public_origin})

    async def declare(self, device):
        async with self.logout_outbox.lock:
            await self.logout_outbox.barrier()
            await self._declare(device)

    async def _declare(self, device):
        result = await self.manager._request('PUT','/v1/internal/spaces/owner-home/device',device=device,
            json={'protocol':PROTOCOL,'enabled':bool(READY),
                  'ownerLoginResumeLogoutProtocol':'owner-login-resume-logout-v1',
                  **({'mobileAccessProtocol':MOBILE_PROTOCOL} if unified_ready() else {})})
        url = result.get('ownerAuthorizationUrl','')
        parsed = urlsplit(url)
        installation = self.manager.space.installation(device)
        if (parsed.scheme != 'https' or parsed.hostname != 'coder.ai2apps.com'
                or parsed.netloc != 'coder.ai2apps.com'
                or parsed.path != '/u/'+installation.core_user_id
                or parsed.query != 'entry=owner-home' or parsed.fragment):
            raise RemoteTokenError('Invalid Owner authorization URL')
        self.urls[device.device_id] = url
        self.capabilities[device.device_id] = result
        logging.getLogger(__name__).info("Owner unified Mobile exchange capability confirmed=%s", negotiated(result))
        logging.getLogger(__name__).info(
            "Owner login resume capability confirmed=%s",
            result.get("ownerLoginResumeProtocol") == "owner-login-resume-v1")

    def apply(self, result, jwks, *, previous=None, initial=None):
        now = time.time()
        c = verify(result['leaseToken'],jwks,audience='ai2apps-owner-home-lease-v1',now=now)
        if result['sessionId'] != c['session_id']:
            raise RemoteTokenError('Owner Home session mismatch')
        if initial is not None and any(initial.get(k) != c.get(k) for k in BINDINGS):
            raise RemoteTokenError('Owner Home member/lease mismatch')
        if previous and any(previous.claims.get(k) != c.get(k) for k in BINDINGS):
            raise RemoteTokenError('Owner Home bindings changed')
        absolute, idle = timestamp(result['absoluteExpiresAt']), timestamp(result['idleExpiresAt'])
        deadline = min(c['exp'],timestamp(result['leaseExpiresAt']),absolute,idle)
        if deadline <= now or absolute > now+28801 or idle > now+1801:
            raise RemoteTokenError('Invalid Owner Home lifetime')
        if previous and (previous.revoked or absolute != previous.absolute or idle < previous.idle):
            raise RemoteTokenError('Owner Home deadlines changed')
        if not previous:
            record = LeaseSession(c,result['refreshToken'],deadline,absolute,idle,
                                  time.monotonic()+deadline-now,time.monotonic()+30)
        else:
            record = previous
            record.claims, record.deadline, record.idle = c, deadline, idle
            record.monotonic_deadline = time.monotonic()+deadline-now
            record.next_refresh = time.monotonic()+30
        self.current(record)
        return record

    async def exchange(self, device, handoff, *, mobile_connection_id=None):
        async with self.logout_outbox.lock:
            await self.logout_outbox.barrier()
            return await self._exchange(device, handoff, mobile_connection_id=mobile_connection_id)

    async def _exchange(self, device, handoff, *, mobile_connection_id=None):
        if not READY:
            raise RemoteTokenError('Owner Home integration is not ready')
        if not re.fullmatch(r'oh1\.[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}',handoff):
            raise RemoteTokenError('Owner Home handoff protocol required')
        installation = self.manager.space.installation(device)
        if len(self.sessions) >= 128:
            raise RemoteTokenError('Owner Home is busy')
        payload={'handoff':handoff}
        if mobile_connection_id is not None:
            if not isinstance(mobile_connection_id,str) or not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',mobile_connection_id):
                raise RemoteTokenError('Invalid pairing connection')
            payload.update(mobileConnectionId=mobile_connection_id,appHandoffProtocol=APP_HANDOFF_PROTOCOL)
        unified = False
        if unified_ready() and mobile_connection_id is not None:
            view = await self.manager.mobile_agent.pairing(device.device_id, mobile_connection_id)
            if view.get('mobileAccessProtocol') == MOBILE_PROTOCOL:
                if not negotiated(view) or view.get('status') not in ('awaiting_exchange','active'):
                    raise RemoteTokenError('Unified Mobile exchange not prepared')
                unified = True
        elif mobile_connection_id is None:
            # Account-entry handoffs use negotiated device capabilities, not browser input.
            unified = negotiated(self.capabilities.get(device.device_id, {}))
        if unified:
            payload['exchangeRequestId'] = self.exchange_requests.request_id(device.device_id,mobile_connection_id,handoff)
        for attempt in range(2 if unified else 1):
            try:
                result = await self.manager._request('POST',f'/v1/internal/installations/{installation.id}/member-handoffs/exchange',
                    device=device,json=payload)
                break
            except httpx.TransportError:
                if not unified or attempt:raise
                # Same persisted ID and exact body only; never retry a business call.

        if 'appHandoff' in result and mobile_connection_id is None:
            raise RemoteTokenError('Paired App handoff requires connection binding')
        if result.get('protocol') != PROTOCOL or not re.fullmatch(r'[A-Za-z0-9_-]{43}', result.get('refreshToken','')):
            raise RemoteTokenError('Owner Home exchange protocol mismatch')
        jwks = await self.manager._request('GET','/v1/installation-auth/jwks.json')
        member = verify(result['accessToken'],jwks,audience='ai2apps-installation-member-v1',now=time.time())
        if mobile_connection_id is None and any(k in member for k in APP_BINDINGS):
            raise RemoteTokenError('Signed paired handoff cannot downgrade')
        record = self.apply(result,jwks,initial=member)
        if record.claims['device_id'] != device.device_id:
            raise RemoteTokenError('Owner Home receiver device mismatch')
        if mobile_connection_id is not None:
            signed={'app_handoff_protocol':APP_HANDOFF_PROTOCOL,'app_handoff_connection_id':mobile_connection_id}
            if any(record.claims.get(k)!=v for k,v in signed.items()) or type(record.claims.get('app_handoff_agent')) is not int:
                raise RemoteTokenError('Signed App handoff binding mismatch')
            binding=result.get('appHandoff',{})
            expected={'protocol':APP_HANDOFF_PROTOCOL,'connectionId':mobile_connection_id,
                'deviceId':device.device_id,'installationId':installation.id,'actorUserId':record.claims['actor_user_id']}
            if not isinstance(binding,dict) or any(binding.get(k)!=v for k,v in expected.items()) or type(binding.get('agent')) is not bool:
                raise RemoteTokenError('App handoff pairing binding mismatch')
            if record.claims['app_handoff_agent']!=int(binding['agent']):
                raise RemoteTokenError('Signed App handoff Agent mismatch')
            if binding['agent']:
                agent=self.manager.mobile_agent
                if agent.require(device.device_id)['active']!=mobile_connection_id:
                    raise RemoteTokenError('App handoff Agent ACK is not active')
        if member.get('mobile_access_protocol') == MOBILE_PROTOCOL:
            if not unified or not negotiated(result):
                raise RemoteTokenError('Unified Mobile exchange contract mismatch')
            receipt = result.get('commitReceipt', {})
            self.manager.mobile_agent.apply_unified_receipt(device.device_id,receipt,
                connection=mobile_connection_id,session=record.claims['session_id'],claims=record.claims)
        elif unified:
            raise RemoteTokenError('Unified Mobile signed binding missing')
        previous_records = [item for item in self.sessions.values() if item.claims['session_id'] == record.claims['session_id']]
        if previous_records:
            if not unified or result.get('replayed') is not True:
                raise RemoteTokenError('Owner Home session replay')
            # The replay was authenticated again by Cloud. Replace only the same
            # session with identical binding and deadlines, never an expired/revoked one.
            for previous in previous_records:
                if (previous.revoked or any(previous.claims.get(k)!=record.claims.get(k) for k in BINDINGS)
                        or previous.absolute!=record.absolute or previous.idle!=record.idle):
                    raise RemoteTokenError('Unified Mobile replay binding changed')
            for previous in previous_records:self.drop(previous)

        token = secrets.token_urlsafe(32)
        self.sessions[hashlib.sha256(token.encode()).hexdigest()] = record
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.maintain())
        return token, record

    async def refresh(self, record):
        async with record.lock:
            if record not in self.sessions.values():
                raise RemoteTokenError('Owner Home session ended')
            try:
                device,_ = self.current(record)
            except Exception:
                self.drop(record)
                raise
            if time.time() >= min(record.absolute,record.idle):
                self.drop(record)
                raise RemoteTokenError('Owner Home authorization expired')
            activity = record.activity
            body = {'refreshToken':record.refresh_token}
            if activity is not None:
                body['lastActivityAt'] = datetime.fromtimestamp(activity,timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
            try:
                result = await self.manager._request('POST',f"/v1/internal/owner-home/sessions/{record.claims['session_id']}/refresh",
                    device=device,json=body)
                jwks = await self.manager._request('GET','/v1/installation-auth/jwks.json')
                if record.revoked or not any(item is record for item in self.sessions.values()):
                    raise RemoteTokenError('Owner Home session ended')
                self.apply(result,jwks,previous=record)
                if record.activity == activity:
                    record.activity = None
            except Exception as error:
                if isinstance(error, RemoteTokenError) or getattr(error,'status_code',0) in (400,401,403,409):
                    self.drop(record)
                record.next_refresh = time.monotonic()+5
                raise

    async def authorize(self, token):
        record = self.sessions.get(hashlib.sha256((token or '').encode()).hexdigest())
        if record is None:
            raise RemoteTokenError('Owner Home session required')
        try:
            return self.valid(record)
        except RemoteTokenError:
            await self.refresh(record)
            return self.valid(record)

    def drop(self, record):
        record.revoked = True
        self.sessions = {k:v for k,v in self.sessions.items() if v is not record}
        record.deadline = 0
        record.monotonic_deadline = 0

    def clear(self):
        self.logout_outbox.close()
        for record in list(self.sessions.values()):
            self.drop(record)
        if self.task is not None:
            self.task.cancel()
            self.task = None

    async def revoke(self, record):
        async with self.logout_outbox.lock:
            entries = self.logout_outbox.read()
            entries[record.claims['session_id']] = {
                'deviceId': record.claims['device_id'], 'refreshToken': record.refresh_token}
            # Persist before removing the only available proof or browser cookie.
            self.logout_outbox.write(entries)
            for item in list(self.sessions.values()):
                if (item.claims['device_id'] == record.claims['device_id']
                        and item.claims['cloud_session_id'] == record.claims['cloud_session_id']):
                    self.drop(item)
            self.drop(record)
            try:
                await self.logout_outbox.drain()
            except Exception:
                self.logout_outbox.start()
                return {'cloudConfirmed': False, 'revocationPending': True}
            return {'cloudConfirmed': True, 'revocationPending': False}

    async def maintain(self):
        while self.sessions:
            await asyncio.sleep(1)
            for record in list(self.sessions.values()):
                if time.monotonic() >= record.next_refresh:
                    try:
                        await self.refresh(record)
                    except Exception:
                        pass  # No secret-bearing exception logging; deadline remains authoritative.
