"""Imagine owns reference-prefill semantics; the AS uses its normal contract gate."""
import json
import httpx
import pytest
from fastapi import FastAPI
from PIL import Image
from ai2apps.agents.aaat_context import PREFIX
from ai2apps.api.router import create_ai2apps_router
from ai2apps.core import MessageRole
from ai2apps.identity import IdentityRepository
from ai2apps.storage import MessagePartInput
from ai2apps.storage.repositories import MessageRepository
from test_app_interactions import runtime,wait
from test_aaat_execution_flow import new_run,response


def test_all_image_providers_publish_owner_reference_semantics(runtime):
    from ai2apps.agents.parameter_forms import FORMS
    for provider in runtime.app_capability_router.providers.values():
        if provider.app_id not in {'ai2apps.images','ai2apps.imagine-studio'}:continue
        assert provider.agent_context['schema']=='ai2apps.aaat-declaration/v1'
        assert provider.agent_context==FORMS[provider.id].agent_context
        assert provider.agent_context['result_semantics']['artifact']


@pytest.mark.asyncio
async def test_prior_generated_source_is_prefilled_while_missing_user_photo_remains_required(runtime,monkeypatch):
    from ai2apps.images.parameters import from_options
    async def models(*args):return [from_options('fixture-image','Fixture',{})],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    run=new_run(runtime,['app.collect_parameters'],prompt='Make a group picture of me with the panda just generated.')
    path=runtime.config.paths.base_path/'panda.png';Image.new('RGB',(16,16),'white').save(path)
    source=runtime.workspace.import_artifact(run.session_id,path,name='panda.png',media_type='image/png')
    MessageRepository(runtime.database,runtime.events).append(session_id=run.session_id,role=MessageRole.ASSISTANT,
        parts=(MessagePartInput(kind='openai_content',content={'content':[
            {'type':'text','text':'Generated panda eating bamboo.'},
            {'type':'image_url','image_url':{'url':f'/v1/platform/sessions/{run.session_id}/artifacts/{source.id}/download','artifact_id':source.id}}]}),))
    requests=[]
    async def model(request):
        requests.append(request)
        assert source.id in json.dumps(request['messages'])
        values={'model':'fixture-image','size':'1024x1024','background':'bamboo forest'}
        if len(requests)==1:
            assert not any(m.get('role')=='system' and str(m.get('content','')).startswith(PREFIX) for m in request['messages'])
        else:
            assert len(requests)==2
            contexts=[item for m in request['messages'] if m.get('role')=='system' and str(m.get('content','')).startswith(PREFIX)
                for item in json.loads(m['content'][len(PREFIX):])]
            assert contexts[0]['declaration']==runtime.app_capability_router.providers['ai2apps.imagine.group-photo'].agent_context
            assert not runtime.agents.list_interactions(run.id)
            values['person_artifact_ids']=[source.id]
        return response('app.collect_parameters',{'request_id':'reuse-reference','capability':'image.group_photo','values':values})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0]
        principal=lambda:IdentityRepository(runtime.database).local_principal_for('flow-owner')
        app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=principal))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
            state=(await client.get(url)).json()
            assert state['values']['person_artifact_ids']==[source.id]
            field=next(f for f in state['descriptor']['fields'] if f['key']=='person_artifact_ids')
            assert field['type']=='asset' and field['multiple'] and field['minItems']==2
            assert any(e['field']=='person_artifact_ids' for e in state['invalid'])
            assert (await client.post(url+'/submit',json={'revision':0,'values':state['values']})).status_code==422
            removed={**state['values'],'person_artifact_ids':[]}
            assert (await client.put(url,json={'revision':0,'values':removed})).status_code==200
            assert (await client.get(url)).json()['values']['person_artifact_ids']==[]
        with runtime.database.transaction() as db:assert db.execute('select count(*) from studio_background_jobs').fetchone()[0]==0
        assert len(requests)==2
    finally:await runtime.stop_background_tasks()
