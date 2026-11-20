"""Owner business behavior plus scheduler/form end-to-end fixtures."""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest
from ai2apps.intelligence.aaat import discovery, news, PROVIDER, RESEARCH
from ai2apps.intelligence.models import ChannelInput
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.services.aaat import principal_for
from test_aaat_execution_flow import runtime, new_run, response, wait


def seed(runtime, owner='flow-owner'):
    store = IntelligenceStore(runtime.config.paths.artifacts_path / 'intelligence')
    channel = store.save_channel(owner, ChannelInput(name='腕表', interests='腕表新品、行业新闻', interval_hours=0).model_dump())
    now = datetime.now(timezone.utc).isoformat()
    article = {'title':'腕表新品实测','summary':'已保存新闻摘要','body':'实际保存的正文', 'published_at':now,
               'sources':[{'title':'原始新闻','url':'https://example.com/watch','published_at':now}]}
    store.import_article(owner, channel['id'], article, 'https://example.com/watch')
    return store, channel


@pytest.mark.asyncio
async def test_refresh_requires_channel_without_parameter_review(runtime):
    from jsonschema import Draft202012Validator
    from ai2apps.identity import RequestPrincipal

    provider = runtime.app_capability_router.providers['ai2apps.intelligence.intelligence.refresh']
    contract = await provider.describe(RequestPrincipal.legacy_local())
    validator = Draft202012Validator(contract['effective_schema'])
    assert not contract['selection_required']
    assert validator.is_valid({'channel_id':'observed-channel'})
    assert not validator.is_valid({})


