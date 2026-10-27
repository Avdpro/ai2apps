import asyncio
from types import SimpleNamespace
import pytest
from test_system_tasks import service
from ai2apps.system_tasks import TaskHandler, TaskContext


@pytest.mark.asyncio
@pytest.mark.parametrize('app',['arbitrary.one','package.two'])
async def test_task_center_and_aaat_observe_the_same_owner_snapshot(service,app):
    gate=asyncio.Event();seen=asyncio.Event();updates=[]
    def view(task):
        return {'text':task['message'] or task['name'],'phase':'owner-stage',
                'content':{'task_progress':{'metrics':[{'label':'Units','value':task['progress'].get('units',0)}]}}}
    async def execute(ctx):
        ctx.report(state='waiting_resource',message='Waiting for resource',progress={'units':2})
        await gate.wait();return {'_status':'partial','done':1}
    service.register('fixture',TaskHandler(app,execute,progress_view=view))
    task=service.submit('alice',app,'fixture','Work',{})
    await service.tick();await asyncio.sleep(0)
    async def report(**update):updates.append(update);seen.set()
    context=SimpleNamespace(actor_user_id='alice',session_id='session',installation_id='install',report_progress=report)
    observer=asyncio.create_task(service.follow('alice',task['id'],context,app_id=app,timeout=5))
    try:
        await asyncio.wait_for(seen.wait(),2)
        current=service.get('alice',task['id'])
        assert current['progress_snapshot']==updates[-1]
        assert service.snapshot('alice')['tasks'][0]['progress_snapshot']==updates[-1]
        assert updates[-1]['content']['task_progress']['requires_user'] is False
        assert updates[-1]['content']['task_progress']['state']=='waiting'
        assert updates[-1]['content']['task_progress']['metrics'][0]['value']==2
        gate.set();final=await observer
        assert final['status']=='partial'
        assert updates[-1]['content']['task_progress']['state']=='partial'
        TaskContext(service,final).report(message='stale',progress={'units':999})
        assert service.get('alice',task['id'])['status']=='partial'
        assert service.get('alice',task['id'])['message']!='stale'
        with pytest.raises(PermissionError):await service.follow('bob',task['id'],context,app_id=app)
        with pytest.raises(PermissionError):await service.follow('alice',task['id'],context,app_id='other')
    finally:
        gate.set();await asyncio.gather(*service.jobs.values(),return_exceptions=True)


@pytest.mark.asyncio
async def test_observer_cancellation_does_not_cancel_the_business_task(service):
    gate=asyncio.Event();seen=asyncio.Event()
    async def execute(ctx):await gate.wait();return {}
    service.register('fixture',TaskHandler('app',execute))
    task=service.submit('alice','app','fixture','Work',{})
    await service.tick();await asyncio.sleep(0)
    async def report(**update):seen.set()
    ctx=SimpleNamespace(actor_user_id='alice',session_id='session',installation_id='install',report_progress=report)
    observing=asyncio.create_task(service.follow('alice',task['id'],ctx,app_id='app'))
    try:
        await seen.wait();observing.cancel()
        with pytest.raises(asyncio.CancelledError):await observing
        assert service.get('alice',task['id'])['status']=='running'
    finally:gate.set();await asyncio.gather(*service.jobs.values(),return_exceptions=True)


def test_invalid_owner_view_cannot_block_task_status_or_cancellation(service):
    async def execute(ctx):return {}
    service.register('fixture',TaskHandler('app',execute,progress_view=lambda task:{
        'text':'broken','content':{'task_progress':{'metrics':[{'label':'bad','value':-3}]}}}))
    task=service.submit('alice','app','fixture','Work',{})
    assert task['progress_snapshot']['content']['task_progress']['metrics']==[]
    service.cancel('alice',task['id'])
    assert service.get('alice',task['id'])['status']=='cancelled'
