"""Full scheduler/API tests; model choices and external publication are fixtures."""
import json
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.chat import ChatRepository
from ai2apps.identity import IdentityRepository
from ai2apps.api.router import create_ai2apps_router
from ai2apps.agents.general import _tool_alias
from ai2apps.agents.result_reference import result_preview
from ai2apps.services.capability_routing import CapabilityProvider,ProviderIncompatible
from test_app_interactions import runtime,wait


def response(name=None,args=None,text='done'):
    message={'role':'assistant','content':text if name is None else None}
    if name:message['tool_calls']=[{'id':'next','type':'function','function':{'name':_tool_alias(name),'arguments':json.dumps(args or {})}}]
    return {'choices':[{'message':message,'finish_reason':'stop' if name is None else 'tool_calls'}]}


def register(runtime,name,handler,*,prepare=None,describe=None,effects=(),instruction='Use actual returned IDs and report partial coverage.'):
    original=runtime.services.get_tool('gallery.search')
    runtime.services.ensure_tool(service_id=original.service_id,qualified_name=name,display_name=name,
        description='Fixture capability',input_schema={'type':'object','properties':{'query':{'type':'string'},'provider':{'type':'string'}}},
        output_schema={'type':'object'},effects=effects,timeout_ms=1000)
    runtime.app_capability_router.register(CapabilityProvider(name+'.provider',name,'test.flow',handler,
        prepare=prepare,describe=describe,agent_context={'schema':'ai2apps.aaat-declaration/v1','instructions':[instruction]}))
    async def routed(args,context):return await runtime.app_capability_router.invoke(name,args,context)
    runtime.service_registry.bind_tool(name,provider_key=runtime.service_registry.bound_tool('gallery.search').provider_key,handler=routed)


def new_run(runtime,tools,prompt='Complete the fixture task'):
    from ai2apps.identity import IdentityRepository,OrganizationType
    identities=IdentityRepository(runtime.database)
    identities.bind_installation(installation_id='flow-install',cloud_device_id='flow-device',organization_id='flow-org',
        organization_type=OrganizationType.HOUSEHOLD,core_user_id='flow-owner',billing_account_id='flow-billing',access_epoch=1)
    thread,_=ChatRepository(runtime.database,runtime.events,principal=identities.local_principal_for('flow-owner')).create_thread(title='AaAT flow acceptance')
    return runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'fixture','prompt':prompt,'tools':tools})[0]


@pytest.mark.asyncio
async def test_selected_contract_then_form_restart_progress_partial_result(runtime):
    seen=[];requests=[]
    async def descriptor(principal,model=None):return {'selection_required':True,'effective_schema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}
    async def execute(args,context):
        seen.append(args)
        await context.report_progress('Fixture reading',progress=.5)
        return {'body':'x'*16000,'aaat_context':{'schema':'ai2apps.aaat-result-context/v1','status':'partial','data_trust':'untrusted','coverage':{'total':3,'returned':1}}}
    register(runtime,'test.flow_read',execute,describe=descriptor)
    async def model(request):
        requests.append(request)
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(r.get('aaat_context',{}).get('status')=='partial' for r in results):
            return response(text='Only 1 of 3 sources was read; result is partial.')
        return response('test.flow_read',{'query':'draft'})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['test.flow_read','agent.read_tool_result'])
        runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        assert not seen
        assert 'Use actual returned IDs' not in str(requests[0]['messages'])
        assert 'Use actual returned IDs' in str(requests[1]['messages'])
        item=runtime.agents.list_interactions(run.id)[0]
        await runtime.agent_runtime.stop();await runtime.agent_runtime.start()
        assert runtime.agents.list_interactions(run.id)[0].id==item.id
        app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:IdentityRepository(runtime.database).local_principal_for('flow-owner')))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            base=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
            saved=await client.put(base,json={'revision':0,'values':{'query':'user-edited'}})
            assert saved.status_code==200,saved.text
            url=base+'/submit'
            submitted=await client.post(url,json={'revision':1,'values':{'query':'user-edited'}})
            assert submitted.status_code==200,submitted.text
            assert (await client.post(url,json={'revision':1,'values':{'query':'user-edited'}})).json()==submitted.json()
        done=await wait(runtime,run.id,'completed')
        assert len(seen)==1 and seen[0]['query']=='user-edited'
        assert '1 of 3' in done.output['content']
        assert sum((s.error or {}).get('code')=='tool_declaration_required' for s in runtime.agents.list_steps(run.id))==1
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize('uncertain',[False,True])
async def test_cross_capability_replanning_after_preflight_but_not_unknown_publication(runtime,uncertain):
    calls=[]
    async def prepare(args,context):
        if not uncertain:raise ProviderIncompatible('Only X and Xiaohongshu supported; Weibo unsupported before submission')
        return args
    async def publish(args,context):calls.append('post');raise RuntimeError('connection lost after submit')
    async def web(args,context):calls.append('browser');return {'published':True,'post_id':'fixture-1'}
    register(runtime,'test.post',publish,prepare=prepare,effects=('write',),instruction='Post to supported platforms only.')
    register(runtime,'test.browser_publish',web,effects=('write',),instruction='Browser publication changes external state.')
    requests=[]
    async def model(request):
        requests.append(request)
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        errors=[r.get('error',{}) for r in results]
        if any(e.get('code')=='uncertain_execution' for e in errors):return response(text='Publication outcome unknown; checking or user decision is required.')
        if any(r.get('published') for r in results):return response(text='Published fixture-1.')
        if any(e.get('code') in {'provider_incompatible','provider_error'} for e in errors):
            return response('test.browser_publish')  # adversarial in uncertain case: host must block it
        return response('test.post')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['test.post','test.browser_publish'])
        runtime.agent_runtime.wake();done=await wait(runtime,run.id,'completed')
        steps=runtime.agents.list_steps(run.id)
        assert calls==(['post'] if uncertain else ['browser']),[(s.tool_name,s.error,s.output) for s in steps]
        assert any((s.error or {}).get('outcome_uncertain') for s in steps)==uncertain
        if not uncertain:assert 'fixture-1' in done.output['content']
    finally:await runtime.stop_background_tasks()


