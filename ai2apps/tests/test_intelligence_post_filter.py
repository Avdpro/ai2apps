import pytest
from ai2apps.intelligence import post_filter, service
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.tests.test_intelligence_api import client, channel_and_source, legacy_run


@pytest.mark.asyncio
async def test_review_requires_complete_decisions_and_context(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validate):
        assert data['stage']=='list' and data['preferences'][0]['feedback']=='less'
        assert 'image' in instruction and 'likes' in instruction
        with pytest.raises(ValueError):
            validate({'decisions':[]})
        return validate({'decisions':[{'index':0,'reject':False,'reason':'图片内容待详情判断'}]})
    monkeypatch.setattr(post_filter,'model_json',fake)
    result=await post_filter.review(None,None,None,{'id':'c','post_filter_level':'strict'},[{'url':'https://weibo.com/12345/abc','text':'图'}],[{'feedback':'less'}],'list')
    assert not result[0].reject


def test_owner_isolation_and_restore_persists(tmp_path):
    store=IntelligenceStore(tmp_path)
    channel=store.save_channel('a',{'name':'腕表','interests':'新品','interval_hours':0})['id']
    page={'url':'https://weibo.com/12345/abc','text':'抽奖'}
    store.save_filtered_post('a',channel,page,'纯抽奖','list')
    row=store.filtered_posts('a',channel)[0]
    with pytest.raises(KeyError):
        store.restore_filtered_post('b',channel,row['id'])
    store.restore_filtered_post('a',channel,row['id'])
    store.save_filtered_post('a',channel,page,'再次判断','detail')
    assert store.filtered_posts('a',channel)[0]['status']=='restored'


def test_filter_and_restore_detail_on_next_run(client,monkeypatch):
    c,s=channel_and_source(client)
    page={'source_id':s['id'],'url':'https://weibo.com/12345/abc','title':'晒表','text':'今天戴这个','platform':'weibo'}
    async def reject(*args):
        return [post_filter.Decision(index=i,reject=True,reason='缺少具体体验') for i in range(len(args[4]))]
    received=[]
    async def digest(*args):
        received.append(args[4])
        return []
    monkeypatch.setattr(post_filter,'review',reject)
    monkeypatch.setattr(service,'digest',digest)
    def finish(pages):
        run=legacy_run(client,c['id'])
        return client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':pages,'logs':[]})
    assert finish([page]).status_code==200
    assert received[-1]==[]
    endpoint='/intelligence/channels/'+c['id']+'/filtered-posts'
    row=client.get(endpoint).json()['items'][0]
    assert row['stage']=='detail'
    assert client.post(endpoint+'/'+row['id']+'/restore').status_code==200
    assert finish([]).status_code==200
    assert received[-1][0]['url']==page['url']
    assert finish([]).status_code==200
    assert received[-1]==[]


def test_list_filter_reuses_records_and_restore(client,monkeypatch):
    c,s=channel_and_source(client)
    calls=[]
    async def review(*args):
        calls.append(len(args[4]))
        return [post_filter.Decision(index=i,reject=True,reason='抽奖引流') for i in range(len(args[4]))]
    monkeypatch.setattr(post_filter,'review',review)
    endpoint='/intelligence/channels/'+c['id']+'/post-candidates/'+s['id']
    body={'candidates':[{'url':'https://weibo.com/12345/abc','text':'转发抽奖'}]}
    assert client.post(endpoint,json=body).json()['filtered']==1
    assert client.post(endpoint,json=body).json()['filtered']==1
    assert calls==[1,0]
    rows='/intelligence/channels/'+c['id']+'/filtered-posts'
    row=client.get(rows).json()['items'][0]
    client.post(rows+'/'+row['id']+'/restore')
    assert len(client.post(endpoint,json=body).json()['candidates'])==1
    assert client.post('/intelligence/channels/other/post-candidates/'+s['id'],json=body).status_code==404
