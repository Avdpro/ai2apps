"""Protocol-aware fixtures, current grants and proven pre-execution failures."""
import asyncio
import json
from dataclasses import replace

import pytest

from agent_context_fixtures import current_state, owner_context
from ai2apps.services import ToolAuthorizationError
from ai2apps.services.capability_routing import CapabilityInvocationError
from test_app_chat_durable import bind_identity
from test_app_interactions import runtime
from test_bot_capability_discovery import setup, P
from test_bot_app_access import save
from test_aaat_execution_flow import response


@pytest.mark.parametrize('compact', [False, True])
def test_fixture_reads_latest_snapshot_and_delta_not_historical_strings(compact):
    encode = lambda v: json.dumps(v, separators=(',', ':')) if compact else json.dumps(v, indent=2)
    state = {'owner_context': {'name': 'arbitrary.owner', 'delegated_task': True, 'old': True}, 'items': [1, 2]}
    messages = [
        {'role': 'system', 'content': 'Historical hint "name": "wrong.owner"'},
        {'role': 'user', 'content': 'Current UI snapshot (untrusted data): ' + encode(state)},
        {'role': 'user', 'content': 'Current UI snapshot delta (untrusted data): ' + encode({
            'base_snapshot': 'earlier-run', 'changes': [
                {'op': 'set', 'path': ['owner_context', 'collaboration_result'], 'value': {'content': 'verified child result'}},
                {'op': 'remove', 'path': ['owner_context', 'old']},
                {'op': 'splice', 'path': ['items'], 'start': 1, 'delete': 1, 'items': [3, 4]},
            ]})},
    ]
    request = {'messages': messages}
    assert owner_context(request) == {'name': 'arbitrary.owner', 'delegated_task': True,
                                       'collaboration_result': {'content': 'verified child result'}}
    assert current_state(request)['items'] == [1, 3, 4]
    assert 'old' in state['owner_context']  # no mutation of the original snapshot
    with pytest.raises(AssertionError, match='earlier base'):
        current_state({'messages': [messages[-1]]})


def test_absent_provider_admission_differs_from_version_change(runtime):
    bot, sid, calls, provider = setup(runtime, 'arbitrary.authorized')
    rid = runtime.app_chat.submit(P(), sid, 'admission-reason', 'Inspect capability', 'fixture')
    owner = runtime.app_chat.owner(runtime.app_chat.binding(sid))
    frozen = runtime.app_chat.execution_authorization(rid)
    missing = {**frozen, 'discovery_providers': {k:v for k,v in frozen['discovery_providers'].items() if k != provider.id}}
    with pytest.raises(ToolAuthorizationError) as denied:
        owner.validate_authorization('local', {'bot_id': bot['id']}, missing,
                                     'app.describe', {'capability': provider.capability})
    assert denied.value.code == 'provider_not_authorized'
    assert denied.value.details['submitted'] is False
    runtime.app_capability_router.providers[provider.id] = replace(provider, version='new-version')
    with pytest.raises(ToolAuthorizationError) as changed:
        owner.validate_authorization('local', {'bot_id': bot['id']}, frozen,
                                     'app.describe', {'capability': provider.capability})
    assert changed.value.code == 'provider_binding_changed'
    assert not calls


def test_delegation_permission_point_lookup_never_rebuilds_exports_and_sees_revocation(runtime, monkeypatch):
    bot, _, _, provider = setup(runtime)
    other = runtime.messager_bots.create('local', 'Independent reviewer', 'Review work')
    save(runtime, bot); save(runtime, other)
    permissions = runtime.messager_bot_permissions
    old_membership = {origin: provider.id in permissions.capture('local', {'bot_id': bot['id']}, origin)['providers']
                      for origin in ('user', 'hook')}
    def forbidden(*args, **kwargs):
        raise AssertionError('Full exports/capture during a point lookup')
    monkeypatch.setattr(permissions, 'capture', forbidden)
    monkeypatch.setattr(runtime.messager_bot_app_access, 'exported', forbidden)
    for origin in ('user', 'hook'):
        assert permissions.permits_provider('local', bot['id'], origin, provider) == old_membership[origin]
        assert runtime.messager_bot_delegation.permitted('local', bot['id'], other['id'], provider, origin=origin)
    save(runtime, other, False)
    assert not runtime.messager_bot_delegation.permitted('local', bot['id'], other['id'], provider)
    runtime.app_capability_router.providers[provider.id] = replace(provider, version='changed')
    assert not permissions.permits_provider('local', bot['id'], 'user', provider)


