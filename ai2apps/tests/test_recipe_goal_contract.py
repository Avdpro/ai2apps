import ast
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from ai2apps.agent_builder.compiler import compile_source

@pytest.mark.parametrize('name',['done','failed','pause'])
def test_terminal_destinations_cannot_be_step_names(name):
    result=compile_source({'name':'List','site_scope':['https://example.com/**'],
        'steps':[{'name':name,'operation':'inspect','desc':'Inspect page','on':{'success':'done','failed':'failed'}}]})
    assert not result.valid
    assert any(e['code']=='reserved_step_name' for e in result.report['errors'])

def test_review_prompt_preserves_goal_without_instructing_optional_summary():
    source=Path(__file__).parents[1].joinpath('api/agent_platform.py').read_text()
    tree=ast.parse(source)
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_review_revision_prompt')
    fn.returns=None
    for arg in fn.args.args:arg.annotation=None
    env={'json':json}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'prompt','exec'),env)
    recipe=SimpleNamespace(description='Original list goal',source={'description':'Extract title and url only'})
    prompt=env['_review_revision_prompt'](recipe,SimpleNamespace(locale='zh',feedback='Wait for the page'))
    assert 'Extract title and url only' in prompt
    assert 'Original list goal' in prompt
    assert 'never step names or ids' in prompt
    assert 'returns that result unchanged' in prompt
    assert 'For optional summary add' not in prompt
    assert 'Do not add optional features' in prompt


def load_prompt_function(name):
    if name == '_exploration_prompt':
        from ai2apps.agent_builder.exploration_prompt import _exploration_prompt
        return _exploration_prompt
    tree = ast.parse(Path(__file__).parents[1].joinpath('api/agent_platform.py').read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    fn.returns = None
    for arg in fn.args.args:
        arg.annotation = None
    env = {'json': json, 're': __import__('re'), 'Any': object}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'prompt', 'exec'), env)
    return env[name]


def test_exploration_evidence_reports_quality_and_goal_without_wording_gate():
    prompt = load_prompt_function('_exploration_prompt')(SimpleNamespace(
        goal='打开 https://example.com，获取文章列表，至少包含 title 和 url',
        observation={}, attempts=[{'outcome': 'success', 'source_step': {
            'name': 'extract', 'operation': 'extract_list'}, 'evidence': {'result': {
                'items': [{'title': 'Article', 'url': 'https://example.com/a'},
                          {'title': '', 'url': None}]}}}]))
    assert 'complete immediately' in prompt
    assert 'completion never depends on the words' in prompt
    assert 'unmet requirement' in prompt
    assert '"count": 2' in prompt
    assert '"non_empty_counts": {"title": 1, "url": 1}' in prompt
    assert '"field_types":' in prompt


def test_compile_prompt_does_not_inject_summary_or_assume_page_ready():
    prompt = load_prompt_function('_compile_prompt')(SimpleNamespace(prompt='Extract title and url'), [])
    assert 'For optional summary' not in prompt
    assert 'Only when the user requests reading' in prompt
    assert 'without reading articles or summarizing' in prompt
    assert 'not proof that it is loaded' in prompt


def test_normalization_preserves_explicit_navigation_even_for_current_page():
    sanitize = load_prompt_function('_sanitize_compiled_source')
    source = sanitize(SimpleNamespace(prompt='重新打开当前页面，然后读取列表',
        name='Reload and extract', session_id=None, model_tier='standard',
        page={'url': 'https://example.com'}), [], {
        'steps': [
            {'name': 'open', 'operation': 'open', 'arguments': {'url': 'https://example.com'},
             'on': {'success': 'extract', 'failed': 'failed'}},
            {'name': 'extract', 'operation': 'extract_list',
             'on': {'success': 'done', 'failed': 'failed'}}]}, 'test-model')
    assert [step['name'] for step in source['steps']] == ['open', 'extract']


