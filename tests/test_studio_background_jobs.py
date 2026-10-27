import asyncio
import json
from types import SimpleNamespace

import pytest
from ai2apps.identity import RequestPrincipal, MemberRole
from ai2apps.storage import PlatformDatabase
from ai2apps.studio.background import StudioBackgroundJobs


def principal(actor='owner'):
    return RequestPrincipal(actor, 'installation', 'organization', 'billing', MemberRole.OWNER, 1)


def service(tmp_path):
    db = PlatformDatabase(tmp_path / 'platform.sqlite3'); db.initialize()
    runtime = SimpleNamespace(database=db, config=SimpleNamespace(paths=SimpleNamespace(base_path=tmp_path)))
    return StudioBackgroundJobs(runtime)


def submit(manager, key='request-1', actor='owner'):
    return manager.submit(principal=principal(actor), app_instance_id='app', studio_id='studio',
        mini_app_id='mini', kind='quick-read', key=key, payload={'text': 'hello'})


async def wait_status(manager, identifier, status):
    for _ in range(200):
        if manager.get(identifier, principal())['status'] == status:
            return
        await asyncio.sleep(.005)
    assert manager.get(identifier, principal())['status'] == status


async def test_detached_execution_and_idempotent_submission(tmp_path):
    manager=service(tmp_path); release=asyncio.Event(); calls=[]
    async def execute(job):
        calls.append(job['id']); await release.wait(); return b'audio', {'title':'hello'}
    manager.execute=execute; manager.publish=lambda job,path:{'downloadUrl':'/saved'}
    job=submit(manager); assert submit(manager)['id']==job['id']
    await manager.startup(); await wait_status(manager,job['id'],'running')
    # There is no request/DOM/connection object retained by the worker.
    release.set(); await wait_status(manager,job['id'],'succeeded')
    assert len(calls)==1; assert submit(manager)['status']=='succeeded'
    await manager.shutdown()


def test_isolation_and_key_conflict(tmp_path):
    manager=service(tmp_path); job=submit(manager)
    with pytest.raises(KeyError):manager.get(job['id'],principal('other'))
    assert manager.list(principal('other'),'studio')==[]
    assert submit(manager,actor='other')['id']!=job['id']
    with pytest.raises(ValueError):manager.submit(principal=principal(),app_instance_id='app',studio_id='studio',mini_app_id='mini',kind='quick-read',key='request-1',payload={'text':'different'})


async def test_restart_publishes_checkpoint_without_regeneration(tmp_path):
    manager=service(tmp_path); job=submit(manager); path=manager.root/job['id'];path.mkdir(exist_ok=True)
    (path/'output').write_bytes(b'audio');(path/'result.json').write_text('{}')
    manager._update(job['id'],'running')
    async def forbidden(job):raise AssertionError('must not regenerate')
    manager.execute=forbidden; manager.publish=lambda job,path:{'downloadUrl':'/saved'}
    await manager.startup();await wait_status(manager,job['id'],'succeeded');await manager.shutdown()


async def test_interrupted_inference_requires_explicit_retry(tmp_path):
    manager=service(tmp_path);job=submit(manager);manager._update(job['id'],'running')
    manager.execute=lambda job:None
    await manager.startup();assert manager.get(job['id'],principal())['status']=='interrupted';await manager.shutdown()


async def test_publish_retry_reuses_checkpoint(tmp_path):
    manager=service(tmp_path);calls=[]
    async def execute(job):calls.append(job['id']);return b'audio',{}
    def fail(job,path):raise ValueError('storage temporarily unavailable')
    manager.execute=execute;manager.publish=fail;job=submit(manager)
    await manager.startup();await wait_status(manager,job['id'],'publish_failed')
    manager.publish=lambda job,path:{'downloadUrl':'/saved'}
    manager.retry(job['id'],principal());await wait_status(manager,job['id'],'succeeded')
    assert len(calls)==1;await manager.shutdown()


