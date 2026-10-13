"""Private, bounded geometry previews; never Studio Runs or Output artifacts."""
import asyncio
from io import BytesIO
from pathlib import Path
import tempfile
import uuid

from fastapi import BackgroundTasks, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps

from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.studio.frozen_time_editor import parse_frame_plan
from ai2apps.studio.frozen_time_pipeline import DEPTH_MODELS, prepare_preview


async def normalize_upload(image):
    data = await image.read(20*1024*1024+1)
    if not data or len(data) > 20*1024*1024:
        raise HTTPException(413, 'Image exceeds 20 MiB')
    try:
        with Image.open(BytesIO(data)) as decoded:
            w,h = decoded.size
            if w*h > 16_000_000 or min(w,h)<32 or max(w,h)/min(w,h)>3:
                raise ValueError('Use an image up to 16 MP, aspect ratio 1:3 to 3:1')
            buffer = BytesIO()
            ImageOps.exif_transpose(decoded).convert('RGB').save(buffer,format='PNG')
            return buffer.getvalue()
    except Exception as error:
        raise HTTPException(422, 'Invalid image: '+str(error)[:200]) from error


class PreviewStore:
    def __init__(self):
        self.items = {}

    def discard(self, key):
        item = self.items.pop(key, None)
        if item:
            item['cancelled'] = True
            item['timer'].cancel()
            if item['status'] != 'running':
                item['temporary'].cleanup()

    def get(self, key, scope):
        item = self.items.get(key)
        if not item or item['scope'] != scope:
            raise HTTPException(404, 'Preview expired or not found')
        return item

    @staticmethod
    def public(key, item):
        return {'id':key, 'status':item['status'], 'progress':item['progress'],
                'detail':item['detail'], 'error':item.get('error')}


def register_preview(router, runtime_provider, principal_dependency, studio, scoped_kwargs, require_mount, ready):
    store = PreviewStore()

    @router.post('/frozen-time/mounts/{mount_id}/previews', status_code=202)
    async def create(mount_id: str, background_tasks: BackgroundTasks, image: UploadFile=File(),
                     depth: str=Form('vggt'), output: str=Form('live-photo'),
                     long_edge: int=Form(768), reference_speedup: bool=Form(True), trajectory: str=Form(''), app_instance_id: str=Header(alias='X-AI2Apps-App-Instance'),
                     principal=principal_dependency):
        studio(principal,app_instance_id)
        require_mount(mount_id,principal)
        try:
            trajectory=parse_frame_plan(trajectory)
        except (ValueError,TypeError) as error:
            raise HTTPException(422,str(error)) from error
        if depth not in DEPTH_MODELS or output not in {'html','mp4','live-photo'} or long_edge not in {512,768}:
            raise HTTPException(422,'Invalid Frozen Time settings')
        runtime = runtime_provider()
        if not ready(runtime,DEPTH_MODELS[depth],'depth_estimation'):
            raise HTTPException(409,'Configure the geometry model first')
        data = await normalize_upload(image)
        scope = scoped_kwargs(principal,app_instance_id)
        if len(store.items)>=16 or sum(item['scope']==scope for item in store.items.values())>=2:
            raise HTTPException(429,'Cancel or discard previous previews first')
        key = uuid.uuid4().hex
        temporary = tempfile.TemporaryDirectory(prefix='frozen-preview-')
        directory = Path(temporary.name)
        (directory/'input.png').write_bytes(data)
        item = dict(scope=scope, temporary=temporary, directory=directory, status='running', progress=0,
                    detail='Estimating depth',cancelled=False,
                    settings=dict(depth=depth,output=output,long_edge=long_edge,trajectory=trajectory,reference_speedup=reference_speedup))
        store.items[key] = item
        item['timer'] = asyncio.get_running_loop().call_later(1800,store.discard,key)
        context = ModelInvocationContext.from_principal(principal,session_id='frozen-preview:'+key,
            app_instance_id=app_instance_id,consumer_app_id='ai2apps.imagine-studio')
        async def work():
            def progress(value,detail):
                item.update(progress=value,detail=detail)
            try:
                item['prepared'] = await prepare_preview(runtime,directory/'input.png',directory,
                    **item['settings'],context=context,request_id='preview-'+key,
                    cancelled=lambda:item['cancelled'],progress=progress)
                item.update(status='succeeded',progress=100,detail='Preview ready')
            except Exception as error:
                item.update(status='failed',error=str(error)[:1000],detail='Preview failed')
            finally:
                if item['cancelled']:
                    temporary.cleanup()
        background_tasks.add_task(work)
        return store.public(key,item)

    @router.get('/frozen-time/previews/{key}')
    async def status(key: str, app_instance_id: str=Header(alias='X-AI2Apps-App-Instance'),principal=principal_dependency):
        studio(principal,app_instance_id)
        return store.public(key,store.get(key,scoped_kwargs(principal,app_instance_id)))

    @router.get('/frozen-time/previews/{key}/video')
    async def video(key: str, app_instance_id: str=Header(alias='X-AI2Apps-App-Instance'),principal=principal_dependency):
        studio(principal,app_instance_id)
        item = store.get(key,scoped_kwargs(principal,app_instance_id))
        if item['status'] != 'succeeded':
            raise HTTPException(409,'Preview is not ready')
        return FileResponse(item['directory']/'preview.mp4',media_type='video/mp4',headers={'Cache-Control':'private, no-store'})

    @router.delete('/frozen-time/previews/{key}')
    async def discard(key: str, app_instance_id: str=Header(alias='X-AI2Apps-App-Instance'),principal=principal_dependency):
        studio(principal,app_instance_id)
        store.get(key,scoped_kwargs(principal,app_instance_id))
        store.discard(key)
        return {'cancelled':True}
    return store
