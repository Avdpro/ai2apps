import base64
import json
import unittest
from types import SimpleNamespace
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from ai2apps.core import utc_now
from ai2apps.remote.space import verify_space_token, PersonalSpace
from ai2apps.remote.security import RemoteTokenError, verify_remote_token
from ai2apps.web.space_routes import create_space_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def enc(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()

class SpaceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.jwks = {'keys':[{'kid':'test', 'kty':'OKP', 'crv':'Ed25519', 'use':'sig', 'alg':'EdDSA',
                             'x':enc(self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))}]}
        now = int(utc_now().timestamp())
        self.claims = dict(iss='ai2apps-cloud', aud='ai2apps-personal-space-v1', sub='owner',
            owner_user_id='owner', device_id='device', access_epoch=1, account_session_epoch=1,
            mapping_revision=1, capability_revision=1, access_mode='owner', scope='personal-space:visit',
            jti='unique', iat=now, nbf=now-5, exp=now+120)
        self.device = SimpleNamespace(device_id='device', enabled=True, status='active', access_epoch=1,
                                      public_origin='https://device.example')
        installation = SimpleNamespace(id='installation', status='active', cloud_device_id='device', access_epoch=1, core_user_id='owner')
        async def request(method, path, **kwargs):
            return self.jwks if path.endswith('jwks.json') else {'accessToken':self.token()}
        self.manager = SimpleNamespace(identity_repository=SimpleNamespace(get_installation=lambda:installation),
            require_device=lambda _:self.device, _request=request,
            frpc=SimpleNamespace(status=lambda:{'running':True,'deviceId':'device'}),
            repository=SimpleNamespace(list=lambda:[self.device]),
            owner_home=SimpleNamespace(urls={}))
        self.manager.space = PersonalSpace(self.manager)
        self.manager.space.visitor_settings = lambda device: {'enabled': True, 'epoch': 1,
            'revision': 1, 'published': {'title': 'Test', 'description': '', 'theme': 'violet', 'cards': []}}

    def token(self):
        data = enc(json.dumps({'alg':'EdDSA','kid':'test'}).encode())+'.'+enc(json.dumps(self.claims).encode())
        return data+'.'+enc(self.key.sign(data.encode()))

    def verify(self):
        return verify_space_token(self.token(), self.jwks, device_id='device', owner_user_id='owner', access_epoch=1)

    def test_owner_and_visitor(self):
        self.assertEqual(self.verify()['access_mode'],'owner')
        self.claims.update(sub='visitor', access_mode='visitor')
        self.assertEqual(self.verify()['sub'],'visitor')

    def test_invalid_bindings(self):
        for key,value in [('aud','ai2apps-remote-mobile-v1'),('owner_user_id','other'),('device_id','other'),
                          ('access_epoch',2),('scope','admin'),('access_mode','visitor'),('account_session_epoch',True)]:
            old=self.claims[key]
            with self.subTest(key=key),self.assertRaises(RemoteTokenError):
                self.claims[key]=value
                self.verify()
            self.claims[key]=old

    def test_expiry(self):
        self.claims['exp']=int(utc_now().timestamp())-1
        with self.assertRaises(RemoteTokenError): self.verify()

    def test_cannot_be_mobile_token(self):
        with self.assertRaises(RemoteTokenError):
            verify_remote_token(self.token(),self.jwks,device_id='device',access_epoch=1)

    async def test_replay_and_stop(self):
        token,claims=await self.manager.space.exchange(self.device,'handoff')
        self.assertEqual(self.manager.space.authorize(self.device,token)['sub'],'owner')
        with self.assertRaises(RemoteTokenError): await self.manager.space.exchange(self.device,'handoff')
        self.device.enabled=False
        with self.assertRaises(RemoteTokenError): self.manager.space.authorize(self.device,token)

    async def test_epoch_change_and_revoke(self):
        token,_=await self.manager.space.exchange(self.device,'handoff')
        self.device.access_epoch=2
        with self.assertRaises(RemoteTokenError): self.manager.space.authorize(self.device,token)
        self.device.access_epoch=1
        self.manager.space.revoke()
        with self.assertRaises(RemoteTokenError): self.manager.space.authorize(self.device,token)

    def test_member_receiver_sets_only_scoped_owner_cookie(self):
        import time
        from fastapi.responses import HTMLResponse
        async def exchange_owner(device, handoff):
            self.assertIs(device, self.device)
            return 'opaque-owner-cookie', SimpleNamespace(absolute=time.time()+28800)
        self.manager.owner_home = SimpleNamespace(exchange=exchange_owner, urls={})
        app = FastAPI()
        app.include_router(create_space_router(lambda:self.manager, mobile_renderer=lambda request:HTMLResponse('Mobile Home')))
        with TestClient(app, base_url='https://device.example') as client:
            self.assertEqual(client.get('/mobile/member/complete').text, 'Mobile Home')
            self.assertEqual(client.post('/v1/mobile/member-session/exchange',json={'handoff':'x'*30}).status_code,403)
            response = client.post('/v1/mobile/member-session/exchange', json={'handoff':'x'*30},
                                   headers={'Origin':'https://device.example'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(set(response.json()), {'connected'})
            self.assertIn('__Secure-ai2apps_owner_home=',response.headers['set-cookie'])
            self.assertIn('HttpOnly',response.headers['set-cookie'])
            self.assertIn('Secure',response.headers['set-cookie'])
            self.assertIn('SameSite=strict',response.headers['set-cookie'])
            self.assertNotIn('ai2apps_local_session',response.headers['set-cookie'])

    def test_router_host_origin_and_isolation(self):
        app=FastAPI(); app.include_router(create_space_router(lambda:self.manager))
        with TestClient(app,base_url='https://device.example') as client:
            self.assertEqual(client.get('/mobile/space/complete').status_code,200)
            self.assertEqual(client.get('/mobile/space/complete',headers={'host':'attacker.example'}).status_code,404)
            self.assertEqual(client.post('/v1/mobile/space/exchange',json={'handoff':'x'*30}).status_code,403)
            self.assertEqual(client.get('/v1/mobile/space/bootstrap').status_code,401)
            response=client.post('/v1/mobile/space/exchange',json={'handoff':'x'*30},headers={'origin':'https://device.example'})
            self.assertEqual(response.status_code,200)
            self.assertIn('HttpOnly',response.headers['set-cookie'])
            self.assertIn('Secure',response.headers['set-cookie'])
            self.assertEqual(client.get('/v1/mobile/space/bootstrap').json()['mode'],'owner')
            self.assertEqual(client.get('/v1/mobile/space/bootstrap').json()['entries'],[])
            self.assertEqual(client.get('/v1/mobile/apps').status_code,404)
            self.assertEqual(client.get('/admin').status_code,404)
            self.device.enabled=False
            self.assertEqual(client.get('/v1/mobile/space/bootstrap').status_code,401)

if __name__=='__main__': unittest.main()

class PublicBoundaryTests(unittest.TestCase):
    def setUp(self):
        from ai2apps.web.public_boundary import PublicDeviceBoundary
        device=SimpleNamespace(public_origin='https://device.example')
        async def authorize(_): return None
        manager=SimpleNamespace(repository=SimpleNamespace(list=lambda:[device]),authorize_session=authorize)
        app=FastAPI()
        @app.get('/{path:path}')
        async def deliberately_unprotected(path): return {'sensitive':True}
        @app.websocket('/ws')
        async def websocket(ws): await ws.accept()
        app.add_middleware(PublicDeviceBoundary,manager_provider=lambda:manager)
        self.client=TestClient(app,base_url='https://device.example')

    def test_sensitive_paths_denied_even_with_cookies_and_key(self):
        for path in ['/admin','/admin/api/settings','/apps/ai2apps.account','/v1/platform/cloud/auth/me',
                     '/v1/chat/completions','/mcp','/docs','/openapi.json','/mobile','/v1/mobile/apps',
                     '/mobile/%2e%2e/admin','/mobile//../admin']:
            with self.subTest(path=path):
                response=self.client.get(path,headers={'authorization':'Bearer fake','cookie':'__Secure-ai2apps_space=fake; ai2apps_session=fake'})
                self.assertEqual(response.status_code,403)

    def test_spoofed_forwarded_host_cannot_open_admin(self):
        self.assertEqual(self.client.get('/admin',headers={'x-forwarded-host':'localhost','x-forwarded-for':'127.0.0.1'}).status_code,403)
        self.assertEqual(self.client.get('/mobile/space/home',headers={'host':'unknown.example'}).status_code,403)

    def test_local_and_explicit_public_entry(self):
        self.assertEqual(self.client.get('/admin',headers={'host':'127.0.0.1:8000'}).status_code,200)
        self.assertEqual(self.client.get('/mobile/space/home').status_code,200)

    def test_websocket_is_denied(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/ws'): pass
