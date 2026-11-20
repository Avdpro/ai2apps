"""Real Bot/Run/policy/interaction flow; model and owner effects are fixtures."""
import json
from dataclasses import replace
import pytest
from ai2apps.identity import RequestPrincipal
from ai2apps.messager.bots import install, REGISTRATION
from ai2apps.services.capability_routing import CapabilityProvider
from test_app_chat_durable import bind_identity, response
from test_app_interactions import runtime, wait
from bot_access_fixtures import restricted_bot
P=RequestPrincipal.legacy_local


def setup(r,name='fixture.paint',app='ai2apps.gallery',required=(),describe=None,*,effects=('workspace.write',)):
    calls=[]
    async def handler(args,ctx):calls.append((args,ctx.session_id));return {'created':'fixture-output'}
    source=r.services.get_tool('todo.get');instance=r.services.get_instance_for_service(source.service_id)
    r.services.ensure_tool(service_id=source.service_id,qualified_name=name,display_name='Fixture maker',description='Create a fixture output.',input_schema={'type':'object','properties':{'prompt':{'type':'string'}},'required':['prompt'],'additionalProperties':False},output_schema={'type':'object'},effects=effects,required_capabilities=required)
    provider=CapabilityProvider(app+'.'+name,name,app,handler,describe=describe,agent_context={'schema':'ai2apps.aaat-declaration/v1','instructions':['Create the requested fixture output.']})
    r.app_capability_router.register(provider)
    async def invoke(a,c):return await r.app_capability_router.invoke(name,a,c)
    r.service_registry.bind_tool(name,provider_key=instance.provider_key,handler=invoke)
    install(r);bot=r.messager_bots.create('local','Fixture Bot','Help with requested work')
    restricted_bot(r,bot,legacy_read=True)
    sid=r.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    return bot,sid,calls,provider


@pytest.mark.parametrize('name,app',[('fixture.paint','ai2apps.gallery'),('different.compose','ai2apps.knowledge')])
@pytest.mark.asyncio
async def test_discovery_approval_continues_original_run_without_background_grant(runtime,name,app):
    bot,sid,calls,provider=setup(runtime,name,app)
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created')=='fixture-output' for x in results):return response(text='Fixture complete')
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':name})
        return response(name,{'prompt':'panda eating bamboo'})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.app_chat.submit(P(),sid,'discover-request','Create the requested output','fixture')
        await wait(runtime,rid,'waiting_capability');assert calls==[]
        item=runtime.agents.list_interactions(rid)[0]
        assert item.request['tool_name']==name
        assert item.response_schema['properties']['scope']['enum']==['once','run']
        snap=runtime.app_chat.snapshot(P(),sid)['runs'][-1]['interactions'][0]
        assert snap['kind']=='approval' and snap['ui_hints']['control']=='approval'
        with pytest.raises(Exception):runtime.agents.respond_interaction(rid,item.id,response_id='forged',response={'decision':'approve','scope':'agent'})
        runtime.agents.respond_interaction(rid,item.id,response_id='approved',response={'decision':'approve','scope':'once'})
        runtime.agent_runtime.wake();await wait(runtime,rid,'completed')
        assert len(calls)==1 and calls[0][1]==sid
        assert runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')['providers']=={}
        assert runtime.app_chat.execution_authorization(rid)['mode']=='foreground'
        assert any(m['content']=='Fixture complete' for m in runtime.app_chat.snapshot(P(),sid)['messages'])
        other=restricted_bot(runtime,runtime.messager_bots.create('local','Other','Help'));other_sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':other['id']},{})
        other_run=runtime.app_chat.submit(P(),other_sid,'other-request','Create output','fixture')
        await wait(runtime,other_run,'waiting_capability');assert len(calls)==1
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_discovery_does_not_admit_forged_runs_changed_tools_or_hooks(runtime):
    bot,sid,calls,provider=setup(runtime)
    service=runtime.app_chat
    rid=service.submit(P(),sid,'not-started','Create output','fixture')
    context=runtime.tools.context_for_session(caller_id='test',session_id=sid,trace_id=rid)
    assert service.visible(context,'app.describe')
    assert service.authorize(context,provider.capability,{'prompt':'fixture'}) is False
    with pytest.raises(Exception):await runtime.tools.execute(provider.capability,{'prompt':'fixture'},context=context)
    with pytest.raises(Exception):await runtime.app_capability_router.invoke(provider.capability,{'prompt':'fixture'},context)
    assert not calls
    frozen=service.execution_authorization(rid)
    hook={**frozen,'mode':'background'};hook.pop('discovery_tools');hook.pop('discovery_providers')
    owner=service.owners[REGISTRATION]
    with pytest.raises(PermissionError):owner.validate_authorization('local',{'bot_id':bot['id']},hook,provider.capability,{})
    runtime.app_capability_router.providers[provider.id]=replace(provider,version='changed')
    with pytest.raises(Exception):service.authorize(context,provider.capability,{'prompt':'fixture'})
    forged,_=runtime.agents.create_run(session_id=sid,agent_key='ai2apps.app-chat-agent',input={'prompt':'forged','owner_authorization':frozen})
    with pytest.raises(PermissionError):service.validate_execution(service.binding(sid),owner,forged,'app.describe',{})


