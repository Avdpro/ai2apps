import asyncio
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from ai2apps.tests import test_personal_space as legacy
from ai2apps.remote.visitor_sessions import VisitorSessions, PROTOCOL, LeaseUnavailable
from ai2apps.remote.security import RemoteTokenError
from ai2apps.remote.manager import RemoteAccessError


class SessionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        fixture=legacy.SpaceTests();fixture.setUp();self.key=fixture.key;self.jwks=fixture.jwks
        self.manager=fixture.manager;self.space=self.manager.space;self.service=self.space.visitor_sessions
        owner='10000000-0000-0000-0000-000000000001';device='20000000-0000-0000-0000-000000000001';installation='30000000-0000-0000-0000-000000000001';self.sid='40000000-0000-0000-0000-000000000001'
        self.device=fixture.device;self.device.device_id=device;self.device.credential_version=1
        inst=self.manager.identity_repository.get_installation();inst.id=installation;inst.core_user_id=owner;inst.cloud_device_id=device
        self.manager.frpc.status=lambda:{'running':True,'deviceId':device}
        self.space.anonymous_capabilities[device]={'_local_epoch':1,'_local_revision':1,'visitorRevision':3}
        self.bindings=dict(owner_user_id=owner,device_id=device,installation_id=installation,access_epoch=1,credential_version=1,mapping_revision=2,capability_revision=3,space_epoch=2,published_revision=2)
        self.started=int(time.time());self.calls=[];self.fail=None;self.close_during_refresh=False
        async def request(method,path,**kwargs):
            if path.endswith('jwks.json'):return self.jwks
            if '/public/spaces/' in path:return {'mappingRevision':2,'status':'online'}
            if path.endswith('/exchange'):return self.payload(1,proof=True)
            self.calls.append(kwargs['json'].copy());await asyncio.sleep(0)
            if self.close_during_refresh:self.service.revoke()
            if self.fail:raise self.fail
            return self.payload(kwargs['json']['expectedLeaseVersion']+1)
        self.manager._request=request

    def payload(self,version,proof=False):
        now=int(time.time());claims={**self.bindings,'iss':'ai2apps-cloud','aud':'ai2apps-anonymous-visitor-session-v1','protocol':PROTOCOL,'scope':'personal-space:visit','access_mode':'anonymous','sub':'anonymous:'+self.sid,'session_id':self.sid,'jti':f'50000000-0000-0000-0000-{version:012d}','lease_version':version,'iat':now,'nbf':now,'exp':now+120,'absolute_expires_at':self.started+28800,'idle_expires_at':now+1800}
        data=legacy.enc(json.dumps({'alg':'EdDSA','typ':'JWT','kid':'test'}).encode())+'.'+legacy.enc(json.dumps(claims).encode());token=data+'.'+legacy.enc(self.key.sign(data.encode()))
        result={'protocol':PROTOCOL,'sessionId':self.sid,'leaseVersion':version,'leaseToken':token,'spaceUrl':'https://coder.ai2apps.com/u/'+self.bindings['owner_user_id']}
        if proof:result['refreshToken']='p'*43
        return result

    async def start(self):
        with patch('ai2apps.remote.visitor_space.app_gateway_ready',return_value=True):
            token,_=await self.service.exchange(self.device,'handoff')
        return token,self.service.records[self.service.key(token)]

    async def test_single_flight_expired_lease_recovers_same_session(self):
        token,r=await self.start();r['claims']['exp']=time.time()-1
        results=await asyncio.gather(*(self.service.authorize(self.device,token) for _ in range(8)))
        self.assertEqual(len(self.calls),1);self.assertTrue(all(c['session_id']==self.sid and c['lease_version']==2 for c in results))

    async def test_foreground_activity_and_background_no_activity(self):
        token,r=await self.start();r['last_activity']=time.time()-61
        await self.service.authorize(self.device,token,activity=True)
        self.assertIn('lastActivityAt',self.calls[-1]);r['next_attempt']=0;r['claims']['exp']=time.time()+40
        await self.service.authorize(self.device,token)
        self.assertNotIn('lastActivityAt',self.calls[-1])

    async def test_close_in_flight_never_restores(self):
        token,r=await self.start();r['claims']['exp']=time.time()+40;self.close_during_refresh=True
        with self.assertRaises(RemoteTokenError):await self.service.authorize(self.device,token)
        self.assertFalse(self.service.records)

    async def test_transient_failure_retains_request_and_blocks_expired_lease(self):
        token,r=await self.start();r['claims']['exp']=time.time()+40;self.fail=RemoteAccessError(503,'UNAVAILABLE','offline')
        await self.service.authorize(self.device,token);pending=r['pending'].copy()
        r['claims']['exp']=time.time()-1
        with self.assertRaises(LeaseUnavailable):await self.service.authorize(self.device,token)
        r['next_attempt']=0;self.fail=None;await self.service.authorize(self.device,token)
        self.assertEqual(self.calls[-1],pending)

    async def test_idle_expiry_cannot_be_revived_by_reading(self):
        token,r=await self.start();r['claims']['idle_expires_at']=time.time()-1
        with self.assertRaises(RemoteTokenError):await self.service.authorize(self.device,token,activity=True)
        self.assertFalse(self.calls)

    async def test_response_rollback_and_wrong_binding_rejected(self):
        token,r=await self.start()
        with self.assertRaises(RemoteTokenError):self.service.accept(self.payload(1),self.jwks,self.bindings,r['claims'])
        with self.assertRaises(RemoteTokenError):self.service.accept(self.payload(2),self.jwks,dict(self.bindings,credential_version=2),r['claims'])

    def test_route_cookie_lifetime_origin_and_no_proof_leak(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from unittest.mock import AsyncMock
        from ai2apps.web.space_routes import create_space_router
        claims=dict(access_mode='anonymous',protocol=PROTOCOL,exp=int(time.time())+120,
            absolute_expires_at=int(time.time())+28800,idle_expires_at=int(time.time())+1800,
            lease_version=1,owner_user_id=self.bindings['owner_user_id'])
        self.service.exchange=AsyncMock(return_value=('opaque-test',claims))
        self.service.authorize=AsyncMock(return_value=claims)
        app=FastAPI();app.include_router(create_space_router(lambda:self.manager))
        with TestClient(app,base_url=self.device.public_origin) as c:
            self.assertEqual(c.get('/mobile/space/session/complete').status_code,200)
            self.assertEqual(c.post('/v1/mobile/space/bootstrap').status_code,403)
            r=c.post('/v1/mobile/space/exchange',json={'handoff':'x'*40,'protocol':PROTOCOL},headers={'Origin':self.device.public_origin})
            self.assertEqual(r.status_code,200);cookie=r.headers['set-cookie']
            self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=strict',cookie)
            self.assertIn('Max-Age=28800',cookie)
            r=c.post('/v1/mobile/space/bootstrap',headers={'Origin':self.device.public_origin})
            self.assertEqual(r.status_code,200);self.assertNotIn('refreshToken',r.text)
            self.assertEqual(r.json()['sessionProtocol'],PROTOCOL)
            self.assertTrue(self.service.authorize.call_args.kwargs['activity'])
