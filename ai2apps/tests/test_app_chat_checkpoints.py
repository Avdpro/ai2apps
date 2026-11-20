"""Generic owner checkpoints work across unrelated providers, without business names."""
import pytest
from ai2apps.app_chat.service import AppChatOwner
from ai2apps.agents.context_selection import CONTEXT_SELECTION
from ai2apps.agents.models import CompleteAction, ModelCallAction
from ai2apps.services.capability_routing import CapabilityProvider
from test_app_chat_durable import bind_identity,response,P
from test_app_interactions import runtime,wait

@pytest.mark.parametrize('app,capability',[('ai2apps.knowledge','unrelated.inspect'),('ai2apps.gallery','arbitrary.lookup')])
@pytest.mark.parametrize('context_rounds',[0, 2])
@pytest.mark.asyncio
async def test_committed_owner_checkpoint_stops_next_model_round(runtime,app,capability,context_rounds):
    calls=[];models=[]
    async def handler(args,ctx):calls.append(ctx.session_id);return {'stored_checkpoint':True}
    p=CapabilityProvider(capability+'.owner',capability,app,handler);runtime.app_capability_router.register(p)
    source=runtime.services.get_tool('todo.get');instance=runtime.services.get_instance_for_service(source.service_id)
    runtime.services.ensure_tool(service_id=source.service_id,qualified_name=capability,display_name='Fixture',description='fixture',input_schema={'type':'object'},output_schema={'type':'object'},effects=(),required_capabilities=())
    async def invoke(a,c):return await runtime.app_capability_router.invoke(capability,a,c)
    runtime.service_registry.bind_tool(capability,provider_key=instance.provider_key,handler=invoke)
    def checkpoint(binding,ctx):
        if any(s.kind=='tool' and s.status.value=='completed' and (s.output or {}).get('stored_checkpoint') for s in ctx.steps):return CompleteAction({'content':'Owner retained logical continuation'})
    def select(ctx, *, read=True):
        for offset in range(context_rounds):
            key=f'{CONTEXT_SELECTION}:fixture-{offset}'
            if ctx.step(key) is None:
                return ModelCallAction(key, {'model':'fixture','messages':[{'role':'user','content':key}]}),None
        return None,{'role':'user','content':'Owner projected supporting context'}
    runtime.app_chat.register(AppChatOwner(capability,app,'1',(capability,),lambda a,s:s,lambda *a:None,{'type':'object'},execution_checkpoint=checkpoint,approval_scopes=lambda scope:('once',),select_model_context=select if context_rounds else None))
    sid=runtime.app_chat.open(P(),capability,{}, {})
    assert runtime.app_chat.approval_scopes(sid)==('once',)
    async def model(request):
        models.append(request)
        messages=request['messages']
        if messages[0]['content'].startswith(CONTEXT_SELECTION):
            return response(text='Internal choice must not be replayed')
        assert not any(m.get('content')=='Internal choice must not be replayed' for m in messages)
        if context_rounds:
            assert any(m.get('content')=='Owner projected supporting context' for m in messages)
        return response(capability,{})
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        rid=runtime.app_chat.submit(P(),sid,'checkpoint-input','Inspect','fixture');run=await wait(runtime,rid,'completed')
        assert len(calls)==1 and len(models)==context_rounds+1
        assert run.output['content']=='Owner retained logical continuation'
    finally:await runtime.agent_runtime.stop()
