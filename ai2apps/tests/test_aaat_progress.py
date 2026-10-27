import asyncio
from types import SimpleNamespace
import pytest
from ai2apps.services.models import validate_progress_update
from test_aaat_execution_flow import runtime, new_run, register, response, wait


def snapshot(state='running'):
    return {'schema':'ai2apps.task-progress/v1','state':state,'stage':'arbitrary-stage',
        'task_id':'owner-task','requires_user':False,'metrics':[{'label':'Processed','value':3,'total':9}]}


@pytest.mark.parametrize('change',[
    {'progress':float('nan')}, {'progress':1.1},
    {'content':{'task_progress':{**snapshot(), 'metrics':[{'label':'bad','value':-1}]}}},
    {'content':{'task_progress':{'schema':'ai2apps.task-progress/v1','state':'waiting'}}},
    {'content':{'task_progress':{**snapshot(),'execute':'hidden-action'}}},
])
def test_invalid_progress_is_rejected(change):
    with pytest.raises(ValueError):validate_progress_update({'text':'working',**change})


@pytest.mark.asyncio
@pytest.mark.parametrize('capability',['fixture.alpha','package.other'])
async def test_owner_snapshot_persists_and_late_progress_cannot_overwrite_terminal(runtime,capability):
    sent=asyncio.Event();release=asyncio.Event()
    async def handler(args,context):
        await context.report_progress('Owner stage',content={'task_progress':snapshot()})
        sent.set();await release.wait();return {'done':True}
    register(runtime,capability,handler)
    async def model(request):
        if any(m.get('role')=='tool' and '"done": true' in m.get('content','') for m in request['messages']):return response(text='done')
        return response(capability)
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,[capability]);runtime.agent_runtime.wake()
        await asyncio.wait_for(sent.wait(),10)
        line=runtime.agents.get_status_line(run.id)
        assert line.content['task_progress']==snapshot()
        assert line.revision>0
        release.set();await wait(runtime,run.id,'completed')
        final=runtime.agents.get_status_line(run.id)
        late=runtime.agents.update_status_line(run.id,phase='old',text='late')
        assert late==final
    finally:release.set();await runtime.stop_background_tasks()


def test_owner_stage_projections_keep_counts_and_waiting_semantics():
    from ai2apps.browser.shopping import history_progress_view as task_progress
    from ai2apps.intelligence.aaat import refresh_progress
    task={'id':'private-task','status':'waiting_input','requires_user':False,
          'progress':{'phase':'order_details','current':3,'total':9}}
    update=task_progress(task);validate_progress_update(update)
    assert update['content']['task_progress']['state']=='running'
    assert update['content']['task_progress']['metrics'][0]['value']==3
    assert 'Web Reader' not in update['text']
    task['requires_user']=True
    assert task_progress(task)['content']['task_progress']['state']=='waiting'
    news=refresh_progress({'id':'news-run','status':'running','message':'正在保存',
        'progress':{'phase':'digest','articles_saved':2,'pages_read':5}})
    validate_progress_update(news)
    assert news['content']['task_progress']['metrics']==[
        {'label':'已读取页面','value':5},{'label':'已保存情报','value':2}]


def test_news_refresh_receipt_survives_terminal_and_rejects_changed_channel(tmp_path):
    from ai2apps.intelligence.store import IntelligenceStore
    store=IntelligenceStore(tmp_path)
    a=store.save_channel('owner',{'name':'one','interval_hours':0})
    b=store.save_channel('owner',{'name':'two','interval_hours':0})
    store.save_source('owner',a['id'],{'name':'source','url':'https://example.com','kind':'website','enabled':True})
    run=store.claim('owner',a['id'],request_key='one-call')
    store.progress('owner',run['id'],'done','completed')
    assert store.claim('owner',a['id'],request_key='one-call')['id']==run['id']
    with pytest.raises(ValueError,match='parameters changed'):store.claim('owner',b['id'],request_key='one-call')
    with pytest.raises(KeyError):store.claim('another',a['id'],request_key='one-call')


