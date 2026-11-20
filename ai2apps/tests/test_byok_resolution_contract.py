"""Geometry contracts and wire-level preservation; no paid provider calls."""
import asyncio
import base64
import io
import json
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.images.cloud_gateway import request_cloud_image
from ai2apps.images.byok_capabilities import image_options
from ai2apps.images.parameters import models, effective_schema, validate_size
from ai2apps.model_manager import ModelManagerStore
from ai2apps.secrets import MemorySecretBackend
from ai2apps.video.byok import catalog, _request_body, SEEDANCE_RESOLUTIONS

FLEXIBLE = ['gpt-image-2', 'gpt-image-2-2026-04-21'] + [
    f'gpt-image-{version}-{variant}{snapshot}' for version in ('2.5', '2.6')
    for variant in ('flare', 'sunburst') for snapshot in ('', '-2026-09-08')]

@pytest.mark.parametrize('name', FLEXIBLE)
def test_custom_size_version_contract(name):
    options = image_options(name)
    for size in ('1536x1152', '1152x1536', '3840x2160', '2160x3840', '1024x640', 'auto'):
        validate_size(size, options['size'])
    for size, reason in [('1537x1152', 'multiple'), ('4096x1024', 'width'),
                         ('640x640', 'Pixel'), ('3840x3840', 'Pixel'), ('3072x768', 'ratio')]:
        with pytest.raises(ValueError, match=reason): validate_size(size, options['size'])
    assert options['size']['experimentalAbovePixels'] == 3686400
    assert ('max' in options['quality']) == ('2.5' in name or '2.6' in name)

@pytest.mark.parametrize('name', ['gpt-image-1', 'gpt-image-1-mini', 'gpt-image-1.5', 'gpt-image-1.5-2025-12-16', 'chatgpt-image-latest'])
def test_old_models_keep_fixed_geometry(name):
    options = image_options(name)
    assert options['quality'] == ['auto','low','medium','high']
    validate_size('auto', options['size'])
    with pytest.raises(ValueError): validate_size('1536x1152', options['size'])

@pytest.mark.asyncio
async def test_bot_and_studio_share_every_byok_contract(tmp_path, monkeypatch):
    store = ModelManagerStore(tmp_path, secret_backend=MemorySecretBackend())
    names = FLEXIBLE + ['gpt-image-1.5', 'dall-e-2', 'dall-e-3', 'flux-custom']
    store.put_cloud('openai', {'api_key':'fixture', 'models':names})
    for name in names: store.set_cloud_model_enabled('openai', name, True)
    runtime=SimpleNamespace(model_manager=store,cloud=None)
    monkeypatch.setattr('ai2apps.api.imagine_studio.list_package_models',lambda _:[])
    monkeypatch.setattr('ai2apps.model_providers.list_package_models',lambda *a,**k:[])
    app=FastAPI();app.include_router(create_imagine_studio_router(lambda:runtime,lambda:object()))
    ui={m['id']:m for m in TestClient(app).get('/imagine-studio/models').json()['data']}
    for edit in (False, True):
        bot,_=await models(runtime,None,edit)
        for model in bot:
            other=ui[model['id']]['imageOptions']
            assert model['size']==other['size']
            assert model['qualities']==other['quality']
            if model['size']['mode']=='bounded-custom':
                assert 'enum' not in effective_schema(model,edit)['properties']['size']
        assert any(m['id'].endswith('gpt-image-2.6-flare') for m in bot)
        if edit: assert not any(m['id'].endswith('dall-e-3') for m in bot)

