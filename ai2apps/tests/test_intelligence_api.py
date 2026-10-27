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
    duplicate = client.post('/intelligence/channels/'+channel['id']+'/runs', json={})
    assert duplicate.status_code == 200 and duplicate.json()['id'] == run['id']


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
    async def fake(runtime,request,principal,id,instruction,data,validator,**kwargs):
        with pytest.raises(ValueError):
            validator({'sources':[{'url':'https://invented.com/','name':'Fake','reason':'a'}]})
        return validator({'sources':[{'url':'https://example.com/','name':'Source','reason':'observed'}]})
    monkeypatch.setattr(service,'model_json',fake)
    result=await service.recommend(None,None,None,{'id':'c'},[{'url':'https://example.com/'}])
    assert len(result['sources'])==1


@pytest.mark.asyncio
async def test_digest_rejects_bad_evidence_and_update_id(monkeypatch):
    async def fake(runtime,request,principal,id,instruction,data,validator,**kwargs):
        draft={'title':'new','summary':'s','body':'b [1]','evidence_ids':[3]}
        with pytest.raises(ValueError):validator({'articles':[draft]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'evidence_ids':[1],'update_article_id':'foreign'}]})
        return validator({'articles':[{**draft,'evidence_ids':[1]}]})
    monkeypatch.setattr(service,'model_json',fake)
    page={'url':'https://example.com/','title':'title','source_name':'source','retrieved_at':'now','text':'evidence'}
    result=await service.digest_event(None,None,None,{'id':'c'},[page],[])
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
    async def fake(runtime,request,principal,id,instruction,data,validator,**kwargs):
        assert [p['evidence_id'] for p in data['evidence']] == [1,2,3]
        draft={'title':'Event','summary':'New facts','body':'One fact [3]. Another [2]. Again [3].','evidence_ids':[3,2],'primary_evidence_id':3}
        with pytest.raises(ValueError):validator({'articles':[{**draft,'body':'Undeclared source [1]'}]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'body':'No citation'}]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'evidence_ids':[0]}]})
        with pytest.raises(ValueError):validator({'articles':[{**draft,'evidence_ids':[3,3]}]})
        return validator({'articles':[draft]})
    monkeypatch.setattr(service,'model_json',fake)
    pages=[{'url':f'https://example.com/{i}','title':str(i),'source_name':'source','retrieved_at':'now','text':'facts'} for i in range(1,4)]
    result=await service.digest_event(None,None,None,{'id':'c'},pages,[])
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
    async def fake(runtime,request,principal,id,instruction,data,validator,**kwargs):
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
    async def fake(runtime,request,principal,id,instruction,data,validator,**kwargs):
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
    async def fake(runtime,request,principal,id,instruction,data,validator,**kwargs):
        draft={'title':'New','summary':'Facts','body':'Facts [1]','evidence_ids':[1]}
        for section in [None,'foreign']:
            with pytest.raises(ValueError):validator({'articles':[{**draft,'section_id':section}]})
        return validator({'articles':[{**draft,'section_id':'s'}]})
    monkeypatch.setattr(service,'model_json',fake)
    page={'url':'https://example.com/a','title':'New','source_name':'Source','retrieved_at':'now','text':'Facts'}
    result=await service.digest_event(None,None,None,{'id':'c','sections':[{'id':'s','name':'新品发布'}]},[page],[])
    assert result[0]['section_id']=='s'


def test_legacy_section_endpoint_failure_keeps_history_and_retry_succeeds(client,monkeypatch):
    async def legacy_plan(*args):return []
    monkeypatch.setattr(service,'plan_sections',legacy_plan)
    c,s=channel_and_source(client)
    async def digest(*args,**kwargs):return [{'title':'新品','summary':'新表','body':'正文 [1]','sources':[]}]
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
    async def digest(*args,**kwargs):
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
    async def digest(*args,**kwargs):return [{'title':'新表','summary':'摘要','body':'新表机芯','sources':[{'url':'https://example.com/a'}]}]
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


