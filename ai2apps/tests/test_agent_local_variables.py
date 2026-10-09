from copy import deepcopy
from types import SimpleNamespace
import pytest
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agent_builder.variables import evaluate, initialize_variables, execute_local_step
from ai2apps.agent_builder.calls import bind_values
from ai2apps.agents.browser_builder import browser_builder_executor
from ai2apps.agents.models import AgentExecutionContext, CompleteAction, InteractionStatus

SCHEMA={'type':'object','properties':{'index':{'type':'integer','default':0},'item':{'type':'string','default':''}}}
def source():
    return {'site_scope':['https://example.com/**'],'variables':deepcopy(SCHEMA),
      'inputs':{'type':'object','properties':{'items':{'type':'array','items':{'type':'string'}}},'required':['items']},
      'steps':[
        {'name':'check','operation':'condition','arguments':{'expression':'vars.index < len(input.items)'},'on':{'true':'update','false':'done','failed':'failed'}},
        {'name':'update','operation':'assign','execution_mode':'interpreted','arguments':{'assignments':[
          {'variable':'item','expression':'input.items[vars.index]'}, {'variable':'index','expression':'vars.index + 1'}]},'on':{'success':'check','failed':'failed'}}]}
def ctx(ir, interactions=()):
    return AgentExecutionContext(definition=SimpleNamespace(max_steps=100),run=SimpleNamespace(input={'parameters':{'ir':ir,'invocation_input':{'items':['a','b','c']}}}),interactions=interactions,steps=[])

def test_compiled_loop_finishes_without_browser_or_ai_calls():
    compiled=compile_source(source()); assert compiled.valid,compiled.report
    assert all(s['mode']=='compiled' for s in compiled.ir['steps'])
    action=browser_builder_executor(ctx(compiled.ir))
    assert isinstance(action,CompleteAction)
    assert action.output['variables']=={'index':3,'item':'c'}
    assert [e['outcome'] for e in action.output['evidence']]==['true','success','true','success','true','success','false']
    assert browser_builder_executor(ctx(compiled.ir)).output==action.output

def test_browser_pause_replay_reconstructs_variables_and_does_not_repeat_action():
    raw=source();raw['steps'][1]['on']['success']='read'
    raw['steps'].append({'name':'read','operation':'inspect','on':{'success':'check','failed':'failed'}})
    compiled=compile_source(raw);assert compiled.valid,compiled.report
    records=[]
    for expected in ['a','b','c']:
        action=browser_builder_executor(ctx(compiled.ir,records))
        assert action.request['step_id']=='read'
        records.append(SimpleNamespace(id=action.request_key,request_key=action.request_key,request=action.request,
          status=InteractionStatus.SUBMITTED,response={'outcome':'success','evidence':{'result':{'seen':expected}}}))
    action=browser_builder_executor(ctx(compiled.ir,records))
    assert isinstance(action,CompleteAction)
    assert action.output['variables']=={'index':3,'item':'c'}
    assert len({r.request_key for r in records})==3

@pytest.mark.parametrize('expression',["__import__('os')",'input.__class__','[x for x in input.items]','(lambda:1)()','2 ** 20','input.items.pop()'])
def test_code_execution_constructs_rejected(expression):
    with pytest.raises(ValueError): evaluate(expression,{}, {},{})

@pytest.mark.parametrize('expression',['input.items[-1]','input.items[5]','1 / 0','true + 1','len(1)','1 and true'])
def test_invalid_expressions_fail_cleanly(expression):
    with pytest.raises(ValueError): evaluate(expression,{'items':['a']},{},{})

def test_assignment_rollback_and_false_distinct_from_failure():
    original=initialize_variables(SCHEMA,{})
    step={'operation':'assign','arguments':{'assignments':[{'variable':'index','expression':'1'}, {'variable':'item','expression':'42'}]}}
    result,values=execute_local_step(step,{},original,{},SCHEMA)
    assert result['outcome']=='failed' and values==original and original['index']==0
    for expression,outcome in [('false','false'),('true','true'),('0','failed')]:
        result,_=execute_local_step({'operation':'condition','arguments':{'expression':expression}},{},original,{},SCHEMA)
        assert result['outcome']==outcome

def test_typed_initial_expression_and_typed_binding():
    schema={'type':'object','properties':{'items':{'type':'array','initial':'input.items'},'size':{'type':'integer','initial':'len(input.items)'}}}
    values=initialize_variables(schema,{'items':[{'url':'x'}]})
    assert bind_values('${vars.items}',{},variables=values)==[{'url':'x'}]
    assert bind_values('${vars.items.0.url}',{},variables=values)=='x'
    assert evaluate('steps.fetch.output.items[0].url',{},values,{'fetch':{'output':{'items':[{'url':'y'}]}}})=='y'
    with pytest.raises(ValueError): initialize_variables(schema,{'items':42})

