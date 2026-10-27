import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException

from ai2apps.apps import ensure_system_apps
from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.events import EventStore
from ai2apps.events.bus import EventNotificationBus
from ai2apps.extensions.manager import InteractivePackageManager
from ai2apps.identity import IdentityRepository, RequestPrincipal
from ai2apps.intelligence.collector import IntelligenceCollector
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import SessionRepository


@pytest.fixture
def collector(tmp_path,monkeypatch):
    database=PlatformDatabase(tmp_path/'platform.sqlite3');database.initialize()
    bus=EventNotificationBus();events=EventStore(database)
    runtime=NS(database=database,events=events,notifications=bus,
        config=NS(paths=NS(artifacts_path=tmp_path)),agents=NS(),knowledge=None,
        agent_runtime=NS(cancel=lambda _:None))
    principal=replace(RequestPrincipal.legacy_local(),actor_user_id='owner')
    monkeypatch.setattr(IdentityRepository,'local_principal_for',lambda self,owner:replace(principal,actor_user_id=owner))
    ensure_system_apps(database,events)
    manager=object.__new__(InteractivePackageManager)
    manager.database=database
    manager.sessions=SessionRepository(database,events)
    runtime.extension_manager=manager
    c=IntelligenceCollector(runtime)
    background=c.execution_session('owner')
    instance=manager.sessions.get(background).app_instance_id
    c.session_id=manager.sessions.create(app_instance_id=instance,title='Collection fixture').id
    return c,principal


def source_and_channel(collector,principal):
    channel=collector.store.save_channel(principal.actor_user_id,dict(name='Watches',interests='Watches',interval_hours=0))
    source=collector.store.save_source(principal.actor_user_id,channel['id'],dict(name='Example',url='https://example.com/',kind='website',enabled=True,profile_key='default'))
    return source,channel


def test_atomic_background_claim_and_no_frontend_expiry(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],c.session_id)
    assert run['execution_owner']=='local'
    with c.store.connect() as db:
        job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
        db.execute('UPDATE runs SET updated=0 WHERE id=?',(run['id'],))
    assert json.loads(job['data'])['sources'][0]['id']==s['id']
    assert job['session_id']==c.execution_session('owner')
    assert c.store.snapshot('owner')['runs'][0]['status']=='running'
    with pytest.raises(ValueError):c.submit(p,ch['id'],c.session_id)
    assert c.store.snapshot('other')['runs']==[]


def test_shared_submission_is_idempotent_and_admitted_once(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    kwargs=dict(owner='owner',session_id=c.session_id,profile='default',name='Collect',key='collection:source:phase',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}))
    one=c.invocations.submit(**kwargs)
    assert c.invocations.submit(**kwargs)['id']==one['id']
    assert len(c.tasks.list('owner'))==1
    ir,caller=c.tasks.program('owner',one['id'])
    assert ir['steps'][0]['operation']=='read_page' and caller=='ai2apps.intelligence'
    assert c.tasks.program('other',one['id'])==(None,None)
    c.tasks.enqueue('owner','default','agent','cap','gen','UI task',{})
    assert c.tasks.claim('owner','worker')['id']==one['id']
    assert c.tasks.claim('owner','worker') is None


@pytest.mark.parametrize('owner,use_existing_session',[('owner',False),('other',True)])
def test_submission_rejects_missing_or_foreign_session_before_admission(collector,owner,use_existing_session):
    c,p=collector;s,ch=source_and_channel(c,p)
    with pytest.raises(HTTPException) as error:
        c.invocations.submit(owner=owner,session_id=c.session_id if use_existing_session else 'missing-session',
            name='Denied',key='denied',caller_app_id='ai2apps.intelligence',
            source=c.program(s,'read_page',{'url':s['url']}))
    assert error.value.status_code==404
    assert error.value.detail['code']=='session_not_found'
    assert c.tasks.list('owner')==[] and c.tasks.list('other')==[]


