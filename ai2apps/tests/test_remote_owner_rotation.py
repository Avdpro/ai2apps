from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request
from ai2apps.api.remote import create_remote_router, RotateRemoteCredentialRequest
from ai2apps.remote.manager import RemoteAccessManager, RemoteAccessError


def setup_route():
    manager=NS(require_device=Mock(),identity_repository=NS(get_installation=lambda:NS(id='installation-one',cloud_device_id='device-one')),
        _request=AsyncMock(return_value={'grant':'fixture-single-use-grant'}),rotate=AsyncMock(return_value=JSONResponse({'ok':True})))
    router=create_remote_router(lambda:NS(remote=manager))
    endpoint=next(r.endpoint for r in router.routes if getattr(r,'path',None)=='/remote/devices/{device_id}/credentials/rotate')
    request=Request({'type':'http','method':'POST','scheme':'http','path':'/remote/devices/device-one/credentials/rotate',
        'headers':[(b'host',b'local.test'),(b'origin',b'http://local.test')],'server':('local.test',80),'query_string':b''})
    return manager,endpoint,request

@pytest.mark.asyncio
async def test_correct_purpose_resource_and_secret_repr():
    m,endpoint,request=setup_route();cloud=NS();body=RotateRemoteCredentialRequest(ownerPassword='fixture-password')
    assert 'fixture-password' not in repr(body)
    assert (await endpoint('device-one',body,request,cloud)).status_code==200
    m._request.assert_awaited_once_with('POST','/v1/owner-reauth/grants',cloud=cloud,json={'purpose':'installation.rotate_credential','resourceType':'installation','resourceId':'installation-one','password':'fixture-password'})
    m.rotate.assert_awaited_once_with('device-one',cloud=cloud,owner_reauth_grant='fixture-single-use-grant')

@pytest.mark.asyncio
@pytest.mark.parametrize('grant',[{}, {'grant':''}])
async def test_bad_grant_does_not_rotate(grant):
    m,endpoint,request=setup_route();m._request.return_value=grant
    assert (await endpoint('device-one',RotateRemoteCredentialRequest(ownerPassword='fixture-password'),request,NS())).status_code==502
    m.rotate.assert_not_awaited()

@pytest.mark.asyncio
async def test_rejected_password_does_not_rotate():
    m,endpoint,request=setup_route();m._request.side_effect=RemoteAccessError(403,'OWNER_REAUTH_INVALID','Password verification failed')
    assert (await endpoint('device-one',RotateRemoteCredentialRequest(ownerPassword='fixture-password'),request,NS())).status_code==403
    m.rotate.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize('wrong_origin',[False,True])
async def test_device_and_origin_guards(wrong_origin):
    m,endpoint,request=setup_route()
    if wrong_origin:request.scope['headers']=[(b'host',b'local.test'),(b'origin',b'https://other.test')]
    with pytest.raises(HTTPException):await endpoint('device-one' if wrong_origin else 'different-device',RotateRemoteCredentialRequest(ownerPassword='fixture-password'),request,NS())
    m._request.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize('timeout',[False,True])
async def test_single_use_grant_header_and_no_uncertain_replay(timeout):
    m=RemoteAccessManager.__new__(RemoteAccessManager);m.require_device=Mock(return_value=NS(enabled=False,secret_backend_key='key'))
    m.stop=AsyncMock();m._request=AsyncMock(return_value={});m._validate_credential=Mock(return_value='fixture-new-key')
    m.secret_backend=NS(load=Mock(),store=Mock());m.repository=NS(update_credential=Mock(return_value=NS(enabled=False)))
    if timeout:
        m._request.side_effect=httpx.ReadTimeout('uncertain')
        with pytest.raises(httpx.ReadTimeout):await m.rotate('device-one',owner_reauth_grant='fixture-grant')
    else:await m.rotate('device-one',owner_reauth_grant='fixture-grant')
    m._request.assert_awaited_once_with('POST','/v1/remote/devices/device-one/credentials/rotate',cloud=None,headers={'X-Owner-Reauth-Grant':'fixture-grant'})