def test_distillation_only_collapses_identical_adjacent_extractions():
    from copy import deepcopy
    from ai2apps.api.agent_platform import _redundant_exploration_read
    first = {'outcome': 'success', 'source_step': {'name': 'extract',
        'operation': 'extract_list', 'arguments': {}}, 'evidence': {
        'after': {'fingerprint': 'page-a'},
        'result': {'items': [{'title': 'A', 'url': 'https://example.com/a'}]}}}
    second = deepcopy(first)
    second['evidence']['before'] = {'fingerprint': 'page-a'}
    second['source_step']['arguments']['fields'] = ['title', 'url']
    assert _redundant_exploration_read(first, second)
    changed = deepcopy(second)
    changed['evidence']['result']['items'].append({'title': 'B', 'url': 'https://example.com/b'})
    assert not _redundant_exploration_read(first, changed)
    changed = deepcopy(second)
    changed['evidence']['before']['fingerprint'] = 'page-b'
    assert not _redundant_exploration_read(first, changed)
    changed = deepcopy(second)
    changed['source_step']['arguments']['fields'].append('author')
    assert not _redundant_exploration_read(first, changed)
    assert not _redundant_exploration_read({'outcome': 'failed'}, second)


def test_foundation_duplicate_ignores_names_hints_and_rotating_dom():
    from copy import deepcopy
    from ai2apps.api.agent_platform import _redundant_exploration_read
    first = {'outcome': 'success', 'source_step': {'name': 'extract_articles',
        'operation': 'agent.call', 'target': {'intent': 'homepage articles'},
        'arguments': {'agent_id': 'builtin:web:extract-list', 'capability': 'web.extract-list',
                      'parameters': {'limit': 50}}}, 'evidence': {
        'after': {'fingerprint': 'https://example.com/|77|683|19854'},
        'result': {'page_url': 'https://example.com/', 'items': [
            {'title': 'A', 'url': 'https://example.com/a'}]}}}
    second = deepcopy(first)
    second['source_step']['name'] = 'extract_articles_current'
    second['source_step']['target']['intent'] = 'current homepage articles'
    second['evidence']['after']['fingerprint'] = 'https://example.com/|77|694|19705'
    assert _redundant_exploration_read(first, second)
    second['evidence']['result']['page_url'] = 'https://example.com/page/2'
    assert not _redundant_exploration_read(first, second)


def test_open_defaults_to_three_second_wait_and_validates_override():
    step = {'name': 'open', 'operation': 'open', 'arguments': {'url': 'https://example.com'},
            'on': {'success': 'done', 'failed': 'failed'}}
    result = compile_source({'steps': [step]})
    assert result.valid
    assert result.ir['steps'][0]['arguments']['delay_ms'] == 3000
    step['arguments']['delay_ms'] = 0
    result = compile_source({'steps': [step]})
    assert result.valid
    assert result.ir['steps'][0]['arguments']['delay_ms'] == 0
    step['arguments']['delay_ms'] = -1
    assert not compile_source({'steps': [step]}).valid


def test_interpreted_list_retains_authored_operation():
    result = compile_source({'steps': [{'name': 'extract', 'operation': 'extract_list',
        'execution': {'mode': 'interpreted'}, 'on': {'success': 'done', 'failed': 'failed'}}]})
    assert result.valid
    assert result.ir['steps'][0]['authored_operation'] == 'extract_list'


@pytest.mark.parametrize('control,label', [('browser_bidi_action','等待浏览器响应'),
    ('browser_user_assistance','等待协助'), ('agent_confirmation','等待确认')])
def test_task_wait_labels_distinguish_browser_and_human(control, label):
    from ai2apps.api.agent_platform import _browser_task_wait_presentation
    result = _browser_task_wait_presentation([SimpleNamespace(status='pending',
        request={'control':control},prompt='Concrete reason')])
    assert result['status_label'] == label
    if control != 'browser_bidi_action':
        assert result['message'] == 'Concrete reason'
