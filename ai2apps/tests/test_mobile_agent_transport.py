import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from ai2apps.web.mobile_agent_transport import create_mobile_agent_router, allowed_control
from ai2apps.web.owner_home_gateway import public_allowed


def test_transport_default_closed_before_forward_even_with_spoofed_app_headers():
    calls=[]
    async def forward(**kwargs):
        calls.append(kwargs)
        return Response(200,json={})
    app=FastAPI();app.include_router(create_mobile_agent_router(principal_provider=lambda:'verified-user',forward=forward))
    with TestClient(app) as client:
        for method,path in [('GET','/v1/mobile/chat/threads/s/agent-runs'),('POST','/v1/mobile/agent-runs/r/cancel'),('PUT','/v1/mobile/agent-runs/r/interactions/i/parameters')]:
            assert client.request(method,path,headers={'X-Is-App':'true','User-Agent':'AI2Apps-iOS'}).status_code==403
    assert calls==[]


def test_fixture_grant_preserves_actor_revision_body_idempotency_and_exact_route():
    actor=object();calls=[]
    async def forward(**kwargs):
        calls.append(kwargs)
        return Response(200,json={'revision':4})
    app=FastAPI();app.include_router(create_mobile_agent_router(principal_provider=lambda:actor,forward=forward,enabled=lambda r,p:p is actor))
    with TestClient(app) as client:
        payload={'revision':3,'values':{'field':'edited'}}
        response=client.put('/v1/mobile/agent-runs/r/interactions/i/parameters',json=payload,headers={'Authorization':'forged','Idempotency-Key':'same-action'})
        assert response.json()=={'revision':4}
        assert calls[0]['principal'] is actor
        assert calls[0]['path']=='/agent-runs/r/interactions/i/parameters'
        import json
        assert json.loads(calls[0]['body'])==payload
        assert calls[0]['headers']=={'content-type':'application/json','idempotency-key':'same-action'}
        for path in ['retry','resume','interactions/i/parameters/handoff/link','interactions/i/parameters/../../secrets','interactions/i/parameters/anything']:
            assert client.post('/v1/mobile/agent-runs/r/'+path).status_code==404
        assert len(calls)==1


@pytest.mark.parametrize('method,path', [('POST','/v1/mobile/agent-runs/r/cancel'),('POST','/v1/mobile/agent-runs/r/interactions/i/respond'),('GET','/v1/mobile/chat/threads/s/agent-runs'),('PUT','/v1/mobile/agent-runs/r/interactions/i/parameters')])
def test_existing_owner_public_boundary_stays_closed(method,path):
    assert not public_allowed(method,path)


def test_control_surface_is_methods_and_paths_not_arbitrary_proxy():
    assert allowed_control('POST','interactions/i/parameters/submit')
    assert allowed_control('GET','interactions/i/parameters/materials')
    assert not allowed_control('GET','cancel')
    assert not allowed_control('POST','interactions/i/handoff')
    assert not allowed_control('PUT','interactions/i/parameters/submit')

from test_aaat_declaration_context import runtime

@pytest.mark.asyncio
async def test_session_history_is_owner_scoped_and_never_executes(runtime):
    from test_aaat_execution_flow import new_run
    from ai2apps.identity import IdentityRepository
    from ai2apps.api import create_ai2apps_router
    from ai2apps.chat import ChatRepository
    import httpx
    run=new_run(runtime,[],prompt='history only')
    # An internal executor may itself be a root Run. Its trusted declaration,
    # not its name or executor prefix, determines conversation visibility.
    hidden=[]
    for key in ('fixture.private-executor','arbitrary.hidden-worker'):
        runtime.agents.ensure_definition(agent_key=key,package_version='1',
            display_name='Implementation worker',description='Internal fixture',
            executor_key='fixture:worker',manifest={'discoverable':False})
        hidden.append(runtime.agents.create_run(session_id=run.session_id,agent_key=key,input={})[0])
    runtime.agents.ensure_definition(agent_key='fixture.visible-specialist',package_version='1',
        display_name='Browser Builder Runtime',description='User-facing fixture',
        executor_key='fixture:worker',manifest={'discoverable':True})
    visible=runtime.agents.create_run(session_id=run.session_id,agent_key='fixture.visible-specialist',input={})[0]
    actor=IdentityRepository(runtime.database).local_principal_for('flow-owner')
    other,_=ChatRepository(runtime.database,runtime.events,principal=actor).create_thread(title='other')
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:actor))
    before=runtime.agents.list_runs()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        result=await client.get(f'/v1/platform/sessions/{run.session_id}/agent-runs')
        assert result.status_code==200,result.text
        assert {item['id'] for item in result.json()['items']}=={run.id,visible.id}
        # Internal execution records remain available for owned status/diagnosis.
        for item in hidden:
            detail=await client.get(f'/v1/platform/agent-runs/{item.id}')
            assert detail.status_code==200
        assert (await client.get(f'/v1/platform/sessions/{other.session.id}/agent-runs')).json()['items']==[]
        assert (await client.get('/v1/platform/sessions/unknown/agent-runs')).status_code==404
    assert runtime.agents.list_runs()==before

