import pytest
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.api.agent_platform import AgentExplorationNextRequest

@pytest.mark.parametrize('tier', ['simple', 'standard', 'complex'])
def test_browser_step_preserves_execution_tier(tier):
    result = compile_source({'site_scope':['https://example.com/**'], 'steps':[
        {'name':'type', 'desc':'input text', 'operation':'input',
         'arguments':{'value':'hello'}, 'execution':{'mode':'adaptive'}, 'ai':{'tier':tier}}
    ]})
    assert result.valid, result.report
    assert result.ir['steps'][0]['ai']['tier'] == tier
    assert result.ir['steps'][0]['mode'] == 'adaptive'


def test_interpreted_goal_does_not_need_a_compileable_operation():
    result = compile_source({'site_scope':['https://example.com/**'], 'steps':[
        {'name':'judge', 'desc':'判断当前网页状态并完成这一任务',
         'execution':{'mode':'interpreted'}, 'ai':{'tier':'complex'}}
    ]})
    assert result.valid, result.report
    step = result.ir['steps'][0]
    assert step['mode'] == 'interpreted'
    assert step['effect'] == 'interact'
    assert step['description'] == '判断当前网页状态并完成这一任务'


def test_invalid_tier_is_rejected_and_exact_tier_planning_can_disable_escalation():
    result = compile_source({'site_scope':['https://example.com/**'], 'steps':[
        {'name':'step', 'operation':'inspect', 'desc':'Inspect', 'ai':{'tier':'wrong'}}
    ]})
    assert any(error['code']=='invalid_ai_tier' for error in result.report['errors'])
    request = AgentExplorationNextRequest(goal='Type', allow_model_escalation=False, model_tier='simple')
    assert request.allow_model_escalation is False