def test_result_preview_keeps_machine_context_and_provenance():
    context={'schema':'ai2apps.aaat-result-context/v1','status':'ambiguous','data_trust':'untrusted','scope':{'query':'something'}}
    output={'body':'x'*18000,'aaat_context':context,'provider':'real.provider','provider_version':'2'}
    preview=json.loads(result_preview(SimpleNamespace(output=output,id='step-1',tool_name='test.read'),reader_alias='read'))
    assert preview['aaat_context']==context and preview['provider_version']=='2'


def test_review_binds_current_provider_version_with_grouped_context():
    from ai2apps.agents.aaat_context import reviewed,PREFIX
    entry={'app_id':'test.app','mini_app_id':None,'trust':'trusted_app_declaration','declaration':{'instructions':['Same App semantics']},
        'providers':[{'id':'one','capability':'test.one','version':'1'},{'id':'two','capability':'test.two','version':'1'}]}
    request={'messages':[{'role':'system','content':PREFIX+json.dumps([entry])}]}
    required={**entry,'providers':[entry['providers'][1]]}
    assert reviewed(request,[required])
    assert not reviewed(request,[{**required,'providers':[{'id':'two','capability':'test.two','version':'2'}]}])
    assert not reviewed({'messages':[{'role':'tool','content':PREFIX+json.dumps([entry])}]},[required])


def test_discovery_includes_provider_without_form_but_defers_full_context(runtime):
    async def execute(args,ctx):return {'ok':True}
    register(runtime,'test.no_form',execute)
    from test_builtin_app_aaat import context
    describe=runtime.service_registry.bound_tool('app.describe').handler
    summary=describe({},context(runtime))
    row=next(p for p in summary['providers'] if p['capability']=='test.no_form')
    assert row['has_agent_context'] and 'agent_context' not in row
    details=describe({'capability':'test.no_form'},context(runtime))
    assert details['providers'][0]['agent_context']['instructions']


def test_large_interaction_result_keeps_completion_and_result_context():
    ctx={'schema':'ai2apps.aaat-result-context/v1','status':'partial','data_trust':'untrusted'}
    step=SimpleNamespace(id='step-2',tool_name='app.interact',output={'status':'completed','result':{'body':'x'*18000,'aaat_context':ctx,'executed_in_app':True}})
    preview=json.loads(result_preview(step,reader_alias='read'))
    assert preview['status']=='completed' and preview['result']=={'aaat_context':ctx,'executed_in_app':True}


