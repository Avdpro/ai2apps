import asyncio,base64,io,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from fastapi.responses import Response
from ai2apps.studio.extended_jobs import submit
from ai2apps.studio.repository import StudioRepository
from ai2apps.studio.image_adjustments import render,freeze_target,publish_target
from test_studio_background_jobs import publication_service,principal,wait_status
from test_video_background_jobs import wav


def png(color='red',size=(8,6)):
    out=io.BytesIO();Image.new('RGB',size,color).save(out,format='PNG');return out.getvalue()


def setup(tmp_path,studio='ai2apps.imagine-studio',mini='ai2apps.imagine.text-to-image'):
    m,app=publication_service(tmp_path,studio);m.runtime.studio_jobs=m
    m.runtime.extension_manager=SimpleNamespace(require_instance_access=lambda *a:None,instance_entry=lambda *a,**k:{'app_key':studio})
    scope=dict(actor_id='owner',installation_id='installation',app_instance_id=app,studio_id=studio)
    run=StudioRepository(m.database).create_run(**scope,mini_app_id=mini,mini_app_version='1',placement='inline',title='Test',input_data={})
    return m,app,scope,run

async def finish(m,job,status='succeeded'):
    await m.startup()
    for _ in range(500):
        if m.get(job['id'],principal())['status']==status:return
        await asyncio.sleep(.01)
    assert m.get(job['id'],principal())['status']==status,m.get(job['id'],principal())

@pytest.mark.parametrize('operation',['design','clone'])
async def test_voice_preview_frozen_input_and_shared_output(tmp_path,monkeypatch,operation):
    m,app,scope,run=setup(tmp_path,'ai2apps.readaloud','ai2apps.audio.voice-design');calls=[]
    async def invoke(*args,**kw):
        calls.append(kw)
        if operation=='clone':assert kw['files']['reference_audio'][1]==wav()
        return Response(wav(),media_type='audio/wav')
    m.runtime.model_invocations=SimpleNamespace(invoke_background_json=invoke,invoke_background_multipart=invoke)
    from ai2apps.readaloud import ReadAloudRepository
    attached=[]
    monkeypatch.setattr(ReadAloudRepository,'attach_design_preview',lambda *a:attached.append(a) or False)
    monkeypatch.setattr(ReadAloudRepository,'verify_training_preview',lambda *a:attached.append(a) or False)
    payload={'operation':operation,'model':'test','body':{'model':'test','input':'test'},'title':'Voice','model_label':'Test','profile_id':'profile-changed','expected':[] if operation=='design' else {},'preview':{}}
    job=submit(m.runtime,principal(),app,scope['studio_id'],run['miniAppId'],'voice-preview',payload,files={'reference':wav()})
    try:
        await finish(m,job)
        assert len(calls)==1 and len(attached)==1
        result=m.get(job['id'],principal())['result'];assert result['profileUpdated'] is False
        assert len(m.runtime.readaloud_tasks.output_history('owner'))==1
        assert not m.runtime.readaloud_tasks.output_history('other')
    finally:await m.shutdown()

@pytest.mark.parametrize('edit',[False,True])
async def test_cloud_image_checkpoint_retry_no_second_request(tmp_path,monkeypatch,edit):
    m,app,scope,run=setup(tmp_path);calls=[]
    async def cloud(body,**kw):
        calls.append((body,kw));return {'image':{'dataUrl':'data:image/png;base64,'+base64.b64encode(png()).decode(),'format':'png'}}
    monkeypatch.setattr('ai2apps.cloud_gateway.request_cloud_image',cloud)
    m.runtime.cloud=object();m.runtime.cloud_ai_authorization_headers=lambda p:{}
    body={'model':'cloud/test','prompt':'test','size':'1024x1024','source':'cloud'}
    if edit:body['imageDataUrls']=['data:image/png;base64,'+base64.b64encode(png()).decode()]
    job=submit(m.runtime,principal(),app,scope['studio_id'],run['miniAppId'],'cloud-image',{'body':body},run_id=run['id'])
    publish=m.publish;m.publish=lambda *a,**k:(_ for _ in ()).throw(OSError('disk full'))
    try:
        await finish(m,job,'publish_failed');m.publish=publish;m.retry(job['id'],principal());await wait_status(m,job['id'],'succeeded')
        assert len(calls)==1 and calls[0][1]['edit']==edit
        assert calls[0][0]['idempotencyKey']=='imagine-run-'+run['id']
        assert len(StudioRepository(m.database).get_run(run['id'],**scope)['artifacts'])==1
    finally:await m.shutdown()

