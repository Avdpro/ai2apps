"""Live regression shapes: generic receipt rejection, scoped assistance, owner progress."""
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.agents import InteractionKind, RunStepStatus
from ai2apps.agents.parameter_forms import claim_form_invocation
from ai2apps.browser.shopping import history_progress_view
from ai2apps.browser.aaat_controls import require_task
from legacy_package_backend_fixture import runtime

@pytest.mark.parametrize('name',['arbitrary.alpha','different.beta'])
@pytest.mark.parametrize('phase',['prepare','execute'])
def test_parameter_rejection_only_releases_unexecuted_confirmation(runtime,name,phase):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Receipt regression')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    item=runtime.agents.create_interaction(run.id,request_key='form',kind=InteractionKind.FORM,prompt='Review',response_schema={'type':'object'})
    assert claim_form_invocation(runtime.database,item.id,'first')
    step,_=runtime.agents.create_step(run.id,action_key='first',kind='tool',tool_name=name,input={})
    runtime.agents.settle_step(step.id,status=RunStepStatus.FAILED,error={'code':'invalid_tool_arguments','phase':phase})
    assert claim_form_invocation(runtime.database,item.id,'corrected') is (phase=='prepare')


def test_progress_describes_actual_page_order_counts():
    v=history_progress_view({'id':'task','status':'running','progress':{'phase':'order_details','page':2,'current':3,'total':7}})
    assert '2' in v['text'] and '3 / 7' in v['text']
    assert v['content']['task_progress']['metrics'][0]['value']==3


def test_task_id_alone_cannot_authorize_private_session_controls(runtime):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Task scope')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    with pytest.raises(HTTPException) as error:require_task(runtime,RequestPrincipal.legacy_local(),run.id,'model-supplied-id')
    assert error.value.status_code==404

@pytest.mark.asyncio
async def test_waiting_overrides_stale_progress_text():
    import time
    from ai2apps.research.mini_apps import wait_task
    task={'id':'task','status':'waiting_input','requires_user':True,'message':'Quantity control needs assistance',
        'progress_snapshot':{'text':'Preparing','content':{'task_progress':{'metrics':[{'label':'Products','value':0,'total':2}]}}}}
    class Notifications:
        def subscribe(self):return self
        async def __aenter__(self):return self
        async def __aexit__(self,*a):return False
        async def get(self):task.update(status='completed',requires_user=False)
    updates=[]
    async def report(text,**kw):updates.append((text,kw))
    await wait_task(NS(notifications=Notifications()),NS(task_declared=lambda *a:dict(task)),NS(declaration={'id':'arbitrary.mini'}),
        NS(actor_user_id='owner'),dict(task),NS(report_progress=report),time.monotonic()+2)
    assert updates[0][0]=='Quantity control needs assistance'
    assert updates[0][1]['content']['task_progress']['requires_user']
    assert updates[0][1]['content']['task_progress']['metrics'][0]['total']==2

@pytest.mark.asyncio
@pytest.mark.parametrize('mini',['fixture.one','unrelated.two'])
async def test_private_browser_task_assistance_requires_observed_invocation_and_exact_interaction(runtime,mini):
    import httpx
    from fastapi import FastAPI
    from ai2apps.browser.tasks import BrowserTaskRepository
    from ai2apps.browser.aaat_controls import create_router
    principal=RequestPrincipal.legacy_local()
    chat=ChatRepository(runtime.database,runtime.events)
    thread,_=chat.create_thread(title='Origin')
    private,_=chat.create_thread(title='Private executor')
    origin,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    child,_=runtime.agents.create_run(session_id=private.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    interaction=runtime.agents.create_interaction(child.id,request_key='help',kind=InteractionKind.FORM,prompt='Inspect quantity',
        response_schema={'type':'object','properties':{'continued':{'const':True}},'required':['continued'],'additionalProperties':False},
        request={'control':'browser_user_assistance'})
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    task=tasks.enqueue('local','default','',mini,'','Fixture',{},session_id=private.session.id)
    tasks.update('local',task['id'],run_id=child.id,status='waiting_input')
    tool=runtime.services.get_tool('gallery.search')
    invocation=runtime.services.create_invocation(tool=tool,provider_key='fixture',caller_id='test',session_id=thread.session.id,trace_id=origin.id,arguments={},timeout_ms=30000)
    app=FastAPI();app.include_router(create_router(lambda:runtime,lambda:principal))
    url=f'/agent-runs/{origin.id}/browser-tasks/{task["id"]}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get(url)).status_code==404
        runtime.services.update_invocation_progress(invocation.id,{'content':{'browser_task_id':task['id']}})
        data=(await client.get(url)).json()
        assert data['requires_user'] and data['interactions'][0]['id']==interaction.id
        assert (await client.post(url,json={'action':'continue','interaction_id':'other','response_id':'one'})).status_code==409
        assert runtime.agents.list_interactions(child.id)[0].status.value=='pending'
        response=await client.post(url,json={'action':'continue','interaction_id':interaction.id,'response_id':'one'})
        assert response.status_code==200
        assert runtime.agents.list_interactions(child.id)[0].response=={'continued':True}
        assert (await client.post(url,json={'action':'continue','interaction_id':interaction.id,'response_id':'one'})).status_code==200
        assert (await client.post(url,json={'action':'continue','interaction_id':interaction.id,'response_id':'two'})).status_code==409


def test_span_button_plus_is_an_increment_from_production_selector():
    from ai2apps.browser.shopping import CART_SCRIPT
    import subprocess
    source=CART_SCRIPT[CART_SCRIPT.index(' const increase='):CART_SCRIPT.index(' const label=increase')]
    script="const node={textContent:' +  ',getAttribute:()=>null};const c={};const shoppingQuery=(c,selector)=>selector.includes('.a-button')?[node]:[];"+source+"console.log(increase===node);"
    assert subprocess.check_output(['node','-e',script],text=True).strip()=='true'

@pytest.mark.asyncio
async def test_run_owner_metadata_is_minimal_trusted_and_uses_same_agent_transport(runtime):
    import httpx
    from test_app_interactions import client_app
    from ai2apps.web.mobile_agent_gateway import business_target
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Metadata')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    url=f'/v1/platform/agent-runs/{run.id}/owners'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime)),base_url='http://test') as client:
        response=await client.get(url)
        assert response.status_code==200
        data=response.json()
        assert data['apps']
        assert all(set(a)=={'app_key','display_name','navigation'} for a in data['apps'])
        assert any(a['navigation']['icon']!='app-window' for a in data['apps'])
    assert business_target('GET',f'/agent-runs/{run.id}/owners')==f'/agent-runs/{run.id}/owners'
