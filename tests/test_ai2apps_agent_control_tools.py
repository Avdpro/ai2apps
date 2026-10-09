"""Durable question/answer and Run plan contracts."""

import json

import pytest
from test_ai2apps_agents import _runtime, _session, _wait_status

from ai2apps.agents import AgentRunStatus
from ai2apps.agents.control_tools import ASK_USER, PLAN_READ, PLAN_UPDATE
from ai2apps.api.agents import _run_response
from ai2apps.core import ResourceConflictError
from ai2apps.services import ToolGatewayError


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [None, ["CSV", "JSON"]])
async def test_question_survives_restart_and_returns_free_text(tmp_path, options):
    runtime = _runtime(tmp_path)
    calls = []
    arguments = {"question_id": "format", "question": "选择格式？"}
    if options:
        arguments["options"] = options

    def model(request):
        calls.append(request)
        if len(calls) == 1:
            alias = next(
                t["function"]["name"]
                for t in request["tools"]
                if t["function"]["name"].startswith("agent__ask_user_")
            )
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "ask-format",
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
        result = request["messages"][-1]
        assert result["tool_call_id"] == "ask-format"
        assert json.loads(result["content"])["answer"] == "用 Markdown"
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "done"},
                    "finish_reason": "stop",
                }
            ]
        }

    runtime.agent_runtime.bind_model_provider(model)
    run, _ = runtime.agents.create_run(
        session_id=_session(runtime),
        agent_key="ai2apps.general-agent",
        input={"model": "test", "prompt": "export"},
    )
    await runtime.agent_runtime.start()
    try:
        await _wait_status(runtime, run.id, AgentRunStatus.WAITING_INPUT)
        interaction = runtime.agents.list_interactions(run.id)[0]
        assert interaction.kind.value == ("menu" if options else "text")
        assert interaction.ui_hints["allow_other"] == bool(options)
        await runtime.agent_runtime.stop()
        await runtime.agent_runtime.start()
        assert len(runtime.agents.list_interactions(run.id)) == 1
        with pytest.raises(ResourceConflictError):
            runtime.agents.respond_interaction(
                run.id, interaction.id, response={"answer": ""}, response_id="empty"
            )
        runtime.agents.respond_interaction(
            run.id,
            interaction.id,
            response={"answer": "用 Markdown"},
            response_id="answer",
        )
        runtime.agent_runtime.wake()
        completed = await _wait_status(runtime, run.id, AgentRunStatus.COMPLETED, timeout=10)
        assert not completed.granted_capabilities
        assert len(calls) == 2
        assert len(runtime.agents.list_steps(run.id)) == 3
    finally:
        await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_plan_is_revisioned_isolated_and_in_run_snapshot(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    run, _ = runtime.agents.create_run(
        session_id=session, agent_key="ai2apps.general-agent", input={"prompt": "plan"}
    )
    assert runtime.agents.claim_next().id == run.id
    runtime.agents.transition(
        run.id, expected={AgentRunStatus.PLANNING}, status=AgentRunStatus.RUNNING
    )
    ctx = runtime.tools.context_for_session(
        caller_id="agent:ai2apps.general-agent", session_id=session, trace_id=run.id
    )
    with pytest.raises(ToolGatewayError):
        await runtime.tools.execute(
            ASK_USER, {"question_id": "fake", "question": "Fabricated?"}, context=ctx
        )
    initial = (await runtime.tools.execute(PLAN_READ, {}, context=ctx)).output
    assert initial == {"revision": 0, "items": []}
    items = [{"id": "one", "title": "Read data", "status": "in_progress"}]
    args = {"expected_revision": 0, "items": items}
    result = (await runtime.tools.execute(PLAN_UPDATE, args, context=ctx)).output
    assert result["revision"] == 1
    assert (
        await runtime.tools.execute(PLAN_UPDATE, args, context=ctx)
    ).output == result
    assert _run_response(runtime, runtime.agents.get_run(run.id)).plan == result
    with pytest.raises(ToolGatewayError):
        await runtime.tools.execute(
            PLAN_UPDATE, {"expected_revision": 0, "items": []}, context=ctx
        )
    other = runtime.tools.context_for_session(
        caller_id=ctx.caller_id, session_id=_session(runtime), trace_id=run.id
    )
    with pytest.raises(ToolGatewayError):
        await runtime.tools.execute(PLAN_READ, {}, context=other)
    with pytest.raises(ValueError):
        runtime.agents.update_plan(run.id, expected_revision=1, items=items * 2)
    finished = [{**items[0], "status": "completed"}]
    runtime.agents.update_plan(run.id, expected_revision=1, items=finished)
    assert runtime.agents.get_run(run.id).status is AgentRunStatus.RUNNING
    assert runtime.agents.get_plan(run.id)["revision"] == 2
    events = [
        e
        for e in runtime.events.list_after(subject_id=run.id, limit=1000)
        if e.type == "agent.plan.updated"
    ]
    assert len(events) == 2
    runtime.stop()
