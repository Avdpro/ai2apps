"""Agent model-stream reconstruction and durable progress tests."""

from __future__ import annotations

import asyncio

import pytest

from ai2apps.agents import AgentRunStatus
from ai2apps.agents.model_stream import ChatCompletionStreamAccumulator
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.identity import IdentityRepository, MemberRole, OrganizationType
from ai2apps.platform_runtime import PlatformRuntime


def test_chat_completion_stream_accumulates_content_reasoning_tools_and_usage():
    stream = ChatCompletionStreamAccumulator()
    stream.add(
        {
            "id": "chat-1",
            "created": 12,
            "model": "agent-model",
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "reasoning_content": "check ",
                    "tool_calls": [{
                        "index": 0, "id": "call_1", "type": "function",
                        "function": {"name": "web.", "arguments": '{"query":"ML'},
                    }],
                },
            }],
        }
    )
    stream.add(
        {
            "id": "chat-1",
            "model": "agent-model",
            "choices": [{
                "index": 0,
                "delta": {
                    "reasoning_content": "sources",
                    "tool_calls": [{
                        "index": 0,
                        "function": {"name": "search", "arguments": 'X"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
    )
    stream.add(
        {
            "choices": [],
            "usage": {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24},
        }
    )

    result = stream.result()
    message = result["choices"][0]["message"]
    assert result["object"] == "chat.completion"
    assert message["reasoning_content"] == "check sources"
    assert message["tool_calls"] == [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "web.search", "arguments": '{"query":"MLX"}'},
    }]
    assert result["choices"][0]["finish_reason"] == "tool_calls"
    assert result["usage"]["completion_tokens"] == 4
    assert stream.has_tool_calls is True


def test_chat_completion_stream_preserves_cloud_settlement_and_rejects_failure():
    completed = ChatCompletionStreamAccumulator()
    completed.add(
        {
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": "done",
                    "ai2apps_cloud": {
                        "phase": "completed",
                        "requestId": "req-agent",
                        "charged": "4",
                        "balance": "996",
                    },
                },
                "finish_reason": "stop",
            }],
        }
    )
    result = completed.result()
    assert result["ai2apps_cloud"][0]["requestId"] == "req-agent"
    assert result["ai2apps_cloud"][0]["charged"] == "4"

    failed = ChatCompletionStreamAccumulator()
    failed.add(
        {
            "choices": [{
                "index": 0,
                "delta": {
                    "ai2apps_cloud": {
                        "phase": "failed",
                        "requestId": "req-failed",
                        "error": {
                            "code": "INSUFFICIENT_POINTS",
                            "message": "Not enough points",
                        },
                    }
                },
                "finish_reason": "stop",
            }],
        }
    )
    with pytest.raises(ValueError, match="INSUFFICIENT_POINTS"):
        failed.result()


@pytest.mark.asyncio
async def test_progress_aware_model_provider_updates_durable_agent_status(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.agent_runtime is not None
    assert runtime.agents is not None
    progress_visible = asyncio.Event()
    release = asyncio.Event()

    async def provider(request, report_progress):
        assert request["model"] == "progress-model"
        await report_progress(
            {
                "phase": "model_streaming",
                "text": "Receiving the model plan",
                "presentation": "indeterminate",
                "content": {
                    "detail": "Streaming model output · 128 characters",
                    "output_characters": 128,
                },
            }
        )
        progress_visible.set()
        await release.wait()
        return {"choices": [{"message": {"role": "assistant", "content": "finished"}}]}

    runtime.agent_runtime.bind_model_provider(provider)
    thread, _ = ChatRepository(runtime.database, runtime.events).create_thread(
        title="Model progress"
    )
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=thread.session.id,
            agent_key="ai2apps.diagnostic-agent",
            input={
                "mode": "model",
                "request": {
                    "model": "progress-model",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            },
        )
        runtime.agent_runtime.wake()
        await asyncio.wait_for(progress_visible.wait(), timeout=2)

        status = runtime.agents.get_status_line(run.id)
        assert status.phase == "model_streaming"
        assert status.text == "Receiving the model plan"
        assert status.presentation == "indeterminate"
        assert status.content["output_characters"] == 128
        assert status.content["model"] == "progress-model"
        assert status.content["step"] == 1
        assert "agent.status" in [
            event.type for event in runtime.events.list_after(subject_id=run.id, limit=100)
        ]

        release.set()
        await runtime.agent_runtime.wait_for_terminal(run.id, timeout=2)
        assert runtime.agents.get_run(run.id).status is AgentRunStatus.COMPLETED
    finally:
        release.set()
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_agent_model_provider_receives_server_derived_identity_and_cache_context(
    tmp_path,
):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    identities = IdentityRepository(runtime.database)
    identities.bind_installation(
        installation_id="nas-1",
        cloud_device_id="device-1",
        organization_id="family-1",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="core-user",
        billing_account_id="core-billing",
        access_epoch=1,
    )
    identities.upsert_membership(
        cloud_user_id="member-alice",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=7,
    )
    principal = identities.principal_for("member-alice")
    thread, _ = ChatRepository(
        runtime.database, runtime.events, principal=principal
    ).create_thread(title="Alice model context")
    received = {}

    async def provider(request, report_progress, context):
        received["request"] = request
        received["context"] = context
        return {
            "choices": [{"message": {"role": "assistant", "content": "finished"}}]
        }

    runtime.agent_runtime.bind_model_provider(provider)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run, _ = runtime.agents.create_run(
            session_id=thread.session.id,
            agent_key="ai2apps.diagnostic-agent",
            input={
                "mode": "model",
                "request": {
                    "model": "context-model",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            },
        )
        runtime.agent_runtime.wake()
        await runtime.agent_runtime.wait_for_terminal(run.id, timeout=2)
    finally:
        await runtime.stop_background_tasks()

    context = received["context"]
    assert context.actor_user_id == "member-alice"
    assert context.billing_account_id == "core-billing"
    assert context.session_id == thread.session.id
    assert context.cache_namespace.startswith("a2c-")
    assert "actor_user_id" not in received["request"]
    event = runtime.events.latest_for_subject(
        run.id, event_type="agent.model.invocation.started"
    )
    assert event is not None
    assert event.payload["cache_namespace"] == context.cache_namespace
