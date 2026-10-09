"""Durable session projection acceptance over real SQLite and scheduler."""

import asyncio
import json

import pytest
from test_ai2apps_agents import _runtime, _session, _wait_status
from test_ai2apps_context_checkpoints import response, summary

from ai2apps.agents import AgentRunStatus
from ai2apps.agents.general import _session_message
from ai2apps.agents.session_memory import SESSION_KEY, SessionMemory
from ai2apps.context_engine import ContextOverflowError
from ai2apps.core import MessageRole
from ai2apps.storage import MessagePartInput
from ai2apps.storage.repositories import MessageRepository


def history(runtime, session, count=6):
    repository = MessageRepository(runtime.database, runtime.events)
    for i in range(count):
        repository.append(
            session_id=session,
            role=MessageRole.USER,
            parts=(
                MessagePartInput(kind="text", content={"text": f"PIN-{i} must stay"}),
            ),
        )
        repository.append(
            session_id=session,
            role=MessageRole.ASSISTANT,
            parts=(
                MessagePartInput(kind="text", content={"text": str(i) + "x" * 3000}),
            ),
        )
    return repository


@pytest.mark.asyncio
async def test_manual_compaction_cross_run_preserves_constraints_and_sources(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    history(runtime, session)
    calls = []

    async def model(request):
        assert SESSION_KEY not in request
        calls.append(request)
        return response(json.dumps(summary()))

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"prompt": "compact", "model": "test", "memory_only": True, "tools": []},
    )
    await runtime.agent_runtime.start()
    try:
        done = await _wait_status(
            runtime,
            run.id,
            {AgentRunStatus.COMPLETED, AgentRunStatus.FAILED},
            timeout=15,
        )
        assert done.status is AgentRunStatus.COMPLETED, done.error
        assert len(calls) == 1
        memory = SessionMemory(runtime.database, runtime.events, _session_message)
        surface = memory.snapshot(session, None)
        assert len(surface.nodes) < 13
        node = next(n for n in surface.nodes if n.id.startswith("memory:"))
        content = json.loads(node.body["content"])
        assert content["protected_user_messages"][0]["content"] == "PIN-0 must stay"
        assert "PIN-0" in memory.source(session, content["source"]["transaction"])
        with pytest.raises(ValueError):
            memory.source(_session(runtime, "other"), content["source"]["transaction"])
        # New executor instance replays committed projection; originals stay intact.
        assert (
            SessionMemory(runtime.database, runtime.events, _session_message).snapshot(
                session, None
            )
            == surface
        )
        assert (
            len(
                MessageRepository(runtime.database, runtime.events).list_for_session(
                    session, limit=100
                )
            )
            == 13
        )
        await asyncio.sleep(0.05)
    finally:
        await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_invalid_summary_is_bounded_and_originals_retained(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    history(runtime, session)

    async def model(request):
        return response("invalid")

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"prompt": "compact", "model": "test", "memory_only": True, "tools": []},
    )
    await runtime.agent_runtime.start()
    try:
        done = await _wait_status(
            runtime,
            run.id,
            {AgentRunStatus.COMPLETED, AgentRunStatus.FAILED},
            timeout=15,
        )
        assert done.status is AgentRunStatus.FAILED
        assert done.error["code"] == "session_memory_unavailable"
        assert len(runtime.agents.list_steps(run.id)) == 1
        assert not any(
            n.id.startswith("memory:")
            for n in SessionMemory(runtime.database, runtime.events, _session_message)
            .snapshot(session, None)
            .nodes
        )
    finally:
        await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_provider_overflow_compacts_once_and_retries_without_replaying_tools(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    history(runtime, session)
    calls = []

    async def model(request):
        calls.append(request)
        if len(calls) == 1:
            raise ContextOverflowError("context window exceeded")
        if "source_message_ids" in str(request["messages"]):
            return response(json.dumps(summary()))
        return response("done")

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"prompt": "finish", "model": "test"},
    )
    await runtime.agent_runtime.start()
    try:
        done = await _wait_status(
            runtime,
            run.id,
            {AgentRunStatus.COMPLETED, AgentRunStatus.FAILED},
            timeout=20,
        )
        assert done.status is AgentRunStatus.COMPLETED, done.error
        assert len(calls) == 3
        assert len(str(calls[-1]["messages"])) < len(str(calls[0]["messages"]))
        assert not any(s.kind == "tool" for s in runtime.agents.list_steps(run.id))
    finally:
        await runtime.agent_runtime.stop()