def test_mobile_scoped_router_cloud_writing_never_loops_into_chat_route(client,monkeypatch):
    """Mobile delegates to an isolated App router with no /v1/chat/completions."""
    from types import SimpleNamespace as NS
    c,s=channel_and_source(client)
    async def digest(*args,**kwargs):return [{'title':'Nezumi VM2','summary':'12.9 mm case','body':'The case is 12.9 mm thick.','sources':[{'url':'https://example.com/watch'}]}]
    monkeypatch.setattr(service,'digest',digest)
    run=legacy_run(client,c['id'])
    client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':[{'source_id':s['id'],'url':'https://example.com/watch','title':'Nezumi VM2','text':'12.9 mm'}],'logs':[]})
    article=client.get('/intelligence').json()['articles'][0]
    runtime=client.app.state.runtime;calls=[]
    async def invoke(payload,*,context):
        calls.append((payload,context))
        assert context.actor_user_id==RequestPrincipal.legacy_local().actor_user_id
        assert context.consumer_app_id=='ai2apps.intelligence'
        assert context.session_id=='intelligence-'+c['id']
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'title':'VM2 review','content':'The 12.9 mm case feels thick [1].','note':'Based on stated thickness.','evidence_ids':[1]})}}]}
    monkeypatch.setattr(runtime,'model_manager',NS(resolve_default_model=lambda _:'cloud/openai/test'))
    monkeypatch.setattr(runtime,'model_invocations',NS(model=lambda _:None,invoke_agent_cloud_json=invoke))
    path='/intelligence/channels/'+c['id']+'/drafts'
    body={'request_id':'mobile-write-123','scope':'article','scope_id':article['id'],'kind':'short_post','guidance':'吐槽机芯偏厚'}
    result=client.post(path,json=body)
    assert result.status_code==200,result.text
    assert result.json()['current']['content'].endswith('[1].')
    assert client.post(path,json=body).json()['id']==body['request_id'] and len(calls)==1
    revision={'request_id':'mobile-revise-123','revision':1,'guidance':'Make it shorter'}
    result=client.post('/intelligence/drafts/'+body['request_id']+'/revise',json=revision)
    assert result.status_code==200,result.text
    assert result.json()['revision']==2 and len(calls)==2


def test_manual_manuscript_edit_preserves_images_and_is_idempotent(client,monkeypatch):
    from ai2apps.intelligence import writing
    c,_=channel_and_source(client)
    store=client.app.state.runtime.intelligence_collector.store
    owner=RequestPrincipal.legacy_local().actor_user_id
    original={'id':'manual-draft','channel_id':c['id'],'kind':'long_article','scope':'article','scope_id':'a','scope_label':'Watch','total_articles':1,'title':'Title','revision':1,'updated_at':'now','turns':[],
        'current':{'title':'Title','content':'First [1]\n\nSecond','evidence_ids':[1],'note':'Initial'},'evidence':[{'id':'a','evidence_id':1}],
        'images':[{'article_id':'a','url':'https://example.com/one.jpg','before':'First [1]'}]}
    store.save_draft(owner,original)
    path='/intelligence/drafts/manual-draft/text'
    body={'request_id':'manual-edit-123','revision':1,'title':'My title','content':'Edited first [1]\n\nSecond'}
    response=client.put(path,json=body);assert response.status_code==200,response.text
    draft=response.json();assert draft['revision']==2 and draft['current']['content']==body['content']
    assert draft['images'][0]['before']=='Edited first [1]' and draft['turns'][-1]['kind']=='manual'
    assert client.put(path,json=body).json()['revision']==2
    assert client.put(path,json={**body,'content':'Other'}).status_code==409
    assert client.put(path,json={**body,'request_id':'stale-edit-123'}).status_code==409
    assert client.put(path,json={**body,'request_id':'blank-edit-123','revision':2,'content':'  '}).status_code==422
    async def compose(runtime,request,principal,channel_id,base,guidance):
        assert base['current']['content']==body['content']
        return {'title':'AI revision','content':'Revised [1]','evidence_ids':[1],'note':'Revised user text'}
    monkeypatch.setattr(writing,'compose',compose)
    response=client.post('/intelligence/drafts/manual-draft/revise',json={'request_id':'after-manual-123','revision':2,'guidance':'Improve'})
    assert response.status_code==200 and response.json()['revision']==3
    assert client.put('/intelligence/drafts/missing/text',json=body).status_code==404


