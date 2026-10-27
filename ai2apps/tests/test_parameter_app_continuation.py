import asyncio
import io
import json
import httpx
import pytest
from fastapi import FastAPI
from PIL import Image
from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.studio.repository import StudioRepository
from test_app_interactions import runtime, wait
from ai2apps.chat import ChatRepository
from ai2apps.agents import CompleteAction, ToolCallAction
from ai2apps.agents.parameter_forms import form_action

@pytest.mark.asyncio
@pytest.mark.parametrize("choose_related", [False, True])
async def test_switch_and_app_completion_return_trusted_result_to_origin(runtime,monkeypatch,choose_related):
    import test_parameter_forms
    from ai2apps.images.parameters import from_options
    async def models(*args):return [from_options('model','Image',{})],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='App continuation test')
    runtime.agents.ensure_definition(agent_key='test.form',package_version='1',display_name='Form',executor_key='test.form',max_steps=12,timeout_seconds=120)
    refs=[]
    for index,color in enumerate(['red','blue']):
        path=runtime.config.paths.base_path/f'ref-{index}.png';Image.new('RGB',(16,16),color).save(path)
        refs.append(runtime.workspace.import_artifact(thread.session.id,path,name=path.name,media_type='image/png').id)
    values={'person_artifact_ids':refs,'background':'bamboo','prompt':'keep both subjects','model':'model'}
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'app-form','capability':'image.group_photo','values':values})
    # Create the actual form in a session with its own owned references.
    def execute(context):
        action=form_action(context,test_parameter_forms.ARGS)
        if action:return action
        item=context.interaction('form:app-form')
        if not context.step('resolved'):
            return ToolCallAction('resolved',item.response['result']['capability'],values,resolved_interaction_id=item.id)
        return CompleteAction(context.step('resolved').output)
    runtime.agent_runtime.bind_executor('test.form',execute)
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='test.form',input={})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            state=(await c.get(url)).json();assert state['can_continue_in_app']
            provider=runtime.app_capability_router.providers[state['descriptor']['provider']]
            assert state['descriptor']['display_name']==provider.display_name
            assert state['descriptor']['summary']==provider.summary
            for choice in state['alternatives']:
                declared=runtime.app_capability_router.providers[choice['provider']]
                assert choice['display_name']==declared.display_name
                assert choice['description']==declared.summary
            assert {x['capability'] for x in state['alternatives']}=={'image.group_photo','image.reference_creation'}
            assert (await c.post(url+'/switch',json={'revision':0,'provider':'voice.transcribe'})).status_code==422
            switched=await c.post(url+'/switch',json={'revision':0,'provider':'ai2apps.imagine.reference-creation'});assert switched.status_code==200,switched.text
            assert switched.json()['values']['artifact_ids']==refs
            assert switched.json()['values']['prompt']=='keep both subjects'
            assert (await c.post(url+'/switch',json={'revision':0,'provider':'ai2apps.imagine.group-photo'})).status_code==409
            restored=await c.post(url+'/switch',json={'revision':1,'provider':'ai2apps.imagine.group-photo'});assert restored.status_code==200,restored.text
            assert restored.json()['values']==values
            target='ai2apps.imagine.group-photo'
            selected_values=values
            revision=2
            if choose_related:
                changed=await c.post(url+'/switch',json={'revision':revision,'provider':'ai2apps.imagine.reference-creation'})
                assert changed.status_code==200,changed.text
                selected_values=changed.json()['values'];revision=3;target='ai2apps.imagine.reference-creation'
            body={'revision':revision,'values':selected_values}
            handoff=await c.post(url+'/handoff',json=body);assert handoff.status_code==200,handoff.text
            assert handoff.json()['parameters']['references'][0]['artifact_id']==refs[0]
            assert (await c.get(url)).json()['waiting_app']
            reopened=FastAPI();reopened.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=reopened),base_url='http://test') as other:
                persisted=(await other.get(url)).json();assert persisted['waiting_app'] and persisted['values']==selected_values
            assert (await c.post(url+'/submit',json=body)).status_code==409
            assert (await c.post(url+'/handoff/complete')).status_code==409
            shell=(await c.get(url.replace('/parameters','/handoff'))).json();assert shell['target']['mini_app_id']==target
            instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=RequestPrincipal.legacy_local())
            scope=dict(actor_id='local',installation_id='local',app_instance_id=instance.id,studio_id='ai2apps.imagine-studio')
            repo=StudioRepository(runtime.database)
            wrong=repo.create_run(**scope,mini_app_id='ai2apps.imagine.image-edit',mini_app_version='1',placement='main',title='wrong',input_data={'parameterHandoffInteractionId':item.id})
            assert (await c.post(url+'/handoff/link',json={'studio_run_id':wrong['id'],'app_instance_id':instance.id})).status_code==404
            job=repo.create_run(**scope,mini_app_id=target,mini_app_version='1',placement='main',title='correct',input_data={'parameterHandoffInteractionId':item.id,'modelId':'model'})
            assert (await c.post(url+'/handoff/link',json={'studio_run_id':job['id'],'app_instance_id':instance.id})).status_code==200
            assert (await c.post(url+'/handoff/complete')).status_code==409
            repo.create_artifact(job['id'],**scope,kind='image',name='output.png',media_type='image/png',preview_url='/preview',download_url='/download',source_id='test-output',metadata={'workspaceSessionId':thread.session.id,'workspaceArtifactId':refs[0]})
            repo.update_run(job['id'],**scope,status='succeeded',progress=100)
            response=await c.post(url+'/handoff/complete');assert response.status_code==200,response.text
            result=response.json()['result'];assert result['executed_in_app'] and result['mini_app_id']==target
            assert runtime.workspace.get_artifact(thread.session.id,result['artifact']['id']).media_type=='image/png'
            assert (await c.post(url+'/handoff/complete')).json()==response.json()
            completed=await wait(runtime,run.id,'completed');assert completed.output['studio_run_id']==job['id']
    finally:await runtime.stop_background_tasks()


