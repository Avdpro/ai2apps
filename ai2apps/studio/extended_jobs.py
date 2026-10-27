"""Durable Studio adapters for previews, image exports and Frozen Time."""
from __future__ import annotations
import asyncio, hashlib, io, json, shutil, uuid
from pathlib import Path
from ai2apps.studio.repository import StudioRepository
from ai2apps.studio.image_jobs import checkpoint
from ai2apps.model_invocation import ModelInvocationContext


def submit(runtime, principal, app_instance_id, studio_id, mini_app_id, kind, payload, *, files=None, run_id=None, key=None):
    jobs=runtime.studio_jobs
    key=key or kind+'-'+(run_id or uuid.uuid4().hex)
    fingerprint=hashlib.sha256(json.dumps([payload,app_instance_id,mini_app_id],sort_keys=True).encode()+b''.join(k.encode()+hashlib.sha256(v).digest() for k,v in sorted((files or {}).items()))).hexdigest()
    with runtime.database.transaction() as db:
        old=db.execute('SELECT * FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND idempotency_key=?',(principal.actor_user_id,principal.installation_id,studio_id,key)).fetchone()
    if old:
        if json.loads(old['request_json']).get('fingerprint')!=fingerprint or old['kind']!=kind:raise ValueError('Submission changed')
        return jobs.public(old)
    root=jobs.root/('input-'+uuid.uuid4().hex);root.mkdir(mode=0o700)
    try:
        for name,data in (files or {}).items():
            if Path(name).name!=name:raise ValueError('Invalid input name')
            checkpoint(root/name,data,{})
        return jobs.submit(principal=principal,app_instance_id=app_instance_id,studio_id=studio_id,mini_app_id=mini_app_id,kind=kind,key=key,run_id=run_id,payload={**payload,'input_root':str(root),'fingerprint':fingerprint})
    except BaseException:shutil.rmtree(root,ignore_errors=True);raise


async def execute(manager,job,principal,payload):
    runtime=manager.runtime;root=Path(payload['input_root']);directory=manager.root/job['id']
    context=ModelInvocationContext.from_principal(principal,session_id=job['id'],app_instance_id=job['app_instance_id'],consumer_app_id=job['studio_id'])
    if job['run_id']:
        StudioRepository(manager.database).update_run(job['run_id'],**manager.scope(job),status='running',progress=5,detail='Processing')
    if job['kind']=='voice-preview':
        from ai2apps.readaloud.speech import invoke_speech
        inv=runtime.model_invocations;body=payload['body'];model=payload['model']
        try:
            if payload['operation']=='design':
                response=await invoke_speech(inv.invoke_background_json,model,'audio_speech',body,request_id=job['id'],context=context)
            else:
                response=await invoke_speech(inv.invoke_background_multipart,model,'audio_speech',data=body,files={'reference_audio':('reference.wav',(root/'reference'/'output').read_bytes(),'audio/wav')},request_id=job['id'],context=context)
        except asyncio.CancelledError:
            await inv.cancel_request(model,job['id']);raise
        if response.status_code>=400:raise ValueError('Voice preview generation failed')
        content=bytes(response.body)
        import wave
        if len(content)>64*1024*1024:raise ValueError('Voice preview is too large')
        with wave.open(io.BytesIO(content)) as audio:
            if audio.getnframes()<=0:raise ValueError('Empty voice preview')
        return content,{'title':payload['title'],'model_label':payload['model_label'],'mini_app_id':job['mini_app_id']}
    if job['kind']=='cloud-image':
        from ai2apps.studio.image_jobs import generate_image
        return await generate_image(runtime,principal,job,payload['body'],'imagine-run-'+job['run_id'])
    if job['kind']=='image-upscale':
        destination=directory/'upscaled.png';source=root/'image'/'output'
        await runtime.model_invocations.invoke_background_to_file(payload['model'],'image_upscaling',{'parameters':payload['parameters']},destination,files={'image':('input',source,payload['media_type'])},request_id=job['id'],cancel_requested=lambda:manager.get(job['id'],principal)['status']=='cancelled',context=context)
        from PIL import Image
        with Image.open(destination) as image:size=f'{image.width}x{image.height}'
        return destination,{'filename':'upscaled.png','media_type':'image/png','kind':'image','size':size,'model':payload['model'],'scale':2}
    if job['kind']=='image-adjust':
        from ai2apps.studio.image_adjustments import render, publish_target
        for index,item in enumerate(payload['items']):
            out=directory/f'item-{index}';key=job['id']+f'-{index}'
            if not (out/'result.json').exists():
                content=await asyncio.to_thread(render,(root/str(index)/'output').read_bytes(),payload['state'],item['media_type'])
                checkpoint(out,content,{'filename':item['name'],'media_type':item['media_type'],'kind':'image'})
            manager.publish(job,out,output_key=key,complete=False)
            if item.get('target') and not (out/'target.done').exists():
                await asyncio.to_thread(publish_target,runtime,principal,item['target'],(out/'output').read_bytes(),key)
                (out/'target.done').write_text('done')
            manager._update(job['id'],'running',result={'completed':index+1,'total':len(payload['items'])})
        return b'',{'batch':True,'completed':len(payload['items'])}
    if job['kind']=='frozen-time':
        return await render_frozen(manager,job,principal,payload)
    raise ValueError('Unknown durable Studio operation')


