"""Anonymous Cloud visitor assertions. Never creates a Local principal."""
import json
import uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from ai2apps.core import utc_now
from .security import RemoteTokenError, _decode

PROTOCOL = 'personal-space-anonymous-v1'
AUDIENCE = 'ai2apps-anonymous-visitor-v1'


def verify(token, jwks, bindings, *, session=False):
    try:
        head, body, signature = token.split('.')
        header, claims = json.loads(_decode(head)), json.loads(_decode(body))
        if header.get('alg') != 'EdDSA' or header.get('typ') != 'JWT' or not isinstance(header.get('kid'),str):
            raise ValueError('algorithm')
        keys = [k for k in jwks.get('keys', []) if k.get('kid') == header.get('kid')]
        if len(keys) != 1 or any(keys[0].get(k) != v for k, v in
                                {'kty':'OKP','crv':'Ed25519','use':'sig','alg':'EdDSA'}.items()):
            raise ValueError('key')
        Ed25519PublicKey.from_public_bytes(_decode(keys[0]['x'])).verify(
            _decode(signature), (head+'.'+body).encode('ascii'))
        constants = dict(iss='ai2apps-cloud', aud='ai2apps-anonymous-visitor-session-v1' if session else AUDIENCE, protocol='personal-space-anonymous-session-v1' if session else PROTOCOL,
                         access_mode='anonymous', scope='personal-space:visit')
        fields = set(constants) | set(bindings) | {'sub','jti','iat','nbf','exp'}
        if session:
            fields |= {'session_id','lease_version','absolute_expires_at','idle_expires_at'}
        if set(claims) != fields or any(claims.get(k) != v for k,v in {**constants,**bindings}.items()):
            raise ValueError('binding')
        for field in ('jti','owner_user_id','device_id','installation_id'):
            if str(uuid.UUID(claims[field])) != claims[field]:
                raise ValueError('identity')
        if claims['sub'] != 'anonymous:'+claims['session_id' if session else 'jti']:
            raise ValueError('subject')
        for field in ('access_epoch','mapping_revision','capability_revision','space_epoch','published_revision'):
            if type(claims[field]) is not int or claims[field] < 1:
                raise ValueError('epoch')
        if session:
            if str(uuid.UUID(claims['session_id'])) != claims['session_id']:
                raise ValueError('session')
            for field in ('lease_version','credential_version','absolute_expires_at','idle_expires_at'):
                if type(claims[field]) is not int or claims[field] < 1:
                    raise ValueError('session lifetime')
        now = int(utc_now().timestamp())
        if (any(type(claims[k]) is not int for k in ('iat','nbf','exp'))
                or claims['iat'] != claims['nbf']
                or (not 0 < claims['exp']-claims['iat'] <= 120 if session else claims['exp']-claims['iat'] != 120)
                or (session and not claims['exp'] <= claims['idle_expires_at'] <= claims['absolute_expires_at'])
                or not claims['iat'] <= now < claims['exp']):
            raise ValueError('lifetime')
        return claims
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, InvalidSignature) as exc:
        raise RemoteTokenError('Anonymous visitor assertion rejected') from exc
