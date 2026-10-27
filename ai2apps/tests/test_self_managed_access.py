from dataclasses import replace
from types import SimpleNamespace
import hashlib
import time

import httpx
import pytest
from fastapi import FastAPI, Request
from ai2apps.identity import RequestPrincipal, MemberRole
from ai2apps.remote.self_managed import SelfManagedAccess, configuration, COOKIE
from ai2apps.web.owner_home_gateway import MARKER


def service(tmp_path):
    actor=RequestPrincipal(actor_user_id='offline.test',installation_id='test',organization_id='offline.test',billing_account_id='offline.test',role=MemberRole.CORE,membership_epoch=1,authentication_type='offline_session')
    runtime=SimpleNamespace(legacy_api_key_principal=lambda:actor)
    value=SelfManagedAccess(runtime,tmp_path/'access.json')
    value.config=configuration(dict(mode='tunnel',bind='127.0.0.1',port=57440,origin='https://desk.example.com'))
    value.server=SimpleNamespace()
    return value


@pytest.mark.parametrize('value',[
    dict(mode='vpn',bind='0.0.0.0',port=57440,origin='http://0.0.0.0:57440'),
    dict(mode='tunnel',bind='192.168.1.2',port=57440,origin='https://desk.example.com'),
    dict(mode='tunnel',bind='127.0.0.1',port=57440,origin='http://desk.example.com'),
    dict(mode='vpn',bind='100.80.1.2',port=57440,origin='http://100.80.1.3:57440'),
    dict(mode='tunnel',bind='127.0.0.1',port=57440,origin='https://user:password@desk.example.com'),
])
def test_invalid_configuration(value):
    with pytest.raises(ValueError): configuration(value)


def test_vpn_cgnat_supported():
    assert configuration(dict(mode='vpn',bind='100.80.1.2',port=57440,origin='http://100.80.1.2:57440'))['mode']=='vpn'


@pytest.mark.asyncio
async def test_pairing_confirmation_boundary_and_revoke(tmp_path):
    access=service(tmp_path)
    target=FastAPI()
    @target.get('/mobile')
    async def mobile(request:Request):
        assert request.scope[MARKER][0] is access
        assert not request.headers.get('authorization')
        assert not request.headers.get('cookie')
        assert not request.headers.get('x-forwarded-host')
        return {'actor':access.principal(request.scope[MARKER][1]).actor_user_id}
    token=access.invite().split('#')[1]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=access.application(target)),base_url=access.config['origin']) as client:
        assert (await client.get('/mobile')).status_code==401
        assert (await client.post('/pair/request',json={'token':token})).status_code==403
        headers={'Origin':access.config['origin']}
        claim=await client.post('/pair/request',json={'token':token,'name':'My Phone'},headers=headers)
        assert claim.status_code==200
        assert (await client.post('/pair/request',json={'token':token},headers=headers)).status_code==401
        proof=claim.json()['proof']
        assert (await client.post('/pair/finish',json={'proof':proof},headers=headers)).status_code==202
        next(iter(access.pending.values()))['approved']=True
        completed=await client.post('/pair/finish',json={'proof':proof},headers=headers)
        assert completed.status_code==200
        assert 'HttpOnly' in completed.headers['set-cookie'] and 'Secure' in completed.headers['set-cookie']
        assert (await client.post('/pair/finish',json={'proof':proof},headers=headers)).status_code==401
        assert (await client.get('/mobile',headers={'Authorization':'Bearer attacker','X-Forwarded-Host':'localhost'})).json()['actor']=='offline.test'
        assert (await client.get('/admin')).status_code==403
        assert (await client.get('/v1/platform/self-managed-access')).status_code==403
        assert (await client.get('/mobile',headers={'Host':'evil.example'})).status_code==403
        await access.revoke(next(iter(access.sessions.values())))
        assert (await client.get('/mobile')).status_code==401


