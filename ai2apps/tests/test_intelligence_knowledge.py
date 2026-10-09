from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.identity import RequestPrincipal, MemberRole
from ai2apps.storage import PlatformDatabase
from ai2apps.knowledge import KnowledgeStore, KnowledgeScope, KnowledgeConflictError
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence.models import ChannelInput, SourceInput
from ai2apps.intelligence.knowledge_sync import sync_pending, validate_buckets, APP_ID
from ai2apps.api.intelligence import create_intelligence_router


def principal(user='alice'):
    return RequestPrincipal(actor_user_id=user, installation_id='install', organization_id='org',
        billing_account_id='bill', role=MemberRole.MEMBER, membership_epoch=1)


@pytest.fixture
def env(tmp_path):
    db=PlatformDatabase(tmp_path/'platform.sqlite3');db.initialize()
    kb=KnowledgeStore(db)
    p=principal()
    store=IntelligenceStore(tmp_path/'intelligence')
    c=store.save_channel(p.actor_user_id,ChannelInput(name='腕表',interests='新品').model_dump())
    store.save_source('alice',c['id'],SourceInput(name='品牌',url='https://example.com').model_dump())
    buckets=[kb.create_bucket(p,name='专用'),kb.create_bucket(p,name='已有'),
             kb.create_bucket(p,name='共享',scope=KnowledgeScope.INSTALLATION)]
    return store,kb,p,c,buckets


def article(store,c,update=None,body='mechanical movement'):
    run=store.claim('alice',c['id'])
    store.finish('alice',run['id'],[],[dict(title='新品',summary='summary',body=body,
        sources=[{'url':'https://example.com/a','title':'original'}],update_article_id=update)],[])
    return store.snapshot('alice')['articles'][0]


def exports(store):
    with store.connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM knowledge_exports')]


def test_backfill_multibucket_updates_unlink_relink(env):
    store,kb,p,c,b=env
    a=article(store,c)
    assert not exports(store)
    store.save_channel('alice',{**c,'knowledge_bucket_ids':[x.id for x in b]},c['id'])
    assert sync_pending(store,kb,p)=={'synced':3,'failed':0}
    jobs=exports(store)
    assert len({j['item_id'] for j in jobs})==3
    items=[kb.get_item(p,j['item_id']) for j in jobs]
    assert all('https://example.com/a' in i.text and '腕表' in i.text for i in items)
    assert sync_pending(store,kb,p)=={'synced':0,'failed':0}
    assert all(kb.get_item(p,i.id).revision==1 for i in items)
    # Unlink one library: it keeps the old version while linked copies advance.
    store.save_channel('alice',{**c,'knowledge_bucket_ids':[b[0].id,b[2].id]},c['id'])
    article(store,c,a['id'],'new development')
    assert sync_pending(store,kb,p)['synced']==2
    old_job=next(j for j in jobs if j['bucket']==b[1].id)
    assert kb.get_item(p,old_job['item_id']).revision==1
    assert len(kb.search(p,'development'))==2
    store.save_channel('alice',{**c,'knowledge_bucket_ids':[x.id for x in b]},c['id'])
    assert sync_pending(store,kb,p)['synced']==1
    assert kb.get_item(p,old_job['item_id']).revision==2
    assert len(kb.search(p,'development'))==3
    store.delete('channels','alice',c['id'])
    assert not exports(store)
    assert all(kb.get_item(p,i.id) for i in items)