@pytest.mark.asyncio
@pytest.mark.parametrize('contract_changes', [False, True])
async def test_bot_uses_original_parameter_form_then_approval(runtime, contract_changes):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.agents.parameter_forms import FORMS
    contract = {}
    async def describe(principal, model=None):
        return contract
    bot,sid,calls,provider=setup(runtime,describe=describe)
    schema=runtime.services.get_tool(provider.capability).input_schema
    contract['effective_schema']=schema
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created')=='fixture-output' for x in results):return response(text='Completed with supplied parameters')
        if any(x.get('error', {}).get('code') in {'provider_binding_changed','parameter_contract_required'}
               for x in results if x.get('error')):
            if any(x.get('status')=='completed' and 'result' in x for x in results):
                return response(text='Review is required for the changed contract')
        submitted=next((x for x in results if x.get('status')=='completed' and 'result' in x),None)
        if submitted:return response(provider.capability,{'prompt':'user supplied panda'})
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
        return response('app.collect_parameters',{'request_id':'original-form','capability':provider.capability,'provider':provider.id,'values':{}})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=P))
    try:
        rid=runtime.app_chat.submit(P(),sid,'form-request','Create output, collect missing inputs','fixture')
        await wait(runtime,rid,'waiting_input')
        item=runtime.agents.list_interactions(rid)[0]
        assert item.ui_hints['control']=='parameter_form' and not calls
        snap=runtime.app_chat.snapshot(P(),sid)['runs'][-1]['interactions'][0]
        assert snap['request']['capability']==provider.capability
        url=f'/v1/platform/agent-runs/{rid}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            value=await client.get(url);assert value.status_code==200,value.text
            saved=await client.put(url,json={'revision':value.json()['revision'],'values':{'prompt':'user supplied panda'}})
            assert saved.status_code==200,saved.text
            result=await client.post(url+'/submit',json={'revision':saved.json()['revision'],'values':{'prompt':'user supplied panda'}})
            assert result.status_code==200,result.text
            version=value.json()['parameter_contract_version']
            assert result.json()['result']['parameter_contract_version']==version
        await wait(runtime,rid,'waiting_capability')
        approval=next(x for x in runtime.agents.list_interactions(rid) if x.status.value=='pending')
        assert approval.request['provider_binding']==[provider.capability,provider.id,provider.version,version]
        if contract_changes:
            contract['effective_schema']={**schema,'description':'Owner contract changed during approval'}
        runtime.agents.respond_interaction(rid,approval.id,response_id='form-approved',response={'decision':'approve','scope':'once'})
        runtime.agent_runtime.wake();await wait(runtime,rid,'completed')
        if contract_changes:
            assert not calls
        else:
            assert calls==[({'prompt':'user supplied panda'},sid)]
            result=next(s.output for s in runtime.agents.list_steps(rid)
                        if s.tool_name==provider.capability and s.status.value=='completed')
            assert (result['provider'],result['parameter_contract_version'])==(provider.id,version)
    finally:
        FORMS.pop(provider.id,None)
        await runtime.stop_background_tasks()


