import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from unittest.mock import AsyncMock
from ai2apps.browser.mini_apps import validate_web_agent
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.extensions.development import DevelopmentPackageLoader
from ai2apps.browser.background_executor import BackgroundExecutor
from ai2apps.browser.background_page import BackgroundPage

ROOT=Path(__file__).resolve().parents[2]

def test_search_package_uses_normal_loader_and_only_compiled_scoped_capabilities():
    package=DevelopmentPackageLoader(ROOT)._load(ROOT/'packages/ai2apps-search-all')
    entries=validate_web_agent(package.manifest['mini_apps'][0])
    assert [e['id'] for e in entries]==['google','bing','duckduckgo','brave','wikipedia','xiaohongshu','x','weibo','youtube','bilibili','plan','fast_api','summarize','review']
    for entry in entries[:10]:
        ir=compile_source(entry['source']).ir
        assert all(step['mode']=='compiled' for step in ir['steps'])
        assert all(scope.startswith('https://') and not scope.startswith('https://*') for scope in ir['site_scope'])
        assert entry['source']['inputs']['properties']['limit']['maximum']==20
    for entry in entries[:4]:
        provider=entry['id']
        assert len(entry['source']['steps'])==2
        assert all(step['arguments']['search_provider']==provider for step in entry['source']['steps'])
        assert entry['source']['steps'][1]['on']['not_found']=='failed'
        host='brave.com' if provider=='brave' else provider+'.com'
        assert all(host in scope for scope in entry['source']['site_scope'])
    assert 'web/merge.js' in package.files

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['duckduckgo','brave'])
async def test_new_engine_extraction_uses_shared_native_bidi_page(provider):
    page=BackgroundPage(None,'task-tab')
    page.call_json=AsyncMock(return_value={'provider':provider,'items':[],'empty':True})
    result=await page.extract_list({'arguments':{'search_provider':provider,'query':'watches','limit':3}})
    assert result['provider']==provider
    assert page.call_json.call_args.args[1]==[provider,3,'watches',True]

@pytest.mark.asyncio
@pytest.mark.parametrize('provider,host',[('duckduckgo','duckduckgo.com'),('brave','search.brave.com')])
async def test_new_engine_navigation_failure_is_terminal_search_failure(provider,host):
    page=SimpleNamespace(snapshot=AsyncMock(return_value={'url':'about:blank'}),navigate=AsyncMock(side_effect=TimeoutError('timeout')))
    result=await BackgroundExecutor(None).compiled(page,{'operation':'open','arguments':{'url':f'https://{host}/','search_provider':provider}},[f'https://{host}/**'])
    assert result['outcome']=='failed'
    assert result['evidence']['reason']=='search_navigation_failed'

@pytest.mark.asyncio
@pytest.mark.parametrize('result,outcome',[
    ({'items':[],'empty':True},'success'),
    ({'items':[],'classification':'needs_user','reason':'authentication'},'needs_user'),
    ({'items':[],'reason':'search_markup_unavailable'},'not_found'),
])
async def test_site_search_empty_and_assistance_results(result,outcome):
    class Page:
        async def snapshot(self):return {'url':'https://x.com/search'}
        async def extract_list(self,step):return result
    executor=BackgroundExecutor(SimpleNamespace())
    output=await executor.compiled(Page(),{'operation':'extract_list','arguments':{'search_provider':'x'}},['https://x.com/**'])
    assert output['outcome']==outcome


def test_review_is_a_shared_ai_data_task_with_bounded_inputs():
    package=DevelopmentPackageLoader(ROOT)._load(ROOT/'packages/ai2apps-search-all')
    entries=validate_web_agent(package.manifest['mini_apps'][0])
    entry=entries[-1]
    ir=compile_source(entry['source']).ir
    assert ir['steps'][0]['operation']=='ai.transform'
    assert ir['steps'][0]['ai']['tier']=='standard'
    assert entry['source']['inputs']['properties']['items']['maxItems']==200
    output=ir['steps'][0]['ai']['output_schema']['properties']['items']['items']
    assert set(output['required'])=={'id','title','summary','reason','is_ad','source_language','translated','translated_content'}
    assert output['additionalProperties'] is False

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['youtube','bilibili'])
async def test_video_reader_uses_shared_bidi_page(provider):
    page=BackgroundPage(None,'task-tab')
    page.call_json=AsyncMock(return_value={'provider':provider,'items':[],'empty':True})
    await page.extract_list({'arguments':{'search_provider':provider,'query':'watches','limit':3}})
    assert page.call_json.call_args.args[1]==[provider,3,'watches',True]

