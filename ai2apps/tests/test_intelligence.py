"""Core isolation, schedule and evidence regression tests for Intelligence Center."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from ai2apps.intelligence.models import ChannelInput, SourceInput, public_url
from ai2apps.intelligence.store import IntelligenceStore


@pytest.fixture
def data(tmp_path):
    store=IntelligenceStore(tmp_path)
    channel=store.save_channel('alice',ChannelInput(name='腕表',interests='新品',interval_hours=1).model_dump())
    source=store.save_source('alice',channel['id'],SourceInput(name='品牌',url='https://example.com/news').model_dump())
    return store,channel,source


def test_owner_isolation(data):
    store,c,s=data
    assert not store.snapshot('bob')['channels']
    for table,id in [('channels',c['id']),('sources',s['id'])]:
        with pytest.raises(KeyError):store.get(table,'bob',id)
    with pytest.raises(KeyError):store.save_source('bob',c['id'],{'url':'https://example.org/'})
    with pytest.raises(KeyError):store.claim('bob',c['id'])


def test_atomic_claim_and_schedule(data):
    store,c,s=data
    with pytest.raises(ValueError):store.claim('alice',c['id'],True)
    def claim(_):
        try:return store.claim('alice',c['id'])
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs=list(pool.map(claim,range(4)))
    assert sum(bool(r) for r in runs)==1
    run=next(r for r in runs if r)
    store.progress('alice',run['id'],'done','failed')
    assert store.claim('alice',c['id'])['status']=='running'


def test_incremental_commit_and_retry(data):
    store,c,s=data
    page={'source_id':s['id'],'url':'https://example.com/new','title':'新品','text':'本次发布全新机芯。'}
    assert len(store.new_pages('alice',c['id'],[page,page]))==1
    run=store.claim('alice',c['id'])
    store.progress('alice',run['id'],'model error','failed')
    assert len(store.new_pages('alice',c['id'],[page]))==1
    run=store.claim('alice',c['id'])
    pages=store.new_pages('alice',c['id'],[page])
    article={'title':'新品','summary':'发布机芯','body':'新品信息 [1]','sources':[{'url':page['url']}],'update_article_id':None}
    store.finish('alice',run['id'],pages,[article],[{'status':'success','pages':1}])
    assert not store.new_pages('alice',c['id'],[page])
    assert len(store.new_pages('alice',c['id'],[{**page,'text':'新增售价和发售日期。'}]))==1
    with pytest.raises(ValueError):store.finish('alice',run['id'],[],[],[])


def test_updates_preserve_history_and_reset_unread(data):
    store,c,s=data
    article={'title':'新品','summary':'一代','body':'第一版 [1]','sources':[],'update_article_id':None}
    run=store.claim('alice',c['id']);store.finish('alice',run['id'],[],[article],[])
    old=store.snapshot('alice')['articles'][0]
    store.feedback('alice',old['id'],'more',True)
    run=store.claim('alice',c['id']);store.finish('alice',run['id'],[],[{**article,'body':'新增进展 [1]','update_article_id':old['id']}],[])
    changed=store.snapshot('alice')['articles'][0]
    assert changed['feedback']=='more' and not changed['read']
    assert changed['versions'][0]['body']=='第一版 [1]'
    assert changed['created_at']==old['created_at']


def test_cross_channel_evidence_rejected(data):
    store,c,s=data
    other=store.save_channel('alice',ChannelInput(name='摄影',interests='相机').model_dump())
    with pytest.raises(KeyError):store.new_pages('alice',other['id'],[{'source_id':s['id'],'url':s['url'],'text':'a'}])
    with pytest.raises(ValueError):store.save_source('alice',other['id'],s,s['id'])


def test_expire_and_partial_status(data):
    store,c,s=data
    run=store.claim('alice',c['id'])
    with store.connect() as db:db.execute('UPDATE runs SET updated=0 WHERE id=?',(run['id'],))
    assert store.snapshot('alice')['runs'][0]['status']=='interrupted'
    with pytest.raises(ValueError):store.progress('alice',run['id'],'late')
    run=store.claim('alice',c['id']);store.finish('alice',run['id'],[],[],[{'status':'needs_user','pages':0}])
    assert store.snapshot('alice')['runs'][0]['status']=='failed'


def test_no_delete_running_and_duplicate_source(data):
    store,c,s=data
    with pytest.raises(ValueError):store.save_source('alice',c['id'],s)
    run=store.claim('alice',c['id'])
    with pytest.raises(ValueError):store.delete('channels','alice',c['id'])
    with pytest.raises(ValueError):store.delete('sources','alice',s['id'])
    store.progress('alice',run['id'],'stop','cancelled')
    store.delete('channels','alice',c['id'])
    assert not any(store.snapshot('alice').values())


@pytest.mark.parametrize('url',['file:///tmp/a','http://127.0.0.1/','http://10.0.0.1','http://localhost','http://[::1]','https://user:pass@example.com','https://example.com:8080','http://test.local'])
def test_public_url_rejects_private(url):
    with pytest.raises(ValueError):public_url(url)


def test_canonical_urls_and_inputs():
    assert public_url('https://example.com/news?q=watch&utm_source=x#top')=='https://example.com/news?q=watch'
    with pytest.raises(ValueError):ChannelInput(name=' ',interests='test')
    with pytest.raises(ValueError):ChannelInput(name='x',interests='test',interval_hours=2)


def test_legacy_sections_atomic_preserve_article_state_and_owner(data):
    store,c,s=data
    run=store.claim('alice',c['id'])
    store.finish('alice',run['id'],[],[{'title':'新品','summary':'一代','body':'原文 [1]','sources':[]}],[])
    article=store.snapshot('alice')['articles'][0]
    store.feedback('alice',article['id'],'more',True)
    sections=[{'id':'s','name':'新品发布','description':'新品与发布'}]
    with pytest.raises(KeyError):store.initialize_sections('bob',c['id'],sections,{},[])
    run=store.claim('alice',c['id'])
    with pytest.raises(ValueError):store.initialize_sections('alice',c['id'],sections,{article['id']:'s'},[article])
    assert not store.get('channels','alice',c['id']).get('sections')
    store.progress('alice',run['id'],'done','failed')
    store.initialize_sections('alice',c['id'],sections,{article['id']:'s'},[article])
    result=store.get('articles','alice',article['id'])
    assert result['section_id']=='s' and result['read'] and result['feedback']=='more'
    assert result['body']==article['body'] and result['updated_at']==article['updated_at']
    with pytest.raises(ValueError):store.initialize_sections('alice',c['id'],sections,{},[])