@pytest.mark.asyncio
@pytest.mark.parametrize('cancel', [False,True])
async def test_mobile_fixture_real_parameter_guards_restart_and_result_persistence(runtime,cancel):
    """Real General/SQLite/Platform behind an isolated, actor-bound Mobile adapter."""
    import httpx,json,asyncio
    from test_aaat_execution_flow import new_run,register,response
    from test_aaat_declaration_context import wait
    from ai2apps.api import create_ai2apps_router
    from ai2apps.identity import IdentityRepository
    calls=[]
    async def descriptor(principal,model=None):
        return {'selection_required':True,'effective_schema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}
    async def execute(args,context):
        calls.append(args)
        await context.report_progress('Reading fixture evidence',progress=.5)
        return {'value':args['query'],'aaat_view':{'schema':'ai2apps.aaat-view/v1','id':'evidence','layout':'cards','title':'Fixture evidence', 'items':[{'id':'one','title':'Read result','url':'https://example.org/original'}]}}
    register(runtime,'test.mobile_fixture',execute,describe=descriptor)
    async def model(request):
        if calls:return response(text='Read result, original evidence retained.')
        return response('test.mobile_fixture',{'query':'draft'})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['test.mobile_fixture']);runtime.agent_runtime.wake()
        await wait(runtime,run.id,'waiting_input')
        actor=IdentityRepository(runtime.database).local_principal_for('flow-owner')
        platform=FastAPI();platform.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:actor))
        async def forward(*,principal,method,path,query,body,headers):
            assert principal is actor
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=platform),base_url='http://platform') as client:
                return await client.request(method,'/v1/platform'+path+('?' + query if query else ''),content=body,headers=headers)
        mobile=FastAPI();mobile.include_router(create_mobile_agent_router(principal_provider=lambda:actor,forward=forward,enabled=lambda req,p:p is actor))
        item=runtime.agents.list_interactions(run.id)[0]
        path=f'/v1/mobile/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mobile),base_url='http://mobile') as client:
            draft=(await client.get(path)).json()
            saved=await client.put(path,json={'revision':draft['revision'],'values':{'query':'mobile edit'}})
            assert saved.status_code==200,saved.text
            await runtime.agent_runtime.stop();await runtime.agent_runtime.start()
            restored=(await client.get(path)).json();assert restored['values']['query']=='mobile edit'
            assert not calls
            if cancel:
                result=await client.post(f'/v1/mobile/agent-runs/{run.id}/cancel')
                assert result.status_code==200,result.text
                assert (await client.post(path+'/submit',json={'revision':restored['revision'],'values':restored['values']})).status_code==409
                assert not calls
            else:
                payload={'revision':restored['revision'],'values':restored['values']}
                result=await client.post(path+'/submit',json=payload);assert result.status_code==200,result.text
                assert (await client.post(path+'/submit',json=payload)).json()==result.json()
                done=await wait(runtime,run.id,'completed')
                assert calls==[{'query':'mobile edit'}]
                assert done.output['aaat_views'][0]['view']['items'][0]['url']=='https://example.org/original'
                history=(await client.get(f'/v1/mobile/chat/threads/{run.session_id}/agent-runs')).json()
                assert history['items'][0]['id']==run.id
                with runtime.database.transaction() as db:
                    metadata=json.loads(db.execute('SELECT metadata_json FROM messages WHERE id=?',(done.output['message_id'],)).fetchone()['metadata_json'])
                assert metadata['aaat_views']==done.output['aaat_views']
                assert len(calls)==1
    finally:
        await runtime.stop_background_tasks()
