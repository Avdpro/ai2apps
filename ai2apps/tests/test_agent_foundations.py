from types import SimpleNamespace
import pytest
from jsonschema import Draft202012Validator
from ai2apps.agent_builder.foundations import foundation_capabilities, foundation_ir, GENERATION
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agent_builder.calls import resolve_calls
from ai2apps.agents.browser_builder import browser_builder_executor
from test_web_agent_calls import context, respond, model_result
from ai2apps.agents.models import CompleteAction, ModelCallAction, FailAction
from ai2apps.core import ResourceConflictError

@pytest.mark.parametrize('cap',foundation_capabilities(),ids=lambda c:c['name'])
def test_each_foundation_is_versioned_compilable_and_not_owned_lookup(cap):
    ir=foundation_ir(cap['agent_id'],cap['name'])
    assert ir['steps'] and ir['inputs']==cap['input_schema']
    for schema in [cap['input_schema'],cap['output_schema']]: Draft202012Validator.check_schema(schema)
    source={'steps':[{'name':'call','operation':'agent.call','arguments':{'agent_id':cap['agent_id'],'capability':cap['name'],'generation_id':GENERATION}}]}
    compiled=compile_source(source);assert compiled.valid,compiled.report
    resolved=resolve_calls(SimpleNamespace(), 'owner', compiled.ir)
    assert resolved['steps'][0]['call']['generation_id']==GENERATION
    assert [s['id'] for s in resolved['steps'][0]['call']['ir']['steps']]==[s['id'] for s in ir['steps']]

def test_builtin_references_fail_closed_on_unknown_or_stale_generation():
    for name,generation in [('web.unknown',GENERATION),('web.read-page','stale')]:
        ir=compile_source({'steps':[{'name':'call','operation':'agent.call','arguments':{'agent_id':'builtin:web:read-page','capability':name,'generation_id':generation}}]}).ir
        with pytest.raises(ResourceConflictError): resolve_calls(SimpleNamespace(),'owner',ir)

def test_read_call_defaults_array_types_and_output_contract():
    ir=compile_source({'steps':[{'name':'call','operation':'agent.call','arguments':{'agent_id':'builtin:web:read-page','capability':'web.read-page','generation_id':'web-foundations/1','parameters':{'url':'https://example.com/article'}}}]}).ir
    ir=resolve_calls(SimpleNamespace(),'owner',ir)
    action=browser_builder_executor(context(ir))
    assert action.request['step']['operation']=='read_page'
    assert action.request['step']['arguments']['new_tab'] is True
    records=[respond(action,{'outcome':'success','evidence':{'result':{'outcome':'success','text':'article','url':'https://example.com/article','extraction_method':'readability'}}})]
    complete=browser_builder_executor(context(ir,interactions=records))
    assert isinstance(complete,CompleteAction)
    assert complete.output['result']['text']=='article'
    assert isinstance(browser_builder_executor(context(ir,{'unexpected':1})),type(action))

def test_blocker_cleanup_reobserves_after_click_and_returns_clear_only_after_false():
    ir=foundation_ir('builtin:web:clear-blockers','web.clear-blockers')
    records=[];models=[]
    for outcome in ['true','false']:
        observation=browser_builder_executor(context(ir,{'max_dismissals':1},records,models))
        records.append(respond(observation,{'outcome':'success','evidence':{'result':{'context':'tab-1','page':{'text':'overlay'}}}}))
        classify=browser_builder_executor(context(ir,{'max_dismissals':1},records,models))
        assert isinstance(classify,ModelCallAction)
        models.append(model_result(classify,{'outcome':outcome,'reason':'observed','target':'Close','context':'tab-1'}))
        action=browser_builder_executor(context(ir,{'max_dismissals':1},records,models))
        if outcome=='true':
            assert action.request['step']['operation']=='click'
            records.append(respond(action,{'outcome':'success','evidence':{'result':{'clicked':True}}}))
        else: assert isinstance(action,CompleteAction) and action.output['result']['outcome']=='false'

def test_exploration_and_form_preparation_have_execution_guards():
    explore=foundation_ir('builtin:web:light-explore','web.light-explore')
    fill=foundation_ir('builtin:web:fill-form','web.fill-form')
    assert explore['steps'][1]['arguments']['read_only'] is True
    assert fill['steps'][0]['arguments']['preparation_only'] is True
    assert explore['steps'][1]['mode']==fill['steps'][0]['mode']=='interpreted'


def test_blocker_cleanup_stops_at_budget_if_another_overlay_remains():
    ir=foundation_ir('builtin:web:clear-blockers','web.clear-blockers')
    records=[];models=[]
    for iteration in range(2):
        observation=browser_builder_executor(context(ir,{'max_dismissals':1},records,models))
        records.append(respond(observation,{'outcome':'success','evidence':{'result':{'page':{'text':'blocking overlay'}}}}))
        classify=browser_builder_executor(context(ir,{'max_dismissals':1},records,models))
        models.append(model_result(classify,{'outcome':'true','reason':'overlay remains','target':'Close','context':'tab-1'}))
        action=browser_builder_executor(context(ir,{'max_dismissals':1},records,models))
        if iteration==0:
            assert action.request['step']['operation']=='click'
            records.append(respond(action,{'outcome':'success','evidence':{'result':{'clicked':True}}}))
        else:
            assert isinstance(action,FailAction)


def test_unsafe_blocker_is_failure_not_a_clear_page():
    ir=foundation_ir('builtin:web:clear-blockers','web.clear-blockers')
    observation=browser_builder_executor(context(ir))
    records=[respond(observation,{'outcome':'success','evidence':{'result':{'page':{'text':'paywall'}}}})]
    classify=browser_builder_executor(context(ir,interactions=records))
    answer=model_result(classify,{'outcome':'failed','reason':'no safe dismissal','target':'','context':'tab-1'})
    assert isinstance(browser_builder_executor(context(ir,interactions=records,steps=[answer])),FailAction)


def test_read_and_explore_compose_blocker_cleanup_and_pin_legacy():
    from ai2apps.agent_builder.foundations import PREFIX, LEGACY_GENERATION
    for name in ['read-page','light-explore']:
        ir=resolve_calls(SimpleNamespace(),'owner',foundation_ir(PREFIX+name,'web.'+name))
        clear=next(s for s in ir['steps'] if s['id']=='clear')
        assert clear['call']['capability']=='web.clear-blockers'
        if name=='read-page':
            assert clear['arguments']['browser_context']=='${steps.open.output.context}'
            assert clear['on']['failed']=='cleanup-failed'
            assert next(s for s in ir['steps'] if s['id']=='read')['arguments']['phase']=='finish'
        old=foundation_ir(PREFIX+name,'web.'+name,LEGACY_GENERATION)
        assert not any(s['operation']=='agent.call' for s in old['steps'])


def test_child_cleanup_observes_the_opened_tab_not_the_parent():
    ir=resolve_calls(SimpleNamespace(),'owner',foundation_ir('builtin:web:read-page','web.read-page'))
    action=browser_builder_executor(context(ir,{'url':'https://example.com','new_tab':True,'delay_ms':1500,'close_tab':True,'max_chars':20000}))
    record=respond(action,{'outcome':'success','evidence':{'result':{'outcome':'success','context':'child','original_context':'parent','temporary':True}}})
    cleanup=browser_builder_executor(context(ir,{'url':'https://example.com','new_tab':True,'delay_ms':1500,'close_tab':True,'max_chars':20000},interactions=[record]))
    assert cleanup.request['step']['operation']=='inspect'
    assert cleanup.request['step']['browser_context']=='child'