@pytest.mark.parametrize('mutate',[lambda s:s['steps'][0]['arguments'].update(expression='vars.missing == 0'),
 lambda s:s['steps'][1]['arguments']['assignments'][0].update(variable='missing'),
 lambda s:s['variables']['properties']['index'].update(default='wrong')])
def test_invalid_local_definitions_rejected_by_compiler(mutate):
    raw=source(); mutate(raw); assert not compile_source(raw).valid

def test_capability_variables_preserved():
    raw=source();cap={k:v for k,v in raw.items() if k!='site_scope'};cap.update(id='loop',name='site.loop')
    result=compile_source({'site_scope':raw['site_scope'],'capabilities':[cap]})
    assert result.valid,result.report
    assert result.ir['capabilities'][0]['variables']==SCHEMA

def test_invalid_capability_name_reports_error_instead_of_crashing():
    raw=source();cap={k:v for k,v in raw.items() if k!='site_scope'};cap.update(id='loop',name='Invalid Name')
    assert not compile_source({'site_scope':raw['site_scope'],'capabilities':[cap]}).valid

def test_child_agent_has_fresh_isolated_local_state():
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class Run:
        input:dict
    child=compile_source(source()).ir
    parent=compile_source({'site_scope':['https://example.com/**'],'variables':SCHEMA,'steps':[
      {'name':'set','operation':'assign','arguments':{'assignments':[{'variable':'index','expression':'7'}]},'on':{'success':'child','failed':'failed'}},
      {'name':'child','operation':'agent.call','arguments':{'agent_id':'child','capability':'site.loop','parameters':{'items':['x','y']}},'on':{'success':'done','failed':'failed'}}]}).ir
    parent['steps'][1]['call']={'agent_id':'child','generation_id':'gen','capability':'site.loop','ir':child}
    context=AgentExecutionContext(definition=SimpleNamespace(max_steps=100),run=Run({'parameters':{'ir':parent}}),interactions=[],steps=[])
    action=browser_builder_executor(context)
    assert isinstance(action,CompleteAction)
    assert action.output['variables']['index']==7
    assert action.output['evidence'][1]['evidence']['steps'][-1]['outcome']=='false'

def test_local_evaluation_api_ownership_types_and_no_draft_mutation(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.identity import RequestPrincipal
    principal=RequestPrincipal.legacy_local()
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));runtime.start()
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principal))
    try:
        with TestClient(app) as client:
            response=client.post('/v1/platform/agent-drafts',json={'name':'Loop','site_scope':['https://example.com/**'],'source':source()})
            assert response.status_code==201,response.text
            draft=response.json(); path='/v1/platform/agent-drafts/'+draft['id']+'/steps/update/evaluate'
            initialized=client.post('/v1/platform/agent-drafts/'+draft['id']+'/variables/evaluate',json={'input':{'items':['a']}})
            assert initialized.status_code==200 and initialized.json()['variables']=={'index':0,'item':''}
            body={'input':{'items':['a']},'variables':{'index':0,'item':''}}
            evaluated=client.post(path,json=body)
            assert evaluated.status_code==200,evaluated.text
            assert evaluated.json()['variables']=={'index':1,'item':'a'}
            body['variables']['index']='bad'
            assert client.post(path,json=body).status_code==422
            foreign=runtime.agent_builder.create_draft(owner_user_id='different-owner',name='Foreign',description='',site_scope=['https://example.com/**'],source=source())
            assert client.post('/v1/platform/agent-drafts/'+foreign.id+'/steps/update/evaluate',json={'input':{'items':['a']}}).status_code in (403,404)
            saved=client.get('/v1/platform/agent-drafts/'+draft['id']).json()
            assert saved['revision']==draft['revision'] and saved['source']==draft['source']
    finally: runtime.stop()


def test_nested_browser_arguments_keep_local_variable_bindings():
    values={'current':[{'url':'https://example.com'}],'index':2}
    assert bind_values({'items':'${vars.current}','nested':['${vars.index}']},{},variables=values)=={'items':values['current'],'nested':[2]}

def test_read_results_uses_current_loop_items_without_from_step_override():
    raw={'site_scope':['https://example.com/**'],'variables':{'type':'object','properties':{'current':{'type':'array','default':[{'url':'https://example.com/one'}]}}},'steps':[{'name':'read','operation':'read_results','arguments':{'items':'${vars.current}','limit':1,'new_tab':True,'delay_ms':3000},'on':{'success':'done','failed':'failed'}}]}
    compiled=compile_source(raw)
    assert compiled.valid,compiled.report
    action=browser_builder_executor(ctx(compiled.ir))
    assert action.request['step']['arguments']['items']==[{'url':'https://example.com/one'}]
