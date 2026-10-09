import json
import pytest
from ai2apps.intelligence import writing, service
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence.models import ChannelInput


def context():
    channel={'id':'c','name':'腕表','sections':[{'id':'s','name':'机芯'}],'hot_topics':{'items':[{'id':'t','title':'Model X','article_ids':['a','b','foreign']}]}}
    articles=[{'id':id,'channel_id':c,'section_id':s,'title':id,'summary':'summary','body':'facts','updated_at':'2026-10-07T00:00:00+00:00'} for id,c,s in [('a','c','s'),('b','c','other'),('foreign','other','s')]]
    return channel,articles


def test_scope_boundaries_and_empty_evidence():
    channel,articles=context()
    for scope,id,expected in [('article','a',{'a'}),('section','s',{'a'}),('section','unassigned',{'b'}),('topic','t',{'a','b'}),('channel','',{'a','b'})]:
        body=writing.CreateDraft(request_id='req-123456',scope=scope,scope_id=id,kind='short_post',guidance='介绍新品')
        selected=writing.select_evidence(channel,articles,body)
        assert {e['id'] for e in selected['evidence']}==expected
    for scope,id in [('article','foreign'),('section','missing'),('topic','old'),('channel','other')]:
        with pytest.raises(ValueError):writing.select_evidence(channel,articles,writing.CreateDraft(request_id='req-123456',scope=scope,scope_id=id,kind='short_post',guidance='写稿'))
    with pytest.raises(ValueError):writing.select_evidence(channel,[],writing.CreateDraft(request_id='req-123456',scope='channel',kind='short_post',guidance='写稿'))


@pytest.mark.asyncio
async def test_writing_checks_citations_and_reuses_current_manuscript(monkeypatch):
    async def model(*args):
        data,validate=args[-2:]
        assert data['user_guidance']=='修改开头' and data['current_manuscript']['content']=='原稿 [1]'
        for content,ids in [('no citations',[1]),('bad [2]',[1]),('bad [2]',[2]),('ok [1]',[1,1])]:
            with pytest.raises(ValueError):validate({'title':'title','content':content,'note':'note','evidence_ids':ids})
        return validate({'title':'新稿','content':'新开头 [1]','note':'修改了开头','evidence_ids':[1]})
    monkeypatch.setattr(service,'model_json',model)
    result=await writing.compose(None,None,None,'c',{'kind':'short_post','scope_label':'文章','guidance':'初稿','evidence':[{'evidence_id':1}],'current':{'content':'原稿 [1]'}},'修改开头')
    assert result['content']=='新开头 [1]'


def test_store_owner_and_revision_conflict(tmp_path):
    store=IntelligenceStore(tmp_path);c=store.save_channel('alice',ChannelInput(name='腕表',interests='机械表').model_dump())
    draft={'id':'draft','channel_id':c['id'],'title':'title','kind':'short_post','scope':'channel','scope_label':'腕表','updated_at':'now','revision':1}
    store.save_draft('alice',draft)
    with pytest.raises(KeyError):store.draft('bob','draft')
    with pytest.raises(KeyError):store.drafts('bob',c['id'])
    with pytest.raises(ValueError):store.save_draft('alice',{**draft,'revision':2},0)
    store.save_draft('alice',{**draft,'revision':2},1)
    assert store.draft('alice','draft')['revision']==2
    store.delete('channels','alice',c['id'])
    with pytest.raises(KeyError):store.draft('alice','draft')
