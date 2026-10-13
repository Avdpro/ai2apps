import base64
from types import SimpleNamespace
import pytest
from fastapi import APIRouter, Depends, HTTPException
from ai2apps.web import mobile_app_gateway as gateway

SPEC={'api':{'module':'fixture','factory':'create_fixture_router','prefix':'/v1/platform/fixture'}}

@pytest.fixture
def declared(monkeypatch):
    def factory(runtime, principal):
        router=APIRouter(prefix='/fixture')
        @router.get('/actor')
        def actor(value=Depends(principal)):
            return {'owner':value.actor_user_id}
        @router.post('/upload')
        async def upload(request: __import__('fastapi').Request, value=Depends(principal)):
            return {'size':len(await request.body()),'owner':value.actor_user_id}
        return router
    monkeypatch.setattr(gateway,'import_module',lambda name:SimpleNamespace(create_fixture_router=factory))
    gateway._APPS.clear()

@pytest.mark.asyncio
async def test_actor_binding_and_upload(declared):
    runtime=object()
    for owner in ['alice','bob']:
        result=await gateway.api_response(runtime,SimpleNamespace(actor_user_id=owner),SPEC,{'method':'request','path':'/v1/platform/fixture/actor'})
        assert result.json()=={'owner':owner}
    result=await gateway.bridge(runtime,SimpleNamespace(actor_user_id='alice'),SPEC,{'method':'request','verb':'POST','path':'/v1/platform/fixture/upload','body':base64.b64encode(b'bytes').decode()})
    assert result['status']==200
    assert b'"size":5' in base64.b64decode(result['body'])

@pytest.mark.asyncio
@pytest.mark.parametrize('body',[
    {'path':'/v1/platform/account'}, {'path':'https://evil.example/v1/platform/fixture'},
    {'path':'/v1/platform/fixture/../account'}, {'path':'/v1/platform/fixture','verb':'CONNECT'},
    {'path':'/v1/platform/fixture','headers':{'Authorization':'secret'}},
    {'path':'/v1/platform/fixture','body':'not base64!'},
    {'path':'/v1/platform/fixture','url':'https://evil.example'},
])
async def test_scope_fail_closed(declared,body):
    with pytest.raises(HTTPException):await gateway.api_response(object(),None,SPEC,body)

def test_package_cannot_declare_trusted_host():
    assert gateway.descriptor(None,{'source':'package','renderer':'host'}) is None
    assert gateway.descriptor(None,{'source':'builtin','renderer':'sandbox'}) is None
    assert not gateway.supported({'mobile_renderer':'host'})
    assert gateway.supported({'mobile_renderer':'sandbox'})


def test_asset_path_traversal_denied():
    with pytest.raises(HTTPException):gateway.asset_response({'assets':[]},'assets/../../secrets')
