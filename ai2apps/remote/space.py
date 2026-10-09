"""Strict verification for Cloud personal-space visit assertions.

These assertions never grant a Local member or administrative session.
"""
from __future__ import annotations

import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.core import utc_now
from .security import RemoteTokenError, _decode

SPACE_GATEWAY_READY = False

SPACE_AUDIENCE = 'ai2apps-personal-space-v1'


def verify_space_token(token: str, jwks: dict[str, Any], *, device_id: str,
                       owner_user_id: str, access_epoch: int) -> dict[str, Any]:
    """Validate cryptography, lifetime and exact owner/device binding."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError('JWT structure')
        header, claims = (json.loads(_decode(part)) for part in parts[:2])
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise ValueError('JWT objects')
        if header.get('alg') != 'EdDSA' or not isinstance(header.get('kid'), str):
            raise ValueError('JWT algorithm')
        key = next((key for key in jwks.get('keys', [])
                    if key.get('kid') == header['kid']), None)
        if not key or any(key.get(k) != v for k, v in {
            'kty': 'OKP', 'crv': 'Ed25519', 'use': 'sig', 'alg': 'EdDSA'
        }.items()):
            raise ValueError('JWT key')
        Ed25519PublicKey.from_public_bytes(_decode(key['x'])).verify(
            _decode(parts[2]), '.'.join(parts[:2]).encode('ascii'))
        for field in ('sub', 'jti', 'owner_user_id', 'device_id'):
            if not isinstance(claims.get(field), str) or not claims[field]:
                raise ValueError('JWT identity')
        for field in ('iat', 'nbf', 'exp', 'access_epoch', 'account_session_epoch',
                      'mapping_revision', 'capability_revision'):
            if type(claims.get(field)) is not int or claims[field] < 1:
                raise ValueError('JWT epoch')
        now = int(utc_now().timestamp())
        if (claims.get('iss') != 'ai2apps-cloud'
                or claims.get('aud') != SPACE_AUDIENCE
                or claims.get('scope') != 'personal-space:visit'
                or claims['owner_user_id'] != owner_user_id
                or claims['device_id'] != device_id
                or claims['access_epoch'] != access_epoch
                or claims.get('access_mode') != ('owner' if claims['sub'] == owner_user_id else 'visitor')
                or not 0 < claims['exp'] - claims['iat'] <= 120
                or claims['iat'] > now or claims['nbf'] > now or claims['exp'] <= now):
            raise ValueError('JWT binding or lifetime')
        return claims
    except (KeyError, TypeError, ValueError, UnicodeError, InvalidSignature) as error:
        raise RemoteTokenError('Personal space assertion was rejected') from error


class PersonalSpace:
    """Independent, short-lived visit sessions; no Local principal conversion."""

    def __init__(self, manager):
        self.manager = manager
        self.sessions = {}
        self.used_assertions = {}
        self.anonymous_capabilities = {}
        from .visitor_sessions import VisitorSessions
        self.visitor_sessions = VisitorSessions(self)

    def _prune(self):
        now = int(utc_now().timestamp())
        self.sessions = {key: value for key, value in self.sessions.items() if value['exp'] > now}
        self.used_assertions = {key: expiry for key, expiry in self.used_assertions.items() if expiry > now}

    def installation(self, device):
        repo = self.manager.identity_repository
        value = repo.get_installation() if repo else None
        if (value is None or value.status != 'active'
                or value.cloud_device_id != device.device_id
                or value.access_epoch != device.access_epoch):
            raise RemoteTokenError('Personal space installation is unavailable')
        return value

    async def declare(self, device, enabled=True):
        self.installation(device)
        from .visitor_space import app_gateway_ready
        from .anonymous_space import PROTOCOL
        body = {'protocol': 'personal-space-v1', 'enabled': enabled}
        settings = self.visitor_settings(device)
        if app_gateway_ready():
            body.update(visitorProtocol=PROTOCOL, visitorEnabled=settings['enabled'],
                published=settings['published'] is not None,
                visitorSessionProtocol='personal-space-anonymous-session-v1',
                spaceEpoch=settings['epoch']+1, publishedRevision=settings['revision']+1,
                publishedAppCount=sum(c['kind']=='app' and not c.get('hidden') for c in (settings['published'] or {}).get('cards', [])))
        result = await self.manager._request('PUT', '/v1/internal/spaces/device', device=device, json=body)
        if app_gateway_ready():
            self.anonymous_capabilities[device.device_id] = {**result, '_local_epoch': settings['epoch'], '_local_revision': settings['revision']}
        return result

    def visitor_settings(self, device):
        from .visitor_space import VisitorSpaceStore
        installation = self.installation(device)
        return VisitorSpaceStore(self.manager.repository.database).get(installation.id)

    def running(self, device):
        connector = self.manager.frpc.status()
        return connector.get('running') and connector.get('deviceId') == device.device_id

    async def exchange(self, device, handoff, *, anonymous=False):
        import hashlib
        import secrets
        self._prune()
        installation = self.installation(device)
        if not device.enabled or device.status != 'active' or not self.running(device):
            raise RemoteTokenError('Personal space is stopped')
        settings = self.visitor_settings(device)
        if not settings['enabled']:
            raise RemoteTokenError('Visitor space is closed')
        if len(self.sessions) >= 1024:
            raise RemoteTokenError('Personal space is busy')
        if anonymous:
            from .visitor_space import app_gateway_ready
            from .anonymous_space import verify, PROTOCOL
            if not app_gateway_ready():
                raise RemoteTokenError('Anonymous visitor gateway unavailable')
            capability = self.anonymous_capabilities.get(device.device_id, {})
            if (capability.get('_local_epoch') != settings['epoch'] or capability.get('_local_revision') != settings['revision']):
                await self.declare(device)
                capability = self.anonymous_capabilities.get(device.device_id, {})
            mapping = await self.manager._request('GET', '/v1/public/spaces/'+installation.core_user_id)
            if mapping.get('status') != 'online':
                raise RemoteTokenError('Anonymous visitor space unavailable')
            payload = await self.manager._request('POST', '/v1/internal/spaces/visitor/exchange', device=device, json={'handoff':handoff})
            jwks = await self.manager._request('GET', '/v1/remote/jwks.json')
            if payload.get('protocol') != PROTOCOL or payload.get('spaceUrl') != 'https://coder.ai2apps.com/u/'+installation.core_user_id:
                raise RemoteTokenError('Anonymous visitor response rejected')
            claims = verify(payload.get('accessToken',''), jwks, dict(
                owner_user_id=installation.core_user_id, device_id=device.device_id,
                installation_id=installation.id, access_epoch=device.access_epoch,
                mapping_revision=mapping.get('mappingRevision'), capability_revision=capability.get('visitorRevision'),
                space_epoch=settings['epoch']+1, published_revision=settings['revision']+1))
        else:
            payload = await self.manager._request('POST', '/v1/internal/spaces/exchange',
                device=device, json={'handoff': handoff})
            jwks = await self.manager._request('GET', '/v1/remote/jwks.json')
            claims = verify_space_token(payload.get('accessToken', ''), jwks,
                device_id=device.device_id, owner_user_id=installation.core_user_id,
                access_epoch=device.access_epoch)
        # Recheck after network awaits: Stop, epoch rotation or binding change wins.
        current = self.manager.require_device(device.device_id)
        if not current.enabled or current.status != 'active' or not self.running(current):
            raise RemoteTokenError('Personal space is stopped')
        current_installation = self.installation(current)
        if (current.access_epoch != claims['access_epoch']
                or current_installation.id != installation.id
                or current_installation.core_user_id != claims['owner_user_id']
                or claims['jti'] in self.used_assertions):
            raise RemoteTokenError('Personal space assertion cannot be reused')
        current_settings = self.visitor_settings(current)
        if not current_settings['enabled'] or current_settings['epoch'] != settings['epoch'] or current_settings['revision'] != settings['revision']:
            raise RemoteTokenError('Visitor space changed')
        claims['_space_epoch'] = settings['epoch']
        claims['_published_revision'] = settings['revision']
        self.used_assertions[claims['jti']] = claims['exp']
        token = secrets.token_urlsafe(32)
        self.sessions[hashlib.sha256(token.encode()).hexdigest()] = claims
        return token, claims

    def authorize(self, device, token):
        import hashlib
        self._prune()
        claims = self.sessions.get(hashlib.sha256((token or '').encode()).hexdigest())
        installation = self.installation(device)
        if (not claims or not device.enabled or device.status != 'active' or not self.running(device)
                or claims['device_id'] != device.device_id
                or claims['access_epoch'] != device.access_epoch
                or claims['owner_user_id'] != installation.core_user_id):
            raise RemoteTokenError('Personal space session has expired')
        settings = self.visitor_settings(device)
        if not settings['enabled'] or claims.get('_space_epoch') != settings['epoch'] or claims.get('_published_revision') != settings['revision']:
            raise RemoteTokenError('Visitor space is closed or revoked')
        if claims.get('access_mode') == 'anonymous' and claims['installation_id'] != installation.id:
            raise RemoteTokenError('Visitor space is closed or revoked')
        return claims

    def revoke(self, device_id=None):
        self.visitor_sessions.revoke(device_id)
        self.sessions = {key: value for key, value in self.sessions.items()
                         if device_id is not None and value['device_id'] != device_id}
