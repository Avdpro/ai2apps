"""Transparent sticker contracts: fixture inference only, never paid calls."""
import base64
import json
from io import BytesIO
from types import SimpleNamespace
import httpx
import pytest
from PIL import Image
from fastapi import HTTPException
from ai2apps.images.background import validate_alpha
from ai2apps.images.byok_capabilities import validate_request, image_options
from ai2apps.images.parameters import effective_schema, from_options
from ai2apps.gallery.sticker_packs import Variant, prompt, StickerPacks
from ai2apps.images.cloud_gateway import request_cloud_image
from ai2apps.model_manager import ModelManagerStore
from ai2apps.secrets import MemorySecretBackend
from ai2apps.studio.image_jobs import generate_image


def png(alpha):
    out=BytesIO();Image.new('RGBA',(32,32),(255,255,255,alpha)).save(out,'PNG');return out.getvalue()


@pytest.mark.parametrize('alpha',[0,128,254])
def test_actual_alpha(alpha):
    validate_alpha(png(alpha))


def test_opaque_png_is_not_transparent():
    with pytest.raises(ValueError,match='opaque'):validate_alpha(png(255))


@pytest.mark.parametrize('model',['gpt-image-1','gpt-image-1.5','gpt-image-2','gpt-image-2.5-flare','gpt-image-2.5-sunburst','gpt-image-2.6-flare'])
def test_native_background_contract(model):
    for output in ('png','webp'):
        validate_request(model,{'background':'transparent','outputFormat':output},edit=True)
    with pytest.raises(ValueError,match='PNG or WebP'):
        validate_request(model,{'background':'transparent','outputFormat':'jpeg'},edit=True)
    schema=effective_schema(from_options('fixture','Fixture',image_options(model)))
    assert 'transparent' in schema['properties']['background_mode']['enum']


@pytest.mark.parametrize('model',['dall-e-2','dall-e-3','unknown-gateway'])
def test_unsupported_background_rejected(model):
    with pytest.raises(ValueError,match='does not declare'):
        validate_request(model,{'background':'transparent'},edit=False)


def test_prompt_and_legacy_variant_matching():
    packs=StickerPacks(None,'fixture')
    item={'state':'happy','framing':'half','facing':'center','asset_id':'old','content_hash':'abc'}
    packs.image=lambda _:({'content_hash':'abc'},None)
    pack={'stickers':[item]}
    assert packs.find(pack,Variant(state='happy'),flexible=True)
    assert packs.find(pack,Variant(state='happy',background='transparent'),flexible=True) is None
    assert 'plain white' in prompt(Variant(state='happy'),{'description':''})
    assert 'transparent alpha' in prompt(Variant(state='happy',background='transparent'),{'description':''})


@pytest.mark.asyncio
@pytest.mark.parametrize('edit',[False,True])
async def test_background_on_byok_wire(tmp_path,edit):
    store=ModelManagerStore(tmp_path,secret_backend=MemorySecretBackend())
    model='gpt-image-2.5-flare'
    store.put_cloud('openai',{'api_key':'fixture','models':[model]});store.set_cloud_model_enabled('openai',model,True)
    encoded=base64.b64encode(png(0)).decode()
    def handler(request):
        if edit:
            body=request.content.decode('latin1');assert 'name="background"\r\n\r\ntransparent' in body
            assert 'name="output_format"\r\n\r\npng' in body
        else:
            body=json.loads(request.content);assert body['background']=='transparent' and body['output_format']=='png'
        return httpx.Response(200,json={'data':[{'b64_json':encoded}]})
    body={'model':'cloud/openai/'+model,'prompt':'sticker','size':'1024x1024','background':'transparent','outputFormat':'png'}
    if edit:body['imageDataUrls']=['data:image/png;base64,'+encoded]
    result=await request_cloud_image(body,edit=edit,base_path=tmp_path,model_manager=store,transport=httpx.MockTransport(handler))
    validate_alpha(base64.b64decode(result['image']['dataUrl'].split(',')[1]))


@pytest.mark.asyncio
@pytest.mark.parametrize('alpha',[0,255])
async def test_job_checks_alpha(monkeypatch,alpha):
    async def cloud(*a,**kw):return {'image':{'dataUrl':'data:image/png;base64,'+base64.b64encode(png(alpha)).decode()}}
    monkeypatch.setattr('ai2apps.images.cloud_gateway.request_cloud_image',cloud)
    runtime=SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(base_path=None)),cloud=None,cloud_ai_authorization_headers=lambda _: {})
    call=generate_image(runtime,None,{},dict(source='byok',model='fixture',prompt='sticker',background='transparent',outputFormat='png'),'job')
    if alpha==255:
        with pytest.raises(ValueError,match='opaque'):await call
    else:
        content,_=await call;assert content==png(0)


@pytest.mark.asyncio
async def test_cloud_missing_declaration_never_posts(tmp_path):
    class Cloud:
        async def request(self,method,path,**kw):
            assert method=='GET' and path=='/v1/ai/models'
            return httpx.Response(200,json={'items':[]},request=httpx.Request(method,'https://fixture'+path))
    with pytest.raises(HTTPException,match='does not declare'):
        await request_cloud_image({'model':'cloud/ai2apps/openai/gpt-image-2','background':'transparent'},edit=False,base_path=tmp_path,cloud_client=Cloud())


@pytest.mark.asyncio
async def test_cloud_declared_background_is_forwarded(tmp_path):
    calls=[]
    class Cloud:
        async def request(self,method,path,**kw):
            calls.append(method)
            if method=='GET':
                result={'items':[{'id':'openai/gpt-image-2','imageOptions':{'background':['transparent']}}]}
            else:
                assert kw['json']['background']=='transparent'
                assert kw['json']['model']=='openai/gpt-image-2'
                result={'image':{'dataUrl':'data:image/png;base64,'+base64.b64encode(png(0)).decode()}}
            return httpx.Response(200,json=result,request=httpx.Request(method,'https://fixture'+path))
    result=await request_cloud_image({'model':'cloud/ai2apps/openai/gpt-image-2','prompt':'sticker','background':'transparent','outputFormat':'png'},edit=False,base_path=tmp_path,cloud_client=Cloud())
    assert calls==['GET','POST']
    validate_alpha(base64.b64decode(result['image']['dataUrl'].split(',')[1]))


def test_ui_submission_schemas_keep_background():
    from ai2apps.api.imagine_studio import StudioRunExecuteRequest
    from ai2apps.api.studio_background import StickerBatchInput
    body={'model':'fixture','prompt':'sticker','size':'1024x1024','background':'transparent','outputFormat':'png'}
    assert StudioRunExecuteRequest(**body).model_dump(by_alias=True)['background']=='transparent'
    assert StickerBatchInput(**body,source='byok',prompts=['a','b','c','d'],imageDataUrls=['fixture']).model_dump()['background']=='transparent'
