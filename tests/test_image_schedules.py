import asyncio
import json
from types import SimpleNamespace as NS
import pytest
from ai2apps.events import EventNotificationBus
from ai2apps.system_tasks import SystemTaskService
from ai2apps.studio.image_schedules import ImageWorkflowSchedules,Recipe,ScheduleSettings
from ai2apps.studio.repository import StudioRepository
from test_studio_extended_jobs import setup,png
from test_studio_background_jobs import principal


def spec(iterations=1):
    return Recipe(system='Owner instructions',instruction='Prepare two images and a label',context={'style':'fixture'},
        source_path=['resources','r'],memory_field='history',memory_keys=['label'],
        data_schema={'type':'object','additionalProperties':False,'properties':{'label':{'type':'string'}},'required':['label']},
        model='fixture/image',size='1024x1024',step_count=2,iterations=iterations)


@pytest.fixture(params=[('vendor.alpha','alpha.images'),('vendor.beta','beta.pages')])
def env(tmp_path,monkeypatch,request):
    provider,mini=request.param;m,app,scope,run=setup(tmp_path,mini=mini);r=m.runtime
    r.notifications=EventNotificationBus();r.model_manager=NS(resolve_default_model=lambda *a,**k:'fixture/text')
    clock=[1000.];r.system_tasks=SystemTaskService(r,clock=lambda:clock[0]);service=ImageWorkflowSchedules(r);r.image_workflow_schedules=service
    binding={'provider':provider,'provider_instance':app,'digest':'fixture-digest','mini_id':mini,'version':'1',
        'owner':'owner','installation':'installation','scope':scope}
    allowed=[True]
    r.extension_manager.list_studio_mini_apps=lambda *a,**k:[{'id':mini,'provider':{'appId':provider,'digest':'fixture-digest'},
        'requirements':{'capabilities':['image.workflow','llm.text','image.workflow.schedule']}}] if allowed[0] else []
    monkeypatch.setattr('ai2apps.studio.image_schedules.execution_principal',lambda runtime,owner:principal(owner))
    async def models(*a):return {'items':[{'id':'fixture/image','ready':True,'referenceLimit':4,'qualities':['auto'],'formats':['png'],
        'size':{'mode':'fixed','presets':['1024x1024']}}]}
    monkeypatch.setattr('ai2apps.studio.image_schedules.model_catalog',models)
    monkeypatch.setattr('ai2apps.studio.image_workflow.model_catalog',models)
    StudioRepository(m.database).save_draft(**scope,mini_app_id=mini,draft={'resources':[{'id':'r','history':[{'label':'before'}]}]})
    return NS(manager=m,runtime=r,service=service,system=r.system_tasks,binding=binding,clock=clock,allowed=allowed)


async def wait(env,task):
    for _ in range(600):
        current=env.system.get('owner',task['id'])
        if current['status'] in ('completed','failed','partial','cancelled'):return current
        await asyncio.sleep(.01)
    pytest.fail(str(env.system.get('owner',task['id'])))


async def configure(env,recipe=None):
    return await env.service.configure(env.binding,'r',ScheduleSettings(enabled=True,name='Fixture',next_run=1100.,
        interval_seconds=3600,recipe=recipe or spec()))


async def test_default_manual_and_disabling_preserves_no_execution(env):
    assert env.service.snapshot(env.binding,'r')=={'enabled':False,'results':[]}
    assert not env.system.snapshot('owner')['schedules']
    enabled=await configure(env)
    assert enabled['enabled']==1
    await env.service.configure(env.binding,'r',ScheduleSettings())
    assert not env.system.snapshot('owner')['schedules']
    env.clock[0]=10000;await env.system.tick()
    assert not env.system.snapshot('owner')['tasks']


