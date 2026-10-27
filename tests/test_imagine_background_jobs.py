import asyncio
import base64
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from ai2apps.studio.repository import StudioRepository
from ai2apps.api.studio_background import create_studio_background_router
from test_studio_background_jobs import publication_service, principal, wait_status

PNG = b'\x89PNG\r\n\x1a\nreference'
REFERENCE = 'data:image/png;base64,' + base64.b64encode(PNG).decode()


def setup(tmp_path, batch=False, source='local'):
    manager, app_id = publication_service(tmp_path, 'ai2apps.imagine-studio')
    runtime = manager.runtime
    runtime.studio_jobs = manager
    scope = dict(actor_id='owner', installation_id='installation', app_instance_id=app_id, studio_id='ai2apps.imagine-studio')
    mini = 'ai2apps.imagine.sticker-workshop' if batch else 'ai2apps.imagine.image-edit'
    run = StudioRepository(manager.database).create_run(**scope, mini_app_id=mini, mini_app_version='1', placement='create', title='Edit', input_data={'stickerBatch': batch})
    def access(instance, actor):
        if instance != app_id or actor.actor_user_id != 'owner':
            raise HTTPException(404, 'Not found')
    runtime.extension_manager=SimpleNamespace(require_instance_access=access, instance_entry=lambda *a,**k:{'app_key':'ai2apps.imagine-studio'})
    calls=[]
    async def invoke(model, operation, payload, **options):
        calls.append((operation, dict(payload), options))
        return JSONResponse({'image':{'dataUrl':REFERENCE}})
    model=SimpleNamespace(id='edit', model_type='image_generation', checkpoint_ready=True,
        image_capabilities={'operations':['image_edit'],'inputs':{'reference_images':{'minimum':1,'maximum':1}}})
    runtime.model_invocations=SimpleNamespace(model=lambda key:model if key=='edit' else None, invoke_background_json=invoke)
    payload={'model':'edit','prompt':'edit the image','imageDataUrls':[REFERENCE], 'use_kv_cache':False, 'strength':.25}
    if batch:payload.update(source=source, prompts=['happy','love','wow','sad'])
    job=manager.submit(principal=principal(),app_instance_id=app_id,studio_id=scope['studio_id'],mini_app_id=mini,
        kind='sticker-batch' if batch else 'local-image-edit',key='image-request',payload=payload,run_id=run['id'])
    return manager, scope, run, job, calls


async def test_local_edit_uses_snapshot_and_shared_output(tmp_path):
    manager, scope, run, job, calls = setup(tmp_path)
    # No HTTP request, live page or mount is available to the worker.
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        assert calls[0][0]=='image_edit'
        assert calls[0][1]['imageDataUrls']==[REFERENCE]
        assert calls[0][1]['strength']==.25 and calls[0][1]['use_kv_cache'] is False
        result=StudioRepository(manager.database).get_run(run['id'],**scope)
        assert len(result['artifacts'])==1
        assert result['artifacts'][0]['metadata']['miniAppId']=='ai2apps.imagine.image-edit'
    finally:await manager.shutdown()


