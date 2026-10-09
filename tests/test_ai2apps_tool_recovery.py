"""Isolated fixtures for paired tool failures and safe continuation."""

import asyncio
import json

import pytest
from test_ai2apps_agents import _runtime, _session, _wait_status

from ai2apps.agents import AgentRunStatus, RunStepStatus
from ai2apps.agents.general import GeneralAgentExecutor
from ai2apps.agents.session_memory import SessionMemory
from ai2apps.agents.tool_recovery import error_result, model_visible, recoverable
from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRuntimeMode,
    ToolProviderError,
)


@pytest.mark.parametrize(
    "code",
    [
        "provider_error",
        "tool_timeout",
        "invalid_tool_output",
        "invalid_tool_input",
        "service_unavailable",
        "provider_unavailable",
    ],
)
def test_policy_is_bounded_and_preserves_effectful_failures(code):
    assert recoverable(code, effects=(), enabled=True, prior_errors=0)
    assert not recoverable(code, effects=("write",), enabled=True, prior_errors=0)
    assert not recoverable(code, effects=(), enabled=False, prior_errors=0)
    assert not recoverable(code, effects=(), enabled=True, prior_errors=3)


@pytest.mark.parametrize(
    "code",
    [
        "capability_denied",
        "provider_identity_mismatch",
        "session_not_found",
        "tool_cancelled",
        "unknown_error",
    ],
)
def test_policy_never_converts_control_or_unknown_failures(code):
    assert not recoverable(code, effects=(), enabled=True, prior_errors=0)
    assert not recoverable(
        code, effects=(), enabled=True, prior_errors=0, preflight=True
    )


def test_error_envelope_is_bounded_and_legacy_compatible():
    result = error_result("provider_error", "x" * 4000)
    assert len(result["message"]) == 2048
    assert model_visible(result)
    assert model_visible({"recoverable_input_error": True})
    assert not model_visible({"code": "provider_error"})


def _response(calls=None):
    message = {"role": "assistant", "content": "done" if calls is None else None}
    if calls is not None:
        message["tool_calls"] = calls
    return {
        "choices": [
            {
                "message": message,
                "finish_reason": "stop" if calls is None else "tool_calls",
            }
        ]
    }


def _call(identifier, alias, arguments):
    return {
        "id": identifier,
        "type": "function",
        "function": {"name": alias, "arguments": arguments},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["provider", "timeout", "output", "json", "array", "alias"]
)
async def test_failure_pairs_batch_results_persists_and_allows_new_decision(
    tmp_path, failure
):
    runtime = _runtime(tmp_path)
    executed = []
    requests = []
    if failure == "timeout":
        tool = runtime.services.get_tool("system.echo")
        runtime.services.ensure_tool(
            service_id=tool.service_id,
            qualified_name=tool.qualified_name,
            display_name=tool.display_name,
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            timeout_ms=10,
        )

    async def echo(arguments, context):
        executed.append(arguments["value"])
        if arguments["value"] == "fail":
            if failure == "provider":
                raise ToolProviderError("fixture failure")
            if failure == "timeout":
                await asyncio.sleep(1)
            if failure == "output":
                return []
        return {"value": arguments["value"]}

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=echo
    )

    async def model(request):
        requests.append(request)
        alias = next(
            t["function"]["name"]
            for t in request["tools"]
            if t["function"]["name"].startswith("system__echo_")
        )
        if len(requests) == 1:
            args = (
                '{"value":'
                if failure == "json"
                else "[]"
                if failure == "array"
                else '{"value":"fail"}'
            )
            return _response(
                [
                    _call(
                        "bad", "missing_alias" if failure == "alias" else alias, args
                    ),
                    _call("good", alias, '{"value":"ok"}'),
                ]
            )
        results = [m for m in request["messages"] if m["role"] == "tool"]
        assert [m["tool_call_id"] for m in results] == ["bad", "good"]
        assert json.loads(results[0]["content"])["error"]["is_error"] is True
        assert "ok" in results[1]["content"]
        return _response()

    runtime.agent_runtime.bind_model_provider(model)
    session = _session(runtime)
    run, _ = runtime.agents.create_run(
        session_id=session,
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "continue safely"},
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED, timeout=20)
        assert executed == (
            ["ok"] if failure in {"json", "array", "alias"} else ["fail", "ok"]
        )
        assert len(requests) == 2
        steps = runtime.agents.list_steps(run.id)
        assert len([s for s in steps if s.status is RunStepStatus.FAILED]) == 1
        # A fresh executor rebuilds the same paired transcript from durable rows.
        executor = GeneralAgentExecutor(runtime.database, runtime.events, runtime.tools)
        transcript, *_ = executor._transcript([], steps, result_reader_alias=None)
        assert [m["tool_call_id"] for m in transcript if m["role"] == "tool"] == [
            "bad",
            "good",
        ]
        memory = SessionMemory(runtime.database, runtime.events, None)
        with runtime.database.transaction() as connection:
            nodes = memory._historical_rounds(connection, run.id, session)
        assert nodes and "model_visible_error" in str(nodes)
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("effectful", [False, True])
async def test_provider_failure_is_bounded_and_write_is_not_replayed(
    tmp_path, effectful
):
    runtime = _runtime(tmp_path)
    service = runtime.services.ensure_service(
        service_key="test.recovery",
        package_id="test.recovery",
        package_version="1",
        display_name="Recovery",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
    )
    instance = runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="test:recovery",
        status=ServiceInstanceStatus.RUNNING,
    )
    runtime.services.ensure_tool(
        service_id=service.id,
        qualified_name="fixture.failure",
        display_name="Fail",
        description="Recovery fixture",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        effects=("write",) if effectful else (),
    )
    executions = []
    model_calls = []

    async def handler(arguments, context):
        executions.append(arguments)
        raise ToolProviderError("failure")

    runtime.service_registry.bind_tool(
        "fixture.failure", provider_key=instance.provider_key, handler=handler
    )

    async def model(request):
        model_calls.append(request)
        alias = next(
            t["function"]["name"]
            for t in request["tools"]
            if t["function"]["name"].startswith("fixture__failure_")
        )
        return _response([_call(f"call-{len(model_calls)}", alias, "{}")])

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "fail"},
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        finished = await _wait_status(
            runtime, run.id, AgentRunStatus.FAILED, timeout=20
        )
        assert finished.error["code"] == "provider_error"
        assert len(executions) == (1 if effectful else 4)
        assert len(model_calls) == len(executions)
        failures = runtime.agents.list_steps(run.id)
        assert sum(model_visible(s.error) for s in failures) == (0 if effectful else 3)
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


