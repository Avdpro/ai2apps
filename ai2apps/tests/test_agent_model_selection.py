from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.agent_builder import compile_source
from ai2apps.agents import browser_builder_executor
from ai2apps.api.agent_platform import AgentFromChatRequest, RecipeReviewRevisionRequest
from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime


def source(tier="standard"):
    return {
        "inputs": {"type": "object"},
        "outputs": {"type": "object"},
        "site_scope": ["https://example.com/**"],
        "steps": [
            {
                "name": "summary",
                "operation": "ai.transform",
                "desc": "Summarize",
                "ai": {
                    "tier": tier,
                    "instruction": "Summarize actual evidence",
                    "output_schema": {"type": "object"},
                },
                "on": {"success": "done", "failed": "failed"},
            }
        ],
    }


def test_review_tier_change_is_versioned_and_preserves_instructions(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    principal = RequestPrincipal.legacy_local()
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime, principal_provider=lambda: principal
        )
    )
    client = TestClient(app)
    recipe = runtime.agent_builder.create_recipe(
        owner_user_id=principal.actor_user_id,
        name="Summary",
        description="Read and summarize",
        source=source(),
    )
    url = f"/v1/platform/agent-recipes/{recipe.id}/steps/model-tier"
    response = client.post(
        url,
        json={"expected_revision": recipe.revision, "step_index": 0, "tier": "complex"},
    )
    assert response.status_code == 200, response.text
    revised = response.json()
    ai = revised["review"]["source"]["steps"][0]["ai"]
    assert ai["tier"] == "complex"
    assert ai["instruction"] == "Summarize actual evidence"
    assert revised["review"]["compiled_ir"]["steps"][0]["ai"]["tier"] == "complex"
    assert (
        client.post(
            url,
            json={
                "expected_revision": recipe.revision,
                "step_index": 0,
                "tier": "simple",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            url,
            json={
                "expected_revision": recipe.revision + 1,
                "step_index": 5,
                "tier": "simple",
            },
        ).status_code
        == 422
    )
    runtime.stop()


def test_each_ai_tier_calls_the_matching_execution_model():
    for tier in ["simple", "standard", "complex"]:
        compiled = compile_source(source(tier))
        assert compiled.valid
        context = SimpleNamespace(
            definition=SimpleNamespace(max_steps=20),
            run=SimpleNamespace(
                input={
                    "parameters": {
                        "ir": compiled.ir,
                        "ai_model_routes": {
                            "simple": "low-model",
                            "standard": "medium-model",
                            "complex": "high-model",
                        },
                    }
                }
            ),
            interactions=[],
            step=lambda _: None,
        )
        action = browser_builder_executor(context)
        assert (
            action.request["model"]
            == {
                "simple": "low-model",
                "standard": "medium-model",
                "complex": "high-model",
            }[tier]
        )


def test_builder_defaults_to_medium_and_accepts_explicit_model():
    assert AgentFromChatRequest(prompt="Search").model_tier == "standard"
    assert (
        RecipeReviewRevisionRequest(
            expected_revision=1, feedback="Summarize", model="cloud/ai2apps/example"
        ).model
        == "cloud/ai2apps/example"
    )


def test_builder_uses_explicit_model_or_selected_task_tier(tmp_path):
    import json

    from starlette.responses import JSONResponse

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    called = []

    class Invocations:
        def model(self, model_id):
            return SimpleNamespace(id=model_id, endpoints=["chat_completions"])

        def context_for_actor(self, actor, **kwargs):
            return SimpleNamespace(actor=actor)

        async def invoke_foreground_json(self, model_id, endpoint, payload, **kwargs):
            called.append((model_id, payload["model"]))
            return JSONResponse(
                {"choices": [{"message": {"content": json.dumps(source())}}]}
            )

    runtime.model_invocations = Invocations()
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: purpose + "-model"
    )
    principal = RequestPrincipal.legacy_local()
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime, principal_provider=lambda: principal
        )
    )
    client = TestClient(app)
    for choice, expected in [
        ({"model": "specific-model"}, "specific-model"),
        ({"model_tier": "complex"}, "work_complex-model"),
        ({}, "work_standard-model"),
    ]:
        response = client.post(
            "/v1/platform/agent-recipes",
            json={
                "prompt": "Summarize actual evidence",
                "page": {"url": "https://example.com"},
                **choice,
            },
        )
        assert response.status_code == 201, response.text
        assert called[-1] == (expected, expected)
    runtime.stop()
