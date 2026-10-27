import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace as NS
import pytest
from ai2apps.intelligence import projections, entities
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.storage import PlatformDatabase
from ai2apps.events import EventStore, EventNotificationBus
from ai2apps.system_tasks import SystemTaskService, TaskContext


@pytest.fixture
def setup(tmp_path):
    db=PlatformDatabase(tmp_path/'platform.sqlite3');db.initialize()
    runtime=NS(database=db,events=EventStore(db),notifications=EventNotificationBus(),knowledge=None)
    store=IntelligenceStore(tmp_path/'intelligence')
    runtime.intelligence_collector=NS(store=store,runtime=runtime)
    runtime.system_tasks=SystemTaskService(runtime)
    channel=store.save_channel('owner',{'name':'News','interests':'news','interval_hours':0})
    def authorize(owner,payload):store.get('channels',owner,payload['channel_id'])
    projections.register(runtime,lambda owner:NS(actor_user_id=owner),authorize)
    return runtime,store,channel['id']


def save(store,channel,id='a',body='facts'):
    article={'id':id,'channel_id':channel,'title':'Event '+id,'summary':'summary','body':body,'sources':[],
             'updated_at':datetime.now(timezone.utc).isoformat()}
    with store.connect() as db:db.execute('INSERT OR REPLACE INTO articles VALUES(?,?,?,?)',(id,'owner',channel,json.dumps(article)))
    return article


def tasks(runtime):
    with runtime.database.transaction() as db:
        return [runtime.system_tasks._decode(r) for r in db.execute('SELECT * FROM system_tasks ORDER BY created_at')]


async def execute(runtime,task):
    return await runtime.system_tasks.handlers[task['kind']].execute(TaskContext(runtime.system_tasks,task))


@pytest.mark.asyncio
async def test_outbox_dedup_survives_dispatch_failure_and_new_snapshot(setup,monkeypatch):
    r,s,c=setup;save(s,c)
    real=r.system_tasks.submit
    monkeypatch.setattr(r.system_tasks,'submit',lambda *a,**k:(_ for _ in ()).throw(ValueError('offline')))
    projections.request(r.intelligence_collector,'owner',c)
    with s.connect() as db:assert db.execute('SELECT count(*) FROM projection_requests WHERE dispatched=0').fetchone()[0]==1
    monkeypatch.setattr(r.system_tasks,'submit',real)
    projections.flush(r.intelligence_collector)
    assert len(tasks(r))==1
    projections.request(r.intelligence_collector,'owner',c)
    assert len(tasks(r))==1
    save(s,c,body='new facts')
    projections.request(r.intelligence_collector,'owner',c)
    assert len(tasks(r))==2
    with pytest.raises(KeyError):projections.request(r.intelligence_collector,'other',c)


@pytest.mark.asyncio
async def test_topic_signature_skips_repeat_and_stale_result_cannot_overwrite(setup,monkeypatch):
    r,s,c=setup;save(s,c);save(s,c,'b')
    calls=[]
    async def summarize(*args):calls.append(1);return []
    monkeypatch.setattr(projections.topics,'summarize',summarize)
    projections.request(r.intelligence_collector,'owner',c,('topics',))
    task=tasks(r)[0]
    await execute(r,task)
    await execute(r,task)
    assert len(calls)==1
    async def stale(*args):save(s,c,body='changed during model call');return []
    monkeypatch.setattr(projections.topics,'summarize',stale)
    save(s,c,body='fresh')
    with pytest.raises(ValueError,match='已变化'):await execute(r,task)
    assert s.get('channels','owner',c)['hot_topics']['items']==[]


@pytest.mark.asyncio
async def test_entity_failure_keeps_success_and_retry_skips_it(setup,monkeypatch):
    r,s,c=setup;save(s,c);save(s,c,'b')
    done=set();calls=[];fail=True
    class Repo:
        def __init__(self,*args):pass
        def pending(self,owner,articles):return [a for a in articles if a['id'] not in done]
        def ingest(self,owner,article,plan):done.add(article['id'])
        def snapshot(self,owner):return {'entities':[]}
    async def extract(runtime,request,principal,article,repo):
        calls.append(article['id'])
        if fail and article['id']=='b':raise ValueError('Quotes must be exact excerpts')
        return NS()
    monkeypatch.setattr(projections.entities,'Repository',Repo)
    monkeypatch.setattr(projections.entities,'extract_or_review',extract)
    projections.request(r.intelligence_collector,'owner',c,('entities',))
    task=tasks(r)[0]
    result=await execute(r,task)
    assert result['_status']=='partial' and done=={'a'}
    assert 'Quotes must be exact excerpts' in result['failures'][0]['error']
    fail=False
    await execute(r,task)
    assert done=={'a','b'} and calls==['a','b','b']
    await execute(r,task)
    assert calls==['a','b','b']


@pytest.mark.asyncio
async def test_cancellation_propagates_without_saving_failed_extraction(setup,monkeypatch):
    r,s,c=setup;save(s,c)
    async def cancel(*args):raise asyncio.CancelledError()
    monkeypatch.setattr(projections.entities,'extract_or_review',cancel)
    projections.request(r.intelligence_collector,'owner',c,('entities',))
    with pytest.raises(asyncio.CancelledError):await execute(r,tasks(r)[0])
    assert len(entities.Repository(s).pending('owner',projections.articles(s,'owner',c)))==1

@pytest.mark.asyncio
async def test_real_system_queue_executes_independent_tasks_and_checks_access(setup,monkeypatch):
    r,s,c=setup
    monkeypatch.setattr(projections.knowledge_sync,'sync_pending',lambda *a:None)
    projections.request(r.intelligence_collector,'owner',c)
    assert len(tasks(r))==1
    for _ in range(6):
        await r.system_tasks.tick()
        await asyncio.sleep(0)
        await asyncio.gather(*list(r.system_tasks.jobs.values()))
    jobs=tasks(r)
    assert len(jobs)==1
    assert all(t['status']=='completed' for t in jobs)
    assert {t['kind'] for t in jobs}=={'intelligence.derive.knowledge'}
    with pytest.raises(KeyError):
        r.system_tasks.submit('other','ai2apps.intelligence','intelligence.derive.entities','Forbidden',{'channel_id':c})


@pytest.mark.asyncio
async def test_legacy_automatic_entity_jobs_do_not_resume_model_work(setup,monkeypatch):
    r,s,c=setup;save(s,c)
    async def forbidden(*args):raise AssertionError('Manual action required')
    monkeypatch.setattr(projections.entities,'extract_or_review',forbidden)
    for kind in ('entities','categories','opportunities'):
        task=r.system_tasks.submit('owner','ai2apps.intelligence','intelligence.derive.'+kind,'Legacy',{'channel_id':c})
        assert (await execute(r,task))['reason']=='manual_only'
    with s.connect() as db:
        db.execute('INSERT INTO projection_requests VALUES(?,?,?,?,0)',('owner',c,'legacy','entities'))
    before=len(tasks(r));projections.flush(r.intelligence_collector)
    assert len(tasks(r))==before


def test_collection_projection_dispatch_failure_never_reopens_articles(setup,monkeypatch):
    r,s,c=setup;save(s,c)
    monkeypatch.setattr(projections,'request',lambda *a,**kw:(_ for _ in ()).throw(ValueError('outbox unavailable')))
    projections.after_collection(r.intelligence_collector,'owner',c)
    assert len(projections.articles(s,'owner',c))==1