def test_projection_loads_more_than_one_thousand_messages(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    repository = MessageRepository(runtime.database, runtime.events)
    for i in range(1002):
        repository.append(
            session_id=session,
            role=MessageRole.USER,
            parts=(MessagePartInput(kind="text", content={"text": str(i)}),),
        )
    surface = SessionMemory(
        runtime.database, runtime.events, _session_message
    ).snapshot(session, None)
    assert len(surface.nodes) == 1002
    assert surface.nodes[0].body["content"] == "0"
    assert surface.nodes[-1].pinned


@pytest.mark.asyncio
async def test_token_pressure_is_measured_and_audited(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    history(runtime, session)
    requests = []

    async def measure(request, owner):
        assert owner.session_id == session
        return {
            "provider": "test",
            "model": "test",
            "capacity": 12000,
            "input_tokens": 10000 if len(str(request["messages"])) > 10000 else 1000,
            "output_reservation": 2048,
            "unit": "tokens",
            "token_count_exact": True,
        }

    async def model(request):
        requests.append(request)
        if "source_message_ids" in str(request["messages"]):
            return response(json.dumps(summary()))
        assert request["max_tokens"] == 2048
        return response("done")

    runtime.agent_runtime.bind_context_provider(measure)
    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "finish"},
    )
    await runtime.agent_runtime.start()
    try:
        done = await _wait_status(
            runtime,
            run.id,
            {AgentRunStatus.COMPLETED, AgentRunStatus.FAILED},
            timeout=20,
        )
        assert done.status is AgentRunStatus.COMPLETED, done.error
        assert len(requests) == 2
        event = runtime.events.latest_for_subject(
            run.id, event_type="agent.model.context.prepared"
        )
        assert event.payload["context_meter"]["token_count_exact"]
    finally:
        await runtime.agent_runtime.stop()


def test_provider_overflow_only_accepts_confirmed_codes():
    from ai2apps.agents.context_meter import provider_overflow

    assert provider_overflow(
        400, json.dumps({"error": {"code": "context_length_exceeded"}})
    )
    assert provider_overflow(
        400,
        json.dumps(
            {
                "detail": "Prompt too long: 100 tokens exceeds max context window of 50 tokens"
            }
        ),
    )
    assert not provider_overflow(
        500, json.dumps({"error": {"code": "context_length_exceeded"}})
    )
    assert not provider_overflow(
        400, json.dumps({"error": {"message": "context_length_exceeded"}})
    )
    assert not provider_overflow(400, "not json")


def test_source_edit_rejects_commit_and_pending_lock_blocks_other_run(tmp_path):
    from types import SimpleNamespace

    from test_ai2apps_harness_reliability import _context

    from ai2apps.agents import RunStepStatus
    from ai2apps.context_engine import BusyError

    runtime = _runtime(tmp_path)
    session = _session(runtime)
    history(runtime, session)
    memory = SessionMemory(runtime.database, runtime.events, _session_message)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "x"},
    )
    other, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "y"},
    )
    context = _context(runtime, run)
    action = memory.action(context, None, {"model": "test", "messages": []}, force=True)
    assert action
    with pytest.raises(BusyError):
        memory.action(
            _context(runtime, other),
            None,
            {"model": "test", "messages": []},
            force=True,
        )
    first = memory.snapshot(session, None).nodes[0]
    with runtime.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE message_parts SET content_json=? WHERE message_id=?",
            (json.dumps({"text": "changed constraint"}), first.id),
        )
    step = SimpleNamespace(
        kind="model",
        input=action.request,
        status=RunStepStatus.COMPLETED,
        output=response(json.dumps(summary())),
        id="summary",
    )
    memory.adopt(SimpleNamespace(run=run, steps=(step,)), None)
    assert not any(
        n.id.startswith("memory:") for n in memory.snapshot(session, None).nodes
    )