def _client_app(runtime):
    app=FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    return app


def _form_executor(request_id,values):
    def execute(context):
        action=form_action(context,{'request_id':request_id,'capability':'image.group_photo','values':values})
        if action:return action
        item=context.interaction('form:'+request_id)
        if (item.response or {}).get('status')!='completed':return CompleteAction({'cancelled':True})
        if not context.step('resolved'):
            return ToolCallAction('resolved',item.response['result']['capability'],values,resolved_interaction_id=item.id)
        return CompleteAction(context.step('resolved').output)
    return execute


async def _waiting_form(runtime,monkeypatch,request_id='app-form'):
    from ai2apps.images.parameters import from_options
    async def models(*args):return [from_options('model','Image',{})],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='App continuation guards')
    runtime.agents.ensure_definition(agent_key='test.form',package_version='1',display_name='Form',executor_key='test.form',max_steps=12,timeout_seconds=120)
    refs=[]
    for index,color in enumerate(['red','blue']):
        path=runtime.config.paths.base_path/f'ref-{index}.png';Image.new('RGB',(16,16),color).save(path)
        refs.append(runtime.workspace.import_artifact(thread.session.id,path,name=path.name,media_type='image/png').id)
    values={'person_artifact_ids':refs,'background':'bamboo','prompt':'keep both subjects','model':'model'}
    runtime.agent_runtime.bind_executor('test.form',_form_executor(request_id,values))
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='test.form',input={})
    await runtime.start_background_tasks(retention_interval_seconds=60)
    await wait(runtime,run.id,'waiting_input')
    return thread,run,runtime.agents.list_interactions(run.id)[0],values


def _studio_scope(instance):
    return dict(actor_id='local',installation_id='local',app_instance_id=instance.id,studio_id='ai2apps.imagine-studio')


def _succeed(repo,scope,job,thread,source_id,source_artifact):
    repo.create_artifact(job['id'],**scope,kind='image',name='output.png',media_type='image/png',preview_url='/preview',download_url='/download',
        source_id=source_id,metadata={'workspaceSessionId':thread.session.id,'workspaceArtifactId':source_artifact})
    repo.update_run(job['id'],**scope,status='succeeded',progress=100)


