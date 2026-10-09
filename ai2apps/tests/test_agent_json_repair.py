from types import SimpleNamespace

import pytest

from ai2apps.agents.browser_builder import browser_builder_executor
from ai2apps.agents.json_output import MAX_JSON_REPAIRS, parse_model_json, repair_json_request
from ai2apps.agents.models import CompleteAction, FailAction, ModelCallAction, RunStepStatus


def reply(content):
    return {'choices': [{'message': {'content': content}}]}


def execution(operation, completed):
    step = {'id': 'data', 'operation': operation, 'ai': {
        'tier': 'standard', 'instruction': 'Extract the observed title',
        'output_schema': {'type': 'object', 'required': ['title'],
                          'properties': {'title': {'type': 'string'}}}},
        'on': {'success': 'done', 'failed': 'failed'}}
    return SimpleNamespace(definition=SimpleNamespace(max_steps=30),
        run=SimpleNamespace(input={'parameters': {'ir': {'start': 'data', 'steps': [step]},
            'invocation_input': {}, 'ai_model_routes': {'standard': 'deepseek-test'}}}),
        interactions=(), step=lambda key: completed.get(key))


@pytest.mark.parametrize('operation', ['ai.extract', 'ai.classify', 'ai.transform'])
def test_durable_json_and_schema_repairs_share_budget_and_resume(operation):
    completed = {}
    ctx = execution(operation, completed)
    action = browser_builder_executor(ctx)
    assert isinstance(action, ModelCallAction)
    original = action.request
    for index, invalid in enumerate(["{'title': 'x'}", '{"title": 123}']):
        completed[action.call_id] = SimpleNamespace(status=RunStepStatus.COMPLETED, output=reply(invalid))
        action = browser_builder_executor(ctx)
        assert isinstance(action, ModelCallAction)
        assert action.call_id.endswith(f':json-repair:{index+1}')
        assert action.request['model'] == original['model']
        assert action.request['messages'][:2] == original['messages']
        assert invalid in action.request['messages'][-2]['content']
        again = browser_builder_executor(ctx)
        assert again.call_id == action.call_id
        assert again.request == action.request
    completed[action.call_id] = SimpleNamespace(status=RunStepStatus.COMPLETED,
        output=reply('{"title":"Observed title"}'))
    result = browser_builder_executor(ctx)
    assert isinstance(result, CompleteAction)
    assert result.output['result']['title'] == 'Observed title'


def test_exhaustion_and_transport_failure_do_not_retry_forever():
    completed = {}
    ctx = execution('ai.extract', completed)
    for _ in range(MAX_JSON_REPAIRS + 1):
        action = browser_builder_executor(ctx)
        assert isinstance(action, ModelCallAction)
        completed[action.call_id] = SimpleNamespace(status=RunStepStatus.COMPLETED, output=reply('bad'))
    assert isinstance(browser_builder_executor(ctx), FailAction)
    completed = {'browser-ai:data': SimpleNamespace(status=RunStepStatus.FAILED, output=None)}
    assert isinstance(browser_builder_executor(execution('ai.extract', completed)), FailAction)


def test_parser_and_repair_preserve_values_without_executing_or_guessing():
    assert parse_model_json(reply('```json\n{"title":"原文"}\n```')) == {'title':'原文'}
    with pytest.raises(ValueError):
        parse_model_json(reply("{'title':'原文'}"))
    with pytest.raises(ValueError):
        parse_model_json(reply('{"title": NaN}'))
    request = {'model': 'same-model', 'messages':[{'role':'user','content':'original schema'}]}
    repaired = repair_json_request(request, reply('bad'), ValueError('expected object'))
    assert len(request['messages']) == 1
    assert repaired['messages'][-2]['content'] == 'bad'
    assert 'expected object' in repaired['messages'][-1]['content']


@pytest.mark.asyncio
async def test_presentation_uses_same_budget_and_unique_repair_ids():
    import json
    from unittest.mock import AsyncMock
    from starlette.responses import Response
    from ai2apps.api.agent_platform import _create_presentation_for_result
    valid = {'version':1, 'view':'key_value', 'data_path':'$',
             'fields':[{'path':'title','label':'Title'}], 'show_unmapped_fields':True}
    responses = [Response(json.dumps(reply(value))) for value in ['bad', '{}', json.dumps(valid)]]
    invoke = AsyncMock(side_effect=responses)
    model = SimpleNamespace(id='deepseek-test', endpoints={'chat_completions':'/v1/chat/completions'})
    runtime = SimpleNamespace(model_manager=SimpleNamespace(resolve_default_model=lambda _:model.id),
        model_invocations=SimpleNamespace(model=lambda _:model,
            context_for_actor=lambda *a, **k:None, invoke_foreground_json=invoke))
    result = await _create_presentation_for_result(runtime=runtime,
        principal=SimpleNamespace(actor_user_id='owner'), http_request=None,
        result={'title':'Observed'}, locale='zh', request_id='test', session_id=None)
    assert isinstance(result, dict), result
    assert result['presentation']['fields'][0]['path'] == 'title'
    assert invoke.await_count == 3
    ids = [call.kwargs['request_id'] for call in invoke.await_args_list]
    assert len(set(ids)) == 3