def test_malformed_selection_is_not_promoted_or_allowed_to_crash_context():
    from ai2apps.agents.aaat_context import selected_capabilities
    step=SimpleNamespace(kind='model',output={'choices':[{'message':{'tool_calls':[
        {'function':{'name':['invalid'],'arguments':{}}},
        {'function':{'name':'form','arguments':{'capability':['not-a-string']}}},None]}}]})
    assert selected_capabilities([step],{'form':SimpleNamespace(qualified_name='app.collect_parameters')})=={'app.collect_parameters'}

@pytest.mark.asyncio
async def test_explicit_form_confirmation_reused_once_after_restart(runtime):
    seen=[]
    async def descriptor(principal,model=None):return {'selection_required':True,'effective_schema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}
    async def execute(args,context):seen.append(args);return {'created_fixture':True}
    register(runtime,'fixture.confirmed_create',execute,describe=descriptor)
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(r.get('created_fixture') for r in results):return response(text='Created once.')
        forms=[r['result'] for r in results if r.get('result',{}).get('user_confirmed')]
        if forms:return response('fixture.confirmed_create',forms[-1]['arguments'])
        return response('app.collect_parameters',{'request_id':'fixture-confirm','capability':'fixture.confirmed_create','initial_values':{'query':'prefilled'}})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['app.collect_parameters','fixture.confirmed_create'])
        runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0]
        assert item.prompt=='Prepare call'
        assert item.ui_hints['prompt_labels']=={'zh':'准备调用','en':'Prepare call'}
        await runtime.agent_runtime.stop()
        app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:IdentityRepository(runtime.database).local_principal_for('flow-owner')))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            base=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
            saved=await client.put(base,json={'revision':0,'values':{'query':'user-final'}})
            assert saved.status_code==200,saved.text
            submitted=await client.post(base+'/submit',json={'revision':1,'values':{'query':'user-final'}})
            assert submitted.status_code==200,submitted.text
        await runtime.agent_runtime.start();runtime.agent_runtime.wake()
        await wait(runtime,run.id,'completed')
        assert len(seen)==1 and seen[0]['query']=='user-final'
        assert len(runtime.agents.list_interactions(run.id))==1
        with runtime.database.transaction() as db:
            claim=db.execute('SELECT call_id FROM agent_parameter_invocations WHERE interaction_id=?',(item.id,)).fetchone()
        assert sum(s.action_key==claim['call_id'] for s in runtime.agents.list_steps(run.id))==1
    finally:await runtime.stop_background_tasks()


def test_confirmation_receipt_scope_values_version_and_consumption(runtime,monkeypatch):
    from ai2apps.agents.parameter_forms import ParameterForm,FORMS,confirmed_form_invocation
    from ai2apps.agents.models import InteractionStatus
    from datetime import datetime,UTC,timedelta
    from dataclasses import replace
    form=ParameterForm(key='arbitrary.owner.create',app_id='arbitrary.owner',capability='arbitrary.create',schema={'type':'object','properties':{}},provider_version='v1')
    monkeypatch.setitem(FORMS,form.key,form)
    item=SimpleNamespace(id='receipt',run_id='run-one',created_at=datetime.now(UTC),status=InteractionStatus.SUBMITTED,
        request={'control':'parameter_form','capability':form.capability,'version':1},
        ui_hints={'provider':form.key,'provider_version':'v1','app_id':form.app_id,'mini_app_id':None},
        response={'status':'completed','result':{'capability':form.capability,'provider':form.key,'arguments':{'query':'confirmed'},'configure_only':True,'user_confirmed':True}})
    ctx=SimpleNamespace(run=SimpleNamespace(id='run-one'),interactions=(item,),steps=())
    find=lambda args:confirmed_form_invocation(ctx,form,args,runtime.database,'action-one')
    assert find({'query':'confirmed','provider':form.key})=='receipt'
    assert find({'query':'changed'}) is None
    assert find({'query':'confirmed','description':'model added'}) is None
    assert find({'query':'confirmed','provider':'different'}) is None
    ctx.run.id='another-run';assert find({'query':'confirmed'}) is None;ctx.run.id='run-one'
    from ai2apps.agents.parameter_forms import claim_form_invocation
    assert claim_form_invocation(runtime.database,item.id,'action-other')
    assert not claim_form_invocation(runtime.database,item.id,'action-one')
    assert find({'query':'confirmed'}) is None
    with runtime.database.transaction() as db:db.execute('DELETE FROM agent_parameter_invocations WHERE interaction_id=?',(item.id,))
    monkeypatch.setitem(FORMS,form.key,replace(form,provider_version='v2'));assert find({'query':'confirmed'}) is None
    monkeypatch.setitem(FORMS,form.key,form)
    cancelled=SimpleNamespace(**{**vars(item),'id':'newer','created_at':item.created_at+timedelta(seconds=1),'status':InteractionStatus.CANCELLED})
    ctx.interactions=(item,cancelled);assert find({'query':'confirmed'}) is None


