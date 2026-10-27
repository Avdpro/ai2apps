from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from test_web_agent_mini_apps import broker
from ai2apps.research.mini_apps import WebMiniAppAdapters, SEARCH, READER
from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.services import ToolCallContext, ToolProviderError

ROOT=Path(__file__).resolve().parents[2]
def package(name):return json.loads((ROOT/'packages'/('ai2apps-'+name)/'app.yaml').read_text())['mini_apps'][0]
def setup(broker,monkeypatch,name):
    service,mounted,principal=broker;mounted.declaration=package(name);mounted.mount['app_key']=mounted.declaration['id']
    # Workload admission now verifies the persisted Session. Use a real owned
    # fixture thread instead of the previous nonexistent literal 'session'.
    from dataclasses import replace
    from ai2apps.identity import RequestPrincipal
    from ai2apps.chat import ChatRepository
    actor=replace(RequestPrincipal.legacy_local(),actor_user_id='owner')
    thread,_=ChatRepository(service.runtime.database,principal=actor).create_thread()
    monkeypatch.setattr('ai2apps.api.agent_platform._session',lambda *a:thread.session.id)
    adapter=WebMiniAppAdapters(service.runtime);adapter.broker=service
    monkeypatch.setattr(adapter,'resolve',lambda *a:(principal,mounted))
    return adapter,mounted,ToolCallContext('test',session_id=thread.session.id,actor_user_id='owner',installation_id='install',invocation_id='invocation')