def test_restart_retry_after_unacknowledged_write_and_failure(env,monkeypatch):
    store,kb,p,c,b=env
    store.save_channel('alice',{**c,'knowledge_bucket_ids':[b[0].id,b[1].id]},c['id'])
    a=article(store,c)
    complete=store.complete_knowledge_job
    # Simulates a crash after the KB commit, before the outbox acknowledgement.
    monkeypatch.setattr(store,'complete_knowledge_job',lambda *args:None)
    assert sync_pending(store,kb,p)['synced']==2
    reopened=IntelligenceStore(store.root)
    assert sync_pending(reopened,kb,p)['synced']==2
    jobs=exports(reopened)
    assert len(kb.search(p,'mechanical'))==2
    assert all(kb.get_item(p,j['item_id']).revision==1 for j in jobs)
    kb.delete_bucket(p,b[0].id)
    article(reopened,c,a['id'],'changed movement')
    assert sync_pending(reopened,kb,p)=={'synced':1,'failed':1}
    assert sync_pending(reopened,kb,p)=={'synced':0,'failed':0}
    assert sync_pending(reopened,kb,p,retry=True)['failed']==1
    assert reopened.snapshot('alice')['channels'][0]['knowledge_sync']['failed']==1
    assert reopened.snapshot('alice')['runs'][0]['status']=='completed'


def test_tombstone_and_scoped_validation(env):
    store,kb,p,c,b=env
    validate_buckets(kb,p,[b[0].id])
    with pytest.raises(ValueError):validate_buckets(kb,principal('bob'),[b[0].id])
    with pytest.raises(ValueError):validate_buckets(kb,p,['missing'])
    store.save_channel('alice',{**c,'knowledge_bucket_ids':[b[0].id]},c['id'])
    a=article(store,c)
    sync_pending(store,kb,p)
    item=kb.get_item(p,exports(store)[0]['item_id'])
    with pytest.raises(KnowledgeConflictError):
        kb.update_text_item(p,item.id,expected_revision=1,title='x',text='x')
    with pytest.raises(KnowledgeConflictError):
        kb.update_text_item(p,item.id,expected_revision=1,title='x',text='x',generated_source_app_id='other')
    kb.delete_item(p,item.id,expected_revision=item.revision)
    article(store,c,a['id'],'new version')
    assert sync_pending(store,kb,p)['failed']==1
    assert not kb.search(p,'version')
    assert not store.knowledge_jobs('bob')


def test_stale_ack_does_not_lose_new_revision(env):
    store,kb,p,c,b=env
    store.save_channel('alice',{**c,'knowledge_bucket_ids':[b[0].id]},c['id'])
    a=article(store,c)
    old=store.knowledge_jobs('alice')[0]
    article(store,c,a['id'],'new version')
    store.complete_knowledge_job('alice',old,'old-id','',old['hash'])
    assert exports(store)[0]['status']=='pending'
    assert sync_pending(store,kb,p)['synced']==1


def test_api_associations_and_auto_finish(env,monkeypatch):
    store,kb,p,c,b=env
    runtime=SimpleNamespace(knowledge=kb,config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=store.root.parent)))
    runtime.intelligence_collector = SimpleNamespace(store=store)
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS collection_schedules(owner TEXT PRIMARY KEY, session_id TEXT NOT NULL)')
    monkeypatch.setattr('ai2apps.api.agent_platform._session', lambda *args: 'knowledge-test-session')
    app=FastAPI();app.include_router(create_intelligence_router(lambda:runtime,lambda:p))
    client=TestClient(app)
    article(store,c)
    assert client.put('/intelligence/channels/'+c['id'],json={'name':'腕表','interests':'新品','knowledge_bucket_ids':['missing']}).status_code==409
    result=client.put('/intelligence/channels/'+c['id'],json={'name':'腕表','interests':'新品','knowledge_bucket_ids':[b[0].id]})
    assert result.status_code==200
    assert exports(store)[0]['status']=='synced'
    # Old clients that omit association settings must preserve existing links.
    assert client.put('/intelligence/channels/'+c['id'],json={'name':'腕表','interests':'新品'}).json()['knowledge_bucket_ids']==[b[0].id]
    from ai2apps.intelligence import service
    async def digest(*args):
        return [dict(title='Another',summary='summary',body='new automatic content',sources=[])]
    monkeypatch.setattr(service,'digest',digest)
    run=store.claim(p.actor_user_id,c['id'])  # Existing pre-background run compatibility.
    assert client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':[],'logs':[]}).status_code==200
    assert len(exports(store))==2 and all(j['status']=='synced' for j in exports(store))
    assert len(client.get('/intelligence/knowledge/buckets').json()['items'])>=3
