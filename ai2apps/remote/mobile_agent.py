"""Desktop-approved logical Mobile connections, fenced before any Agent action."""
import asyncio
from dataclasses import replace
from datetime import datetime
import hashlib
import json
import secrets
import time
from uuid import uuid4
from ai2apps.identity import IdentityRepository
from .security import RemoteTokenError
from .mobile_unified import PROTOCOL as UNIFIED_PROTOCOL, ready as unified_ready, COMMIT_MODE, negotiated
from .mobile_agent_crypto import PROTOCOL,uuid,public_key,verify_lease,verify_proof,local_input

ROOT='/v1/internal/mobile-agent'

def deadline(value):
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except Exception as error:raise RemoteTokenError('Invalid Cloud deadline') from error

class MobileAgent:
    def __init__(self,manager):
        self.manager=manager;self.database=manager.repository.database
        self.instance=str(uuid4());self.lock=asyncio.Lock();self.ready=set();self.leases={};self.nonces={};self.pairings={};self.revocations=set();self.rates={};self.challenges={};self.clocks={}
        with self.database.transaction(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS mobile_agent_fences(device_id TEXT PRIMARY KEY,enabled INTEGER NOT NULL,generation INTEGER NOT NULL,instance TEXT NOT NULL,active TEXT,pending TEXT)')
        # No saved lease or old instance is accepted after process construction.
    def now(self,device):
        clock=self.clocks.get(device)
        if clock is None:raise RemoteTokenError('Agent Cloud clock not synchronized')
        return clock[0]+time.monotonic()-clock[1]
    def rate(self,key,limit=120):
        now=time.monotonic();bucket=self.rates.get(key)
        if bucket is None or bucket[0]+60<now:bucket=[now,0];self.rates[key]=bucket
        bucket[1]+=1
        if bucket[1]>limit:raise RemoteTokenError('Mobile Agent rate limited')
        if len(self.rates)>2048:self.rates={k:v for k,v in self.rates.items() if v[0]+60>=now}
    def row(self,device):
        with self.database.transaction() as db:r=db.execute('SELECT * FROM mobile_agent_fences WHERE device_id=?',(device,)).fetchone()
        return dict(r) if r else dict(device_id=device,enabled=0,generation=0,instance=self.instance,active=None,pending=None)
    def fence(self,device,*,enabled,generation,active=None,pending=None):
        old=self.row(device)
        if generation<old['generation']:raise RemoteTokenError('Agent generation rollback rejected')
        with self.database.transaction(write=True) as db:
            db.execute('INSERT INTO mobile_agent_fences VALUES(?,?,?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET enabled=excluded.enabled,generation=excluded.generation,instance=excluded.instance,active=excluded.active,pending=excluded.pending',
                (device,int(enabled),generation,self.instance,active,pending))
        for cid,record in list(self.leases.items()):
            if record['claims']['device_id']==device and (cid!=active or record['claims']['authorization_generation']!=generation):self.leases.pop(cid,None)
    async def call(self,device,method,path,body=None):
        record=self.manager.require_device(device)
        installation=self.manager.space.installation(record)
        if installation.cloud_device_id!=record.device_id:raise RemoteTokenError('Agent target Installation mismatch')
        value=await self.manager._request(method,ROOT+path,device=record,server_time=True,**({'json':body} if body is not None else {}))
        clock=value.pop('_server_time',None)
        if not isinstance(clock,(int,float)):raise RemoteTokenError('Cloud time unavailable')
        self.clocks[device]=(clock,time.monotonic())
        return value
    async def configure(self,device,enabled):
        async with self.lock:
            self.ready.discard(device);old=self.row(device)
            self.fence(device,enabled=enabled,generation=old['generation'])
            if enabled and not old['enabled'] and old['generation']>0 and old['instance']==self.instance:
                reset=await self.call(device,'PUT','/device',{'protocol':PROTOCOL,'enabled':False,'enforcerInstanceId':self.instance})
                self.fence(device,enabled=True,generation=reset['generation'])
            result=await self.call(device,'PUT','/device',{'protocol':PROTOCOL,'enabled':enabled,'enforcerInstanceId':self.instance})
            if result.get('protocol')!=PROTOCOL or result.get('enforcerInstanceId')!=self.instance:raise RemoteTokenError('Agent capability mismatch')
            self.fence(device,enabled=enabled,generation=result['generation'])
            if enabled:self.ready.add(device)
            return self.status(device)
    async def startup(self):
        for device in self.manager.repository.list():
            if self.row(device.device_id)['enabled']:
                try:await self.configure(device.device_id,True)
                except Exception:self.ready.discard(device.device_id)
    def block_owner(self):
        # A local Core logout cannot be undone by a later Cloud state read.
        for device in self.manager.repository.list():
            r=self.row(device.device_id)
            self.fence(device.device_id,enabled=False,generation=r['generation'])
        self.close()
    def close(self):
        self.ready.clear();self.leases.clear();self.nonces.clear();self.challenges.clear()
    def status(self,device):
        r=self.row(device)
        return {'protocol':PROTOCOL,'enabled':bool(r['enabled']),'ready':device in self.ready,'generation':r['generation'],'enforcerInstanceId':self.instance,'activeConnectionId':r['active'],'pendingConnectionId':r['pending']}
    def require(self,device):
        r=self.row(device)
        if device not in self.ready or not r['enabled'] or r['instance']!=self.instance:raise RemoteTokenError('Mobile Agent is disabled or not synchronized')
        return r
    async def sync(self,device):
        r=self.require(device);value=await self.call(device,'GET','/device')
        if value.get('protocol')!=PROTOCOL or value.get('enforcerInstanceId')!=self.instance:
            self.ready.discard(device);self.leases.clear();raise RemoteTokenError('Agent enforcement instance changed')
        # A prepared generation is durable locally before Cloud commits it at ACK.
        # Reading old committed state must never restore fenced permissions.
        if r['pending'] and value['generation']<=r['generation'] and value.get('activeConnectionId')!=r['pending']:
            return value
        self.fence(device,enabled=True,generation=value['generation'],active=value.get('activeConnectionId'),pending=value.get('pendingConnectionId'))
        return value
    async def create(self,device):
        async with self.lock:
            capabilities=await self.sync(device)
            from .owner_home import APP_HANDOFF_PROTOCOL
            body={'appHandoffProtocol':APP_HANDOFF_PROTOCOL} if capabilities.get('appHandoffProtocol')==APP_HANDOFF_PROTOCOL else {}
            if negotiated(getattr(getattr(self.manager,'owner_home',None),'capabilities',{}).get(device,{})):
                body.update(mobileAccessProtocol=UNIFIED_PROTOCOL,commitMode=COMMIT_MODE)
            value=await self.call(device,'POST','/pairings',body)
            uuid(value['connectionId']);self.pairings[value['connectionId']]=device
            return value
    async def pairing(self,device,connection):
        uuid(connection);self.require(device)
        value=await self.call(device,'GET','/pairings/'+connection)
        if value.get('deviceId')!=device or (not negotiated(value) and value.get('enforcerInstanceId')!=self.instance):raise RemoteTokenError('Pairing binding mismatch')
        self.pairings[connection]=device
        if value.get('mobileAccessProtocol')==UNIFIED_PROTOCOL:
            if not negotiated(value):raise RemoteTokenError('Unified Mobile commit mode required')
            if value.get('status')=='active':
                self.apply_unified_receipt(device,value.get('commitReceipt',{}),connection=connection)
            return {**value,'serverTime':self.now(device)}
        if value['status']=='awaiting_ack' and value['generation']>=self.row(device)['generation']:
            self.fence(device,enabled=True,generation=value['generation'],pending=connection)
        elif value['generation']!=self.row(device)['generation']:
            await self.sync(device)
        return {**value,'serverTime':self.now(device)}
    def apply_unified_receipt(self,device,result,*,connection=None,session=None,claims=None):
        if not negotiated(result) or result.get('status')!='active' or result.get('deviceId')!=device:
            raise RemoteTokenError('Unified Mobile receipt unavailable')
        try:
            for key in ('sessionId','mobileClientId'):
                uuid(result[key])
            if 'connectionId' in result:uuid(result['connectionId'])
            revoked=result['revokedSessionIds']
            if not isinstance(revoked,list):raise ValueError()
            for sid in revoked:uuid(sid)
            if (type(result['disconnectOtherClients']) is not bool or type(result['generation']) is not int
                    or result['generation']<1 or type(result['mobileClientEpoch']) is not int or result['mobileClientEpoch']<1
                    or connection is not None and result.get('connectionId')!=connection
                    or session is not None and result['sessionId']!=session):raise ValueError()
            if claims is not None and (result['mobileClientId']!=claims.get('mobile_client_id') or result['mobileClientEpoch']!=claims.get('mobile_client_epoch')):raise ValueError()
            legacy=result.get('legacyAgentGeneration')
            if legacy is not None and (type(legacy) is not int or legacy<1):raise ValueError()
            if not result['disconnectOtherClients'] and (revoked or legacy is not None):raise ValueError()
        except (KeyError,TypeError,ValueError):
            raise RemoteTokenError('Invalid unified Mobile commit receipt') from None
        # Independent durable generation; never install this as a legacy Agent fence.
        with self.database.transaction(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS mobile_unified_generations(device_id TEXT PRIMARY KEY,generation INTEGER NOT NULL)')
            db.execute('INSERT INTO mobile_unified_generations VALUES(?,?) ON CONFLICT(device_id) DO UPDATE SET generation=MAX(generation,excluded.generation)',(device,result['generation']))
        for record in list(self.manager.owner_home.sessions.values()):
            if record.claims['device_id']==device and record.claims['session_id'] in revoked:
                self.manager.owner_home.drop(record)
        if legacy is not None and legacy>=self.row(device)['generation']:
            self.fence(device,enabled=bool(self.row(device)['enabled']),generation=legacy)

    async def decision(self,device,connection,choice,expected,disconnect_others=False):
        if choice not in ('agent','chat','deny','connect'):raise RemoteTokenError('Invalid Agent decision')
        async with self.lock:
            r=self.require(device);view=await self.pairing(device,connection)
            if choice=='connect' or choice=='deny' and negotiated(view):
                if not negotiated(view) or type(disconnect_others) is not bool:
                    raise RemoteTokenError('Unified Mobile protocol is not available')
                if view['status']=='active':return view
                if view['status'] not in ('pending','awaiting_exchange') or (view['status']=='pending' and self.now(device)>=deadline(view['displayDeadline'])):
                    raise RemoteTokenError('Mobile confirmation expired or changed')
                result=await self.call(device,'POST',f'/pairings/{connection}/decision',{
                    'decision':choice,'expectedGeneration':expected,'enforcerInstanceId':self.instance,
                    'mobileAccessProtocol':UNIFIED_PROTOCOL,'commitMode':COMMIT_MODE,
                    'disconnectOtherClients':disconnect_others if choice=='connect' else False})
                if not negotiated(result) or result.get('status') != ('denied' if choice=='deny' else 'awaiting_exchange'):
                    raise RemoteTokenError('Unified Mobile confirmation is incomplete')
                # Preparation only. No authority, receipt application or legacy fence.
                return result

            if choice=='agent' and view['status']=='awaiting_ack' and self.row(device)['pending']==connection:
                return await self.ack(device,connection,view)
            if choice=='agent' and view['status']=='active' and view.get('agent'):
                await self.sync(device);return view
            if view['status']=='pending' and self.now(device)>=deadline(view['displayDeadline']):raise RemoteTokenError('Desktop confirmation window expired')
            r=self.require(device)
            if r['generation']!=expected:raise RemoteTokenError('Agent generation changed')
            # A lost decision response must never leave old local leases usable.
            if choice=='agent':
                self.fence(device,enabled=True,generation=r['generation'],pending=connection)
            result=await self.call(device,'POST',f'/pairings/{connection}/decision',{'decision':choice,'expectedGeneration':expected,'enforcerInstanceId':self.instance})
            if choice!='agent':return result
            self.fence(device,enabled=True,generation=result['generation'],pending=connection)
            return await self.ack(device,connection,result)
    async def ack(self,device,connection,view=None):
        r=self.require(device)
        view=view or await self.pairing(device,connection)
        if view.get('mobileAccessProtocol')==UNIFIED_PROTOCOL:raise RemoteTokenError('Unified Mobile does not use ACK')
        r=self.require(device)
        if view.get('status')=='active':
            await self.sync(device);return view
        if r['pending']!=connection or view.get('generation')!=r['generation'] or self.now(device)>=deadline(view['approvalDeadline']):
            raise RemoteTokenError('Agent ACK expired or mismatched')
        result=await self.call(device,'POST',f'/pairings/{connection}/ack',{'generation':r['generation'],'enforcerInstanceId':self.instance})
        if result.get('status')!='active' or result.get('generation')!=r['generation']:raise RemoteTokenError('Agent ACK not active')
        self.fence(device,enabled=True,generation=r['generation'],active=connection)
        return result
    async def revoke(self,device):
        async with self.lock:
            r=self.require(device);self.fence(device,enabled=True,generation=r['generation']);self.revocations.add(device)
            value=await self.call(device,'POST','/device/revoke',{'expectedGeneration':r['generation'],'enforcerInstanceId':self.instance})
            self.fence(device,enabled=True,generation=value['generation']);self.revocations.discard(device)
            return self.status(device)
    async def challenge(self,device,connection,action):
        if action not in ('lease','revoke'):raise RemoteTokenError('Invalid proof action')
        async with self.lock:
            await self.sync(device);r=self.require(device)
            if r['active']!=uuid(connection):raise RemoteTokenError('Agent connection is not active')
            value=await self.call(device,'POST',f'/pairings/{connection}/proof-challenges',{'action':action})
            self.challenges[connection]=(action,value['nonce'],value['clientKeyThumbprint'],time.monotonic()+30)
            return value
    async def proof(self,device,connection,action,body):
        if action not in ('lease','revoke'):raise RemoteTokenError('Invalid proof action')
        async with self.lock:
            await self.sync(device);r=self.require(device)
            if r['active']!=uuid(connection):raise RemoteTokenError('Agent connection is not active')
            jwk=body.get('publicKey');_,jkt=public_key(jwk)
            challenge=self.challenges.get(connection)
            if not challenge or challenge[:3]!=(action,body.get('nonce'),jkt) or challenge[3]<=time.monotonic():raise RemoteTokenError('Agent proof challenge mismatch')
            verify_proof(jwk,'\n'.join(('ai2apps-mobile-agent-proof-v1',action,connection,body['nonce'],jkt)),body.get('signature'))
            self.challenges.pop(connection,None)
            if action=='revoke':self.leases.pop(connection,None);self.revocations.add(device)
            value=await self.call(device,'POST',f'/pairings/{connection}/{action}',{'nonce':body.get('nonce'),'signature':body.get('signature')})
            if action=='revoke':
                self.fence(device,enabled=True,generation=value['generation']);self.revocations.discard(device);return {'status':'revoked'}
            jwks=await self.manager._request('GET','/v1/remote/jwks.json')
            claims=verify_lease(value['leaseToken'],jwks,self.now(device))
            if any(claims[k]!=v for k,v in {'device_id':device,'mobile_connection_id':connection,'enforcer_instance_id':self.instance,'authorization_generation':r['generation'],'client_jkt':jkt}.items()):raise RemoteTokenError('Agent lease binding mismatch')
            previous=self.leases.get(connection)
            if previous and any(previous['claims'].get(k)!=v for k,v in claims.items() if k not in ('iat','nbf','exp','jti')):
                self.leases.pop(connection,None);raise RemoteTokenError('Agent lease bindings changed')
            self.current(claims)
            self.leases[connection]={'claims':claims,'jwk':jwk,'deadline':time.monotonic()+max(0,min(claims['exp'],deadline(value['leaseExpiresAt']))-self.now(device))}
            return {'protocol':PROTOCOL,'connectionId':connection,'generation':r['generation'],'jti':claims['jti'],'expiresAt':value['leaseExpiresAt'],'agent':True,'expiresIn':max(0,min(60,claims['exp']-self.now(device)))}
    def current(self,c):
        r=self.require(c['device_id'])
        if c['device_id'] in self.revocations or r['active']!=c['mobile_connection_id'] or r['generation']!=c['authorization_generation'] or c['enforcer_instance_id']!=self.instance:raise RemoteTokenError('Agent connection revoked')
        device=self.manager.require_device(c['device_id']);installation=self.manager.space.installation(device)
        identities=IdentityRepository(self.database);principal=identities.local_principal_for(c['actor_user_id'])
        with self.database.transaction() as db:
            membership=db.execute("SELECT account_session_epoch FROM installation_memberships WHERE installation_id=? AND cloud_user_id=? AND status='active'",(installation.id,c['actor_user_id'])).fetchone()
        if membership is None:raise RemoteTokenError('Agent membership changed')
        expected={'installation_id':installation.id,'organization_id':installation.organization_id,'sub':installation.core_user_id,'access_epoch':device.access_epoch,'credential_version':device.credential_version,'local_session_epoch':installation.local_session_epoch,'membership_epoch':principal.membership_epoch,'role':principal.role.value,'organization_type':installation.organization_type.value,'account_session_epoch':membership['account_session_epoch']}
        if not device.enabled or device.status!='active' or not self.manager.space.running(device) or any(c[k]!=v for k,v in expected.items()):raise RemoteTokenError('Agent identity binding changed')
        # Cloud validates organization versions on every lease; immutable claims are
        # not silently upgraded locally. Local identity/epoch changes fail immediately.
        return replace(principal,authentication_type='desktop_approved_agent',client_scope='mobile-agent')
    def lease(self,connection):
        record=self.leases.get(uuid(connection))
        if not record or self.now(record['claims']['device_id'])>=record['claims']['exp'] or time.monotonic()>=record['deadline']:raise RemoteTokenError('Agent lease expired')
        self.current(record['claims']);return record
    def nonce(self,connection):
        record=self.lease(connection);now=time.monotonic()
        self.nonces={k:v for k,v in self.nonces.items() if v[2]>now}
        if len(self.nonces)>1024:raise RemoteTokenError('Too many Agent requests')
        value=secrets.token_urlsafe(32);self.nonces[hashlib.sha256(value.encode()).digest()]=(connection,record['claims']['jti'],now+30)
        return {'nonce':value,'jti':record['claims']['jti'],'expiresIn':30}
    def authorize(self,connection,nonce,signature,method,target,body):
        record=self.lease(connection);digest=hashlib.sha256(nonce.encode()).digest();saved=self.nonces.pop(digest,None)
        if not saved or saved[:2]!=(connection,record['claims']['jti']) or saved[2]<=time.monotonic():raise RemoteTokenError('Agent request nonce invalid')
        verify_proof(record['jwk'],local_input(connection,record['claims']['jti'],method,target,body,nonce),signature)
        return self.current(record['claims'])