async def test_real_clock_batch_memory_and_no_duplicate_replay(env,monkeypatch):
    prompts=[];images=[]
    async def text(saved,actor,prompt,key):
        prompts.append(json.loads(prompt));return json.dumps({'title':'page '+str(len(prompts)),
            'steps':[{'prompt':'image one','caption':'a','references':[]},{'prompt':'image two','caption':'b','references':[]}],
            'data':{'label':'new '+str(len(prompts))}})
    async def generate(*a,**k):images.append(1);return png(),{}
    monkeypatch.setattr(env.service,'text',text);monkeypatch.setattr('ai2apps.studio.image_workflow.generate_image',generate)
    accepted=await configure(env,spec(2));env.clock[0]=1101
    await env.manager.startup()
    try:
        await env.system.tick();task=env.system.get('owner',env.service.snapshot(env.binding,'r')['last_task_id'])
        result=await wait(env,task);assert result['status']=='completed',result
        snapshot=env.service.snapshot(env.binding,'r');assert len(snapshot['results'])==2
        assert len(images)==4 and len(prompts)==2
        assert prompts[0]['recent']==[{'label':'before'}]
        assert {'label':'new 1'} in prompts[1]['recent']
        assert snapshot['next_run']==4700
        assert env.system.start_schedule('owner',accepted['id'])['trigger']=='manual'
    finally:await env.system.shutdown();await env.manager.shutdown()


async def test_permission_rechecked_at_trigger_and_unknown_text_not_replayed(env,monkeypatch):
    accepted=await configure(env);env.allowed[0]=False
    env.clock[0]=1101;await env.system.tick()
    assert not env.system.snapshot('owner')['tasks']
    assert env.service.snapshot(env.binding,'r')['error']
    env.allowed[0]=True
    task=env.system.start_schedule('owner',accepted['id'])
    env.system._update('owner',task['id'],{'checkpoint_json':json.dumps({'items':[{'id':'a'*32,'text_submitted':True}]})})
    async def forbidden(*a):pytest.fail('must not replay uncertain text call')
    monkeypatch.setattr(env.service,'text',forbidden)
    await env.system.tick();result=await wait(env,task)
    assert result['status']=='failed' and 'uncertain' in result['message']
    await env.system.shutdown()


async def test_recipe_bounds_and_owner_isolation(env):
    accepted=await configure(env)
    with pytest.raises(KeyError):env.service.row('other',accepted['id'])
    with pytest.raises(ValueError):Recipe.model_validate({**spec().model_dump(),'iterations':6})
    with pytest.raises(ValueError):Recipe.model_validate({**spec().model_dump(),'data_schema':{'type':'object','$ref':'https://example.com/schema'}})
    with pytest.raises(ValueError):await env.service.configure(env.binding,'r',ScheduleSettings(enabled=True,next_run=1000.,recipe=spec()))


async def test_completed_checkpoint_recovery_keeps_same_images_and_records(env,monkeypatch):
    text_calls=[];image_calls=[]
    async def text(*a):text_calls.append(1);return json.dumps({'title':'Resume','steps':[{'prompt':'one'},{'prompt':'two'}],'data':{'label':'saved'}})
    async def image(*a,**k):image_calls.append(1);return png(),{}
    monkeypatch.setattr(env.service,'text',text);monkeypatch.setattr('ai2apps.studio.image_workflow.generate_image',image)
    accepted=await configure(env);task=env.system.start_schedule('owner',accepted['id'])
    await env.manager.startup()
    try:
        await env.system.tick();assert (await wait(env,task))['status']=='completed'
        original=env.service.snapshot(env.binding,'r')['results']
        # Crash-window fixture: business receipt committed before parent terminal state.
        env.system._update('owner',task['id'],{'status':'running'})
        await env.system.startup();assert (await wait(env,task))['status']=='completed'
        assert len(text_calls)==1 and len(image_calls)==2
        assert env.service.snapshot(env.binding,'r')['results']==original
    finally:await env.system.shutdown();await env.manager.shutdown()
