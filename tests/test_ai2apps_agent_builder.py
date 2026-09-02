from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.agent_builder import compile_source
from ai2apps.agent_builder.sites import canonical_site_key, normalize_site_agent_source
from ai2apps.agents import browser_builder_executor
from ai2apps.agents.models import (
    CompleteAction,
    InteractionAction,
    InteractionStatus,
    ModelCallAction,
)
from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime


def _source():
    return {
        "schema": "ai2apps.web-agent-source/v1",
        "name": "Fratello latest",
        "site_scope": ["https://www.fratellowatches.com/**"],
        "steps": [
            {
                "name": "step-1",
                "desc": "检查并关闭可以安全关闭的 Cookie 页面遮挡，成功转 step-2",
            },
            {
                "name": "step-2",
                "desc": "提取页面里的所有文章标题和链接，成功转 step-3，如果失败转 failed",
            },
            {
                "name": "step-3",
                "desc": "读取当前页面并完成",
                "operation": "complete",
            },
        ],
    }


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.agent_builder is not None
    return runtime


def _principal(user_id: str):
    return RequestPrincipal(
        actor_user_id=user_id,
        installation_id="installation-agent-builder",
        organization_id="organization-agent-builder",
        billing_account_id="billing-agent-builder",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )


def _client(runtime, principal):
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: principal,
        )
    )
    return TestClient(app)


def test_natural_language_source_compiles_to_strict_ir():
    result = compile_source(_source())

    assert result.valid is True
    assert [step["operation"] for step in result.ir["steps"]] == [
        "page_access",
        "extract_list",
        "complete",
    ]
    assert result.ir["steps"][0]["on"]["success"] == "step-2"
    assert result.ir["steps"][1]["on"]["failed"] == "failed"
    assert result.ir["effects"] == ["interact", "read"]
    assert result.source_digest.startswith("sha256:")


def test_compiler_accepts_string_execution_and_interaction_shorthand():
    source = _source()
    source["steps"][1].update({
        "execution": "compiled",
        "interaction": "precise",
    })

    result = compile_source(source)

    assert result.valid is True
    assert result.ir["steps"][1]["mode"] == "compiled"
    assert result.ir["steps"][1]["interaction"]["profile"] == "precise"


def test_compiler_rejects_unknown_transitions_and_ambiguous_steps():
    source = _source()
    source["steps"][0] = {
        "name": "step-1",
        "desc": "随便处理一下",
        "on": {"success": "missing-step"},
    }

    result = compile_source(source)

    assert result.valid is False
    assert {item["code"] for item in result.report["errors"]} >= {
        "operation_ambiguous"
    }


def test_compiler_rejects_open_without_an_absolute_url():
    source = {
        "agent_type": "web",
        "site_scope": ["https://example.com/**"],
        "steps": [{
            "name": "open",
            "operation": "open",
            "desc": "Open the site",
            "on": {"success": "done", "failed": "failed"},
        }],
    }

    result = compile_source(source)

    assert "open_url_required" in {
        item["code"] for item in result.report["errors"]
    }


def test_compiler_accepts_tiered_ai_steps_and_guards_destructive_steps():
    source = {
        "agent_type": "web",
        "site_scope": ["https://example.com/**"],
        "steps": [
            {
                "name": "classify",
                "operation": "ai.classify",
                "desc": "识别差评",
                "ai": {
                    "tier": "simple",
                    "instruction": "Return the negative review identifiers.",
                    "output_schema": {
                        "type": "object",
                        "properties": {"ids": {"type": "array"}},
                        "required": ["ids"],
                    },
                },
                "on": {"success": "confirm", "failed": "failed"},
            },
            {
                "name": "confirm",
                "operation": "approval",
                "desc": "确认删除识别到的差评",
                "on": {"success": "delete", "failed": "failed"},
            },
            {
                "name": "delete",
                "operation": "delete",
                "desc": "删除已确认的差评",
                "on": {"success": "done", "failed": "failed"},
            },
        ],
    }

    result = compile_source(source)

    assert result.valid is True
    assert result.ir["steps"][0]["ai"]["tier"] == "simple"
    assert result.ir["steps"][2]["effect"] == "destructive"

    source["steps"][1]["on"]["success"] = "done"
    invalid = compile_source(source)
    assert "destructive_step_requires_approval" in {
        item["code"] for item in invalid.report["errors"]
    }


