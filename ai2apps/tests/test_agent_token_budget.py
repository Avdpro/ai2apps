from types import SimpleNamespace
from ai2apps.agents.models import AgentExecutionContext, InteractionStatus, InteractionAction, CompleteAction
from ai2apps.agents.token_budget import budget_decision, token_allowance, default_model_tokens, CONTINUE, STOP

def context(items=(), budget=100, requested=None):
    return AgentExecutionContext(SimpleNamespace(manifest={'max_total_model_tokens':budget}),
        SimpleNamespace(input={'run_budget': {'max_model_tokens':requested}} if requested else {}, delegation={}), (), tuple(items))

def test_default_and_explicit_budget(monkeypatch):
    monkeypatch.delenv('AI2APPS_AGENT_MAX_MODEL_TOKENS', raising=False)
    assert default_model_tokens() == 500000
    monkeypatch.setenv('AI2APPS_AGENT_MAX_MODEL_TOKENS','900000')
    assert default_model_tokens() == 900000
    monkeypatch.setenv('AI2APPS_AGENT_MAX_MODEL_TOKENS','invalid')
    assert default_model_tokens() == 500000
    assert token_allowance(context(requested=700000)) == (700000,700000)

def test_large_search_preview_keeps_report_and_omits_raw_bodies():
    import json
    from ai2apps.agents.result_reference import result_preview
    output={'workflow_run_id':'child','articles':[{'text':'body'*9000}], 'summary':{'overview':'正文结论','points':[],'limitations':'视频只有简介'},'citations':[{'id':'1','url':'https://example.com/a'}]}
    from ai2apps.research.citations import report_preview
    from ai2apps.agents.models import RunStepStatus
    step=SimpleNamespace(id='step',kind='tool',status=RunStepStatus.COMPLETED,tool_name='web.search',output=output)
    preview=json.loads(result_preview(step,reader_alias='reader',app_preview=report_preview(step)))
    assert preview['app_context']['report']['summary'] == output['summary']
    assert preview['app_context']['report']['citations'] == output['citations']
    assert 'articles' not in preview['app_context']['report']
    assert preview['read_with']['arguments']['step_id'] == 'step'

def test_multibyte_preview_stays_partial_near_byte_threshold():
    import json
    from ai2apps.agents.result_reference import result_preview, result_text
    step=SimpleNamespace(id='step',tool_name='web.fetch',output={'text':'中'*3000})
    text=result_text(step.output)
    preview=json.loads(result_preview(step,reader_alias='reader'))
    assert preview['omitted_characters'] > 0
    assert preview['read_with']['arguments']['offset'] == len(preview['head'])
    assert len(json.dumps(preview,ensure_ascii=False).encode()) < len(text.encode())

def test_durable_continue_covers_overshoot_and_requires_a_new_decision():
    first=budget_decision(context(),144)
    assert isinstance(first,InteractionAction)
    pending=SimpleNamespace(request_key=first.request_key,status=InteractionStatus.PENDING,request=first.request,response=None)
    assert isinstance(budget_decision(context([pending]),144),InteractionAction)
    grant=SimpleNamespace(request_key=first.request_key,status=InteractionStatus.SUBMITTED,request=first.request,response={'answer':CONTINUE})
    # A fresh executor derives the same allowance from persisted interactions.
    assert token_allowance(context([grant])) == (100,244)
    assert budget_decision(context([grant]),243) is None
    second=budget_decision(context([grant]),244)
    assert second.request_key == 'token-budget:244'
    stop=SimpleNamespace(request_key=second.request_key,status=InteractionStatus.SUBMITTED,request=second.request,response={'answer':STOP})
    assert isinstance(budget_decision(context([grant,stop]),244),CompleteAction)