@pytest.mark.parametrize('action',['deny','revoke'])
@pytest.mark.asyncio
async def test_pending_discovery_cannot_bypass_denial_or_revocation(runtime,action):
    bot,sid,calls,provider=setup(runtime)
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        return response(provider.capability,{'prompt':'fixture'}) if any(x.get('providers') for x in results) else response('app.describe',{'capability':provider.capability})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.app_chat.submit(P(),sid,'guard-request','Create fixture','fixture')
        await wait(runtime,rid,'waiting_capability');item=runtime.agents.list_interactions(rid)[0]
        if action=='deny':
            runtime.agents.respond_interaction(rid,item.id,response_id='denied',response={'decision':'deny'})
            assert runtime.agents.get_run(rid).error['code']=='approval_denied'
        else:
            permissions=runtime.messager_bot_permissions
            permissions.save('local',bot['id'],1,[],review_hash=permissions.review_hash())
            with pytest.raises(Exception):runtime.agents.respond_interaction(rid,item.id,response_id='late',response={'decision':'approve','scope':'once'})
        assert calls==[]
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_todo_owner_resolves_directory_under_bot_scope_without_borrowing_ui_scope(runtime):
    from ai2apps.todo.aaat import store
    bot,sid,_,_=setup(runtime)
    permissions=runtime.messager_bot_permissions
    permissions.save('local',bot['id'],1,[{'id':'todo.read','foreground':True,'background':False}],review_hash=permissions.review_hash())
    runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    directory=store(runtime).directory('local','Bot owned directory')
    rid=runtime.app_chat.submit(P(),sid,'resolve-request','Find my directory','fixture')
    ctx=runtime.tools.context_for_session(caller_id='test',session_id=sid,trace_id=rid)
    result=await runtime.tools.execute('todo.resolve_directory',{'query':'Bot owned directory'},context=ctx)
    assert directory['id'] in json.dumps(result.output)

@pytest.mark.parametrize('name,app',[('fixture.paint','ai2apps.gallery'),('different.compose','ai2apps.knowledge')])
@pytest.mark.asyncio
async def test_descriptor_read_is_automatic_but_never_grants_execution(runtime,name,app):
    source=runtime.services.get_tool('capability.describe')
    instance=runtime.services.get_instance_for_service(source.service_id)
    reads=[]
    async def descriptor(args,ctx):
        reads.append(args['provider']);return {'description':'Fixture parameters'}
    runtime.service_registry.bind_tool('capability.describe',provider_key=instance.provider_key,handler=descriptor)
    bot,sid,calls,provider=setup(runtime,name,app)
    rid=runtime.app_chat.submit(P(),sid,'descriptor-request','Inspect before creating','fixture')
    ctx=runtime.tools.context_for_session(caller_id='test',session_id=sid,trace_id=rid)
    assert runtime.app_chat.authorize(ctx,'capability.describe',{'provider':provider.id}) is True
    result=await runtime.tools.execute('capability.describe',{'provider':provider.id},context=ctx)
    assert result.output['description']=='Fixture parameters' and reads==[provider.id]
    assert not runtime.agents.list_interactions(rid) and calls==[]
    assert runtime.app_chat.authorize(ctx,name,{'prompt':'fixture'}) is False
    with pytest.raises(Exception):await runtime.tools.execute(name,{'prompt':'fixture'},context=ctx)
    with pytest.raises(Exception):runtime.app_chat.authorize(ctx,'capability.describe',{'provider':'not-admitted'})
    frozen=runtime.app_chat.execution_authorization(rid)
    owner=runtime.app_chat.owners[REGISTRATION]
    with pytest.raises(PermissionError):owner.validate_authorization('local',{'bot_id':bot['id']},{**frozen,'mode':'background'},'capability.describe',{'provider':provider.id})
    runtime.app_capability_router.providers[provider.id]=replace(provider,version='changed')
    with pytest.raises(Exception):runtime.app_chat.authorize(ctx,'capability.describe',{'provider':provider.id})
    assert calls==[]

@pytest.mark.parametrize('effects,required',[(('workspace.write',),()),((),('workspace.write',))])
@pytest.mark.asyncio
async def test_descriptor_with_execution_effects_or_requirements_is_not_autoauthorized(runtime,effects,required):
    bot,sid,_,provider=setup(runtime)
    source=runtime.services.get_tool('capability.describe')
    runtime.services.ensure_tool(service_id=source.service_id,qualified_name=source.qualified_name,display_name=source.display_name,description=source.description,input_schema=source.input_schema,output_schema=source.output_schema,effects=effects,required_capabilities=required)
    rid=runtime.app_chat.submit(P(),sid,'unsafe-descriptor','Inspect parameters','fixture')
    ctx=runtime.tools.context_for_session(caller_id='test',session_id=sid,trace_id=rid)
    with pytest.raises(Exception):runtime.app_chat.authorize(ctx,'capability.describe',{'provider':provider.id})