@pytest.mark.asyncio
async def test_cancellation_during_tool_does_not_resume_model(tmp_path):
    runtime = _runtime(tmp_path)
    started = asyncio.Event()
    requests = []

    async def echo(arguments, context):
        started.set()
        await asyncio.Event().wait()

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=echo
    )

    async def model(request):
        requests.append(request)
        alias = next(
            t["function"]["name"]
            for t in request["tools"]
            if t["function"]["name"].startswith("system__echo_")
        )
        return _response([_call("cancel", alias, '{"value":"wait"}')])

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "wait"},
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await asyncio.wait_for(started.wait(), timeout=10)
        runtime.agent_runtime.cancel(run.id)
        await _wait_status(runtime, run.id, AgentRunStatus.CANCELLED, timeout=10)
        assert len(requests) == 1
        assert not any(
            model_visible(s.error) for s in runtime.agents.list_steps(run.id)
        )
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["provider", "output"])
async def test_injected_secret_is_redacted_from_failure(tmp_path, failure):
    from test_ai2apps_secrets import _runtime as secret_runtime

    from ai2apps.services import ToolCallContext, ToolGatewayError

    runtime, _ = secret_runtime(tmp_path)
    secret = runtime.secrets.create(
        name="fixture", value="do-not-expose-fixture", allowed_tools=("system.echo",)
    )

    async def handler(arguments, context):
        if failure == "provider":
            raise ToolProviderError(arguments["value"])
        return arguments["value"]  # violates object output schema

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=handler
    )
    try:
        with pytest.raises(ToolGatewayError) as caught:
            await runtime.tools.execute(
                "system.echo",
                {"value": secret.uri},
                context=ToolCallContext(caller_id="agent:test"),
            )
        result = error_result(caught.value.code, str(caught.value))
        assert "do-not-expose-fixture" not in json.dumps(result)
        assert "[secret]" in result["message"]
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_custom_executor_remains_terminal_without_opt_in(tmp_path):
    runtime = _runtime(tmp_path)

    async def handler(arguments, context):
        raise ToolProviderError("fixture failure")

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=handler
    )
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.diagnostic-agent",
        input={
            "mode": "tool",
            "tool_name": "system.echo",
            "arguments": {"value": "fail"},
        },
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        finished = await _wait_status(
            runtime, run.id, AgentRunStatus.FAILED, timeout=10
        )
        assert finished.error["code"] == "provider_error"
        assert not any(
            model_visible(s.error) for s in runtime.agents.list_steps(run.id)
        )
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


@pytest.mark.asyncio
async def test_restart_after_error_does_not_replay_finished_tools(tmp_path):
    runtime = _runtime(tmp_path)
    executed = []
    reached_next_model = asyncio.Event()
    requests = []

    async def echo(arguments, context):
        executed.append(arguments["value"])
        if arguments["value"] == "fail":
            raise ToolProviderError("fixture failure")
        return arguments

    async def model(request):
        requests.append(request)
        if len(requests) > 1:
            reached_next_model.set()
            await asyncio.Event().wait()
        alias = next(
            t["function"]["name"]
            for t in request["tools"]
            if t["function"]["name"].startswith("system__echo_")
        )
        return _response(
            [
                _call("bad", alias, '{"value":"fail"}'),
                _call("good", alias, '{"value":"ok"}'),
            ]
        )

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=echo
    )
    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "resume"},
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await asyncio.wait_for(reached_next_model.wait(), timeout=15)
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()

    restarted = _runtime(tmp_path)
    restarted.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=echo
    )

    async def resume_model(request):
        results = [m for m in request["messages"] if m["role"] == "tool"]
        assert [m["tool_call_id"] for m in results] == ["bad", "good"]
        assert json.loads(results[0]["content"])["error"]["code"] == "provider_error"
        return _response()

    restarted.agent_runtime.bind_model_provider(resume_model)
    await restarted.start_background_tasks(retention_interval_seconds=60)
    try:
        await _wait_status(restarted, run.id, AgentRunStatus.COMPLETED, timeout=15)
        assert executed == ["fail", "ok"]
    finally:
        await restarted.stop_background_tasks()
        restarted.stop()
