import pytest

from ai2apps.browser.background_executor import BackgroundExecutor
from ai2apps.browser.mini_apps import resilient_source
from ai2apps.browser.list_recovery import eligible, selected_result


def test_host_policy_copies_source_and_only_enables_list_reads():
    source = {'steps': [{'operation': 'extract_list', 'execution': {'mode': 'compiled'}},
                        {'operation': 'click', 'execution': {'mode': 'compiled'}}]}
    changed = resilient_source(source)
    assert 'arguments' not in source['steps'][0]
    assert changed['steps'][0]['arguments']['mini_app_list_recovery'] is True
    assert 'arguments' not in changed['steps'][1]
    assert changed['steps'][0]['execution']['mode'] == 'compiled'


@pytest.mark.parametrize('url,provider,valid', [
    ('https://x.com/person/status/123', 'x', True),
    ('https://x.com/search?q=test', 'x', False),
    ('https://x.com.evil/status/123', 'x', False),
    ('https://www.xiaohongshu.com/explore/123', 'xiaohongshu', True),
    ('https://youtube.com/watch?v=123', 'youtube', True),
    ('https://youtube.com/results?q=123', 'youtube', False),
    ('https://user@x.com/p/status/123', 'x', False),
])
def test_recovery_keeps_observed_content_destinations(url, provider, valid):
    assert eligible({'url': url}, provider) is valid


def observed():
    return {'page_url': 'https://x.com/search', 'page_title': 'Search', 'items': [
        {'id': 'c0', 'url': 'https://x.com/p/status/123', 'title': 'Post',
         'content': 'Actual post text', 'image_url': '', 'is_ad': False}]}


@pytest.mark.parametrize('ids', [['invented'], ['c0', 'c0'], [], [{'url': 'https://invented'}]])
def test_unobserved_or_invalid_model_selection_is_rejected(ids):
    with pytest.raises(ValueError):
        selected_result(observed(), ids, {})


@pytest.mark.asyncio
async def test_drift_recovery_uses_actual_dom_and_cannot_invent_fields():
    executor = BackgroundExecutor(None)
    class Page:
        context_id = 'tab'
        async def validate_context(self): pass
        async def call_json(self, script, args): return observed()
    async def compiled(*args):
        return {'outcome': 'not_found', 'evidence': {'reason': 'search_markup_unavailable'}}
    async def select(*args): return ['c0']
    executor.compiled = compiled
    executor.planner.select_list = select
    request = {'step': {'operation': 'extract_list', 'mode': 'compiled', 'arguments': {
        'mini_app_list_recovery': True, 'search_provider': 'x'}}, 'site_scope': ['https://x.com/**']}
    result = await executor.execute(Page(), request, None)
    assert result['outcome'] == 'success'
    item = result['evidence']['result']['items'][0]
    assert item['url'] == observed()['items'][0]['url']
    assert item['content'] == 'Actual post text'
    async def invented(*args): return ['c999']
    executor.planner.select_list = invented
    assert (await executor.execute(Page(), request, None))['outcome'] == 'not_found'


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome,reason', [('needs_user', 'captcha'), ('restricted', 'site_scope'),
    ('not_found', 'xiaohongshu_sort_unverified'), ('not_found', 'provider_unavailable')])
async def test_access_or_sort_failures_do_not_enter_recovery(outcome, reason):
    executor = BackgroundExecutor(None)
    class Page:
        context_id = 'tab'
        async def validate_context(self): pass
    async def compiled(*args): return {'outcome': outcome, 'evidence': {'reason': reason}}
    async def forbidden(*args): raise AssertionError('Must not recover this failure')
    executor.compiled = compiled
    executor.recover_list = forbidden
    request = {'step': {'operation': 'extract_list', 'mode': 'compiled',
                       'arguments': {'mini_app_list_recovery': True}}}
    assert (await executor.execute(Page(), request, None))['outcome'] == outcome


@pytest.mark.asyncio
async def test_compiled_success_does_not_call_ai():
    executor = BackgroundExecutor(None)
    class Page:
        context_id = 'tab'
        async def validate_context(self): pass
    async def compiled(*args): return {'outcome': 'success', 'evidence': {'result': {'items': []}}}
    async def forbidden(*args): raise AssertionError('Compiled success must not call AI')
    executor.compiled = compiled
    executor.recover_list = forbidden
    request = {'step': {'operation': 'extract_list', 'mode': 'compiled',
                       'arguments': {'mini_app_list_recovery': True}}}
    assert (await executor.execute(Page(), request, None))['outcome'] == 'success'


@pytest.mark.asyncio
async def test_recovery_rechecks_site_scope_before_model_selection():
    executor = BackgroundExecutor(None)
    class Page:
        async def call_json(self, *args): return observed()
    async def forbidden(*args): raise AssertionError('Outside scope must not reach AI')
    executor.planner.select_list = forbidden
    result = await executor.recover_list(Page(), {'step': {'arguments': {}},
        'site_scope': ['https://another.example/**']}, None, {'evidence': {}})
    assert result['outcome'] == 'restricted'
