"""Server-only anonymous session proof and single-flight Cloud lease renewal."""
import asyncio
import hashlib
import secrets
import time
import uuid
from datetime import datetime, timezone
import httpx
from .anonymous_space import verify
from .security import RemoteTokenError

PROTOCOL = 'personal-space-anonymous-session-v1'


class LeaseUnavailable(Exception):
    pass


class VisitorSessions:
    def __init__(self, space):
        self.space = space
        self.records = {}

    @staticmethod
    def key(token):
        return hashlib.sha256((token or '').encode()).hexdigest()

    def revoke(self, device_id=None):
        for key, record in list(self.records.items()):
            if device_id is None or record['claims']['device_id'] == device_id:
                record['revoked'] = True
                self.records.pop(key, None)

    def check(self, record, device):
        claims = record['claims']
        inst = self.space.installation(device)
        state = self.space.visitor_settings(device)
        if (record.get('revoked') or time.time() >= min(claims['absolute_expires_at'],claims['idle_expires_at'])
                or not device.enabled or device.status != 'active' or not self.space.running(device)
                or inst.id != claims['installation_id'] or inst.core_user_id != claims['owner_user_id']
                or device.device_id != claims['device_id'] or device.access_epoch != claims['access_epoch']
                or device.credential_version != claims['credential_version']
                or not state['enabled'] or state['published'] is None
                or state['epoch']+1 != claims['space_epoch'] or state['revision']+1 != claims['published_revision']):
            record['revoked'] = True
            raise RemoteTokenError('Visitor session ended')

    def accept(self, payload, jwks, bindings, previous=None):
        if payload.get('protocol') != PROTOCOL:
            raise RemoteTokenError('Visitor session protocol rejected')
        claims = verify(payload.get('leaseToken',''), jwks, bindings, session=True)
        if (payload.get('sessionId') != claims['session_id'] or payload.get('leaseVersion') != claims['lease_version']
                or payload.get('spaceUrl') != 'https://coder.ai2apps.com/u/'+claims['owner_user_id']):
            raise RemoteTokenError('Visitor session response rejected')
        if previous and (claims['session_id'] != previous['session_id']
                or claims['lease_version'] <= previous['lease_version']
                or claims['absolute_expires_at'] != previous['absolute_expires_at']):
            raise RemoteTokenError('Visitor lease rollback rejected')
        if claims['absolute_expires_at'] > claims['iat']+28800 or claims['idle_expires_at'] > claims['iat']+1800:
            raise RemoteTokenError('Visitor session lifetime rejected')
        return claims

    async def exchange(self, device, handoff):
        from .visitor_space import app_gateway_ready
        if not app_gateway_ready():
            raise RemoteTokenError('Visitor session unavailable')
        # Enforce current Local publication before asking Cloud to consume the code.
        settings = self.space.visitor_settings(device)
        inst = self.space.installation(device)
        if not settings['enabled'] or settings['published'] is None or not self.space.running(device):
            raise RemoteTokenError('Visitor space unavailable')
        for key,r in list(self.records.items()):
            if r.get('revoked') or time.time() >= min(r['claims']['absolute_expires_at'],r['claims']['idle_expires_at']):
                self.records.pop(key,None)
        if len(self.records) >= 100:
            raise LeaseUnavailable('Visitor capacity exceeded')
        manager = self.space.manager
        cap = self.space.anonymous_capabilities.get(device.device_id,{})
        if cap.get('_local_epoch') != settings['epoch'] or cap.get('_local_revision') != settings['revision']:
            await self.space.declare(device)
            cap = self.space.anonymous_capabilities.get(device.device_id,{})
        mapping = await manager._request('GET','/v1/public/spaces/'+inst.core_user_id)
        bindings = dict(owner_user_id=inst.core_user_id, device_id=device.device_id, installation_id=inst.id,
            access_epoch=device.access_epoch, credential_version=device.credential_version,
            mapping_revision=mapping.get('mappingRevision'), capability_revision=cap.get('visitorRevision'),
            space_epoch=settings['epoch']+1,published_revision=settings['revision']+1)
        payload = await manager._request('POST','/v1/internal/spaces/visitor/sessions/exchange',device=device,json={'handoff':handoff})
        jwks = await manager._request('GET','/v1/remote/jwks.json')
        claims = self.accept(payload,jwks,bindings)
        proof=payload.get('refreshToken')
        if not isinstance(proof,str) or not 32 <= len(proof) <= 512:
            raise RemoteTokenError('Visitor session proof rejected')
        record=dict(claims=claims,proof=proof,bindings=bindings,lock=asyncio.Lock(),last_activity=time.time(),
                    next_attempt=0,pending=None,revoked=False)
        self.check(record,manager.require_device(device.device_id))
        token=secrets.token_urlsafe(32)
        self.records[self.key(token)] = record
        return token,claims

    async def authorize(self, device, token, activity=False):
        record=self.records.get(self.key(token))
        if record is None:
            return self.space.authorize(device,token)  # Never upgrade a legacy Cookie.
        manager=self.space.manager
        async with record['lock']:
            self.check(record,manager.require_device(device.device_id))
            now=time.time();old=record['claims']
            report_activity=activity and now-record['last_activity'] >= 60
            if now >= record['next_attempt'] and (old['exp']-now <= 60 or report_activity):
                if record['pending'] is None:
                    body={'refreshToken':record['proof'],'requestId':str(uuid.uuid4()),'expectedLeaseVersion':old['lease_version']}
                    if report_activity:
                        body['lastActivityAt']=datetime.fromtimestamp(now,timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
                    record['pending']=body
                try:
                    payload=await manager._request('POST','/v1/internal/spaces/visitor/sessions/'+old['session_id']+'/refresh',device=device,json=record['pending'])
                    jwks=await manager._request('GET','/v1/remote/jwks.json')
                    claims=self.accept(payload,jwks,record['bindings'],old)
                    self.check(record,manager.require_device(device.device_id))
                    record['claims']=claims
                    if 'lastActivityAt' in record['pending']:
                        record['last_activity']=now
                    record['pending']=None
                    record['next_attempt']=now+30
                except Exception as error:
                    from .manager import RemoteAccessError
                    if isinstance(error,RemoteTokenError):
                        record['revoked']=True
                        raise
                    if not isinstance(error,(httpx.HTTPError,RemoteAccessError)):
                        raise
                    status=getattr(error,'status_code',503)
                    if status==409 and getattr(error,'code','')=='VISITOR_REQUEST_EXPIRED':
                        version=getattr(error,'details',{}).get('leaseVersion')
                        if type(version) is int and version >= old['lease_version']:
                            record['pending']={'refreshToken':record['proof'],'requestId':str(uuid.uuid4()),'expectedLeaseVersion':version}
                        else:
                            record['revoked']=True
                            raise RemoteTokenError('Visitor lease conflict') from None
                    elif status < 500 and status != 429:
                        record['revoked']=True
                        raise RemoteTokenError('Visitor session ended') from None
                    try:delay=max(5,float(getattr(error,'retry_after',None) or 10))
                    except (ValueError,TypeError):
                        from email.utils import parsedate_to_datetime
                        try:delay=max(5,parsedate_to_datetime(error.retry_after).timestamp()-now)
                        except (ValueError,TypeError,AttributeError):delay=30
                    record['next_attempt']=now+delay
            self.check(record,manager.require_device(device.device_id))
            if record['claims']['exp'] <= time.time():
                raise LeaseUnavailable('Visitor connection is recovering')
            return record['claims']