async def test_cancel_does_not_stop_dispatcher(tmp_path):
    manager=service(tmp_path);release=asyncio.Event()
    async def execute(job):await release.wait();return b'audio',{}
    manager.execute=execute;manager.publish=lambda job,path:{}
    first=submit(manager);second=submit(manager,key='request-2')
    await manager.startup();await wait_status(manager,first['id'],'running')
    manager.cancel(first['id'],principal());await wait_status(manager,first['id'],'cancelled')
    release.set();await wait_status(manager,second['id'],'succeeded');await manager.shutdown()


def publication_service(tmp_path, studio):
    from ai2apps.config import PlatformConfig
    from ai2apps.events import EventStore
    from ai2apps.workspace import WorkspaceRepository
    from ai2apps.storage.repositories import AppRepository
    from ai2apps.core import AppInstanceMode, SingletonScope
    from ai2apps.identity import user_singleton_key
    from ai2apps.readaloud.tasks import ReadAloudTaskManager
    manager = service(tmp_path)
    runtime = manager.runtime
    runtime.config = PlatformConfig.from_base_path(tmp_path)
    runtime.events = EventStore(manager.database)
    runtime.workspace = WorkspaceRepository(manager.database, runtime.events, runtime.config.paths)
    apps = AppRepository(manager.database)
    definition = apps.create_definition(package_id=studio, package_version='1', display_name='Studio',
        instance_mode=AppInstanceMode.SINGLETON, singleton_scope=SingletonScope.USER)
    instance = apps.create_instance(app_definition_id=definition.id, owner_user_id='owner', singleton_key=user_singleton_key(studio, 'owner'))
    runtime.readaloud_tasks = ReadAloudTaskManager(runtime=runtime, database=manager.database,
        workspace=runtime.workspace, root=tmp_path/'voice')
    return manager, instance.id


def test_voice_publish_is_idempotent_and_shared_output_survives_new_manager(tmp_path):
    manager, app = publication_service(tmp_path, 'ai2apps.readaloud')
    job = manager.submit(principal=principal(), app_instance_id=app, studio_id='ai2apps.readaloud',
        mini_app_id='ai2apps.audio.quick-read', kind='quick-read', key='voice-one', payload={'text':'hello'})
    path = manager.root/job['id']; (path/'output').write_bytes(b'RIFF-audio')
    (path/'result.json').write_text(json.dumps({'title':'hello','voice':'Alice'}))
    with manager.database.transaction() as db:
        record = dict(db.execute('SELECT * FROM studio_background_jobs WHERE id=?', (job['id'],)).fetchone())
    first = manager.publish(record,path)
    assert manager.publish(record,path) == first
    history = manager.runtime.readaloud_tasks.output_history('owner')
    assert len(history) == 1
    assert history[0]['downloadUrl'] == first['downloadUrl']
    assert manager.runtime.readaloud_tasks.output_history('other') == []


def test_image_publish_is_idempotent_and_owned(tmp_path):
    from ai2apps.studio.repository import StudioRepository
    manager, app = publication_service(tmp_path, 'ai2apps.imagine-studio')
    scope = dict(actor_id='owner', installation_id='installation', app_instance_id=app, studio_id='ai2apps.imagine-studio')
    repository = StudioRepository(manager.database)
    run = repository.create_run(**scope, mini_app_id='ai2apps.imagine.text-to-image', mini_app_version='1', placement='create', title='Image', input_data={})
    job = manager.submit(principal=principal(),app_instance_id=app,studio_id=scope['studio_id'],mini_app_id=run['miniAppId'],
        kind='local-image',key='image-one',payload={'model':'image','prompt':'test'},run_id=run['id'])
    path=manager.root/job['id'];path.mkdir();(path/'output').write_bytes(b'\x89PNG\r\n\x1a\nimage')
    (path/'result.json').write_text(json.dumps({'media_type':'image/png'}))
    record = dict(job, **scope, kind='local-image')
    first=manager.publish(record,path)
    assert manager.publish(record,path)==first
    restored=repository.get_run(run['id'],**scope)
    assert restored['status']=='succeeded'
    assert len(restored['artifacts'])==1
    assert manager.for_run(run['id'],principal('other')) is None
    assert manager.for_run(run['id'],principal())['id']==job['id']


