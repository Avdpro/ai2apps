"""Owner business behavior plus scheduler/form end-to-end fixtures."""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.intelligence.aaat import discovery, news, PROVIDER, RESEARCH
from ai2apps.intelligence.models import ChannelInput
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.services.aaat import principal_for
from ai2apps.api.router import create_ai2apps_router
from ai2apps.identity import IdentityRepository
from test_aaat_execution_flow import runtime, new_run, response, wait


def seed(runtime, owner='flow-owner'):
    store = IntelligenceStore(runtime.config.paths.artifacts_path / 'intelligence')
    channel = store.save_channel(owner, ChannelInput(name='腕表', interests='腕表新品、行业新闻', interval_hours=0).model_dump())
    now = datetime.now(timezone.utc).isoformat()
    article = {'title':'腕表新品实测','summary':'已保存新闻摘要','body':'实际保存的正文', 'published_at':now,
               'sources':[{'title':'原始新闻','url':'https://example.com/watch','published_at':now}]}
    store.import_article(owner, channel['id'], article, 'https://example.com/watch')
    return store, channel


def test_confirmation_rejects_changes_other_session_and_newer_cancellation():
    from ai2apps.intelligence.aaat import confirmed_interaction
    from ai2apps.services import ToolProviderError
    args={'query':'topic','sources':['google']}
    item=SimpleNamespace(status=SimpleNamespace(value='submitted'),ui_hints={'provider':PROVIDER,'provider_version':'1'},
        response={'result':{'capability':RESEARCH,'user_confirmed':True,'arguments':{**args,'provider':PROVIDER}}})
    items=[item]
    fake=SimpleNamespace(agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(id='run',session_id='session'),list_interactions=lambda _:items),
        app_capability_router=SimpleNamespace(providers={PROVIDER:SimpleNamespace(version='1')}))
    scope=SimpleNamespace(trace_id='run',session_id='session',invocation_id='call')
    assert confirmed_interaction(fake,args,scope) is item
    with pytest.raises(ToolProviderError): confirmed_interaction(fake,{**args,'sources':['bing']},scope)
    scope.session_id='other'
    with pytest.raises(ToolProviderError): confirmed_interaction(fake,args,scope)
    scope.session_id='session'
    fake.app_capability_router.providers[PROVIDER].version='2'
    with pytest.raises(ToolProviderError): confirmed_interaction(fake,args,scope)
    fake.app_capability_router.providers[PROVIDER].version='1'
    items.append(SimpleNamespace(status=SimpleNamespace(value='cancelled'),ui_hints={'provider':PROVIDER},response=None))
    with pytest.raises(ToolProviderError): confirmed_interaction(fake,args,scope)


@pytest.mark.asyncio
async def test_watch_news_uses_dynamic_owned_channel_and_daily_coverage(runtime):
    store, channel = seed(runtime)
    seen = []
    async def model(request):
        seen.append(request)
        systems = [m['content'] for m in request['messages'] if m['role']=='system']
        assert '腕表新品、行业新闻' not in str(systems)
        observations = [m['content'] for m in request['messages'] if m['content'] and 'AaAT discovery observations:' in str(m['content'])]
        assert channel['id'] in str(observations)
        results = [json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if any('articles' in r for r in results): return response(text='今天的腕表新闻来自已有频道，发表日期已核实。')
        return response('intelligence.news', {'channel_id':channel['id'],'days':1})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run = new_run(runtime,['intelligence.news','intelligence.research','app.collect_parameters'],prompt='今天有哪些腕表新闻？')
        done = await wait(runtime,run.id,'completed')
        assert '腕表新闻' in done.output['content']
        assert not runtime.agents.list_interactions(run.id)
        results=[step.output for step in runtime.agents.list_steps(run.id) if step.tool_name=='intelligence.news' and step.output]
        assert results[-1]['total'] == 1
        assert results[-1]['aaat_context']['coverage']['unknown_publication_dates'] == 0
    finally: await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_military_research_waits_for_sources_survives_restart_and_binds_report(runtime, monkeypatch):
    seed(runtime)
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    from ai2apps.research import search_preparation as prep, search_workflow as workflow
    monkeypatch.setattr(WebAgentMiniAppBroker,'registered',lambda self,*a:SimpleNamespace())
    monkeypatch.setattr(prep,'choices',lambda *a:[{'id':'google','name':'Google'},{'id':'bing','name':'Bing'}])
    calls=[]
    monkeypatch.setattr(prep,'begin',lambda *a,**k: {'id':'fixture-confirmation','status':'completed'})
    def confirm(*a,**k):
        calls.append(('confirm',a[4]));return {'confirmation_id':'fixture-confirmation'}
    monkeypatch.setattr(prep,'confirm',confirm)
    async def invoke(runtime,args,context):
        calls.append(('execute',context.actor_user_id))
        return {'markdown':'正文证据结论 [原始报道](https://example.com/military)',
                'articles':[{'url':'https://example.com/military','text':'实际军事新闻正文'}],
                'citations':[{'id':'1','url':'https://example.com/military','title':'原始报道'}]}
    monkeypatch.setattr(workflow,'invoke',invoke)
    values={'query':'军事新闻','days':1,'sources':['google'],'profile':'default','limit':3}
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if any(r.get('temporary') for r in results): return response(text='模型改写链接 https://wrong.example/ignored')
        return response(RESEARCH,values)
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,[RESEARCH,'app.collect_parameters'],prompt='今天有哪些军事新闻？')
        await wait(runtime,run.id,'waiting_input')
        assert not calls
        item=runtime.agents.list_interactions(run.id)[0]
        assert item.ui_hints['app_id']=='ai2apps.intelligence'
        await runtime.agent_runtime.stop();await runtime.agent_runtime.start()
        app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,
            principal_provider=lambda:IdentityRepository(runtime.database).local_principal_for('flow-owner')))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            base=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
            state=(await client.get(base)).json()
            assert any(f['key']=='sources' and len(f['options'])==2 for f in state['descriptor']['fields'])
            state=(await client.put(base,json={'revision':state['revision'],'values':values})).json()
            submitted=await client.post(base+'/submit',json={'revision':state['revision'],'values':values})
            assert submitted.status_code==200,submitted.text
        done=await wait(runtime,run.id,'completed')
        assert calls==[('confirm',{'query':values['query'],'sources':['google'],'profile':'default','limit':3,'mode':'custom','x_sort':'latest','xiaohongshu_sort':'latest','exclude_ads':True,'retain_pages':False}),('execute','flow-owner')]
        assert 'https://example.com/military' in done.output['content']
        assert 'wrong.example' not in done.output['content']
        assert len(IntelligenceStore(runtime.config.paths.artifacts_path/'intelligence').snapshot('flow-owner')['channels'])==1
    finally: await runtime.stop_background_tasks()


