"""Durable runtime budget renewals preserve completed steps across restart."""
import pytest
from test_app_interactions import runtime,wait
from ai2apps.chat import ChatRepository
from ai2apps.agents import ModelCallAction,CompleteAction
from ai2apps.agents.token_budget import CONTINUE,STOP,step_allowance,token_allowance
from ai2apps.agents.models import AgentExecutionContext

@pytest.mark.asyncio
@pytest.mark.parametrize('budget_kind',['steps','tokens'])
@pytest.mark.parametrize('continue_run',[True,False])
async def test_runtime_budget_wait_restart_continue_or_stop(runtime,budget_kind,continue_run):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Budget round')
    key='fixture.budget.'+budget_kind
    runtime.agents.ensure_definition(agent_key=key,package_version='1',display_name='Budget fixture',executor_key=key,
        max_steps=2 if budget_kind=='steps' else 10,timeout_seconds=60,
        manifest={'max_total_model_tokens':15 if budget_kind=='tokens' else 1000})
    def execute(c):
        if len(c.steps)>=3:return CompleteAction({'result':'all three results retained'})
        return ModelCallAction('model-'+str(len(c.steps)),{'model':'fixture','messages':[]})
    calls=[]
    async def provider(request):
        calls.append(request)
        return {'choices':[{'message':{'role':'assistant','content':'saved result'},'finish_reason':'stop'}],'usage':{'total_tokens':10}}
    runtime.agent_runtime.bind_executor(key,execute);runtime.agent_runtime.bind_model_provider(provider)
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key=key,input={})
    await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'waiting_input')
        assert len(calls)==2
        item=runtime.agents.list_interactions(run.id)[0]
        assert item.request_key.startswith('step-budget:' if budget_kind=='steps' else 'token-budget:')
        await runtime.agent_runtime.stop();await runtime.agent_runtime.start()
        assert len(calls)==2
        runtime.agents.respond_interaction(run.id,item.id,response={'answer':CONTINUE if continue_run else STOP},response_id='explicit-choice')
        runtime.agent_runtime.wake()
        final=await wait(runtime,run.id,'completed')
        assert len(calls)==(3 if continue_run else 2)
        assert len(runtime.agents.list_steps(run.id))==len(calls)
        if continue_run:
            definition,run,_,steps,interactions=runtime.agents.snapshot(run.id)
            ctx=AgentExecutionContext(definition,run,steps,interactions)
            assert step_allowance(ctx)[1]==(4 if budget_kind=='steps' else 12)
            assert token_allowance(ctx)[1]==(1020 if budget_kind=='steps' else 35)
            assert final.output['result']=='all three results retained'
        else:assert final.output['budget_stopped']
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
@pytest.mark.parametrize('owner',['fixture.alpha','another.beta'])
async def test_nested_browser_budget_is_visible_and_resumes_exact_interaction(runtime,owner):
    import httpx
    from fastapi import FastAPI
    from ai2apps.identity import RequestPrincipal
    from ai2apps.agents import InteractionKind
    from ai2apps.browser.tasks import BrowserTaskRepository
    from ai2apps.browser.aaat_controls import create_router
    chat=ChatRepository(runtime.database,runtime.events)
    thread,_=chat.create_thread(title='Budget origin');private,_=chat.create_thread(title='Budget executor')
    origin,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    child,_=runtime.agents.create_run(session_id=private.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    item=runtime.agents.create_interaction(child.id,request_key='step-budget:2',kind=InteractionKind.MENU,prompt='Continue budget?',
        response_schema={'type':'object','properties':{'answer':{'enum':[CONTINUE,STOP]}},'required':['answer'],'additionalProperties':False},request={'control':'agent_budget','used_steps':2,'used_tokens':20})
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    task=tasks.enqueue('local','default','',owner,'','Fixture',{},session_id=private.session.id)
    tasks.update('local',task['id'],run_id=child.id,status='waiting_input')
    tool=runtime.services.get_tool('gallery.search')
    invocation=runtime.services.create_invocation(tool=tool,provider_key=owner,caller_id='test',session_id=thread.session.id,trace_id=origin.id,arguments={},timeout_ms=30000)
    runtime.services.update_invocation_progress(invocation.id,{'content':{'browser_task_id':task['id']}})
    app=FastAPI();app.include_router(create_router(lambda:runtime,RequestPrincipal.legacy_local))
    url=f'/agent-runs/{origin.id}/browser-tasks/{task["id"]}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        data=(await client.get(url)).json();assert data['requires_user'] and data['interactions'][0]['control']=='agent_budget'
        response=await client.post(url,json={'action':'continue','interaction_id':item.id,'response_id':'budget-choice'})
        assert response.status_code==200
        assert runtime.agents.list_interactions(child.id)[0].response=={'answer':CONTINUE}
        assert (await client.post(url,json={'action':'continue','interaction_id':item.id,'response_id':'budget-choice'})).status_code==200