async def test_image_worker_uses_background_scheduler(tmp_path):
    import base64
    from fastapi.responses import JSONResponse
    from ai2apps.studio.repository import StudioRepository
    manager, app = publication_service(tmp_path, 'ai2apps.imagine-studio')
    scope=dict(actor_id='owner',installation_id='installation',app_instance_id=app,studio_id='ai2apps.imagine-studio')
    run=StudioRepository(manager.database).create_run(**scope,mini_app_id='ai2apps.imagine.text-to-image',mini_app_version='1',placement='create',title='Image',input_data={})
    calls=[]
    async def invoke(model, operation, payload, **options):
        calls.append((model,operation,options))
        return JSONResponse({'data':[{'b64_json':base64.b64encode(b'\x89PNG\r\n\x1a\nimage').decode()}]})
    manager.runtime.model_invocations=SimpleNamespace(model=lambda key:SimpleNamespace(id=key,model_type='image_generation',checkpoint_ready=True),
        context_for_actor=lambda *args,**kwargs:kwargs, invoke_background_json=invoke)
    job=manager.submit(principal=principal(),app_instance_id=app,studio_id=scope['studio_id'],mini_app_id=run['miniAppId'],kind='local-image',key='image-one',payload={'model':'image','prompt':'test'},run_id=run['id'])
    await manager.startup();await wait_status(manager,job['id'],'succeeded');await manager.shutdown()
    assert calls[0][:2]==('image','image_generation')
    assert calls[0][2]['request_id']==job['id']
    assert not (manager.root/job['id']).exists()
    assert StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts']


async def test_image_publish_failure_retry_reopens_only_owned_run_without_inference(tmp_path):
    from ai2apps.studio.repository import StudioRepository
    manager, app=publication_service(tmp_path,'ai2apps.imagine-studio')
    scope=dict(actor_id='owner',installation_id='installation',app_instance_id=app,studio_id='ai2apps.imagine-studio')
    repository=StudioRepository(manager.database)
    run=repository.create_run(**scope,mini_app_id='ai2apps.imagine.text-to-image',mini_app_version='1',placement='create',title='Image',input_data={})
    job=manager.submit(principal=principal(),app_instance_id=app,studio_id=scope['studio_id'],mini_app_id=run['miniAppId'],kind='local-image',key='image-one',payload={'model':'image','prompt':'test'},run_id=run['id'])
    calls=[]
    async def execute(job):calls.append(job['id']);return b'\x89PNG\r\n\x1a\nimage',{'media_type':'image/png'}
    actual_publish=manager.publish
    manager.execute=execute
    manager.publish=lambda *args:(_ for _ in ()).throw(OSError('disk unavailable'))
    await manager.startup();await wait_status(manager,job['id'],'publish_failed')
    assert repository.get_run(run['id'],**scope)['status']=='failed'
    manager.publish=actual_publish
    manager.retry(job['id'],principal());await wait_status(manager,job['id'],'succeeded');await manager.shutdown()
    assert len(calls)==1
    assert repository.get_run(run['id'],**scope)['status']=='succeeded'


