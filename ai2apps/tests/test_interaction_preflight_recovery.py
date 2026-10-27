import json
import pytest
from test_app_interactions import runtime,wait
from test_aaat_execution_flow import new_run,response
from ai2apps.agents.tool_recovery import recoverable

@pytest.mark.asyncio
async def test_unregistered_handoff_is_model_visible_without_opening_interaction(runtime):
    calls=[]
    async def model(request):
        calls.append(request)
        if len(calls)==1:return response('app.interact',{'request_id':'fresh','capability':'arbitrary.unregistered','parameters':{}})
        messages=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        assert messages[-1]['error']['code']=='invalid_app_interaction'
        assert messages[-1]['error']['phase']=='prepare'
        return response(text='Corrected decision; no handoff was opened.')
    runtime.agent_runtime.bind_model_provider(model)
    run=new_run(runtime,['app.interact'])
    await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'completed')
        assert len(calls)==2 and runtime.agents.list_interactions(run.id)==()
    finally:await runtime.agent_runtime.stop()

def test_interaction_correction_remains_bounded_and_prepare_only():
    assert recoverable('invalid_app_interaction',effects=(),prior_errors=0,enabled=True,preflight=True)
    assert not recoverable('invalid_app_interaction',effects=(),prior_errors=3,enabled=True,preflight=True)
    assert not recoverable('invalid_app_interaction',effects=('write',),prior_errors=0,enabled=True)