@pytest.mark.asyncio
async def test_bot_remembers_unknown_risk_but_still_requires_app_access(runtime):
    bot, sid, calls, provider = setup(runtime)
    name = provider.capability
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE tool_descriptors SET effects_json=? WHERE qualified_name=?",
                   (json.dumps(["legacy.fixture_write"]), name))

    async def model(request):
        if request["messages"][0]["content"].startswith("Classify the risk"):
            return response(text='{"risk":"high","reason":"Unknown side effects"}')
        messages = request["messages"]
        latest_user = max(i for i, message in enumerate(messages) if message["role"] == "user")
        results = [json.loads(m["content"]) for m in messages[latest_user + 1:] if m.get("role") == "tool"]
        if any(x.get("created") == "fixture-output" for x in results):
            return response(text="Fixture complete")
        if not any(x.get("providers") for x in results):
            return response("app.describe", {"capability": name})
        return response(name, {"prompt": "fixture"})

    access = runtime.messager_bot_app_access
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        first = runtime.app_chat.submit(P(), sid, "risk-first", "Create fixture", "fixture")
        await wait(runtime, first, "waiting_capability")
        item, = runtime.agents.list_interactions(first)
        assert item.ui_hints["unknown_tool_risk"]["ai"]["risk"] == "high"
        request = access.request("local", bot["id"], first, item.id)
        assert not request["access_granted"] and request["special"]
        assert access.allow("local", bot["id"], first, item.id, request["request_hash"])["requires_confirmation"]
        runtime.agents.respond_interaction(first, item.id, response_id=item.id,
            response={"decision": "approve", "scope": "once", "remember_risk": "low"})
        runtime.agent_runtime.wake()
        await wait(runtime, first, "completed")

        second = runtime.app_chat.submit(P(), sid, "risk-second", "Create another fixture", "fixture")
        await wait(runtime, second, "completed")
        assert len(calls) == 2 and not runtime.agents.list_interactions(second)

        catalog = access.catalog("local", bot["id"])
        access.save("local", bot["id"], catalog["revision"], catalog["review_hash"], [])
        third = runtime.app_chat.submit(P(), sid, "risk-third", "Create a fixture", "fixture")
        await wait(runtime, third, "waiting_capability")
        item, = runtime.agents.list_interactions(third)
        assert "app-chat.invoke" in item.request["capabilities"]
        assert len(calls) == 2
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.parametrize('app,effects,required,expected', [
    ('ai2apps.gallery',(),(),True),
    ('ai2apps.knowledge',(),(),True),
    ('ai2apps.gallery',('workspace.write',),(),False),
    ('ai2apps.knowledge',(),('fixture.account',),False),
])
def test_access_exemption_requires_trusted_effect_free_descriptor(runtime,app,effects,required,expected):
    bot,_,_,provider=setup(runtime,'fixture.pure',app)
    tool=replace(runtime.services.get_tool(provider.capability),effects=effects,required_capabilities=required)
    runtime.services.get_tool=lambda name: tool
    access=runtime.messager_bot_app_access
    assert not access.exempt(provider)
    assert access.exempt(replace(provider,access_required=False)) is expected
    with pytest.raises(ValueError,match='effect-free'):
        runtime.app_capability_router.register(replace(provider,access_required=False,access_policy='confirm'))


@pytest.mark.asyncio
async def test_effect_free_provider_runs_without_adding_bot_app_access(runtime):
    r=runtime
    bot,sid,calls,provider=setup(r,'fixture.pure','ai2apps.knowledge')
    tool=r.services.get_tool(provider.capability)
    r.services.ensure_tool(service_id=tool.service_id,qualified_name=tool.qualified_name,
        display_name=tool.display_name,description='Compute a result from explicit input',
        input_schema=tool.input_schema,output_schema=tool.output_schema,effects=(),required_capabilities=())
    r.app_capability_router.providers.pop(provider.id)
    r.app_capability_router.register(replace(provider,access_required=False))
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created') for x in results):return response(text='Fixture complete')
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
        return response(provider.capability,{'prompt':'explicit input'})
    r.agent_runtime.bind_model_provider(model)
    await r.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=r.app_chat.submit(P(),sid,'effect-free-task','Compute a fixture answer','fixture')
        await wait(r,rid,'completed')
        assert len(calls)==1 and not r.agents.list_interactions(rid)
        assert not r.messager_bot_app_access.granted('local',bot['id'],provider)
    finally:
        await r.stop_background_tasks()


