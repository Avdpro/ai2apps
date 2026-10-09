import asyncio
import json
from types import SimpleNamespace as NS
import pytest
from ai2apps.storage import PlatformDatabase
from ai2apps.events import EventStore
from ai2apps.events.bus import EventNotificationBus
from ai2apps.intelligence.collector import IntelligenceCollector
from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.identity import IdentityRepository


@pytest.fixture
def collector(tmp_path,monkeypatch):
    database=PlatformDatabase(tmp_path/'platform.sqlite3');database.initialize()
    bus=EventNotificationBus();events=EventStore(database)
    runtime=NS(database=database,events=events,notifications=bus,
        config=NS(paths=NS(artifacts_path=tmp_path)),agents=NS(),knowledge=None,
        agent_runtime=NS(cancel=lambda _:None))
    principal=NS(actor_user_id='owner')
    monkeypatch.setattr(IdentityRepository,'local_principal_for',lambda self,owner:NS(actor_user_id=owner))
    monkeypatch.setattr('ai2apps.api.ownership.authorize_session',lambda *a:None)
    return IntelligenceCollector(runtime),principal


def source_and_channel(collector,principal):
    channel=collector.store.save_channel(principal.actor_user_id,dict(name='Watches',interests='Watches',interval_hours=0))
    source=collector.store.save_source(principal.actor_user_id,channel['id'],dict(name='Example',url='https://example.com/',kind='website',enabled=True,profile_key='default'))
    return source,channel


def test_atomic_background_claim_and_no_frontend_expiry(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],'session')
    assert run['execution_owner']=='local'
    with c.store.connect() as db:
        job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
        db.execute('UPDATE runs SET updated=0 WHERE id=?',(run['id'],))
    assert json.loads(job['data'])['sources'][0]['id']==s['id']
    assert c.store.snapshot('owner')['runs'][0]['status']=='running'
    with pytest.raises(ValueError):c.submit(p,ch['id'],'session')
    assert c.store.snapshot('other')['runs']==[]


def test_shared_submission_is_idempotent_and_admitted_once(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    kwargs=dict(owner='owner',session_id='session',profile='default',name='Collect',key='collection:source:phase',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}))
    one=c.invocations.submit(**kwargs)
    assert c.invocations.submit(**kwargs)['id']==one['id']
    assert len(c.tasks.list('owner'))==1
    ir,caller=c.tasks.program('owner',one['id'])
    assert ir['steps'][0]['operation']=='read_page' and caller=='ai2apps.intelligence'
    assert c.tasks.program('other',one['id'])==(None,None)
    c.tasks.enqueue('owner','default','agent','cap','gen','UI task',{})
    assert c.tasks.claim('owner','worker')['id']==one['id']
    assert c.tasks.claim('owner','worker') is None


