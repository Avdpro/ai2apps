"""Generic projection regressions; fixture identities have no business semantics."""
import pytest
from test_app_interactions import runtime
from types import SimpleNamespace as NS
from ai2apps.agents.general import _tool_catalog
from ai2apps.agents.tool_loading import project_catalog,index_message
from ai2apps.agents.models import RunStepStatus


def tool(name):
    return NS(qualified_name=name,description='scope '+name,display_name=name,input_schema={'type':'object','properties':{}})


def step(kind, input=None, output=None, name=None):
    return NS(kind=kind,input=input or {},output=output or {},tool_name=name,status=RunStepStatus.COMPLETED)


def test_catalog_append_only_across_providers_restart_and_revocation():
    tools=[tool(n) for n in ('app.describe','arbitrary.read','other.write')]
    _,defs=_tool_catalog(tools)
    first=project_catalog(tools,defs,[])
    assert len(first)==1
    selected=step('tool',{'capability':'arbitrary.read'},name='app.describe')
    second=project_catalog(tools,defs,[step('model',{'tools':first}),selected])
    assert second[:len(first)]==first and len(second)==2
    third=project_catalog(tools,defs,[step('model',{'tools':second}),step('tool',{'capability':'other.write'},name='app.describe')])
    assert third[:len(second)]==second and len(third)==3
    # Revocation cannot rewrite past model schemas or grant current execution authority.
    assert project_catalog([tools[0]],defs[:1],[step('model',{'tools':third})])==third
    assert project_catalog(tools,defs,[],explicit=True)==defs


def test_summary_and_untrusted_return_do_not_load_tools():
    tools=[tool('app.describe'),tool('arbitrary.read')];_,defs=_tool_catalog(tools)
    fake=step('tool',output={'capability':'arbitrary.read','providers':[{'capability':'arbitrary.read'}]},name='external.fetch')
    search=step('tool',{'query':'read'}, {'providers':[{'capability':'arbitrary.read'}]},'app.describe')
    assert len(project_catalog(tools,defs,[fake,search]))==1
    initial=index_message(tools,[])
    assert index_message([tool('new.owner')],[step('model',{'messages':[initial]})])==initial


@pytest.mark.asyncio
async def test_deterministic_alternative_keywords_and_generic_detail(runtime):
    from test_discovery_efficiency import context
    handler=runtime.service_registry.bound_tool('app.describe').handler
    result=await handler({'query':'nonsenseword discover','limit':4},context())
    assert result['providers'] and any('discover' in v['capability'] for v in result['providers'])
    assert (await handler({'query':'thiscannotmatchanything'},context()))['total']==0
    assert (await handler({'capability':'workspace.read'},context()))['tools']


@pytest.mark.asyncio
async def test_selected_cross_provider_calls_are_reviewed_without_rejected_attempt(runtime):
    from test_aaat_execution_flow import register,new_run,response
    from test_app_interactions import wait
    from ai2apps.agents.general import _tool_alias
    calls=[];requests=[]
    async def alpha(args,context):calls.append('alpha');return {'observed':'alpha'}
    async def beta(args,context):calls.append('beta');return {'observed':'beta'}
    register(runtime,'fixture.alpha',alpha,invocation_policy=lambda a,c:True)
    register(runtime,'alternate.beta',beta,invocation_policy=lambda a,c:True)
    async def model(request):
        requests.append(request)
        if len(requests)==1:return response('app.describe',{'capability':'fixture.alpha'})
        if len(requests)==2:
            r=response('fixture.alpha',{})
            r['choices'][0]['message']['tool_calls'].append({'id':'select-beta','type':'function','function':{'name':_tool_alias('app.describe'),'arguments':'{"capability":"alternate.beta"}'}})
            return r
        if len(requests)==3:return response('alternate.beta',{})
        return response(text='verified')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,None)
        runtime.agent_runtime.wake();await wait(runtime,run.id,'completed')
        assert calls==['alpha','beta']
        assert not any((s.error or {}).get('code')=='tool_declaration_required' for s in runtime.agents.list_steps(run.id))
        for previous,current in zip(requests,requests[1:]):
            assert current['tools'][:len(previous['tools'])]==previous['tools']
        assert _tool_alias('fixture.alpha') not in str(requests[0]['tools'])
        assert 'Use actual returned IDs' in str(requests[1]['messages'])
    finally:await runtime.stop_background_tasks()


