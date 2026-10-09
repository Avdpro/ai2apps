import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.api.intelligence import create_intelligence_router
from ai2apps.intelligence import service
from ai2apps.identity import RequestPrincipal


@pytest.fixture
def client(tmp_path, monkeypatch):
    async def plan(*args):
        return [{"id": "section-"+str(i), "name": name, "description": name+"报道"} for i,name in enumerate(["新品发布","上手体验","机芯技术","行业观点"])]
    monkeypatch.setattr(service, "plan_sections", plan)
    from ai2apps.intelligence import entity_categories
    async def category_plan(*args):
        return {'categories':[{'id':'products','name':'Products','description':'Products'}], 'default_id':'products', 'assignments':{}, 'signatures':{}}
    monkeypatch.setattr(entity_categories, 'plan', category_plan)
    principal=RequestPrincipal.legacy_local()
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    app=FastAPI()
    app.state.runtime = runtime
    app.include_router(create_intelligence_router(lambda:runtime,lambda:principal))
    with TestClient(app) as result:
        yield result
    runtime.stop()


def legacy_run(client, channel_id):
    """Seed a pre-migration run to test the retained legacy finish API.

    New POST /runs jobs belong to Local and deliberately reject browser finish.
    """
    return client.app.state.runtime.intelligence_collector.store.claim(
        RequestPrincipal.legacy_local().actor_user_id, channel_id)


def test_new_runs_are_owned_by_local_and_reject_frontend_writes(client):
    channel, _ = channel_and_source(client)
    response = client.post('/intelligence/channels/'+channel['id']+'/runs', json={})
    assert response.status_code == 200, response.text
    run = response.json()
    assert run['execution_owner'] == 'local'
    assert client.post('/intelligence/runs/'+run['id']+'/finish', json={'pages':[], 'logs':[]}).status_code == 409
    assert client.patch('/intelligence/runs/'+run['id'], json={'message':'forged'}).status_code == 409
    assert client.post('/intelligence/channels/'+channel['id']+'/runs', json={}).status_code == 409


def channel_and_source(client):
    c=client.post('/intelligence/channels',json={'name':'腕表','interests':'机芯新品'}).json()
    s=client.post('/intelligence/channels/'+c['id']+'/sources',json={'name':'品牌','url':'https://example.com/news'}).json()
    return c,s


def test_crud_validation_and_failed_read(client):
    c,s=channel_and_source(client)
    assert client.post('/intelligence/channels/'+c['id']+'/sources',json={'name':'bad','url':'http://localhost/'}).status_code==422
    run=legacy_run(client,c['id'])
    assert client.post('/intelligence/channels/'+c['id']+'/runs',json={}).status_code==409
    result=client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':[],'logs':[{'source_id':s['id'],'name':'品牌','status':'needs_user','pages':0,'message':'login'}]})
    assert result.status_code==200 and result.json()['status']=='failed'
    assert client.get('/intelligence').json()['articles']==[]


def test_digest_failure_does_not_commit_and_success_retries(client,monkeypatch):
    c,s=channel_and_source(client)
    page={'source_id':s['id'],'url':'https://example.com/a','title':'New watch','text':'New movement announced.'}
    async def fail(*args,**kwargs):
        from fastapi import HTTPException
        raise HTTPException(502,'model failed')
    monkeypatch.setattr(service,'digest',fail)
    run=legacy_run(client,c['id'])
    body={'pages':[page],'logs':[{'source_id':s['id'],'name':'品牌','status':'success','pages':1}]}
    assert client.post('/intelligence/runs/'+run['id']+'/finish',json=body).status_code==502
    failed = client.get('/intelligence').json()['runs'][0]
    assert failed['logs'] == [{**body['logs'][0], 'message': '', 'skipped': 0, 'agent_stats': {}}]
    assert 'model failed' in failed['message']
    async def good(runtime,request,principal,channel,pages,previous):
        assert len(pages)==1
        return [{'title':'机芯更新','summary':'新机芯','body':'新机芯 [1]','sources':[{'url':pages[0]['url']}]}]
    monkeypatch.setattr(service,'digest',good)
    run=legacy_run(client,c['id'])
    assert client.post('/intelligence/runs/'+run['id']+'/finish',json=body).status_code==200
    assert len(client.get('/intelligence').json()['articles'])==1


