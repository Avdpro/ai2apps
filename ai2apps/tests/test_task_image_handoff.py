"""Real Session copies, preflight, Task/Todo settlement; fixture model/output."""
import asyncio
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from PIL import Image

from agent_context_fixtures import owner_context
from test_app_interactions import runtime, wait
from test_app_chat_durable import bind_identity, response
from test_bot_capability_discovery import setup, P


def image(runtime, sid, path, name, color):
    Image.new('RGB',(32,24),color).save(path)
    return runtime.workspace.import_artifact(sid,path,name=name,media_type='image/png')


def test_context_rebases_only_verified_copies_without_mutating_source(runtime,tmp_path):
    from ai2apps.system_tasks.sessions import execution_session
    _,sid,_,_=setup(runtime)
    target=execution_session(runtime,'local','ai2apps.messager')
    source=image(runtime,sid,tmp_path/'source.png','source.png','red')
    missing=image(runtime,sid,tmp_path/'missing.png','missing.png','blue')
    refs=[{'session_id':sid,'artifact_id':source.id}]
    _,copies=runtime.messager_dialogue.copy_outputs(refs,sid,target)
    copied=copies[0]['artifact_id']
    # A forged source tag with different bytes cannot become a valid mapping.
    runtime.workspace.import_artifact(target,tmp_path/'source.png',name='forged.png',media_type='image/png',
        metadata={'source_session_id':sid,'source_artifact_id':missing.id})
    context={'memory_resources':refs,'task_sessions':[{'summary':f'Image {source.id}: /v1/platform/sessions/{sid}/artifacts/{source.id}/download'}],
             'other':f'/v1/platform/sessions/{sid}/artifacts/{missing.id}/download'}
    original=deepcopy(context)
    result=runtime.messager_dialogue.material_context(context,sid,target)
    assert context==original
    assert result['task_materials']['session_id']==target
    assert copied in {a['artifact_id'] for a in result['task_materials']['items']}
    assert result['memory_resources']==[{'session_id':target,'artifact_id':copied}]
    assert copied in result['task_sessions'][0]['summary'] and source.id not in str(result)
    assert f'/sessions/{target}/artifacts/{copied}/download' in result['task_sessions'][0]['summary']
    assert result['other']==context['other']


