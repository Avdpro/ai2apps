"""Planning must not rebuild all owner exports per Provider or per Tool."""
from dataclasses import replace
from time import perf_counter
import pytest
from ai2apps.agents.models import AgentExecutionContext
from ai2apps.app_chat.service import AppChatOwner,ScopedExecutor
from ai2apps.services.capability_routing import CapabilityProvider
from test_app_interactions import runtime
from test_app_chat_durable import bind_identity
from test_bot_capability_discovery import setup,P


def test_bot_catalog_queries_are_bounded_and_do_not_cache_revoked_authority(runtime,monkeypatch):
    bot,sid,_,_=setup(runtime)
    access=runtime.messager_bot_app_access
    catalog=access.catalog('local',bot['id'])
    access.save('local',bot['id'],catalog['revision'],catalog['review_hash'],[{'app_id':'ai2apps.gallery','enabled':True}])
    runtime.app_chat.open(P(), 'ai2apps.messager.bots',{'bot_id':bot['id']},{})
    rid=runtime.app_chat.submit(P(),sid,'cost','Prepare a fixture output','fixture')
    run=runtime.agents.get_run(rid);definition=runtime.agents.get_definition(run.agent_definition_id)
    context=AgentExecutionContext(definition,run,(),())
    calls={'exports':0,'identity':0,'list_tools':0,'capture':0}
    def count(obj,name,key):
        original=getattr(obj,name)
        def wrapper(*a,**k):calls[key]+=1;return original(*a,**k)
        monkeypatch.setattr(obj,name,wrapper)
    count(runtime.app_chat,'exported','exports');count(access,'identity','identity')
    count(runtime.services,'list_tools','list_tools');count(runtime.messager_bot_permissions,'capture','capture')
    executor=ScopedExecutor(runtime.app_chat)
    start=perf_counter();tools,error=executor._available_tools(context);elapsed=perf_counter()-start
    assert error is None and tools
    # A scan may read the registry once, but never recursively recapture all rights.
    assert calls['capture']==0 and calls['exports']==0,calls
    assert calls['list_tools']<=1 and calls['identity']<=len(tools),calls
    before=dict(calls)
    visible=[runtime.app_chat.provider_visible(sid,p) for p in runtime.app_capability_router.providers.values()]
    assert any(visible)
    assert calls==before,calls
    print({'tools':len(tools),'planning_seconds':round(elapsed,4),'calls':calls})
    service=runtime.messager_bot_permissions
    frozen=runtime.app_chat.execution_authorization(rid)
    c=access.catalog('local',bot['id'])
    access.save('local',bot['id'],c['revision'],c['review_hash'],[])
    with pytest.raises(PermissionError):service.validate('local',{'bot_id':bot['id']},frozen,'gallery.search',{})


@pytest.mark.parametrize('owner_id,capability',[('ai2apps.gallery','arbitrary.alpha'),('ai2apps.knowledge','different.beta')])
def test_owner_point_visibility_preserves_pin_registry_and_default_exports(runtime,owner_id,capability):
    async def handler(a,c):return {}
    p=CapabilityProvider(owner_id+'.'+capability,capability,owner_id,handler)
    runtime.app_capability_router.register(p);p=runtime.app_capability_router.providers[p.id]
    source=runtime.services.get_tool('todo.get')
    runtime.services.ensure_tool(service_id=source.service_id,qualified_name=capability,display_name='Fixture',description='Fixture',input_schema={'type':'object'},output_schema={'type':'object'},effects=())
    calls=[];visible=[True]
    def exports(scope):calls.append('exports');return (p,)
    owner=AppChatOwner('cost.'+capability,owner_id,'1',(),lambda a,s:s,lambda *a:None,{'type':'object'},exports=exports,provider_visibility=lambda s,p:visible[0])
    runtime.app_chat.register(owner);sid=runtime.app_chat.open(P(),owner.id,{},{})
    calls.clear()
    for _ in range(5):assert runtime.app_chat.provider_visible(sid,p)
    assert calls==[]
    visible[0]=False;assert not runtime.app_chat.provider_visible(sid,p)
    visible[0]=True
    changed=replace(p,version='changed');runtime.app_capability_router.providers[p.id]=changed
    assert not runtime.app_chat.provider_visible(sid,p) and not runtime.app_chat.provider_visible(sid,changed)
    # Owners without the point callback still run their original export membership policy.
    runtime.app_chat.owners[owner.id]=replace(owner,provider_visibility=None)
    assert not runtime.app_chat.provider_visible(sid,changed)
    runtime.app_capability_router.providers[p.id]=p
    assert runtime.app_chat.provider_visible(sid,p)
    runtime.app_chat.owners[owner.id]=replace(owner,provider_visibility=None,exports=lambda scope:())
    assert not runtime.app_chat.provider_visible(sid,p)


@pytest.mark.asyncio
async def test_preparing_first_model_request_uses_no_models_or_business_effects(runtime):
    from ai2apps.agents.models import ModelCallAction
    bot,sid,calls,_=setup(runtime)
    rid=runtime.app_chat.submit(P(),sid,'prepare','Create a fixture output','fixture')
    run=runtime.agents.get_run(rid)
    context=AgentExecutionContext(runtime.agents.get_definition(run.agent_definition_id),run,(),())
    start=perf_counter();action=await ScopedExecutor(runtime.app_chat)(context);elapsed=perf_counter()-start
    assert isinstance(action,ModelCallAction),action
    assert not calls
    print({'first_request_preparation_seconds':round(elapsed,4),'schemas':len(action.request.get('tools',[]))})


def test_same_capability_other_owner_is_not_preauthorized_by_one_app_grant(runtime):
    bot,sid,_,p=setup(runtime)
    other=replace(p,id='unrelated.route',app_id='ai2apps.knowledge')
    runtime.app_capability_router.register(other)
    access=runtime.messager_bot_app_access;c=access.catalog('local',bot['id'])
    access.save('local',bot['id'],c['revision'],c['review_hash'],[{'app_id':'ai2apps.gallery','enabled':True}])
    runtime.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':bot['id']},{})
    rid=runtime.app_chat.submit(P(),sid,'route','Create fixture','fixture')
    run=runtime.agents.get_run(rid);service=runtime.app_chat;binding=service.binding(sid);owner=service.owner(binding)
    assert service.validate_execution(binding,owner,run,p.capability,{'provider':p.id}) is True
    assert service.validate_execution(binding,owner,run,p.capability,{'provider':other.id}) is False
    assert service.validate_execution(binding,owner,run,p.capability,{}) is False