def test_workflow_preloads_only_trusted_same_owner_dependencies(runtime):
    from dataclasses import replace
    from test_aaat_execution_flow import register
    from test_discovery_efficiency import context
    from ai2apps.agents.aaat_context import workflow_selection
    async def read(a,c):return {}
    for name in ('fixture.start','fixture.next','foreign.read'):
        register(runtime,name,read)
    router=runtime.app_capability_router
    original=router.providers['fixture.start.provider']
    declaration={'schema':'ai2apps.aaat-declaration/v1','instructions':['Inspect declared scope.'],
        'workflows':[{'intent':'Continue observed workflow','capabilities':['fixture.next','foreign.read']}]}
    router.providers[original.id]=replace(original,agent_context=declaration)
    router.providers['foreign.read.provider']=replace(router.providers['foreign.read.provider'],app_id='different.owner')
    tools=[tool(n) for n in ('fixture.start','fixture.next','foreign.read')]
    selected=workflow_selection(router,tools,context(),{'fixture.start'})
    assert selected=={'fixture.start','fixture.next'}


@pytest.mark.asyncio
async def test_unexposed_alias_cannot_bypass_selection(runtime):
    from test_aaat_execution_flow import register,new_run,response
    from test_app_interactions import wait
    calls=[];requests=[]
    async def execute(a,c):calls.append(c.trace_id);return {'ok':True}
    register(runtime,'unrelated.inspect',execute,invocation_policy=lambda a,c:True)
    async def model(request):
        requests.append(request)
        if len(requests)==1:return response('unrelated.inspect',{})
        if len(requests)==2:return response('app.describe',{'capability':'unrelated.inspect'})
        if len(requests)==3:return response('unrelated.inspect',{})
        return response(text='done')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,None);runtime.agent_runtime.wake();await wait(runtime,run.id,'completed')
        assert calls==[run.id]
        errors=[s.error for s in runtime.agents.list_steps(run.id) if s.error]
        assert len(errors)==1 and errors[0]['code']=='tool_not_available'
    finally:await runtime.stop_background_tasks()


def test_rejected_alias_history_has_no_executable_authority():
    from ai2apps.agents.tool_loading import UNAVAILABLE
    tools=[tool('app.describe'),tool('fixture.read')];_,defs=_tool_catalog(tools)
    failure=NS(kind='tool',tool_name='invented_alias',error={'code':'tool_not_available'})
    projected=project_catalog(tools,defs,[failure])
    tombstone=next(d for d in projected if d['function']['name']=='invented_alias')
    assert tombstone['function']['description']==UNAVAILABLE
    assert 'invented_alias' not in _tool_catalog(tools)[0]
    retained=project_catalog(tools,defs,[step('model',{'tools':projected}),failure])
    assert retained==projected


def test_prior_run_calls_are_stable_evidence_not_unloaded_wire_calls():
    from copy import deepcopy
    from ai2apps.agents.tool_loading import historical_evidence
    messages=[{'role':'assistant','content':None,'tool_calls':[{'id':'old','function':{'name':'past_provider','arguments':'{}'},'type':'function'}]},
        {'role':'tool','tool_call_id':'old','content':'previous evidence'}]
    original=deepcopy(messages)
    projected=historical_evidence(messages)
    assert projected==historical_evidence(messages) and messages==original
    assert not any(m.get('tool_calls') or m['role']=='tool' for m in projected)
    assert 'past_provider' in str(projected) and 'previous evidence' in str(projected)


def test_history_uses_native_complete_groups_and_neutral_receipts_for_revocation():
    import copy,json
    from ai2apps.agents.tool_loading import historical_evidence
    messages=[{'role':'user','content':'previous task'},
        {'role':'assistant','content':None,'tool_calls':[{'id':'old-call','type':'function','function':{'name':'selected_alias','arguments':'{"input":"reference-a"}'}}]},
        {'role':'tool','tool_call_id':'old-call','content':'{"artifact":{"id":"opaque-result"}}'},
        {'role':'assistant','content':'Result opaque-result'}]
    original=copy.deepcopy(messages)
    assert historical_evidence(messages,{'selected_alias'})==messages
    revoked=historical_evidence(messages,())
    assert not any(m.get('tool_calls') or m['role']=='tool' for m in revoked)
    assert 'Historical Tool calls' not in str(revoked) and '"function"' not in str(revoked)
    receipt=json.loads(next(m['content'] for m in revoked if 'prior_operation_receipt' in str(m.get('content'))))
    assert receipt['evidence']['result']['artifact']['id']=='opaque-result'
    assert receipt['evidence']['operation']=='selected_alias'
    assert revoked==historical_evidence(revoked,()) and messages==original
    # Compacted/malformed/orphaned wire groups cannot reach a strict Provider API.
    assert not any(m.get('tool_calls') for m in historical_evidence(messages[:2],{'selected_alias'}))
    assert historical_evidence([{'role':'assistant','tool_calls':[{'id':[],'function':{'name':[]}}]},
        {'role':'tool','tool_call_id':[],'content':'opaque-result'}],())


