"""P0 real SQLite/Bot admission; models and tool effects are deterministic fixtures."""
import json
from dataclasses import replace

import pytest

from ai2apps.messager.realtime_inputs import RealtimeInputs
from ai2apps.core.errors import ResourceNotFoundError
from test_app_chat_durable import response, bind_identity
from test_app_interactions import runtime, wait
from test_bot_capability_discovery import setup, P
from test_bot_dialogue import job_wait


def group(r):
    bot, sid, _, _ = setup(r)
    inputs = r.messager_dialogue.realtime_inputs
    ref = inputs.create(P(), bot['id'], sid, 'explicit-send', model='fixture')
    return inputs, ref, bot, sid


def test_explicit_group_freezes_membership_and_deduplicates(runtime):
    inputs, ref, bot, sid = group(runtime)
    assert inputs.create(P(), bot['id'], sid, 'explicit-send', model='fixture') == ref
    with pytest.raises(ValueError, match='different input'):
        inputs.create(P(), bot['id'], sid, 'explicit-send', model='changed')
    assert inputs.add(P(), ref, 'speech-1', source='speech', text='compare contracts') == 1
    assert inputs.add(P(), ref, 'speech-1', source='speech', text='compare contracts') == 1
    with pytest.raises(ValueError, match='different content'):
        inputs.add(P(), ref, 'speech-1', source='speech', text='send email')
    inputs.add(P(), ref, 'text-1', source='text', text='only payment terms')
    with pytest.raises(ValueError, match='revision'):
        inputs.close(P(), ref, 1)
    with pytest.raises(ValueError, match='Close'):
        inputs.dispatch(P(), ref)
    inputs.close(P(), ref, 2)
    inputs.close(P(), ref, 2)
    with pytest.raises(ValueError, match='closed'):
        inputs.add(P(), ref, 'late', source='text', text='late change')
    accepted = inputs.dispatch(P(), ref)
    assert accepted == inputs.dispatch(P(), ref)
    run = runtime.agents.get_run(accepted['dialogue_run_id'])
    assert run.input['prompt'] == 'compare contracts\nonly payment terms'
    assert run.input['task_session_id'] is None
    with runtime.database.transaction() as db:
        assert db.execute('SELECT count(*) FROM messager_dialogue_turns WHERE session_id=?', (sid,)).fetchone()[0] == 1


def test_crash_after_owner_admission_recovers_original_run(runtime, monkeypatch):
    inputs, ref, _, sid = group(runtime)
    inputs.add(P(), ref, 'text', source='text', text='hello')
    inputs.close(P(), ref, 1)

    def crash(*args):
        raise RuntimeError('simulated process loss before receipt')

    monkeypatch.setattr(inputs, '_save_receipt', crash)
    with pytest.raises(RuntimeError, match='process loss'):
        inputs.dispatch(P(), ref)
    recovered = RealtimeInputs(runtime.messager_dialogue)
    accepted = recovered.dispatch(P(), ref)
    with runtime.database.transaction() as db:
        rows = db.execute('SELECT run_id FROM messager_dialogue_turns WHERE session_id=?', (sid,)).fetchall()
    assert [r[0] for r in rows] == [accepted['dialogue_run_id']]


def test_attachments_wait_for_ready_and_remain_frozen(runtime):
    inputs, ref, _, sid = group(runtime)
    a = runtime.documents.create(sid, filename='one.txt', media_type='text/plain', data=b'first contract')
    b = runtime.documents.create(sid, filename='two.txt', media_type='text/plain', data=b'second contract')
    inputs.add(P(), ref, 'speech', source='speech', text='Compare these')
    inputs.add(P(), ref, 'files', source='attachment', attachment_ids=[a.id, b.id])
    inputs.close(P(), ref, 2)
    assert inputs.dispatch(P(), ref)['state'] == 'waiting_attachments'
    runtime.documents.parse(sid, a.id)
    assert inputs.dispatch(P(), ref) == {'state': 'waiting_attachments', 'attachment_ids': [b.id]}
    runtime.documents.parse(sid, b.id)
    accepted = inputs.dispatch(P(), ref)
    run = runtime.agents.get_run(accepted['dialogue_run_id'])
    assert [f['id'] for f in run.input['selected_materials']['files']] == [a.id, b.id]
    # No new admission on replay after a selected attachment has disappeared.
    runtime.documents.retire(sid, a.id)
    assert inputs.dispatch(P(), ref) == accepted