@pytest.mark.asyncio
async def test_resumed_job_rebinds_mobile_session_before_work(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],'mobile-session')
    with c.store.connect() as db:
        db.execute("UPDATE collection_jobs SET session_id='old-mobile-session',data=json_set(data,'$.rebuild_posts',json('true'),'$.retry_pages',json(?),'$.retry_logs',json(?)) WHERE run_id=?",
                   (json.dumps([{'source_id':s['id'],'url':s['url'],'text':'saved evidence'}]),json.dumps([{'source_id':s['id'],'status':'success','pages':1}]),run['id']))
        job=dict(db.execute('SELECT * FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone())
    seen=[]
    original=c.ensure_source_nodes
    def ensure(job):
        seen.append(job['session_id'])
        original(job)
    monkeypatch.setattr(c,'ensure_source_nodes',ensure)
    async def finish(principal,channel,id,pages,logs):
        with c.store.connect() as db:
            assert db.execute('SELECT session_id FROM collection_jobs WHERE run_id=?',(id,)).fetchone()[0]==c.execution_session('owner')
        c.store.finish('owner',id,pages,[],logs)
    monkeypatch.setattr(c,'finish',finish)
    await c.collect(job)
    assert seen==[c.execution_session('owner')]
    assert c.store.get('runs','owner',run['id'])['status']=='completed'


@pytest.mark.asyncio
async def test_restart_reads_same_task_output_without_resubmission(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
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
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/story',requested_url='https://example.com/story',title='Story',text='Evidence '+('text '*100))
    async def fail(*args,**kwargs):raise ValueError('invalid model output')
    monkeypatch.setattr('ai2apps.intelligence.service.digest',fail)
    with pytest.raises(ValueError):await c.finish(p,ch,run['id'],[page],[])
    assert c.store.new_pages('owner',ch['id'],[page])
    assert c.store.snapshot('owner')['articles']==[]
    with c.store.connect() as db:
        data=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone()['data'])
    assert len(data['editorial']['pages'])==1
    assert all(data['editorial']['pages'][0][key]==value for key,value in page.items())
    assert data['editorial_context']==c.editorial_context(ch)


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
    task=c.invocations.submit(owner='owner',session_id=c.session_id,name='Legacy',key='legacy',caller_app_id='ai2apps.intelligence',agent_id='legacy',generation_id='generation')
    assert task['capability']=='agent.legacy.run'


def test_internal_program_dispatch_preserves_program_and_caller(collector,monkeypatch):
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    c,p=collector;s,ch=source_and_channel(c,p)
    source=c.program(s,'read_page',{'url':s['url']})
    task=c.invocations.submit(owner='owner',session_id=c.session_id,name='Read',key='read',caller_app_id='ai2apps.intelligence',source=source)
    calls=[]
    monkeypatch.setattr('ai2apps.agent_builder.service.create_ir_run',lambda runtime,**kw:calls.append(kw))
    runner=BackgroundBrowserRunner.__new__(BackgroundBrowserRunner)
    runner.runtime=c.runtime;runner.tasks=c.tasks;runner.worker='local-background'
    runner.dispatch_queue()
    assert len(calls)==1
    assert calls[0]['ir']['steps'][0]['operation']=='read_page'
    assert calls[0]['caller_app_id']=='ai2apps.intelligence'
    assert calls[0]['idempotency_key']==task['id']
    assert calls[0]['browser_context']['parallel_limit']==1


@pytest.mark.asyncio
async def test_background_collection_skips_known_details_before_task_submission(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p)
    urls=['https://example.com/'+str(n) for n in range(5)]
    page=dict(source_id=s['id'],url=urls[0],requested_url=urls[0],title='Known',text='Known article')
    old=c.store.claim('owner',ch['id']);c.store.finish('owner',old['id'],[page],[],[])
    run=c.submit(p,ch['id'],c.session_id)
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
    assert visits==urls[1:]
    assert len(finished[0])==4


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
        c.invocations.submit(owner='owner',session_id=c.session_id,name='Multi',key='multi',caller_app_id='ai2apps.intelligence',agent_id='multi',generation_id='generation')
    assert not c.tasks.list('owner')


def test_learned_list_must_cover_the_current_homepage():
    baseline={'items':[{'url':f'https://www.formula1.com/en/latest/article/story-{i}'} for i in range(17)]}
    assert IntelligenceCollector.list_undercovered({'items':baseline['items'][:1]},baseline)
    assert IntelligenceCollector.list_undercovered({'items':baseline['items'][:3]},baseline)
    assert not IntelligenceCollector.list_undercovered(baseline,baseline)
    assert not IntelligenceCollector.list_undercovered({'items':[]},{'items':[]})


def test_single_source_collection_is_scoped_and_preserves_schedule(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    other=c.store.save_source('owner',ch['id'],dict(name='Other',url='https://other.example/',kind='website',enabled=True,profile_key='default'))
    before=c.store.get('channels','owner',ch['id']).get('last_attempt')
    run=c.submit(p,ch['id'],c.session_id,source_id=s['id'])
    assert run['source_id']==s['id']
    with c.store.connect() as db:
        job=db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone()
    assert [v['id'] for v in json.loads(job['data'])['sources']]==[s['id']]
    assert c.store.get('channels','owner',ch['id']).get('last_attempt')==before
    c.store.progress('owner',run['id'],'done','cancelled')
    for invalid in ['missing', other['id']]:
        if invalid==other['id']:
            c.store.save_source('owner',ch['id'],{**other,'enabled':False},other['id'])
        with pytest.raises(ValueError):
            c.submit(p,ch['id'],c.session_id,source_id=invalid)


@pytest.mark.asyncio
async def test_organize_child_cannot_finish_root_before_source(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    root='collection:'+run['id']
    async def finish(*args):
        assert c.tree.get('owner',root+':organize')['status']=='running'
        assert c.tree.get('owner',root)['status']=='running'
    monkeypatch.setattr(c,'_finish',finish)
    await c.finish(p,ch,run['id'],[],[])
    assert c.tree.get('owner',root+':organize')['status']=='completed'
    assert not c.tree.finish('owner',root)


@pytest.mark.asyncio
async def test_recovery_reuses_finished_source_evidence(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    root='collection:'+run['id'];page={'url':s['url'],'text':'Saved evidence','source_id':s['id']}
    log={'source_id':s['id'],'status':'completed'}
    c.tree.finish('owner',root+':source:'+s['id'],result={'pages':[page],'log':log})
    replacement=IntelligenceCollector(c.runtime);seen=[]
    async def finish(principal,channel,id,pages,logs):
        seen.extend(pages);replacement.store.finish('owner',id,[],[],logs)
    monkeypatch.setattr(replacement,'_finish',finish)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone())
    await replacement.collect(job)
    assert seen==[page]
    assert replacement.tree.get('owner',root)['status']=='completed'


@pytest.mark.asyncio
async def test_saved_run_resumes_organize_without_digest_or_status_regression(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    c.store.finish('owner',run['id'],[],[],[])
    monkeypatch.setattr('ai2apps.intelligence.collector.service.digest',lambda *a:(_ for _ in ()).throw(AssertionError('Must not redigest saved run')))
    monkeypatch.setattr('ai2apps.intelligence.collector.knowledge_sync.sync_pending',lambda *a:None)
    c.progress('owner',run['id'],'resuming')
    assert c.store.get('runs','owner',run['id'])['status']=='completed'
    await c.finish(p,ch,run['id'],[],[])
    assert c.tree.get('owner','collection:'+run['id']+':organize')['status']=='completed'


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,values,feed_urls', [
    ('search',['F1 qualifying','McLaren'],['https://x.com/search?q=F1+qualifying&f=live','https://x.com/search?q=McLaren&f=live']),
    ('lists',['https://x.com/i/lists/123','https://twitter.com/i/lists/456?s=20'],['https://x.com/i/lists/123','https://x.com/i/lists/456']),
])
async def test_x_source_visits_all_queries_and_deduplicates_posts(collector, monkeypatch, mode, values, feed_urls):
    from ai2apps.intelligence.models import SourceInput
    c,p=collector
    ch=c.store.save_channel('owner',dict(name='Sports',interests='F1',interval_hours=0))
    data=SourceInput(name='X F1',url='https://x.com/',x_mode=mode,
                     x_values=values,profile_key='default').model_dump()
    s=c.store.save_source('owner',ch['id'],data)
    c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    visits=[];finished=[]
    async def read(job,source,key,url,**kw):
        assert source['profile_key']=='default'
        visits.append((url,kw['x']))
        if kw['x']=='feed':
            ids=['1','2'] if url==feed_urls[0] else ['2','3']
            return {'items':[dict(url='https://x.com/f1/status/'+id,post_id=id,title='F1 news') for id in ids]}
        return dict(url=url,title='F1 news',text='Visible post evidence',platform='x',content_type='post',
                    images=[dict(url='https://pbs.twimg.com/media/example.jpg')])
    async def finish(*args):finished.append(args[3])
    async def no_sleep(*args):pass
    c.read=read;c.finish=finish
    c.recipe=lambda *args:(_ for _ in ()).throw(AssertionError('X uses its bounded post extractor'))
    monkeypatch.setattr('ai2apps.intelligence.collector.asyncio.sleep',no_sleep)
    await c.collect(job)
    assert [v[0] for v in visits if v[1]=='feed']==feed_urls
    assert [v[0] for v in visits if v[1]=='detail']==['https://x.com/f1/status/'+id for id in ['1','2','3']]
    assert len(finished[0])==3 and all(page['content_type']=='post' for page in finished[0])

@pytest.mark.asyncio
async def test_x_reads_beyond_five_and_continues_after_failed_post(collector, monkeypatch):
    from ai2apps.intelligence.models import SourceInput
    c,p=collector
    ch=c.store.save_channel('owner',dict(name='Sports',interests='F1',interval_hours=0))
    c.store.save_source('owner',ch['id'],SourceInput(name='X F1',url='https://x.com/',x_mode='accounts',x_values=['F1']).model_dump())
    c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    visited=[];finished=[];active=0;peak=0
    real_sleep=asyncio.sleep
    async def read(job,source,key,url,**kw):
        nonlocal active,peak
        if kw['x']=='feed':return {'items':[dict(url=f'https://x.com/F1/status/{i}',title='News') for i in range(1,9)]}
        visited.append(url)
        active+=1;peak=max(peak,active)
        await real_sleep(.01)
        active-=1
        if url.endswith('/4'):raise RuntimeError('x_post_body_not_visible')
        return dict(url=url,title='News',text='Evidence',platform='x',content_type='post')
    async def finish(*args):finished.append((args[3],args[4]))
    async def no_sleep(*args):pass
    c.read=read;c.finish=finish
    monkeypatch.setattr('ai2apps.intelligence.collector.asyncio.sleep',no_sleep)
    await c.collect(job)
    assert len(visited)==8
    assert peak==3
    pages,logs=finished[0]
    assert len(pages)==7 and pages[-1]['url'].endswith('/8')
    assert logs[0]['agent_stats']['pending_remaining']==0
    assert len(logs[0]['agent_stats']['post_failures'])==1
    assert logs[0]['status']=='failed'

@pytest.mark.asyncio
async def test_x_rule_learning_activation_reuse_and_bounded_repair(collector,monkeypatch):
    from ai2apps.intelligence import x_agents
    from ai2apps.agent_builder.repository import AgentBuilderRepository
    from ai2apps.intelligence.models import SourceInput
    c,p=collector;c.runtime.agent_builder=AgentBuilderRepository(c.runtime.database)
    ch=c.store.save_channel('owner',dict(name='Sports',interests='F1',interval_hours=0))
    source=c.store.save_source('owner',ch['id'],SourceInput(name='X F1',url='https://x.com/',x_mode='accounts',x_values=['F1']).model_dump())
    c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    observed={f:[{'selector':s,'sample':'Post','count':1}] for f,s in [('card','article'),('link','a[href]'),('text','p'),('author','span'),('photo','img')]}
    post={'post_id':'1','url':'https://x.com/F1/status/1','text':'News','images':[]}
    calls=[];model_calls=[]
    async def model(*args,**kwargs):model_calls.append(1);return args[-1](dict.fromkeys(x_agents.FIELDS,0))
    async def browser(job,source,key,**kwargs):
        calls.append(kwargs)
        if kwargs.get('recipe') or 'validate-rule' in key:return {'items':[post],'text':'News','x_rule_valid':True}
        return {'items':[post],'text':'News','x_observed':observed,'x_rule_valid':False}
    c.browser=browser;monkeypatch.setattr(x_agents,'model_json',model)
    args={'x':'feed','url':source['url']}
    result=await c.read_x(job,source,'feed',args)
    assert result['x_rule_valid'] and len(model_calls)==1
    key=source['url']+'|x-list';record=c.store.site_recipe('owner',key)
    assert c.runtime.agent_builder.get_generation(record['generation_id'],'owner').status.value=='active'
    calls.clear()
    await c.read_x(job,source,'feed2',args)
    assert len(calls)==1 and calls[0]['recipe']['generation_id']==record['generation_id']
    assert len(model_calls)==1
    # Same-update drift does not cause unbounded AI repairs or reuse stale generations.
    async def drift(*args,**kwargs):return {'items':[post],'text':'News','x_observed':observed,'x_rule_valid':False}
    c.browser=drift
    await c.read_x(job,source,'feed3',args)
    assert c.recipe('owner',source,'x-list') is None and len(model_calls)==1


def test_live_progress_merges_and_identical_updates_do_not_emit_events(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    emitted=[];c.changed=lambda *args:emitted.append(args)
    c.progress('owner',run['id'],'reading',details={'source_name':'Example','pages_read':2,'active_pages':[{'url':s['url']}]})
    c.progress('owner',run['id'],'reading',details={'source_name':'Example','pages_read':2,'active_pages':[{'url':s['url']}]})
    assert len(emitted)==1
    c.progress('owner',run['id'],'extracted',details={'articles_extracted':1})
    progress=c.store.get('runs','owner',run['id'])['progress']
    assert progress['pages_read']==2 and progress['articles_extracted']==1


def test_manual_editorial_retry_reuses_saved_source_evidence(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/story',title='Story',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'success','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    c.store.progress('owner',run['id'],'AI failed','failed',details={'phase':'digest'})
    retry=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:
        data=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(retry['id'],)).fetchone()['data'])
    assert data['retry_pages']==[page]
    assert data['retry_logs']==[log]


def test_incremental_article_save_is_idempotent_and_does_not_commit_page(collector):
    import copy
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    article={'update_article_id':'stable','title':'Title','summary':'Summary','body':'facts [1]','sources':[{'url':'https://example.com/story','title':'Story','source_name':'s','retrieved_at':'now'}]}
    c.store.finish('owner',run['id'],[],[copy.deepcopy(article)],[],final=False)
    c.store.finish('owner',run['id'],[],[copy.deepcopy(article)],[],final=False)
    snap=c.store.snapshot('owner')
    assert len(snap['articles'])==1 and not snap['articles'][0].get('versions')
    assert c.store.get('runs','owner',run['id'])['status']=='running'
    assert c.store.new_pages('owner',ch['id'],[dict(source_id=s['id'],url='https://example.com/story',text='facts')])


def test_successful_update_prevents_reusing_an_older_failed_run(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/story',title='Story',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'success','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    c.store.progress('owner',run['id'],'AI failed','failed',details={'phase':'digest'})
    success=c.submit(p,ch['id'],c.session_id)
    c.store.finish('owner',success['id'],[page],[],[log])
    next_run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:data=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(next_run['id'],)).fetchone()['data'])
    assert 'retry_pages' not in data and data['ready']


def test_progress_stage_clock_survives_heartbeat(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    c.progress('owner',run['id'],'planning',details={'phase':'planning'})
    first=c.store.get('runs','owner',run['id'])['progress']['phase_started_at']
    c.progress('owner',run['id'],'planning',details={'phase':'planning','pages_read':2})
    assert c.store.get('runs','owner',run['id'])['progress']['phase_started_at']==first


@pytest.mark.asyncio
async def test_interrupted_source_stops_without_retry_or_wait(collector):
    from ai2apps.intelligence.collector import SourceBlocked
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    task=c.invocations.submit(owner='owner',session_id=c.session_id,profile='default',name='Collect',
        key='intelligence:'+run['id']+':'+s['id']+':list',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}))
    c.tasks.update('owner',task['id'],status='interrupted',message='navigation timeout')
    with pytest.raises(SourceBlocked,match='其它信息源继续更新'):
        await c.browser({'owner':'owner','run_id':run['id'],'session_id':c.session_id},s,'list')
    assert c.tasks.get('owner',task['id'])['status']=='cancelled'


def test_parallel_children_share_one_profile_slot_and_respect_three_tab_cap(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    c.tasks.configure('owner',1,1);c.tree.create('owner','pool-root','Pool')
    children=[c.invocations.submit(owner='owner',session_id=c.session_id,profile='default',name='Article',key=f'pool-{i}',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}),parent_task_id='pool-root',parallel_limit=3) for i in range(4)]
    assert all(c.tasks.claim('owner','worker') is not None for _ in range(3))
    assert c.tasks.claim('owner','worker') is None
    with c.runtime.database.transaction() as db:assert len(c.tasks._active_groups(db,'owner'))==1
    c.tasks.update('owner',children[0]['id'],status='failed')
    assert c.tasks.claim('owner','worker')['id']==children[3]['id']


