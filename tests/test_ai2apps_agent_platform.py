from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from ai2apps.agent_builder import validate_web_agent_package
from ai2apps.agents import AgentRunStatus
from ai2apps.api.agent_platform import (
    AgentPresentationSpec,
    _presentation_content,
    _validate_presentation_for_result,
)
from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.extensions import UnitKind
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.packages.contract_v1 import inspect_package
from ai2apps.platform_runtime import PlatformRuntime


def _principal() -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id="agent-platform-owner",
        installation_id="installation-agent-platform",
        organization_id="organization-agent-platform",
        billing_account_id="billing-agent-platform",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )


def _client(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=_principal,
        )
    )
    return runtime, TestClient(app)


def _source(name: str, capability: str):
    return {
        "schema": "ai2apps.agent-source/v1",
        "agent_type": "web",
        "name": name,
        "description": "Read the current page",
        "site_scope": ["https://example.com/**"],
        "inputs": {
            "type": "object",
            "properties": {"limit": {"type": "integer"}},
        },
        "outputs": {"type": "object"},
        "capability_exports": [
            {"name": capability, "description": "Read page", "effects": ["read"]}
        ],
        "fixtures": [{"name": "basic", "input": {"limit": 5}, "output": {}}],
        "validators": [{"kind": "required_fields", "fields": []}],
        "steps": [
            {
                "name": "inspect",
                "desc": "读取当前页面内容，成功转 done",
                "operation": "inspect",
                "on": {"success": "done", "failed": "failed"},
            },
            {
                "name": "finish",
                "desc": "完成",
                "operation": "complete",
            }
        ],
    }


def _active_agent(client: TestClient, name="Page Reader", capability="web.page.read"):
    source = _source(name, capability)
    draft = client.post(
        "/v1/platform/agent-drafts",
        json={
            "agent_type": "web",
            "name": name,
            "site_scope": source["site_scope"],
            "source": source,
        },
    ).json()
    generation_response = client.post(
        f"/v1/platform/agent-drafts/{draft['id']}/compile"
    )
    assert generation_response.status_code == 200
    generation = generation_response.json()
    assert generation["report"]["fixture_results"][0]["valid"] is True
    activated = client.post(
        f"/v1/platform/agent-drafts/{draft['id']}/generations/"
        f"{generation['id']}/activate"
    )
    assert activated.status_code == 200
    return activated.json(), generation


def test_agent_presentation_spec_is_declarative_and_bound_to_result_paths():
    result = {"items": [{"title": "One", "url": "https://example.com/one"}]}
    spec = AgentPresentationSpec.model_validate(
        {
            "version": 1,
            "view": "cards",
            "data_path": "$.items",
            "fields": [
                {"path": "title", "label": "Title", "primary": True},
                {"path": "url", "label": "Link", "format": "link"},
            ],
            "show_unmapped_fields": True,
        }
    )
    assert _validate_presentation_for_result(spec, result) is spec
    assert _presentation_content(
        {"choices": [{"message": {"content": "```json\n{\"version\": 1}\n```"}}]}
    ) == {"version": 1}

    missing = spec.model_copy(update={"data_path": "$.missing"})
    try:
        _validate_presentation_for_result(missing, result)
    except ValueError as error:
        assert "data_path" in str(error)
    else:
        raise AssertionError("missing presentation data_path must be rejected")


def test_agent_presentation_uses_the_standard_task_model(tmp_path):
    runtime, client = _client(tmp_path)
    _active_agent(client)
    invoked = client.post(
        "/v1/platform/agent-capabilities/web.page.read/invoke",
        json={"browser_context": {"url": "https://example.com/news"}},
    )
    run_id = invoked.json()["run_id"]
    model = SimpleNamespace(
        id="standard-model", endpoints={"chat_completions": "/v1/chat/completions"}
    )
    invoke = AsyncMock(
        return_value=Response(
            content=(
                '{"choices":[{"message":{"content":"{\\"version\\":1,'
                '\\"view\\":\\"key_value\\",\\"data_path\\":\\"$\\",'
                '\\"fields\\":[{\\"path\\":\\"$\\",\\"label\\":\\"Result\\"}],'
                '\\"show_unmapped_fields\\":true}"}}]}'
            ),
            media_type="application/json",
        )
    )
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "standard-model" if purpose == "work_standard" else None
        )
    )
    runtime.model_invocations = SimpleNamespace(
        model=lambda model_id: model if model_id == model.id else None,
        context_for_actor=lambda *args, **kwargs: SimpleNamespace(),
        invoke_foreground_json=invoke,
    )

    response = client.post(
        f"/v1/platform/agent-draft-runs/{run_id}/presentation",
        json={"locale": "en"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["presentation"]["view"] == "key_value"
    assert response.json()["model_id"] == "standard-model"
    assert invoke.await_args.args[1] == "chat_completions"
    assert "temperature" not in invoke.await_args.args[2]


def test_agent_recipe_is_ai_compiled_and_locally_validated(tmp_path):
    runtime, client = _client(tmp_path)
    model = SimpleNamespace(
        id="standard-model", endpoints={"chat_completions": "/v1/chat/completions"}
    )
    source = {
        "steps": [
            {
                "name": "extract",
                "operation": "extract_list",
                "desc": "提取文章标题、链接、作者、发布时间和图片 URL",
                "arguments": {"fields": [
                    "title", "url", "author", "published_at", "image_url"
                ]},
                "on": {"success": "done", "failed": "failed"},
            }
        ]
    }
    invoke = AsyncMock(
        return_value=Response(
            content=json.dumps({
                "choices": [{"message": {"content": json.dumps(source)}}]
            }),
            media_type="application/json",
        )
    )
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "standard-model" if purpose == "work_standard" else None
        )
    )
    runtime.model_invocations = SimpleNamespace(
        model=lambda model_id: model if model_id == model.id else None,
        context_for_actor=lambda *args, **kwargs: SimpleNamespace(),
        invoke_foreground_json=invoke,
    )

    response = client.post(
        "/v1/platform/agent-recipes",
        json={
            "name": "Article extractor",
            "prompt": "提取每篇文章的标题、链接、作者、发布时间和图片 URL",
            "page": {"url": "https://example.com/news"},
        },
    )

    assert response.status_code == 201, response.text
    compiled = response.json()["source"]
    assert compiled["provenance"]["implicit_ai"] is True
    assert compiled["provenance"]["compiler_model_id"] == "standard-model"
    assert compiled["steps"][0]["arguments"]["fields"][-1] == "image_url"
    assert invoke.await_count == 1
    assert "temperature" not in invoke.await_args.args[2]


