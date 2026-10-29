"""Exact route declarations; no live credentials, network or model inference."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from ai2apps.model_vision import resolve_vision,vision_declaration

@pytest.mark.parametrize('raw,status',[(None,'undeclared'),({},'undeclared'),({'imageInput':True},'supported'),({'imageInput':False},'unsupported'),({'imageInput':'true'},'undeclared'),(['image_recognition'],'supported'),(['work'],'undeclared')])
def test_declaration_is_literal_not_model_name(raw,status):
    assert vision_declaration({'id':'anything-vision-vl-gpt','capabilities':raw})==status

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['arbitrary','independent'])
@pytest.mark.parametrize('raw,status',[({'imageInput':True},'supported'),({'imageInput':False},'unsupported'),({},'undeclared')])
async def test_cloud_catalog_is_actor_authorized_and_exact(provider,raw,status):
    response=NS(status_code=200,json=lambda:{'items':[{'id':provider+'/actual','capabilities':raw}]},aclose=AsyncMock())
    request=AsyncMock(return_value=response);principals=[]
    runtime=NS(cloud=NS(request=request),model_manager=NS(list_cloud=lambda:[]),cloud_ai_authorization_headers=lambda p:principals.append(p) or {'fixture':'actor-bound'})
    result=await resolve_vision(runtime,'cloud/ai2apps/'+provider+'/actual','local')
    assert result['status']==status and result['source']=='ai2apps_cloud'
    request.assert_awaited_once_with('GET','/v1/ai/models',headers={'fixture':'actor-bound'})
    assert principals[0].actor_user_id=='local';response.aclose.assert_awaited_once()

@pytest.mark.asyncio
@pytest.mark.parametrize('catalog,status',[(None,'lookup_failed'),({'items':[]},'not_found'),({'items':'broken'},'lookup_failed')])
async def test_cloud_failure_is_not_unsupported(catalog,status):
    response=NS(status_code=503 if catalog is None else 200,json=lambda:catalog,aclose=AsyncMock())
    runtime=NS(cloud=NS(request=AsyncMock(return_value=response)),cloud_ai_authorization_headers=lambda p:{})
    assert (await resolve_vision(runtime,'cloud/ai2apps/future/model','local'))['status']==status
    response.aclose.assert_awaited_once()

@pytest.mark.asyncio
async def test_byok_local_and_missing_are_distinct_without_cloud_fallback():
    cloud=NS(request=AsyncMock(side_effect=AssertionError('Wrong route')))
    runtime=NS(cloud=cloud,model_manager=NS(list_cloud=lambda:[{'id':'vendor','models':[{'id':'model','enabled':True,'capabilities':{'vision':True}}]}]),model_invocations=NS(model=lambda id:NS(capabilities=['image_recognition'])))
    assert (await resolve_vision(runtime,'cloud/vendor/model','local'))['status']=='supported'
    assert (await resolve_vision(runtime,'local/model','local'))['status']=='supported'
    assert (await resolve_vision(runtime,'cloud/vendor/missing','local'))['status']=='not_found'
    runtime.model_manager.list_cloud=lambda:[{'id':'vendor','enabled':False,'models':[{'id':'model','enabled':True}]}]
    assert (await resolve_vision(runtime,'cloud/vendor/model','local'))['status']=='disabled'
    cloud.request.assert_not_awaited()

@pytest.mark.asyncio
async def test_route_lookup_exception_is_diagnostic_not_negative_capability():
    def broken(identifier):raise RuntimeError('route unavailable')
    runtime=NS(model_manager=NS(model_source=broken))
    result=await resolve_vision(runtime,'cloud/future/model','local')
    assert result['status']=='lookup_failed' and result['source']=='unresolved'