@pytest.mark.asyncio
@pytest.mark.parametrize('recover',[True,False])
async def test_task_repairs_reference_or_reports_failed_without_unknown_replay(runtime,tmp_path,monkeypatch,recover):
    from ai2apps.images.parameters import from_options
    async def models(*args):
        return [from_options('fixture-image','Fixture image',{'size':{'mode':'fixed','default':'1280x960','presets':['1280x960']}})],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    monkeypatch.setattr('ai2apps.images.service._default_image_model',lambda store:'fixture-image')
    bot,sid,_,_=setup(runtime)
    access=runtime.messager_bot_app_access;catalog=access.catalog('local',bot['id'])
    access.save('local',bot['id'],catalog['revision'],catalog['review_hash'],[{'app_id':'ai2apps.imagine-studio','enabled':True}])
    dialogue=runtime.messager_dialogue
    originals=[image(runtime,sid,tmp_path/'husky.png','husky.png','red'),image(runtime,sid,tmp_path/'panda.png','panda.png','blue')]
    refs=[{'session_id':sid,'artifact_id':a.id,'filename':a.name} for a in originals]
    dialogue.append(sid,'assistant','Existing husky and panda','fixture-originals',{'artifacts':refs})
    provider=runtime.app_capability_router.providers['ai2apps.imagine.group-photo'];calls=[]
    async def execute(args,ctx):
        calls.append(args)
        for aid in args['person_artifact_ids']:runtime.workspace.get_artifact(ctx.session_id,aid)
        path=tmp_path/'group.png';Image.new('RGB',(1280,960),'green').save(path)
        artifact=runtime.workspace.import_artifact(ctx.session_id,path,name='group.png',media_type='image/png')
        return {'artifact':{'id':artifact.id,'name':artifact.name,'media_type':artifact.media_type,
            'download_url':f'/v1/platform/sessions/{ctx.session_id}/artifacts/{artifact.id}/download'}}
    runtime.app_capability_router.providers[provider.id]=replace(provider,handler=execute)
    original_ids=[a.id for a in originals];current=[];described=False
    async def model(request):
        nonlocal described
        if 'Decide quickly' in request['messages'][0]['content']:
            return response(text=json.dumps({'kind':'task','text':'Queued','title':'Husky and panda 4:3'}))
        context=owner_context(request)
        current[:]=[a['artifact_id'] for a in context.get('memory_resources',[])]
        assert set(current).isdisjoint(original_ids) and len(current)==2
        inventory={a['artifact_id'] for a in context['task_materials']['items']}
        assert set(current)<=inventory
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if calls:return response(text='Verified group image delivered.')
        failures=[r['error'] for r in results if r.get('error',{}).get('code')=='provider_incompatible']
        if failures:
            assert failures[-1]['details']['phase']=='prepare' and not failures[-1].get('outcome_uncertain')
            if not recover:return response(text='The image could not be created; the source reference was unavailable.')
            if not any(isinstance(r.get('items'),list) and any(i.get('id') in current for i in r['items']) for r in results):return response('artifact.list',{})
        if not described:
            described=True
            return response('app.describe',{'capability':'image.group_photo'})
        return response('image.group_photo',{'provider':provider.id,'model':'fixture-image','size':'1280x960',
            'person_artifact_ids':current if failures else original_ids,'background':'bamboo forest'})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source=dialogue.submit(P(),bot['id'],sid,'group-43','生成它和之前画的熊猫的合影，画面比例4:3','fixture',[])
        await wait(runtime,source,'completed')
        # Access is preconfigured; effect approval remains a separate guard.
        # The fixture user explicitly approves each requested generation.
        for _ in range(600):
            with runtime.database.transaction() as db:
                job=dict(db.execute('SELECT * FROM messager_dialogue_jobs WHERE source_run=?',(source,)).fetchone())
            if job['worker_run']:
                for item in runtime.agents.list_interactions(job['worker_run']):
                    if item.status.value!='pending':continue
                    assert item.kind.value=='approval' and item.request.get('action_preview')
                    assert item.request['tool_name']=='image.group_photo'
                    runtime.agents.respond_interaction(job['worker_run'],item.id,response={'decision':'approve','scope':'once'},response_id='fixture-'+item.id)
                    runtime.agent_runtime.wake()
            if job['status'] in ('completed','failed'):break
            await asyncio.sleep(.02)
        assert job['status']==('completed' if recover else 'failed'),job
        run=runtime.agents.get_run(job['worker_run'])
        steps=runtime.agents.list_steps(run.id)
        failed=next(s for s in steps if s.tool_name=='image.group_photo' and (s.error or {}).get('code')=='provider_incompatible')
        assert failed.error['details']['submitted'] is False and not failed.error.get('outcome_uncertain')
        assert all(i.kind.value=='approval' and i.request.get('action_preview') for i in runtime.agents.list_interactions(run.id))
        assert len(calls)==int(recover)
        if recover:
            assert run.output['artifacts'] and calls[0]['person_artifact_ids']==current
        else:
            assert run.error['code']=='image_result_unavailable' and run.output['content']
        todo=next(r for r in runtime.todo.store.snapshot('local')['runs'] if r['task_id']==job['task_id'])
        assert todo['status']==run.status.value
        with runtime.database.transaction() as db:assert db.execute('SELECT count(*) FROM studio_background_jobs').fetchone()[0]==0
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize('capability',['arbitrary.render','independent.compose'])
async def test_owner_completion_check_is_scoped_and_retains_verified_output(runtime,tmp_path,capability):
    from ai2apps.services.aaat import AgentResultPolicy
    from test_aaat_execution_flow import register
    calls=[]
    async def execute(args,ctx):
        calls.append(args)
        path=tmp_path/'result.txt';path.write_text('verified partial result')
        a=runtime.workspace.import_artifact(ctx.session_id,path,name='result.txt',media_type='text/plain')
        return {'files':[{'url':f'/v1/platform/sessions/{ctx.session_id}/artifacts/{a.id}/download'}]}
    register(runtime,capability,execute,invocation_policy=lambda *args:True)
    runtime.app_capability_router.register_result_policy(AgentResultPolicy('fixture-required-output',lambda _:None,
        lambda content,steps:(content,None),capabilities=(capability,),
        completion_check=lambda steps,artifacts:{'code':'required_result_missing','message':'One required result is still missing.'}))
    def forbidden(*args):raise AssertionError('Unrelated owner check must not run')
    runtime.app_capability_router.register_result_policy(AgentResultPolicy('unrelated-required-output',lambda _:None,
        lambda content,steps:(content,None),capabilities=('foreign.operation',),completion_check=forbidden))
    async def model(request):
        return response(text='Here is the verified partial result.') if calls else response(capability,{'query':'fixture'})
    runtime.agent_runtime.bind_model_provider(model)
    from ai2apps.system_tasks.sessions import execution_session
    sid=execution_session(runtime,'local','ai2apps.messager')
    run,_=runtime.agents.create_run(session_id=sid,agent_key='ai2apps.general-agent',input={'model':'fixture','prompt':'Complete the fixture task','tools':[capability]})
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        for _ in range(600):
            result=runtime.agents.get_run(run.id)
            if result.status.value in ('completed','failed'):break
            await asyncio.sleep(.02)
        assert result.status.value=='failed' and result.error['code']=='required_result_missing'
        assert result.output['artifacts'] and result.output['content']=='Here is the verified partial result.'
        a=result.output['artifacts'][0]
        assert runtime.workspace.artifact_path(runtime.workspace.get_artifact(a['session_id'],a['artifact_id'])).read_text()=='verified partial result'
    finally:await runtime.stop_background_tasks()


@pytest.mark.parametrize('failure',['cross_session','unsupported_mime','invalid_bytes','removed_blob'])
def test_image_reference_validation_happens_before_submission(runtime,tmp_path,failure):
    from types import SimpleNamespace
    from ai2apps.images.agent_providers import preflight_references
    from ai2apps.services.capability_routing import ProviderIncompatible
    from ai2apps.system_tasks.sessions import execution_session
    _,sid,_,_=setup(runtime)
    target=execution_session(runtime,'local','ai2apps.messager') if failure=='cross_session' else sid
    path=tmp_path/'reference.png'
    if failure in ('unsupported_mime','invalid_bytes'):
        path.write_bytes(b'This is not an image')
        artifact=runtime.workspace.import_artifact(sid,path,name=path.name,
            media_type='text/plain' if failure=='unsupported_mime' else 'image/png')
    else:
        artifact=image(runtime,sid,path,'reference.png','red')
        if failure=='removed_blob':runtime.workspace.artifact_path(artifact).unlink()
    with pytest.raises(ProviderIncompatible,match='no image job was submitted'):
        preflight_references(runtime.workspace,SimpleNamespace(session_id=target),[artifact.id])
    with runtime.database.transaction() as db:
        assert db.execute('SELECT count(*) FROM studio_background_jobs').fetchone()[0]==0