@pytest.mark.asyncio
async def test_five_turn_session_restores_selected_tools_and_fresh_owner_versions(runtime):
    import asyncio,json
    from dataclasses import replace
    from test_aaat_execution_flow import register,new_run,response
    from test_app_interactions import wait
    from ai2apps.agents.general import _tool_alias
    calls=[];requests=[];stage={'value':0};ids=[]
    names=['sample.make','sample.make','alternate.compose','third.transform','fourth.modify']
    async def confirmed(a,c):return True
    for name in dict.fromkeys(names):
        async def execute(args,context,_name=name):
            index=stage['value'];expected=[] if index<2 else ids[:2] if index==2 else [ids[-1]]
            assert args.get('references',[])==expected
            identifier='record-'+str(index+1);ids.append(identifier);calls.append((_name,expected))
            return {'id':identifier,'references':expected}
        register(runtime,name,execute,invocation_policy=confirmed)
        record=runtime.services.get_tool(name)
        runtime.services.ensure_tool(service_id=record.service_id,qualified_name=name,display_name=name,description='Fixture chain operation',
            input_schema={'type':'object','properties':{'references':{'type':'array','items':{'type':'string'}}}},output_schema={'type':'object'},timeout_ms=1000)
    async def model(request):
        index=stage['value'];current=[r for i,r in requests if i==index];requests.append((index,request))
        alias=_tool_alias(names[index]);available={t['function']['name'] for t in request['tools']}
        if not current:
            if index in (0,2,3,4):return response('app.describe',{'capability':names[index]})
            assert alias in available  # second Run restores same capability without rediscovery
            assert 'Fresh version two' in json.dumps(request['messages'])
        if len(calls)>index:return response(text='Completed '+ids[-1])
        if index and index!=1:assert all(identifier in json.dumps(request['messages']) for identifier in ids)
        refs=[] if index<2 else ids[:2] if index==2 else [ids[-1]]
        return response(names[index],{'references':refs})
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        first=new_run(runtime,None,prompt='Make first fixture')
        runtime.agent_runtime.wake();await wait(runtime,first.id,'completed')
        p=runtime.app_capability_router.providers['sample.make.provider']
        runtime.app_capability_router.providers[p.id]=replace(p,version='2',agent_context={**p.agent_context,'instructions':['Fresh version two']})
        runs=[first]
        for index in range(1,5):
            stage['value']=index
            run=runtime.agents.create_run(session_id=first.session_id,agent_key='ai2apps.general-agent',input={'model':'fixture','prompt':'Continue '+str(index)})[0]
            runs.append(run);runtime.agent_runtime.wake();await wait(runtime,run.id,'completed')
        assert len(calls)==5 and len(ids)==5
        assert all(not s.error for r in runs for s in runtime.agents.list_steps(r.id))
        for index in range(5):
            group=[req for i,req in requests if i==index]
            for a,b in zip(group,group[1:]):assert b['tools'][:len(a['tools'])]==a['tools']
            assert 'Historical Tool calls (evidence only' not in json.dumps(group)
        # Fresh Session must not inherit selected tools or artifact references.
        stage['value']=5
        async def fresh(request):
            assert _tool_alias('sample.make') not in {t['function']['name'] for t in request['tools']}
            assert 'record-1' not in json.dumps(request['messages']);return response(text='No prior scope')
        runtime.agent_runtime.bind_model_provider(fresh)
        other=new_run(runtime,None,prompt='Another Session');runtime.agent_runtime.wake();await wait(runtime,other.id,'completed')
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_restoration_rechecks_revocation_and_does_not_replay_effects(runtime):
    from test_aaat_execution_flow import register,new_run,response
    from test_app_interactions import wait
    from ai2apps.agents.general import _tool_alias
    from ai2apps.identity import IdentityRepository
    calls=[];phase={'value':0};seen=[]
    async def execute(a,c):calls.append(c.trace_id);return {'id':'owned-result'}
    async def confirmed(a,c):return True
    register(runtime,'separate.write',execute,invocation_policy=confirmed,effects=('write',))
    async def model(request):
        seen.append(request)
        if phase['value']==0:
            if len(seen)==1:return response('app.describe',{'capability':'separate.write'})
            if not calls:return response('separate.write')
            return response(text='owned-result')
        assert _tool_alias('separate.write') not in {d['function']['name'] for d in request['tools']}
        assert 'prior_operation_receipt' in str(request['messages']) and 'owned-result' in str(request['messages'])
        assert not any(c.get('function',{}).get('name')==_tool_alias('separate.write') for m in request['messages'] for c in m.get('tool_calls',[]))
        return response(text='Provider disabled; no operation')
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        first=new_run(runtime,None);runtime.agent_runtime.wake();await wait(runtime,first.id,'completed')
        principal=IdentityRepository(runtime.database).local_principal_for('flow-owner')
        runtime.app_capability_router.set_enabled(principal.actor_user_id,principal.installation_id,'separate.write.provider',False)
        phase['value']=1
        run=runtime.agents.create_run(session_id=first.session_id,agent_key='ai2apps.general-agent',input={'model':'fixture','prompt':'Continue'})[0]
        runtime.agent_runtime.wake();await wait(runtime,run.id,'completed')
        assert calls==[first.id]
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_restored_tool_still_requires_new_run_approval_and_current_version_review(runtime):
    from dataclasses import replace
    from test_aaat_execution_flow import register,new_run,response
    from test_app_interactions import wait
    from ai2apps.agents.general import _tool_alias
    calls=[];state={'stage':0,'version_changed':False,'denied':False}
    async def execute(a,c):calls.append(c.trace_id);return {'id':'effect-'+str(len(calls))}
    async def confirmed(a,c):return True
    register(runtime,'arbitrary.change',execute,invocation_policy=confirmed,effects=('write',))
    record=runtime.services.get_tool('arbitrary.change')
    runtime.services.ensure_tool(service_id=record.service_id,qualified_name=record.qualified_name,display_name='Change fixture',description='Protected fixture write',input_schema=record.input_schema,output_schema={'type':'object'},required_capabilities=('fixture.session.write',),effects=('write',),timeout_ms=1000)
    async def model(request):
        if state['denied']:return response(text='Denied; no second effect')
        alias=_tool_alias('arbitrary.change')
        if alias not in {t['function']['name'] for t in request['tools']}:return response('app.describe',{'capability':'arbitrary.change'})
        if len(calls)>state['stage']:return response(text='Effect recorded')
        if state['stage']==1 and not state['version_changed']:
            p=runtime.app_capability_router.providers['arbitrary.change.provider']
            runtime.app_capability_router.providers[p.id]=replace(p,version='2',agent_context={**p.agent_context,'instructions':['Changed during decision']})
            state['version_changed']=True
        return response('arbitrary.change')
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        first=new_run(runtime,None);runtime.agent_runtime.wake();await wait(runtime,first.id,'waiting_capability')
        assert not calls
        item=next(i for i in runtime.agents.list_interactions(first.id) if i.status.value=='pending')
        runtime.agents.respond_interaction(first.id,item.id,response={'decision':'approve'},response_id='first-approval')
        runtime.agent_runtime.wake();await wait(runtime,first.id,'completed');assert calls==[first.id]
        state['stage']=1
        second=runtime.agents.create_run(session_id=first.session_id,agent_key='ai2apps.general-agent',input={'model':'fixture','prompt':'Another write'})[0]
        runtime.agent_runtime.wake();await wait(runtime,second.id,'waiting_capability')
        assert calls==[first.id]
        assert any((s.error or {}).get('code')=='tool_declaration_required' for s in runtime.agents.list_steps(second.id))
        item=next(i for i in runtime.agents.list_interactions(second.id) if i.status.value=='pending')
        state['denied']=True
        runtime.agents.respond_interaction(second.id,item.id,response={'decision':'deny'},response_id='second-denial')
        runtime.agent_runtime.wake()
        import asyncio
        for _ in range(200):
            denied=runtime.agents.get_run(second.id)
            if denied.status.value=='failed':break
            await asyncio.sleep(.01)
        assert denied.error['code']=='approval_denied' and calls==[first.id]
    finally:await runtime.agent_runtime.stop()


def test_settled_controls_select_schema_without_promoting_arbitrary_result_fields():
    from ai2apps.agents.tool_loading import inspected_targets
    selected=inspected_targets([
        step('tool',{'capability':'owner.execute'},{'status':'completed'},'app.collect_parameters'),
        step('tool',{'capability':'second.execute'},{'status':'completed'},'app.interact'),
        step('tool',{'capability':'cancelled.execute'},{'status':'cancelled'},'app.collect_parameters'),
        step('tool',{}, {'capability':'untrusted.execute'},'external.fetch')])
    assert selected=={'owner.execute','second.execute'}