def test_image_offload_is_logged_replayable_and_original_remains(tmp_path):
    from test_ai2apps_harness_reliability import _context

    runtime = _runtime(tmp_path)
    session = _session(runtime)
    repository = MessageRepository(runtime.database, runtime.events)
    image = repository.append(
        session_id=session,
        role=MessageRole.USER,
        parts=(
            MessagePartInput(
                kind="openai_content",
                content={
                    "content": [
                        {"type": "text", "text": "inspect original"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,ABC"},
                        },
                    ]
                },
            ),
        ),
    ).value
    repository.append(
        session_id=session,
        role=MessageRole.USER,
        parts=(
            MessagePartInput(kind="text", content={"text": "current pinned input"}),
        ),
    )
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "x"},
    )
    memory = SessionMemory(runtime.database, runtime.events, _session_message)
    assert memory.offload_oldest_image(_context(runtime, run), None)
    surface = memory.snapshot(session, None)
    assert surface.nodes[0].body["content"][1]["type"] == "text"
    assert "omitted" in surface.nodes[0].body["content"][1]["text"]
    source = json.loads(surface.nodes[0].body["content"][1]["text"])["source"]
    assert "image_url" in memory.source(session, source["transaction"])
    assert (
        repository.get(image.message.id, session_id=session)
        .parts[0]
        .content["content"][1]["type"]
        == "image_url"
    )
    assert not memory.offload_oldest_image(_context(runtime, run), None)


@pytest.mark.asyncio
async def test_manual_api_is_idempotent_and_queues_maintenance_run(tmp_path):
    import httpx
    from fastapi import FastAPI

    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.identity import RequestPrincipal

    runtime = _runtime(tmp_path)
    session = _session(runtime)
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        url = f"/v1/platform/sessions/{session}/memory/compact"
        first = await client.post(
            url, json={"model": "test", "idempotency_key": "manual-memory"}
        )
        second = await client.post(
            url, json={"model": "test", "idempotency_key": "manual-memory"}
        )
        assert first.status_code == 202, first.text
        assert first.json()["id"] == second.json()["id"]
        run = runtime.agents.get_run(first.json()["id"])
        assert run.input["memory_only"] is True and run.input["tools"] == []
        missing = await client.post(
            "/v1/platform/sessions/missing/memory/compact", json={"model": "test"}
        )
        assert missing.status_code in {403, 404}


def test_old_run_tool_rounds_are_complete_and_never_execute_on_projection(tmp_path):
    from ai2apps.agents import RunStepStatus
    from ai2apps.agents.general import _tool_action_key

    runtime = _runtime(tmp_path)
    session = _session(runtime)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "old task"},
    )
    model, _ = runtime.agents.create_step(
        run.id, action_key="model:1", kind="model", input={"model": "test"}
    )
    call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "system__echo", "arguments": '{"value":"original"}'},
    }
    runtime.agents.settle_step(
        model.id,
        status=RunStepStatus.COMPLETED,
        output={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [call],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
    )
    tool, _ = runtime.agents.create_step(
        run.id,
        action_key=_tool_action_key(model.sequence, 0, "call-1"),
        kind="tool",
        input={"value": "original"},
        tool_name="system.echo",
    )
    runtime.agents.settle_step(
        tool.id, status=RunStepStatus.COMPLETED, output={"value": "original result"}
    )
    MessageRepository(runtime.database, runtime.events).append(
        session_id=session,
        role=MessageRole.ASSISTANT,
        metadata={"agent_run_id": run.id},
        parts=(MessagePartInput(kind="text", content={"text": "finished old task"}),),
    )
    memory = SessionMemory(runtime.database, runtime.events, _session_message)
    nodes = memory.snapshot(session, None).nodes
    assert [n.body["role"] for n in nodes] == ["assistant", "tool", "assistant"]
    assert "original result" in nodes[1].body["content"]
    assert len(runtime.agents.list_steps(run.id)) == 2
    # A missing/uncertain result is never exposed as an executable unpaired call.
    with runtime.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE run_steps SET status='uncertain' WHERE id=?", (tool.id,)
        )
    assert len(memory.snapshot(session, None).nodes) == 1