async def test_upscale_closed_page_uses_frozen_bytes(tmp_path):
    m,app,scope,run=setup(tmp_path,mini='ai2apps.imagine.upscale-image')
    async def invoke(model,capability,body,destination,**kw):
        assert kw['files']['image'][1].read_bytes()==png();destination.write_bytes(png(size=(16,12)))
    m.runtime.model_invocations=SimpleNamespace(invoke_background_to_file=invoke)
    job=submit(m.runtime,principal(),app,scope['studio_id'],run['miniAppId'],'image-upscale',{'model':'upscale','parameters':{'scale':2},'media_type':'image/png'},files={'image':png()},run_id=run['id'])
    try:
        await finish(m,job);r=StudioRepository(m.database).get_run(run['id'],**scope)
        assert r['artifacts'][0]['metadata']['size']=='16x12'
    finally:await m.shutdown()

async def test_batch_adjustment_real_render_and_idempotent_target(tmp_path):
    m,app,scope,run=setup(tmp_path,mini='ai2apps.imagine.adjust-image')
    source=tmp_path/'source.png';source.write_bytes(png());out=tmp_path/'export';out.mkdir()
    target=freeze_target(m.runtime,principal(),{'kind':'local','sourcePath':str(source),'outputRoot':str(out),'relativePath':'final.png','name':'final.png','mediaType':'image/png'})
    state={'rotation':90,'cropRatio':'1:1','values':{'exposure':-25,'sharpness':30}}
    items=[{'name':'first.png','media_type':'image/png','target':target},{'name':'second.png','media_type':'image/png'}]
    job=submit(m.runtime,principal(),app,scope['studio_id'],run['miniAppId'],'image-adjust',{'state':state,'items':items},files={'0':png(),'1':png('blue')},run_id=run['id']);source.unlink()
    try:
        await finish(m,job);r=StudioRepository(m.database).get_run(run['id'],**scope)
        assert len(r['artifacts'])==2
        with Image.open(out/'final.png') as image:assert image.size==(6,6) and image.getpixel((0,0))[0]==180
        data=(out/'final.png').read_bytes();publish_target(m.runtime,principal(),target,data,'same')
    finally:await m.shutdown()

def test_adjustment_overwrite_rejects_changed_source(tmp_path):
    m,app,scope,run=setup(tmp_path);source=tmp_path/'input.png';source.write_bytes(png())
    target=freeze_target(m.runtime,principal(),{'kind':'local','overwrite':True,'sourcePath':str(source),'name':'input.png','mediaType':'image/png'})
    source.write_bytes(png('blue'))
    with pytest.raises(ValueError,match='changed'):publish_target(m.runtime,principal(),target,png('green'),'test')
    assert source.read_bytes()==png('blue')

async def test_frozen_generation_keeps_prepared_geometry_and_publishes_once(tmp_path,monkeypatch):
    from ai2apps.studio.frozen_time import CameraKey
    from dataclasses import asdict
    m,app,scope,run=setup(tmp_path,mini='ai2apps.imagine.frozen-time');calls=[]
    async def generate(runtime,source,directory,**kw):
        calls.append(1);assert source.read_bytes()==png();assert isinstance(kw['prepared'][2][0],CameraKey)
        (directory/'poster.jpg').write_bytes(png());(directory/'output.mp4').write_bytes(b'video');return [('output.mp4','video','video/mp4')]
    monkeypatch.setattr('ai2apps.studio.frozen_time_pipeline.generate',generate)
    from ai2apps.studio.frozen_time import camera_plan
    payload={'operation':'generate','settings':{},'prepared':[8,6,[asdict(camera_plan('vertical')[0])]],'metadata':{'output':'mp4'}}
    job=submit(m.runtime,principal(),app,scope['studio_id'],run['miniAppId'],'frozen-time',payload,files={'input.png':png()},run_id=run['id'])
    publish=m.publish;first=True
    def fail(*a,**k):
        nonlocal first
        result=publish(*a,**k)
        if first:first=False;raise OSError('after publish')
        return result
    m.publish=fail
    try:
        await finish(m,job,'publish_failed');m.retry(job['id'],principal());await wait_status(m,job['id'],'succeeded')
        assert len(calls)==1 and len(StudioRepository(m.database).get_run(run['id'],**scope)['artifacts'])==1
    finally:await m.shutdown()