def test_browser_builder_requests_configured_model_for_ai_step():
    source = {
        "agent_type": "web",
        "site_scope": ["https://example.com/**"],
        "steps": [
            {
                "name": "classify",
                "operation": "ai.classify",
                "desc": "识别差评",
                "ai": {
                    "tier": "complex",
                    "instruction": "Classify reviews.",
                    "output_schema": {"type": "object"},
                },
                "on": {"success": "done", "failed": "failed"},
            }
        ],
    }
    ir = compile_source(source).ir
    context = SimpleNamespace(
        definition=SimpleNamespace(max_steps=20),
        run=SimpleNamespace(
            input={"parameters": {
                "ir": ir,
                "ai_model_routes": {"complex": "complex-model"},
            }}
        ),
        interactions=(),
        step=lambda _key: None,
    )

    action = browser_builder_executor(context)

    assert isinstance(action, ModelCallAction)
    assert action.request["model"] == "complex-model"


def test_dry_run_stops_before_destructive_approval():
    source = {
        "agent_type": "web",
        "site_scope": ["https://example.com/**"],
        "steps": [
            {
                "name": "confirm",
                "operation": "approval",
                "desc": "确认删除评论",
                "on": {"success": "delete", "failed": "failed"},
            },
            {
                "name": "delete",
                "operation": "delete",
                "desc": "删除评论",
                "on": {"success": "done", "failed": "failed"},
            },
        ],
    }
    ir = compile_source(source).ir
    definition = SimpleNamespace(max_steps=20)
    preview = browser_builder_executor(SimpleNamespace(
        definition=definition,
        run=SimpleNamespace(input={"parameters": {"ir": ir, "preview": True}}),
        interactions=(),
    ))
    assert isinstance(preview, CompleteAction)
    assert preview.output["result"]["approval_required"] is True

    live = browser_builder_executor(SimpleNamespace(
        definition=definition,
        run=SimpleNamespace(input={"parameters": {"ir": ir, "preview": False}}),
        interactions=(),
    ))
    assert isinstance(live, InteractionAction)
    assert live.request["control"] == "agent_confirmation"


def test_site_agent_compiles_each_capability_as_a_separate_entrypoint():
    source = {
        "schema": "ai2apps.site-agent-source/v1",
        "agent_type": "web",
        "site_key": "fratellowatches.com",
        "name": "Fratello Site Agent",
        "site_scope": ["https://www.fratellowatches.com/**"],
        "capabilities": [
            {
                "id": "latest",
                "name": "fratello.latest",
                "title": "Latest articles",
                "steps": [{"name": "read", "operation": "extract_list", "desc": "提取文章列表"}],
            },
            {
                "id": "search",
                "name": "fratello.search",
                "title": "Search",
                "steps": [{"name": "open", "operation": "inspect", "desc": "找到搜索入口"}],
            },
        ],
    }

    result = compile_source(source)

    assert result.valid is True
    assert result.ir["schema"] == "ai2apps.compiled-site-agent/v1"
    assert [item["id"] for item in result.ir["capabilities"]] == ["latest", "search"]
    assert [item["name"] for item in result.ir["capability_exports"]] == [
        "fratello.latest", "fratello.search"
    ]


def test_site_identity_rejects_browser_internal_urls():
    assert canonical_site_key("about:blank") == ""
    assert canonical_site_key("chrome://browser/content") == ""
    assert canonical_site_key("https://www.Example.com/path") == "example.com"


def test_site_agent_normalization_removes_imported_placeholders_and_duplicates():
    capability = {
        "id": "read", "name": "example.read", "title": "Read articles",
        "description": "Read the current page",
        "steps": [{"name": "read", "operation": "extract_list"}],
        "provenance": {"legacy_draft_id": "draft-1"},
    }
    source = {
        "schema": "ai2apps.site-agent-source/v1",
        "capabilities": [
            {"id": "run", "name": "site.run", "title": "Run", "description": "",
             "steps": [], "provenance": {"legacy_draft_id": "draft-empty"}},
            {key: value for key, value in capability.items() if key != "provenance"},
            {**capability, "id": "read-2", "name": "site.read-2",
             "provenance": {"legacy_draft_id": "draft-2"}},
        ],
    }

    normalized = normalize_site_agent_source(source, site_key="example.com")

    assert [item["title"] for item in normalized["capabilities"]] == ["Read articles"]


