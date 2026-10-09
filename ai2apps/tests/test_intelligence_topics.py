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