@pytest.mark.asyncio
async def test_refresh_busy_is_a_definite_non_submission(runtime, monkeypatch):
    from ai2apps.intelligence import aaat
    from ai2apps.intelligence.store import ChannelRefreshBusy

    monkeypatch.setattr(aaat, 'principal_for', lambda *_: SimpleNamespace(actor_user_id='flow-owner'))
    def already_running(*args, **kwargs):
        raise ChannelRefreshBusy('Channel already refreshing')
    monkeypatch.setattr(runtime.intelligence_collector, 'submit', already_running)
    async def unexpected_follow(*args, **kwargs):
        pytest.fail('A rejected invocation must not follow or cancel another owner job')
    monkeypatch.setattr(runtime.system_tasks, 'follow', unexpected_follow)
    receipt = await aaat.refresh(runtime, {'channel_id':'channel'},
                                 SimpleNamespace(invocation_id='invocation', session_id='session'))
    assert receipt['status'] == 'already_refreshing'
    assert receipt['submitted'] is False


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
async def test_temporary_research_runs_shared_search_without_parameter_form(runtime, monkeypatch):
    from ai2apps.browser.builtin_mini_apps import definitions
    from ai2apps.browser.mini_apps import WebAgentMiniAppBroker
    from ai2apps.identity import IdentityRepository, OrganizationType, RequestPrincipal
    from ai2apps.messager.bots import REGISTRATION, install
    from ai2apps.research.mini_apps import WebMiniAppAdapters
    from ai2apps.research import search_workflow as workflow
    from test_bot_dialogue import job_wait

    IdentityRepository(runtime.database).bind_installation(
        installation_id='local', cloud_device_id='local-device', organization_id='local',
        organization_type=OrganizationType.HOUSEHOLD, core_user_id='local',
        billing_account_id='local', access_epoch=1)
    seed(runtime, 'local')
    install(runtime)
    actor = RequestPrincipal.legacy_local()
    bot = runtime.messager_bots.create('local', 'News fixture', 'Find fresh AI news and cite original sources')
    access = runtime.messager_bot_app_access
    catalog = access.catalog('local', bot['id'])
    provider = runtime.app_capability_router.providers[PROVIDER]
    access.save('local', bot['id'], catalog['revision'], catalog['review_hash'],
                [{'app_id': access.target(provider), 'enabled': True}])
    session_id = runtime.app_chat.open(actor, REGISTRATION, {'bot_id': bot['id']}, {})
    mini = next(item for item in definitions()[0] if item['id'] == 'ai2apps.search-all')
    mounted = SimpleNamespace(declaration=mini, mount={'effective_digest': 'fixture'})
    monkeypatch.setattr(WebAgentMiniAppBroker, 'registered', lambda *args: mounted)
    monkeypatch.setattr(workflow, 'resolve_task_model', lambda *args: 'fixture')
    calls = []
    url = 'https://example.com/ai-news'

    async def search(self, args, context):
        calls.append(('search', args['query'], args['sources'], args['profile'], args['limit']))
        return {'query': args['query'], 'results': [{'url': url, 'title': 'AI news',
                    'browser_task_id': 'source', 'search_source': 'google'}]}

    async def read(self, args, context):
        calls.append(('read', args['url']))
        return {'url': url, 'title': 'AI news', 'text': 'Original article body with a documented AI release.'}

    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:
            return response(text=json.dumps({'kind': 'task', 'title': '今日 AI 新闻', 'text': 'Queued'}))
        if 'tools' not in request:
            return response(text=json.dumps({'overview': 'AI news', 'points': [
                {'text': 'A documented AI release', 'source_ids': ['1']}], 'limitations': ''}))
        results = [json.loads(message['content']) for message in request['messages'] if message['role'] == 'tool']
        if any(result.get('temporary') for result in results):
            return response(text='Unverified link https://wrong.example/ignored')
        if not any(tool['function']['name'].startswith('intelligence__research_') for tool in request['tools']):
            return response('app.describe', {'capability': RESEARCH})
        return response(RESEARCH, {'query': 'AI 新闻', 'provider': PROVIDER})

    monkeypatch.setattr(WebMiniAppAdapters, 'search', search)
    monkeypatch.setattr(WebMiniAppAdapters, 'fetch', read)
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source = runtime.messager_dialogue.submit(actor, bot['id'], session_id, 'research-defaults',
                                                  '看看今天有什么值得注意的AI新闻', 'fixture', [])
        job = await job_wait(runtime, source, 'completed')
        run_id = job['worker_run']
        done = await wait(runtime, run_id, 'completed')
        assert not runtime.agents.list_interactions(run_id)
        assert calls == [('search', 'AI 新闻', ['google', 'bing'], 'default', 3), ('read', url)]
        assert url in done.output['content'] and 'wrong.example' not in done.output['content']
        child, = runtime.agents.list_children(run_id)
        assert child.status.value == 'completed'
        with runtime.database.transaction() as db:
            task, = db.execute('SELECT * FROM intelligence_research_tasks').fetchall()
        assert task['id'] == child.input['origin_invocation']
        assert any(url in message['content'] for message in runtime.app_chat.message_page(actor, session_id)['items'])
        assert len(IntelligenceStore(runtime.config.paths.artifacts_path/'intelligence').snapshot('local')['channels']) == 1
    finally:
        await runtime.stop_background_tasks()


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


