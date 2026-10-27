import pytest
from test_app_interactions import runtime, wait
from ai2apps.chat import ChatRepository

@pytest.mark.asyncio
@pytest.mark.parametrize('options,meter,expected', [({},None,8192),({'max_tokens':4096},None,4096),({'max_completion_tokens':6000},None,6000),({},2048,2048)])
async def test_agent_output_budget(runtime,options,meter,expected):
    seen=[]
    async def provider(request):
        seen.append(request)
        return {'choices':[{'message':{'role':'assistant','content':'Partial output'},'finish_reason':'length'}]}
    runtime.agent_runtime.bind_model_provider(provider)
    if meter:
        runtime.agent_runtime.bind_context_provider(lambda request,owner:{'capacity':32768,'input_tokens':500,'output_reservation':meter})
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Output budget')
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'test','prompt':'Write a briefing','model_options':options})
        runtime.agent_runtime.wake()
        result=await wait(runtime,run.id,'completed')
        assert seen[0].get('max_completion_tokens',seen[0].get('max_tokens'))==expected
        if 'max_completion_tokens' in options: assert 'max_tokens' not in seen[0]
        assert result.output['finish_reason']=='length'
        assert result.output['content']=='Partial output'
    finally:
        await runtime.stop_background_tasks()
