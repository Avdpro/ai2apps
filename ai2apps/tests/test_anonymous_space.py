import json
import unittest
from unittest.mock import patch
from ai2apps.tests.test_personal_space import SpaceTests, enc
from ai2apps.remote.anonymous_space import verify, PROTOCOL
from ai2apps.remote.security import RemoteTokenError


class AnonymousTests(SpaceTests):
    def anonymous(self):
        owner='10000000-0000-0000-0000-000000000001'
        device='20000000-0000-0000-0000-000000000001'
        installation='30000000-0000-0000-0000-000000000001'
        jti='40000000-0000-0000-0000-000000000001'
        self.bindings=dict(owner_user_id=owner,device_id=device,installation_id=installation,
            access_epoch=1,mapping_revision=2,capability_revision=3,space_epoch=2,published_revision=2)
        self.claims={k:v for k,v in self.claims.items() if k in ('iat','exp')}
        self.claims.update(self.bindings,iss='ai2apps-cloud',aud='ai2apps-anonymous-visitor-v1',
            protocol=PROTOCOL,scope='personal-space:visit',access_mode='anonymous',sub='anonymous:'+jti,jti=jti,nbf=self.claims['iat'])

    def anonymous_token(self):
        data=enc(json.dumps({'alg':'EdDSA','typ':'JWT','kid':'test'}).encode())+'.'+enc(json.dumps(self.claims).encode())
        return data+'.'+enc(self.key.sign(data.encode()))

    def test_anonymous_strict_claims(self):
        self.anonymous()
        self.assertEqual(verify(self.anonymous_token(),self.jwks,self.bindings)['access_mode'],'anonymous')
        for key,value in [('aud','ai2apps-personal-space-v1'),('sub',self.bindings['owner_user_id']),('exp',self.claims['exp']+1),('space_epoch',3),('installation_id',self.bindings['device_id']),('access_epoch',True),('nbf',self.claims['iat']-1)]:
            old=self.claims[key];self.claims[key]=value
            with self.subTest(key=key),self.assertRaises(RemoteTokenError):verify(self.anonymous_token(),self.jwks,self.bindings)
            self.claims[key]=old
        self.claims['account_session_epoch']=1
        with self.assertRaises(RemoteTokenError):verify(self.anonymous_token(),self.jwks,self.bindings)

    async def test_anonymous_session_replay_publication_and_close(self):
        self.anonymous();inst=self.manager.identity_repository.get_installation()
        inst.id=self.bindings['installation_id'];inst.core_user_id=self.bindings['owner_user_id'];inst.cloud_device_id=self.bindings['device_id'];self.device.device_id=inst.cloud_device_id
        self.manager.frpc.status=lambda:{'running':True,'deviceId':self.device.device_id}
        service=self.manager.space
        service.anonymous_capabilities[self.device.device_id]={'_local_epoch':1,'_local_revision':1,'visitorRevision':3}
        async def request(method,path,**kwargs):
            if path.endswith('jwks.json'):return self.jwks
            if path.startswith('/v1/public/'):return {'status':'online','mappingRevision':2}
            self.assertEqual(path,'/v1/internal/spaces/visitor/exchange')
            return {'protocol':PROTOCOL,'spaceUrl':'https://coder.ai2apps.com/u/'+inst.core_user_id,'accessToken':self.anonymous_token()}
        self.manager._request=request
        with patch('ai2apps.remote.visitor_space.app_gateway_ready',return_value=True):
            token,_=await service.exchange(self.device,'handoff',anonymous=True)
            self.assertEqual(service.authorize(self.device,token)['access_mode'],'anonymous')
            with self.assertRaises(RemoteTokenError):await service.exchange(self.device,'handoff',anonymous=True)
            prior=service.visitor_settings(self.device);service.visitor_settings=lambda _:dict(prior,revision=2)
            with self.assertRaises(RemoteTokenError):service.authorize(self.device,token)
            service.visitor_settings=lambda _:dict(prior,enabled=False)
            with self.assertRaises(RemoteTokenError):service.authorize(self.device,token)

    async def test_declaration_explicit_publication_zero_apps(self):
        service=self.manager.space
        settings=service.visitor_settings(self.device)
        calls=[]
        async def request(method,path,**kwargs):
            calls.append(kwargs['json']);return {**kwargs['json'],'visitorRevision':1}
        self.manager._request=request
        with patch('ai2apps.remote.visitor_space.app_gateway_ready',return_value=True):
            await service.declare(self.device)
            self.assertIs(calls[-1]['published'],True)
            self.assertEqual(calls[-1]['publishedAppCount'],0)
            self.assertEqual(calls[-1]['publishedRevision'],2)
            service.visitor_settings=lambda _:dict(settings,published=None,revision=0,enabled=False)
            await service.declare(self.device)
            self.assertIs(calls[-1]['published'],False)
            self.assertIs(calls[-1]['visitorEnabled'],False)
            self.assertEqual(calls[-1]['publishedRevision'],1)