def _artifacts(runtime,session_id):
    return {artifact.id for artifact in runtime.workspace.list_artifacts(session_id)}


@pytest.mark.asyncio
async def test_app_continuation_rejects_unbound_predating_and_running_tasks(runtime,monkeypatch):
    thread,run,item,values=await _waiting_form(runtime,monkeypatch)
    url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
    instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=RequestPrincipal.legacy_local())
    scope=_studio_scope(instance)
    repo=StudioRepository(runtime.database)
    # Created before the handoff, so it must never settle this continuation.
    predating=repo.create_run(**scope,mini_app_id='ai2apps.imagine.group-photo',mini_app_version='1',placement='main',title='predating',
        input_data={'parameterHandoffInteractionId':item.id})
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_client_app(runtime)),base_url='http://test') as c:
            assert (await c.post(url+'/handoff',json={'revision':0,'values':values})).status_code==200
            unbound=repo.create_run(**scope,mini_app_id='ai2apps.imagine.group-photo',mini_app_version='1',placement='main',title='unbound',input_data={})
            rejected=await c.post(url+'/handoff/link',json={'studio_run_id':unbound['id'],'app_instance_id':instance.id})
            assert rejected.status_code==409 and 'not linked' in rejected.json()['detail']
            rejected=await c.post(url+'/handoff/link',json={'studio_run_id':predating['id'],'app_instance_id':instance.id})
            assert rejected.status_code==409 and 'predates' in rejected.json()['detail']
            job=repo.create_run(**scope,mini_app_id='ai2apps.imagine.group-photo',mini_app_version='1',placement='main',title='correct',
                input_data={'parameterHandoffInteractionId':item.id,'modelId':'model'})
            assert (await c.post(url+'/handoff/link',json={'studio_run_id':job['id'],'app_instance_id':'another-instance'})).status_code==404
            linked=await c.post(url+'/handoff/link',json={'studio_run_id':job['id'],'app_instance_id':instance.id})
            assert linked.status_code==200,linked.text
            replacement=repo.create_run(**scope,mini_app_id='ai2apps.imagine.group-photo',mini_app_version='1',placement='main',title='replacement',
                input_data={'parameterHandoffInteractionId':item.id,'modelId':'model'})
            rejected=await c.post(url+'/handoff/link',json={'studio_run_id':replacement['id'],'app_instance_id':instance.id})
            assert rejected.status_code==409 and 'still running' in rejected.json()['detail']
            assert (await c.post(url+'/handoff/complete')).status_code==409
            _succeed(repo,scope,job,thread,'guard-output',values['person_artifact_ids'][0])
            # Two views may press retrieve at once; the saved response must be reused, not recomputed.
            from dataclasses import replace
            from ai2apps.agents.form_continuation import ADAPTERS
            from ai2apps.images.app_continuation import KEY
            adapter=ADAPTERS[KEY];imports=[]
            def complete_once(*args):
                imports.append(True)
                return adapter.complete(*args)
            monkeypatch.setitem(ADAPTERS,KEY,replace(adapter,complete=complete_once))
            first,second=await asyncio.gather(c.post(url+'/handoff/complete'),c.post(url+'/handoff/complete'))
            assert [first.status_code,second.status_code]==[200,200]
            assert first.json()==second.json()
            assert imports==[True]
            assert first.json()['result']['studio_run_id']==job['id']
            completed=await wait(runtime,run.id,'completed')
            assert completed.output['studio_run_id']==job['id']
            assert _artifacts(runtime,thread.session.id)==set(values['person_artifact_ids'])|{first.json()['result']['artifact']['id']}
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_cancelled_app_continuation_does_not_import_a_late_app_result(runtime,monkeypatch):
    thread,run,item,values=await _waiting_form(runtime,monkeypatch)
    url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
    instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=RequestPrincipal.legacy_local())
    scope=_studio_scope(instance)
    repo=StudioRepository(runtime.database)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_client_app(runtime)),base_url='http://test') as c:
            assert (await c.post(url+'/handoff',json={'revision':0,'values':values})).status_code==200
            job=repo.create_run(**scope,mini_app_id='ai2apps.imagine.group-photo',mini_app_version='1',placement='main',title='late',
                input_data={'parameterHandoffInteractionId':item.id,'modelId':'model'})
            assert (await c.post(url+'/handoff/link',json={'studio_run_id':job['id'],'app_instance_id':instance.id})).status_code==200
            _succeed(repo,scope,job,thread,'late-output',values['person_artifact_ids'][0])
            cancelled=await c.post(url.replace('/parameters','/respond'),
                json={'response_id':'form-cancel:'+item.id,'response':{'status':'cancelled','result':{}}})
            assert cancelled.status_code==200,cancelled.text
            completed=await wait(runtime,run.id,'completed')
            assert completed.output=={'cancelled':True}
            assert _artifacts(runtime,thread.session.id)==set(values['person_artifact_ids'])
            # The App finished after the user cancelled: report the stored cancellation, never import its output.
            late=await c.post(url+'/handoff/complete')
            assert late.status_code==200,late.text
            assert late.json()=={'status':'cancelled','result':{}}
            assert _artifacts(runtime,thread.session.id)==set(values['person_artifact_ids'])
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['before_link','linked','succeeded','submitted'])
async def test_app_continuation_survives_runtime_restart(tmp_path,monkeypatch,phase):
    first=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));first.start()
    try:
        thread,run,item,values=await _waiting_form(first,monkeypatch)
        instance,_,_=first.extension_manager.launch_app('ai2apps.imagine-studio',principal=RequestPrincipal.legacy_local())
        scope=_studio_scope(instance)
        repo=StudioRepository(first.database)
        url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_client_app(first)),base_url='http://test') as c:
            assert (await c.post(url+'/handoff',json={'revision':0,'values':values})).status_code==200
            job=repo.create_run(**scope,mini_app_id='ai2apps.imagine.group-photo',mini_app_version='1',placement='main',title='restart',
                input_data={'parameterHandoffInteractionId':item.id,'modelId':'model'})
            if phase!='before_link':
                assert (await c.post(url+'/handoff/link',json={'studio_run_id':job['id'],'app_instance_id':instance.id})).status_code==200
            if phase in {'succeeded','submitted'}:
                _succeed(repo,scope,job,thread,'restart-output',values['person_artifact_ids'][0])
            saved=None
            if phase=='submitted':
                saved=(await c.post(url+'/handoff/complete')).json()
                await wait(first,run.id,'completed')
    finally:
        await first.stop_background_tasks()
        first.stop()
    second=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));second.start()
    try:
        # A real Local registers executors at startup; only this test agent needs rebinding.
        second.agent_runtime.bind_executor('test.form',_form_executor('app-form',values))
        await second.start_background_tasks(retention_interval_seconds=60)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_client_app(second)),base_url='http://test') as c:
            if phase!='submitted':
                persisted=(await c.get(url)).json()
                assert persisted['waiting_app'] and persisted['values']==values
                if phase=='before_link':
                    assert (await c.post(url+'/handoff/link',json={'studio_run_id':job['id'],'app_instance_id':instance.id})).status_code==200
                if phase in {'before_link','linked'}:
                    _succeed(StudioRepository(second.database),scope,job,thread,'restart-output',values['person_artifact_ids'][0])
            response=await c.post(url+'/handoff/complete')
            assert response.status_code==200,response.text
            assert response.json()['result']['studio_run_id']==job['id']
            if saved:assert response.json()==saved
            assert _artifacts(second,thread.session.id)==set(values['person_artifact_ids'])|{response.json()['result']['artifact']['id']}
            completed=await wait(second,run.id,'completed')
            assert completed.output['studio_run_id']==job['id']
    finally:
        await second.stop_background_tasks()
        second.stop()