@pytest.mark.asyncio
async def test_sources_and_articles_overlap_and_one_article_failure_isolated(collector,monkeypatch):
    import asyncio
    c,p=collector;s,ch=source_and_channel(c,p)
    c.store.save_source('owner',ch['id'],dict(name='Second',url='https://second.example/',kind='website',enabled=True,profile_key='default'))
    run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone())
    entered=[];both=asyncio.Event();inflight={};peak={};saved=[]
    async def listing(job,source,**kwargs):
        entered.append(source['id'])
        if len(entered)==2:both.set()
        await asyncio.wait_for(both.wait(),1)
        return {'items':[{'url':source['url']+str(i),'title':str(i)} for i in range(4)]}
    async def read(job,source,key,url,**kwargs):
        sid=source['id'];inflight[sid]=inflight.get(sid,0)+1;peak[sid]=max(peak.get(sid,0),inflight[sid])
        try:
            await asyncio.sleep(.01)
            if url.endswith('/1'):raise RuntimeError('single article failed')
            return {'url':url,'title':'Article','text':'Article facts'}
        finally:inflight[sid]-=1
    async def learn(*args):pass
    async def images(job,source,page,*args):return page
    async def finish(principal,channel,id,pages,logs):
        saved.extend(pages);c.store.finish('owner',id,pages,[],logs)
    monkeypatch.setattr(c,'read_list',listing);monkeypatch.setattr(c,'recipe',lambda *a:None)
    monkeypatch.setattr(c,'read',read);monkeypatch.setattr(c,'learn',learn);monkeypatch.setattr(c,'ensure_images',images);monkeypatch.setattr(c,'finish',finish)
    await c.collect(job)
    assert len(entered)==2 and sorted(peak.values())==[3,3]
    assert len(saved)==6
    assert all(log['pages']==3 for log in c.store.get('runs','owner',run['id'])['logs'])


