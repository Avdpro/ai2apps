"""desktop-mobile-agent-v1 byte contracts; no credentials or transport."""
import base64
import hashlib
import json
import re
from uuid import UUID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from .security import RemoteTokenError

PROTOCOL='desktop-mobile-agent-v1'
AUDIENCE='ai2apps-desktop-approved-agent-v1'

def decode(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',value):
        raise RemoteTokenError('Invalid base64url')
    return base64.urlsafe_b64decode(value+'='*(-len(value)%4))

def uuid(value):
    try:
        valid=isinstance(value,str) and str(UUID(value))==value
    except (ValueError,AttributeError):valid=False
    if not valid:raise RemoteTokenError('Invalid UUID')
    return value

def public_key(jwk):
    if not isinstance(jwk,dict) or set(jwk)!={'crv','kty','x','y'} or jwk['crv']!='P-256' or jwk['kty']!='EC':
        raise RemoteTokenError('P-256 public key required')
    x,y=decode(jwk['x']),decode(jwk['y'])
    if len(x)!=32 or len(y)!=32:raise RemoteTokenError('Invalid public key coordinates')
    try:key=ec.EllipticCurvePublicNumbers(int.from_bytes(x,'big'),int.from_bytes(y,'big'),ec.SECP256R1()).public_key()
    except ValueError as error:raise RemoteTokenError('Invalid curve point') from error
    canonical=json.dumps({k:jwk[k] for k in ('crv','kty','x','y')},separators=(',',':')).encode()
    jkt=base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b'=').decode()
    return key,jkt

def verify_proof(jwk,message,signature):
    try:
        key,_=public_key(jwk);raw=decode(signature)
        if len(raw)!=64:raise ValueError()
        key.verify(encode_dss_signature(int.from_bytes(raw[:32],'big'),int.from_bytes(raw[32:],'big')),message.encode(),ec.ECDSA(hashes.SHA256()))
    except Exception as error:raise RemoteTokenError('Mobile Agent proof invalid') from error

def local_input(connection,jti,method,target,body,nonce):
    if '\n' in target or '\r' in target or not target.startswith('/') or target.startswith('//'):
        raise RemoteTokenError('Invalid signed target')
    return '\n'.join(('ai2apps-mobile-agent-local-v1',connection,jti,method.upper(),target,hashlib.sha256(body).hexdigest(),nonce))

def verify_lease(token,jwks,now):
    try:
        head,payload,signature=token.split('.')
        header=json.loads(decode(head));claims=json.loads(decode(payload))
        if header.get('alg')!='EdDSA' or not isinstance(header.get('kid'),str) or any(k in header for k in ('jku','jwk','x5u')):raise ValueError()
        key=next(k for k in jwks['keys'] if k.get('kid')==header.get('kid') and all(k.get(a)==b for a,b in {'kty':'OKP','crv':'Ed25519','alg':'EdDSA','use':'sig'}.items()))
        ed25519.Ed25519PublicKey.from_public_bytes(decode(key['x'])).verify(decode(signature),(head+'.'+payload).encode())
        for k in ('sub','actor_user_id','owner_user_id','device_id','installation_id','organization_id','mobile_connection_id','session_id','enforcer_instance_id','jti'):uuid(claims[k])
        for k in ('membership_epoch','access_epoch','credential_version','local_session_epoch','account_session_epoch','organization_authorization_version','organization_policy_version','authorization_generation'):
            if type(claims[k]) is not int or claims[k]<1:raise ValueError()
        if any(type(claims[k]) is not int for k in ('iat','nbf','exp')):raise ValueError()
        if not 0<claims['exp']-claims['iat']<=60 or claims['iat']>now or claims['nbf']>now or claims['exp']<=now:raise ValueError()
        if any(claims.get(k)!=v for k,v in {'iss':'ai2apps-cloud','aud':AUDIENCE,'protocol':PROTOCOL,'scope':'agent:invoke'}.items()):raise ValueError()
        if claims['sub']!=claims['actor_user_id'] or claims['sub']!=claims['owner_user_id']:raise ValueError()
        if claims['role'] not in ('core','owner') or claims['organization_type'] not in ('household','business'):raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}',claims['client_jkt']) or claims['cnf']!={'jkt':claims['client_jkt']}:raise ValueError()
        return claims
    except Exception as error:raise RemoteTokenError('Mobile Agent lease rejected') from error