def test_abandoned_summary_can_resume_with_a_new_transaction(tmp_path):
    from test_ai2apps_harness_reliability import _context

    from ai2apps.agents import RunStepStatus

    runtime = _runtime(tmp_path)
    session = _session(runtime)
    history(runtime, session)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "x"},
    )
    memory = SessionMemory(runtime.database, runtime.events, _session_message)
    first = memory.action(
        _context(runtime, run), None, {"model": "test", "messages": []}, force=True
    )
    step, _ = runtime.agents.create_step(
        run.id, action_key=first.call_id, kind="model", input=first.request
    )
    runtime.agents.settle_step(
        step.id, status=RunStepStatus.CANCELLED, error={"code": "runtime_interrupted"}
    )
    second = memory.action(
        _context(runtime, run), None, {"model": "test", "messages": []}, force=True
    )
    assert second and second.call_id != first.call_id
    assert (
        second.request[SESSION_KEY]["source_sha256"]
        == first.request[SESSION_KEY]["source_sha256"]
    )


def test_pruning_historical_tool_results_is_durable_and_idempotent(tmp_path):
    from test_ai2apps_harness_reliability import _context

    from ai2apps.agents import RunStepStatus
    from ai2apps.agents.general import _tool_action_key

    runtime = _runtime(tmp_path)
    session = _session(runtime)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "old task"},
    )
    model, _ = runtime.agents.create_step(
        run.id, action_key="model:1", kind="model", input={}
    )
    call = {
        "id": "call",
        "type": "function",
        "function": {"name": "echo", "arguments": "{}"},
    }
    runtime.agents.settle_step(
        model.id,
        status=RunStepStatus.COMPLETED,
        output={
            "choices": [
                {
                    "message": {"role": "assistant", "tool_calls": [call]},
                    "finish_reason": "tool_calls",
                }
            ]
        },
    )
    tool, _ = runtime.agents.create_step(
        run.id,
        action_key=_tool_action_key(model.sequence, 0, "call"),
        kind="tool",
        input={},
        tool_name="system.echo",
    )
    runtime.agents.settle_step(
        tool.id, status=RunStepStatus.COMPLETED, output={"evidence": "x" * 50000}
    )
    MessageRepository(runtime.database, runtime.events).append(
        session_id=session,
        role=MessageRole.ASSISTANT,
        metadata={"agent_run_id": run.id},
        parts=(MessagePartInput(kind="text", content={"text": "done"}),),
    )
    current, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "new task"},
    )
    memory = SessionMemory(runtime.database, runtime.events, _session_message)
    assert memory.prune_old_results(_context(runtime, current), None) == 1
    node = next(n for n in memory.snapshot(session, None).nodes if n.id == tool.id)
    reference = json.loads(node.body["content"])
    assert reference["type"] == "ai2apps.session-tool-reference/v1"
    assert len(node.body["content"]) < 10000
    assert "x" * 40000 in memory.source(session, reference["source"]["transaction"])
    assert memory.prune_old_results(_context(runtime, current), None) == 0
    assert runtime.agents.list_steps(run.id)[1].output["evidence"] == "x" * 50000