def test_parallel_policy_survives_context_updates_and_cannot_be_forged(collector):
    c,p=collector;s,ch=source_and_channel(c,p);c.tree.create('owner','root','Pool')
    task=c.invocations.submit(owner='owner',session_id=c.session_id,name='Read',key='policy',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}),parent_task_id='root',parallel_limit=3)
    c.tasks.update('owner',task['id'],browser_context_json=json.dumps({'bidi_context':'page'}))
    assert c.tasks.get('owner',task['id'])['browser_context']['parallel_limit']==3
    c.tasks.update('owner',task['id'],browser_context_json=json.dumps({'bidi_context':'page','parallel_limit':99}))
    assert c.tasks.get('owner',task['id'])['browser_context']['parallel_limit']==3


def test_healthy_list_does_not_trigger_full_coverage_scan():
    items=[{'url':f'https://example.com/article/{i}'} for i in range(10)]
    assert not IntelligenceCollector.list_needs_check({'items':items})
    assert IntelligenceCollector.list_needs_check({'items':items[:2]})
    assert IntelligenceCollector.list_needs_check({'items':items,'extraction_fallback':'rule_drift'})

@pytest.mark.asyncio
async def test_source_list_tasks_overlap_without_losing_source_scoped_page_reuse(collector):
    c,p=collector;source,channel=source_and_channel(c,p)
    other=c.store.save_source('owner',channel['id'],dict(name='Second',url='https://second.example/',kind='website',enabled=True,profile_key='default'))
    run=c.submit(p,channel['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    pending=[asyncio.create_task(c.read_list(job,s)) for s in [source,other]]
    try:
        await asyncio.sleep(.02)
        tasks=c.tasks.list('owner')
        assert len(tasks)==2
        assert {t['browser_context']['parallel_limit'] for t in tasks}=={3}
        scopes={t['browser_context']['reuse_scope'] for t in tasks}
        assert len(scopes)==2 and '' not in scopes
        c.tasks.configure('owner',global_limit=1,profile_limit=1)
        first=c.tasks.claim('owner','worker');second=c.tasks.claim('owner','worker')
        assert first and second and first['id']!=second['id']
        assert first['root_task_id']==second['root_task_id']=='collection:'+run['id']
        # Both sources share a single Browser root/Profile admission slot.
        assert c.tasks.claim('owner','worker') is None
        for task in tasks:c.tasks.update('owner',task['id'],status='completed',run_id=task['id'])
        c.runtime.agents.get_run=lambda _:NS(output={'result':{'items':[]}})
        c.runtime.notifications.notify()
        assert await asyncio.wait_for(asyncio.gather(*pending),2)==[{'items':[]},{'items':[]}]
    finally:
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)

def test_article_pipeline_preloads_then_calls_compiled_recipe():
    from ai2apps.agent_builder.compiler import compile_source
    source={'url':'https://example.com/'}
    recipe={'draft_id':'agent','generation_id':'generation','capability':'read'}
    program=IntelligenceCollector.article_pipeline(source,None,recipe,{'url':'https://example.com/story'})
    assert program['steps'][0]['arguments']=={'url':'https://example.com/story','preload':True}
    assert program['steps'][1]['operation']=='agent.call'
    assert program['steps'][1]['arguments']['parameters']['url']=='https://example.com/story'
    compiled=compile_source(program)
    assert compiled.valid,compiled.report


@pytest.mark.asyncio
async def test_x_details_overlap_in_one_root_with_distinct_owned_pages(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    s={**s,'url':'https://x.com/OpenAI','x_mode':'accounts','x_values':['OpenAI']}
    run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    pending=[asyncio.create_task(c.browser(job,s,'article-'+str(n),program=c.program(s,'read_page',{'url':f'https://x.com/OpenAI/status/{n}','x':'detail'}))) for n in range(4)]
    try:
        await asyncio.sleep(.02)
        tasks=c.tasks.list('owner')
        assert len(tasks)==4
        assert {t['browser_context']['parallel_limit'] for t in tasks}=={3}
        assert all(not t['browser_context']['reuse_scope'] for t in tasks)
        assert {t['root_task_id'] for t in tasks}=={'collection:'+run['id']}
        c.tasks.configure('owner',global_limit=1,profile_limit=1)
        one=c.tasks.claim('owner','worker');two=c.tasks.claim('owner','worker')
        three=c.tasks.claim('owner','worker')
        assert one and two and three and len({one['id'],two['id'],three['id']})==3
        assert c.tasks.claim('owner','worker') is None
        for task in tasks:c.tasks.update('owner',task['id'],status='completed',run_id=task['id'])
        c.runtime.agents.get_run=lambda _:NS(output={'result':{'text':'Post'}})
        c.runtime.notifications.notify()
        assert await asyncio.wait_for(asyncio.gather(*pending),2)==[{'text':'Post'}]*4
    finally:
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)

@pytest.mark.asyncio
async def test_x_feed_reuses_source_page_but_detail_validation_does_not(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    s={**s,'url':'https://x.com/OpenAI','x_mode':'accounts'}
    run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    keys=['x-feed-0','article-0-validate-rule']
    pending=[asyncio.create_task(c.browser(job,s,k,program=c.program(s,'read_page',{'url':s['url']}))) for k in keys]
    try:
        await asyncio.sleep(.02)
        tasks={t['name'].split(' · ')[1]:t for t in c.tasks.list('owner')}
        assert tasks[keys[0]]['browser_context']['reuse_scope']=='collection:'+run['id']+':source:'+s['id']
        assert tasks[keys[1]]['browser_context']['reuse_scope']==''
    finally:
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)

@pytest.mark.parametrize('phase',['digest','planning','writing','saving'])
@pytest.mark.parametrize('scheduled',[False,True])
def test_editorial_recovery_supports_all_stages_and_schedule(collector,phase,scheduled):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/story',title='Story',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'success','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    c.store.progress('owner',run['id'],'AI failed','failed',details={'phase':phase})
    if scheduled:
        with c.store.connect() as db:
            row=db.execute('select data from channels where id=?',(ch['id'],)).fetchone()
            data=json.loads(row['data']);data.update(interval_hours=1,schedule_anchor=0,last_attempt=0)
            db.execute('update channels set data=? where id=?',(json.dumps(data),ch['id']))
    retry=c.submit(p,ch['id'],c.session_id,scheduled=scheduled)
    with c.store.connect() as db:data=json.loads(db.execute('select data from collection_jobs where run_id=?',(retry['id'],)).fetchone()['data'])
    assert data['retry_pages']==[page] and data['retry_from_run_id']==run['id']


def test_retry_chain_keeps_checkpoint_and_stops_after_editorial_completion(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/story',title='Story',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'success','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    with c.store.connect() as db:
        data=json.loads(db.execute('select data from collection_jobs where run_id=?',(run['id'],)).fetchone()['data'])
        data.update(editorial={'pages':[page],'state':{'plan':{'events':[]},'articles':{}}},editorial_context=c.editorial_context(ch))
        db.execute('update collection_jobs set data=? where run_id=?',(json.dumps(data),run['id']))
    c.store.progress('owner',run['id'],'AI failed','failed',details={'phase':'writing'})
    retry=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:data=json.loads(db.execute('select data from collection_jobs where run_id=?',(retry['id'],)).fetchone()['data'])
    assert data['editorial']['state']['plan']=={'events':[]}
    assert data['editorial_origin_run_id']==run['id']
    c.store.progress('owner',retry['id'],'source failed','partial',details={'phase':'saving'})
    with c.store.connect() as db:
        data['editorial_complete']=True
        db.execute('update collection_jobs set data=? where run_id=?',(json.dumps(data),retry['id']))
    next_run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:data=json.loads(db.execute('select data from collection_jobs where run_id=?',(next_run['id'],)).fetchone()['data'])
    assert 'retry_pages' not in data


def test_changed_source_does_not_reuse_cached_evidence(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/story',title='Story',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'success','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    c.store.progress('owner',run['id'],'AI failed','failed',details={'phase':'planning'})
    c.store.save_source('owner',ch['id'],dict(name='Changed',url='https://example.org/',kind='website',enabled=True,profile_key='default'),s['id'])
    retry=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:data=json.loads(db.execute('select data from collection_jobs where run_id=?',(retry['id'],)).fetchone()['data'])
    assert 'retry_pages' not in data

@pytest.mark.asyncio
async def test_legacy_learned_article_recipe_preload_compiles_without_cached_capability(collector,monkeypatch):
    from ai2apps.agent_builder.repository import AgentBuilderRepository
    from ai2apps.intelligence import site_agents
    c,p=collector;s,ch=source_and_channel(c,p)
    async def choose(*args,**kwargs):return args[-1]({'indices':[0]})
    monkeypatch.setattr(site_agents,'model_json',choose)
    c.runtime.agent_builder=AgentBuilderRepository(c.runtime.database)
    record=await site_agents.learn(c.runtime,None,p,s,site_agents.LearnRequest(kind='article',url=s['url'],regions=[{'selector':'article','sample':'Evidence','count':1}]))
    c.runtime.agent_builder.activate_generation(record['draft_id'],record['generation_id'],'owner')
    assert 'capability' not in record
    c.store.save_site_recipe('owner',site_agents.recipe_key(s,'article'),record)
    cached=c.recipe('owner',s,'article')
    run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone())
    pending=asyncio.create_task(c.browser(job,s,'article-0',recipe=cached,parameters={'url':'https://example.com/story'}))
    try:
        await asyncio.sleep(.02)
        task=c.tasks.list('owner')[0]
        ir,_=c.tasks.program('owner',task['id'])
        assert ir['steps'][0]['operation']=='open'
        assert ir['steps'][1]['operation']=='agent.call'
        assert ir['steps'][1]['arguments']['capability']==f"agent.{record['draft_id']}.run"
        assert 'capability' not in cached  # resolve without mutating old cache records
        c.tasks.update('owner',task['id'],status='completed',run_id='run')
        c.runtime.agents.get_run=lambda _:NS(output={'result':{'text':'article'}})
        c.runtime.notifications.notify()
        assert (await asyncio.wait_for(pending,2))['text']=='article'
    finally:
        pending.cancel();await asyncio.gather(pending,return_exceptions=True)


def test_article_entry_resolution_uses_owned_generation_not_cached_ir(collector):
    from ai2apps.agent_builder.compiler import COMPILER_VERSION
    c,p=collector
    generation=NS(draft_id='agent',status=NS(value='active'),compiler_version=COMPILER_VERSION,
                  ir={'capability_exports':[{'name':'read_article'}]})
    def owned(id,owner):
        if owner!='owner':raise KeyError('owner mismatch')
        return generation
    c.runtime.agent_builder=NS(get_generation=owned)
    record={'draft_id':'agent','generation_id':'generation','ir':{'capability_exports':[{'name':'untrusted_cached_name'}]}}
    resolved=c.resolve_article_recipe('owner',record)
    assert resolved['capability']=='read_article'
    with pytest.raises(KeyError):c.resolve_article_recipe('other',record)
    with pytest.raises(ValueError):c.resolve_article_recipe('owner',{**record,'draft_id':'different'})
    with pytest.raises(ValueError):c.resolve_article_recipe('owner',{**record,'capability':'missing'})
    generation.ir={'capability_exports':[{'name':'first'},{'name':'second'}]}
    with pytest.raises(ValueError):c.resolve_article_recipe('owner',record)
    assert c.resolve_article_recipe('owner',{**record,'capability':'second'})['capability']=='second'
    generation.status=NS(value='retired')
    with pytest.raises(ValueError):c.resolve_article_recipe('owner',record)


@pytest.mark.asyncio
async def test_collection_watchdog_preserves_saved_results_and_reports_phase(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    c.store.progress('owner',run['id'],'Saving',details={'phase':'writing','source_name':'Example','articles_saved':2})
    stopped=[]
    async def stuck(_):
        try:await asyncio.Event().wait()
        finally:stopped.append(True)
    class Expired:
        def __init__(self,*a):pass
        def observe(self,*a,**kw):return True
    monkeypatch.setattr(c,'collect',stuck)
    monkeypatch.setattr('ai2apps.browser.progress_watchdog.ProgressDeadline',Expired)
    c.watchdog_poll_seconds=.001
    await c.guarded_collect(job)
    result=c.store.get('runs','owner',run['id'])
    assert stopped and result['status']=='partial'
    assert result['progress']['articles_saved']==2
    assert result['progress']['stalled'] and result['progress']['timeout_seconds']==300
    assert 'writing' in result['message'] and 'Example' in result['message']


def test_progress_clock_does_not_advance_on_repeated_messages(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],c.session_id)
    c.progress('owner',run['id'],'read one',details={'pages_read':1})
    first=c.store.get('runs','owner',run['id'])['progress']['last_effective_progress_at']
    c.progress('owner',run['id'],'heartbeat changed',details={'pages_read':1,'phase':'list'})
    assert c.store.get('runs','owner',run['id'])['progress']['last_effective_progress_at']==first


def test_legacy_partial_with_all_articles_saved_is_not_editorial_retry(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/old',title='Old',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'failed','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    with c.store.connect() as db:
        j=json.loads(db.execute('select data from collection_jobs where run_id=?',(run['id'],)).fetchone()['data'])
        j['editorial']={'pages':[page],'state':{'plan':{'events':[{}]},'articles':{'0':{'title':'Saved'}}}}
        db.execute('update collection_jobs set data=? where run_id=?',(json.dumps(j),run['id']))
        r=json.loads(db.execute('select data from runs where id=?',(run['id'],)).fetchone()['data']);r.update(article_count=1,progress={'phase':'saving'})
        db.execute("update runs set status='partial',data=? where id=?",(json.dumps(r),run['id']))
    retry=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:j=json.loads(db.execute('select data from collection_jobs where run_id=?',(retry['id'],)).fetchone()['data'])
    assert 'retry_pages' not in j


@pytest.mark.asyncio
async def test_cache_recovery_continues_with_fresh_collection_in_same_root(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    old=dict(source_id=s['id'],url='https://example.com/old',title='Old',text='old facts')
    with c.store.connect() as db:
        job=dict(db.execute('select * from collection_jobs where run_id=?',(run['id'],)).fetchone())
        data=json.loads(job['data']);data.update(retry_pages=[old],retry_logs=[{'source_id':s['id'],'name':s['name'],'status':'failed','pages':1}]);job['data']=json.dumps(data)
        db.execute('update collection_jobs set data=? where run_id=?',(job['data'],run['id']))
    order=[]
    async def recover(principal,channel,id,pages,logs,**kwargs):
        assert kwargs['recovery'] is True and pages==[old] and logs==[]
        order.append('cache');c.store.finish('owner',id,pages,[],[],final=False)
        return {'pages':1,'changed':1,'articles':1}
    async def listing(*args,**kwargs):
        assert c.store.get('runs','owner',run['id'])['status']=='running'
        order.append('fresh');return {'items':[{'url':'https://example.com/new','title':'New'}]}
    async def read(*args,**kwargs):return {'url':'https://example.com/new','title':'New','text':'new facts'}
    async def no_op(*args,**kwargs):pass
    async def images(job,source,page,*args):return page
    async def finish(principal,channel,id,pages,logs):
        assert [x['url'] for x in pages]==['https://example.com/new']
        assert len(logs)==1 and logs[0]['pages']==1
        order.append('finish');c.store.finish('owner',id,pages,[],logs)
    monkeypatch.setattr(c,'_finish',recover);monkeypatch.setattr(c,'finish',finish)
    monkeypatch.setattr(c,'read_list',listing);monkeypatch.setattr(c,'read',read);monkeypatch.setattr(c,'recipe',lambda *a:None)
    monkeypatch.setattr(c,'learn',no_op);monkeypatch.setattr(c,'ensure_images',images)
    await c.collect(job)
    assert order==['cache','fresh','finish']
    result=c.store.get('runs','owner',run['id'])
    assert result['status']=='completed' and result['article_count']==1
    assert result['progress']['cached_pages']==1 and result['progress']['refresh_stage']=='fresh'
    with c.store.connect() as db:data=json.loads(db.execute('select data from collection_jobs where run_id=?',(run['id'],)).fetchone()['data'])
    assert data['recovery_complete'] and 'retry_pages' not in data and 'editorial' not in data


@pytest.mark.asyncio
async def test_cache_editorial_commits_evidence_without_finalizing_run(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    page=dict(source_id=s['id'],url='https://example.com/old',requested_url='https://example.com/old',title='Old',text='Old evidence '+('words '*40))
    async def digest(*args,**kwargs):return [{'title':'Saved cache','summary':'Summary','body':'Old evidence','sources':[]}]
    monkeypatch.setattr('ai2apps.intelligence.service.digest',digest)
    result=await c._finish(p,ch,run['id'],[page],[],recovery=True)
    assert result=={'pages':1,'changed':1,'articles':1}
    assert c.store.get('runs','owner',run['id'])['status']=='running'
    assert c.store.new_pages('owner',ch['id'],[page])==[]
    assert len(c.store.snapshot('owner')['articles'])==1


@pytest.mark.asyncio
@pytest.mark.parametrize('browser,model,expected', [
    ({'blocked':2,'running':0}, {'blocked':0,'running':0}, True),
    ({'blocked':1,'running':1}, {'blocked':0,'running':0}, False),
    ({'blocked':0,'running':0}, {'blocked':1,'running':0}, True),
    ({'blocked':1,'running':0}, {'blocked':0,'running':1}, False),
    ({'blocked':0,'running':1}, {'blocked':1,'running':0}, False),
    ({'blocked':0,'running':0}, {'blocked':0,'running':0}, False),
])
async def test_root_watchdog_pauses_only_when_all_work_is_blocked(collector, monkeypatch, browser, model, expected):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    observed=[]; finished=asyncio.Event()
    async def collect(_): await finished.wait()
    class Watch:
        def __init__(self,*a):pass
        def observe(self,*a,waiting=False):
            observed.append(waiting);finished.set();return False
    async def scoped_activity(**scope):
        assert scope==dict(actor_id='owner',app_id='ai2apps.intelligence',session_id='intelligence-'+ch['id'])
        return model
    c.runtime.worker_scheduler=NS(scoped_activity=scoped_activity)
    monkeypatch.setattr(c,'collect',collect)
    monkeypatch.setattr('ai2apps.browser.progress_watchdog.ProgressDeadline',Watch)
    monkeypatch.setattr('ai2apps.browser.progress_watchdog.browser_activity',lambda *a,**kw:browser)
    c.watchdog_poll_seconds=.001
    await c.guarded_collect(job)
    assert observed==[expected]
    assert not c.store.get('runs','owner',run['id']).get('progress',{}).get('stalled')


@pytest.mark.asyncio
async def test_system_task_owns_collection_and_manual_schedule_deduplicate(collector,monkeypatch):
    from ai2apps.system_tasks import SystemTaskService
    from ai2apps.system_tasks.intelligence import register_intelligence
    c,p=collector;s,ch=source_and_channel(c,p)
    c.runtime.intelligence_collector=c
    c.runtime.system_tasks=SystemTaskService(c.runtime)
    monkeypatch.setattr('ai2apps.apps.access.has_app_capability',lambda *a:True)
    register_intelligence(c.runtime)
    run=c.submit(p,ch['id'],c.session_id)
    assert c.submit(p,ch['id'],c.session_id)['id']==run['id']
    task=c.runtime.system_tasks.snapshot('owner')['tasks'][0]
    assert task['status']=='queued'
    with c.store.connect() as db:
        job=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(run['id'],)).fetchone()['data'])
    assert job['system_task_id']==task['id'] and job['ready']
    c.runtime.system_tasks.schedule('owner','ai2apps.intelligence','intelligence:'+ch['id'],'intelligence.refresh','Update',{'channel_id':ch['id']},next_run=1,interval_seconds=3600)
    assert c.runtime.system_tasks.start_schedule('owner','intelligence:'+ch['id'])['id']==task['id']
    called=[]
    async def collect(job):
        called.append(job['run_id'])
        c.store.progress('owner',run['id'],'Done','completed',details={'pages_read':3})
        c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'])
        c.tree.finish('owner','collection:'+run['id'])
    monkeypatch.setattr(c,'guarded_collect',collect)
    await c.runtime.system_tasks.tick()
    await asyncio.gather(*list(c.runtime.system_tasks.jobs.values()))
    assert called==[run['id']]
    final=c.runtime.system_tasks.get('owner',task['id'])
    assert final['status']=='completed'
    assert final['message']=='Done'
    assert final['progress']['pages_read']==3
    assert final['progress_snapshot']['content']['task_progress']['metrics']==[{'label':'已读取页面','value':3}]


@pytest.mark.asyncio
async def test_system_queued_collection_cancellation_updates_business_tree(collector,monkeypatch):
    from ai2apps.system_tasks import SystemTaskService
    from ai2apps.system_tasks.intelligence import register_intelligence
    c,p=collector;s,ch=source_and_channel(c,p)
    c.runtime.intelligence_collector=c;c.runtime.system_tasks=SystemTaskService(c.runtime)
    monkeypatch.setattr('ai2apps.apps.access.has_app_capability',lambda *a:True)
    register_intelligence(c.runtime)
    run=c.submit(p,ch['id'],c.session_id);task=c.runtime.system_tasks.snapshot('owner')['tasks'][0]
    c.runtime.system_tasks.cancel('owner',task['id']);await c.runtime.system_tasks.tick()
    assert c.store.get('runs','owner',run['id'])['status']=='cancelled'
    assert c.runtime.system_tasks.get('owner',task['id'])['status']=='cancelled'


def test_system_retry_preserves_single_source_scope(collector,monkeypatch):
    from ai2apps.system_tasks import SystemTaskService
    from ai2apps.system_tasks.intelligence import register_intelligence
    c,p=collector;s,ch=source_and_channel(c,p)
    c.runtime.intelligence_collector=c;c.runtime.system_tasks=SystemTaskService(c.runtime)
    monkeypatch.setattr('ai2apps.apps.access.has_app_capability',lambda *a:True)
    register_intelligence(c.runtime)
    run=c.submit(p,ch['id'],c.session_id,source_id=s['id'])
    task=c.runtime.system_tasks.snapshot('owner')['tasks'][0]
    c.runtime.system_tasks._update('owner',task['id'],{'status':'cancelled'})
    retry=c.runtime.system_tasks.start('owner',task['id'])
    assert retry['payload']['source_id']==s['id']
    assert retry['payload']['retry_run_id']==run['id']


@pytest.mark.asyncio
async def test_saved_articles_finish_without_awaiting_derived_models(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    async def digest(*args,**kwargs):
        return [{'title':'Saved','summary':'Summary','body':'Body','sources':[]}]
    async def forbidden(*args):raise AssertionError('Collection must not call derived models')
    monkeypatch.setattr('ai2apps.intelligence.collector.service.digest',digest)
    monkeypatch.setattr('ai2apps.intelligence.collector.entity_categories.organize',forbidden)
    monkeypatch.setattr('ai2apps.intelligence.collector.topics.summarize',forbidden)
    await c.finish(p,ch,run['id'],[],[])
    saved=c.store.get('runs','owner',run['id'])
    assert saved['pending_status']=='completed' and saved['article_count']==1
    with c.store.connect() as db:
        requests=[dict(r) for r in db.execute('SELECT * FROM projection_requests')]
    assert {r['kind'] for r in requests}=={'knowledge'}
    assert all(not r['dispatched'] for r in requests)
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'])
    assert c.tree.finish('owner','collection:'+run['id'])
    completed=c.store.complete_pending('owner',run['id'])
    assert completed['status']=='completed' and completed['finished_at']


@pytest.mark.asyncio
async def test_watchdog_ends_legacy_saved_but_stuck_projection(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    c.store.finish('owner',run['id'],[],[{'title':'Saved','summary':'S','body':'B','sources':[]}],[])
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    async def stuck(_):await asyncio.Event().wait()
    class Expired:
        def __init__(self,*args):pass
        def observe(self,*args,**kwargs):return True
    monkeypatch.setattr(c,'collect',stuck)
    monkeypatch.setattr('ai2apps.browser.progress_watchdog.ProgressDeadline',Expired)
    c.watchdog_poll_seconds=.001
    await c.guarded_collect(job)
    result=c.store.get('runs','owner',run['id'])
    assert result['status']=='partial' and result['progress']['stalled']
    assert len(c.store.snapshot('owner')['articles'])==1


@pytest.mark.asyncio
async def test_projection_enqueue_failure_keeps_collection_success_and_page_fingerprint(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],c.session_id)
    page={'source_id':s['id'],'url':'https://example.com/persisted','title':'Saved report','text':'Concrete new facts'}
    async def digest(*args,**kwargs):
        return [{'title':'Saved','summary':'Summary','body':'Facts [1]','sources':[{'url':page['url']}]}]
    monkeypatch.setattr('ai2apps.intelligence.collector.service.digest',digest)
    def fail(*a,**kw):raise ValueError('projection storage unavailable')
    monkeypatch.setattr('ai2apps.intelligence.projections.request',fail)
    await c.finish(p,ch,run['id'],[page],[{'source_id':s['id'],'name':'source','status':'success','pages':1}])
    assert c.store.new_pages('owner',ch['id'],[page])==[]
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'])
    assert c.tree.finish('owner','collection:'+run['id'])
    assert c.store.complete_pending('owner',run['id'])['status']=='completed'
    assert len([a for a in c.store.snapshot('owner')['articles'] if a['channel_id']==ch['id']])==1


@pytest.mark.asyncio
async def test_x_rule_activation_uses_same_dom_proof_when_live_feed_has_moved(collector,monkeypatch):
    from ai2apps.intelligence import x_agents
    from ai2apps.agent_builder.repository import AgentBuilderRepository
    from ai2apps.intelligence.models import SourceInput
    c,p=collector;c.runtime.agent_builder=AgentBuilderRepository(c.runtime.database)
    ch=c.store.save_channel('owner',dict(name='News',interests='AI',interval_hours=0))
    source=c.store.save_source('owner',ch['id'],SourceInput(name='X AI',url='https://x.com/',x_mode='accounts',x_values=['OpenAI']).model_dump())
    c.submit(p,ch['id'],c.session_id)
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    observed={f:[{'selector':s,'sample':'Post','count':1}] for f,s in [('card','article'),('link','a[href]'),('text','p'),('author','span'),('photo','img')]}
    old={'post_id':'1','url':'https://x.com/OpenAI/status/1','text':'Old feed','images':[]}
    fresh={**old,'post_id':'2','url':'https://x.com/OpenAI/status/2','text':'Fresh feed'}
    calls=[]
    async def model(*args,**kwargs):calls.append(1);assert kwargs['stage']=='x_rule';return args[-1](dict.fromkeys(x_agents.FIELDS,0))
    async def browser(job,source,key,**kwargs):
        if kwargs.get('recipe') or 'validate-rule' in key:return {'items':[fresh],'x_rule_valid':True,'x_rule_compared':True}
        return {'items':[old],'x_rule_valid':False,'x_observed':observed}
    c.browser=browser;monkeypatch.setattr(x_agents,'model_json',model)
    result=await c.read_x(job,source,'feed',{'x':'feed','url':source['url']})
    assert result['x_rule_compared']
    await c.read_x(job,source,'feed-again',{'x':'feed','url':source['url']})
    assert calls==[1]