def test_owner_news_cards_use_owned_image_endpoint_and_original_source():
    from ai2apps.intelligence.aaat import article_view
    from ai2apps.services.aaat import validate_view
    article={'id':'owned-article','title':'News','summary':'Summary','created_at':'2026-10-21',
        'sources':[{'title':'Actual source','url':'https://example.com/original'}],
        'cover_image':{'url':'https://example.com/cover.jpg'}}
    value=validate_view(article_view([article]))
    item=value['items'][0]
    assert value['layout']=='cards' and item['url']=='https://example.com/original'
    assert item['fields']['time']=='2026-10-21' and all(c['label']=='' for c in value['columns'])
    assert item['image']['url']=='/v1/platform/intelligence/articles/owned-article/thumbnail'
    assert item['fields']['source']=='example.com'
    del article['cover_image']
    assert 'image' not in article_view([article])['items'][0]


def test_source_domains_prefer_real_urls_deduplicate_and_never_use_article_title():
    from ai2apps.intelligence.aaat import article_sources
    assert article_sources({'primary_source_url':'https://www.cnn.com/article','sources':[{'title':'Very long article title','url':'https://www.cnn.com/other'},{'url':'https://x.com/account/status/1'}]})=='www.cnn.com · x.com'
    assert article_sources({'sources':[{'title':'Article title only'}]})=='未知'
    assert article_sources({'sources':[{'url':'javascript:bad','platform':'X'}]})=='X'


def test_legacy_source_presentation_upgrade_is_owner_scoped_and_idempotent(runtime):
    from ai2apps.chat import ChatRepository,LegacyChatMessageInput
    from ai2apps.intelligence.aaat import upgrade_news_presentations
    from ai2apps.core import MessageRole
    records=[{'provider':'ai2apps.intelligence.intelligence.news','view':{'id':'news','layout':'cards','items':[{'url':'https://www.cnn.com/article','fields':{'source':'Long old article title','time':'2026-10-26T23:50:00+08:00'}}]}},
             {'provider':'different.owner','view':{'id':'news','layout':'cards','items':[{'url':'https://other.test/a','fields':{'source':'Keep exact owner value'}}]}}]
    records.extend([None,{'provider':'ai2apps.intelligence.intelligence.news','view':None},{'provider':'ai2apps.intelligence.intelligence.news','view':{'id':'news','layout':'cards','items':[None,{'fields':None}]}}])
    ChatRepository(runtime.database,runtime.events).create_thread(title='Saved cards',legacy_messages=(LegacyChatMessageInput(role=MessageRole.ASSISTANT,content='Saved answer',metadata={'aaat_views':records}),))
    with runtime.database.transaction() as db:
        before=[dict(r) for r in db.execute('SELECT id,metadata_json FROM messages')]
    upgrade_news_presentations(runtime)
    with runtime.database.transaction() as db:
        after=[dict(r) for r in db.execute('SELECT id,metadata_json FROM messages')]
    views=json.loads(next(r['metadata_json'] for r in after if 'Long old' not in r['metadata_json'] and 'aaat_views' in r['metadata_json']))['aaat_views']
    assert views[0]['view']['items'][0]['fields']['source']=='www.cnn.com'
    assert views[0]['view']['items'][0]['fields']['time']=='2026-10-26'
    assert views[1]==records[1]
    upgrade_news_presentations(runtime)
    with runtime.database.transaction() as db:assert [dict(r) for r in db.execute('SELECT id,metadata_json FROM messages')]==after
