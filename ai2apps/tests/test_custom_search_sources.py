import pytest

from ai2apps.agent_builder.compiler import compile_source
from ai2apps.browser.custom_search import CustomSearchRepository, discover_source, public_url, resolve_source, search_source
from ai2apps.browser.background_planner import validate_completion
from ai2apps.storage import PlatformDatabase


@pytest.mark.parametrize('url', ['http://example.com', 'https://localhost/', 'https://127.0.0.1/',
    'https://10.0.0.1/', 'https://user:secret@example.com/', 'https://example.com:8888/',
    'https://*.example.com/', 'https://server.internal/'])
def test_custom_urls_cannot_grant_private_or_wildcard_scope(url):
    with pytest.raises(ValueError): public_url(url)


def test_host_authored_discovery_and_query_programs_compile():
    url = 'https://en.wikipedia.org/wiki/Main_Page'
    for source in [discover_source(url), search_source({'url': url, 'kind': 'web'})]:
        compiled = compile_source(source)
        assert compiled.valid, compiled.report
        assert compiled.ir['site_scope'] == ['https://en.wikipedia.org/**']
    program = compile_source(search_source({'url': url, 'kind': 'web'})).ir
    assert program['steps'][1]['mode'] == 'interpreted'
    assert program['steps'][1]['arguments']['read_only'] is True
    assert program['steps'][2]['arguments']['mini_app_list_recovery'] is True


def test_name_resolution_is_a_bounded_ai_task_without_browser_operations():
    source = resolve_source()
    result = compile_source(source)
    assert result.valid, result.report
    assert [step['operation'] for step in result.ir['steps']] == ['ai.transform']
    step = result.ir['steps'][0]
    assert step['ai']['tier'] == 'standard'
    assert step['ai']['output_schema']['properties']['candidates']['maxItems'] == 3
    assert source['inputs']['required'] == ['description', 'locale']


def analyzed_task(ref='search'):
    return {'capability': 'discover_source', 'status': 'completed', 'input': {'url': 'https://example.com/'},
        'result': {'assigned': {'source_report': {'metadata': {'name': 'Example', 'description': 'Example search',
          'kind': 'web', 'search_control_ref': ref}, 'observed': {'url': 'https://example.com/',
          'items': [{'ref': 'search', 'tag': 'input', 'text': 'Search'}]}}}}}


def test_private_persistence_deduplication_and_deletion(tmp_path):
    db = PlatformDatabase(tmp_path/'db.sqlite'); db.initialize()
    repo = CustomSearchRepository(db)
    saved = repo.save('owner-a', analyzed_task())
    assert repo.save('owner-a', analyzed_task())['id'] == saved['id']
    assert len(repo.list('owner-a')) == 1
    assert repo.list('owner-b') == []
    repo.delete('owner-b', saved['id'])
    assert len(repo.list('owner-a')) == 1
    repo.delete('owner-a', saved['id'])
    assert not repo.list('owner-a')


def test_invented_search_control_and_outside_origin_cannot_be_saved(tmp_path):
    db = PlatformDatabase(tmp_path/'db.sqlite'); db.initialize()
    repo = CustomSearchRepository(db)
    with pytest.raises(ValueError, match='search entry'): repo.save('owner', analyzed_task('invented'))
    task = analyzed_task();task['result']['assigned']['source_report']['observed']['url'] = 'https://another.example/'
    with pytest.raises(ValueError, match='origin'): repo.save('owner', task)


def test_query_step_cannot_complete_without_actual_input():
    step = {'operation': 'inspect', 'arguments': {'custom_search': True}}
    with pytest.raises(ValueError, match='actual query input'):
        validate_completion(step, [{'outcome': 'success', 'source_step': {'operation': 'inspect'}}])
    validate_completion(step, [{'outcome': 'success', 'source_step': {'operation': 'input'}}])


@pytest.mark.asyncio
async def test_native_search_input_with_null_role_is_supported():
    from ai2apps.browser.background_executor import BackgroundExecutor
    typed = []
    class Page:
        context_id = 'tab'
        async def snapshot(self): return {'url': 'https://example.com/'}
        async def find_target(self, *a): return {'name': 'Search', 'role': None, 'type': 'search'}
        async def pointer_to(self, *a, **k): return {}
        async def type_text(self, value, **kwargs): typed.append((value, kwargs))
        async def related_windows(self): return []
    result = await BackgroundExecutor(None).compiled(Page(), {'operation': 'input',
        'description': 'Search and press Enter', 'arguments': {'value': 'DeepSeek',
        'foundation_read_only': True, 'foundation_search_goal': 'Search'}}, ['https://example.com/**'])
    assert result['outcome'] == 'success'
    assert typed[0][0] == 'DeepSeek'
    assert typed[0][1]['submit'] is True


@pytest.mark.asyncio
async def test_custom_search_never_clicks_post_even_if_planner_requests_it():
    from ai2apps.browser.background_executor import BackgroundExecutor
    class Page:
        context_id = 'tab'
        async def snapshot(self): return {'url': 'https://example.com/'}
        async def find_target(self, *a): return {'name': 'Post', 'role': None}
    result = await BackgroundExecutor(None).compiled(Page(), {'operation': 'click',
        'description': 'Search', 'arguments': {'custom_search': True}, 'target': {'intent': 'Post'}},
        ['https://example.com/**'])
    assert result['outcome'] == 'restricted'


def test_github_uses_compiled_repository_search_without_navigation_planner():
    source = search_source({'url': 'https://github.com/', 'kind': 'web'})
    compiled = compile_source(source)
    assert compiled.valid, compiled.report
    assert [s['mode'] for s in compiled.ir['steps']] == ['compiled', 'compiled']
    assert source['steps'][0]['on']['success'] == 'results'
    assert source['site_scope'] == ['https://github.com/**']


@pytest.mark.asyncio
async def test_github_query_is_encoded_without_injecting_search_parameters():
    from ai2apps.browser.background_executor import BackgroundExecutor
    from urllib.parse import parse_qs, urlsplit
    urls = []
    class Page:
        async def snapshot(self): return {'url': 'https://github.com/search'}
        async def navigate(self, url, delay): urls.append(url); return {'url': url}
    result = await BackgroundExecutor(None).compiled(Page(), {'operation': 'open', 'arguments': {
        'url': 'https://github.com/search', 'github_repository_search': True,
        'query': '中文 &type=code # test'}}, ['https://github.com/**'])
    assert result['outcome'] == 'success'
    assert parse_qs(urlsplit(urls[0]).query) == {'q': ['中文 &type=code # test'], 'type': ['repositories']}


@pytest.mark.asyncio
@pytest.mark.parametrize('failure,reason', [(TimeoutError(), 'custom_search_planner_timeout'),
    (ValueError('open_url_required'), 'custom_search_planner_invalid_action')])
async def test_custom_planning_failures_finish_without_browser_action(failure, reason):
    from ai2apps.browser.background_executor import BackgroundExecutor
    class Page:
        async def observation(self): return {'context': 'tab', 'url': 'https://example.com/'}
        async def related_windows(self): return []
    class Planner:
        async def next(self, **kwargs): raise failure
    executor = BackgroundExecutor(None); executor.planner = Planner()
    result = await executor.adaptive(Page(), {'step': {'operation': 'inspect',
        'arguments': {'custom_search': True}}, 'site_scope': ['https://example.com/**']}, None)
    assert result['outcome'] == 'failed'
    assert result['evidence']['reason'] == reason
    assert result['evidence']['attempts'] == []