def test_agent_recipe_normalizes_model_dsl_and_drops_redundant_current_page_open(
    tmp_path,
):
    runtime, client = _client(tmp_path)
    model = SimpleNamespace(
        id="standard-model", endpoints={"chat_completions": "/v1/chat/completions"}
    )
    model_source = {
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "array", "items": {"type": "object"}},
        "steps": [
            {
                "id": "open_site",
                "operation": "open",
                "params": {"url": "https://example.com/"},
                "transitions": {"success": "extract", "failed": "failed"},
            },
            {
                "id": "extract",
                "operation": "extract_list",
                "params": {
                    "description": "Extract the current article list with images.",
                    "fields": {
                        "title": {"selector": "h2"},
                        "url": {"selector": "a"},
                        "image_url": {"selector": "img"},
                    },
                },
                "transitions": {"success": "done", "failed": "failed"},
            },
        ],
    }
    invoke = AsyncMock(
        return_value=Response(
            content=json.dumps({
                "choices": [{"message": {"content": json.dumps(model_source)}}]
            }),
            media_type="application/json",
        )
    )
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "standard-model" if purpose == "work_standard" else None
        )
    )
    runtime.model_invocations = SimpleNamespace(
        model=lambda _model_id: model,
        context_for_actor=lambda *args, **kwargs: SimpleNamespace(),
        invoke_foreground_json=invoke,
    )

    response = client.post(
        "/v1/platform/agent-recipes",
        json={
            "name": "Current articles",
            "prompt": "获取当前页面的文章列表，包括图片",
            "page": {"url": "https://example.com/news"},
        },
    )

    assert response.status_code == 201, response.text
    source = response.json()["source"]
    assert [step["operation"] for step in source["steps"]] == ["extract_list"]
    assert source["steps"][0]["name"] == "extract"
    assert source["steps"][0]["on"]["success"] == "done"
    assert source["steps"][0]["arguments"]["fields"] == [
        "title", "url", "image_url"
    ]
    assert source["outputs"]["type"] == "object"