def test_owned_run_checks_every_identity_dimension_and_missing_task(runtime):
    from dataclasses import replace
    from types import SimpleNamespace
    from fastapi import HTTPException
    from ai2apps.agents.parameter_forms import FORMS
    from ai2apps.images.app_continuation import owned_run
    principal=RequestPrincipal.legacy_local()
    instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=principal)
    form=FORMS['ai2apps.imagine.group-photo']
    repo=StudioRepository(runtime.database)
    job=repo.create_run(**_studio_scope(instance),mini_app_id=form.mini_app_id,mini_app_version='1',placement='main',title='scope',input_data={})
    record={'created_at':'2000-01-01T00:00:00+00:00'}
    assert owned_run(runtime,principal,form,record,job['id'],instance.id)['id']==job['id']
    cases=[
        (SimpleNamespace(actor_user_id='other',installation_id='local'),form,job['id'],instance.id),
        (SimpleNamespace(actor_user_id='local',installation_id='other'),form,job['id'],instance.id),
        (principal,form,job['id'],'other-instance'),
        (principal,replace(form,app_id='other-studio'),job['id'],instance.id),
        (principal,replace(form,mini_app_id='other-mini'),job['id'],instance.id),
        (principal,form,'missing-task',instance.id),
    ]
    for actor,target,identifier,app_instance in cases:
        with pytest.raises(HTTPException) as error:
            owned_run(runtime,actor,target,record,identifier,app_instance)
        assert error.value.status_code==404


