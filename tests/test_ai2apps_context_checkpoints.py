"""Checkpoint replay, fail-closed validation and real durable executor integration."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from test_ai2apps_agents import _runtime, _session, _wait_status

from ai2apps.agents import AgentRunStatus, RunStepStatus
from ai2apps.agents.compaction import (
    CHECKPOINT_KEY,
    CHECKPOINT_READER,
    INSTRUCTION,
    PREFIX,
    encode,
    prepare_checkpoint,
)
from ai2apps.services import ToolGatewayError


def response(content, finish="stop"):
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish,
            }
        ]
    }


def summary():
    return {
        "facts": ["Read the first records"],
        "decisions": [],
        "constraints": ["Preserve PIN-42"],
        "pending": ["Finish the remaining records"],
        "uncertainties": [],
        "references": [],
    }


def request(rounds=6):
    messages = [
        {"role": "system", "content": "Never change protected.txt"},
        {"role": "user", "content": "Preserve PIN-42"},
    ]
    for n in range(rounds):
        messages += [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call-{n}",
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "arguments": json.dumps({"value": n}),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": f"call-{n}",
                "content": str(n) + "x" * 2100,
            },
        ]
    return {"model": "test", "messages": messages}


def prepare(value, steps=(), reader="read_checkpoint"):
    return prepare_checkpoint(
        value,
        base_count=2,
        steps=steps,
        max_bytes=12000,
        reader_alias=reader,
        run_id="run",
    )


def checkpoint(action, output=None, status=RunStepStatus.COMPLETED):
    return SimpleNamespace(
        id="checkpoint-1",
        sequence=20,
        kind="model",
        action_key=action.call_id,
        input=action.request,
        output=output or response(encode(summary())),
        status=status,
    )


def test_checkpoint_replay_preserves_anchors_tail_and_raw_source():
    original = request()
    _, _, action = prepare(original)
    assert action and action.call_id.startswith(PREFIX)
    assert "tools" not in action.request
    assert len(encode(action.request).encode()) <= 12000 * 0.85
    step = checkpoint(action)
    projected, audit, next_action = prepare(original, [step])
    assert not next_action
    assert projected["messages"][:2] == original["messages"][:2]
    assert projected["messages"][-4:] == original["messages"][-4:]
    assert audit["checkpoint_step_id"] == step.id
    assert audit["projected_base_count"] == 2
    assert len(encode(projected)) < len(encode(original))
    assert len(original["messages"]) == 14
    assert prepare(original, [step]) == (projected, audit, next_action)
    assert prepare(original, [step], reader=None) == (original, {}, None)
    changed = request()
    changed["messages"][1]["content"] = "A changed task"
    _, stale, _ = prepare(changed, [step])
    assert stale["checkpoint_step_id"] is None
    changed = request()
    changed["messages"][3]["content"] = "changed source"
    _, stale, _ = prepare(changed, [step])
    assert stale["checkpoint_step_id"] is None


@pytest.mark.parametrize(
    "output",
    [
        response("not JSON"),
        response(encode(summary()), "length"),
        response(encode({k: [] for k in summary()})),
    ],
)
def test_invalid_summary_does_not_replace_source_or_repeat_call(output):
    original = request()
    _, _, action = prepare(original)
    step = checkpoint(action, output=output)
    projected, audit, action = prepare(original, [step])
    assert projected == original
    assert audit["checkpoint_rejected_steps"] == [step.id]
    assert action is None


def test_unsettled_checkpoint_and_incomplete_tool_round_are_not_consumed():
    original = request()
    _, _, action = prepare(original)
    projected, audit, _ = prepare(
        original, [checkpoint(action, status=RunStepStatus.RUNNING)]
    )
    assert projected == original
    assert audit["checkpoint_step_id"] is None
    original["messages"].pop()
    projected, audit, action = prepare(original)
    assert action is None and projected == original
    assert audit["checkpoint_skipped"] == "unsupported_or_incomplete_context"
    multimodal = request()
    multimodal["messages"][1]["content"] = [
        {"type": "image_url", "image_url": {"url": "https://example.test/image.png"}}
    ]
    assert prepare(multimodal)[2] is None


def test_successive_checkpoint_uses_incremental_records_and_previous_memory():
    _, _, action = prepare(request())
    step = checkpoint(action)
    _, _, following = prepare(request(10), [step])
    assert following is not None
    source = json.loads(following.request["messages"][-1]["content"])
    assert source["previous_checkpoint_step_id"] == step.id
    assert source["previous_memory"] == summary()
    first = source["records"][0]["messages"][0]["tool_calls"][0]["id"]
    assert first == f"call-{action.request[CHECKPOINT_KEY]['covered_groups']}"
    assert (
        following.request[CHECKPOINT_KEY]["covered_groups"]
        > action.request[CHECKPOINT_KEY]["covered_groups"]
    )


@pytest.mark.asyncio
async def test_long_run_compacts_and_can_read_durable_checkpoint_source(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.agents.ensure_definition(
        agent_key="test.checkpoints",
        package_version="1",
        display_name="checkpoints",
        executor_key="builtin:general-agent",
        max_steps=30,
        manifest={
            "allowed_tools": ["system.echo", CHECKPOINT_READER],
            "max_context_bytes": 12000,
        },
    )
    runtime.service_registry.bind_tool(
        "system.echo",
        provider_key="builtin:diagnostics",
        handler=lambda args, ctx: {
            "value": {"index": args["value"], "data": "x" * 2100}
        },
    )
    normal_calls, summary_calls, saw_memory = 0, 0, False

    first_summary_started = asyncio.Event()

    async def model(value):
        nonlocal normal_calls, summary_calls, saw_memory
        assert (
            CHECKPOINT_KEY not in value
        )  # Host-only metadata is not a provider parameter.
        if value["messages"][0].get("content") == INSTRUCTION:
            summary_calls += 1
            if summary_calls == 1:
                first_summary_started.set()
                await asyncio.Event().wait()  # Simulate a stop during summarization.
            return response(encode(summary()))
        normal_calls += 1
        assert any(m.get("content") == "Preserve PIN-42" for m in value["messages"])
        saw_memory |= any(
            '"type":"context-checkpoint/v2"' in str(m.get("content"))
            for m in value["messages"]
        )
        # Every visible tool result still has a visible paired model call.
        ids = {c["id"] for m in value["messages"] for c in m.get("tool_calls", [])}
        assert all(
            m["tool_call_id"] in ids for m in value["messages"] if m["role"] == "tool"
        )
        if normal_calls == 7:
            return response("done")
        alias = next(
            t["function"]["name"]
            for t in value["tools"]
            if t["function"]["name"].startswith("system__echo")
        )
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call-{normal_calls}",
                                "type": "function",
                                "function": {
                                    "name": alias,
                                    "arguments": json.dumps(
                                        {"value": str(normal_calls)}
                                    ),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"total_tokens": 10},
        }

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="test.checkpoints",
        input={"model": "test", "prompt": "Preserve PIN-42"},
    )
    await runtime.agent_runtime.start()
    try:
        try:
            await asyncio.wait_for(first_summary_started.wait(), timeout=30)
        except TimeoutError:
            pytest.fail(
                f"No checkpoint: {runtime.agents.get_run(run.id).error}; "
                f"steps={[(s.kind, s.error) for s in runtime.agents.list_steps(run.id)]}"
            )
        await runtime.agent_runtime.stop()
        await runtime.agent_runtime.start()
        final = await _wait_status(
            runtime, run.id, AgentRunStatus.COMPLETED, timeout=40
        )
        assert final.output["content"] == "done"
        assert summary_calls >= 2 and saw_memory
        steps = runtime.agents.list_steps(run.id)
        assert any(
            s.action_key.startswith(PREFIX) and s.status is RunStepStatus.CANCELLED
            for s in steps
        )
        cp = next(
            s
            for s in steps
            if s.action_key.startswith(PREFIX) and s.status is RunStepStatus.COMPLETED
        )
        assert cp.input[CHECKPOINT_KEY]["source_sha256"]
        ctx = runtime.tools.context_for_session(
            caller_id="agent:test.checkpoints",
            session_id=run.session_id,
            trace_id=run.id,
        )
        page = (
            await runtime.tools.execute(
                CHECKPOINT_READER, {"step_id": cp.id}, context=ctx
            )
        ).output
        assert "previous_checkpoint_step_id" in page["content"]
        assert len(page["sha256"]) == 64
        other = runtime.tools.context_for_session(
            caller_id=ctx.caller_id, session_id=_session(runtime), trace_id=run.id
        )
        with pytest.raises(ToolGatewayError):
            await runtime.tools.execute(
                CHECKPOINT_READER, {"step_id": cp.id}, context=other
            )
        assert sum(s.kind == "tool" for s in steps) == 6
        # Reconstruct after Runtime restart; summaries are not user-facing answers.
        await runtime.agent_runtime.stop()
        await runtime.agent_runtime.start()
        assert runtime.agents.get_run(run.id).output["content"] == "done"
        assert runtime.agents.list_steps(run.id) == steps
    finally:
        await runtime.agent_runtime.stop()


def test_v2_preserves_user_evidence_even_when_summary_omits_constraints():
    value = request()
    value["messages"][1:1] = [
        {"role": "user", "content": "只能修改 A；不能修改 B；必须通过测试 C。"},
        {"role": "assistant", "content": "investigation " * 400},
    ]
    kwargs = dict(
        base_count=4, steps=(), max_bytes=12000, reader_alias="reader", run_id="run"
    )
    _, _, action = prepare_checkpoint(value, **kwargs)
    assert action is not None
    missing = summary()
    missing["constraints"] = []
    step = checkpoint(action, response(encode(missing)))
    projected, audit, _ = prepare_checkpoint(value, **{**kwargs, "steps": [step]})
    memory = next(
        json.loads(m["content"])
        for m in projected["messages"]
        if '"verbatim_user_records"' in str(m.get("content"))
    )
    records = memory["verbatim_user_records"]
    assert records[0]["message"] == value["messages"][1]
    assert memory["summary"]["constraints"] == []
    assert audit["checkpoint_user_record_count"] == 1
    assert audit["checkpoint_coverage_verified"] is True
    assert records[0]["source_group"] == 0
    step.input[CHECKPOINT_KEY]["requirements_sha256"] = "wrong"
    restored, rejected, _ = prepare_checkpoint(value, **{**kwargs, "steps": [step]})
    assert restored == value
    assert rejected["checkpoint_step_id"] is None


def test_v2_state_is_rebuilt_not_taken_from_generated_summary():
    from ai2apps.agents.compaction import execution_state
    from ai2apps.agents.models import InteractionKind, InteractionStatus

    context = SimpleNamespace(
        run=SimpleNamespace(id="run", revision=9),
        steps=[
            SimpleNamespace(
                id="failed-tool",
                kind="tool",
                tool_name="test",
                status=RunStepStatus.FAILED,
                error={"code": "test_failed"},
            )
        ],
        interactions=[
            SimpleNamespace(
                id="answer",
                revision=2,
                kind=InteractionKind.TEXT,
                status=InteractionStatus.SUBMITTED,
                prompt="格式？",
                response={"answer": "用 CSV，不要 JSON"},
            ),
            SimpleNamespace(
                id="permission",
                revision=1,
                kind=InteractionKind.APPROVAL,
                status=InteractionStatus.SUBMITTED,
                prompt="private",
                response={"credential": "must-not-be-projected"},
            ),
        ],
    )
    plan = {
        "revision": 3,
        "items": [{"id": "test", "title": "Run test C", "status": "pending"}],
    }
    state = execution_state(context, plan)
    assert state["tool_steps"][0]["status"] == "failed"
    assert state["interactions"][0]["response"] == {"answer": "用 CSV，不要 JSON"}
    assert "must-not-be-projected" not in encode(state)
    value = request()
    _, _, action = prepare(value)
    step = checkpoint(action)

    def project(snapshot):
        return prepare_checkpoint(
            value,
            base_count=2,
            steps=[step],
            max_bytes=12000,
            reader_alias="reader",
            run_id="run",
            state=snapshot,
        )

    projected, audit, _ = project(state)
    envelope = json.loads(projected["messages"][-1]["content"])
    assert envelope["state"]["plan"] == plan
    assert audit["execution_state_sha256"]
    updated = {**state, "revision": 10, "plan": {"revision": 4, "items": []}}
    new, new_audit, _ = project(updated)
    assert json.loads(new["messages"][-1]["content"])["state"]["plan"]["revision"] == 4
    assert new_audit["checkpoint_step_id"] == audit["checkpoint_step_id"]
    assert new_audit["execution_state_sha256"] != audit["execution_state_sha256"]


def test_protected_history_never_falls_back_to_silent_dropping():
    from ai2apps.agents.context import ContextBudgetError, bound_request

    value = {
        "messages": [
            {"role": "user", "content": "important " * 1000},
            {"role": "user", "content": "continue"},
        ]
    }
    with pytest.raises(ContextBudgetError):
        bound_request(value, base_count=2, max_bytes=500, preserve_history=True)
    assert bound_request(value, base_count=2, max_bytes=500)[1]["omitted_messages"] == 1


def test_legacy_checkpoint_is_rebuilt_under_v2_not_adopted():
    value = request()
    _, _, action = prepare(value)
    step = checkpoint(action)
    step.input[CHECKPOINT_KEY]["policy"] = "context-checkpoint/v1"
    step.action_key = PREFIX + "legacy"
    projected, audit, upgrade = prepare(value, [step])
    assert audit["checkpoint_step_id"] is None
    assert projected == value
    assert upgrade is not None
    assert upgrade.request[CHECKPOINT_KEY]["policy"] == "context-checkpoint/v2"


def test_provider_pressure_can_force_checkpoint_under_byte_ceiling():
    value = request()
    _, _, action = prepare_checkpoint(
        value, base_count=2, steps=(), max_bytes=524288,
        reader_alias='read_checkpoint', run_id='run', force=True,
    )
    assert action is not None
    assert action.request[CHECKPOINT_KEY]['covered_groups'] > 0