@pytest.mark.asyncio
async def test_recommendation_rejects_invented_urls(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validator):
        with pytest.raises(ValueError):
            validator({'sources':[{'url':'https://invented.com/','name':'Fake','reason':'a'}]})
        return validator({'sources':[{'url':'https://example.com/','name':'Source','reason':'observed'}]})
    monkeypatch.setattr(service,'model_json',fake)
    result=await service.recommend(None,None,None,{'id':'c'},[{'url':'https://example.com/'}])
    assert len(result['sources'])==1


@pytest.mark.asyncio
async def test_digest_rejects_bad_evidence_and_update_id(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validator):
        draft={'title':'new','summary':'s','body':'b [1]','evidence_ids':[3]}
        with pytest.raises(ValueError):validator({'articles':[draft]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'evidence_ids':[1],'update_article_id':'foreign'}]})
        return validator({'articles':[{**draft,'evidence_ids':[1]}]})
    monkeypatch.setattr(service,'model_json',fake)
    page={'url':'https://example.com/','title':'title','source_name':'source','retrieved_at':'now','text':'evidence'}
    result=await service.digest(None,None,None,{'id':'c'},[page],[])
    assert result[0]['sources'][0]['url']==page['url']


def test_profile_save_checks_owner_and_preserves_key(client,monkeypatch):
    from ai2apps.api import intelligence
    calls=[]
    class Profiles:
        def __init__(self,db):pass
        def require(self,owner,key):
            calls.append((owner,key))
            if key=='b'*32:raise KeyError('Profile not owned by user')
            return SimpleNamespace(key=key)
    monkeypatch.setattr(intelligence,'BrowserProfileRepository',Profiles)
    # Isolate non-default Profile ownership validation from browser storage.
    runtime=SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=Path('/tmp'))),database=None)
    import tempfile
    with tempfile.TemporaryDirectory() as root:
        runtime.config.paths.artifacts_path=Path(root)
        app=FastAPI();app.include_router(create_intelligence_router(lambda:runtime,RequestPrincipal.legacy_local))
        c=TestClient(app);channel,source=channel_and_source(c)
        path='/intelligence/sources/'+source['id']
        body={'name':'Social','url':'https://example.com/topic','profile_key':'a'*32,'kind':'social'}
        result=c.put(path,json=body)
        assert result.status_code==200 and result.json()['profile_key']=='a'*32
        assert c.put(path,json={**body,'profile_key':'b'*32}).status_code==404
        assert c.put(path,json={**body,'profile_key':'../other'}).status_code==422
        assert calls[0][0]==RequestPrincipal.legacy_local().actor_user_id


@pytest.mark.asyncio
async def test_digest_global_citations_remap_to_article_sources(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validator):
        assert [p['evidence_id'] for p in data['evidence']] == [1,2,3]
        draft={'title':'Event','summary':'New facts','body':'One fact [3]. Another [2]. Again [3].','evidence_ids':[3,2]}
        with pytest.raises(ValueError):validator({'articles':[{**draft,'body':'Undeclared source [1]'}]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'body':'No citation'}]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'evidence_ids':[0]}]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'evidence_ids':[3,3]}]})
        return validator({'articles':[draft]})
    monkeypatch.setattr(service,'model_json',fake)
    pages=[{'url':f'https://example.com/{i}','title':str(i),'source_name':'source','retrieved_at':'now','text':'facts'} for i in range(1,4)]
    result=await service.digest(None,None,None,{'id':'c'},pages,[])
    assert result[0]['body']=='One fact [1]. Another [2]. Again [1].'
    assert [p['url'] for p in result[0]['sources']]==['https://example.com/3','https://example.com/2']


