"""Explicit tool-wide consent never silently broadens legacy resource grants."""
import pytest
from ai2apps.agents import InteractionKind
from ai2apps.chat import ChatRepository
from test_app_interactions import runtime

@pytest.mark.parametrize('tool', ['fixture.reader', 'another.provider'])
@pytest.mark.parametrize('wide', [False, True])
def test_explicit_scope_and_legacy_resource_binding(runtime, tool, wide):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Consent fixture')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    interaction=runtime.agents.create_interaction(run.id,request_key='consent',kind=InteractionKind.APPROVAL,
        prompt='Allow?',response_schema={'type':'object'},request={'tool_name':tool,'capabilities':['fixture.read'],
        'resource_selector':{'arguments':{'url':'https://example.org/a'}}})
    response={'decision':'approve','scope':'app'}
    if wide: response['resource_scope']='tool'
    runtime.agents.respond_interaction(run.id,interaction.id,response=response,response_id='chosen')
    leases=runtime.capabilities.active_leases_for_run(run.id,tool,{'url':'https://example.org/b'})
    assert bool(leases) is wide
    assert runtime.capabilities.active_leases_for_run(run.id,tool,{'url':'https://example.org/a'})
    assert not runtime.capabilities.active_leases_for_run(run.id,'different.tool',{'url':'https://example.org/a'})
    lease=runtime.capabilities.list_leases()[0]
    assert lease.evidence['resource_scope']==('tool' if wide else 'current')

    second,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Second conversation')
    next_run,_=runtime.agents.create_run(session_id=second.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    assert bool(runtime.capabilities.active_leases_for_run(next_run.id,tool,{'url':'https://example.org/b'})) is wide

def test_decision_api_accepts_explicit_tool_scope_and_once():
    from ai2apps.api.agents import InteractionDecisionRequest
    request=InteractionDecisionRequest(response_id='choice',scope='once')
    assert request.resource_scope=='current'
    assert InteractionDecisionRequest(response_id='remember',scope='app',resource_scope='tool').resource_scope=='tool'
    with pytest.raises(ValueError):
        InteractionDecisionRequest(response_id='invalid',resource_scope='all_apps')


@pytest.mark.parametrize('tool',['fixture.reader','package.other-operation'])
@pytest.mark.parametrize('effects',[('external_read','network'),('artifact.create',),('read-host',)])
def test_timed_approval_eligibility_is_generic_and_only_once(tool,effects):
    from ai2apps.capabilities.risk import action_preview
    preview=action_preview(tool,effects,{'url':'https://example.org'})
    assert preview['approval_countdown_seconds']==60


@pytest.mark.parametrize('effects',[(),('network',),('network','artifact.create'),('network','read-host'),('unknown.effect',),('external_read','credential'),
    ('artifact.create','payment'),('delete',),('send',),('publish',),('execute',),('privileged',),('upload',)])
def test_sensitive_or_undeclared_effects_never_get_timed_approval(effects):
    from ai2apps.capabilities.risk import approval_countdown_seconds
    assert approval_countdown_seconds(effects) is None


def test_countdown_once_consent_does_not_create_reusable_app_authority(runtime):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Timed consent fixture')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    item=runtime.agents.create_interaction(run.id,request_key='timed',kind=InteractionKind.APPROVAL,
        prompt='Allow?',response_schema={'type':'object'},ui_hints={'control':'approval','auto_approve_seconds':60},
        request={'tool_name':'fixture.reader','capabilities':['fixture.read'],'effects':['external_read'],
                 'resource_selector':{'arguments':{'url':'https://example.org/a'}}})
    runtime.agents.respond_interaction(run.id,item.id,response={'decision':'approve','scope':'once'},response_id='timed-once')
    assert all(lease.scope!='app' for lease in runtime.capabilities.list_leases())
    second,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.diagnostic-agent',input={})
    assert not runtime.capabilities.active_leases_for_run(second.id,'fixture.reader',{'url':'https://example.org/a'})