def test_agent_draft_api_is_actor_scoped_and_activates_valid_generation(tmp_path):
    runtime = _runtime(tmp_path)
    owner = _client(runtime, _principal("agent-builder-owner"))
    stranger = _client(runtime, _principal("agent-builder-stranger"))

    created = owner.post(
        "/v1/platform/agent-drafts",
        json={
            "name": "Fratello latest",
            "site_scope": ["https://www.fratellowatches.com/**"],
            "source": _source(),
        },
    )
    assert created.status_code == 201
    draft = created.json()

    assert stranger.get(
        f"/v1/platform/agent-drafts/{draft['id']}"
    ).status_code == 404

    plan = owner.post(
        f"/v1/platform/agent-drafts/{draft['id']}/steps/step-2/plan"
    )
    assert plan.status_code == 200
    assert plan.json()["valid"] is True
    assert plan.json()["step"]["operation"] == "extract_list"

    compiled = owner.post(
        f"/v1/platform/agent-drafts/{draft['id']}/compile"
    )
    assert compiled.status_code == 200
    generation = compiled.json()
    assert generation["status"] == "validated"

    evidence = owner.post(
        f"/v1/platform/agent-drafts/{draft['id']}/steps/step-2/evidence",
        json={
            "outcome": "success",
            "generation_id": generation["id"],
            "page_fingerprint": "sha256:page",
            "evidence": {
                "item_count": 32,
                "target_semantics": {"role": "main"},
            },
            "user_feedback": "accepted",
        },
    )
    assert evidence.status_code == 201
    assert evidence.json()["outcome"] == "success"

    activated = owner.post(
        f"/v1/platform/agent-drafts/{draft['id']}/generations/"
        f"{generation['id']}/activate"
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert activated.json()["active_generation_id"] == generation["id"]

    run = owner.post(
        f"/v1/platform/agent-drafts/{draft['id']}/runs",
        json={
            "preview": False,
            "browser_context": {
                "bidi_context": "context-fratello",
                "url": "https://www.fratellowatches.com/archives/",
            },
        },
    )
    assert run.status_code == 202
    assert run.json()["draft_id"] == draft["id"]
    run_id = run.json()["id"]
    assert owner.get(f"/v1/platform/agent-draft-runs/{run_id}").status_code == 200
    assert stranger.get(
        f"/v1/platform/agent-draft-runs/{run_id}"
    ).status_code in {403, 404}


def test_browser_builder_executor_checkpoints_each_bidi_action():
    ir = compile_source(_source()).ir
    definition = SimpleNamespace(max_steps=20)
    run = SimpleNamespace(
        input={"parameters": {"draft_id": "adraft_test", "ir": ir}}
    )
    first_context = SimpleNamespace(
        definition=definition, run=run, interactions=()
    )

    first = browser_builder_executor(first_context)
    assert isinstance(first, InteractionAction)
    assert first.request["control"] == "browser_bidi_action"
    assert first.request["step_id"] == "step-1"

    submitted = SimpleNamespace(
        id="interaction-1",
        request=first.request,
        request_key=first.request_key,
        kind=first.kind,
        prompt=first.prompt,
        response_schema=first.response_schema,
        ui_hints=first.ui_hints,
        status=InteractionStatus.SUBMITTED,
        response={"outcome": "success", "evidence": {"dismissed": True}},
    )
    second = browser_builder_executor(
        SimpleNamespace(
            definition=definition, run=run, interactions=(submitted,)
        )
    )
    assert isinstance(second, InteractionAction)
    assert second.request["step_id"] == "step-2"

    submitted_second = SimpleNamespace(
        id="interaction-2",
        request=second.request,
        request_key=second.request_key,
        kind=second.kind,
        prompt=second.prompt,
        response_schema=second.response_schema,
        ui_hints=second.ui_hints,
        status=InteractionStatus.SUBMITTED,
        response={"outcome": "success", "evidence": {"items": [{"title": "A"}]}},
    )
    completed = browser_builder_executor(
        SimpleNamespace(
            definition=definition,
            run=run,
            interactions=(submitted, submitted_second),
        )
    )
    assert isinstance(completed, CompleteAction)
    assert completed.output["terminal"] == "done"
