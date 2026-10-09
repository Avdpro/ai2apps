"""Long-history admission, hard-loss recovery and bounded model correction."""

import hashlib
import json

import pytest
from test_ai2apps_agents import _runtime, _session, _user_message, _wait_status

from ai2apps.agents import AgentRunStatus, CompleteAction, RunStepStatus, ToolCallAction
from ai2apps.agents.context import ContextBudgetError, bound_request
from ai2apps.agents.general import GeneralAgentExecutor
from ai2apps.agents.models import AgentExecutionContext, ModelCallAction
from ai2apps.core import ResourceNotFoundError
from ai2apps.storage.repositories import MessageRepository


def _context(runtime, run):
    definition, run, _, steps, interactions = runtime.agents.snapshot(run.id)
    return AgentExecutionContext(definition, run, steps, interactions)


@pytest.mark.asyncio
async def test_long_history_anchors_explicit_and_generated_inputs(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    for i in range(1002):
        current = _user_message(runtime, session, f"message-{i}")
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "message_id": current.message.id},
    )
    _user_message(runtime, session, "future input must not leak")
    executor = GeneralAgentExecutor(runtime.database, runtime.events, runtime.tools)
    action = await executor(_context(runtime, run))
    assert isinstance(action, ModelCallAction)
    assert action.request["messages"][-1]["content"] == "message-1001"
    assert "future input" not in json.dumps(action.request)
    assert action.request["messages"][0]["content"] == "message-0"
    assert len(action.request["messages"]) == 1002

    generated, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "generated input"},
    )
    for _ in range(2):
        action = await executor(_context(runtime, generated))
        assert isinstance(action, ModelCallAction)
        assert action.request["messages"][-1]["content"] == "generated input"
    repository = MessageRepository(runtime.database, runtime.events)
    assert len(repository.list_for_session(session, latest=True, limit=2)) == 2
    with pytest.raises(ResourceNotFoundError):
        repository.list_for_session(session, latest=True, app_instance_id="another-app")
    assert (
        repository.get_by_idempotency_key(
            _session(runtime), f"agent-run:{generated.id}:user"
        )
        is None
    )
    runtime.stop()


