from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from ai2apps.identity import RequestPrincipal
from ai2apps.api.intelligence import create_intelligence_router
from ai2apps.intelligence import service
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence.models import ChannelInput


@pytest.fixture
def env(tmp_path):
    store=IntelligenceStore(tmp_path/'intelligence')
    owner=RequestPrincipal.legacy_local().actor_user_id
    channel=store.save_channel(owner,ChannelInput(name='腕表',interests='新品').model_dump())
    runtime=SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)))
    principal=RequestPrincipal.legacy_local()
    app=FastAPI();app.include_router(create_intelligence_router(lambda:runtime,lambda:principal))
    return TestClient(app),store,owner,channel


def test_empty_channel_persistence_and_idempotency(env):
    client,store,owner,c=env
    path='/intelligence/channels/'+c['id']+'/conversation'
    body={'question':'有哪些新品？','request_id':'request-123456789'}
    first=client.post(path,json=body)
    assert first.status_code==200 and not first.json()['references']
    assert client.post(path,json=body).json()==first.json()
    assert len(client.get(path).json()['turns'])==1
    assert len(IntelligenceStore(store.root).conversation(owner,c['id']))==1
    assert client.post(path,json={**body,'question':'其他问题'}).status_code==409
    assert client.post(path,json={**body,'question':'  '}).status_code==422
    store.delete('channels',owner,c['id'])
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM conversations').fetchone()[0]==0


def test_failed_answer_retries_and_channel_isolation(env,monkeypatch):
    client,store,owner,c=env
    other=store.save_channel('other',ChannelInput(name='私有',interests='私有').model_dump())
    assert client.get('/intelligence/channels/'+other['id']+'/conversation').status_code==404
    path='/intelligence/channels/'+c['id']+'/conversation'
    calls=[]
    async def fail(*args):
        raise TimeoutError()
    monkeypatch.setattr(service,'converse',fail)
    body={'question':'总结','request_id':'request-123456789'}
    assert client.post(path,json=body).status_code==504
    assert client.get(path).json()['turns']==[]
    async def success(runtime,request,principal,channel,question,articles,history,article_id):
        calls.append((channel,articles,history))
        return {'answer':'暂无资料','references':[]}
    monkeypatch.setattr(service,'converse',success)
    assert client.post(path,json=body).status_code==200
    assert client.post(path,json={**body,'request_id':'request-222222222','question':'继续'}).status_code==200
    assert len(calls[-1][2])==1
    assert client.post(path,json={**body,'request_id':'request-333333333','article_id':'foreign'}).status_code==404


@pytest.mark.asyncio
async def test_evidence_validation_and_follow_up(monkeypatch):
    a={'id':'a','title':'机芯技术','summary':'动力储存','body':'新款动力储存72小时。','updated_at':'2026-10-07'}
    async def fake(runtime,request,principal,id,instruction,data,validate):
        assert data['current_question']=='续航多长？'
        assert data['history'][0]['question']=='谈谈机芯'
        assert data['articles'][0]['id']=='a'
        with pytest.raises(ValueError):validate({'answer':'事实[2]','evidence_ids':[2]})
        with pytest.raises(ValueError):validate({'answer':'事实[1]','evidence_ids':[]})
        with pytest.raises(ValueError):validate({'answer':'事实','evidence_ids':[1]})
        return validate({'answer':'报道显示72小时 [1]。','evidence_ids':[1]})
    monkeypatch.setattr(service,'model_json',fake)
    answer=await service.converse(None,None,None,{'id':'c','name':'腕表','interests':'新品'},
        '续航多长？',[a],[{'question':'谈谈机芯','answer':'先前回答'}],'a')
    assert answer['references']==[{'number':1,'article_id':'a','title':'机芯技术'}]


def test_retrieval_budget_selected_article_and_chinese_matching():
    articles=[{'id':str(i),'title':'其他新闻','summary':'概要','body':'x'*9000,'updated_at':str(i)} for i in range(100)]
    articles[0].update(title='机芯续航',body='72小时动力储存')
    selected=service.conversation_evidence(articles,'机芯续航',[])
    assert selected[0]['id']=='0'
    selected=service.conversation_evidence(articles,'机芯续航',[],'1')
    assert selected[0]['id']=='1'
    assert len(selected)<=20 and sum(len(e['body'])+len(e['title'])+len(e['summary']) for e in selected)<=80000


def test_deleted_channel_cannot_be_resurrected(env):
    client,store,owner,c=env
    store.delete('channels',owner,c['id'])
    with pytest.raises(KeyError):
        store.save_conversation(owner,c['id'],{'id':'test','question':'x','answer':'y'})