async def test_quick_worker_does_not_read_modified_profile(tmp_path, monkeypatch):
    from ai2apps.readaloud import ReadAloudRepository
    from fastapi.responses import Response
    manager,app=publication_service(tmp_path,'ai2apps.readaloud')
    profile={'id':'voice','name':'Original','model_id':'speech','training':{'design':{'description':'Original voice'}}}
    monkeypatch.setattr(ReadAloudRepository,'get_voice_profile',lambda *args:profile)
    model=SimpleNamespace(id='speech',model_type='audio_tts',checkpoint_ready=True,audio_capabilities={})
    calls=[]
    async def invoke(model,operation,payload,**kwargs):calls.append(payload);return Response(b'RIFF-test-wave')
    manager.runtime.model_invocations=SimpleNamespace(model=lambda key:model,context_for_actor=lambda *args,**kwargs:None,invoke_background_json=invoke)
    job=manager.submit(principal=principal(),app_instance_id=app,studio_id='ai2apps.readaloud',mini_app_id='ai2apps.audio.quick-read',kind='quick-read',key='voice-one',payload={'text':'hello','model_id':'speech','voice_profile_id':'voice'})
    profile['training']['design']['description']='Changed voice'
    await manager.startup();await wait_status(manager,job['id'],'succeeded');await manager.shutdown()
    assert calls[0]['instructions']=='Original voice'
    assert manager.runtime.readaloud_tasks.output_history('owner')[0]['downloadUrl']


def test_api_owner_isolation_validation_and_idempotency(tmp_path):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from ai2apps.api.studio_background import create_studio_background_router
    manager,app_id=publication_service(tmp_path,'ai2apps.readaloud')
    runtime=manager.runtime;runtime.studio_jobs=manager
    identity=[principal()]
    def access(instance, actor):
        if instance!=app_id or actor.actor_user_id!='owner':raise HTTPException(404,'Not found')
    runtime.extension_manager=SimpleNamespace(require_instance_access=access,instance_entry=lambda *args,**kwargs:{'app_key':'ai2apps.readaloud'})
    runtime.model_invocations=SimpleNamespace(model=lambda key:SimpleNamespace(model_type='audio_tts',checkpoint_ready=True) if key=='speech' else None)
    app=FastAPI();app.include_router(create_studio_background_router(lambda:runtime,lambda:identity[0]))
    with TestClient(app) as client:
        headers={'X-AI2Apps-App-Instance':app_id,'Idempotency-Key':'voice-request'}
        body={'kind':'quick-read','payload':{'text':'hello','model_id':'speech'}}
        response=client.post('/studio-jobs',headers=headers,json=body)
        assert response.status_code==202,response.text
        identifier=response.json()['id']
        assert client.post('/studio-jobs',headers=headers,json=body).json()['id']==identifier
        body['payload']['text']='changed'
        assert client.post('/studio-jobs',headers=headers,json=body).status_code==409
        identity[0]=principal('other')
        assert client.get('/studio-jobs/'+identifier).status_code==404
        assert client.post('/studio-jobs/'+identifier+'/cancel').status_code==404
        assert client.get('/studio-jobs?studio_id=ai2apps.readaloud').json()['items']==[]
        assert client.post('/studio-jobs',headers=headers,json=body).status_code==404
        identity[0]=principal()
        assert client.post('/studio-jobs/'+identifier+'/cancel').json()['status']=='cancelled'


async def test_cancel_image_before_worker_body_updates_run_and_dispatcher(tmp_path):
    from ai2apps.studio.repository import StudioRepository
    manager, app = publication_service(tmp_path, 'ai2apps.imagine-studio')
    scope = dict(actor_id='owner', installation_id='installation', app_instance_id=app, studio_id='ai2apps.imagine-studio')
    repository = StudioRepository(manager.database)
    run = repository.create_run(**scope, mini_app_id='ai2apps.imagine.text-to-image', mini_app_version='1', placement='create', title='Image', input_data={})
    job = manager.submit(principal=principal(), app_instance_id=app, studio_id=scope['studio_id'], mini_app_id=run['miniAppId'], kind='local-image', key='image-one', payload={'model':'image','prompt':'test'}, run_id=run['id'])
    async def forbidden(job): raise AssertionError('cancelled before inference')
    manager.execute = forbidden
    await manager.startup()
    await asyncio.sleep(0)  # Dispatcher has created the child; its body has not run.
    assert manager.active_id == job['id']
    manager.cancel(job['id'], principal())
    await wait_status(manager, job['id'], 'cancelled')
    assert repository.get_run(run['id'], **scope)['status'] == 'cancelled'
    assert not manager.runner.done()
    await manager.shutdown()