@pytest.mark.asyncio
async def test_hard_loss_abandons_model_attempt_and_resumes(tmp_path):
    runtime = _runtime(tmp_path)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "resume me"},
    )
    assert runtime.agents.claim_next().id == run.id
    runtime.agents.transition(
        run.id, expected={AgentRunStatus.PLANNING}, status=AgentRunStatus.RUNNING
    )
    step, _ = runtime.agents.create_step(
        run.id, action_key="model:1", kind="model", input={"model": "test"}
    )
    # Do not call stop(): this snapshot represents lost process cleanup.
    assert runtime.agents.recover_interrupted()["recovered"] == 1
    assert runtime.agents.recover_interrupted()["recovered"] == 0
    recovered = runtime.agents.list_steps(run.id)[0]
    assert recovered.id == step.id
    assert recovered.status is RunStepStatus.CANCELLED
    assert recovered.action_key != "model:1"
    assert recovered.error["code"] == "process_interrupted_during_model"

    runtime.agent_runtime.bind_model_provider(
        lambda request: {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "resumed"},
                    "finish_reason": "stop",
                }
            ]
        }
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        steps = runtime.agents.list_steps(run.id)
        assert [s.status for s in steps] == [
            RunStepStatus.CANCELLED,
            RunStepStatus.COMPLETED,
        ]
        events = runtime.events.list_after(subject_id=run.id, limit=1000)
        audit = next(
            e.payload for e in events if e.type == "agent.model.context.prepared"
        )
        wire = json.dumps(
            steps[-1].input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        assert audit["request_sha256"] == hashlib.sha256(wire).hexdigest()
        assert audit["step_id"] == steps[-1].id
    finally:
        await runtime.stop_background_tasks()


def test_byte_budget_preserves_current_input_system_and_tool_pairs():
    current = {"role": "user", "content": "current task"}
    call = {
        "role": "assistant",
        "tool_calls": [{"id": "a", "function": {"name": "read", "arguments": "{}"}}],
    }
    result = {"role": "tool", "tool_call_id": "a", "content": "result"}
    request = {
        "model": "test",
        "messages": [
            {"role": "system", "content": "must remain"},
            {"role": "user", "content": "古い内容" * 2000},
            {"role": "assistant", "content": "old reply"},
            current,
            call,
            result,
        ],
    }
    bounded, audit = bound_request(request, base_count=4, max_bytes=750)
    assert bounded["messages"][-3:] == [current, call, result]
    assert any(
        m["content"] == "must remain" for m in bounded["messages"] if "content" in m
    )
    assert audit["request_bytes"] <= 750
    assert audit["omitted_messages"] == 2
    assert len(request["messages"]) == 6
    assert bound_request(request, base_count=4, max_bytes=750) == (bounded, audit)
    with pytest.raises(ContextBudgetError):
        bound_request(request, base_count=4, max_bytes=50)


@pytest.mark.asyncio
async def test_delegation_anchors_generated_parent_input(tmp_path):
    runtime = _runtime(tmp_path)
    executor = GeneralAgentExecutor(runtime.database, runtime.events, runtime.tools)
    for name in ("parent", "child"):
        runtime.agents.ensure_definition(
            agent_key=f"test.anchor-{name}",
            package_version="1",
            display_name=name,
            executor_key=f"test:anchor-{name}",
        )

    def parent(context):
        if context.step("delegate") is not None:
            return CompleteAction({"done": True})
        assert executor._ensure_prompt(context) is None
        _user_message(runtime, context.run.session_id, "later unrelated input")
        return ToolCallAction(
            call_id="delegate",
            tool_name="agent.delegate",
            arguments={
                "agent": "test.anchor-child",
                "task": "child task",
                "request_key": "one",
            },
        )

    def child(context):
        assert context.run.delegation["context"]["parent_message_id"]
        messages, error = executor._messages_for_run(context)
        assert error is None
        assert [m["content"] for m in messages] == ["parent task", "child task"]
        return CompleteAction({"anchored": True})

    runtime.agent_runtime.bind_executor("test:anchor-parent", parent)
    runtime.agent_runtime.bind_executor("test:anchor-child", child)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="test.anchor-parent",
        input={"prompt": "parent task"},
    )
    await runtime.agent_runtime.start()
    try:
        await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED, timeout=8)
        assert runtime.agents.list_children(run.id)[0].output == {"anchored": True}
    finally:
        await runtime.agent_runtime.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("always_invalid", [False, True])
async def test_schema_error_is_correctable_but_bounded(tmp_path, always_invalid):
    runtime = _runtime(tmp_path)
    calls = []
    tool_calls = []

    async def echo(arguments, _context):
        tool_calls.append(arguments)
        return {"value": arguments["value"]}

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=echo
    )

    async def model(request):
        calls.append(request)
        alias = next(
            t["function"]["name"]
            for t in request["tools"]
            if t["function"]["name"].startswith("system__echo_")
        )
        if len(calls) > 1:
            tool_result = request["messages"][-1]
            assert tool_result["role"] == "tool"
            if always_invalid or len(calls) == 2:
                assert (
                    json.loads(tool_result["content"])["error"]["code"]
                    == "invalid_tool_input"
                )
        if len(calls) == 3 and not always_invalid:
            return {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "fixed"},
                        "finish_reason": "stop",
                    }
                ]
            }
        arguments = {} if always_invalid or len(calls) == 1 else {"value": "valid"}
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call-{len(calls)}",
                                "type": "function",
                                "function": {
                                    "name": alias,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "echo"},
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        expected = AgentRunStatus.FAILED if always_invalid else AgentRunStatus.COMPLETED
        finished = await _wait_status(runtime, run.id, expected, timeout=12)
        assert len(calls) == (4 if always_invalid else 3)
        assert tool_calls == ([] if always_invalid else [{"value": "valid"}])
        if always_invalid:
            assert finished.error["code"] == "invalid_tool_input"
        failures = [
            s
            for s in runtime.agents.list_steps(run.id)
            if s.status is RunStepStatus.FAILED
        ]
        assert len(failures) == (4 if always_invalid else 1)
    finally:
        await runtime.stop_background_tasks()