def test_pending_pages_filters_committed_history_and_preserves_retry(client, monkeypatch):
    c,s=channel_and_source(client)
    endpoint='/intelligence/channels/'+c['id']+'/pending-pages'
    candidates=[{'url':'https://example.com/old?utm_source=feed#top'},
                {'url':'https://example.com/new'}, {'url':'https://example.com/new?fbclid=track'},
                {'url':'https://example.com/article?id=2'}]
    assert len(client.post(endpoint,json={'candidates':candidates}).json()['candidates'])==3
    page={'source_id':s['id'],'url':'https://example.com/final','requested_url':'https://example.com/old',
          'title':'Old','text':'Source content'}
    async def fail(*args):
        from fastapi import HTTPException
        raise HTTPException(502,'retry')
    monkeypatch.setattr(service,'digest',fail)
    run=legacy_run(client,c['id'])
    body={'pages':[page],'logs':[{'source_id':s['id'],'name':'source','status':'success','pages':1}]}
    client.post('/intelligence/runs/'+run['id']+'/finish',json=body)
    assert client.post(endpoint,json={'candidates':candidates}).json()['candidates'][0]['url']=='https://example.com/old'
    async def good(*args):return []  # successfully analysed but no article warranted
    monkeypatch.setattr(service,'digest',good)
    run=legacy_run(client,c['id'])
    assert client.post('/intelligence/runs/'+run['id']+'/finish',json=body).status_code==200
    result=client.post(endpoint,json={'candidates':candidates,'seen_urls':['https://example.com/new']}).json()
    assert result['skipped']==3
    assert [p['url'] for p in result['candidates']]==['https://example.com/article?id=2']
    assert not client.post(endpoint,json={'candidates':[{'url':page['url']}]}).json()['candidates']
    assert client.post('/intelligence/channels/not-owned/pending-pages',json={'candidates':candidates}).status_code==404
    other=client.post('/intelligence/channels',json={'name':'Other','interests':'Other'}).json()
    assert client.post('/intelligence/channels/'+other['id']+'/pending-pages',json={'candidates':[candidates[0]]}).json()['candidates']


def test_channel_sections_created_preserved_and_failure_atomic(client, monkeypatch):
    c,_=channel_and_source(client)
    assert len(c['sections'])==4
    edited=client.put('/intelligence/channels/'+c['id'],json={'name':'腕表','interests':'新品与技术'}).json()
    assert edited['sections']==c['sections']
    async def fail(*args):
        from fastapi import HTTPException
        raise HTTPException(502,'planning failed')
    monkeypatch.setattr(service,'plan_sections',fail)
    assert client.post('/intelligence/channels',json={'name':'摄影','interests':'相机'}).status_code==502
    assert len(client.get('/intelligence').json()['channels'])==1
    assert client.post('/intelligence/channels/foreign/sections').status_code==404
    assert client.post('/intelligence/channels/'+c['id']+'/sections').status_code==409


@pytest.mark.asyncio
async def test_section_plan_validates_names_and_uses_interests(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validator):
        assert data['interests']=='独立制表与机芯'
        sections=[{'name':n,'description':n+'的报道'} for n in ['新品发布','佩戴体验','机芯解析','行业观察']]
        with pytest.raises(ValueError):validator({'sections':sections[:2]})
        with pytest.raises(ValueError):validator({'sections':[sections[0]]*4})
        with pytest.raises(ValueError):validator({'sections':[{**s,'name':' '} for s in sections]})
        return validator({'sections':sections})
    monkeypatch.setattr(service,'model_json',fake)
    sections=await service.plan_sections(None,None,None,{'name':'腕表','interests':'独立制表与机芯'})
    assert len({s['id'] for s in sections})==4
    assert sections[2]['name']=='机芯解析'


@pytest.mark.asyncio
async def test_classification_requires_complete_owned_ids(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validator):
        for assignments in [[],[{'article_id':'other','section_id':'s'}],
                            [{'article_id':'a','section_id':'foreign'}],
                            [{'article_id':'a','section_id':'s'}]*2]:
            with pytest.raises(ValueError):validator({'assignments':assignments})
        return validator({'assignments':[{'article_id':'a','section_id':'s'}]})
    monkeypatch.setattr(service,'model_json',fake)
    result=await service.classify_articles(None,None,None,{'id':'c'},[{'id':'s'}],[{'id':'a','title':'Title'}])
    assert result=={'a':'s'}


