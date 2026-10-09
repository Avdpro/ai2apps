from types import SimpleNamespace
import pytest
from ai2apps.storage import PlatformDatabase
from ai2apps.agent_builder.repository import AgentBuilderRepository
from ai2apps.intelligence import site_agents
from ai2apps.intelligence.store import IntelligenceStore


@pytest.mark.asyncio
async def test_observed_rule_compiles_and_repair_versions_same_draft(tmp_path,monkeypatch):
    db=PlatformDatabase(tmp_path/'platform.sqlite3');db.initialize()
    runtime=SimpleNamespace(database=db);principal=SimpleNamespace(actor_user_id='alice')
    async def model(runtime,request,principal,id,instruction,data,validator):
        with pytest.raises(ValueError):validator({'index':39})
        return validator({'index':0})
    monkeypatch.setattr(site_agents,'model_json',model)
    source={'name':'Site','channel_id':'channel','url':'https://example.com/news'}
    body=site_agents.LearnRequest(kind='list',url=source['url'],regions=[{'selector':'#news','sample':'Headlines','count':20}])
    first=await site_agents.learn(runtime,None,principal,source,body)
    assert first['ir']['steps'][0]['mode']=='compiled'
    assert first['ir']['steps'][0]['operation']=='extract_list'
    repo=AgentBuilderRepository(db)
    assert repo.find_site_agent('alice','example.com') is None
    assert repo.reconcile_site_agents('alice')['merged'] == []
    repo.activate_generation(first['draft_id'],first['generation_id'],'alice')
    second=await site_agents.learn(runtime,None,principal,source,body,first)
    assert second['draft_id']==first['draft_id'] and second['generation_id']!=first['generation_id']
    assert len(repo.list_generations(first['draft_id'],'alice'))==2
    with pytest.raises(Exception):repo.get_generation(first['generation_id'],'bob')
    body.url='https://other.com/news'
    with pytest.raises(ValueError):await site_agents.learn(runtime,None,principal,source,body)
    body.url=source['url'];body.kind='article'
    article=await site_agents.learn(runtime,None,principal,source,body)
    assert article['ir']['steps'][0]['operation']=='read_page'


def test_recipe_owner_and_list_url_boundaries(tmp_path):
    store=IntelligenceStore(tmp_path)
    key=site_agents.recipe_key({'url':'https://example.com/news?topic=watches&utm_source=feed'},'list')
    store.save_site_recipe('alice',key,{'generation_id':'v1'})
    assert store.site_recipe('alice',key)['generation_id']=='v1'
    assert store.site_recipe('bob',key) is None
    assert key!=site_agents.recipe_key({'url':'https://example.com/news?topic=cars'},'list')


def test_site_agent_api_validates_activation_and_reuses_across_channels(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.intelligence import create_intelligence_router
    from ai2apps.identity import RequestPrincipal
    from ai2apps.intelligence import service
    db=PlatformDatabase(tmp_path/'platform.sqlite3');db.initialize()
    runtime=SimpleNamespace(database=db,config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path/'artifacts')))
    async def plan(*args):return []
    from ai2apps.intelligence import entity_categories
    async def category_plan(*args):
        return {'categories':[{'id':'products','name':'Products','description':'Products'}], 'default_id':'products', 'assignments':{}, 'signatures':{}}
    monkeypatch.setattr(entity_categories, 'plan', category_plan)
    async def model(runtime,request,principal,id,instruction,data,validator):return validator({'index':0})
    monkeypatch.setattr(service,'plan_sections',plan);monkeypatch.setattr(site_agents,'model_json',model)
    app=FastAPI();app.include_router(create_intelligence_router(lambda:runtime,RequestPrincipal.legacy_local));client=TestClient(app)
    def source(url):
        c=client.post('/intelligence/channels',json={'name':'Test','interests':'News'}).json()
        return client.post('/intelligence/channels/'+c['id']+'/sources',json={'name':'Site','url':url}).json()
    a=source('https://example.com/news');b=source('https://example.com/news');c=source('https://example.com/other')
    base='/intelligence/sources/'+a['id']+'/site-agent/'
    candidate=client.post(base+'learn',json={'kind':'list','url':a['url'],'regions':[{'selector':'#news','sample':'Titles','count':20}]}).json()
    assert client.get(base+'list').json()['recipe'] is None
    body={'generation_id':candidate['generation_id'],'samples':10,'matched':1}
    assert client.post(base+'activate',json=body).status_code==422
    body['matched']=9
    assert client.post('/intelligence/sources/'+c['id']+'/site-agent/activate',json=body).status_code==422
    assert client.post(base+'activate',json=body).status_code==200
    assert client.get('/intelligence/sources/'+b['id']+'/site-agent/list').json()['recipe']['generation_id']==candidate['generation_id']
    assert client.get('/intelligence/sources/foreign/site-agent/list').status_code==404
    client.post(base+'invalidate',json={'kind':'list','generation_id':'stale'})
    assert client.get(base+'list').json()['recipe']
    client.post(base+'invalidate',json={'kind':'list','generation_id':candidate['generation_id']})
    assert client.get(base+'list').json()['recipe'] is None