def test_failed_and_changed_files_never_admit(runtime):
    inputs, ref, _, sid = group(runtime)
    a = runtime.documents.create(sid, filename='one.txt', media_type='text/plain', data=b'contract')
    inputs.add(P(), ref, 'files', source='attachment', attachment_ids=[a.id])
    inputs.close(P(), ref, 1)
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE document_blobs SET parse_status='failed' WHERE id=?", (a.blob_id,))
    assert inputs.dispatch(P(), ref) == {'state': 'attachment_failed', 'attachment_ids': [a.id]}
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE document_blobs SET sha256=?,parse_status='ready' WHERE id=?", ('0' * 64, a.blob_id))
    with pytest.raises(ValueError, match='content changed'):
        inputs.dispatch(P(), ref)
    with runtime.database.transaction() as db:
        assert db.execute('SELECT count(*) FROM messager_dialogue_turns').fetchone()[0] == 0


@pytest.mark.parametrize('principal', [replace(P(), actor_user_id='other'),
                                     replace(P(), installation_id='other'),
                                     replace(P(), client_scope='mobile')])
def test_principal_isolation(runtime, principal):
    inputs, ref, _, _ = group(runtime)
    with pytest.raises(PermissionError):
        inputs.add(principal, ref, 'stolen', source='text', text='hello')
    with pytest.raises(PermissionError):
        inputs.dispatch(principal, ref)


def test_partial_empty_cross_conversation_and_bounds(runtime):
    inputs, ref, _, sid = group(runtime)
    with pytest.raises(ValueError, match='committed'):
        inputs.add(P(), ref, 'partial', source='speech', text='maybe send', final=False)
    with pytest.raises(ValueError, match='Empty'):
        inputs.close(P(), ref, 0)
    _, other_sid, _, _ = setup(runtime, name='different.compose')
    foreign = runtime.documents.create(other_sid, filename='private.txt', media_type='text/plain', data=b'private')
    with pytest.raises(ResourceNotFoundError):
        inputs.add(P(), ref, 'foreign', source='attachment', attachment_ids=[foreign.id])
    inputs.add(P(), ref, 'large', source='text', text='x' * inputs.MAX_TEXT)
    with pytest.raises(ValueError, match='limit'):
        inputs.add(P(), ref, 'overflow', source='text', text='x')


@pytest.mark.asyncio
async def test_real_bot_owner_decides_task_and_continuation(runtime, bind_identity):
    inputs, ref, bot, sid = group(runtime)
    target = None

    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:
            return response(text=json.dumps({'kind': 'continue' if target else 'task',
                'target_session_id': target, 'text': 'ack', 'title': 'Contract comparison'}))
        return response(text='Verified fixture result')

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        inputs.add(P(), ref, 'speech', source='speech', text='compare payment terms')
        inputs.close(P(), ref, 1)
        first = inputs.dispatch(P(), ref)['dialogue_run_id']
        task = await wait(runtime, first, 'completed')
        target = task.output['task_session_id']
        first_job = await job_wait(runtime, first, 'completed')
        next_group = inputs.create(P(), bot['id'], sid, 'explicit-followup', model='fixture', task_session_id=target)
        inputs.add(P(), next_group, 'text', source='text', text='also compare termination')
        inputs.close(P(), next_group, 1)
        second = inputs.dispatch(P(), next_group)['dialogue_run_id']
        continued = await wait(runtime, second, 'completed')
        second_job = await job_wait(runtime, second, 'completed')
        assert continued.output['task_session_id'] == target
        assert first_job['worker_run'] != second_job['worker_run']
        assert first_job['worker_session'] == second_job['worker_session']
    finally:
        await runtime.stop_background_tasks()