def test_article_favorites_persist_without_reordering_and_survive_updates(client):
    channel, source = channel_and_source(client)
    owner = RequestPrincipal.legacy_local().actor_user_id
    store = client.app.state.runtime.intelligence_collector.store
    article = store.import_article(owner, channel['id'], {
        'title': 'Saved story', 'summary': 'Summary', 'body': 'Body',
        'sources': [], 'section_id': channel['sections'][0]['id'],
    }, 'https://example.com/saved')
    endpoint = '/intelligence/articles/' + article['id']
    saved = client.patch(endpoint, json={'favorite': True}).json()
    assert saved['favorite'] is True
    assert saved['updated_at'] == article['updated_at']
    assert saved['read'] is False and saved['feedback'] == ''
    from ai2apps.intelligence.store import IntelligenceStore
    assert IntelligenceStore(store.root).get('articles', owner, article['id'])['favorite'] is True
    assert client.patch(endpoint, json={'read': True}).json()['favorite'] is True
    assert client.patch(endpoint, json={'favorite': False}).json()['favorite'] is False
    client.patch(endpoint, json={'favorite': True})
    run = legacy_run(client, channel['id'])
    store.finish(owner, run['id'], [], [{
        'update_article_id': article['id'], 'title': 'Updated story', 'summary': 'New facts',
        'body': 'Updated body', 'sources': [], 'section_id': article['section_id'],
    }], [{'source_id': source['id'], 'name': 'Source', 'status': 'success', 'pages': 1}])
    updated = store.get('articles', owner, article['id'])
    assert updated['favorite'] is True and updated['read'] is False
    with pytest.raises(KeyError):
        store.feedback('another-owner', article['id'], favorite=False)


def test_mobile_client_diagnostics_are_bounded_and_structured(client, caplog):
    caplog.set_level('WARNING',logger='ai2apps.api.intelligence')
    event={'event_id':'a'*32,'request_id':'b'*32,'timestamp':'2026-10-18T00:00:00Z',
           'method':'GET','path':'/v1/platform/intelligence','phase':'relay_json',
           'code':'mobile_gateway_invalid_json','status':200,'relay_status':200,
           'response_kind':'html','response_bytes':123,'view':'channel','tab':'runs'}
    response=client.post('/intelligence/client-diagnostics',json={'events':[event]})
    assert response.status_code==200,response.text
    assert response.json()['accepted']==[event['event_id']]
    assert 'Mobile Intelligence diagnostic actor=' in caplog.text
    assert event['request_id'] in caplog.text and '"tab":"runs"' in caplog.text
    first_log=caplog.text
    assert client.post('/intelligence/client-diagnostics',json={'events':[event]}).status_code==200
    assert caplog.text==first_log
    for invalid in ({**event,'response_body':'private article'}, {**event,'path':'/v1/platform/intelligence?token=secret'}, {**event,'status':999}):
        assert client.post('/intelligence/client-diagnostics',json={'events':[invalid]}).status_code==422
    assert client.post('/intelligence/client-diagnostics',json={'events':[event]*21}).status_code==422


