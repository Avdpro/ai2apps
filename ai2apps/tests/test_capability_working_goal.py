from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agent_builder.sites import normalize_site_agent_source
from ai2apps.agents.browser_builder import browser_builder_executor
from test_web_agent_calls import context


def test_capability_guidance_overrides_agent_and_blank_inherits():
    source = {'description': 'Agent guidance', 'capabilities': [
        {'id': name, 'name': f'site.{name}', 'description': 'Concise label only',
         'working_goal': goal, 'steps': [{'name': 'inspect', 'operation': 'inspect'}]}
        for name, goal in [('list', ' Return titles and URLs '), ('article', 'Read full article'), ('fallback', '  ')]
    ]}
    result = compile_source(source)
    assert result.valid, result.report
    for cap, expected in zip(result.ir['capabilities'], ['Return titles and URLs', 'Read full article', 'Agent guidance']):
        assert cap['working_goal'] == expected
        assert cap['steps'][0]['working_goal'] == expected
        action = browser_builder_executor(context(cap))
        assert action.request['step']['working_goal'] == expected


def test_legacy_guidance_survives_normalization_and_blank_falls_back():
    for goal in ['', 'Capability instruction']:
        source = {'description': 'Agent instruction', 'working_goal': goal,
                  'steps': [{'name': 'inspect', 'operation': 'inspect'}]}
        result = compile_source(normalize_site_agent_source(source))
        assert result.valid, result.report
        assert result.ir['capabilities'][0]['working_goal'] == (goal or 'Agent instruction')


def test_description_is_not_a_working_goal():
    result = compile_source({'capabilities': [{'id': 'read', 'description': 'Short label',
        'steps': [{'name': 'inspect', 'operation': 'inspect'}]}]})
    assert result.valid, result.report
    assert result.ir['capabilities'][0]['working_goal'] == ''