@pytest.mark.asyncio
async def test_restart_reads_same_task_output_without_resubmission(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    program=c.program(s,'read_page',{'url':s['url']})
    pending=asyncio.create_task(c.browser(job,s,'landing',program=program))
    await asyncio.sleep(.02)
    task=c.tasks.list('owner')[0]
    c.tasks.update('owner',task['id'],status='completed',run_id='run')
    c.runtime.agents.get_run=lambda _:NS(output={'result':{'url':s['url'],'text':'article'}})
    c.runtime.notifications.notify()
    assert (await asyncio.wait_for(pending,2))['text']=='article'
    replacement=IntelligenceCollector(c.runtime)
    replacement.invocations.submit=lambda **kw:(_ for _ in ()).throw(AssertionError('Must not resubmit'))
    assert (await replacement.browser(job,s,'landing',program=program))['text']=='article'
    assert len(c.tasks.list('owner'))==1


@pytest.mark.asyncio
async def test_failed_editorial_does_not_commit_fingerprint(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
    page=dict(source_id=s['id'],url='https://example.com/story',requested_url='https://example.com/story',title='Story',text='Evidence '+('text '*100))
    async def fail(*args):raise ValueError('invalid model output')
    monkeypatch.setattr('ai2apps.intelligence.service.digest',fail)
    with pytest.raises(ValueError):await c.finish(p,ch,run['id'],[page],[])
    assert c.store.new_pages('owner',ch['id'],[page])
    assert c.store.snapshot('owner')['articles']==[]


@pytest.mark.asyncio
async def test_background_model_does_not_require_http_request(collector,monkeypatch):
    c,p=collector
    from ai2apps.intelligence.service import model_json
    calls=[]
    async def invoke(*args,**kwargs):
        calls.append(kwargs['context'])
        return NS(status_code=200,body=json.dumps({'choices':[{'message':{'content':'{"ok":true}'}}]}).encode())
    c.runtime.model_manager=NS(resolve_default_model=lambda _: 'model')
    c.runtime.model_invocations=NS(model=lambda _:NS(id='model',endpoints=['chat_completions']),
        context_for_actor=lambda actor,**kw:dict(actor=actor,**kw),invoke_background_json=invoke)
    result=await model_json(c.runtime,None,p,'channel','Return ok',{},lambda x:x)
    assert result=={'ok':True}
    assert calls[0]['actor']=='owner' and calls[0]['consumer_app_id']=='ai2apps.intelligence'


def test_frontend_only_submits_and_observes():
    from pathlib import Path
    script=(Path(__file__).parents[1]/'web/static/js/intelligence.js').read_text()
    collect=script.split('async function collect(')[1].split("$('#collect').onclick")[0]
    assert 'browserSession' not in collect and '/finish' not in collect
    assert 'EventSource' in script and 'async function tick' not in script
    assert '需保持此页面打开' not in script


def test_legacy_generation_gets_callable_capability(collector):
    c,p=collector
    c.runtime.agent_builder=NS(get_generation=lambda *a:NS(draft_id='legacy',status=NS(value='active'),ir={}))
    task=c.invocations.submit(owner='owner',session_id='session',name='Legacy',key='legacy',caller_app_id='ai2apps.intelligence',agent_id='legacy',generation_id='generation')
    assert task['capability']=='agent.legacy.run'


def test_internal_program_dispatch_preserves_program_and_caller(collector,monkeypatch):
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    c,p=collector;s,ch=source_and_channel(c,p)
    source=c.program(s,'read_page',{'url':s['url']})
    task=c.invocations.submit(owner='owner',session_id='session',name='Read',key='read',caller_app_id='ai2apps.intelligence',source=source)
    calls=[]
    monkeypatch.setattr('ai2apps.agent_builder.service.create_ir_run',lambda runtime,**kw:calls.append(kw))
    runner=BackgroundBrowserRunner.__new__(BackgroundBrowserRunner)
    runner.runtime=c.runtime;runner.tasks=c.tasks;runner.worker='local-background'
    runner.dispatch_queue()
    assert len(calls)==1
    assert calls[0]['ir']['steps'][0]['operation']=='read_page'
    assert calls[0]['caller_app_id']=='ai2apps.intelligence'
    assert calls[0]['idempotency_key']==task['id']


@pytest.mark.asyncio
async def test_background_collection_skips_known_details_before_task_submission(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p)
    urls=['https://example.com/'+str(n) for n in range(5)]
    page=dict(source_id=s['id'],url=urls[0],requested_url=urls[0],title='Known',text='Known article')
    old=c.store.claim('owner',ch['id']);c.store.finish('owner',old['id'],[page],[],[])
    run=c.submit(p,ch['id'],'session')
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    visits=[];finished=[]
    c.recipe=lambda *a:None
    async def read(job,source,key,url,**kw):
        visits.append(url);return dict(url=url,title='Article',text='Evidence '+('word '*100),
                                      images=[{'url':'https://example.com/image.jpg'}])
    async def browser(*a,**kw):return {'items':[dict(url=u,title='Story') for u in urls]}
    async def noop(*a,**kw):pass
    async def finish(*args):finished.append(args[3])
    c.read=read;c.browser=browser;c.learn=noop;c.finish=finish
    await c.collect(job)
    assert visits==urls[1:4]
    assert len(finished[0])==3


@pytest.mark.asyncio
async def test_background_cloud_route_uses_actor_invocation(collector):
    from ai2apps.intelligence.service import model_json
    c,p=collector;calls=[]
    async def invoke(payload,**kw):
        calls.append(kw['context']);return {'choices':[{'message':{'content':'{"ok":true}'}}]}
    c.runtime.model_manager=NS(resolve_default_model=lambda _:'cloud/provider/model')
    c.runtime.model_invocations=NS(model=lambda _:None,context_for_actor=lambda actor,**kw:dict(actor=actor,**kw),invoke_agent_cloud_json=invoke)
    assert await model_json(c.runtime,None,p,'channel','Return ok',{},lambda x:x)=={'ok':True}
    assert calls[0]['actor']=='owner'


def test_multi_capability_submission_requires_selection(collector):
    c,p=collector
    c.runtime.agent_builder=NS(get_generation=lambda *a:NS(draft_id='multi',status=NS(value='active'),ir={'capability_exports':[{'name':'read'},{'name':'write'}]}))
    with pytest.raises(ValueError,match='explicit'):
        c.invocations.submit(owner='owner',session_id='session',name='Multi',key='multi',caller_app_id='ai2apps.intelligence',agent_id='multi',generation_id='generation')
    assert not c.tasks.list('owner')