@pytest.mark.asyncio
async def test_double_reference_composite_and_edit_preserve_exact_wire_size(tmp_path):
    store=ModelManagerStore(tmp_path,secret_backend=MemorySecretBackend())
    name='gpt-image-2.5-flare'; route='cloud/openai/'+name
    store.put_cloud('openai',{'api_key':'fixture','models':[name]})
    store.set_cloud_model_enabled('openai',name,True)
    def png(size):
        out=io.BytesIO();Image.new('RGB',size,'white').save(out,format='PNG');return base64.b64encode(out.getvalue()).decode()
    reference='data:image/png;base64,'+png((1024,1024))
    result_png=png((1536,1152));calls=[]
    def handler(request):
        body=request.content.decode('latin1')
        assert request.url.host=='api.openai.com' and request.url.path=='/v1/images/edits'
        assert '1536x1152' in body and name in body and 'xhigh' in body
        assert 'response_format' not in body and 'input_fidelity' not in body
        calls.append(body.count('name="image[]"'))
        return httpx.Response(200,json={'data':[{'b64_json':result_png}]})
    class NoCloud:
        async def request(self,*a,**kw):raise AssertionError('Cloud fallback')
    for refs in ([reference,reference],[reference]):
        result=await request_cloud_image({'model':route,'prompt':'composite/edit','size':'1536x1152','quality':'xhigh','imageDataUrls':refs},
            edit=True,base_path=tmp_path,model_manager=store,transport=httpx.MockTransport(handler),cloud_client=NoCloud())
        actual=Image.open(io.BytesIO(base64.b64decode(result['image']['dataUrl'].split(',')[1])))
        assert actual.size==(1536,1152)
    assert calls==[2,1]
    with pytest.raises(HTTPException,match='multiple'):
        await request_cloud_image({'model':route,'size':'1537x1152'},edit=False,base_path=tmp_path,model_manager=store,
                                  transport=httpx.MockTransport(lambda _:pytest.fail('invalid request submitted')))


def test_every_video_variant_resolution_reaches_adapter():
    runtime=SimpleNamespace(model_manager=SimpleNamespace(secret_backend=MemorySecretBackend()))
    for model in catalog(runtime,'actor'):
        provider=model.metadata['provider']
        for resolution in model.video_capabilities['geometry']['resolutions']:
            ratios = [SEEDANCE_RESOLUTIONS[resolution][1]] if provider=='volcengine' else model.video_capabilities['geometry']['ratios']
            for ratio in ratios:
                body=_request_body(provider,model,{'prompt':'test','duration':5,'resolution':resolution,'ratio':ratio})
                assert body['ratio']==ratio
                if provider=='volcengine': assert body['resolution']==SEEDANCE_RESOLUTIONS[resolution][0]
        if 'flash' in model.id:
            assert all(SEEDANCE_RESOLUTIONS[r][0] in ('480p','720p') for r in model.video_capabilities['geometry']['resolutions'])
        if provider=='volcengine' and 'flash' not in model.id:
            assert '3326x2494' in model.video_capabilities['geometry']['resolutions']

@pytest.mark.parametrize('name',['openai/gpt-image-2.5-flare','openai/gpt-image-2.6-sunburst','vendor/gpt-image-2'])
def test_namespaced_gateway_ids_reuse_geometry_without_changing_id(name):
    assert image_options(name)==image_options(name.rsplit('/',1)[-1])
    validate_size('1536x1152',image_options(name)['size'])


def test_unknown_gateway_geometry_is_not_a_fake_square_only_contract():
    options=image_options('flux-custom')
    assert options['size']['validation']=='provider'
    validate_size('1536x1152',options['size'])
    validate_size('512x768',options['size'])

@pytest.mark.asyncio
async def test_namespaced_custom_json_request_is_not_rewritten(tmp_path):
    store=ModelManagerStore(tmp_path,secret_backend=MemorySecretBackend())
    name='openai/gpt-image-2.6-flare'
    store.put_cloud('openai',{'api_key':'fixture','models':[name]});store.set_cloud_model_enabled('openai',name,True)
    def handler(request):
        body=json.loads(request.content)
        assert body=={'model':name,'prompt':'test','size':'1536x1152','quality':'max','n':1,'output_format':'png'}
        return httpx.Response(200,json={'data':[{'b64_json':'aW1hZ2U='}]})
    await request_cloud_image({'model':'cloud/openai/'+name,'prompt':'test','size':'1536x1152','quality':'max'},
        edit=False,base_path=tmp_path,model_manager=store,transport=httpx.MockTransport(handler))