@pytest.mark.asyncio
async def test_expired_invitation(tmp_path):
    access=service(tmp_path); token=access.invite().split('#')[1]
    access.invitations[hashlib.sha256(token.encode()).hexdigest()]=time.time()-1
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=access.application(FastAPI())),base_url=access.config['origin']) as client:
        result=await client.post('/pair/request',json={'token':token},headers={'Origin':access.config['origin']})
    assert result.status_code==401

@pytest.mark.asyncio
async def test_real_offline_mobile_shell_and_catalog(tmp_path, monkeypatch):
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.web import owner_home_gateway
    from omlx.admin import routes
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path, secret_backend='encrypted-file'))
    runtime.start()
    try:
        await runtime.activate_offline()
        access=runtime.self_managed_access
        access.config=configuration(dict(mode='tunnel',bind='127.0.0.1',port=57440,origin='https://desk.example.com'))
        access.server=SimpleNamespace()
        monkeypatch.setattr(routes,'_get_platform_runtime',lambda:runtime)
        monkeypatch.setattr(owner_home_gateway,'_runtime',lambda:runtime)
        app=FastAPI()
        app.include_router(routes.shell_router)
        from ai2apps.web.public_boundary import PublicDeviceBoundary
        app.add_middleware(PublicDeviceBoundary,manager_provider=lambda:runtime.remote)
        token=access.invite().split('#')[1]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=access.application(app)),base_url=access.config['origin']) as client:
            headers={'Origin':access.config['origin']}
            claim=await client.post('/pair/request',json={'token':token},headers=headers)
            next(iter(access.pending.values()))['approved']=True
            assert (await client.post('/pair/finish',json={'proof':claim.json()['proof']},headers=headers)).status_code==200
            shell=await client.get('/mobile')
            assert shell.status_code==200
            assert 'owner_session.js' in shell.text
            catalog=await client.get('/v1/mobile/apps')
            assert catalog.status_code==200, catalog.text
            assert any(item['app_key']=='ai2apps.general-chat' for item in catalog.json()['items'])
            assert (await client.get('/mobile/static/js/mobile.js')).status_code==200
            opened=await client.post('/v1/mobile/apps/ai2apps.general-chat/open',json={},headers=headers)
            assert opened.status_code==200, opened.text
            chat=await client.get('/mobile/chat')
            assert chat.status_code==200, chat.text
            state=await client.get('/v1/mobile/chat/state')
            assert state.status_code==200, state.text
            assert runtime.offline_mode
            assert runtime.remote.repository.list()==()
    finally:
        runtime.stop()

@pytest.mark.asyncio
async def test_desktop_management_requires_local_owner(tmp_path):
    from ai2apps.api.self_managed import create_self_managed_router
    access=service(tmp_path)
    runtime=SimpleNamespace(self_managed_access=access)
    actor=access.owner()
    app=FastAPI()
    app.include_router(create_self_managed_router(lambda:runtime,lambda:actor))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('127.0.0.1',1234)),base_url='http://127.0.0.1') as client:
        assert (await client.get('/self-managed-access')).status_code==200
        assert (await client.post('/self-managed-access/pairing',headers={'Origin':'https://evil.example'})).status_code==403
        actor=replace(actor,authentication_type='owner_home_lease')
        assert (await client.get('/self-managed-access')).status_code==403
    actor=access.owner()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('100.80.1.3',1234)),base_url='http://127.0.0.1') as client:
        assert (await client.get('/self-managed-access')).status_code==403


@pytest.mark.asyncio
async def test_loopback_listener_start_stop(tmp_path):
    import socket
    access=service(tmp_path)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    access.config['port']=port
    access.server=None
    await access.start()
    try:
        async with httpx.AsyncClient() as client:
            assert (await client.get(f'http://127.0.0.1:{port}/pair',headers={'Host':'desk.example.com'})).status_code==200
            assert (await client.get(f'http://127.0.0.1:{port}/pair')).status_code==403
    finally:
        await access.stop()
    assert access.server is None and access.task is None