@pytest.mark.asyncio
async def test_video_spa_retry_stops_on_results_or_assistance(monkeypatch):
    import ai2apps.browser.background_page as module
    pause=AsyncMock()
    monkeypatch.setattr(module.asyncio,'sleep',pause)
    page=BackgroundPage(None,'task-tab')
    page.call_json=AsyncMock(side_effect=[{'reason':'search_page_not_loaded'},{'items':[{'title':'Video'}]}])
    result=await page.extract_list({'arguments':{'search_provider':'youtube'}})
    assert result['items'][0]['title']=='Video'
    assert pause.await_count==1
    page.call_json=AsyncMock(return_value={'classification':'needs_user','reason':'captcha'})
    await page.extract_list({'arguments':{'search_provider':'youtube'}})
    assert page.call_json.await_count==1

@pytest.mark.asyncio
async def test_video_spa_retries_are_bounded(monkeypatch):
    import ai2apps.browser.background_page as module
    monkeypatch.setattr(module.asyncio,'sleep',AsyncMock())
    page=BackgroundPage(None,'task-tab')
    page.call_json=AsyncMock(return_value={'reason':'search_page_not_loaded'})
    assert (await page.extract_list({'arguments':{'search_provider':'youtube'}}))['reason']=='search_page_not_loaded'
    assert page.call_json.await_count==7

@pytest.mark.asyncio
async def test_xhs_sort_verification_failure_is_a_source_failure_not_a_queue_interrupt():
    page=SimpleNamespace(snapshot=AsyncMock(return_value={'url':'https://www.xiaohongshu.com/search_result'}),extract_list=AsyncMock(side_effect=RuntimeError('xiaohongshu_sort_not_verified: likes')))
    result=await BackgroundExecutor(None).compiled(page,{'operation':'extract_list','arguments':{'search_provider':'xiaohongshu'}},['https://www.xiaohongshu.com/**'])
    assert result['outcome']=='not_found'
    assert result['evidence']['reason']=='xiaohongshu_sort_not_verified'

def test_summary_is_bounded_durable_read_ai_and_trusted_bundle():
    package=DevelopmentPackageLoader(ROOT)._load(ROOT/'packages/ai2apps-search-all')
    entry=next(e for e in validate_web_agent(package.manifest['mini_apps'][0]) if e['id']=='summarize')
    result=compile_source(entry['source']);assert result.valid,result.report
    assert [step['operation'] for step in result.ir['steps']]==['read_results','ai.transform','assign']
    assert result.ir['steps'][0]['arguments']['limit']==3
    assert entry['source']['inputs']['properties']['items']['maxItems']==5
    assert 'steps.read.output.articles' in result.ir['steps'][2]['arguments']['assignments'][0]['expression']

@pytest.mark.asyncio
async def test_summary_reader_skips_restricted_source_without_changing_existing_default():
    page=BackgroundPage(None,'original');page.public_url=lambda url:None
    page.read_page=AsyncMock(side_effect=[{'outcome':'restricted','reason':'paywall'},{'outcome':'success','url':'https://example.com/two','title':'Two','text':'Actual body'}])
    result=await page.read_results([{'url':'https://example.com/one','source_id':'a1'},{'url':'https://example.com/two','source_id':'a2'}],skip_restricted=True)
    assert result['outcome']=='success' and result['articles'][0]['source_id']=='a2'
    assert result['failures'][0]['reason']=='paywall'
    page.read_page=AsyncMock(return_value={'outcome':'restricted','reason':'paywall'})
    assert (await page.read_results([{'url':'https://example.com/one'}]))['outcome']=='restricted'