@pytest.mark.asyncio
async def test_channel_html_aaat_defaults_actual_task_and_session_attachment(runtime,monkeypatch):
    import asyncio
    from ai2apps.intelligence import export_aaat
    from ai2apps.agents.artifact_outputs import output_artifacts
    from ai2apps.services import ToolProviderError
    _,channel=seed(runtime)
    seen=[];original=export_aaat.execute
    async def capture(rt,args,context):
        seen.append((dict(args),context));return await original(rt,args,context)
    monkeypatch.setattr(export_aaat,'execute',capture)
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if any(r.get('files') for r in results):return response(text='HTML file is ready.')
        return response('intelligence.export_html',{'channel_id':channel['id']})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['intelligence.export_html'],prompt='输出腕表频道HTML')
        done=await wait(runtime,run.id,'completed')
        steps=runtime.agents.list_steps(run.id)
        output=next(s.output for s in reversed(steps) if s.tool_name=='intelligence.export_html' and s.output and s.output.get('files'))
        task=runtime.system_tasks.get('flow-owner',output['export_id'])
        assert task['status']=='completed' and task['kind']=='intelligence.export'
        payload=task['payload'];assert payload['quality']=='reading' and payload['include_toc'] is False
        assert (datetime.fromisoformat(payload['until'])-datetime.fromisoformat(payload['since'])).total_seconds()==86400
        assert output['published'] is False and output['summary']['articles']==1
        files=output_artifacts(steps,runtime.workspace,run.session_id)
        assert len(files)==1 and files[0]['media_type']=='text/html'
        assert b'<html' in runtime.workspace.artifact_path(runtime.workspace.get_artifact(run.session_id,files[0]['artifact_id'])).read_bytes()
        args,context=seen[-1]
        replay=await original(runtime,args,context)
        assert replay['export_id']==output['export_id'] and replay['files']==output['files']
        with pytest.raises(ToolProviderError,match='parameters changed'):await original(runtime,{**args,'hours':48},context)
        with runtime.database.transaction() as db:
            assert db.execute("select count(*) from system_tasks where kind='intelligence.export'").fetchone()[0]==1
            assert db.execute('select count(*) from gallery_assets').fetchone()[0]==0
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_html_export_cancellation_and_foreign_channel_do_not_create_outputs(runtime,monkeypatch):
    from dataclasses import replace
    from ai2apps.services.models import ToolCallContext
    from ai2apps.intelligence.export_aaat import execute
    from ai2apps.identity import IdentityRepository
    import asyncio
    _,channel=seed(runtime);_,foreign=seed(runtime,'other-owner')
    run=new_run(runtime,['intelligence.export_html'])
    principal=IdentityRepository(runtime.database).local_principal_for('flow-owner')
    context=replace(ToolCallContext.from_principal(principal,caller_id='test',session_id=run.session_id,trace_id=run.id),invocation_id='cancel-fixture')
    async def cancelled(*args,**kwargs):raise asyncio.CancelledError()
    monkeypatch.setattr(runtime.system_tasks,'follow',cancelled)
    with pytest.raises(KeyError):await execute(runtime,{'channel_id':foreign['id']},context)
    with runtime.database.transaction() as db:assert db.execute("select count(*) from system_tasks where kind='intelligence.export'").fetchone()[0]==0
    with pytest.raises(asyncio.CancelledError):await execute(runtime,{'channel_id':channel['id']},context)
    await runtime.system_tasks.tick()
    with runtime.database.transaction() as db:
        row=db.execute("select status from system_tasks where kind='intelligence.export'").fetchone();assert row[0]=='cancelled'
    assert not list(runtime.workspace.list_artifacts(run.session_id))


@pytest.mark.asyncio
async def test_failed_html_export_has_no_chat_attachment(runtime,monkeypatch):
    from ai2apps.intelligence import html_export
    from ai2apps.agents.artifact_outputs import output_artifacts
    _,channel=seed(runtime)
    async def failed(*args,**kwargs):raise ValueError('Fixture export failure')
    monkeypatch.setattr(html_export,'build_html',failed)
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if any(r.get('status')=='failed' for r in results):return response(text='Export failed; no file was created.')
        return response('intelligence.export_html',{'channel_id':channel['id']})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['intelligence.export_html'])
        await wait(runtime,run.id,'completed')
        steps=runtime.agents.list_steps(run.id)
        output=next(s.output for s in reversed(steps) if s.tool_name=='intelligence.export_html' and s.output and s.output.get('status')=='failed')
        assert output['aaat_context']['status']=='partial' and 'files' not in output
        assert not output_artifacts(steps,runtime.workspace,run.session_id)
        assert runtime.system_tasks.get('flow-owner',output['export_id'])['status']=='failed'
    finally:await runtime.stop_background_tasks()
