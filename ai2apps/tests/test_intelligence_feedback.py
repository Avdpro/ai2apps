import json
import pytest
from ai2apps.intelligence import feedback, service
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence.models import ChannelInput


@pytest.fixture
def data(tmp_path):
    store=IntelligenceStore(tmp_path)
    channel=store.save_channel('alice',ChannelInput(name='腕表',interests='机械表新品').model_dump())
    article={'id':'a','title':'铂金三重追针','summary':'复杂机芯','body':'发布与技术细节','updated_at':'2026-10-07T00:00:00+00:00','sources':[]}
    with store.connect() as db:
        db.execute('INSERT INTO articles VALUES(?,?,?,?)',('a','alice',channel['id'],json.dumps(article)))
    return store,channel,store.get('articles','alice','a')


def test_preferences_require_generated_selected_reasons_and_undo(data):
    store,c,a=data;digest=feedback.signature(c,a)
    store.save_feedback_options('alice','a',digest,['不关注铂金表款','技术细节不足','报道重复'])
    assert store.preferences('alice',c['id'])==[]
    for reasons,signature in [([],digest),(['编造的理由'],digest),(['报道重复'],'old')]:
        with pytest.raises(ValueError):store.feedback('alice','a','less',reasons=reasons,reason_signature=signature)
    store.feedback('alice','a','less',reasons=['报道重复'],reason_signature=digest)
    assert store.preferences('alice',c['id'])[0]['reasons']==['报道重复']
    store.feedback('alice','a','more')
    assert store.preferences('alice',c['id'])[0]['reasons']==[]
    assert len(store.preferences('alice',c['id']))==1
    store.feedback('alice','a','')
    assert store.preferences('alice',c['id'])==[]
    with pytest.raises(KeyError):store.preferences('bob',c['id'])
    with pytest.raises(KeyError):store.feedback('bob','a','more')


def test_stale_options_and_channel_deletion(data):
    store,c,a=data;digest=feedback.signature(c,a)
    store.save_feedback_options('alice','a',digest,['a','b','c'])
    store.feedback('alice','a','more')
    store.save_channel('alice',ChannelInput(name='腕表',interests='只关注潜水表').model_dump(),c['id'])
    with pytest.raises(ValueError):store.feedback('alice','a','less',reasons=['a'],reason_signature=digest)
    with pytest.raises(ValueError):store.save_feedback_options('alice','a',digest,['a','b','c'])
    store.delete('channels','alice',c['id'])
    with store.connect() as db:assert db.execute('SELECT count(*) FROM preferences').fetchone()[0]==0


@pytest.mark.asyncio
async def test_context_and_reason_validation(monkeypatch):
    async def model(*args):
        assert args[-2]['channel']['name']=='腕表'
        assert args[-2]['article']['title']=='三重追针'
        validate=args[-1]
        for reasons in [['a'],['a','a','c'],['  ','b','c'],['a'*101,'b','c']]:
            with pytest.raises(ValueError):validate({'reasons':reasons})
        return validate({'reasons':[' 不关注追针功能 ','报道重复','细节不足']})
    monkeypatch.setattr(service,'model_json',model)
    assert (await feedback.generate(None,None,None,{'id':'c','name':'腕表'},{'title':'三重追针'}))[0]=='不关注追针功能'