def publish_voice(manager,job,directory):
    from ai2apps.readaloud import ReadAloudRepository
    p=json.loads(job['request_json']);meta=json.loads((directory/'result.json').read_text())
    url=manager.runtime.readaloud_tasks.save_quick_audio(job['actor_id'],(directory/'output').read_bytes(),output_key=job['id'],**meta)
    repo=ReadAloudRepository(manager.database,manager.runtime.events);attached=False
    if p.get('profile_id'):
        try:
            if p['operation']=='design':
                preview={**p['preview'],'session_id':url.split('/')[4],'artifact_id':url.split('/')[-2],'download_url':url}
                attached=repo.attach_design_preview(job['actor_id'],p['profile_id'],tuple(p['expected']),preview)
            else:attached=repo.verify_training_preview(job['actor_id'],p['profile_id'],p['expected'])
        except Exception as error:
            from ai2apps.core import ResourceNotFoundError
            if not isinstance(error,ResourceNotFoundError):raise
    return {'downloadUrl':url,'profileId':p.get('profile_id'),'profileUpdated':attached}


async def render_frozen(manager,job,principal,p):
    from ai2apps.studio.frozen_time_pipeline import generate
    from ai2apps.studio.frozen_time_conversion import convert_saved,CACHE_FILES
    root=Path(p['input_root']);directory=manager.root/job['id']/'render';directory.mkdir(exist_ok=True)
    repo=StudioRepository(manager.database);scope=manager.scope(job)
    def cancelled():return manager.get(job['id'],principal)['status']=='cancelled'
    def progress(value,detail):repo.update_run(job['run_id'],**scope,status='running',progress=value,detail=detail)
    for source in root.iterdir():
        if source.is_dir():shutil.copyfile(source/'output',directory/source.name)
    soundtrack=directory/'soundtrack.audio' if (directory/'soundtrack.audio').exists() else None
    if p['operation']=='convert':
        source_dir=directory/'source';source_dir.mkdir(exist_ok=True)
        for source in root.iterdir():
            if source.is_dir():shutil.copyfile(source/'output',source_dir/source.name)
        artifacts=await convert_saved(source_dir,directory,p['output'],p['original_output'],cancelled,**({'soundtrack':soundtrack} if soundtrack else {}))
    else:
        context=ModelInvocationContext.from_principal(principal,session_id=job['id'],app_instance_id=job['app_instance_id'],consumer_app_id=job['studio_id'])
        from ai2apps.studio.frozen_time import CameraKey
        extra={'prepared':(p['prepared'][0],p['prepared'][1],tuple(CameraKey(**k) for k in p['prepared'][2]))} if p.get('prepared') else {}
        artifacts=await generate(manager.runtime,directory/'input.png',directory,**p['settings'],context=context,request_id=job['id'],cancelled=cancelled,progress=progress,soundtrack=soundtrack,**extra)
    if not artifacts:raise ValueError('Frozen Time did not produce output')
    return b'',{'frozen':True,'artifacts':artifacts,'metadata':p['metadata']}


def publish_frozen(manager,job,directory,metadata):
    from urllib.parse import quote
    from ai2apps.studio.frozen_time_conversion import CACHE_FILES
    source=directory/'render';destination=manager.runtime.config.paths.artifacts_path/'imagine-frozen-time'/job['run_id'];destination.mkdir(parents=True,exist_ok=True)
    for name in set(['poster.jpg']+[a[0] for a in metadata['artifacts']]+list(CACHE_FILES)):
        if (source/name).is_file():
            temporary=destination/(name+'.tmp');shutil.copyfile(source/name,temporary);temporary.replace(destination/name)
    base=f"/v1/platform/imagine-studio/runs/{job['run_id']}/frozen-content/";query='?appInstanceId='+quote(job['app_instance_id'],safe='')
    repo=StudioRepository(manager.database);scope=manager.scope(job);run=repo.get_run(job['run_id'],**scope)
    for name,kind,media in metadata['artifacts']:
        source_id=job['run_id']+':'+name
        if not any(a.get('sourceId')==source_id for a in run['artifacts']):
            repo.create_artifact(job['run_id'],kind=kind,name=name,media_type=media,preview_url=base+('output.mp4' if kind=='archive' else name)+query,download_url=base+name+query+'&download=true',source_id=source_id,metadata={**metadata['metadata'],'miniAppId':job['mini_app_id'],'posterUrl':base+'poster.jpg'+query},**scope)
    repo.update_run(job['run_id'],**scope,status='succeeded',progress=100,detail='Completed')
    return {'runId':job['run_id']}