@pytest.mark.asyncio
async def test_read_results_from_fresh_task_checks_each_url_scope():
    page=SimpleNamespace(snapshot=AsyncMock(return_value={'url':'about:blank'}),read_results=AsyncMock(return_value={'outcome':'success','articles':[{'url':'https://example.com/a'}],'failures':[]}))
    executor=BackgroundExecutor(None)
    step={'operation':'read_results','arguments':{'items':[{'url':'https://example.com/a'}],'skip_restricted':True}}
    assert (await executor.compiled(page,step,['https://example.com/**']))['outcome']=='success'
    assert (await executor.compiled(page,step,['https://other.example/**']))['outcome']=='restricted'

@pytest.mark.asyncio
async def test_video_cover_keeps_native_observed_pixels(monkeypatch):
    from ai2apps.browser.background_page import BackgroundPage
    page=object.__new__(BackgroundPage)
    calls=[]
    async def target(script,args):
        calls.append(args)
        return {'rect':{'x':10,'y':20,'width':160,'height':90}}
    async def cover(rect,budget):
        assert rect['width']==160 and budget<=2_000_000
        return 'data:image/jpeg;base64,/9j/AA=='
    monkeypatch.setattr(page,'call_json',target)
    monkeypatch.setattr(page,'xhs_cover',cover)
    result={'items':[{'url':'https://www.youtube.com/watch?v=abc'}]}
    await page.enrich_video_covers(result)
    assert result['items'][0]['image_data_url'].startswith('data:image/jpeg;')
    assert calls==[['https://www.youtube.com/watch?v=abc']]

@pytest.mark.asyncio
async def test_xhs_unverified_sort_still_extracts_readable_results(monkeypatch):
    from ai2apps.browser.background_page import BackgroundPage
    page=BackgroundPage(None,'task-tab')
    page.ensure_xhs_sort=AsyncMock(side_effect=RuntimeError('xiaohongshu_sort_not_verified: likes'))
    page.call_json=AsyncMock(return_value={'items':[{'url':'https://www.xiaohongshu.com/explore/example','title':'Recipe'}]})
    page.enrich_xhs_notes=AsyncMock()
    result=await page.extract_list({'arguments':{'search_provider':'xiaohongshu','xiaohongshu_sort':'likes'}})
    assert result['items'][0]['title']=='Recipe'
    assert result['sort_warning']=='xiaohongshu_sort_not_verified'
    assert result['sort_verified'] is False
    assert page.ensure_xhs_sort.await_args_list[1].args==('general',)
    page.enrich_xhs_notes.assert_awaited_once()

@pytest.mark.asyncio
async def test_xhs_checks_both_sites_in_same_profile_and_prefers_logged_in(monkeypatch):
    from ai2apps.browser.background_page import BackgroundPage
    import ai2apps.browser.background_page as module
    monkeypatch.setattr(module.asyncio,'sleep',AsyncMock())
    connection=SimpleNamespace(command=AsyncMock(side_effect=[{'context':'probe-cn'},{},{'context':'probe-global'},{}]))
    page=BackgroundPage(connection,'search-task')
    page.user_context='profile-context'
    page.navigate=AsyncMock()
    page.call_json=AsyncMock(side_effect=[{'state':'logged_out'},{'state':'logged_in'}])
    url=await page.select_xhs_site('https://www.xiaohongshu.com/search_result?keyword=recipe')
    assert url=='https://www.rednote.com/search_result?keyword=recipe'
    assert page.context_id=='search-task'
    assert page.xhs_site_selection['verified_login']
    assert page.navigate.await_count==2
    creates=[c for c in connection.command.await_args_list if c.args[0]=='browsingContext.create']
    assert all(c.args[1]['userContext']=='profile-context' for c in creates)
    assert [c.args[1]['context'] for c in connection.command.await_args_list if c.args[0]=='browsingContext.close']==['probe-cn','probe-global']
