"""Chat snapshots must not replace the scheduler's durable input identity."""
import asyncio
import json
from types import SimpleNamespace
import pytest

from ai2apps.chat import ChatRepository, LegacyChatMessageInput
from ai2apps.core import MessageRole
from ai2apps.storage import MessagePartInput
from ai2apps.storage.repositories import MessageRepository
from test_app_interactions import runtime, wait


def setup(runtime, *, content=None, message_id=None, tools=()):
    chat = ChatRepository(runtime.database, runtime.events)
    thread, _ = chat.create_thread(title='Input identity')
    payload = {'model':'fixture', 'tools':list(tools)}
    payload.update({'message_id': message_id} if message_id else {'content':content} if content else {'prompt':'same prompt'})
    run, _ = runtime.agents.create_run(session_id=thread.session.id, agent_key='ai2apps.general-agent', input=payload)
    executor = runtime.agent_runtime._executors['builtin:general-agent']
    context = SimpleNamespace(run=run)
    return chat, run, executor, context


def snapshot(chat, run, messages):
    return chat.replace_content(run.session_id, expected_revision=chat.get_thread(run.session_id).session.revision,
                                metadata={}, messages=tuple(messages))


def alias(run, text='same prompt'):
    return LegacyChatMessageInput(role=MessageRole.USER, content=text,
        metadata={'id':'optimistic-input', 'agent_run_id':run.id, 'agent_input':True})


def test_snapshot_preserves_input_key_parts_and_id_on_repeated_executor_pass(runtime):
    chat, run, executor, context = setup(runtime)
    assert executor._ensure_prompt(context) is None
    messages = MessageRepository(runtime.database, runtime.events)
    original = messages.get_by_idempotency_key(run.session_id, f'agent-run:{run.id}:user')
    for _ in range(3):
        content = snapshot(chat, run, [alias(run), *chat.get_content(run.session_id).messages])
        assert len(content.messages) == 1
        assert executor._ensure_prompt(context) is None
        saved = messages.get_by_idempotency_key(run.session_id, f'agent-run:{run.id}:user')
        assert saved == original
        assert len(messages.list_for_session(run.session_id)) == 1


def test_snapshot_before_scheduler_input_does_not_persist_optimistic_duplicate(runtime):
    chat, run, executor, context = setup(runtime)
    snapshot(chat, run, [alias(run)])
    executor._ensure_prompt(context)
    assert len(chat.get_content(run.session_id).messages) == 1
    executor._ensure_prompt(context)
    assert len(chat.get_content(run.session_id).messages) == 1


def test_rich_input_and_explicit_reference_identity_survive_snapshot(runtime):
    rich = [{'type':'text','text':'inspect attachment'}, {'type':'image_url','image_url':{'url':'/owned/reference'}}]
    chat, run, executor, context = setup(runtime, content=rich)
    executor._ensure_prompt(context)
    messages = MessageRepository(runtime.database, runtime.events)
    original = messages.get_by_idempotency_key(run.session_id, f'agent-run:{run.id}:user')
    snapshot(chat, run, [alias(run, rich)])
    assert messages.get(original.message.id, session_id=run.session_id) == original
    second, _ = runtime.agents.create_run(session_id=run.session_id, agent_key='ai2apps.general-agent', input={'message_id':original.message.id,'model':'fixture'})
    snapshot(chat, second, chat.get_content(run.session_id).messages)
    assert messages.get(original.message.id, session_id=run.session_id) == original
    runtime.agents.request_cancel(run.id)
    snapshot(chat, second, [])  # Another live Run still owns this explicit reference.
    assert messages.get(original.message.id, session_id=run.session_id) == original


def test_legacy_read_projection_only_coalesces_exact_run_and_leaves_storage(runtime):
    chat, run, executor, context = setup(runtime)
    executor._ensure_prompt(context)
    repo = MessageRepository(runtime.database, runtime.events)
    repo.append(session_id=run.session_id, role=MessageRole.USER,
                parts=(MessagePartInput(kind='chat_ui_content',content={'content':'original UI text'}),),
                metadata={'agent_run_id':run.id})
    repo.append(session_id=run.session_id, role=MessageRole.USER,
                parts=(MessagePartInput(kind='text',content={'text':'same prompt'}),), metadata={})
    assert len(chat.get_content(run.session_id).messages) == 2
    assert len(repo.list_for_session(run.session_id)) == 3  # No migration/deletion on read.
    other, foreign, _, _ = setup(runtime)
    snapshot(other, foreign, [alias(run)])  # Foreign Run metadata is not ownership.
    assert len(other.get_content(foreign.session_id).messages) == 1