@pytest.mark.asyncio
async def test_digest_requires_valid_channel_section(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validator):
        draft={'title':'New','summary':'Facts','body':'Facts [1]','evidence_ids':[1]}
        for section in [None,'foreign']:
            with pytest.raises(ValueError):validator({'articles':[{**draft,'section_id':section}]})
        return validator({'articles':[{**draft,'section_id':'s'}]})
    monkeypatch.setattr(service,'model_json',fake)
    page={'url':'https://example.com/a','title':'New','source_name':'Source','retrieved_at':'now','text':'Facts'}
    result=await service.digest(None,None,None,{'id':'c','sections':[{'id':'s','name':'新品发布'}]},[page],[])
    assert result[0]['section_id']=='s'


def test_legacy_section_endpoint_failure_keeps_history_and_retry_succeeds(client,monkeypatch):
    async def legacy_plan(*args):return []
    monkeypatch.setattr(service,'plan_sections',legacy_plan)
    c,s=channel_and_source(client)
    async def digest(*args):return [{'title':'新品','summary':'新表','body':'正文 [1]','sources':[]}]
    monkeypatch.setattr(service,'digest',digest)
    run=legacy_run(client,c['id'])
    client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':[],'logs':[]})
    before=client.get('/intelligence').json()['articles'][0]
    sections=[{'id':'s','name':'新品发布','description':'新表上市'}]
    async def plan(*args):return sections
    async def fail(*args):
        from fastapi import HTTPException
        raise HTTPException(502,'classification failed')
    monkeypatch.setattr(service,'plan_sections',plan)
    monkeypatch.setattr(service,'classify_articles',fail)
    path='/intelligence/channels/'+c['id']+'/sections'
    assert client.post(path).status_code==502
    state=client.get('/intelligence').json()
    assert not state['channels'][0]['sections'] and state['articles'][0]==before
    async def classify(*args):return {before['id']:'s'}
    monkeypatch.setattr(service,'classify_articles',classify)
    assert client.post(path).json()['sections']==sections
    assert client.get('/intelligence').json()['articles'][0]['section_id']=='s'


def test_topics_cache_and_owner_scope(client,monkeypatch):
    c,s=channel_and_source(client)
    calls=[]
    from ai2apps.intelligence import topics
    async def summarize(*args):
        calls.append(args)
        return []
    monkeypatch.setattr(topics,'summarize',summarize)
    path='/intelligence/channels/'+c['id']+'/topics'
    result=client.post(path)
    assert result.status_code==200 and result.json()['article_count']==0
    assert client.post(path).json()==result.json() and len(calls)==1
    assert client.post('/intelligence/channels/missing/topics').status_code==404
    assert client.get('/intelligence').json()['channels'][0]['hot_topics']==result.json()


def test_article_feedback_flow(client,monkeypatch):
    from ai2apps.intelligence import feedback
    c,s=channel_and_source(client)
    async def digest(*args):
        return [{'title':'三重追针','summary':'新品','body':'技术介绍','sources':[{'url':'https://example.com/a'}]}]
    monkeypatch.setattr(service,'digest',digest)
    run=legacy_run(client,c['id'])
    assert client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':[{'source_id':s['id'],'url':'https://example.com/a','title':'表款','text':'新表发布'}],'logs':[]}).status_code==200
    a=client.get('/intelligence').json()['articles'][0];path='/intelligence/articles/'+a['id']
    calls=[]
    async def generate(*args):calls.append(1);return ['不关注追针','报道重复','细节不足']
    monkeypatch.setattr(feedback,'generate',generate)
    options=client.post(path+'/feedback-reasons').json()
    assert client.post(path+'/feedback-reasons').json()==options and len(calls)==1
    assert client.patch(path,json={'feedback':'less'}).status_code==409
    assert client.patch(path,json={'feedback':'less','reasons':['伪造'],'reason_signature':options['signature']}).status_code==409
    result=client.patch(path,json={'feedback':'less','reasons':['不关注追针'],'reason_signature':options['signature']})
    assert result.status_code==200 and result.json()['feedback_reasons']==['不关注追针']
    assert client.get('/intelligence/channels/'+c['id']+'/preferences').json()['items'][0]['reasons']==['不关注追针']
    client.patch(path,json={'read':True})
    assert client.get('/intelligence').json()['articles'][0]['feedback']=='less'
    assert client.post('/intelligence/articles/missing/feedback-reasons').status_code==404
    client.patch(path,json={'feedback':''})
    assert client.get('/intelligence/channels/'+c['id']+'/preferences').json()['items']==[]