@pytest.mark.asyncio
@pytest.mark.parametrize('mini',['package.alpha','package.beta'])
@pytest.mark.parametrize('requires_user',[False,True])
async def test_browser_waiter_forwards_owner_snapshot_and_real_identity(mini,requires_user):
    from contextlib import asynccontextmanager
    import time
    from ai2apps.research.mini_apps import wait_task
    seen=[]
    @asynccontextmanager
    async def subscribe():
        q=asyncio.Queue();q.put_nowait(None);q.put_nowait(None);yield q
    tasks=iter([{'id':'task','status':'waiting_input','requires_user':requires_user,'message':'Owner requests inspection; no retry','name':'Owner task'},
                {'id':'task','status':'waiting_input','requires_user':requires_user,'message':'Owner requests inspection; no retry','name':'Owner task'},
                {'id':'task','status':'completed','name':'Owner task'}])
    def read(mounted,principal,identifier):
        assert principal.actor_user_id=='alice' and identifier=='task'
        return next(tasks)
    async def report(text,**rest):
        update={'text':text,**rest};validate_progress_update(update);seen.append(update)
    rt=SimpleNamespace(notifications=SimpleNamespace(subscribe=subscribe))
    result=await wait_task(rt,SimpleNamespace(task_declared=read),SimpleNamespace(declaration={'id':mini}),
        SimpleNamespace(actor_user_id='alice'),{'id':'task'},SimpleNamespace(report_progress=report),time.monotonic()+5)
    assert result['status']=='completed'
    assert len(seen)==2  # Repeated source snapshots must not feed back through notifications.
    assert seen[0]['content']['task_progress']['state']=='waiting'
    assert seen[0]['content']['task_progress']['requires_user'] is requires_user
    assert seen[0]['content']['task_progress']['wait_reason']=='Owner requests inspection; no retry'
    assert seen[-1]['content']['mini_app_id']==mini
    assert seen[-1]['content']['task_progress']['state']=='completed'


@pytest.mark.asyncio
async def test_news_refresh_uses_existing_collector_and_forwards_partial_snapshot(monkeypatch):
    from contextlib import asynccontextmanager
    from ai2apps.intelligence import aaat
    calls=[];updates=[]
    principal=SimpleNamespace(actor_user_id='owner')
    monkeypatch.setattr(aaat,'principal_for',lambda *a:principal)
    states=iter([{'id':'collection','status':'running','message':'reading','progress':{'pages_read':2}},
                 {'id':'collection','status':'partial','message':'one source failed','article_count':1}])
    def submit(actor,channel,**kw):
        assert actor is principal and channel=='channel'
        calls.append(kw);return {'id':'collection','request_key':kw['request_key']}
    @asynccontextmanager
    async def subscribe():
        q=asyncio.Queue();q.put_nowait(None);yield q
    async def report(**update):validate_progress_update(update);updates.append(update)
    from contextlib import contextmanager
    import json
    @contextmanager
    def connect():
        yield SimpleNamespace(execute=lambda *a:SimpleNamespace(fetchone=lambda:{'data':json.dumps({'system_task_id':'system-task'})}))
    async def follow(owner,identifier,context,**kwargs):
        assert owner=='owner' and identifier=='system-task' and kwargs['app_id']==aaat.APP
        for run in states:
            await context.report_progress(**aaat.refresh_progress(run))
        return {'status':'partial','message':'one source failed'}
    collector=SimpleNamespace(submit=submit,store=SimpleNamespace(connect=connect,get=lambda *a:{'id':'collection','article_count':1},article_cards=lambda owner,channel:{'items':[{'id':'article','title':'Saved article'}]}))
    runtime=SimpleNamespace(intelligence_collector=collector,system_tasks=SimpleNamespace(follow=follow))
    result=await aaat.refresh(runtime,{'channel_id':'channel'},SimpleNamespace(invocation_id='invoke',session_id='session',report_progress=report))
    assert len(calls)==1 and calls[0]['request_key']=='aaat:session:invoke'
    assert updates[0]['content']['task_progress']['metrics']==[{'label':'已读取页面','value':2}]
    assert updates[-1]['content']['task_progress']['state']=='partial'
    assert result['status']=='partial' and result['aaat_context']['coverage']['collection_status']=='partial'

    assert result['aaat_view']['layout']=='cards' and result['aaat_view']['items'][0]['id']=='article'
    assert 'partial' in result['aaat_view']['summary'] and '此前记录' in result['aaat_view']['summary']


@pytest.mark.asyncio
@pytest.mark.parametrize('mini',['arbitrary.package.alpha','arbitrary.package.beta'])
async def test_terminal_partial_survives_waiter(mini):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    import time
    from ai2apps.research.mini_apps import wait_task
    updates=[]
    @asynccontextmanager
    async def subscribe():yield None
    task={'id':'partial-task','status':'completed','result':{},'progress_snapshot':{'text':'One item unavailable; others verified','content':{'task_progress':{'state':'partial'}}}}
    async def report(text,**kw):updates.append(kw)
    await wait_task(SimpleNamespace(notifications=SimpleNamespace(subscribe=subscribe)),SimpleNamespace(task_declared=lambda *a:task),SimpleNamespace(declaration={'id':mini}),SimpleNamespace(actor_user_id='owner'),task,SimpleNamespace(report_progress=report),time.monotonic()+1)
    assert updates[-1]['content']['task_progress']['state']=='partial'