@pytest.mark.asyncio
async def test_real_general_run_snapshot_during_model_then_completion_and_terminal_delete(runtime):
    chat, run, executor, context = setup(runtime)
    entered, release = asyncio.Event(), asyncio.Event()
    async def model(request):
        entered.set()
        await release.wait()
        return {'choices':[{'message':{'role':'assistant','content':'done'},'finish_reason':'stop'}]}
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.agent_runtime.wake()
        await asyncio.wait_for(entered.wait(), 5)
        repo = MessageRepository(runtime.database, runtime.events)
        original = repo.get_by_idempotency_key(run.session_id, f'agent-run:{run.id}:user')
        snapshot(chat, run, [])  # Stale UI cannot delete an in-flight input.
        snapshot(chat, run, [alias(run)])
        assert repo.get(original.message.id, session_id=run.session_id) == original
        release.set()
        completed = await wait(runtime, run.id, 'completed')
        result_id = completed.output['message_id']
        restored = snapshot(chat, run, chat.get_content(run.session_id).messages)
        assert len(restored.messages) == 2
        assert repo.get(result_id, session_id=run.session_id).message.id == result_id
        # Existing explicit deletion/edit truncation of completed history remains supported.
        assert snapshot(chat, run, []).messages == ()
    finally:
        release.set()
        await runtime.stop_background_tasks()


def test_identical_text_from_different_runs_is_not_deduplicated(runtime):
    chat, first, executor, context = setup(runtime)
    executor._ensure_prompt(context)
    second, _ = runtime.agents.create_run(session_id=first.session_id, agent_key='ai2apps.general-agent',
        input={'model':'fixture', 'prompt':'same prompt', 'tools':[]})
    executor._ensure_prompt(SimpleNamespace(run=second))
    content = snapshot(chat, first, [alias(first), alias(second)])
    assert len(content.messages) == 2
    assert {m.metadata['agent_run_id'] for m in content.messages} == {first.id, second.id}


@pytest.mark.asyncio
async def test_general_form_wait_recovery_cancel_keeps_one_input_and_original_call(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.agents.general import _tool_alias
    from ai2apps.agents.parameter_forms import ParameterForm, register_form, FORMS
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.identity import RequestPrincipal
    key = 'fixture.identity.review'
    register_form(ParameterForm(key, 'fixture.owner', {'type':'object','properties':{'name':{'type':'string'}},'required':['name']}, ()))
    chat, run, _, _ = setup(runtime, tools=['app.collect_parameters'])
    async def model(request):
        results = [json.loads(m['content']) for m in request['messages'] if m.get('role') == 'tool']
        if any(r.get('status') == 'cancelled' for r in results):
            return {'choices':[{'message':{'role':'assistant','content':'cancelled without execution'},'finish_reason':'stop'}]}
        return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'review-input','type':'function',
            'function':{'name':_tool_alias('app.collect_parameters'),'arguments':json.dumps({'request_id':'identity-review','capability':key,'values':{'name':'draft'}})}}]},'finish_reason':'tool_calls'}]}
    runtime.agent_runtime.bind_model_provider(model)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime, principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.agent_runtime.wake()
        await wait(runtime, run.id, 'waiting_input')
        item = runtime.agents.list_interactions(run.id)[0]
        from ai2apps.agents.general import _tool_action_key
        model_step = next(s for s in reversed(runtime.agents.list_steps(run.id)) if s.kind == 'model')
        original_call_key = _tool_action_key(model_step.sequence, 0, 'review-input')
        snapshot(chat, run, [alias(run)])
        await runtime.stop_background_tasks()
        await runtime.start_background_tasks(retention_interval_seconds=60)
        restored = chat.get_content(run.session_id)
        assert len([m for m in restored.messages if m.role is MessageRole.USER]) == 1
        assert runtime.agents.list_interactions(run.id)[0].id == item.id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/respond'
            response=await client.post(url,json={'response_id':'identity-cancel','response':{'status':'cancelled','result':{}}})
            assert response.status_code == 200, response.text
        await wait(runtime, run.id, 'completed')
        current = [s for s in runtime.agents.list_steps(run.id) if s.tool_name == 'app.collect_parameters']
        assert len(current) == 1 and current[0].action_key == original_call_key
        assert len([m for m in chat.get_content(run.session_id).messages if m.role is MessageRole.USER]) == 1
    finally:
        await runtime.stop_background_tasks()
        FORMS.pop(key,None)
