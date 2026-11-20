"""Real General/Router model loop; visual ownership uses two arbitrary providers."""
import pytest
from PIL import Image
from ai2apps.services.aaat import AgentResultPolicy
from test_app_interactions import runtime


@pytest.mark.asyncio
@pytest.mark.parametrize('capability',['arbitrary.visual_read','independent.page_review'])
async def test_harness_visual_projection_reaches_real_general_loop_for_unrelated_owners(runtime,tmp_path,capability):
    from test_aaat_execution_flow import register, new_run, response
    from test_app_interactions import wait
    image=tmp_path/'visual.png';Image.new('RGB',(64,32),'red').save(image)
    selected=[];calls=[]
    async def execute(args,context):return {'image_id':selected[0]}
    register(runtime,capability,execute)
    runtime.app_capability_router.register_result_policy(AgentResultPolicy('visual-fixture',lambda s:None,
        lambda c,s:(c,None),capabilities=(capability,),visual_inputs=lambda s:[s.output['image_id']]))
    run=new_run(runtime,[capability])
    selected.append(runtime.workspace.import_artifact(run.session_id,image,name='visual.png',run_id=run.id).id)
    async def model(request):
        calls.append(request)
        if len(calls)<=2:return response(capability,{'query':'inspect'})
        images=[part for m in request['messages'] if isinstance(m.get('content'),list) for part in m['content'] if part.get('type')=='image_url']
        assert len(images)==1 and images[0]['image_url']['url'].startswith('data:image/jpeg;base64,')
        return response(text='Verified the red image fixture.')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'completed')
        assert len(calls)==3
    finally:await runtime.agent_runtime.stop()
