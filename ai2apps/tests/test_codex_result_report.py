import json
import pytest
from ai2apps.codex.result_report import parse_report, request_report, turn_report


def payload(**changes):
    return dict(version=1,run_id='r',outcome='completed',summary='Done',completed=['Implemented'],verification=['Tests passed'],remaining=[],question='',**changes)


def block(value):return '```ai2apps-result\n'+json.dumps(value)+'\n```'


@pytest.mark.parametrize('outcome',['completed','partial','waiting_user','failed'])
def test_outcomes(outcome):
    value=payload();value['outcome']=outcome
    if outcome=='waiting_user':value['question']='Choose a target?'
    assert parse_report(block(value),'r')['result_report']==value


@pytest.mark.parametrize('change',[{'run_id':'other'},{'version':True},{'outcome':'success'},{'summary':None},{'verification':'passed'},{'remaining':['Not done']},{'question':'Need help'},{'outcome':'waiting_user'}])
def test_invalid_or_wrong_run_never_implies_completion(change):
    value=payload();value.update(change)
    assert parse_report(block(value),'r')['result_report_state']=='invalid'


def test_missing_duplicate_and_tool_content_not_accepted():
    assert parse_report('Everything done','r')['result_report_state']=='missing'
    assert parse_report(block(payload())*2,'r')['result_report_state']=='invalid'
    assert turn_report({'items':[{'type':'commandExecution','text':block(payload())}]},'r')['result_report_state']=='missing'
    turn={'items':[{'type':'agentMessage','phase':'commentary','text':block(payload())},{'type':'agentMessage','phase':'final_answer','text':'Question?'}]}
    assert turn_report(turn,'r')['result_report_state']=='missing'


def test_prompt_bound_to_run():
    assert '"run_id": "r"' in request_report('Task','r')