@pytest.mark.asyncio
async def test_link_guards_all_active_states_and_serializes_competing_tasks(runtime,monkeypatch):
    thread,run,item,values=await _waiting_form(runtime,monkeypatch)
    url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
    instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=RequestPrincipal.legacy_local())
    scope=_studio_scope(instance);repo=StudioRepository(runtime.database)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_client_app(runtime)),base_url='http://test') as c:
            assert (await c.post(url+'/handoff',json={'revision':0,'values':values})).status_code==200
            def job():
                return repo.create_run(**scope,mini_app_id='ai2apps.imagine.group-photo',mini_app_version='1',placement='main',title='race',input_data={'parameterHandoffInteractionId':item.id})
            first,second=job(),job()
            def body(value):return {'studio_run_id':value['id'],'app_instance_id':instance.id}
            a,b=await asyncio.gather(c.post(url+'/handoff/link',json=body(first)),c.post(url+'/handoff/link',json=body(second)))
            assert sorted([a.status_code,b.status_code])==[200,409]
            winner,loser=(first,second) if a.status_code==200 else (second,first)
            assert (await c.post(url+'/handoff/link',json=body(winner))).status_code==200
            for status in ('draft','queued','running','waiting_input'):
                with runtime.database.transaction() as db:db.execute('UPDATE studio_runs SET status=? WHERE id=?',(status,winner['id']))
                rejected=await c.post(url+'/handoff/link',json=body(loser))
                assert rejected.status_code==409,(status,rejected.text)
            for status in ('succeeded','failed','cancelled','expired'):
                with runtime.database.transaction() as db:db.execute('UPDATE studio_runs SET status=? WHERE id=?',(status,winner['id']))
                assert (await c.post(url+'/handoff/link',json=body(loser))).status_code==200
                winner,loser=loser,winner
            winner=job()
            assert (await c.post(url+'/handoff/link',json=body(winner))).status_code==200
            _succeed(repo,scope,winner,thread,'race-output',values['person_artifact_ids'][0])
            # Either request can acquire the interaction lock first. A terminal
            # binding may be replaced before retrieval, but never after settlement.
            completed,relinked=await asyncio.gather(c.post(url+'/handoff/complete'),c.post(url+'/handoff/link',json=body(loser)))
            assert (completed.status_code,relinked.status_code) in ((200,409),(409,200)),(completed.text,relinked.text)
            if relinked.status_code==200:
                assert 'not successful yet: expired' in completed.text
                assert _artifacts(runtime,thread.session.id)==set(values['person_artifact_ids'])
                assert (await c.post(url+'/handoff/link',json=body(winner))).status_code==200
                completed=await c.post(url+'/handoff/complete')
            assert completed.status_code==200,completed.text
            assert (await c.post(url+'/handoff/link',json=body(loser))).status_code==409
            assert completed.json()['result']['studio_run_id']==winner['id']
            assert _artifacts(runtime,thread.session.id)==set(values['person_artifact_ids'])|{completed.json()['result']['artifact']['id']}
    finally:await runtime.stop_background_tasks()
