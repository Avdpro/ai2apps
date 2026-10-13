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
    async def fail(*args,**kwargs):raise ValueError('invalid model output')
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
    assert calls[0]['browser_context']['parallel_limit']==1


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
        c.invocations.submit(owner='owner',session_id='session',name='Multi',key='multi',caller_app_id='ai2apps.intelligence',agent_id='multi',generation_id='generation')
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
    run=c.submit(p,ch['id'],'session',source_id=s['id'])
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
            c.submit(p,ch['id'],'session',source_id=invalid)


@pytest.mark.asyncio
async def test_organize_child_cannot_finish_root_before_source(collector,monkeypatch):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
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
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
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
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
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
    c.submit(p,ch['id'],'session')
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
    c.submit(p,ch['id'],'session')
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    visited=[];finished=[]
    async def read(job,source,key,url,**kw):
        if kw['x']=='feed':return {'items':[dict(url=f'https://x.com/F1/status/{i}',title='News') for i in range(1,9)]}
        visited.append(url)
        if url.endswith('/4'):raise RuntimeError('x_post_body_not_visible')
        return dict(url=url,title='News',text='Evidence',platform='x',content_type='post')
    async def finish(*args):finished.append((args[3],args[4]))
    async def no_sleep(*args):pass
    c.read=read;c.finish=finish
    monkeypatch.setattr('ai2apps.intelligence.collector.asyncio.sleep',no_sleep)
    await c.collect(job)
    assert len(visited)==8
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
    c.submit(p,ch['id'],'session')
    with c.store.connect() as db:job=dict(db.execute('SELECT * FROM collection_jobs').fetchone())
    observed={f:[{'selector':s,'sample':'Post','count':1}] for f,s in [('card','article'),('link','a[href]'),('text','p'),('author','span'),('photo','img')]}
    post={'post_id':'1','url':'https://x.com/F1/status/1','text':'News','images':[]}
    calls=[];model_calls=[]
    async def model(*args):model_calls.append(1);return args[-1](dict.fromkeys(x_agents.FIELDS,0))
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
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
    emitted=[];c.changed=lambda *args:emitted.append(args)
    c.progress('owner',run['id'],'reading',details={'source_name':'Example','pages_read':2,'active_pages':[{'url':s['url']}]})
    c.progress('owner',run['id'],'reading',details={'source_name':'Example','pages_read':2,'active_pages':[{'url':s['url']}]})
    assert len(emitted)==1
    c.progress('owner',run['id'],'extracted',details={'articles_extracted':1})
    progress=c.store.get('runs','owner',run['id'])['progress']
    assert progress['pages_read']==2 and progress['articles_extracted']==1


def test_manual_editorial_retry_reuses_saved_source_evidence(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],'session')
    page=dict(source_id=s['id'],url='https://example.com/story',title='Story',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'success','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    c.store.progress('owner',run['id'],'AI failed','failed',details={'phase':'digest'})
    retry=c.submit(p,ch['id'],'session')
    with c.store.connect() as db:
        data=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(retry['id'],)).fetchone()['data'])
    assert data['retry_pages']==[page]
    assert data['retry_logs']==[log]


def test_incremental_article_save_is_idempotent_and_does_not_commit_page(collector):
    import copy
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
    article={'update_article_id':'stable','title':'Title','summary':'Summary','body':'facts [1]','sources':[{'url':'https://example.com/story','title':'Story','source_name':'s','retrieved_at':'now'}]}
    c.store.finish('owner',run['id'],[],[copy.deepcopy(article)],[],final=False)
    c.store.finish('owner',run['id'],[],[copy.deepcopy(article)],[],final=False)
    snap=c.store.snapshot('owner')
    assert len(snap['articles'])==1 and not snap['articles'][0].get('versions')
    assert c.store.get('runs','owner',run['id'])['status']=='running'
    assert c.store.new_pages('owner',ch['id'],[dict(source_id=s['id'],url='https://example.com/story',text='facts')])


def test_successful_update_prevents_reusing_an_older_failed_run(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    run=c.submit(p,ch['id'],'session')
    page=dict(source_id=s['id'],url='https://example.com/story',title='Story',text='facts')
    log={'source_id':s['id'],'name':s['name'],'status':'success','pages':1}
    c.tree.finish('owner','collection:'+run['id']+':source:'+s['id'],result={'pages':[page],'log':log})
    c.store.progress('owner',run['id'],'AI failed','failed',details={'phase':'digest'})
    success=c.submit(p,ch['id'],'session')
    c.store.finish('owner',success['id'],[page],[],[log])
    next_run=c.submit(p,ch['id'],'session')
    with c.store.connect() as db:data=json.loads(db.execute('SELECT data FROM collection_jobs WHERE run_id=?',(next_run['id'],)).fetchone()['data'])
    assert 'retry_pages' not in data and data['ready']


def test_progress_stage_clock_survives_heartbeat(collector):
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
    c.progress('owner',run['id'],'planning',details={'phase':'planning'})
    first=c.store.get('runs','owner',run['id'])['progress']['phase_started_at']
    c.progress('owner',run['id'],'planning',details={'phase':'planning','pages_read':2})
    assert c.store.get('runs','owner',run['id'])['progress']['phase_started_at']==first


@pytest.mark.asyncio
async def test_interrupted_source_stops_without_retry_or_wait(collector):
    from ai2apps.intelligence.collector import SourceBlocked
    c,p=collector;s,ch=source_and_channel(c,p);run=c.submit(p,ch['id'],'session')
    task=c.invocations.submit(owner='owner',session_id='session',profile='default',name='Collect',
        key='intelligence:'+run['id']+':'+s['id']+':list',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}))
    c.tasks.update('owner',task['id'],status='interrupted',message='navigation timeout')
    with pytest.raises(SourceBlocked,match='其它信息源继续更新'):
        await c.browser({'owner':'owner','run_id':run['id'],'session_id':'session'},s,'list')
    assert c.tasks.get('owner',task['id'])['status']=='cancelled'


def test_parallel_children_share_one_profile_slot_and_respect_three_tab_cap(collector):
    c,p=collector;s,ch=source_and_channel(c,p)
    c.tasks.configure('owner',1,1);c.tree.create('owner','pool-root','Pool')
    children=[c.invocations.submit(owner='owner',session_id='session',profile='default',name='Article',key=f'pool-{i}',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}),parent_task_id='pool-root',parallel_limit=3) for i in range(4)]
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
    run=c.submit(p,ch['id'],'session')
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
    task=c.invocations.submit(owner='owner',session_id='session',name='Read',key='policy',caller_app_id='ai2apps.intelligence',source=c.program(s,'read_page',{'url':s['url']}),parent_task_id='root',parallel_limit=3)
    c.tasks.update('owner',task['id'],browser_context_json=json.dumps({'bidi_context':'page'}))
    assert c.tasks.get('owner',task['id'])['browser_context']['parallel_limit']==3
    c.tasks.update('owner',task['id'],browser_context_json=json.dumps({'bidi_context':'page','parallel_limit':99}))
    assert c.tasks.get('owner',task['id'])['browser_context']['parallel_limit']==3


def test_healthy_list_does_not_trigger_full_coverage_scan():
    items=[{'url':f'https://example.com/article/{i}'} for i in range(10)]
    assert not IntelligenceCollector.list_needs_check({'items':items})
    assert IntelligenceCollector.list_needs_check({'items':items[:2]})
    assert IntelligenceCollector.list_needs_check({'items':items,'extraction_fallback':'rule_drift'})