async def test_batch_failure_retry_keeps_completed_items_and_checkpoints(tmp_path):
    manager, scope, run, job, calls=setup(tmp_path,batch=True)
    original=manager.publish
    failed=False
    def publish(record,path,**options):
        nonlocal failed
        if options.get('output_key','').endswith('-1') and not failed:
            failed=True;raise OSError('disk full')
        return original(record,path,**options)
    manager.publish=publish
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'failed')
        assert len(calls)==2
        assert len(StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts'])==1
        manager.retry(job['id'],principal())
        await wait_status(manager,job['id'],'succeeded')
        assert [x[1]['prompt'] for x in calls]==['happy','love','wow','sad']
        result=StudioRepository(manager.database).get_run(run['id'],**scope)
        assert len(result['artifacts'])==4
        assert len({a['sourceId'] for a in result['artifacts']})==4
        assert result['status']=='succeeded'
    finally:await manager.shutdown()


async def test_batch_stop_finishes_current_and_preserves_output(tmp_path):
    manager, scope, run, job, calls=setup(tmp_path,batch=True)
    began=asyncio.Event();release=asyncio.Event();invoke=manager.runtime.model_invocations.invoke_background_json
    async def held(*args,**kwargs):
        began.set();await release.wait();return await invoke(*args,**kwargs)
    manager.runtime.model_invocations.invoke_background_json=held
    await manager.startup()
    try:
        await began.wait()
        manager.stop_after_current(job['id'],principal());release.set()
        await wait_status(manager,job['id'],'cancelled')
        assert len(calls)==1
        result=StudioRepository(manager.database).get_run(run['id'],**scope)
        assert result['status']=='cancelled' and len(result['artifacts'])==1
    finally:await manager.shutdown()


async def test_cloud_batch_reuses_existing_api_with_stable_per_image_keys(tmp_path,monkeypatch):
    manager,scope,run,job,calls=setup(tmp_path,batch=True,source='cloud')
    runtime=manager.runtime;runtime.cloud=object();runtime.cloud_ai_authorization_headers=lambda p:{'test-owner':p.actor_user_id}
    received=[]
    async def cloud(payload,**options):
        received.append((payload,options));return {'image':{'dataUrl':REFERENCE}}
    monkeypatch.setattr('ai2apps.cloud_gateway.request_cloud_image',cloud)
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        assert not calls
        assert [x[0]['idempotencyKey'] for x in received]==[job['id']+f'-{i}' for i in range(4)]
        assert all(x[1]['edit'] and x[1]['cloud_headers']=={'test-owner':'owner'} for x in received)
    finally:await manager.shutdown()


def test_edit_submission_scope_and_reference_validation(tmp_path):
    manager,scope,run,job,calls=setup(tmp_path)
    # New key but same Run is protected against a second job as well.
    identity=[principal()]
    app=FastAPI();app.include_router(create_studio_background_router(lambda:manager.runtime,lambda:identity[0]))
    with TestClient(app) as client:
        headers={'X-AI2Apps-App-Instance':scope['app_instance_id'],'Idempotency-Key':'image-request'}
        body={'kind':'local-image-edit','run_id':run['id'],'payload':{'model':'edit','prompt':'edit the image','imageDataUrls':[REFERENCE]}}
        for change,status in [({'imageDataUrls':['https://example.com/image.png']},400),({'imageDataUrls':['data:image/png;base64,YQ==']},422),({'imageDataUrls':[REFERENCE,REFERENCE]},422),({'use_kv_cache':True},422),({'model':'missing'},409)]:
            r=client.post('/studio-jobs',headers=headers,json={**body,'payload':{**body['payload'],**change}})
            assert r.status_code==status,r.text
        r=client.post('/studio-jobs',headers=headers,json={**body,'kind':'sticker-batch','payload':{**body['payload'],'source':'local','prompts':['one']*4}})
        assert r.status_code==422
        identity[0]=principal('other')
        assert client.post('/studio-jobs',headers=headers,json=body).status_code==404
        assert client.post('/studio-jobs/'+job['id']+'/cancel?after_current=true').status_code==404

async def test_cancel_local_edit_requests_worker_cancel(tmp_path):
    manager,scope,run,job,calls=setup(tmp_path)
    began=asyncio.Event();cancelled=[]
    async def invoke(*a,**k):began.set();await asyncio.Event().wait()
    async def cancel(model,identifier):cancelled.append((model,identifier))
    manager.runtime.model_invocations.invoke_background_json=invoke
    manager.runtime.model_invocations.cancel_request=cancel
    await manager.startup()
    try:
        await began.wait();manager.cancel(job['id'],principal())
        await wait_status(manager,job['id'],'cancelled')
        assert cancelled==[('edit',job['id'])]
        assert not StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts']
    finally:await manager.shutdown()


async def test_batch_retry_after_restart_reuses_checkpoint(tmp_path):
    from ai2apps.studio.background import StudioBackgroundJobs
    manager,scope,run,job,calls=setup(tmp_path,batch=True)
    original=manager.publish
    def publish(record,path,**options):
        if options.get('output_key','').endswith('-1'):raise OSError('disk unavailable')
        return original(record,path,**options)
    manager.publish=publish
    await manager.startup();await wait_status(manager,job['id'],'failed');await manager.shutdown()
    fresh=StudioBackgroundJobs(manager.runtime)
    await fresh.startup()
    try:
        fresh.retry(job['id'],principal());await wait_status(fresh,job['id'],'succeeded')
        assert len(calls)==4
        assert len(StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts'])==4
    finally:await fresh.shutdown()


async def test_shared_output_gallery_import_and_scope(tmp_path):
    from ai2apps.api.imagine_studio import create_imagine_studio_router
    manager,scope,run,job,calls=setup(tmp_path)
    await manager.startup();await wait_status(manager,job['id'],'succeeded');await manager.shutdown()
    artifact=StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts'][0]
    identity=[principal()]
    app=FastAPI();app.include_router(create_imagine_studio_router(lambda:manager.runtime,lambda:identity[0]))
    with TestClient(app) as client:
        path='/imagine-studio/artifacts/'+artifact['id']+'/gallery'
        headers={'X-AI2Apps-App-Instance':scope['app_instance_id']}
        result=client.post(path,headers=headers,json={})
        assert result.status_code==201,result.text
        identity[0]=principal('other')
        assert client.post(path,headers=headers,json={}).status_code==404


def test_mobile_edit_acceptance_and_idempotency(tmp_path,monkeypatch):
    from dataclasses import replace
    manager,scope,run,job,calls=setup(tmp_path)
    identity=replace(principal(),authentication_type='owner_home_lease')
    monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda *a:True)
    new_run=StudioRepository(manager.database).create_run(**scope,mini_app_id='ai2apps.imagine.image-edit',mini_app_version='1',placement='create',title='Mobile',input_data={})
    app=FastAPI();app.include_router(create_studio_background_router(lambda:manager.runtime,lambda:identity))
    with TestClient(app) as client:
        headers={'X-AI2Apps-App-Instance':scope['app_instance_id'],'Idempotency-Key':'mobile-edit-key'}
        body={'kind':'local-image-edit','run_id':new_run['id'],'payload':{'model':'edit','prompt':'blue sky','imageDataUrls':[REFERENCE]}}
        result=client.post('/studio-jobs',headers=headers,json=body)
        assert result.status_code==202,result.text
        assert client.post('/studio-jobs',headers=headers,json=body).json()['id']==result.json()['id']
        assert not calls
        monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda *a:False)
        assert client.post('/studio-jobs',headers=headers,json=body).status_code==403
