"""Durable result references, isolation and non-progressing Tool cycles."""

import hashlib
import json
from types import SimpleNamespace

import pytest
from test_ai2apps_agents import _runtime, _session, _wait_status

from ai2apps.agents import AgentRunStatus, RunStepStatus
from ai2apps.agents.loop_guard import repeats_cycle
from ai2apps.agents.result_reference import RESULT_READER, result_preview, result_text
from ai2apps.services import ToolGatewayError


def test_preview_is_reversible_unicode_safe_and_requires_reader():
    output = {"text": "😀中文" * 16000}
    step = SimpleNamespace(id="step", tool_name="source", output=output)
    original = result_text(output)
    assert result_preview(step, reader_alias=None) == original
    preview = json.loads(result_preview(step, reader_alias="reader"))
    assert preview["total_bytes"] == len(original.encode())
    assert preview["sha256"] == hashlib.sha256(original.encode()).hexdigest()
    assert preview["omitted_characters"] == len(original) - len(preview["head"]) - len(
        preview["tail"]
    )
    assert preview["head"] == original[:2048]
    assert preview["tail"] == original[-1024:]
    assert result_text(step.output) == original


@pytest.mark.asyncio
async def test_result_reader_pages_and_isolates_runs_and_sessions(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    run, _ = runtime.agents.create_run(
        session_id=session, agent_key="ai2apps.general-agent", input={"prompt": "read"}
    )
    step, _ = runtime.agents.create_step(
        run.id, action_key="source", kind="tool", tool_name="system.echo", input={}
    )
    output = {"text": "你好😀" * 6000}
    runtime.agents.settle_step(step.id, status=RunStepStatus.COMPLETED, output=output)
    context = runtime.tools.context_for_session(
        caller_id="agent:ai2apps.general-agent", session_id=session, trace_id=run.id
    )
    original = result_text(output)
    chunks = []
    offset = 0
    while True:
        page = (
            await runtime.tools.execute(
                RESULT_READER,
                {"step_id": step.id, "offset": offset, "limit": 8192},
                context=context,
            )
        ).output
        chunks.append(page["content"])
        assert page["sha256"] == hashlib.sha256(original.encode()).hexdigest()
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert "".join(chunks) == original
    other_run, _ = runtime.agents.create_run(
        session_id=session, agent_key="ai2apps.general-agent", input={"prompt": "other"}
    )
    for session_id, trace in [
        (session, other_run.id),
        (_session(runtime), run.id),
        (session, None),
    ]:
        foreign = runtime.tools.context_for_session(
            caller_id="agent:ai2apps.general-agent",
            session_id=session_id,
            trace_id=trace,
        )
        with pytest.raises(ToolGatewayError):
            await runtime.tools.execute(
                RESULT_READER, {"step_id": step.id}, context=foreign
            )
    with pytest.raises(ToolGatewayError):
        await runtime.tools.execute(
            RESULT_READER, {"step_id": step.id, "limit": 8193}, context=context
        )
    with pytest.raises(ToolGatewayError):
        await runtime.tools.execute(
            RESULT_READER,
            {"step_id": step.id, "offset": len(original) + 1},
            context=context,
        )
    runtime.stop()


@pytest.mark.asyncio
async def test_model_can_read_omitted_middle_under_context_budget(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.agents.ensure_definition(
        agent_key="test.references",
        package_version="1",
        display_name="references",
        executor_key="builtin:general-agent",
        max_steps=12,
        manifest={
            "allowed_tools": ["system.echo", RESULT_READER],
            "max_context_bytes": 16000,
        },
    )
    output = {"value": "x" * 50000 + "needle-你好😀" + "y" * 50000}
    runtime.service_registry.bind_tool(
        "system.echo",
        provider_key="builtin:diagnostics",
        handler=lambda args, ctx: output,
    )
    requests = []

    def reply(name, arguments, call_id):
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(arguments),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    def model(request):
        requests.append(request)
        assert len(json.dumps(request, ensure_ascii=False).encode()) < 16000
        if len(requests) == 1:
            echo = next(
                t["function"]["name"]
                for t in request["tools"]
                if t["function"]["name"].startswith("system__echo_")
            )
            return reply(echo, {"value": "large"}, "source")
        if len(requests) == 2:
            preview = json.loads(request["messages"][-1]["content"])
            assert preview["type"] == "ai2apps.tool-result-reference/v1"
            return reply(
                preview["read_with"]["tool"],
                {
                    "step_id": preview["step_id"],
                    "offset": result_text(output).index("needle"),
                    "limit": 9,
                },
                "read-middle",
            )
        page = json.loads(request["messages"][-1]["content"])
        assert page["content"] == "needle-你好"
        assert request["messages"][-1]["tool_call_id"] == "read-middle"
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "found"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="test.references",
        input={"model": "test", "prompt": "find middle"},
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED, timeout=8)
        assert len(requests) == 3
        source = next(
            s for s in runtime.agents.list_steps(run.id) if s.tool_name == "system.echo"
        )
        assert source.output == output
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.parametrize("period", [2, 3, 4])
def test_cycle_guard_allows_output_or_argument_progress(period):
    pattern = [
        SimpleNamespace(tool_name=f"tool{i}", input={"q": i}, output={"value": i})
        for i in range(period)
    ]
    steps = pattern * 3
    assert repeats_cycle(steps, "tool0", {"q": 0})
    assert not repeats_cycle(steps[:-1], "tool0", {"q": 0})
    assert not repeats_cycle(steps, "tool0", {"q": "new"})
    changed = [
        *steps[:-1],
        SimpleNamespace(
            tool_name=pattern[-1].tool_name,
            input=pattern[-1].input,
            output={"new": True},
        ),
    ]
    assert not repeats_cycle(changed, "tool0", {"q": 0})


@pytest.mark.asyncio
async def test_alternating_tool_loop_stops_before_fourth_cycle(tmp_path):
    runtime = _runtime(tmp_path)
    calls = []
    dispatched = []

    def echo(arguments, context):
        dispatched.append(arguments)
        return arguments

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=echo
    )

    def model(request):
        calls.append(request)
        name = next(
            t["function"]["name"]
            for t in request["tools"]
            if t["function"]["name"].startswith("system__echo_")
        )
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
                                    "name": name,
                                    "arguments": json.dumps(
                                        {"value": "A" if len(calls) % 2 else "B"}
                                    ),
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
        input={"model": "test", "prompt": "do work"},
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        # Thirteen durable model/Tool steps traverse the real scheduler; allow
        # its dispatch cadence rather than imposing a short wall-clock race.
        failed = await _wait_status(runtime, run.id, AgentRunStatus.FAILED, timeout=25)
        assert failed.error["code"] == "repeated_tool_cycle"
        assert len(dispatched) == 6
        assert len(calls) == 7
    finally:
        await runtime.stop_background_tasks()