@pytest.mark.parametrize('app,capability', [('ai2apps.gallery','fixture.review'),('ai2apps.knowledge','arbitrary.inspect_review')])
@pytest.mark.asyncio
async def test_form_only_review_admission_preserves_owner_handoff(runtime,monkeypatch,app,capability):
    """Real Bot/Run/form host; owner continuation is a non-effectful fixture."""
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.agents.parameter_forms import ParameterForm,register_form,FORMS
    from ai2apps.agents.form_continuation import ADAPTERS,ContinuationAdapter
    key=app+'.review-entry';calls=[]
    def begin(*args):calls.append('review');return {'review_required':True}
    monkeypatch.setitem(ADAPTERS,key,ContinuationAdapter(begin,lambda *a:None,lambda *a:None))
    register_form(ParameterForm(key,app,{'type':'object','properties':{},'additionalProperties':False},capability=capability,continuation=key,provider_version='1'))
    try:
        bot,sid,business_calls,provider=setup(runtime)
        async def model(request):
            results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
            if not results:return response('app.describe',{'capability':capability})
            return response('app.collect_parameters',{'request_id':'review','capability':capability,'values':{}})
        runtime.agent_runtime.bind_model_provider(model)
        await runtime.start_background_tasks(retention_interval_seconds=60)
        rid=runtime.app_chat.submit(P(),sid,'form-only','Review this operation','fixture')
        await wait(runtime,rid,'waiting_input')
        item=runtime.agents.list_interactions(rid)[0]
        assert item.ui_hints['provider']==key and calls==[] and not business_calls
        assert key in runtime.app_chat.execution_authorization(rid)['discovery_forms']
        assert capability not in runtime.app_chat.execution_authorization(rid)['discovery_tools']
        api=FastAPI();api.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=P))
        url=f'/v1/platform/agent-runs/{rid}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api),base_url='http://test') as client:
            current=await client.get(url);assert current.status_code==200,current.text
            assert current.json()['can_continue_in_app']
            review=await client.post(url+'/handoff',json={'revision':current.json()['revision'],'values':{}})
            assert review.status_code==200,review.text
            assert calls==['review'] and not business_calls
            monkeypatch.setitem(FORMS,key,replace(FORMS[key],schema={'type':'object','properties':{'changed':{'type':'string'}}}))
            changed=await client.get(url)
            assert changed.status_code==403,changed.text
        context=runtime.tools.context_for_session(caller_id='test',session_id=sid,trace_id=rid)
        assert runtime.app_chat.authorize(context,provider.capability,{'prompt':'fixture'}) is False
    finally:
        FORMS.pop(key,None)
        await runtime.stop_background_tasks()


@pytest.mark.parametrize('change',['late','schema','owner','continuation','execute','unregistered','background'])
@pytest.mark.asyncio
async def test_review_form_admission_is_frozen_and_not_business_authority(runtime,monkeypatch,change):
    from ai2apps.agents.parameter_forms import ParameterForm,FORMS
    from ai2apps.agents.form_continuation import ADAPTERS,ContinuationAdapter
    from ai2apps.services import ToolAuthorizationError
    key='arbitrary.owner.review'
    form=ParameterForm(key,'ai2apps.gallery',{'type':'object','properties':{}},capability='arbitrary.review',continuation=key)
    monkeypatch.setitem(ADAPTERS,key,ContinuationAdapter(lambda *a:None,lambda *a:None,lambda *a:None))
    if change!='late':monkeypatch.setitem(FORMS,key,form)
    bot,sid,_,_=setup(runtime)
    rid=runtime.app_chat.submit(P(),sid,'pin-review','Review the requested operation','fixture')
    context=runtime.tools.context_for_session(caller_id='test',session_id=sid,trace_id=rid)
    args={'capability':form.capability,'provider':key}
    if change=='late':monkeypatch.setitem(FORMS,key,form)
    elif change=='schema':monkeypatch.setitem(FORMS,key,replace(form,schema={'type':'object','properties':{'x':{'type':'string'}}}))
    elif change=='owner':monkeypatch.setitem(FORMS,key,replace(form,app_id='ai2apps.knowledge'))
    elif change=='continuation':monkeypatch.delitem(ADAPTERS,key)
    elif change=='execute':monkeypatch.setitem(FORMS,key,replace(form,mode='execute',complete=lambda *a:None))
    elif change=='unregistered':monkeypatch.delitem(FORMS,key)
    if change=='background':
        owner=runtime.app_chat.owners[REGISTRATION]
        frozen={**runtime.app_chat.execution_authorization(rid),'mode':'background'}
        with pytest.raises(PermissionError):owner.validate_authorization('local',{'bot_id':bot['id']},frozen,'app.collect_parameters',args)
    else:
        with pytest.raises(ToolAuthorizationError) as rejected:runtime.app_chat.authorize(context,'app.collect_parameters',args)
        assert rejected.value.code==('provider_not_authorized' if change in ('late','unregistered') else 'provider_binding_changed')
        assert rejected.value.details=={'phase':'prepare','submitted':False,'side_effects':False}
