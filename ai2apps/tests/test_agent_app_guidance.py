import pytest
from test_app_interactions import runtime, wait
from ai2apps.chat import ChatRepository
from ai2apps.agents.general import GENERAL_AGENT_INSTRUCTIONS

@pytest.mark.asyncio
async def test_general_agent_sends_app_form_guidance_with_actual_registered_tools(runtime):
    requests=[]
    async def provider(request):
        requests.append(request)
        return {'choices':[{'message':{'role':'assistant','content':'Test response'},'finish_reason':'stop'}]}
    runtime.agent_runtime.bind_model_provider(provider)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='App guidance')
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'test','prompt':'Use an installed App to complete my task'})
        runtime.agent_runtime.wake();await wait(runtime,run.id,'completed')
        request=requests[0]
        assert request['messages'][0]=={'role':'system','content':GENERAL_AGENT_INSTRUCTIONS}
        assert 'app.collect_parameters' in GENERAL_AGENT_INSTRUCTIONS
        assert 'agent.ask_user' in GENERAL_AGENT_INSTRUCTIONS
        assert 'group_photo' not in GENERAL_AGENT_INSTRUCTIONS
        tools=[x['function']['description'] for x in request['tools']]
        assert any('registered capability' in d for d in tools)
    finally:await runtime.stop_background_tasks()
