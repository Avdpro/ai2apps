from datetime import datetime,timedelta,timezone
import json
import pytest
from ai2apps.intelligence import topics, service
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence.models import ChannelInput


def articles():
    return [{'id':str(i),'title':'Model X '+str(i),'summary':'release','body':'same model','updated_at':datetime.now(timezone.utc).isoformat()} for i in range(3)]


@pytest.mark.asyncio
async def test_topics_validate_evidence_and_concrete_groups(monkeypatch):
    data=articles()
    async def model(*args):
        validate=args[-1]
        with pytest.raises(ValueError):validate({'topics':[{'anchor':'Model X','title':'x','summary':'s','article_ids':['0','foreign']}]})
        with pytest.raises(ValueError):validate({'topics':[{'anchor':'Model X','title':'x','summary':'s','article_ids':['0','0']}]})
        with pytest.raises(ValueError):validate({'topics':[{'anchor':'Model X','title':'x','summary':'s','article_ids':['0']}]})
        with pytest.raises(ValueError):validate({'topics':[{'anchor':'Model X','title':'x','summary':'s','article_ids':['0','1']},{'anchor':'Model X','title':'y','summary':'s','article_ids':['1','0']}]})
        with pytest.raises(ValueError):validate({'topics':[{'anchor':'Another model','title':'bad','summary':'s','article_ids':['0','1']}]})
        return validate({'topics':[{'anchor':'Model X','title':'Model X 发布','summary':'发布与评测','article_ids':['0','1']}]})
    monkeypatch.setattr(service,'model_json',model)
    result=await topics.summarize(None,None,None,{'id':'c','name':'AI','interests':'models'},data)
    assert result[0]['article_ids']==['1','0']
    assert await topics.summarize(None,None,None,{},[])==[]


def test_recent_window_and_signature():
    data=articles()
    old={**data[0],'id':'old','updated_at':(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()}
    assert len(topics.recent(data+[old]))==3
    assert len(topics.recent([{**data[0],'id':str(i)} for i in range(100)]))==60
    assert topics.signature(data)!=topics.signature([{**data[0],'body':'changed'},*data[1:]])


def test_transaction_rejects_stale_results_and_preserves_settings(tmp_path):
    store=IntelligenceStore(tmp_path);c=store.save_channel('a',ChannelInput(name='AI',interests='models').model_dump())
    data=articles()
    with store.connect() as db:
        for a in data:db.execute('INSERT INTO articles VALUES(?,?,?,?)',(a['id'],'a',c['id'],json.dumps(a)))
    digest=topics.signature(topics.recent(data))
    store.save_topics('a',c['id'],digest,[{'title':'Model X'}])
    assert store.get('channels','a',c['id'])['name']=='AI'
    with pytest.raises(KeyError):store.save_topics('b',c['id'],digest,[])
    with pytest.raises(ValueError):store.save_topics('a',c['id'],'outdated',[])
    assert store.get('channels','a',c['id'])['hot_topics']['items'][0]['title']=='Model X'


@pytest.mark.asyncio
async def test_automatic_topics_opt_in_daily_budget_and_manual_override(tmp_path,monkeypatch):
    from types import SimpleNamespace as NS
    import time
    store=IntelligenceStore(tmp_path);owner='owner';principal=NS(actor_user_id=owner)
    channel=store.save_channel(owner,ChannelInput(name='AI',interests='models').model_dump());id=channel['id']
    data=articles()
    with store.connect() as db:
        for a in data:db.execute('INSERT INTO articles VALUES(?,?,?,?)',(a['id'],owner,id,json.dumps(a)))
    calls=[]
    async def summarize(*args):calls.append(1);return []
    monkeypatch.setattr(topics,'summarize',summarize)
    assert (await topics.refresh(None,None,principal,store,id,automatic=True))['skipped']
    assert not calls
    # Manual use remains available with the option disabled.
    await topics.refresh(None,None,principal,store,id)
    assert len(calls)==1
    store.save_channel(owner,{'auto_topics':True},id)
    with store.connect() as db:
        db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps({**data[0],'body':'new content'}),data[0]['id']))
    assert (await topics.refresh(None,None,principal,store,id,automatic=True))['skipped']
    await topics.refresh(None,None,principal,store,id)
    assert len(calls)==2
    # New process/store, changed content, same daily budget.
    reloaded=IntelligenceStore(tmp_path)
    assert not topics.automatic_due(reloaded,owner,reloaded.get('channels',owner,id))
    with store.connect() as db:
        db.execute('UPDATE topic_attempts SET last_attempt=?',(time.time()-86401,))
        current=json.loads(db.execute('SELECT data FROM channels WHERE id=?',(id,)).fetchone()['data'])
        current['hot_topics']['generated_at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        db.execute('UPDATE channels SET data=? WHERE id=?',(json.dumps(current),id))
        db.execute('UPDATE articles SET data=? WHERE id=?',(json.dumps({**data[0],'body':'next day'}),data[0]['id']))
    await topics.refresh(None,None,principal,store,id,automatic=True)
    assert len(calls)==3


@pytest.mark.asyncio
async def test_failed_automatic_topics_are_budgeted_and_collection_cache_untouched(tmp_path,monkeypatch):
    from types import SimpleNamespace as NS
    store=IntelligenceStore(tmp_path);owner='owner';principal=NS(actor_user_id=owner)
    c=store.save_channel(owner,ChannelInput(name='News',interests='facts',auto_topics=True).model_dump());calls=[]
    async def fail(*args):calls.append(1);raise ValueError('unsupported evidence')
    monkeypatch.setattr(topics,'summarize',fail)
    with pytest.raises(ValueError,match='unsupported evidence'):await topics.refresh(None,None,principal,store,c['id'],automatic=True)
    assert (await topics.refresh(None,None,principal,store,c['id'],automatic=True))['skipped']
    assert len(calls)==1
    # An explicit user request can retry a failed analysis, still using the same validator.
    with pytest.raises(ValueError):await topics.refresh(None,None,principal,store,c['id'])
    assert len(calls)==2


@pytest.mark.asyncio
async def test_topic_claim_serializes_ui_and_background_without_duplicate_model_calls(tmp_path,monkeypatch):
    import asyncio
    from types import SimpleNamespace as NS
    from fastapi import HTTPException
    store=IntelligenceStore(tmp_path);owner='owner';principal=NS(actor_user_id=owner)
    c=store.save_channel(owner,ChannelInput(name='News',interests='facts',auto_topics=True).model_dump())
    entered=asyncio.Event();release=asyncio.Event();calls=[]
    async def slow(*args):calls.append(1);entered.set();await release.wait();return []
    monkeypatch.setattr(topics,'summarize',slow)
    first=asyncio.create_task(topics.refresh(None,None,principal,store,c['id']))
    await entered.wait()
    try:
        with pytest.raises(HTTPException) as error:await topics.refresh(None,None,principal,store,c['id'])
        assert error.value.status_code==409
        assert (await topics.refresh(None,None,principal,store,c['id'],automatic=True))['skipped']
        assert len(calls)==1
    finally:release.set();await first