async def test_frozen_conversion_real_media_after_source_deleted(tmp_path):
    import numpy as np,av
    from ai2apps.studio.frozen_time_pipeline import encode_frames
    m,app,scope,run=setup(tmp_path,mini='ai2apps.imagine.frozen-time');source=tmp_path/'clip.mp4'
    encode_frames(source,(np.full((32,32,3),i*3,dtype='uint8') for i in range(73)),32,32)
    files={'output.mp4':source.read_bytes(),'poster.jpg':png(size=(32,32))};source.unlink()
    job=submit(m.runtime,principal(),app,scope['studio_id'],run['miniAppId'],'frozen-time',{'operation':'convert','output':'html','original_output':'mp4','metadata':{'output':'html'}},files=files,run_id=run['id'])
    try:
        await finish(m,job)
        out=m.runtime.config.paths.artifacts_path/'imagine-frozen-time'/run['id']
        assert (out/'output.html').is_file()
        with av.open(str(out/'output.mp4')) as v:assert sum(1 for _ in v.decode(video=0))==73
    finally:await m.shutdown()

@pytest.mark.parametrize('operation',['cloud','upscale','adjust'])
async def test_imagine_http_accepts_owned_durable_tasks(tmp_path,operation):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.imagine_studio import create_imagine_studio_router
    mini={'cloud':'ai2apps.imagine.text-to-image','upscale':'ai2apps.imagine.upscale-image','adjust':'ai2apps.imagine.adjust-image'}[operation]
    m,app_id,scope,run=setup(tmp_path,mini=mini)
    m.runtime.model_invocations=SimpleNamespace(model=lambda x:SimpleNamespace(capabilities=['image_upscaling'],checkpoint_ready=True))
    app=FastAPI();app.include_router(create_imagine_studio_router(lambda:m.runtime,principal))
    headers={'X-AI2Apps-App-Instance':app_id};base='/imagine-studio/runs/'+run['id']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        if operation=='cloud':r=await c.post(base+'/execute',headers=headers,json={'model':'cloud/test','prompt':'test','size':'1024x1024'})
        elif operation=='upscale':r=await c.post(base+'/upscale',headers=headers,data={'model_id':'upscale'},files={'image':('source.png',png(),'image/png')})
        else:r=await c.post(base+'/adjust',headers=headers,data={'spec':json.dumps({'state':{'rotation':90},'items':[{'name':'out.png','mediaType':'image/png'}]})},files={'files':('source.png',png(),'image/png')})
        assert r.status_code==202,r.text
        job=m.for_run(run['id'],principal());assert job['status']=='queued'
        foreign=await c.post('/imagine-studio/runs/strun_missing/adjust',headers=headers,data={'spec':'{}'},files={'files':('source.png',png(),'image/png')})
        assert foreign.status_code==404


def test_color_and_sharpen_match_javascript_engine():
    import subprocess,numpy as np
    # Execute the exact production color functions without a browser or canvas.
    src=Path('ai2apps/web/static/js/imagine_adjust.js').read_text().replace('defaults: () =>','applyColor, sharpen, defaults: () =>')
    rng=np.random.default_rng(42);pixels=rng.integers(0,256,(8,9,4),dtype=np.uint8);pixels[:,:,3]=255
    values={'exposure':12,'brilliance':20,'highlights':-30,'shadows':10,'contrast':17,'brightness':-10,'saturation':-12,'vibrance':25,'blackPoint':13,'colorBalance':15,'warmth':-5,'tint':13,'definition':25,'vignette':30,'sharpness':30}
    script="const window={};"+src+"\nconst d=JSON.parse(require('fs').readFileSync(0,'utf8'));d.image.data=new Uint8ClampedArray(d.image.data);window.ImagineAdjustEngine.applyColor(d.image,d.values);window.ImagineAdjustEngine.sharpen(d.image,d.values.sharpness);console.log(JSON.stringify(Array.from(d.image.data)));"
    result=subprocess.run(['node','-e',script],input=json.dumps({'image':{'width':9,'height':8,'data':pixels.flatten().tolist()},'values':values}),text=True,capture_output=True,check=True)
    expected=np.array(json.loads(result.stdout)).reshape(8,9,4)
    inp=io.BytesIO();Image.fromarray(pixels).save(inp,format='PNG');actual=np.array(Image.open(io.BytesIO(render(inp.getvalue(),{'values':values}))))
    assert np.max(np.abs(actual.astype(int)-expected))<=1

@pytest.mark.parametrize('rotation',[0,90,180,270,-90])
@pytest.mark.parametrize('flip',[False,True])
def test_adjust_geometry_and_alpha(rotation,flip):
    import numpy as np
    a=np.arange(3*4*4,dtype='uint8').reshape(3,4,4);inp=io.BytesIO();Image.fromarray(a).save(inp,format='PNG')
    actual=np.array(Image.open(io.BytesIO(render(inp.getvalue(),{'rotation':rotation,'flipX':flip}))))
    expected=np.rot90(a[:,::-1] if flip else a,-rotation//90)
    assert np.array_equal(actual,expected)