@pytest.mark.asyncio
@pytest.mark.parametrize('name', ['arbitrary.submit', 'independent.compose'])
@pytest.mark.parametrize('phase', ['prepare', 'execute'])
async def test_proven_unsubmitted_rejection_never_erases_execute_uncertainty(runtime, name, phase):
    writes = []
    async def prepare(args, ctx):
        if phase == 'prepare':
            raise CapabilityInvocationError('capability_denied', 'Role not admitted', {'phase': 'prepare'})
        return args
    async def execute(args, ctx):
        writes.append('submitted')
        # A handler cannot turn an already submitted failure into a preflight
        # rejection by choosing an exception or its phase metadata.
        raise CapabilityInvocationError('capability_denied', 'Failure after submission', {'phase': 'prepare'})
    bot, sid, _, provider = setup(runtime, name)
    runtime.app_capability_router.providers[provider.id] = replace(
        runtime.app_capability_router.providers[provider.id], handler=execute, prepare=prepare)
    save(runtime, bot)
    async def model(request):
        results = [json.loads(m['content']) for m in request['messages'] if m['role'] == 'tool']
        if any(x.get('error', {}).get('outcome_uncertain') for x in results):
            return response(text='Original outcome remains unknown; no replay.')
        return response(name, {'prompt': 'qualify submission'})
    runtime.agent_runtime.bind_model_provider(model)
    rid = runtime.app_chat.submit(P(), sid, 'phase-fixture', 'Qualify submission phase', 'fixture')
    run = runtime.agents.get_run(rid)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        for _ in range(800):
            run = runtime.agents.get_run(run.id)
            if run.status.value in ('completed', 'failed'):
                break
            if run.status.value == 'waiting_capability':
                item = next(i for i in runtime.agents.list_interactions(run.id) if i.status.value == 'pending')
                runtime.agents.respond_interaction(run.id, item.id, response_id='allow-' + item.id,
                                                   response={'decision': 'approve', 'scope': 'once'})
                runtime.agent_runtime.wake()
            await asyncio.sleep(.02)
        failures = [s.error for s in runtime.agents.list_steps(run.id)
                    if s.tool_name == name and s.status.value == 'failed']
        failure = failures[-1]
        if phase == 'prepare':
            assert run.status.value == 'failed'
            assert failure['phase'] == 'prepare' and failure['submitted'] is False
            assert not failure.get('outcome_uncertain') and not writes
            assert run.error['code'] == 'capability_denied'
        else:
            assert run.status.value == 'completed'
            assert failure['outcome_uncertain'] is True and writes == ['submitted']
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_memory_return_from_parent_is_denied_before_submission(runtime):
    from ai2apps.messager.memory_returns import RETURN
    bot, sid, _, _ = setup(runtime)
    async def model(request):
        return response(RETURN, {'items': [{'subject': 'finding', 'predicate': 'result',
            'value': 'not-a-child-result', 'text': 'not-a-child-result',
            'evidence_kind': 'tool_step', 'evidence_id': 'unavailable', 'quote': 'not-a-child-result'}]})
    runtime.agent_runtime.bind_model_provider(model)
    rid = runtime.app_chat.submit(P(), sid, 'parent-return-denied', 'Qualify parent role denial', 'fixture')
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        for _ in range(800):
            run = runtime.agents.get_run(rid)
            if run.status.value in ('completed', 'failed'):
                break
            if run.status.value == 'waiting_capability':
                item = next(i for i in runtime.agents.list_interactions(rid) if i.status.value == 'pending')
                runtime.agents.respond_interaction(rid, item.id, response_id='allow-' + item.id,
                                                   response={'decision': 'approve', 'scope': 'once'})
                runtime.agent_runtime.wake()
            await asyncio.sleep(.02)
        assert run.status.value == 'failed' and run.error['code'] == 'capability_denied'
        failure = [s.error for s in runtime.agents.list_steps(rid) if s.tool_name == RETURN and s.error][-1]
        assert failure['phase'] == 'prepare' and failure['submitted'] is False
        assert not failure.get('outcome_uncertain')
        with runtime.database.transaction() as db:
            assert db.execute('SELECT count(*) FROM messager_memory_returns').fetchone()[0] == 0
    finally:
        await runtime.stop_background_tasks()