def test_recipe_review_gates_commit_and_feedback_creates_new_revision(tmp_path):
    runtime, client = _client(tmp_path)
    created = client.post(
        "/v1/platform/agent-recipes",
        json={
            "name": "Current articles",
            "prompt": "获取当前页面的文章列表",
            "page": {"url": "https://example.com/news"},
        },
    )
    assert created.status_code == 201, created.text
    recipe = created.json()

    rejected = client.post(
        f"/v1/platform/agent-recipes/{recipe['id']}/commit",
        json={"mode": "create"},
    )
    assert rejected.status_code == 409

    model = SimpleNamespace(
        id="standard-model", endpoints={"chat_completions": "/v1/chat/completions"}
    )
    revised_source = {
        "steps": [{
            "name": "extract",
            "desc": "提取文章；发布日期缺失时仍然保留",
            "operation": "extract_list",
            "arguments": {"fields": ["title", "url", "published_at", "image_url"]},
            "on": {"success": "done", "failed": "failed"},
        }]
    }
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "standard-model" if purpose == "work_standard" else None
        )
    )
    runtime.model_invocations = SimpleNamespace(
        model=lambda _model_id: model,
        context_for_actor=lambda *args, **kwargs: SimpleNamespace(),
        invoke_foreground_json=AsyncMock(return_value=Response(
            content=json.dumps({
                "choices": [{"message": {"content": json.dumps(revised_source)}}]
            }),
            media_type="application/json",
        )),
    )

    revised = client.post(
        f"/v1/platform/agent-recipes/{recipe['id']}/review/revisions",
        json={
            "expected_revision": recipe["revision"],
            "feedback": "发布日期缺失时仍保留，并增加 image_url",
            "locale": "zh-CN",
        },
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["recipe"]["revision"] == recipe["revision"] + 1
    assert revised.json()["review"]["status"] == "awaiting_review"
    assert revised.json()["review"]["steps"][0]["compiled"]["arguments"]["fields"][-1] == "image_url"

    stale = client.post(
        f"/v1/platform/agent-recipes/{recipe['id']}/review/approve",
        json={"expected_revision": recipe["revision"]},
    )
    assert stale.status_code == 409
    current = revised.json()["recipe"]
    approved = client.post(
        f"/v1/platform/agent-recipes/{recipe['id']}/review/approve",
        json={"expected_revision": current["revision"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review"]["status"] == "approved"


def test_exploration_plans_one_step_then_distills_verified_path(tmp_path):
    runtime, client = _client(tmp_path)
    model = SimpleNamespace(
        id="standard-model", endpoints={"chat_completions": "/v1/chat/completions"}
    )
    act = {
        "decision": "act",
        "reason": "First read the current list.",
        "expected_effect": "Return article records.",
        "step": {
            "name": "extract-articles",
            "desc": "提取当前页面文章标题、链接、作者、发布时间和图片 URL",
            "operation": "extract_list",
            "arguments": {"fields": [
                "title", "url", "author", "published_at", "image_url"
            ]},
            "on": {"success": "done", "failed": "failed"},
            "execution": "compiled",
            "interaction": "precise",
        },
    }
    invoke = AsyncMock(side_effect=[
        Response(content=json.dumps({
            "choices": [{"message": {"content": json.dumps(act)}}]
        }), media_type="application/json"),
        Response(content=json.dumps({
            "choices": [{"message": {"content": json.dumps({
                "version": 1,
                "view": "cards",
                "title": "Articles",
                "data_path": "$.items",
                "fields": [
                    {"path": "title", "label": "Title", "primary": True},
                    {"path": "url", "label": "Link", "format": "link"},
                    {"path": "image_url", "label": "Image", "format": "image"},
                ],
                "show_unmapped_fields": True,
            })}}]
        }), media_type="application/json"),
    ])
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "standard-model" if purpose == "work_standard" else None
        )
    )
    runtime.model_invocations = SimpleNamespace(
        model=lambda _model_id: model,
        context_for_actor=lambda *args, **kwargs: SimpleNamespace(),
        invoke_foreground_json=invoke,
    )
    base = {
        "goal": "获取当前页面的文章列表，包含图片 URL",
        "name": "Article explorer",
        "page": {"url": "https://example.com/news", "title": "Private title"},
        "observation": {
            "fingerprint": "example.com|/news|10|4|0",
            "text_length": 999,
            "link_count": 4,
            "button_count": 0,
            "control_count": 4,
            "text_sample": "DO NOT FORWARD THIS PRIVATE PAGE TEXT",
        },
        "attempts": [],
    }
    proposed = client.post("/v1/platform/agent-explorations/next", json=base)
    assert proposed.status_code == 200, proposed.text
    proposal = proposed.json()
    assert proposal["decision"] == "act"
    assert proposal["compiled_step"]["operation"] == "extract_list"
    assert proposal["confirmation"] is None
    first_payload = invoke.await_args_list[0].args[2]
    assert "DO NOT FORWARD" not in json.dumps(first_payload)

    attempt = {
        "proposal_id": proposal["proposal_id"],
        "source_step": proposal["source_step"],
        "compiled_step": proposal["compiled_step"],
        "outcome": "success",
        "evidence": {
            "before": {"fingerprint": "before"},
            "after": {"fingerprint": "after"},
            "result": {"items": [{
                "title": "PRIVATE ARTICLE TITLE",
                "url": "https://example.com/a",
                "image_url": "https://example.com/a.jpg",
            }]},
        },
    }
    finished = client.post(
        "/v1/platform/agent-explorations/next",
        json={**base, "attempts": [attempt]},
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["decision"] == "complete"
    assert finished.json()["model_tier"] == "deterministic"
    assert invoke.await_count == 1

    distilled = client.post(
        "/v1/platform/agent-explorations/distill",
        json={
            "goal": base["goal"], "name": base["name"],
            "page": base["page"], "attempts": [attempt],
        },
    )
    assert distilled.status_code == 201, distilled.text
    assert distilled.json()["recipe"]["source"]["provenance"]["strategy"] == "one_step_exploration"
    assert distilled.json()["recipe"]["source"]["provenance"]["presentation_sample"] == attempt["evidence"]["result"]
    assert distilled.json()["review"]["steps"][0]["compiled"]["operation"] == "extract_list"
    presented = client.post(
        "/v1/platform/agent-recipes/"
        f"{distilled.json()['recipe']['id']}/presentation",
        json={"locale": "zh-CN"},
    )
    assert presented.status_code == 200, presented.text
    assert presented.json()["recipe_id"] == distilled.json()["recipe"]["id"]
    assert presented.json()["presentation"]["view"] == "cards"
    assert invoke.await_count == 2


def test_exploration_escalates_invalid_standard_plan_to_complex_model(tmp_path):
    runtime, client = _client(tmp_path)
    models = {
        "standard-model": SimpleNamespace(
            id="standard-model", endpoints={"chat_completions": "/v1/chat/completions"}
        ),
        "complex-model": SimpleNamespace(
            id="complex-model", endpoints={"chat_completions": "/v1/chat/completions"}
        ),
    }
    valid = {
        "decision": "act",
        "reason": "Use deterministic extraction.",
        "expected_effect": "Return complete article records.",
        "step": {
            "name": "extract-articles",
            "desc": "提取文章及图片 URL",
            "operation": "extract_list",
            "arguments": {
                "fields": [
                    "title", "url", "author", "published_at", "image_url"
                ]
            },
            "on": {"success": "done", "failed": "failed"},
            "execution": "compiled",
            "interaction": "precise",
        },
    }
    invalid_response = Response(
        content=json.dumps({
            "choices": [{"message": {"content": '{"decision":"unknown"}'}}]
        }),
        media_type="application/json",
    )
    valid_response = Response(
        content=json.dumps({
            "choices": [{"message": {"content": json.dumps(valid)}}]
        }),
        media_type="application/json",
    )
    invoke = AsyncMock(side_effect=[invalid_response, invalid_response, valid_response])
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: {
            "work_standard": "standard-model",
            "work_complex": "complex-model",
        }.get(purpose)
    )
    runtime.model_invocations = SimpleNamespace(
        model=lambda model_id: models[model_id],
        context_for_actor=lambda *args, **kwargs: SimpleNamespace(),
        invoke_foreground_json=invoke,
    )

    response = client.post(
        "/v1/platform/agent-explorations/next",
        json={
            "goal": "提取当前页面文章标题、链接、作者、发布时间和图片 URL",
            "name": "Article explorer",
            "page": {"url": "https://example.com/news", "title": "News"},
            "observation": {
                "fingerprint": "example.com|/news|10|4|0",
                "text_length": 999,
                "link_count": 4,
                "button_count": 0,
                "control_count": 4,
            },
            "attempts": [],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["decision"] == "act"
    assert result["model_id"] == "complex-model"
    assert result["model_tier"] == "complex"
    assert result["model_escalated"] is True
    assert result["compiled_step"]["mode"] == "compiled"
    assert result["compiled_step"]["interaction"]["profile"] == "precise"
    assert result["model_failures"][0]["tier"] == "standard"
    assert [call.args[0] for call in invoke.await_args_list] == [
        "standard-model", "standard-model", "complex-model"
    ]
    assert all(
        "temperature" not in call.args[2]
        for call in invoke.await_args_list
    )


def test_exploration_normalizes_common_model_shorthand(tmp_path):
    runtime, client = _client(tmp_path)
    candidate = {
        "decision": "act",
        "step": {
            "name": "extract-articles",
            "description": "Extract the current page article list",
            "operation": "extract",
            "target": "article cards",
            "params": {
                "fields": "title, url, author, published_at, image_url",
            },
            "execution": "deterministic",
            "interaction": "natural",
            "transitions": "done",
        },
    }
    response_body = Response(
        content=json.dumps({
            "choices": [{"message": {"content": json.dumps(candidate)}}]
        }),
        media_type="application/json",
    )
    invoke = AsyncMock(return_value=response_body)
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "standard-model" if purpose == "work_standard" else None
        )
    )
    runtime.model_invocations = SimpleNamespace(
        model=lambda _model_id: SimpleNamespace(
            id="standard-model",
            endpoints={"chat_completions": "/v1/chat/completions"},
        ),
        context_for_actor=lambda *args, **kwargs: SimpleNamespace(),
        invoke_foreground_json=invoke,
    )

    response = client.post(
        "/v1/platform/agent-explorations/next",
        json={
            "goal": "提取当前页面文章标题、链接、作者、发布时间和图片 URL",
            "name": "Article explorer",
            "page": {"url": "https://example.com/news", "title": "News"},
            "observation": {
                "fingerprint": "example.com|/news|10|4|0",
                "text_length": 999,
                "link_count": 4,
                "button_count": 0,
                "control_count": 4,
            },
            "attempts": [],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["compiled_step"]["operation"] == "extract_list"
    assert result["compiled_step"]["mode"] == "adaptive"
    assert result["source_step"]["target"] == {"intent": "article cards"}
    assert result["source_step"]["arguments"]["fields"] == [
        "title", "url", "author", "published_at", "image_url"
    ]


def test_agent_presentation_routes_enabled_cloud_standard_model(tmp_path):
    runtime, client = _client(tmp_path)

    @client.app.post("/v1/chat/completions")
    async def fake_chat_completion(payload: dict):
        assert payload["model"] == "cloud/deepseek/deepseek-v4-flash"
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"version":1,"view":"key_value","data_path":"$",'
                            '"fields":[{"path":"$","label":"Result"}],'
                            '"show_unmapped_fields":true}'
                        )
                    }
                }
            ]
        }

    _active_agent(client)
    invoked = client.post(
        "/v1/platform/agent-capabilities/web.page.read/invoke",
        json={"browser_context": {"url": "https://example.com/news"}},
    )
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "cloud/deepseek/deepseek-v4-flash"
            if purpose == "work_standard"
            else None
        )
    )
    runtime.model_invocations = SimpleNamespace(model=lambda _model_id: None)

    response = client.post(
        "/v1/platform/agent-draft-runs/"
        f"{invoked.json()['run_id']}/presentation",
        json={"locale": "zh-CN"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["model_id"] == "cloud/deepseek/deepseek-v4-flash"


def test_capability_contract_and_generation_rollback(tmp_path):
    _runtime, client = _client(tmp_path)
    draft, first_generation = _active_agent(client)

    listed = client.get(
        "/v1/platform/agent-capabilities",
        params={"url": "https://example.com/news"},
    )
    assert listed.status_code == 200
    assert listed.json()["implicit_ai"] is False
    assert listed.json()["items"][0]["name"] == "web.page.read"

    source = _source("Page Reader v2", "web.page.read")
    source["description"] = "Edited but not active"
    edited = client.patch(
        f"/v1/platform/agent-drafts/{draft['id']}",
        json={
            "expected_revision": draft["revision"],
            "name": "Page Reader v2",
            "source": source,
        },
    )
    assert edited.status_code == 200
    assert edited.json()["active_generation_id"] == first_generation["id"]

    generations = client.get(
        f"/v1/platform/agent-drafts/{draft['id']}/generations"
    )
    assert generations.status_code == 200
    assert generations.json()[0]["id"] == first_generation["id"]


def test_chat_workflow_schedule_and_knowledge_handoffs(tmp_path):
    runtime, client = _client(tmp_path)
    draft, _generation = _active_agent(client)

    from_chat = client.post(
        "/v1/platform/agent-drafts/from-chat",
        json={
            "name": "Search Agent",
            "prompt": "找到并点击搜索按钮，成功后完成",
            "page": {"url": "https://example.com/news"},
        },
    )
    assert from_chat.status_code == 201
    assert from_chat.json()["source"]["provenance"]["implicit_ai"] is False
    assert from_chat.json()["id"].startswith("arec_")

    review = client.get(
        f"/v1/platform/agent-recipes/{from_chat.json()['id']}/review"
    )
    assert review.status_code == 200, review.text
    assert review.json()["schema"] == "ai2apps.agent-review/v1"
    assert review.json()["steps"][0]["source"]["description"]
    assert review.json()["steps"][0]["compiled"]["operation"] == "click"
    approved = client.post(
        f"/v1/platform/agent-recipes/{from_chat.json()['id']}/review/approve",
        json={"expected_revision": from_chat.json()["revision"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review"]["status"] == "approved"

    committed = client.post(
        f"/v1/platform/agent-recipes/{from_chat.json()['id']}/commit",
        json={"mode": "merge"},
    )
    assert committed.status_code == 201, committed.text
    assert committed.json()["site_agent"]["id"] == draft["id"]
    assert len(committed.json()["site_agent"]["source"]["capabilities"]) == 2

    workflow = client.post(
        "/v1/platform/agent-workflows",
        json={
            "name": "Daily reader",
            "definition": {
                "steps": [{"name": "read", "draft_id": draft["id"]}],
                "inputs": {"type": "object"},
                "outputs": {"type": "object"},
            },
        },
    )
    assert workflow.status_code == 201

    invoked = client.post(
        "/v1/platform/agent-capabilities/web.page.read/invoke",
        headers={"X-AI2Apps-App-ID": "ai2apps.news"},
        json={
            "input": {"limit": 5},
            "browser_context": {"url": "https://example.com/news"},
        },
    )
    assert invoked.status_code == 202, invoked.text
    run_id = invoked.json()["run_id"]

    presentation = client.post(
        f"/v1/platform/agent-draft-runs/{run_id}/presentation",
        json={"locale": "en"},
    )
    assert presentation.status_code == 409
    assert presentation.json()["error"]["code"] == "standard_model_not_configured"

    chat = client.post(
        f"/v1/platform/agent-draft-runs/{run_id}/chat-context", json={}
    )
    assert chat.status_code == 201
    knowledge = client.post(
        f"/v1/platform/agent-draft-runs/{run_id}/knowledge",
        json={"title": "Agent result"},
    )
    assert knowledge.status_code == 201
    assert runtime.knowledge.get_item(_principal(), knowledge.json()["id"]).title == "Agent result"

    schedule = client.post(
        "/v1/platform/agent-schedules",
        json={
            "name": "Daily reader",
            "kind": "interval",
            "interval_seconds": 3600,
            "workflow_id": workflow.json()["id"],
            "input": {"limit": 5},
        },
    )
    assert schedule.status_code == 201
    paused = client.post(
        f"/v1/platform/agent-schedules/{schedule.json()['id']}/pause",
        json={"expected_revision": schedule.json()["revision"]},
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert client.get("/v1/platform/agent-schedules").json()["items"]

    run_now = client.post(
        f"/v1/platform/agent-schedules/{schedule.json()['id']}/run", json={}
    )
    assert run_now.status_code == 200
    runtime.agent_schedule_runner._pass()
    dispatches = client.get(
        f"/v1/platform/agent-schedules/{schedule.json()['id']}/dispatches"
    )
    assert dispatches.status_code == 200
    assert dispatches.json()["items"][0]["run_id"]
    assert dispatches.json()["items"][0]["status"] == "dispatched"


def test_reconcile_combines_same_site_drafts_without_deleting_history(tmp_path):
    _runtime, client = _client(tmp_path)
    first = client.post(
        "/v1/platform/agent-drafts",
        json={"name": "Reader", "site_scope": ["https://www.example.com/**"],
              "source": _source("Reader", "example.read")},
    ).json()
    second_source = _source("Search", "example.read")
    second = client.post(
        "/v1/platform/agent-drafts",
        json={"name": "Search", "site_scope": ["https://example.com/**"],
              "source": second_source},
    ).json()

    reconciled = client.post("/v1/platform/site-agents/reconcile", json={})

    assert reconciled.status_code == 200
    assert len(reconciled.json()["merged"]) == 1
    remaining = client.get("/v1/platform/agent-drafts").json()["items"]
    assert len(remaining) == 1
    assert len(remaining[0]["source"]["capabilities"]) == 2
    assert len({item["name"] for item in remaining[0]["source"]["capabilities"]}) == 2
    assert client.post(
        f"/v1/platform/agent-drafts/{remaining[0]['id']}/compile"
    ).json()["status"] == "validated"
    archived_id = ({first["id"], second["id"]} - {remaining[0]["id"]}).pop()
    archived = client.get(f"/v1/platform/agent-drafts/{archived_id}")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


def test_reconcile_does_not_merge_preview_only_transient_drafts(tmp_path):
    _runtime, client = _client(tmp_path)
    saved_source = _source("Reader", "example.read")
    saved_source["authoring"] = {"saved": True}
    transient_source = _source("Run", "example.preview")
    transient_source["authoring"] = {"saved": False}
    saved = client.post(
        "/v1/platform/agent-drafts",
        json={"name": "Reader", "site_scope": ["https://example.com/**"],
              "source": saved_source},
    ).json()
    transient = client.post(
        "/v1/platform/agent-drafts",
        json={"name": "Run", "site_scope": ["https://example.com/**"],
              "source": transient_source},
    ).json()

    reconciled = client.post("/v1/platform/site-agents/reconcile", json={})

    assert reconciled.status_code == 200
    assert reconciled.json()["merged"] == []
    assert client.get(f"/v1/platform/agent-drafts/{saved['id']}").json()["status"] == "editing"
    assert client.get(f"/v1/platform/agent-drafts/{transient['id']}").json()["status"] == "editing"


def test_internal_browser_page_creates_unscoped_temporary_recipe(tmp_path):
    _runtime, client = _client(tmp_path)

    created = client.post(
        "/v1/platform/agent-recipes",
        json={"name": "Read title", "prompt": "读取当前页面并返回标题",
              "page": {"url": "about:blank", "title": "New tab"}},
    )

    assert created.status_code == 201, created.text
    assert created.json()["site_key"] == ""
    assert created.json()["source"]["site_scope"] == []


def test_p2_exports_contract_package_and_provisions_installed_site_source(tmp_path):
    runtime, client = _client(tmp_path)
    draft, _generation = _active_agent(client)

    exported = client.post(
        f"/v1/platform/agent-drafts/{draft['id']}/package-source",
        json={
            "package_id": "example/page-reader",
            "version": "1.0.0",
            "publisher_id": "publisher-example",
        },
    )
    assert exported.status_code == 201, exported.text
    inspected = inspect_package(exported.json()["artifact"])
    assert inspected.manifest["package"]["type"] == "agent"

    package_source = _source("Packaged Reader", "web.packaged.read")
    package_source["site_key"] = "packaged.example"
    package_source["site_scope"] = ["https://packaged.example/**"]
    package_source["fixtures"] = [{"name": "compile", "input": {}, "output": {}}]
    manifest = {
        "schema": "ai2apps.agent/v1",
        "id": "example.packaged-reader",
        "name": "Packaged Reader",
        "version": "1.0.0",
        "publisher": {"id": "example.publisher"},
        "executor": {"key": "builtin:browser-builder-runtime"},
        "runtime": {"max_steps": 100, "timeout_seconds": 86400},
        "web_agent": {
            "schema": "ai2apps.web-agent-package/v1",
            "site_key": "packaged.example",
            "source": package_source,
            "permissions": ["browser.read"],
            "tests": [{"name": "compile", "kind": "compile"}],
            "publisher_hint": {"untrusted": True},
        },
    }
    bundle = SimpleNamespace(
        kind=UnitKind.AGENT,
        key="example.packaged-reader",
        version="1.0.0",
        digest="sha256:" + "a" * 64,
        manifest=manifest,
        files=(),
        sbom={"spdxVersion": "SPDX-2.3"},
        signature={},
        attestation={},
        archive_path=tmp_path / "packaged.ai2agent",
    )
    record = runtime.extension_repository.record_package(
        bundle, str(tmp_path / "store"), {"signature": "verified"}
    )
    runtime.extension_repository.activate_package(record)

    candidates = client.get(
        "/v1/platform/site-agent-packages",
        params={"url": "https://packaged.example/news", "capability": "web.packaged.read"},
    )
    assert candidates.status_code == 200
    assert candidates.json()["items"][0]["publisher_hint_trusted"] is False
    provisioned = client.post(
        "/v1/platform/site-agent-packages/example.packaged-reader/provision",
        json={
            "granted_permissions": ["browser.read"],
            "expected_digest": bundle.digest,
            "activate": True,
        },
    )
    assert provisioned.status_code == 201, provisioned.text
    assert provisioned.json()["publisher_hint_executed"] is False
    assert provisioned.json()["site_agent"]["active_generation_id"]

    unsafe_source = dict(package_source)
    unsafe_source["steps"] = [
        {"name": "bad", "operation": "inspect", "script": "fetch('/leak')"}
    ]
    unsafe_manifest = dict(manifest)
    unsafe_manifest["web_agent"] = {**manifest["web_agent"], "source": unsafe_source}
    try:
        validate_web_agent_package(unsafe_manifest)
    except ValueError as error:
        assert "forbidden script access" in str(error)
    else:
        raise AssertionError("unsafe Site Agent Package must be rejected")

    old_generation_id = provisioned.json()["site_agent"]["active_generation_id"]
    upgrade_manifest = {**manifest, "version": "1.1.0"}
    upgrade_bundle = SimpleNamespace(
        **{
            **bundle.__dict__,
            "version": "1.1.0",
            "digest": "sha256:" + "b" * 64,
            "manifest": upgrade_manifest,
        }
    )
    upgrade_record = runtime.extension_repository.record_package(
        upgrade_bundle, str(tmp_path / "store-v1.1"), {"signature": "verified"}
    )
    runtime.extension_repository.activate_package(upgrade_record)
    runtime.registry_packages = SimpleNamespace(
        install=AsyncMock(return_value=upgrade_record)
    )
    rejected_upgrade = client.post(
        "/v1/platform/site-agent-registry/example/packaged-reader/install",
        json={"granted_permissions": [], "version": "1.1.0", "activate": False},
    )
    assert rejected_upgrade.status_code == 409
    assert runtime.extension_repository.active_package(
        UnitKind.AGENT, "example.packaged-reader"
    ).digest == bundle.digest
    runtime.extension_manager.activate_version(
        UnitKind.AGENT, "example.packaged-reader", upgrade_bundle.digest
    )
    upgraded = client.post(
        "/v1/platform/site-agent-registry/example/packaged-reader/install",
        json={
            "granted_permissions": ["browser.read"],
            "version": "1.1.0",
            "activate": False,
        },
    )
    assert upgraded.status_code == 201, upgraded.text
    assert upgraded.json()["binding"]["package_digest"] == upgrade_bundle.digest
    assert upgraded.json()["binding"]["status"] == "installed"
    assert upgraded.json()["site_agent"]["active_generation_id"] == old_generation_id

    lifecycle = client.get(
        "/v1/platform/site-agent-packages/example.packaged-reader/lifecycle"
    )
    assert lifecycle.status_code == 200, lifecycle.text
    assert lifecycle.json()["active_binding"]["package_version"] == "1.0.0"
    assert {item["version"] for item in lifecycle.json()["versions"]} == {"1.0.0", "1.1.0"}

    pinned = client.post(
        "/v1/platform/site-agent-packages/example.packaged-reader/policy",
        json={"update_policy": "pinned", "pinned_version": "1.0.0"},
    )
    assert pinned.status_code == 200, pinned.text
    blocked_upgrade = client.post(
        "/v1/platform/site-agent-packages/example.packaged-reader/activate",
        json={"package_digest": upgrade_bundle.digest},
    )
    assert blocked_upgrade.status_code == 409
    assert client.post(
        "/v1/platform/site-agent-packages/example.packaged-reader/policy",
        json={"update_policy": "manual"},
    ).status_code == 200
    activated_upgrade = client.post(
        "/v1/platform/site-agent-packages/example.packaged-reader/activate",
        json={"package_digest": upgrade_bundle.digest},
    )
    assert activated_upgrade.status_code == 200, activated_upgrade.text
    assert activated_upgrade.json()["binding"]["package_version"] == "1.1.0"
    rolled_back = client.post(
        "/v1/platform/site-agent-packages/example.packaged-reader/rollback",
        json={"package_digest": bundle.digest},
    )
    assert rolled_back.status_code == 200, rolled_back.text
    assert rolled_back.json()["binding"]["package_version"] == "1.0.0"
    lifecycle = client.get(
        "/v1/platform/site-agent-packages/example.packaged-reader/lifecycle"
    ).json()
    assert [item["action"] for item in lifecycle["events"]][:2] == [
        "rolled_back", "activated"
    ]


def test_p4_discovery_sends_exact_site_capability_and_schema_query(tmp_path):
    runtime, client = _client(tmp_path)
    search = AsyncMock(return_value={"items": [{"packageId": "example/site-reader"}]})
    runtime.registry_packages = SimpleNamespace(search=search)

    response = client.get(
        "/v1/platform/site-agent-discovery",
        params={
            "url": "https://www.example.com/news/latest?ignored=yes",
            "capability": "web.article_feed",
            "output_schema": "ArticleList/v1",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["query"] == {
        "url": "https://www.example.com/news/latest?ignored=yes",
        "origin": "https://www.example.com",
        "path": "/news/latest",
        "capability": "web.article_feed",
        "output_schema": "ArticleList/v1",
    }
    assert response.json()["implicit_ai"] is False
    assert search.await_args.kwargs == {
        "q": "example.com web.article_feed ArticleList/v1",
        "type": "agent",
        "agent_kind": "site-agent",
        "origin": "https://www.example.com",
        "path": "/news/latest",
        "capability": "web.article_feed",
        "output_schema": "ArticleList/v1",
        "sort": "relevance",
        "limit": 20,
    }


def test_p3_health_incremental_state_circuit_repair_and_dependency(tmp_path):
    runtime, client = _client(tmp_path)
    draft, _generation = _active_agent(client)

    def finish(result=None, error=None):
        response = client.post(
            "/v1/platform/agent-capabilities/web.page.read/invoke",
            headers={"X-AI2Apps-App-ID": "ai2apps.news"},
            json={
                "input": {"limit": 5},
                "browser_context": {"url": "https://example.com/news"},
            },
        )
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]
        runtime.agents.transition(
            run_id, expected={AgentRunStatus.QUEUED}, status=AgentRunStatus.PLANNING
        )
        runtime.agents.transition(
            run_id, expected={AgentRunStatus.PLANNING}, status=AgentRunStatus.RUNNING
        )
        runtime.agents.transition(
            run_id,
            expected={AgentRunStatus.RUNNING},
            status=AgentRunStatus.COMPLETED if error is None else AgentRunStatus.FAILED,
            output=None if error is not None else {"result": result or {}},
            error=error,
        )
        runtime._handle_site_agent_terminal(run_id)
        return run_id

    finish({"items": [{"url": "https://example.com/a", "title": "A"}]})
    finish({
        "items": [
            {"url": "https://example.com/a", "title": "A"},
            {"url": "https://example.com/b", "title": "B"},
        ]
    })
    health = client.get("/v1/platform/agent-health").json()["items"][0]
    assert health["status"] == "healthy"
    assert health["metrics"]["last_diff"]["new"] == ["https://example.com/b"]
    state = client.get(
        f"/v1/platform/agent-drafts/{draft['id']}/site-state"
    ).json()["items"][0]
    assert state["calibration_status"] == "passed"

    for _ in range(3):
        finish(error={"code": "selector_not_found", "message": "DOM changed"})
    health = client.get("/v1/platform/agent-health").json()["items"][0]
    assert health["status"] == "drifted"
    blocked = client.post(
        "/v1/platform/agent-capabilities/web.page.read/invoke",
        json={"browser_context": {"url": "https://example.com/news"}},
    )
    assert blocked.status_code == 409

    model_repair = client.post(
        f"/v1/platform/agent-drafts/{draft['id']}/repairs/model",
        json={
            "capability_name": "web.page.read",
            "strategy": "lightweight",
            "max_model_tokens": 2000,
            "evidence": {
                "error_code": "selector_not_found",
                "failed_steps": ["inspect"],
                "page_content": "must not be forwarded",
            },
        },
    )
    assert model_repair.status_code == 202, model_repair.text
    repair_run = runtime.agents.get_run(model_repair.json()["run_id"])
    assert repair_run.input["repair_request"]["evidence"] == {
        "error_code": "selector_not_found",
        "failed_steps": ["inspect"],
    }
    assert "must not be forwarded" not in repair_run.input["prompt"]

    repair = client.post(
        f"/v1/platform/agent-drafts/{draft['id']}/repairs",
        json={
            "capability_name": "web.page.read",
            "strategy": "advanced",
            "source": _source("Repaired Reader", "web.page.read"),
        },
    )
    assert repair.status_code == 201, repair.text
    activated = client.post(
        f"/v1/platform/agent-repairs/{repair.json()['id']}/activate"
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "activated"

    dependency = client.post(
        "/v1/platform/agent-app-dependencies",
        json={
            "consumer_app_id": "ai2apps.news",
            "capability_name": "web.page.read",
            "site_scope": "https://example.com/*",
            "provider_draft_id": draft["id"],
        },
    )
    assert dependency.status_code == 201
    assert client.get("/v1/platform/agent-app-dependencies").json()["items"]
