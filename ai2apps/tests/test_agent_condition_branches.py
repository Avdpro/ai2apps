import json
from types import SimpleNamespace
import pytest
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agents.browser_builder import browser_builder_executor
from ai2apps.agents.models import RunStepStatus


def condition_source():
    return {'site_scope':['https://example.com/**'], 'steps':[
        {'name':'check', 'desc':'Check condition', 'operation':'ai.classify',
         'ai':{'tier':'standard', 'instruction':'Return true, false or failed for the condition.',
               'output_schema':{'type':'object','properties':{'outcome':{'enum':['true','false','failed']}},'required':['outcome']}},
         'on':{'true':'yes','false':'no','failed':'error'}},
        *[{'name':name,'desc':'Inspect '+name,'operation':'inspect','on':{'success':'done','failed':'failed'}} for name in ['yes','no','error']]
    ]}

@pytest.mark.parametrize('outcome,target', [('true','yes'),('false','no'),('failed','error')])
def test_condition_routes_three_distinct_results(outcome,target):
    compiled=compile_source(condition_source())
    assert compiled.valid, compiled.report
    model=SimpleNamespace(status=RunStepStatus.COMPLETED,output={'choices':[{'message':{'content':json.dumps({'outcome':outcome})}}]})
    context=SimpleNamespace(definition=SimpleNamespace(max_steps=20),run=SimpleNamespace(input={'parameters':{
        'ir':compiled.ir,'ai_model_routes':{'standard':'model'}}}),interactions=[],step=lambda key:model)
    action=browser_builder_executor(context)
    assert action.request['step_id']==target

@pytest.mark.parametrize('status,content', [(RunStepStatus.FAILED,None),(RunStepStatus.COMPLETED,'bad-json')])
def test_failed_judgment_follows_failure_branch_instead_of_false(status,content):
    compiled=compile_source(condition_source())
    model=SimpleNamespace(status=status, output={'choices':[{'message':{'content':content}}]})
    context=SimpleNamespace(definition=SimpleNamespace(max_steps=20),run=SimpleNamespace(input={'parameters':{
        'ir':compiled.ir,'ai_model_routes':{'standard':'model'}}}),interactions=[],step=lambda key:model)
    action=browser_builder_executor(context)
    assert action.request['step_id']=='error'


def test_false_can_jump_back_to_an_existing_step():
    source=condition_source();source['steps'][0]['on']['false']='check'
    compiled=compile_source(source)
    assert compiled.valid, compiled.report
    assert compiled.ir['steps'][0]['on']['false']=='check'


def test_repeated_ai_data_step_requests_a_fresh_model_call_each_iteration():
    source=condition_source(); source['steps']=[{'name':'update','desc':'Update loop state','operation':'ai.transform',
        'ai':{'tier':'standard','instruction':'Update counter','output_schema':{'type':'object'}},
        'on':{'success':'update','failed':'failed'}}]
    compiled=compile_source(source); assert compiled.valid
    completed=SimpleNamespace(status=RunStepStatus.COMPLETED,output={'choices':[{'message':{'content':'{"counter":1}'}}]})
    context=SimpleNamespace(definition=SimpleNamespace(max_steps=20),run=SimpleNamespace(input={'parameters':{
        'ir':compiled.ir,'ai_model_routes':{'standard':'model'}}}),interactions=[],
        step=lambda key:completed if key=='browser-ai:update' else None)
    action=browser_builder_executor(context)
    assert action.call_id=='browser-ai:update:1'
