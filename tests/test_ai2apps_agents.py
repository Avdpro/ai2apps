# SPDX-License-Identifier: Apache-2.0
"""Asynchronous Agent scheduling, interaction, recovery, and API contracts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.agents import (
    AgentRunStatus,
    CompleteAction,
    InteractionAction,
    InteractionKind,
    RunStepStatus,
    ToolCallAction,
)
from ai2apps.agents.general import _provider_tool_schema
from ai2apps.api.router import create_ai2apps_router
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.core import MessageRole, ResourceConflictError, format_utc
from ai2apps.identity import RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ServiceInstanceStatus, ServiceRuntimeMode
from ai2apps.storage import MessagePartInput
from ai2apps.storage.repositories import MessageRepository


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.agents is not None
    assert runtime.agent_runtime is not None
    assert runtime.services is not None
    assert runtime.service_registry is not None
    assert runtime.tools is not None
    return runtime


def test_provider_tool_schema_removes_only_root_composition_keywords():
    source = {
        "type": "object",
        "properties": {
            "target": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "x": {"type": "integer"},
        },
        "anyOf": [{"required": ["target"]}, {"required": ["x"]}],
        "additionalProperties": False,
    }

    normalized = _provider_tool_schema(source)

    assert normalized["type"] == "object"
    assert "anyOf" not in normalized
    assert "anyOf" in normalized["properties"]["target"]
    assert source["anyOf"] == [{"required": ["target"]}, {"required": ["x"]}]


def _session(runtime, title="Agent test"):
    thread, _ = ChatRepository(runtime.database, runtime.events).create_thread(
        title=title
    )
    return thread.session.id


async def _wait_status(runtime, run_id, statuses, timeout=3.0):
    statuses = {statuses} if isinstance(statuses, AgentRunStatus) else set(statuses)
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        run = runtime.agents.get_run(run_id)
        if run.status in statuses:
            return run
        await asyncio.sleep(0.01)
    raise AssertionError(
        f"Run {run_id} did not reach {sorted(item.value for item in statuses)}; "
        f"current={runtime.agents.get_run(run_id).status.value}"
    )


def test_run_creation_is_idempotent_and_always_has_status_line(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)

    first, created = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={"hello": "world"},
        idempotency_key="request-1",
    )
    replay, replay_created = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={"hello": "world"},
        idempotency_key="request-1",
    )

    assert created is True
    assert replay_created is False
    assert replay.id == first.id
    status = runtime.agents.get_status_line(first.id)
    assert status.phase == "queued"
    assert status.text
    with pytest.raises(ResourceConflictError):
        runtime.agents.create_run(
            session_id=session_id,
            agent_key="ai2apps.diagnostic-agent",
            input={"different": True},
            idempotency_key="request-1",
        )


def test_delegated_runs_persist_tree_and_enforce_depth(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    parent, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={"value": "parent"},
    )
    runtime.agents.transition(
        parent.id,
        expected={AgentRunStatus.QUEUED},
        status=AgentRunStatus.PLANNING,
    )
    runtime.agents.transition(
        parent.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.RUNNING,
    )
    child, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={"value": "child"},
        parent_run_id=parent.id,
        delegation={
            "request_key": "child-one",
            "task": "Run the child",
            "parameters": {},
            "context": {},
            "budget": {"max_steps": 2, "timeout_seconds": 30},
        },
    )

    assert child.parent_run_id == parent.id
    assert child.root_run_id == parent.id
    assert child.depth == 1
    assert runtime.agents.list_children(parent.id) == (child,)
    assert runtime.agents.get_delegated_child(parent.id, "child-one") == child

    runtime.agents.transition(
        child.id,
        expected={AgentRunStatus.QUEUED},
        status=AgentRunStatus.PLANNING,
    )
    runtime.agents.transition(
        child.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.RUNNING,
    )
    grandchild, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={"value": "grandchild"},
        parent_run_id=child.id,
        delegation={
            "request_key": "grandchild-one",
            "task": "Run the grandchild",
            "parameters": {},
            "context": {},
            "budget": {},
        },
    )
    assert grandchild.root_run_id == parent.id
    assert grandchild.depth == 2
    runtime.agents.transition(
        grandchild.id,
        expected={AgentRunStatus.QUEUED},
        status=AgentRunStatus.PLANNING,
    )
    runtime.agents.transition(
        grandchild.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.RUNNING,
    )
    with pytest.raises(ResourceConflictError, match="depth"):
        runtime.agents.create_run(
            session_id=session_id,
            agent_key="ai2apps.diagnostic-agent",
            input={"value": "too deep"},
            parent_run_id=grandchild.id,
            delegation={
                "request_key": "too-deep",
                "task": "This must be rejected",
                "parameters": {},
                "context": {},
                "budget": {},
            },
        )


@pytest.mark.asyncio
async def test_agent_delegate_tool_runs_child_and_returns_output(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    runtime.agents.ensure_definition(
        agent_key="test.delegate-parent",
        package_version="1.0.0",
        display_name="Delegate parent",
        executor_key="test:delegate-parent",
    )
    runtime.agents.ensure_definition(
        agent_key="test.delegate-child",
        package_version="1.0.0",
        display_name="Delegate child",
        executor_key="test:delegate-child",
    )

    def parent_executor(context):
        step = context.step("delegate:one")
        if step is None:
            return ToolCallAction(
                call_id="delegate:one",
                tool_name="agent.delegate",
                arguments={
                    "agent": "test.delegate-child",
                    "task": "Return a bounded result",
                    "request_key": "one",
                    "parameters": {},
                    "budget": {"max_steps": 2, "timeout_seconds": 30},
                },
            )
        return CompleteAction({"delegation_result": step.output})

    runtime.agent_runtime.bind_executor("test:delegate-parent", parent_executor)
    runtime.agent_runtime.bind_executor(
        "test:delegate-child", lambda context: CompleteAction({"child": context.run.id})
    )
    run, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="test.delegate-parent",
        input={},
    )
    await runtime.agent_runtime.start()
    try:
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
    finally:
        await runtime.agent_runtime.stop()

    children = runtime.agents.list_children(run.id)
    assert len(children) == 1
    assert children[0].status is AgentRunStatus.COMPLETED
    result = completed.output["delegation_result"]
    assert result["child_run_id"] == children[0].id
    assert result["output"] == {"child": children[0].id}


def test_parent_cancel_cascades_to_active_children(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    parent, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={},
    )
    runtime.agents.transition(
        parent.id,
        expected={AgentRunStatus.QUEUED},
        status=AgentRunStatus.PLANNING,
    )
    runtime.agents.transition(
        parent.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.RUNNING,
    )
    child, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={},
        parent_run_id=parent.id,
        delegation={
            "request_key": "cancel-child",
            "task": "Wait",
            "parameters": {},
            "context": {},
            "budget": {},
        },
    )

    runtime.agent_runtime.cancel(parent.id)

    assert runtime.agents.get_run(parent.id).status is AgentRunStatus.CANCELLED
    assert runtime.agents.get_run(child.id).status is AgentRunStatus.CANCELLED


def test_agent_invocation_schema_validates_parameters_and_snapshots_identity(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.agents.ensure_definition(
        agent_key="test.parameterized",
        package_version="2.3.4",
        display_name="Parameterized",
        executor_key="test:parameterized",
        manifest={
            "invocation_schema": {
                "type": "object",
                "properties": {"tone": {"type": "string", "enum": ["brief"]}},
                "required": ["tone"],
                "additionalProperties": False,
            }
        },
    )
    session_id = _session(runtime)

    with pytest.raises(ValueError, match="tone.*required"):
        runtime.agents.create_run(
            session_id=session_id,
            agent_key="test.parameterized",
            input={"prompt": "Hello", "parameters": {}},
        )

    run, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="test.parameterized",
        input={
            "prompt": "Hello",
            "parameters": {"tone": "brief"},
            "invocation": {"source": "mention", "package_version": "forged"},
        },
    )

    assert run.input["parameters"] == {"tone": "brief"}
    assert run.input["invocation"] == {
        "agent_definition_id": run.agent_definition_id,
        "agent_key": "test.parameterized",
        "package_version": "2.3.4",
        "source": "mention",
    }


def test_builtin_agent_metadata_refreshes_without_replacing_definition(tmp_path):
    runtime = _runtime(tmp_path)
    first = runtime.agents.ensure_definition(
        agent_key="test.refreshable-builtin",
        package_version="1.0.0",
        display_name="Old name",
        executor_key="test:refreshable",
        manifest={"discoverable": False},
    )
    second = runtime.agents.ensure_definition(
        agent_key="test.refreshable-builtin",
        package_version="1.1.0",
        display_name="New name",
        executor_key="test:refreshable",
        manifest={"discoverable": True, "aliases": ["fresh"]},
    )

    assert second.id == first.id
    assert second.package_version == "1.1.0"
    assert second.display_name == "New name"
    assert second.manifest["aliases"] == ["fresh"]


@pytest.mark.asyncio
async def test_diagnostic_agent_completes_asynchronously_with_replayable_status(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=_session(runtime),
            agent_key="ai2apps.diagnostic-agent",
            input={"message": "hello"},
        )
        runtime.agent_runtime.wake()

        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        status = runtime.agents.get_status_line(run.id)
        events = runtime.events.list_after(subject_id=run.id, limit=100)

        assert completed.output == {"echo": {"message": "hello"}}
        assert status.phase == "completed"
        assert status.text == "Completed"
        assert "agent.run.queued" in [event.type for event in events]
        assert "agent.status" in [event.type for event in events]
        assert "agent.run.completed" in [event.type for event in events]
        assert all(event.session_id == run.session_id for event in events)
    finally:
        await runtime.stop_background_tasks()


def test_waiting_and_paused_time_do_not_consume_run_deadline(tmp_path):
    runtime = _runtime(tmp_path)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.diagnostic-agent",
        input={"mode": "text"},
    )
    runtime.agents.claim_next()
    runtime.agents.transition(
        run.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.RUNNING,
    )
    interaction = runtime.agents.create_interaction(
        run.id,
        request_key="deadline-input",
        kind=InteractionKind.TEXT,
        prompt="Continue",
        response_schema={"type": "object"},
    )
    now = datetime.now(UTC)
    with runtime.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE agent_runs SET deadline_at=?, updated_at=? WHERE id=?",
            (
                format_utc(now + timedelta(seconds=10)),
                format_utc(now - timedelta(seconds=90)),
                run.id,
            ),
        )
    runtime.agents.respond_interaction(
        run.id,
        interaction.id,
        response={},
        response_id="deadline-response",
    )
    resumed = runtime.agents.get_run(run.id)
    assert resumed.deadline_at > now + timedelta(seconds=95)

    paused = runtime.agents.request_pause(run.id)
    with runtime.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE agent_runs SET updated_at=? WHERE id=?",
            (format_utc(now - timedelta(seconds=60)), paused.id),
        )
    resumed_again = runtime.agents.resume_interrupted(paused.id)
    assert resumed_again.deadline_at > resumed.deadline_at + timedelta(seconds=55)


@pytest.mark.asyncio
async def test_shutdown_freezes_queued_deadline_and_startup_recovers(tmp_path):
    runtime = _runtime(tmp_path)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.diagnostic-agent",
        input={"message": "survive restart"},
    )
    original_deadline = run.deadline_at
    await runtime.agent_runtime.stop()
    suspended = runtime.agents.get_run(run.id)
    assert suspended.error == {"code": "runtime_stopped"}
    with runtime.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE agent_runs SET updated_at=? WHERE id=?",
            (format_utc(datetime.now(UTC) - timedelta(seconds=120)), run.id),
        )

    recovery = runtime.agents.recover_interrupted()
    recovered = runtime.agents.get_run(run.id)
    assert recovery["recovered"] == 1
    assert recovered.error is None
    assert recovered.deadline_at > original_deadline + timedelta(seconds=115)


def test_failed_run_retry_is_fresh_bounded_and_auditable(tmp_path):
    runtime = _runtime(tmp_path)
    original, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.diagnostic-agent",
        input={"message": "retry me"},
    )
    runtime.agents.transition(
        original.id,
        expected={AgentRunStatus.QUEUED},
        status=AgentRunStatus.PLANNING,
    )
    runtime.agents.transition(
        original.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.FAILED,
        error={"code": "transient"},
    )

    retried, created = runtime.agents.retry_run(
        original.id, idempotency_key="retry-attempt-1"
    )
    replay, replay_created = runtime.agents.retry_run(
        original.id, idempotency_key="retry-attempt-1"
    )
    assert created is True
    assert replay_created is False
    assert replay.id == retried.id
    assert retried.status is AgentRunStatus.QUEUED
    assert retried.input["retry"] == {
        "attempt": 1,
        "retry_of_run_id": original.id,
        "root_attempt_run_id": original.id,
    }
    with pytest.raises(ResourceConflictError, match="failed or cancelled"):
        runtime.agents.retry_run(retried.id)
    current = retried
    for expected_attempt in (2, 3):
        runtime.agents.transition(
            current.id,
            expected={AgentRunStatus.QUEUED},
            status=AgentRunStatus.PLANNING,
        )
        runtime.agents.transition(
            current.id,
            expected={AgentRunStatus.PLANNING},
            status=AgentRunStatus.FAILED,
            error={"code": "again"},
        )
        current, _ = runtime.agents.retry_run(current.id)
        assert current.input["retry"]["attempt"] == expected_attempt
    runtime.agents.transition(
        current.id,
        expected={AgentRunStatus.QUEUED},
        status=AgentRunStatus.PLANNING,
    )
    runtime.agents.transition(
        current.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.FAILED,
        error={"code": "limit"},
    )
    with pytest.raises(ResourceConflictError, match="retry limit"):
        runtime.agents.retry_run(current.id)


def test_general_agent_is_serialized_for_single_user_runtime(tmp_path):
    runtime = _runtime(tmp_path)
    definition = runtime.agents.get_definition("ai2apps.general-agent")
    assert definition.concurrency_group == "model:foreground"
    assert definition.concurrency_limit == 1


def test_per_run_budget_is_bounded_by_agent_definition(tmp_path):
    runtime = _runtime(tmp_path)
    before = datetime.now(UTC)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.general-agent",
        input={"content": "bounded"},
        budget={
            "max_steps": 2,
            "timeout_seconds": 30,
            "max_model_tokens": 500,
        },
    )
    assert run.input["run_budget"] == {
        "max_steps": 2,
        "timeout_seconds": 30,
        "max_model_tokens": 500,
    }
    assert runtime.agent_runtime._step_budget(
        run, runtime.agents.get_definition(run.agent_definition_id)
    ) == 2
    assert before + timedelta(seconds=29) < run.deadline_at
    assert run.deadline_at <= before + timedelta(seconds=31)


@pytest.mark.asyncio
async def test_agent_api_exposes_budget_usage_and_retry_endpoint(tmp_path):
    runtime = _runtime(tmp_path)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    session_id = _session(runtime)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            f"/v1/platform/sessions/{session_id}/agent-runs",
            json={
                "agent": "ai2apps.diagnostic-agent",
                "input": {"message": "retry API"},
                "budget": {"max_steps": 2, "timeout_seconds": 20},
            },
        )
        assert created.status_code == 202
        payload = created.json()
        assert payload["budget"]["max_steps"] == 2
        assert payload["budget"]["timeout_seconds"] == 20
        assert payload["usage"] == {"steps": 0, "model_tokens": 0}
        run_id = payload["id"]
        runtime.agents.transition(
            run_id,
            expected={AgentRunStatus.QUEUED},
            status=AgentRunStatus.PLANNING,
        )
        runtime.agents.transition(
            run_id,
            expected={AgentRunStatus.PLANNING},
            status=AgentRunStatus.FAILED,
            error={"code": "test_failure"},
        )
        retried = await client.post(
            f"/v1/platform/agent-runs/{run_id}/retry",
            json={"idempotency_key": "api-retry-1"},
        )
        assert retried.status_code == 202
        assert retried.json()["input"]["retry"]["retry_of_run_id"] == run_id


@pytest.mark.asyncio
async def test_waiting_interaction_releases_serial_resource_slot(tmp_path):
    runtime = _runtime(tmp_path)
    observed = []

    async def executor(context):
        if context.run.input.get("wait"):
            interaction = context.interaction("choice")
            if interaction is None:
                return InteractionAction(
                    request_key="choice",
                    kind=InteractionKind.MENU,
                    prompt="Choose",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "choice": {"type": "string", "enum": ["yes", "no"]}
                        },
                        "required": ["choice"],
                    },
                    ui_hints={"control": "menu"},
                )
            return CompleteAction({"choice": interaction.response["choice"]})
        observed.append(context.run.id)
        return CompleteAction({"second": True})

    runtime.agents.ensure_definition(
        agent_key="test.serial-agent",
        package_version="1",
        display_name="Serial Agent",
        executor_key="test:serial",
        concurrency_group="hardware:exclusive-test",
        concurrency_limit=1,
    )
    runtime.agent_runtime.bind_executor("test:serial", executor)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        first, _ = runtime.agents.create_run(
            session_id=_session(runtime, "first"),
            agent_key="test.serial-agent",
            input={"wait": True},
        )
        second, _ = runtime.agents.create_run(
            session_id=_session(runtime, "second"),
            agent_key="test.serial-agent",
            input={"wait": False},
        )
        runtime.agent_runtime.wake()

        waiting = await _wait_status(runtime, first.id, AgentRunStatus.WAITING_INPUT)
        completed_second = await _wait_status(
            runtime, second.id, AgentRunStatus.COMPLETED
        )
        interaction = runtime.agents.list_interactions(first.id)[0]

        assert waiting.status is AgentRunStatus.WAITING_INPUT
        assert completed_second.output == {"second": True}
        assert observed == [second.id]
        runtime.agents.respond_interaction(
            first.id,
            interaction.id,
            response={"choice": "yes"},
            response_id="answer-1",
        )
        runtime.agent_runtime.wake()
        completed_first = await _wait_status(
            runtime, first.id, AgentRunStatus.COMPLETED
        )
        assert completed_first.output == {"choice": "yes"}
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_shared_resource_group_serializes_and_unbounded_agent_runs_parallel(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    active = 0
    max_active = 0

    async def measured(context):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.04)
        active -= 1
        return CompleteAction({"run": context.run.id})

    for agent_key, executor_key in (
        ("test.hw-a", "test:hw-a"),
        ("test.hw-b", "test:hw-b"),
    ):
        runtime.agents.ensure_definition(
            agent_key=agent_key,
            package_version="1",
            display_name=agent_key,
            executor_key=executor_key,
            concurrency_group="hardware:gpu-test",
            concurrency_limit=1,
        )
        runtime.agent_runtime.bind_executor(executor_key, measured)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runs = [
            runtime.agents.create_run(
                session_id=_session(runtime, key), agent_key=key, input={}
            )[0]
            for key in ("test.hw-a", "test.hw-b")
        ]
        runtime.agent_runtime.wake()
        for run in runs:
            await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        assert max_active == 1

        max_active = 0
        runtime.agents.ensure_definition(
            agent_key="test.parallel",
            package_version="1",
            display_name="Parallel",
            executor_key="test:parallel",
        )
        runtime.agent_runtime.bind_executor("test:parallel", measured)
        parallel = [
            runtime.agents.create_run(
                session_id=_session(runtime, f"parallel-{index}"),
                agent_key="test.parallel",
                input={},
            )[0]
            for index in range(2)
        ]
        runtime.agent_runtime.wake()
        for run in parallel:
            await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        assert max_active == 2
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_tool_capability_creates_approval_before_side_effect(tmp_path):
    runtime = _runtime(tmp_path)
    calls = []
    service = runtime.services.ensure_service(
        service_key="test.secure-service",
        package_id="test.secure-service",
        package_version="1",
        display_name="Secure Service",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
    )
    instance = runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="test:secure-provider",
        status=ServiceInstanceStatus.RUNNING,
    )
    runtime.services.ensure_tool(
        service_id=service.id,
        qualified_name="secure.mutate",
        display_name="Secure Mutate",
        description="Approval test",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        effects=("write",),
        required_capabilities=("secure.write",),
    )

    async def secure(arguments, context):
        calls.append(arguments)
        return {"ok": True}

    runtime.service_registry.bind_tool(
        "secure.mutate", provider_key=instance.provider_key, handler=secure
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=_session(runtime),
            agent_key="ai2apps.diagnostic-agent",
            input={
                "mode": "tool",
                "tool_name": "secure.mutate",
                "arguments": {"value": 7},
            },
        )
        runtime.agent_runtime.wake()
        await _wait_status(runtime, run.id, AgentRunStatus.WAITING_CAPABILITY)
        interaction = runtime.agents.list_interactions(run.id)[0]

        assert calls == []
        assert interaction.kind is InteractionKind.APPROVAL
        assert interaction.request["effects"] == ["write"]
        assert interaction.ui_hints["default_scope"] == "once"
        assert interaction.ui_hints["operation_class"] == "write"
        assert interaction.ui_hints["risk_level"] == "medium"
        assert interaction.request["action_preview"]["summary"] == "secure.mutate"
        runtime.agents.respond_interaction(
            run.id,
            interaction.id,
            response={"decision": "approve"},
            response_id="approve-1",
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)

        assert calls == [{"value": 7}]
        assert completed.output == {"tool_output": {"ok": True}}
        assert runtime.agents.get_run(run.id).granted_capabilities == ("secure.write",)
        leases = runtime.capabilities.list_leases(include_inactive=True)
        once = next(item for item in leases if item.tool_pattern == "secure.mutate")
        assert once.evidence["requested_scope"] == "once"
        assert once.revoke_reason == "consumed"
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_model_action_uses_bound_model_runtime_and_persists_step(tmp_path):
    runtime = _runtime(tmp_path)
    requests = []

    async def model_provider(request):
        requests.append(request)
        return {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}

    runtime.agent_runtime.bind_model_provider(model_provider)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=_session(runtime),
            agent_key="ai2apps.diagnostic-agent",
            input={
                "mode": "model",
                "request": {
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            },
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        steps = runtime.agents.list_steps(run.id)

        assert requests[0]["model"] == "test-model"
        assert steps[0].kind == "model"
        assert steps[0].status is RunStepStatus.COMPLETED
        assert (
            completed.output["model_output"]["choices"][0]["message"]["content"]
            == "hello"
        )
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_cancel_stops_running_executor_and_is_terminal(tmp_path):
    runtime = _runtime(tmp_path)
    cancelled = asyncio.Event()
    started = asyncio.Event()

    async def slow(context):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return CompleteAction({})

    runtime.agents.ensure_definition(
        agent_key="test.slow",
        package_version="1",
        display_name="Slow",
        executor_key="test:slow",
    )
    runtime.agent_runtime.bind_executor("test:slow", slow)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=_session(runtime), agent_key="test.slow", input={}
        )
        runtime.agent_runtime.wake()
        await _wait_status(runtime, run.id, AgentRunStatus.RUNNING)
        await asyncio.wait_for(started.wait(), timeout=1)
        runtime.agent_runtime.cancel(run.id)

        final = await _wait_status(runtime, run.id, AgentRunStatus.CANCELLED)
        await asyncio.wait_for(cancelled.wait(), timeout=1)
        assert final.finished_at is not None
        assert runtime.agents.get_status_line(run.id).phase == "cancelled"
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_pause_stops_running_executor_and_resume_requeues_it(tmp_path):
    runtime = _runtime(tmp_path)
    stopped = asyncio.Event()
    started = asyncio.Event()

    async def slow(context):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
        return CompleteAction({})

    runtime.agents.ensure_definition(
        agent_key="test.pausable",
        package_version="1",
        display_name="Pausable",
        executor_key="test:pausable",
    )
    runtime.agent_runtime.bind_executor("test:pausable", slow)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=_session(runtime), agent_key="test.pausable", input={}
        )
        runtime.agent_runtime.wake()
        await asyncio.wait_for(started.wait(), timeout=1)

        paused = runtime.agent_runtime.pause(run.id)
        await asyncio.wait_for(stopped.wait(), timeout=1)
        assert paused.status is AgentRunStatus.INTERRUPTED
        assert paused.error == {"code": "user_paused"}

        async def finish(context):
            return CompleteAction({"resumed": True})

        runtime.agent_runtime.bind_executor("test:pausable", finish)
        resumed = runtime.agents.resume_interrupted(run.id)
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)

        assert resumed.status is AgentRunStatus.QUEUED
        assert completed.output == {"resumed": True}
    finally:
        await runtime.stop_background_tasks()


def test_uncertain_tool_recovery_requires_explicit_resolution(tmp_path):
    runtime = _runtime(tmp_path)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.diagnostic-agent",
        input={"mode": "tool"},
    )
    claimed = runtime.agents.claim_next()
    assert claimed.id == run.id
    runtime.agents.transition(
        run.id,
        expected={AgentRunStatus.PLANNING},
        status=AgentRunStatus.RUNNING,
    )
    step, _ = runtime.agents.create_step(
        run.id,
        action_key="diagnostic-tool",
        kind="tool",
        input={"value": "agent"},
        tool_name="system.echo",
    )

    recovery = runtime.agents.recover_interrupted()

    assert recovery == {"recovered": 0, "interrupted": 1, "failed": 0}
    assert runtime.agents.get_run(run.id).status is AgentRunStatus.INTERRUPTED
    assert runtime.agents.list_steps(run.id)[0].status is RunStepStatus.UNCERTAIN
    with pytest.raises(ResourceConflictError, match="require"):
        runtime.agents.resume_interrupted(run.id)
    resumed = runtime.agents.resume_interrupted(run.id, uncertain_resolution="retry")
    assert resumed.status is AgentRunStatus.QUEUED
    assert runtime.agents.list_steps(run.id)[0].id == step.id


@pytest.mark.asyncio
async def test_agent_api_exposes_status_menu_response_and_event_stream_url(tmp_path):
    runtime = _runtime(tmp_path)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            catalog = await client.get("/v1/platform/agents")
            created = await client.post(
                f"/v1/platform/sessions/{_session(runtime)}/agent-runs",
                json={
                    "agent": "ai2apps.diagnostic-agent",
                    "input": {"mode": "menu"},
                    "idempotency_key": "api-menu-1",
                },
            )
            run_id = created.json()["id"]
            await _wait_status(runtime, run_id, AgentRunStatus.WAITING_INPUT)
            waiting = await client.get(f"/v1/platform/agent-runs/{run_id}")
            interaction = waiting.json()["interactions"][0]
            answered = await client.post(
                f"/v1/platform/agent-runs/{run_id}/interactions/{interaction['id']}/respond",
                json={"response": {"choice": "beta"}, "response_id": "menu-answer-1"},
            )
            replay = await client.post(
                f"/v1/platform/agent-runs/{run_id}/interactions/{interaction['id']}/respond",
                json={"response": {"choice": "beta"}, "response_id": "menu-answer-1"},
            )
            completed = await _wait_status(runtime, run_id, AgentRunStatus.COMPLETED)

        assert created.status_code == 202
        assert catalog.status_code == 200
        assert "ai2apps.diagnostic-agent" in {
            item["agent_key"] for item in catalog.json()["items"]
        }
        assert created.json()["agent_key"] == "ai2apps.diagnostic-agent"
        assert created.json()["agent_display_name"] == "Diagnostic Agent"
        assert created.json()["agent_package_version"] == "1.0.0"
        diagnostic = next(
            item
            for item in catalog.json()["items"]
            if item["agent_key"] == "ai2apps.diagnostic-agent"
        )
        general = next(
            item
            for item in catalog.json()["items"]
            if item["agent_key"] == "ai2apps.general-agent"
        )
        assert diagnostic["discoverable"] is False
        assert "general" in general["aliases"]
        assert general["invocation_schema"]["type"] == "object"
        assert waiting.json()["status_line"]["phase"] == "waiting_input"
        assert interaction["ui_hints"]["control"] == "menu"
        assert waiting.json()["event_stream_url"].endswith(f"/{run_id}/events")
        assert answered.status_code == 200
        assert replay.status_code == 200
        assert completed.output["response"] == {"choice": "beta"}
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_agent_manager_api_exposes_lifecycle_runs_and_provenance(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    first, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.diagnostic-agent",
        input={"value": "one"},
    )
    runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.general-agent",
        input={"prompt": "two"},
    )
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        management = await client.get(
            "/v1/platform/agents/ai2apps.diagnostic-agent/management"
        )
        filtered = await client.get(
            "/v1/platform/agent-runs",
            params={"agent": "ai2apps.diagnostic-agent", "limit": 20},
        )
        disabled = await client.post(
            "/v1/platform/agents/ai2apps.diagnostic-agent/disable"
        )
        enabled = await client.post(
            "/v1/platform/agents/ai2apps.diagnostic-agent/enable"
        )

    assert management.status_code == 200
    assert management.json()["definition"]["source"] == "builtin"
    assert (
        management.json()["definition"]["executor_key"]
        == "builtin:diagnostic-agent"
    )
    assert management.json()["run_counts"]["total"] == 1
    assert management.json()["packages"] == []
    assert management.json()["patches"] == []
    assert management.json()["effective_definition"] is None
    assert [item["id"] for item in filtered.json()["items"]] == [first.id]
    assert disabled.json()["status"] == "disabled"
    assert enabled.json()["status"] == "enabled"


@pytest.mark.asyncio
async def test_agent_api_pauses_and_resumes_queued_run(tmp_path):
    runtime = _runtime(tmp_path)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            f"/v1/platform/sessions/{_session(runtime)}/agent-runs",
            json={"agent": "ai2apps.diagnostic-agent", "input": {}},
        )
        run_id = created.json()["id"]
        paused = await client.post(f"/v1/platform/agent-runs/{run_id}/pause")
        resumed = await client.post(
            f"/v1/platform/agent-runs/{run_id}/resume",
            json={"uncertain_resolution": None},
        )

    assert paused.status_code == 200
    assert paused.json()["status"] == "interrupted"
    assert paused.json()["error"] == {"code": "user_paused"}
    assert paused.json()["status_line"]["text"] == "Paused"
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "queued"
    events = runtime.events.list_after(subject_id=run_id, limit=20)
    assert "agent.run.paused" in [event.type for event in events]


@pytest.mark.asyncio
async def test_unanswered_interaction_expires_fail_closed(tmp_path):
    runtime = _runtime(tmp_path)

    async def executor(context):
        return InteractionAction(
            request_key="short-lived-choice",
            kind=InteractionKind.MENU,
            prompt="Choose before the deadline",
            response_schema={
                "type": "object",
                "properties": {"choice": {"type": "string"}},
                "required": ["choice"],
            },
            timeout_seconds=1,
        )

    runtime.agents.ensure_definition(
        agent_key="test.expiring-interaction",
        package_version="1",
        display_name="Expiring interaction",
        executor_key="test:expiring-interaction",
    )
    runtime.agent_runtime.bind_executor("test:expiring-interaction", executor)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=_session(runtime),
            agent_key="test.expiring-interaction",
            input={},
        )
        runtime.agent_runtime.wake()
        await _wait_status(runtime, run.id, AgentRunStatus.WAITING_INPUT)
        failed = await _wait_status(
            runtime,
            run.id,
            AgentRunStatus.FAILED,
            timeout=2.5,
        )

        interaction = runtime.agents.list_interactions(run.id)[0]
        status = runtime.agents.get_status_line(run.id)
        assert failed.error["code"] == "interaction_expired"
        assert interaction.status.value == "expired"
        assert status.phase == "failed"
    finally:
        await runtime.stop_background_tasks()


def _user_message(runtime, session_id, text="Use the available tool"):
    return (
        MessageRepository(runtime.database, runtime.events)
        .append(
            session_id=session_id,
            role=MessageRole.USER,
            parts=(MessagePartInput(kind="text", content={"text": text}),),
            idempotency_key=f"user:{session_id}:{text}",
        )
        .value
    )


@pytest.mark.asyncio
async def test_general_agent_persists_final_model_reply_in_session(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    user = _user_message(runtime, session_id, "Hello Agent")
    requests = []

    async def model_provider(request):
        requests.append(request)
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello user"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 9},
            "ai2apps_cloud": [
                {
                    "phase": "completed",
                    "requestId": "req-agent-test",
                    "charged": "2",
                    "balance": "998",
                }
            ],
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=session_id,
            agent_key="ai2apps.general-agent",
            input={"model": "test-model", "message_id": user.message.id},
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        messages = MessageRepository(runtime.database, runtime.events).list_for_session(
            session_id
        )

        assert requests[0]["messages"][-1] == {
            "role": "user",
            "content": "Hello Agent",
        }
        assert requests[0]["ai2apps_idempotency_key"] == (
            f"agent-{run.id}-model-1"
        )
        assert any(
            tool["function"]["name"].startswith("system__echo_")
            for tool in requests[0]["tools"]
        )
        assert len(messages) == 2
        assert messages[-1].message.role is MessageRole.ASSISTANT
        assert messages[-1].parts[0].content == {"text": "Hello user"}
        assert messages[-1].message.metadata["agent_run_id"] == run.id
        assert messages[-1].message.metadata["ai2apps_cloud"][0]["charged"] == "2"
        assert completed.output["message_id"] == messages[-1].message.id
        assert completed.output["usage"] == {"total_tokens": 9}
        assert completed.output["ai2apps_cloud"][0]["requestId"] == "req-agent-test"
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_general_agent_runs_model_tool_model_loop_durably(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    user = _user_message(runtime, session_id)
    requests = []

    async def model_provider(request):
        requests.append(request)
        if len(requests) == 1:
            echo_alias = next(
                item["function"]["name"]
                for item in request["tools"]
                if item["function"]["name"].startswith("system__echo_")
            )
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_echo_1",
                                    "type": "function",
                                    "function": {
                                        "name": echo_alias,
                                        "arguments": '{"value":"durable"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Tool returned durable",
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=session_id,
            agent_key="ai2apps.general-agent",
            input={"model": "test-model", "message_id": user.message.id},
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        steps = runtime.agents.list_steps(run.id)
        invocations = runtime.services.list_invocations(trace_id=run.id)

        assert [step.kind for step in steps] == ["model", "tool", "model"]
        assert steps[1].tool_name == "system.echo"
        assert steps[1].output == {"value": "durable"}
        assert len(invocations) == 1
        assert invocations[0].qualified_name == "system.echo"
        assert invocations[0].output == {"value": "durable"}
        assert requests[1]["messages"][-2]["tool_calls"][0]["id"] == "call_echo_1"
        assert requests[1]["messages"][-1] == {
            "role": "tool",
            "tool_call_id": "call_echo_1",
            "content": '{"value": "durable"}',
        }
        assert completed.output["content"] == "Tool returned durable"
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_general_agent_retries_non_effectful_tool_after_runtime_restart(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    user = _user_message(runtime, session_id, "Survive a restart")
    tool_started = asyncio.Event()

    async def interrupted_echo(arguments, _context):
        tool_started.set()
        await asyncio.Event().wait()
        return {"value": arguments["value"]}

    runtime.service_registry.bind_tool(
        "system.echo",
        provider_key="builtin:diagnostics",
        handler=interrupted_echo,
    )
    model_calls = 0

    async def model_provider(request):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            alias = next(
                item["function"]["name"]
                for item in request["tools"]
                if item["function"]["name"].startswith("system__echo_")
            )
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "restart-echo",
                                    "type": "function",
                                    "function": {
                                        "name": alias,
                                        "arguments": '{"value":"resumed"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Recovered"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    run, _ = runtime.agents.create_run(
        session_id=session_id,
        agent_key="ai2apps.general-agent",
        input={"model": "test-model", "message_id": user.message.id},
    )
    runtime.agent_runtime.wake()
    await asyncio.wait_for(tool_started.wait(), timeout=2)
    await runtime.stop_background_tasks()

    interrupted = runtime.agents.get_run(run.id)
    first_invocation = runtime.services.list_invocations(trace_id=run.id)[0]
    assert interrupted.status is AgentRunStatus.QUEUED
    assert first_invocation.status.value == "cancelled"
    assert runtime.agents.list_steps(run.id)[1].action_key.startswith(
        "tool:1:0:"
    )
    assert ":retry:" in runtime.agents.list_steps(run.id)[1].action_key

    async def resumed_echo(arguments, _context):
        return {"value": arguments["value"]}

    runtime.service_registry.bind_tool(
        "system.echo", provider_key="builtin:diagnostics", handler=resumed_echo
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)
        invocations = runtime.services.list_invocations(trace_id=run.id)

        assert completed.output["content"] == "Recovered"
        assert [item.status.value for item in invocations] == [
            "completed",
            "cancelled",
        ]
        assert model_calls == 2
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_general_agent_stops_repeated_identical_tool_loop(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    user = _user_message(runtime, session_id, "Do not loop")
    calls = 0

    async def looping_model(request):
        nonlocal calls
        calls += 1
        echo_alias = next(
            item["function"]["name"]
            for item in request["tools"]
            if item["function"]["name"].startswith("system__echo_")
        )
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"repeat-{calls}",
                                "type": "function",
                                "function": {
                                    "name": echo_alias,
                                    "arguments": '{"value":"same"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(looping_model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=session_id,
            agent_key="ai2apps.general-agent",
            input={"model": "test-model", "message_id": user.message.id},
        )
        runtime.agent_runtime.wake()
        failed = await _wait_status(
            runtime, run.id, AgentRunStatus.FAILED, timeout=10.0
        )
        tool_steps = [
            step for step in runtime.agents.list_steps(run.id) if step.kind == "tool"
        ]

        assert failed.error["code"] == "repeated_tool_call"
        assert len(tool_steps) == 3
        assert calls == 4
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_general_agent_waits_for_capability_before_model_selected_effect(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    effects = []
    service = runtime.services.ensure_service(
        service_key="test.general-secure-service",
        package_id="test.general-secure-service",
        package_version="1",
        display_name="General secure service",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
    )
    instance = runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="test:general-secure-provider",
        status=ServiceInstanceStatus.RUNNING,
    )
    runtime.services.ensure_tool(
        service_id=service.id,
        qualified_name="secure.write_value",
        display_name="Write value",
        description="Write a value after approval",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        effects=("write",),
        required_capabilities=("secure.write",),
    )

    async def write_value(arguments, context):
        effects.append(arguments["value"])
        return {"written": arguments["value"]}

    runtime.service_registry.bind_tool(
        "secure.write_value",
        provider_key=instance.provider_key,
        handler=write_value,
    )
    model_calls = 0

    async def model_provider(request):
        nonlocal model_calls
        model_calls += 1
        if model_calls == 1:
            secure_alias = next(
                item["function"]["name"]
                for item in request["tools"]
                if item["function"]["name"].startswith("secure__write_value_")
            )
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "secure-call",
                                    "type": "function",
                                    "function": {
                                        "name": secure_alias,
                                        "arguments": '{"value":7}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Written"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    session_id = _session(runtime)
    user = _user_message(runtime, session_id, "Write seven")
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=session_id,
            agent_key="ai2apps.general-agent",
            input={"model": "test-model", "message_id": user.message.id},
        )
        runtime.agent_runtime.wake()
        await _wait_status(runtime, run.id, AgentRunStatus.WAITING_CAPABILITY)
        interaction = runtime.agents.list_interactions(run.id)[0]

        assert effects == []
        assert interaction.request["capabilities"] == ["secure.write"]
        runtime.agents.respond_interaction(
            run.id,
            interaction.id,
            response={"decision": "approve"},
            response_id="approve-general-secure-call",
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)

        assert effects == [7]
        assert completed.output["content"] == "Written"
        assert model_calls == 2
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_agent_api_defaults_to_general_agent_and_accepts_direct_prompt(tmp_path):
    runtime = _runtime(tmp_path)

    async def model_provider(request):
        assert request["messages"][-1] == {"role": "user", "content": "Direct prompt"}
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Direct reply"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    session_id = _session(runtime)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post(
                f"/v1/platform/sessions/{session_id}/agent-runs",
                json={"input": {"model": "test-model", "prompt": "Direct prompt"}},
            )
        completed = await _wait_status(
            runtime, created.json()["id"], AgentRunStatus.COMPLETED
        )
        messages = MessageRepository(runtime.database, runtime.events).list_for_session(
            session_id
        )

        assert created.status_code == 202
        assert completed.output["content"] == "Direct reply"
        assert [item.message.role for item in messages] == [
            MessageRole.USER,
            MessageRole.ASSISTANT,
        ]
        assert messages[0].message.metadata["agent_input"] is True
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_general_agent_can_complete_at_exact_step_budget(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.agents.ensure_definition(
        agent_key="test.one-step-general",
        package_version="1",
        display_name="One step general Agent",
        executor_key="builtin:general-agent",
        max_steps=1,
        manifest={"allowed_tools": []},
    )

    async def model_provider(request):
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "One step"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    session_id = _session(runtime)
    user = _user_message(runtime, session_id, "Finish in one")
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=session_id,
            agent_key="test.one-step-general",
            input={"model": "test-model", "message_id": user.message.id},
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)

        assert completed.current_step == 1
        assert completed.output["content"] == "One step"
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_general_agent_applies_context_and_token_budgets_before_effects(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    runtime.agents.ensure_definition(
        agent_key="test.budgeted-general",
        package_version="1",
        display_name="Budgeted general Agent",
        executor_key="builtin:general-agent",
        manifest={
            "allowed_tools": ["system.echo"],
            "context_message_limit": 2,
            "max_total_model_tokens": 1,
        },
    )
    session_id = _session(runtime)
    _user_message(runtime, session_id, "Old one")
    _user_message(runtime, session_id, "Old two")
    current = _user_message(runtime, session_id, "Current")

    async def model_provider(request):
        assert request["messages"][-2:] == [
            {"role": "user", "content": "Old two"},
            {"role": "user", "content": "Current"},
        ]
        assert (
            "1 earlier Session messages were omitted"
            in request["messages"][0]["content"]
        )
        echo_alias = next(
            item["function"]["name"]
            for item in request["tools"]
            if item["function"]["name"].startswith("system__echo_")
        )
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "over-budget-effect",
                                "type": "function",
                                "function": {
                                    "name": echo_alias,
                                    "arguments": '{"value":"must-not-run"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"total_tokens": 1},
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=session_id,
            agent_key="test.budgeted-general",
            input={"model": "test-model", "message_id": current.message.id},
        )
        runtime.agent_runtime.wake()
        failed = await _wait_status(runtime, run.id, AgentRunStatus.FAILED)

        assert failed.error["code"] == "model_token_budget_exceeded"
        assert [step.kind for step in runtime.agents.list_steps(run.id)] == ["model"]
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_general_agent_preserves_rich_input_and_per_run_instructions(tmp_path):
    runtime = _runtime(tmp_path)
    session_id = _session(runtime)
    rich_content = [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
        {"type": "text", "text": "Describe this"},
    ]

    async def model_provider(request):
        assert request["messages"][0] == {
            "role": "system",
            "content": "Be concise",
        }
        assert request["messages"][-1] == {
            "role": "user",
            "content": rich_content,
        }
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "An image"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model_provider)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=session_id,
            agent_key="ai2apps.general-agent",
            input={
                "model": "test-model",
                "content": rich_content,
                "instructions": "Be concise",
            },
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED)

        assert completed.output["content"] == "An image"
    finally:
        await runtime.stop_background_tasks()
