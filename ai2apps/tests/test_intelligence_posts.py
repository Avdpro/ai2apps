import json
import pytest
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence import posts
from ai2apps.intelligence.models import PlannedEvent

def test_post_archive_promotion_is_owner_scoped_and_idempotent(tmp_path):
    store=IntelligenceStore(tmp_path);channel=store.save_channel('owner',{'name':'AI','interests':'AI','interval_hours':0})
    page={'url':'https://x.com/example/status/123','title':'Original announcement','text':'A short but important original statement.','platform':'x','author':'Example','retrieved_at':'2026-10-15','source_name':'X'}
    with store.connect() as db:db.execute('INSERT INTO pages VALUES(?,?,?,?,?)',('owner',channel['id'],page['url'],'hash',json.dumps(page)))
    result=posts.list_posts(store,'owner',channel['id']);item=result['items'][0]
    assert item['role']=='supplementary' and item['text']==page['text']
    with pytest.raises((KeyError,ValueError)):posts.list_posts(store,'other',channel['id'])
    one=posts.promote(store,'owner',channel['id'],item['id']);two=posts.promote(store,'owner',channel['id'],item['id'])
    assert one['id']==two['id'] and one['body']==page['text']
    assert one['manual_post_promotion'] and len(store.snapshot('owner')['articles'])==1
    assert posts.list_posts(store,'owner',channel['id'])['items'][0]['briefings'][0]['id']==one['id']
    with pytest.raises(KeyError):posts.promote(store,'owner',channel['id'],'missing')

def test_event_plan_keeps_supporting_evidence_separate():
    event=PlannedEvent(title='Release',evidence_ids=[1,2],supporting_evidence_ids=[2])
    assert event.presentation=='event' and event.supporting_evidence_ids==[2]

@pytest.mark.asyncio
async def test_x_digest_merges_event_preserves_support_and_keeps_uncited_posts(monkeypatch):
    from ai2apps.intelligence import service
    pages=[{'url':f'https://x.com/ai/status/{i}','title':'Release','text':text,'platform':'x','author':'AI team','source_name':'X','retrieved_at':'now'} for i,text in enumerate(['Original new model announcement','Related reaction, an opinion','Minor contextual post'])]
    async def model(runtime,request,principal,id,instruction,data,validate,**kw):
        if kw['stage']=='event_plan':
            assert 'default to ONE briefing' in instruction
            assert data['evidence'][0]['platform']=='x'
            return validate({'events':[{'title':'Model release','evidence_ids':[1,2],'supporting_evidence_ids':[2]}]})
        return validate({'articles':[{'title':'Model release','summary':'One event','body':'Official statement [1]','evidence_ids':[1]}]})
    monkeypatch.setattr(service,'model_json',model)
    result=await service.digest(None,None,None,{'id':'c'},pages,[])
    assert len(result)==1
    assert [p['role'] for p in result[0]['post_evidence']]==['primary','supplementary']
    assert result[0]['post_evidence'][1]['text']==pages[1]['text']
    assert not result.failed_urls  # Unpromoted evidence remains eligible for storage.

@pytest.mark.asyncio
async def test_explicit_regroup_preserves_existing_article_identity(monkeypatch):
    from ai2apps.intelligence import service
    page={'url':'https://x.com/team/status/1','title':'Official release','text':'Official model announcement','platform':'x','source_name':'X','retrieved_at':'now'}
    async def model(runtime,request,principal,id,instruction,data,validate,**kw):
        if kw['stage']=='event_plan':return validate({'events':[{'title':'Official release','evidence_ids':[1],'presentation':'important_post','importance_reason':'Original model release','update_article_id':'existing'}]})
        return validate({'articles':[{'title':'Official release','summary':'Release','body':'Official model announcement [1]','evidence_ids':[1],'update_article_id':'existing'}]})
    monkeypatch.setattr(service,'model_json',model)
    result=await service.digest(None,None,None,{'id':'c'},[page],[{'id':'existing','title':'Official release'}],rebuild=True)
    assert result[0]['update_article_id']=='existing'
    assert result[0]['presentation']=='important_post'
    assert result[0]['post_evidence'][0]['text']==page['text']
