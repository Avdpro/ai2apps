from types import SimpleNamespace as NS
from uuid import uuid4
import pytest
import httpx
from ai2apps.remote import mobile_unified as protocol
from ai2apps.web import owner_agent_gateway as gateway, owner_home_gateway as owner
from ai2apps.remote.security import RemoteTokenError
from test_mobile_agent_protocol import env


def claims():
    return dict(mobile_access_protocol=protocol.PROTOCOL,mobile_client_id=str(uuid4()),mobile_client_epoch=1)


def test_grant_requires_readiness_and_complete_signed_bindings(monkeypatch):
    c=claims()
    monkeypatch.delenv('AI2APPS_OWNER_MOBILE_UNIFIED_READY',raising=False)
    assert protocol.authorized(c)
    monkeypatch.setenv('AI2APPS_OWNER_MOBILE_UNIFIED_READY','0')
    assert not protocol.authorized(c)
    monkeypatch.setenv('AI2APPS_OWNER_MOBILE_UNIFIED_READY','1')
    assert protocol.authorized(c)
    assert not protocol.authorized({})
    for key in c:
        bad=c.copy();bad.pop(key)
        assert not protocol.authorized(bad)
    for value in [0,True,-1,'1']:
        assert not protocol.authorized({**c,'mobile_client_epoch':value})


def test_unified_routes_are_exact_and_do_not_include_admin_or_key_exchange():
    assert gateway.allowed('POST','/v1/mobile/owner-agent/chat/threads/a/agent-runs')
    assert gateway.allowed('GET','/v1/mobile/owner-agent/models')
    for path in ['connections/a/lease','bootstrap','../admin','http','agent-runs/a/retry']:
        assert not gateway.allowed('POST','/v1/mobile/owner-agent/'+path)


@pytest.mark.asyncio
async def test_unified_gateway_denies_legacy_owner_and_uses_verified_actor(monkeypatch):
    monkeypatch.setenv('AI2APPS_OWNER_MOBILE_UNIFIED_READY','1')
    actor=object();record=NS(claims={});calls=[]
    service=NS(principal=lambda r:actor,valid=lambda r:None)
    monkeypatch.setattr(owner,'authority',lambda r:(service,record))
    monkeypatch.setattr(owner,'_runtime',lambda:object())
    async def dispatch(runtime,principal,method,path,body,headers,query):
        from starlette.responses import JSONResponse
        calls.append((principal,path));return JSONResponse({'ok':True})
    monkeypatch.setattr(gateway.agent,'dispatch',dispatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway.application),base_url='https://device.example') as client:
        assert (await client.post('/v1/mobile/owner-agent/chat/threads',json={})).status_code==403
        assert not calls
        record.claims=claims()
        assert (await client.post('/v1/mobile/owner-agent/chat/threads',json={})).status_code==200
        assert calls==[(actor,'/chat/threads')]
        assert (await client.post('/v1/mobile/owner-agent/chat/%74hreads',json={})).status_code==403


@pytest.mark.asyncio
async def test_strict_decision_is_preparation_only(env,monkeypatch):
    e=env;monkeypatch.setenv('AI2APPS_OWNER_MOBILE_UNIFIED_READY','1')
    await e.service.configure(e.device,True)
    old_generation=e.service.row(e.device)['generation']
    async def pairing(device,connection):
        return dict(status='pending',generation=99,displayDeadline='2099-01-01T00:00:00Z',mobileAccessProtocol=protocol.PROTOCOL,commitMode=protocol.COMMIT_MODE)
    monkeypatch.setattr(e.service,'pairing',pairing)
    bodies=[]
    async def call(device,method,path,body):
        bodies.append(body)
        return dict(status='awaiting_exchange',mobileAccessProtocol=protocol.PROTOCOL,commitMode=protocol.COMMIT_MODE,generation=99,disconnectOtherClients=body['disconnectOtherClients'],revokedSessionIds=[])
    monkeypatch.setattr(e.service,'call',call)
    result=await e.service.decision(e.device,str(uuid4()),'connect',99,True)
    assert result['status']=='awaiting_exchange'
    assert bodies[-1]['commitMode']=='exchange-v1'
    assert bodies[-1]['expectedGeneration']==99
    assert e.service.row(e.device)['generation']==old_generation
    monkeypatch.setenv('AI2APPS_OWNER_MOBILE_UNIFIED_READY','0')
    with pytest.raises(RemoteTokenError):await e.service.decision(e.device,str(uuid4()),'connect',99)


def test_receipt_uses_only_legacy_generation_for_legacy_fence(env,monkeypatch):
    e=env;monkeypatch.setenv('AI2APPS_OWNER_MOBILE_UNIFIED_READY','1')
    old=str(uuid4());new=str(uuid4());cid=str(uuid4());client=str(uuid4());dropped=[]
    e.manager.owner_home=NS(sessions={old:NS(claims={'device_id':e.device,'session_id':old})},drop=lambda r:dropped.append(r.claims['session_id']))
    receipt=dict(status='active',mobileAccessProtocol=protocol.PROTOCOL,commitMode=protocol.COMMIT_MODE,
        deviceId=e.device,connectionId=cid,sessionId=new,mobileClientId=client,mobileClientEpoch=1,
        generation=99,disconnectOtherClients=True,revokedSessionIds=[old],legacyAgentGeneration=7)
    e.service.apply_unified_receipt(e.device,receipt,connection=cid,session=new)
    assert dropped==[old] and e.service.row(e.device)['generation']==7
    with e.service.database.transaction() as db:
        assert db.execute('SELECT generation FROM mobile_unified_generations WHERE device_id=?',(e.device,)).fetchone()[0]==99
    with pytest.raises(RemoteTokenError):e.service.apply_unified_receipt(e.device,{**receipt,'status':'awaiting_exchange'})
    with pytest.raises(RemoteTokenError):e.service.apply_unified_receipt(e.device,receipt,session=str(uuid4()))
    # A delayed old receipt must never roll back a newer legacy generation.
    e.service.fence(e.device,enabled=True,generation=8)
    e.service.apply_unified_receipt(e.device,receipt)
    assert e.service.row(e.device)['generation']==8


def test_exchange_request_id_survives_service_recreation_and_never_stores_bearer():
    from ai2apps.remote.owner_exchange import ExchangeRequests,KEY
    from ai2apps.secrets.backends import MemorySecretBackend
    manager=NS(secret_backend=MemorySecretBackend());device=str(uuid4());cid=str(uuid4())
    first=ExchangeRequests(manager).request_id(device,cid,'private-handoff')
    assert ExchangeRequests(manager).request_id(device,cid,'private-handoff')==first
    assert ExchangeRequests(manager).request_id(device,str(uuid4()),'private-handoff')!=first
    assert 'private-handoff' not in manager.secret_backend.load(KEY)
    manager.secret_backend.store(KEY,'broken')
    with pytest.raises(RemoteTokenError):ExchangeRequests(manager).request_id(device,cid,'private-handoff')


def test_generated_library_import_is_exact_and_owner_authorized():
    assert gateway.allowed('POST','/v1/mobile/owner-agent/files/r/a/gallery')
    assert not gateway.allowed('DELETE','/v1/mobile/owner-agent/files/r/a/gallery')
    assert not gateway.allowed('POST','/v1/mobile/owner-agent/files/r/a/gallery/other')