def test_progressive_channel_counts_and_cursor_cards(client):
    store = client.app.state.runtime.intelligence_collector.store
    owner = RequestPrincipal.legacy_local().actor_user_id
    c, source = channel_and_source(client)
    other = client.post('/intelligence/channels',json={'name':'Other','interests':'Other'}).json()
    for n in range(45):
        store.import_article(owner,c['id'],{'title':f'Story {n}', 'summary':'Short', 'body':'LARGE_BODY_'*1000,
            'section_id':c['sections'][0]['id'], 'sources':[{'url':'https://example.com/'+str(n),'content_type':'webpage'}]},str(n))
    store.import_article(owner,other['id'],{'title':'Other', 'summary':'Other','body':'Other body','sources':[]},'other')
    selected = next(a for a in store.snapshot(owner)['articles'] if a['channel_id']==c['id'])
    store.feedback(owner,selected['id'],read=True,favorite=True)
    overview = client.get('/intelligence?view=channels')
    assert overview.status_code == 200 and 'LARGE_BODY_' not in overview.text
    data = overview.json()
    assert data['progressive'] and data['articles']==data['sources']==[]
    stats = next(ch['article_stats'] for ch in data['channels'] if ch['id']==c['id'])
    assert (stats['total'],stats['unread'],stats['favorite'])==(45,44,1)
    assert stats['sections'][c['sections'][0]['id']]==45
    view = client.get('/intelligence/channels/'+c['id']+'/view').json()
    assert view['channel']['id']==c['id'] and [s['id'] for s in view['sources']]==[source['id']]
    path='/intelligence/channels/'+c['id']+'/articles'
    first=client.get(path).json()
    assert len(first['items'])==20 and first['total']==45 and first['next_cursor']
    assert all(a['_summary'] and 'body' not in a and a['channel_id']==c['id'] for a in first['items'])
    assert 'LARGE_BODY_' not in client.get(path).text
    second=client.get(path,params={'cursor':first['next_cursor']}).json()
    third=client.get(path,params={'cursor':second['next_cursor']}).json()
    ids=[a['id'] for page in (first,second,third) for a in page['items']]
    assert len(ids)==len(set(ids))==45 and len(third['items'])==5 and third['next_cursor'] is None
    favorites=client.get(path,params={'section':'$favorites'}).json()
    assert favorites['total']==1 and favorites['items'][0]['id']==selected['id']
    assert client.get(path,params={'status':'unread'}).json()['total']==44
    assert client.get(path,params={'q':'LARGE_BODY_'}).json()['total']==45
    assert client.get(path,params={'format':'post'}).json()['total']==0
    assert client.get(path,params={'format':'webpage'}).json()['total']==45
    detail=client.get('/intelligence/articles/'+selected['id']).json()
    assert detail['body'].startswith('LARGE_BODY_') and detail['favorite'] and detail['read']
    assert client.get('/intelligence/channels/missing/articles').status_code==404
    assert client.get('/intelligence/articles/missing').status_code==404
    assert client.get(path,params={'cursor':'bad'}).status_code==409
    assert 'LARGE_BODY_' in client.get('/intelligence').text


def test_active_system_task_overrides_early_completed_run_in_all_views(client):
    runtime=client.app.state.runtime
    store=runtime.intelligence_collector.store
    owner=RequestPrincipal.legacy_local().actor_user_id
    c,_=channel_and_source(client)
    run=legacy_run(client,c['id'])
    store.finish(owner,run['id'],[],[],[])
    task=runtime.system_tasks.submit(owner,'ai2apps.intelligence','intelligence.refresh','Finishing',{'channel_id':c['id'],'run_id':run['id']})
    for path in ('/intelligence','/intelligence?view=channels','/intelligence/channels/'+c['id']+'/view'):
        result=next(r for r in client.get(path).json()['runs'] if r['id']==run['id'])
        assert result['status']=='running' and result['collection_status']=='completed'
        assert 'finished_at' not in result and result['progress']['phase']=='finalizing'
        assert result['system_task_id']==task['id']
    runtime.system_tasks._update(owner,task['id'],{'status':'completed'})
    assert client.get('/intelligence').json()['runs'][0]['status']=='completed'


def test_channel_auto_topics_setting_and_legacy_update_preservation(client):
    c,_=channel_and_source(client)
    assert c['auto_topics'] is False
    data={'name':c['name'],'interests':c['interests'],'auto_topics':True}
    assert client.put('/intelligence/channels/'+c['id'],json=data).json()['auto_topics'] is True
    data.pop('auto_topics')
    assert client.put('/intelligence/channels/'+c['id'],json=data).json()['auto_topics'] is True
    assert client.put('/intelligence/channels/'+c['id'],json={**data,'auto_topics':False}).json()['auto_topics'] is False
