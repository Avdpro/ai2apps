from types import SimpleNamespace

from ai2apps.agent_builder import compile_source
from ai2apps.agents import browser_builder_executor
from ai2apps.agents.models import (
    CompleteAction,
    InteractionAction,
    InteractionStatus,
    ModelCallAction,
)


def source():
    return {
        "inputs": {
            "type": "object",
            "properties": {"summarize": {"type": "boolean", "default": False}},
        },
        "outputs": {"type": "object"},
        "site_scope": ["https://www.google.com/**"],
        "steps": [
            {
                "name": "results",
                "operation": "extract_list",
                "desc": "Extract results",
                "on": {"success": "read", "failed": "failed"},
            },
            {
                "name": "read",
                "operation": "read_results",
                "desc": "Read top results",
                "arguments": {"from_step": "results", "limit": 3},
                "when": {"input": "summarize", "equals": True},
                "on": {"success": "summary", "skipped": "done", "failed": "failed"},
            },
            {
                "name": "summary",
                "operation": "ai.transform",
                "desc": "Summarize pages",
                "ai": {
                    "tier": "standard",
                    "instruction": "Summarize only article evidence with sources",
                    "output_schema": {"type": "object"},
                },
                "on": {"success": "done", "failed": "failed"},
            },
        ],
    }


def context(enabled, interactions=()):
    compiled = compile_source(source())
    assert compiled.valid, compiled.report
    return SimpleNamespace(
        definition=SimpleNamespace(max_steps=20),
        run=SimpleNamespace(
            input={
                "parameters": {
                    "ir": compiled.ir,
                    "invocation_input": {"summarize": enabled},
                    "ai_model_routes": {"standard": "test-model"},
                }
            }
        ),
        interactions=interactions,
        step=lambda _: None,
    )


def submit(action, result, ident):
    return SimpleNamespace(
        id=ident,
        request=action.request,
        status=InteractionStatus.SUBMITTED,
        response={"outcome": "success", "evidence": {"result": result}},
    )


def test_optional_summary_skips_reading_and_preserves_search_results():
    first = browser_builder_executor(context(False))
    items = [{"url": "https://example.com/story", "title": "Story"}]
    finished = browser_builder_executor(
        context(False, (submit(first, {"items": items}, "1"),))
    )
    assert isinstance(finished, CompleteAction)
    assert finished.output["result"]["items"] == items


def test_result_urls_and_article_text_flow_into_summary_model():
    first = browser_builder_executor(context(True))
    items = [{"url": "https://example.com/story", "title": "Story"}]
    extracted = submit(first, {"items": items}, "1")
    reading = browser_builder_executor(context(True, (extracted,)))
    assert isinstance(reading, InteractionAction)
    assert reading.request["step"]["arguments"]["items"] == items
    article = {"articles": [{"url": items[0]["url"], "text": "Actual article body"}]}
    model = browser_builder_executor(
        context(True, (extracted, submit(reading, article, "2")))
    )
    assert isinstance(model, ModelCallAction)
    assert model.request["model"] == "test-model"
    assert "Actual article body" in model.request["messages"][1]["content"]
    assert "https://example.com/story" in model.request["messages"][1]["content"]


def test_reader_rejects_future_reference_and_unbounded_count():
    value = source()
    value["steps"][1]["arguments"] = {"from_step": "summary", "limit": 100}
    report = compile_source(value).report
    assert {"prior_result_required", "read_limit_invalid"} <= {
        item["code"] for item in report["errors"]
    }


async def test_durable_cloud_model_uses_session_owner_without_http_cookie(monkeypatch):
    import json

    from fastapi.responses import JSONResponse

    from ai2apps import cloud_gateway, model_invocation
    from ai2apps.model_invocation import ModelInvocationService

    principal = SimpleNamespace(
        actor_user_id="owner", installation_id="installation", membership_epoch=4
    )
    monkeypatch.setattr(
        model_invocation,
        "IdentityRepository",
        lambda _: SimpleNamespace(
            principal_for=lambda actor: principal if actor == "owner" else None
        ),
    )
    received = {}

    async def proxy(request, **kwargs):
        received.update(kwargs)
        assert request.stream is False
        return JSONResponse(
            {"choices": [{"message": {"content": '{"summary":"Actual summary"}'}}]}
        )

    monkeypatch.setattr(cloud_gateway, "proxy_cloud_chat_completion", proxy)
    runtime = SimpleNamespace(
        database=object(),
        config=SimpleNamespace(paths=SimpleNamespace(base_path="/tmp")),
        model_manager=object(),
        cloud=object(),
        cloud_ai_authorization_headers=lambda actor: {"actor": actor.actor_user_id},
    )
    service = ModelInvocationService(runtime)
    result = await service.invoke_agent_cloud_json(
        {
            "model": "cloud/ai2apps/test",
            "messages": [{"role": "user", "content": "Summarize"}],
        },
        context=SimpleNamespace(
            actor_user_id="owner", installation_id="installation", membership_epoch=4
        ),
    )
    assert (
        json.loads(result["choices"][0]["message"]["content"])["summary"]
        == "Actual summary"
    )
    assert received["authorization_headers"] == {"actor": "owner"}