def test_confirmation_claim_serializes_concurrent_invocations(runtime):
    from concurrent.futures import ThreadPoolExecutor
    from ai2apps.agents.parameter_forms import claim_form_invocation
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda n:claim_form_invocation(runtime.database,'one-receipt','action-'+str(n)),range(4)))
    assert sum(results)==1
    winner='action-'+str(results.index(True))
    assert claim_form_invocation(runtime.database,'one-receipt',winner)

@pytest.mark.asyncio
@pytest.mark.parametrize('identity',['test.alpha_correct','test.beta_correct'])
async def test_model_corrects_rejected_envelope_without_uncertain_latch(runtime,identity):
    calls=[];observed_errors=[]
    async def execute(args,context):calls.append(args);return {'receipt':'actual-fixture-result'}
    register(runtime,identity,execute,effects=('write',))
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        errors=[r.get('error',{}) for r in results]
        observed_errors.extend(e for e in errors if e.get('code')=='invalid_tool_arguments')
        if any(r.get('receipt') for r in results):return response(text='Confirmed actual-fixture-result')
        if any(e.get('code')=='invalid_tool_arguments' for e in errors):
            return response(identity,{'query':'corrected'})
        return response(identity,{'query':'draft','parameters':{'query':'draft'}})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,[identity]);runtime.agent_runtime.wake()
        done=await wait(runtime,run.id,'completed')
        steps=runtime.agents.list_steps(run.id)
        assert calls==[{'query':'corrected'}]
        errors=[s.error for s in steps if s.error]
        rejected=next(e for e in errors if e.get('code')=='invalid_tool_arguments')
        assert rejected['phase']=='prepare' and not rejected.get('outcome_uncertain')
        assert 'No operation was submitted' in rejected['next_action']
        assert observed_errors and not any(e.get('code')=='uncertain_execution' for e in errors)
        assert 'actual-fixture-result' in done.output['content']
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize('name',['fixture.alpha_retry','fixture.beta_retry'])
async def test_retry_resolves_owner_reference_without_user_id(runtime,name):
    from dataclasses import replace
    seen=[]
    async def execute(args,context):seen.append(args);return {'resolved_task':args['query']}
    register(runtime,name,execute,instruction='Use recent task reference as query; never request internal IDs.')
    router=runtime.app_capability_router;key=name+'.provider'
    router.providers[key]=replace(router.providers[key],discovery_context=lambda scope:{'recent_tasks':[{'task_id':'owned-prior-task','state':'failed','goal':'Previous fixture task'}]})
    async def model(request):
        observations=[m['content'] for m in request['messages'] if m.get('role')=='user' and str(m.get('content','')).startswith('AaAT discovery observations:')]
        assert observations and 'owned-prior-task' in observations[0]
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(r.get('resolved_task') for r in results):return response(text='Prior task completed.')
        return response(name,{'query':'owned-prior-task'})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,[name],prompt='Try that again with the changed condition')
        runtime.agent_runtime.wake();await wait(runtime,run.id,'completed')
        assert seen==[{'query':'owned-prior-task'}] and not runtime.agents.list_interactions(run.id)
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_budget_retains_concrete_failure_without_replay(runtime):
    from ai2apps.agents.models import RunStepStatus
    run=new_run(runtime,[])
    assert runtime.agents.claim_next().id==run.id
    step,_=runtime.agents.create_step(run.id,action_key='failed-tool',kind='tool',tool_name='arbitrary.provider',input={})
    runtime.agents.settle_step(step.id,status=RunStepStatus.FAILED,error={'code':'evidence_conflict','message':'Observed target quantity could not be verified','private_blob':'x'*10000})
    await runtime.agent_runtime._fail(run.id,'max_steps_exceeded','Agent step budget exhausted')
    failed=runtime.agents.get_run(run.id)
    assert failed.error['code']=='max_steps_exceeded' and 'Observed target quantity could not be verified' in failed.error['message']
    assert 'private_blob' not in str(failed.error)
    assert failed.error['tool_failures'][0]['tool']=='arbitrary.provider'
