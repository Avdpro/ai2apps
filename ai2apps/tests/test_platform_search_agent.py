from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai2apps.agent_builder.foundations import foundation_ir
from ai2apps.agent_builder.calls import bind_values
from ai2apps.agents.browser_builder import browser_builder_executor
from ai2apps.agents.models import CompleteAction, FailAction
from ai2apps.browser.background_executor import BackgroundExecutor
from test_web_agent_calls import context, respond


def test_search_default_and_fallback_are_compiled_and_encode_query():
    ir = foundation_ir('builtin:web:search', 'web.search')
    assert all(step['mode'] == 'compiled' for step in ir['steps'])
    action = browser_builder_executor(context(ir, {'query':'腕表 & clock?','limit':10}))
    assert action.request['step']['arguments']['url'] == 'https://www.google.com/search?q=%E8%85%95%E8%A1%A8%20%26%20clock%3F'
    records = [respond(action, {'outcome':'success','evidence':{'result':{}}})]
    action = browser_builder_executor(context(ir, {'query':'腕表 & clock?','limit':10}, interactions=records))
    assert action.request['step']['arguments']['limit'] == 10
    records.append(respond(action, {'outcome':'not_found','evidence':{'reason':'no_valid_search_results'}}))
    action = browser_builder_executor(context(ir, {'query':'腕表 & clock?','limit':10}, interactions=records))
    assert action.request['step']['arguments']['url'].startswith('https://www.bing.com/search?q=')
    records.append(respond(action, {'outcome':'success','evidence':{'result':{}}}))
    action = browser_builder_executor(context(ir, {'query':'腕表 & clock?','limit':10}, interactions=records))
    result = {'query':'腕表 & clock?','provider':'bing','count':1,'items':[{'title':'Watch','url':'https://example.org/article','summary':''}]}
    records.append(respond(action, {'outcome':'success','evidence':{'result':result}}))
    done = browser_builder_executor(context(ir, {'query':'腕表 & clock?','limit':10}, interactions=records))
    assert isinstance(done, CompleteAction)
    assert done.output['result'] == result


@pytest.mark.asyncio
async def test_empty_results_and_navigation_timeout_trigger_fallback():
    page = SimpleNamespace(snapshot=AsyncMock(return_value={'url':'https://www.google.com/search?q=test'}),
        navigate=AsyncMock(side_effect=TimeoutError('navigation timeout')),
        extract_list=AsyncMock(return_value={'items':[], 'reason':'unexpected_search_page'}))
    executor = BackgroundExecutor(None)
    ir = foundation_ir('builtin:web:search', 'web.search')
    opened = await executor.compiled(page, bind_values(ir['steps'][0], {'query':'test','limit':10}), ir['site_scope'])
    assert opened['outcome'] == 'failed'
    extracted = await executor.compiled(page, ir['steps'][1], ir['site_scope'])
    assert extracted['outcome'] == 'not_found'


def test_both_engines_fail_without_false_success():
    ir = foundation_ir('builtin:web:search', 'web.search')
    records=[]
    for expected in ('google', 'bing'):
        action=browser_builder_executor(context(ir, {'query':'test'}, interactions=records))
        assert action.request['step']['arguments']['search_provider'] == expected
        records.append(respond(action, {'outcome':'failed','evidence':{'reason':'search_navigation_failed'}}))
    assert isinstance(browser_builder_executor(context(ir, {'query':'test'}, interactions=records)), FailAction)


def test_search_call_supplies_default_limit_without_ai():
    from ai2apps.agent_builder.calls import resolve_calls
    from ai2apps.agent_builder.compiler import compile_source
    ir=compile_source({'steps':[{'name':'search','operation':'agent.call',
        'arguments':{'agent_id':'builtin:web:search','capability':'web.search',
            'parameters':{'query':'test'}}}]}).ir
    ir=resolve_calls(SimpleNamespace(), 'owner', ir)
    opened=browser_builder_executor(context(ir))
    records=[respond(opened, {'outcome':'success','evidence':{'result':{}}})]
    extract=browser_builder_executor(context(ir, interactions=records))
    assert extract.request['step']['arguments']['limit']==10
    assert extract.request['step']['mode']=='compiled'
