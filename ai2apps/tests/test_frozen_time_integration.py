from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from fastapi import HTTPException, UploadFile

from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import RequestPrincipal
from ai2apps.storage import PlatformDatabase
from ai2apps.studio.frozen_time_pipeline import prepare_reference, export_video, crop_model_input, reference_size, save_original_still
from ai2apps.provisioning.profiles import CapabilityProfileRegistry
from ai2apps.studio.frozen_time import CAMERA_MODES, camera_plan, live_photo_frame_order
from ai2apps.studio.frozen_time_pipeline import encode_frames
from ai2apps.api.imagine_frozen_time import normalize_soundtrack
from wave import open as wave_open
import json
from dataclasses import asdict

def frame_payload(mode='vertical'):
    plan=camera_plan(mode)
    return {'schema':'ai2apps.camera-frames/v1','frames':[asdict(k) for k in plan],
            'playback':list(live_photo_frame_order(plan)),'poster':36}


@pytest.mark.asyncio
async def test_soundtrack_is_optional_mp4_only_and_validated_before_run():
    assert await normalize_soundtrack(None,'mp4') is None
    audio_buffer=BytesIO()
    with wave_open(audio_buffer,'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(48000);output.writeframes(b'\0\0'*4800)
    audio=audio_buffer.getvalue()
    assert await normalize_soundtrack(UploadFile(BytesIO(audio),filename='music.wav',headers={'content-type':'audio/wav'}),'mp4')==audio
    for data,kind,output,status in [(audio,'audio/wav','html',422),(b'not audio','audio/wav','mp4',422),(audio,'application/octet-stream','mp4',422)]:
        with pytest.raises(HTTPException) as error:
            await normalize_soundtrack(UploadFile(BytesIO(data),filename='music.wav',headers={'content-type':kind}),output)
        assert error.value.status_code==status


@pytest.mark.asyncio
async def test_geometry_stage_keeps_reference_and_exports_returning_preview(tmp_path):
    import av
    from ai2apps.studio.frozen_time_pipeline import prepare_preview
    source=tmp_path/'input.png'
    Image.new('RGB',(64,64),'orange').save(source)
    class Invocations:
        async def invoke_background_to_file(self,model,capability,payload,destination,**kwargs):
            assert capability=='depth_estimation'  # No Meridian call during preview.
            np.savez(destination,depth=np.ones((64,64),dtype='f4'),depth_kind=np.array('relative_inverse_depth'))
    prepared=await prepare_preview(SimpleNamespace(model_invocations=Invocations()),source,tmp_path,
        depth='vggt',output='mp4',long_edge=512,context=None,
        request_id='test-preview',cancelled=lambda:False,progress=lambda *args:None,trajectory=frame_payload())
    assert prepared[:2]==(512,512)
    for name,expected in [('reference.mp4',73),('preview.mp4',109)]:
        with av.open(str(tmp_path/name)) as container:
            assert len(list(container.decode(video=0)))==expected


@pytest.mark.parametrize('mode',CAMERA_MODES)
@pytest.mark.parametrize('output',('html','mp4','live-photo'))
def test_preview_and_final_share_exact_playback_order(tmp_path,mode,output):
    import av
    plan=camera_plan(mode,output='html' if output=='html' else 'live-photo')
    raw=tmp_path/'reference.mp4'
    encode_frames(raw,(np.full((32,32,3),i*3,dtype='uint8') for i in range(73)),32,32)
    before=raw.read_bytes()
    preview,final=tmp_path/'preview.mp4',tmp_path/'output.mp4'
    export_video(raw,preview,tmp_path/'preview-poster.jpg',plan,output,lambda:False)
    export_video(raw,final,tmp_path/'poster.jpg',plan,output,lambda:False)
    with av.open(str(preview)) as container:
        preview_frames=[f.to_ndarray(format='rgb24') for f in container.decode(video=0)]
    with av.open(str(final)) as container:
        final_frames=[f.to_ndarray(format='rgb24') for f in container.decode(video=0)]
    order=tuple(range(73)) if output=='html' else live_photo_frame_order(plan)
    assert len(preview_frames)==len(final_frames)==len(order)
    np.testing.assert_array_equal(preview_frames,final_frames)
    assert raw.read_bytes()==before  # Meridian still receives the original 73 frames.
    if mode=='vertical' and output!='html':
        assert len(order)==109 and order[-1]==36

def test_live_photo_still_preserves_full_upload(tmp_path):
    source, poster = tmp_path/'input.png', tmp_path/'poster.jpg'
    Image.new('RGB',(798,710),'orange').save(source)
    save_original_still(source,poster)
    with Image.open(poster) as image:
        assert image.size == (798,710)

@pytest.mark.parametrize('size,edge', [((798,710),512),((1536,1024),768),((710,798),512),((1024,1024),512),((3000,1000),512)])
def test_center_crop_matches_model_canvas(tmp_path, size, edge):
    source, cropped = tmp_path/'original.png', tmp_path/'model-input.png'
    pixels = np.arange(size[0]*size[1]*3, dtype=np.uint8).reshape(size[1],size[0],3)
    Image.fromarray(pixels).save(source)
    original = source.read_bytes()
    rw, rh = crop_model_input(source,cropped,edge)
    with Image.open(cropped) as image:
        assert image.width*rh == image.height*rw
        assert reference_size(image.size,edge) == (rw,rh)
        x,y = (size[0]-image.width)//2,(size[1]-image.height)//2
        np.testing.assert_array_equal(np.asarray(image),pixels[y:y+image.height,x:x+image.width])
    assert source.read_bytes() == original


@pytest.mark.parametrize('reference_speedup,ref_size', [(True,(256,192)),(False,(512,384))])
def test_reference_preserves_aspect_and_exports_73_frames(tmp_path,reference_speedup,ref_size):
    import av
    source = tmp_path / "input.png"
    Image.new("RGB", (320, 224), "orange").save(source)
    depth = tmp_path / "depth.npz"
    np.savez(depth, depth=np.linspace(0, 1, 320*224).reshape(224,320).astype('f4'), depth_kind=np.array('relative_inverse_depth'))
    ref = tmp_path / "ref.mp4"
    w,h,plan = prepare_reference(source, depth, ref, output='html', long_edge=512, cancelled=lambda:False,trajectory=frame_payload('push-orbit'),reference_speedup=reference_speedup)
    assert (w,h)==(512,384)
    with av.open(str(ref)) as container:
        frames=list(container.decode(video=0))
    assert len(frames)==73 and (frames[0].width,frames[0].height)==ref_size
    assert plan[0].yaw==-10 and plan[-1].yaw==10
    assert plan[0].radius==pytest.approx(1+.22*2/3)
    export_video(ref,tmp_path/'output.mp4',tmp_path/'poster.jpg',plan,'mp4',lambda:False)
    with av.open(str(tmp_path/'output.mp4')) as container:
        # Push-in occupies the first leg; only the latter orbit returns to center.
        assert len(list(container.decode(video=0)))==91
    assert (tmp_path/'poster.jpg').is_file()


def test_acpf_both_geometries_share_exact_h3():
    import yaml
    p=Path(__file__).parents[1]/'provisioning/profiles/imagine-frozen-time.yaml'
    data=yaml.safe_load(p.read_text())
    CapabilityProfileRegistry()
    for key in ('da','vggt'):
        components=data['capabilities']['image.frozen_time.'+key]['profiles'][0]['stack']['components']
        assert next(c for c in components if c['id']=='h3')['version']=='==0.11.0'
        assert next(c for c in components if c['id']=='h3-checkpoint')['model_id'].endswith('/fl2va-8bit')


def test_private_preview_then_render_reuses_geometry(surface,monkeypatch):
    client,headers,_=surface
    async def geometry(runtime,source,directory,**kwargs):
        (directory/'model-input.png').write_bytes(source.read_bytes())
        (directory/'reference.mp4').write_bytes(b'geometry')
        (directory/'preview.mp4').write_bytes(b'playback-preview')
        return (512,512,('saved-camera-plan',))
    monkeypatch.setattr('ai2apps.api.frozen_preview.prepare_preview',geometry)
    image=BytesIO();Image.new('RGB',(64,64)).save(image,format='PNG')
    settings={'depth':'vggt','mode':'orbit','output':'mp4','long_edge':'512','trajectory':json.dumps(frame_payload('orbit'))}
    base='/imagine-studio/frozen-time'
    preview=client.post(base+'/mounts/test/previews',headers=headers,
        files={'image':('input.png',image.getvalue(),'image/png')},data=settings).json()
    token=preview['id']
    assert client.get('/imagine-studio/runs',headers=headers).json()['items']==[]
    assert client.get(base+'/previews/'+token,headers=headers).json()['status']=='succeeded'
    assert client.get(base+'/previews/'+token+'/video',headers=headers).content==b'playback-preview'
    wrong={'X-AI2Apps-App-Instance':'appi_'+'c'*32}
    assert client.get(base+'/previews/'+token,headers=wrong).status_code==404
    run=client.post(base+'/mounts/test/runs',headers=headers).json()
    url='/imagine-studio/runs/'+run['id']+'/frozen-time'
    assert client.post(url,headers=headers,data={**settings,'trajectory':json.dumps(frame_payload('arc')),'preview_id':token}).status_code==409
    assert client.post(url,headers=headers,data={**settings,'trajectory':'{}','preview_id':token}).status_code==422
    assert client.post(url,headers=headers,data={**settings,'reference_speedup':'false','preview_id':token}).status_code==409
    sound_buffer=BytesIO()
    with wave_open(sound_buffer,'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(48000);output.writeframes(b'\0\0'*4800)
    sound_bytes=sound_buffer.getvalue()
    async def render(runtime,source,directory,**kwargs):
        assert 'amplitude' not in kwargs and 'mode' not in kwargs
        assert kwargs['prepared']==(512,512,('saved-camera-plan',))
        assert kwargs['reference_speedup'] is True
        assert (directory/'reference.mp4').read_bytes()==b'geometry'
        assert source.read_bytes()==(directory/'model-input.png').read_bytes()
        assert kwargs['soundtrack'].read_bytes()==sound_bytes
        (directory/'poster.jpg').write_bytes(b'poster')
        (directory/'output.mp4').write_bytes(b'rendered')
        return [('output.mp4','video','video/mp4')]
    monkeypatch.setattr('ai2apps.api.imagine_frozen_time.generate',render)
    assert client.post(url,headers=headers,data={**settings,'preview_id':token},files={'audio':('music.wav',sound_bytes,'audio/wav')}).status_code==202
    result=client.get('/imagine-studio/runs/'+run['id'],headers=headers).json()
    assert result['status']=='succeeded' and len(result['artifacts'])==1
    assert client.get(base+'/previews/'+token,headers=headers).status_code==404


def test_preview_cancel_never_creates_output(surface,monkeypatch):
    client,headers,_=surface
    async def geometry(runtime,source,directory,**kwargs):
        (directory/'reference.mp4').write_bytes(b'geometry')
        return (512,512,())
    monkeypatch.setattr('ai2apps.api.frozen_preview.prepare_preview',geometry)
    source=BytesIO();Image.new('RGB',(64,64)).save(source,format='PNG')
    base='/imagine-studio/frozen-time'
    result=client.post(base+'/mounts/test/previews',headers=headers,files={'image':('input.png',source.getvalue(),'image/png')},data={'trajectory':json.dumps(frame_payload())}).json()
    assert client.delete(base+'/previews/'+result['id'],headers=headers).status_code==200
    assert client.get(base+'/previews/'+result['id']+'/video',headers=headers).status_code==404
    assert client.get('/imagine-studio/runs',headers=headers).json()['items']==[]


def test_convert_completed_run_is_scoped_and_outputs_new_run(surface,monkeypatch):
    client,headers,config=surface
    run=client.post('/imagine-studio/frozen-time/mounts/test/runs',headers=headers).json()
    path=config.paths.artifacts_path/'imagine-frozen-time'/run['id'];path.mkdir(parents=True)
    (path/'output.mp4').write_bytes(b'old-video')
    (path/'poster.jpg').write_bytes(b'poster')
    client.patch('/imagine-studio/runs/'+run['id'],headers=headers,json={'status':'running'})
    client.patch('/imagine-studio/runs/'+run['id'],headers=headers,json={'status':'succeeded'})
    async def convert(source,destination,output,original,cancelled):
        assert source==path and output=='html'
        (destination/'output.mp4').write_bytes(b'converted-video')
        (destination/'poster.jpg').write_bytes(b'poster')
        (destination/'output.html').write_text('<html>converted</html>')
        return [('output.html','document','text/html'),('output.mp4','video','video/mp4')]
    monkeypatch.setattr('ai2apps.api.imagine_frozen_time.convert_saved',convert)
    url='/imagine-studio/frozen-time/mounts/test/runs/'+run['id']+'/convert'
    assert client.post(url,headers=headers,data={'output':'bogus'}).status_code==422
    wrong={'X-AI2Apps-App-Instance':'appi_'+'c'*32}
    assert client.post(url,headers=wrong,data={'output':'html'}).status_code==404
    response=client.post(url,headers=headers,data={'output':'html'})
    assert response.status_code==202
    result=client.get('/imagine-studio/runs/'+response.json()['id'],headers=headers).json()
    assert result['id']!=run['id'] and result['status']=='succeeded'
    assert len(result['artifacts'])==2
    assert (path/'output.mp4').read_bytes()==b'old-video'


@pytest.fixture
def surface(tmp_path,monkeypatch):
    config=PlatformConfig.from_base_path(tmp_path)
    db=PlatformDatabase(config.paths.database_path);db.initialize()
    principal=RequestPrincipal.legacy_local();instance='appi_'+'b'*32
    class Extensions:
        def require_instance_access(self, iid, actor):
            if iid!=instance:
                from fastapi import HTTPException
                raise HTTPException(404)
        def instance_entry(self,iid,**kwargs):return {'app_key':'ai2apps.imagine-studio'}
    class Models:
        def model(self,mid):return SimpleNamespace(checkpoint_ready=True, capabilities=['depth_estimation','video_generation'])
    runtime=SimpleNamespace(config=config,database=db,extension_manager=Extensions(),events=None,model_invocations=Models())
    monkeypatch.setattr('ai2apps.studio.capability_broker.StudioCapabilityBroker.mounted_mini_app',
        lambda *args,**kwargs:SimpleNamespace(declaration={'id':'ai2apps.imagine.frozen-time','version':'0.1.0'},
            capabilities={'image.frozen_time.da','image.frozen_time.vggt'}))
    app=FastAPI();app.include_router(create_imagine_studio_router(lambda:runtime,lambda:principal))
    with TestClient(app) as client:yield client,{'X-AI2Apps-App-Instance':instance},config


def test_save_native_live_photo_is_scoped_unique_and_requires_pair(surface,monkeypatch,tmp_path):
    client,headers,config=surface
    from ai2apps.native_export import NativeExportBroker
    broker=NativeExportBroker()
    broker.claim_next()
    chosen=tmp_path/'User selected location';chosen.mkdir()
    original_wait=broker.wait
    def picker_wait(identifier):
        broker.claim_next()
        broker.finish(identifier,path=str(chosen/(identifier+'.pvt')))
        return original_wait(identifier)
    monkeypatch.setattr(broker,'wait',picker_wait)
    monkeypatch.setattr('ai2apps.native_export.native_export_broker',broker)
    run=client.post('/imagine-studio/frozen-time/mounts/test/runs',headers=headers).json()
    url='/imagine-studio/frozen-time/mounts/test/runs/'+run['id']+'/save-live-photo'
    assert client.post(url,headers=headers).status_code==404
    client.patch('/imagine-studio/runs/'+run['id'],headers=headers,json={'status':'running'})
    client.patch('/imagine-studio/runs/'+run['id'],headers=headers,json={'status':'succeeded'})
    assert client.post(url,headers=headers).status_code==409
    path=config.paths.artifacts_path/'imagine-frozen-time'/run['id'];path.mkdir(parents=True)
    (path/'LivePhoto.jpg').write_bytes(b'paired-jpeg')
    (path/'LivePhoto.mov').write_bytes(b'paired-mov')
    assert client.post(url,headers={'X-AI2Apps-App-Instance':'appi_'+'c'*32}).status_code==404
    first=client.post(url,headers=headers).json()
    second=client.post(url,headers=headers).json()
    assert first['path']!=second['path']
    destination=Path(first['path'])
    assert destination.parent==chosen and destination.suffix=='.pvt'
    assert not (tmp_path/'Downloads').exists()
    assert (destination/'LivePhoto.mov').read_bytes()==b'paired-mov'
    import plistlib
    assert plistlib.loads((destination/'metadata.plist').read_bytes())=={'PFVideoComplementMetadataVersionKey':'1'}
    assert len(client.get('/imagine-studio/runs',headers=headers).json()['items'])==1
    direct='/imagine-studio/runs/'+run['id']+'/save-live-photo'
    assert client.post(direct,headers={'X-AI2Apps-App-Instance':'appi_'+'c'*32}).status_code==404
    assert client.post(direct,headers=headers).status_code==200


def test_frozen_api_owned_artifacts_and_rejected_duplicates(surface,monkeypatch):
    client,headers,config=surface
    async def fake_generate(runtime,source,directory,**kwargs):
        assert kwargs['depth']=='vggt'
        assert not kwargs['cancelled']()
        (directory/'output.html').write_text('<html>offline</html>')
        (directory/'output.mp4').write_bytes(b'video')
        (directory/'poster.jpg').write_bytes(b'poster')
        return [('output.html','document','text/html'),('output.mp4','video','video/mp4')]
    monkeypatch.setattr('ai2apps.api.imagine_frozen_time.generate',fake_generate)
    run=client.post('/imagine-studio/frozen-time/mounts/test/runs',headers=headers).json()
    source=BytesIO();Image.new('RGB',(64,64)).save(source,format='PNG')
    url=f"/imagine-studio/runs/{run['id']}/frozen-time"
    assert client.post(url,headers=headers,files={'image':('a.png',source.getvalue(),'image/png')},data={'output':'bogus'}).status_code==422
    assert client.post(url,headers=headers,data={'trajectory':json.dumps(frame_payload())},files={'image':('a.png',source.getvalue(),'image/png')}).status_code==202
    assert client.post(url,headers=headers,data={'trajectory':json.dumps(frame_payload())},files={'image':('a.png',source.getvalue(),'image/png')}).status_code==409
    result=client.get('/imagine-studio/runs',headers=headers).json()['items'][0]
    assert result['status']=='succeeded' and len(result['artifacts'])==2
    content=f"/imagine-studio/runs/{run['id']}/frozen-content/output.html?appInstanceId={headers['X-AI2Apps-App-Instance']}"
    response=client.get(content)
    assert response.status_code==200 and 'sandbox allow-scripts' in response.headers['content-security-policy']
    assert client.get(content.replace(headers['X-AI2Apps-App-Instance'],'appi_'+'a'*32)).status_code==404
    assert client.get(content.replace('output.html','input.png')).status_code==404
    client.delete('/imagine-studio/runs/'+run['id'],headers=headers)
    assert not (config.paths.artifacts_path/'imagine-frozen-time'/run['id']).exists()
    assert client.get(content).status_code==404


def test_frozen_recovery(surface):
    client,headers,_=surface
    run=client.post('/imagine-studio/frozen-time/mounts/test/runs',headers=headers).json()
    client.patch('/imagine-studio/runs/'+run['id'],headers=headers,json={'status':'running','progress':35})
    result=client.get('/imagine-studio/runs',headers=headers).json()['items'][0]
    assert result['status']=='failed' and result['error']['code']=='host_restarted'


def test_frozen_mp4_gallery_import_is_owned_and_preserves_video(surface, monkeypatch):
    client, headers, config = surface
    async def fake_generate(runtime, source, directory, **kwargs):
        encode_frames(directory/'output.mp4', (np.zeros((32,32,3),dtype='uint8') for _ in range(3)), 32, 32)
        Image.new('RGB',(32,32)).save(directory/'poster.jpg')
        return [('output.mp4','video','video/mp4')]
    monkeypatch.setattr('ai2apps.api.imagine_frozen_time.generate',fake_generate)
    run=client.post('/imagine-studio/frozen-time/mounts/test/runs',headers=headers).json()
    source=BytesIO();Image.new('RGB',(64,64)).save(source,format='PNG')
    assert client.post(f"/imagine-studio/runs/{run['id']}/frozen-time",headers=headers,
        files={'image':('a.png',source.getvalue(),'image/png')},
        data={'output':'mp4','trajectory':json.dumps(frame_payload())}).status_code==202
    artifact=client.get('/imagine-studio/runs',headers=headers).json()['items'][0]['artifacts'][0]
    url=f"/imagine-studio/artifacts/{artifact['id']}/gallery"
    assert client.post(url,headers={'X-AI2Apps-App-Instance':'appi_'+'c'*32},json={}).status_code==404
    imported=client.post(url,headers=headers,json={})
    assert imported.status_code==201, imported.text
    assert imported.json()['asset']['kind']=='video'


@pytest.mark.parametrize('requested', [None, -1, 0, 42, 4294967295])
def test_random_seed_default_and_fixed_seed(surface,monkeypatch,requested):
    client,headers,_=surface
    monkeypatch.setattr('ai2apps.api.imagine_frozen_time.SystemRandom',lambda:SimpleNamespace(randrange=lambda limit:123456789))
    expected=123456789 if requested in (None,-1) else requested
    async def fake_generate(runtime,source,directory,**kwargs):
        assert kwargs['seed']==expected
        (directory/'output.mp4').write_bytes(b'video')
        (directory/'poster.jpg').write_bytes(b'poster')
        return [('output.mp4','video','video/mp4')]
    monkeypatch.setattr('ai2apps.api.imagine_frozen_time.generate',fake_generate)
    run=client.post('/imagine-studio/frozen-time/mounts/test/runs',headers=headers).json()
    source=BytesIO();Image.new('RGB',(64,64)).save(source,format='PNG')
    url='/imagine-studio/runs/'+run['id']+'/frozen-time'
    for invalid in (-2,4294967296):
        assert client.post(url,headers=headers,data={'seed':invalid}).status_code==422
    data={} if requested is None else {'seed':requested}
    assert client.post(url,headers=headers,data={**data,'trajectory':json.dumps(frame_payload())},files={'image':('a.png',source.getvalue(),'image/png')}).status_code==202
    result=client.get('/imagine-studio/runs/'+run['id'],headers=headers).json()
    assert result['status']=='succeeded'
    assert result['artifacts'][0]['metadata']['seed']==expected
    assert result['artifacts'][0]['metadata']['requestedSeed']==(-1 if requested is None else requested)
    assert str(expected) in result['steps'][0]['detail']