@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['fast','preferred'])
async def test_search_all_uses_declared_tasks_merges_sources_and_keeps_provenance(broker,monkeypatch,mode):
    adapter,mounted,ctx=setup(broker,monkeypatch,'search-all');observed=[]
    async def wait(runtime,broker,mount,principal,task,*_):
        observed.append(task)
        source=task['capability']
        return {**task,'result':{'items':[{'url':'https://example.com/shared','title':source,'summary':'snippet'},
            {'url':'https://example.com/'+source,'title':source+' result'}]}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    result=await adapter.search({'query':'SQLite WAL','limit':5,'mode':mode},ctx)
    assert result['count']==3 and result['mini_app_id']==SEARCH
    assert [t['capability'] for t in observed]==['google','bing']
    assert all(t['input']['query']=='SQLite WAL' for t in observed)
    assert result['results'][0]['browser_task_id']==observed[0]['id']
    repo=BrowserTaskRepository(adapter.runtime.database)
    program,caller=repo.program('owner',observed[0]['id'])
    assert caller==adapter.broker.caller(mounted)
    assert program['execution_policy']['visual_locating'] is (mode!='fast')
    assert program['execution_policy']['visual_review']==('off' if mode=='fast' else 'on_recovery')
    assert program['execution_policy']['readback']
    assert not program['execution_policy']['allow_user_intervention']
    assert program['execution_policy']['timeout_seconds']==10
    assert program['site_scope']==mounted.declaration['web_agent']['capabilities'][0]['source']['site_scope']
    with pytest.raises(ValueError,match='search source'):await adapter.search({'query':'test','sources':['summarize']},ctx)

@pytest.mark.asyncio
async def test_one_engine_failure_keeps_verified_results_without_claiming_full_success(broker,monkeypatch):
    adapter,_,ctx=setup(broker,monkeypatch,'search-all')
    async def wait(runtime,broker,mount,principal,task,*_):
        if task['capability']=='google':raise RuntimeError('source unavailable')
        return {**task,'result':{'items':[{'url':'https://example.com/','title':'Evidence'}]}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    result=await adapter.search({'query':'test'},ctx)
    assert result['count']==1 and result['failures'][0]['source']=='google'

@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['fast','preferred',None])
async def test_reader_uses_package_article_program_narrows_origin_and_returns_bounded_text(broker,monkeypatch,mode):
    adapter,mounted,ctx=setup(broker,monkeypatch,'web-reader');observed=[]
    monkeypatch.setattr('ai2apps.research.mini_apps.SafeHttpClient._validate_url',lambda _,url:url)
    async def wait(runtime,broker,mount,principal,task,*_):
        observed.append((mount,task));return {**task,'result':{'url':'https://sqlite.org/wal.html','title':'WAL','text':'Evidence '*500,
            'content_kind':'description','extraction_method':'bilibili-video-content','content_warnings':['subtitle_http_403'],
            'subtitle_discovery':{'status':'subtitles_loaded','cid':123},
            'subtitle_cues':[{'start_ms':1000,'end_ms':2500,'text':'实际字幕全文'}],
            'subtitle_text':'[00:00:01.000 --> 00:00:02.500] 实际字幕全文',
            'subtitle_video_url':'https://sqlite.org/wal.html'}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    result=await adapter.fetch({'url':'https://sqlite.org/wal.html','max_chars':1000,'mode':mode},ctx)
    assert result['mini_app_id']==READER and len(result['text'])==1000 and result['truncated']
    assert result['content_kind']=='description' and result['extraction_method']=='bilibili-video-content'
    assert result['content_warnings']==['subtitle_http_403']
    assert result['subtitle_cues']==[{'start_ms':1000,'end_ms':2500,'text':'实际字幕全文'}]
    assert result['subtitle_video_url']==result['url'] and result['subtitle_discovery']['cid']==123
    used,task=observed[0];assert task['input']['max_chars']==1000
    program,_=BrowserTaskRepository(adapter.runtime.database).program('owner',task['id'])
    assert program['execution_policy']['visual_locating'] is (mode!='fast')
    assert program['execution_policy']['visual_review']==('off' if mode=='fast' else 'on_recovery')
    assert program['execution_policy']['readback']
    assert not program['execution_policy']['allow_user_intervention']
    assert program['execution_policy']['timeout_seconds']==10
    article=next(c for c in used.declaration['web_agent']['capabilities'] if c['id']=='article')
    assert article['source']['site_scope']==['https://sqlite.org/**']
    assert mounted.declaration['web_agent']['capabilities'][1]['source']['site_scope']==['https://*/**','http://*/**']

def test_read_only_network_failure_does_not_poison_later_research_calls():
    from ai2apps.agents.tool_recovery import has_mutating_effects
    assert not has_mutating_effects(('external_read','network'))
    assert not has_mutating_effects(())
    assert has_mutating_effects(('network',))
    assert has_mutating_effects(('external_read','network','billing'))
    assert has_mutating_effects(('external_read','network','workspace.write'))

@pytest.mark.asyncio
async def test_browser_action_wait_is_not_user_assistance(broker,monkeypatch):
    from contextlib import asynccontextmanager
    import asyncio,time
    from ai2apps.research.mini_apps import wait_task
    service,mounted,principal=broker;queue=asyncio.Queue();queue.put_nowait('progress')
    @asynccontextmanager
    async def subscribe():yield queue
    service.runtime.notifications=SimpleNamespace(subscribe=subscribe)
    states=iter([{'id':'task','status':'waiting_input','requires_user':False},{'id':'task','status':'completed','result':{'items':[]}}])
    monkeypatch.setattr(service,'task_declared',lambda *a:next(states))
    result=await wait_task(service.runtime,service,mounted,principal,{'id':'task'},ToolCallContext('test'),time.monotonic()+3)
    assert result['status']=='completed'

@pytest.mark.asyncio
async def test_reader_reports_missing_page_instead_of_successful_article(broker,monkeypatch):
    from ai2apps.services import ToolProviderError
    adapter,_,ctx=setup(broker,monkeypatch,'web-reader')
    monkeypatch.setattr('ai2apps.research.mini_apps.SafeHttpClient._validate_url',lambda _,url:url)
    async def wait(runtime,broker,mount,principal,task,*_):
        return {**task,'result':{'url':'https://example.com/missing','title':'Not Found','text':'Document Not Found'}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    with pytest.raises(ToolProviderError,match='page unavailable'):
        await adapter.fetch({'url':'https://example.com/missing'},ctx)

@pytest.mark.asyncio
async def test_three_sources_keep_all_per_source_results_and_interleave_read_candidates(broker,monkeypatch):
    adapter,_,ctx=setup(broker,monkeypatch,'search-all')
    async def wait(runtime,broker,mount,principal,task,*_):
        source=task['capability']
        return {**task,'result':{'items':[{'url':f'https://example.com/{source}/{i}','title':f'{source} {i}'} for i in range(5)]}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    result=await adapter.search({'query':'回锅肉','limit':5,'sources':['xiaohongshu','bilibili','google']},ctx)
    assert result['count']==15
    assert [r['search_source'] for r in result['results'][:5]]==['xiaohongshu','bilibili','google','xiaohongshu','bilibili']
    assert [(s['source'],s['status'],s['count']) for s in result['source_statuses']]==[(s,'completed',5) for s in ['xiaohongshu','bilibili','google']]

@pytest.mark.asyncio
async def test_google_redirects_keep_provenance_and_prefer_article_over_video(broker,monkeypatch):
    from ai2apps.research.provider import WebProviderError
    from ai2apps.research.search_workflow import readable_results
    adapter,_,ctx=setup(broker,monkeypatch,'search-all')
    async def wait(*args):return {'id':'google-task','result':{'items':[{'title':x,'url':'https://www.google.com/goto?url='+x} for x in ['video','article','private']]}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    def resolve(url):
        if url.endswith('private'):raise WebProviderError('Local, private, and reserved web hosts are blocked')
        return {'url':'https://www.youtube.com/watch?v=1' if url.endswith('video') else 'https://example.com/recipe','search_url':url,'redirect_chain':[url,'https://example.com/recipe']}
    monkeypatch.setattr('ai2apps.research.search_urls.resolve_google_url',resolve)
    result=await adapter.search({'query':'回锅肉','sources':['google']},ctx)
    assert result['count']==3
    assert [r['title'] for r in result['results']]==['article','video','private']
    assert result['results'][0]['search_url'].endswith('article')
    assert result['failures'][0]['phase']=='resolve_redirect'
    assert len(readable_results(result))==2

@pytest.mark.asyncio
async def test_reader_gets_only_resolved_exact_origin_and_rejects_other_origin(broker,monkeypatch):
    from ai2apps.services import ToolProviderError
    adapter,_,ctx=setup(broker,monkeypatch,'web-reader');seen=[]
    monkeypatch.setattr('ai2apps.research.search_urls.resolve_google_url',lambda url:{'url':'https://example.com/recipe','search_url':url})
    monkeypatch.setattr('ai2apps.research.mini_apps.SafeHttpClient._validate_url',lambda _,url:url)
    async def wait(runtime,broker,mount,principal,task,*_):
        seen.append((mount,task));return {**task,'result':{'url':'https://example.com/recipe','title':'Recipe','text':'Body'}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    result=await adapter.fetch({'url':'https://www.google.com/goto?url=opaque'},ctx)
    assert result['url']=='https://example.com/recipe'
    assert seen[0][1]['input']['url']=='https://example.com/recipe'
    entry=next(c for c in seen[0][0].declaration['web_agent']['capabilities'] if c['id']=='article')
    assert entry['source']['site_scope']==['https://example.com/**']
    async def outside(*_):return {'result':{'url':'https://other.example/a','text':'Body'}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',outside)
    with pytest.raises(ToolProviderError,match='left its validated article origin'):
        await adapter.fetch({'url':'https://www.google.com/goto?url=opaque'},ctx)

@pytest.mark.asyncio
async def test_completed_source_results_are_published_while_another_source_is_waiting(broker,monkeypatch):
    import asyncio
    from dataclasses import replace
    adapter,_,ctx=setup(broker,monkeypatch,'search-all')
    release=asyncio.Event();visible=asyncio.Event();updates=[]
    async def report(update):
        updates.append(update)
        if update.get('content',{}).get('results'):visible.set()
    async def wait(runtime,broker,mount,principal,task,*_):
        if task['capability']=='bing':await release.wait()
        return {**task,'result':{'items':[{'url':'https://example.com/'+task['capability'],'title':task['capability']}]}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    pending=asyncio.create_task(adapter.search({'query':'test','sources':['google','bing']},replace(ctx,progress_reporter=report)))
    try:
        await asyncio.wait_for(visible.wait(),2)
        assert not pending.done()
        snapshot=next(u['content'] for u in updates if u.get('content',{}).get('results'))
        assert snapshot['results'][0]['search_source']=='google'
        assert next(s for s in snapshot['source_statuses'] if s['source']=='bing')['status']!='completed'
    finally:release.set()
    assert len((await pending)['results'])==2

@pytest.mark.asyncio
async def test_fetch_budget_covers_resolution_and_queue_not_only_reading(monkeypatch):
    import asyncio
    original=asyncio.timeout;budgets=[]
    def short(seconds):budgets.append(seconds);return original(.01)
    monkeypatch.setattr('ai2apps.research.mini_apps.asyncio.timeout',short)
    adapter=WebMiniAppAdapters(SimpleNamespace())
    async def stalled(*a):await asyncio.sleep(1)
    adapter._fetch=stalled
    with pytest.raises(TimeoutError):await adapter.fetch({'url':'https://example.com/'},None)
    assert budgets==[10]

@pytest.mark.parametrize('state',['waiting_input','interrupted','failed'])
@pytest.mark.parametrize('kind',['authentication','login','login_required','captcha','legal_consent','cookie_consent','sensitive_input','missing_information','confirmation','blocking_prompt','unknown'])
@pytest.mark.asyncio
async def test_unattended_reader_wait_cancels_child_and_never_asks_user(monkeypatch,kind,state):
    from contextlib import asynccontextmanager
    from ai2apps.research.mini_apps import wait_task,WebMiniAppTaskError
    import asyncio,time
    task={'id':'btask_unknown','run_id':'run','execution_task_id':'node','status':state,'requires_user':True,'message':'Blocked','assistance_kind':kind}
    @asynccontextmanager
    async def subscribe():yield asyncio.Queue()
    cancelled=[]
    runtime=SimpleNamespace(notifications=SimpleNamespace(subscribe=subscribe),database=object(),events=None,
        agent_runtime=SimpleNamespace(cancel=lambda rid:cancelled.append(rid)))
    monkeypatch.setattr('ai2apps.browser.tasks.BrowserTaskRepository',lambda *a:SimpleNamespace(get=lambda *a:task))
    monkeypatch.setattr('ai2apps.browser.task_tree.TaskTreeRepository',lambda *a:SimpleNamespace(cancel=lambda *a:['run']))
    updates=[]
    async def report(text,**kw):updates.append(kw)
    with pytest.raises(WebMiniAppTaskError) as error:
        await wait_task(runtime,SimpleNamespace(task_declared=lambda *a:task),SimpleNamespace(declaration={'id':'reader'}),
            SimpleNamespace(actor_user_id='owner'),task,SimpleNamespace(report_progress=report),time.monotonic()+10,True)
    assert not error.value.details['requires_user'] and not error.value.details['help_url']
    assert cancelled==([] if state=='failed' else ['run']) and updates==[]
    assert error.value.details['failure']['code']=='read_requires_interaction'


@pytest.mark.asyncio
async def test_interactive_observer_keeps_existing_human_wait_contract(monkeypatch):
    from contextlib import asynccontextmanager
    from ai2apps.research.mini_apps import wait_task
    import asyncio,time
    queue=asyncio.Queue();queue.put_nowait('resumed')
    @asynccontextmanager
    async def subscribe():yield queue
    task={'id':'btask_interactive','status':'waiting_input','requires_user':True,'message':'Sign in','assistance_kind':'authentication'}
    states=iter([task,{**task,'status':'completed','requires_user':False}])
    runtime=SimpleNamespace(notifications=SimpleNamespace(subscribe=subscribe))
    updates=[]
    async def report(text,**kw):updates.append(kw)
    result=await wait_task(runtime,SimpleNamespace(task_declared=lambda *a:next(states)),SimpleNamespace(declaration={'id':'arbitrary-reader'}),
        SimpleNamespace(actor_user_id='owner'),task,SimpleNamespace(report_progress=report),time.monotonic()+10)
    assert result['status']=='completed'
    assert updates[0]['content']['task_progress']['requires_user']
    assert updates[0]['content']['reading_assistance'][0]['help_url'].endswith('#task=btask_interactive')


@pytest.mark.parametrize('where',['web_agent','capability','source'])
@pytest.mark.parametrize('minimum',[{'visual_locating':True},{'visual_review':'always'}])
def test_fast_search_rejects_visual_owner_floor_instead_of_waiving_it(where,minimum):
    from ai2apps.research.mini_apps import search_execution_policy
    mounted=SimpleNamespace(declaration=package('web-reader'))
    spec=mounted.declaration['web_agent'];entry=next(c for c in spec['capabilities'] if c['id']=='article')
    target={'web_agent':spec,'capability':entry,'source':entry['source']}[where]
    target['minimum_execution_policy']=minimum
    with pytest.raises(ToolProviderError,match='requiring visual assistance'):
        search_execution_policy(mounted,'article','fast')
    assert search_execution_policy(mounted,'article','preferred')=={'allow_user_intervention':False,'timeout_seconds':10}

@pytest.mark.asyncio
async def test_existing_reader_task_does_not_silently_change_visual_policy(broker,monkeypatch):
    adapter,_,ctx=setup(broker,monkeypatch,'web-reader')
    monkeypatch.setattr('ai2apps.research.mini_apps.SafeHttpClient._validate_url',lambda _,url:url)
    async def wait(runtime,broker,mount,principal,task,*_):
        return {**task,'result':{'url':'https://example.com/article','text':'actual body'}}
    monkeypatch.setattr('ai2apps.research.mini_apps.wait_task',wait)
    await adapter.fetch({'url':'https://example.com/article'},ctx)
    with pytest.raises(ValueError,match='different execution policy'):
        await adapter.fetch({'url':'https://example.com/article','mode':'fast'},ctx)