def test_manuscript_creation_revision_idempotency(client,monkeypatch):
    from ai2apps.intelligence import writing
    c,s=channel_and_source(client)
    async def digest(*args):return [{'title':'新表','summary':'摘要','body':'新表机芯','sources':[{'url':'https://example.com/a'}]}]
    monkeypatch.setattr(service,'digest',digest)
    run=legacy_run(client,c['id'])
    client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':[{'source_id':s['id'],'url':'https://example.com/a','title':'新表','text':'新表机芯'}],'logs':[]})
    article=client.get('/intelligence').json()['articles'][0]
    calls=[]
    async def compose(*args):
        calls.append(args[-1]);return {'title':'新表稿件','content':'介绍新表 [1]','note':'按要求调整','evidence_ids':[1]}
    monkeypatch.setattr(writing,'compose',compose)
    path='/intelligence/channels/'+c['id']+'/drafts'
    body={'request_id':'draft-12345','scope':'article','scope_id':article['id'],'kind':'short_post','guidance':'简洁介绍'}
    result=client.post(path,json=body)
    assert result.status_code==200 and result.json()['revision']==1
    assert client.post(path,json=body).json()['id']=='draft-12345' and len(calls)==1
    assert client.post(path,json={**body,'guidance':'different'}).status_code==409
    revision={'request_id':'revise-1234','revision':1,'guidance':'更轻松'}
    result=client.post('/intelligence/drafts/draft-12345/revise',json=revision)
    assert result.status_code==200 and result.json()['revision']==2 and len(result.json()['turns'])==2
    assert client.post('/intelligence/drafts/draft-12345/revise',json=revision).json()['revision']==2 and len(calls)==2
    assert client.post('/intelligence/drafts/draft-12345/revise',json={**revision,'request_id':'new-req-123'}).status_code==409
    assert client.get(path).json()['items'][0]['revision']==2
    assert client.get('/intelligence/drafts/missing').status_code==404
    assert client.get('/intelligence/drafts/draft-12345').json()['evidence'][0]['id']==article['id']
    async def fail(*args):raise TimeoutError()
    monkeypatch.setattr(writing,'compose',fail)
    assert client.post('/intelligence/drafts/draft-12345/revise',json={'request_id':'fail-12345','revision':2,'guidance':'再改一次'}).status_code==504
    assert client.get('/intelligence/drafts/draft-12345').json()['revision']==2


def test_source_agent_bindings_saved_and_cleared(client, monkeypatch):
    from ai2apps.intelligence import site_agents
    calls = []
    def resolve(runtime, owner, generation):
        calls.append(generation)
        if generation == 'invalid': raise ValueError('invalid agent')
        return {'generation_id': generation}
    monkeypatch.setattr(site_agents, 'selected_agent', resolve)
    c, s = channel_and_source(client)
    body = {'name': s['name'], 'url': s['url'], 'list_agent_generation_id': 'list-v', 'article_agent_generation_id': 'body-v'}
    result = client.put('/intelligence/sources/'+s['id'], json=body)
    assert result.status_code == 200
    assert result.json()['list_agent_generation_id'] == 'list-v'
    assert calls == ['list-v', 'body-v']
    body['list_agent_generation_id'] = 'invalid'
    assert client.put('/intelligence/sources/'+s['id'], json=body).status_code == 409
    body.update(list_agent_generation_id='', article_agent_generation_id='')
    assert client.put('/intelligence/sources/'+s['id'], json=body).json()['article_agent_generation_id'] == ''
