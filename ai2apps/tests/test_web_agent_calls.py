from dataclasses import dataclass
from types import SimpleNamespace
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agent_builder.calls import bind_values, resolve_calls
from ai2apps.agent_builder.login import login_capability, login_ir
from ai2apps.agents.browser_builder import browser_builder_executor
from ai2apps.agents.models import AgentExecutionContext, CompleteAction, InteractionAction, InteractionStatus, ModelCallAction, RunStepStatus
from ai2apps.core import ResourceConflictError


def test_embedded_server_agents_first_import_order():
    process = subprocess.run([sys.executable,"-c","import ai2apps.agents; import ai2apps.platform_runtime"],
        cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=30)
    assert process.returncode == 0, process.stderr


@dataclass(frozen=True)
class Run:
    input: dict


def source(steps, **extra):
    return {"agent_type":"web", "site_scope":["https://example.com/**"], "steps":steps, **extra}


def call(agent_id="child", capability="site.login", **params):
    return {"name":"login", "operation":"agent.call", "arguments":{
        "agent_id":agent_id,"capability":capability,"parameters":params},
        "on":{"success":"done","failed":"failed"}}


def context(ir, inputs=None, interactions=(), steps=()):
    return AgentExecutionContext(definition=SimpleNamespace(max_steps=100),
        run=Run({"parameters":{"ir":ir, "invocation_input":inputs or {},
            "browser_context":{"bidi_context":"tab-1","profile_id":"profile-1"},
            "ai_model_routes":{"standard":"configured-model"}}}),
        interactions=interactions, steps=steps)


def respond(action, response):
    return SimpleNamespace(id=action.request_key, request_key=action.request_key,
        request=action.request, status=InteractionStatus.SUBMITTED,response=response)


def model_result(action, result):
    return SimpleNamespace(action_key=action.call_id,status=RunStepStatus.COMPLETED,
        output={"choices":[{"message":{"content":json.dumps(result)}}]})


def test_compiler_requires_export_reference_and_rejects_injected_ir():
    assert compile_source(source([call()])).valid
    step = call(); step["arguments"]["ir"] = {}
    assert not compile_source(source([step])).valid
    step = call(); del step["arguments"]["capability"]
    assert not compile_source(source([step])).valid


def test_bindings_keep_files_and_encode_query():
    files = [{"asset_id":"asset-1","url":"https://example.com/a.png"}]
    assert bind_values("${input.attachments}", {"attachments":files}) == files
    assert bind_values("${steps.login.output.authenticated}", {}, {"login":{"output":{"authenticated":True}}}) is True
    assert bind_values({"url":"https://example.com?q=${input.query}"}, {"query":"a & b"})["url"].endswith("a%20%26%20b")
    with pytest.raises(ValueError): bind_values("${input.missing}", {})


def test_owned_resolution_snapshots_generation_and_rejects_cycles():
    child = compile_source(source([{"name":"read","operation":"inspect","on":{"success":"done"}}],
        capability_exports=[{"name":"site.login"}])).ir
    owners = []
    store = SimpleNamespace(
        get_draft=lambda agent_id, owner: (owners.append(owner) or SimpleNamespace(id=agent_id,
            active_generation_id="generation-1",owner_user_id=owner,agent_type=SimpleNamespace(value="web"))),
        get_generation=lambda gen, owner: SimpleNamespace(id=gen, ir=child))
    ir = resolve_calls(store,"user-1",compile_source(source([call()])).ir)
    assert owners == ["user-1"]
    assert ir["steps"][0]["call"]["generation_id"] == "generation-1"
    child["steps"][0]["description"] = "changed"
    assert ir["steps"][0]["call"]["ir"]["steps"][0]["description"] != "changed"
    child["steps"] = compile_source(source([call()])).ir["steps"]
    with pytest.raises(ResourceConflictError, match="cycle"):
        resolve_calls(store,"user-1",compile_source(source([call()])).ir)


def test_parent_replays_child_and_binds_output_without_repeating_browser_action():
    child = compile_source(source([{"name":"read","operation":"inspect","on":{"success":"done"}}])).ir
    parent = call(); parent["on"]["success"] = "compose"
    ir = compile_source(source([parent,{"name":"compose","operation":"input",
        "arguments":{"value":"${steps.login.output.text}"},"on":{"success":"done"}}])).ir
    ir["steps"][0]["call"] = {"agent_id":"child","generation_id":"v1","capability":"site.login","ir":child}
    action = browser_builder_executor(context(ir))
    assert isinstance(action, InteractionAction)
    assert action.request["step_id"] == "login@0/read"
    assert action.request["call_path"][0]["generation_id"] == "v1"
    assert action.request["site_scope"] == child["site_scope"]
    answered = respond(action, {"outcome":"success","evidence":{"result":{"text":"发布正文"}}})
    next_action = browser_builder_executor(context(ir, interactions=(answered,)))
    assert next_action.request["step_id"] == "compose"
    assert next_action.request["step"]["arguments"]["value"] == "发布正文"


def test_login_waits_then_reobserves_before_parent_continues():
    metadata = login_capability("https://example.com/post")
    ir = resolve_calls(None,"user",compile_source(source([call(metadata["agent_id"],metadata["name"])] )).ir)
    observed = browser_builder_executor(context(ir))
    observation = respond(observed, {"outcome":"success","evidence":{"result":{"page":{"text":"scan QR"}}}})
    classifier = browser_builder_executor(context(ir,interactions=(observation,)))
    assert isinstance(classifier, ModelCallAction)
    model = model_result(classifier, {"outcome":"needs_user","reason":"请扫码","target":"","context":""})
    pause = browser_builder_executor(context(ir,interactions=(observation,),steps=(model,)))
    assert pause.request["control"] == "browser_user_assistance"
    resumed = respond(pause, {"continued":True})
    fresh = browser_builder_executor(context(ir, interactions=(observation,resumed),steps=(model,)))
    assert fresh.request["step_id"].endswith("/observe")
    assert fresh.request_key != observed.request_key
    fresh_answer = respond(fresh,{"outcome":"success","evidence":{"result":{"page":{"text":"account composer"}}}})
    next_model = browser_builder_executor(context(ir,interactions=(observation,resumed,fresh_answer),steps=(model,)))
    assert next_model.call_id != classifier.call_id
    success = model_result(next_model, {"outcome":"success","reason":"composer authenticated","target":"","context":""})
    complete = browser_builder_executor(context(ir,interactions=(observation,resumed,fresh_answer),steps=(model,success)))
    assert isinstance(complete, CompleteAction)
    assert complete.output["result"]["outcome"] == "success"


def test_login_ai_selects_observed_entry_and_context():
    ir = login_ir(login_capability("https://example.com")["agent_id"])
    observe = browser_builder_executor(context(ir))
    observation = respond(observe,{"outcome":"success","evidence":{"result":{"page":{"text":"Login"}}}})
    classifier = browser_builder_executor(context(ir,interactions=(observation,)))
    result = model_result(classifier,{"outcome":"not_found","reason":"login entry visible","target":"e24","context":"tab-1"})
    click = browser_builder_executor(context(ir,interactions=(observation,),steps=(result,)))
    assert click.request["step"]["target"]["intent"] == "e24"
    assert click.request["step"]["browser_context"] == "tab-1"


def test_call_api_pins_login_frame_and_planner_receives_site_capabilities(tmp_path):
    from fastapi import FastAPI, Response
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.identity import MemberRole, RequestPrincipal

    principal = RequestPrincipal(actor_user_id="call-owner",installation_id="call-install",
        organization_id="call-org",billing_account_id="call-billing",role=MemberRole.MEMBER,membership_epoch=1)
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path)); runtime.start()
    app = FastAPI(); app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principal))
    client = TestClient(app)
    try:
        catalog = client.get('/v1/platform/agent-capabilities',params={"url":"https://example.com/post"}).json()
        login = next(item for item in catalog["items"] if item["name"] == "site.ensure-login")
        blank_catalog=client.get('/v1/platform/agent-capabilities',params={"url":"about:newtab"}).json()["items"]
        assert len(blank_catalog)==9 and all(x["agent_id"].startswith("builtin:web:") for x in blank_catalog)
        read=client.post('/v1/platform/agent-capabilities/web.read-page/invoke',json={"input":{"url":"https://example.com/article"},"browser_context":{"bidi_context":"tab-1","url":"about:newtab"}})
        assert read.status_code==202,read.text
        assert runtime.agents.get_run(read.json()["run_id"]).input["parameters"]["ir"]["steps"][0]["call"]["generation_id"]=="web-foundations/2"
        # This catalog test intentionally keeps both independent invocations alive.
        from ai2apps.browser.tasks import BrowserTaskRepository
        BrowserTaskRepository(runtime.database).configure(principal.actor_user_id, 4, 2)
        runtime.model_manager = SimpleNamespace(resolve_default_model=lambda purpose:"standard-model")
        request = {"agent_id":login["agent_id"],"capability":login["name"],
            "generation_id":login["generation_id"],"browser_context":{"bidi_context":"tab-1","url":"https://example.com/post"},
            "idempotency_key":"call-once"}
        created = client.post('/v1/platform/agent-calls/runs',json=request)
        assert created.status_code == 202, created.text
        receipt = created.json(); request["session_id"] = receipt["session_id"]
        assert client.post('/v1/platform/agent-calls/runs',json=request).json()["run_id"] == receipt["run_id"]
        run = runtime.agents.get_run(receipt["run_id"])
        assert run.input["parameters"]["browser_context"]["bidi_context"] == "tab-1"
        assert run.input["parameters"]["ir"]["steps"][0]["call"]["generation_id"] == login["generation_id"]
        act = {"decision":"act","reason":"Account needed to publish","step":call(login["agent_id"],login["name"])}
        invoke = AsyncMock(return_value=Response(content=json.dumps({"choices":[{"message":{"content":json.dumps(act)}}]}),media_type="application/json"))
        runtime.model_invocations = SimpleNamespace(model=lambda _:SimpleNamespace(id="standard-model",endpoints={"chat_completions":"/v1/chat/completions"}),
            context_for_actor=lambda *a,**kw:SimpleNamespace(),invoke_foreground_json=invoke)
        plan = client.post('/v1/platform/agent-explorations/next',json={"goal":"Publish a post", "page":{"url":"https://example.com/post"},
            "observation":{"context":"tab-1","controls":[{"name":"Login"}]}})
        assert plan.status_code == 200, plan.text
        assert plan.json()["compiled_step"]["operation"] == "agent.call"
        prompt = str(invoke.call_args.args[2])
        assert "web.clear-blockers" in prompt and "web.light-explore" in prompt and "Readability" in prompt
        assert "Public reading/search" in prompt and "site.ensure-login" in prompt
    finally:
        runtime.stop()


def test_call_api_reports_profile_capacity_instead_of_internal_error(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.identity import MemberRole, RequestPrincipal
    from ai2apps.browser.tasks import BrowserTaskRepository
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path)); runtime.start()
    principal = RequestPrincipal(actor_user_id="capacity-owner", installation_id="install",
        organization_id="org", billing_account_id="billing", role=MemberRole.MEMBER, membership_epoch=1)
    app = FastAPI(); app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime, principal_provider=lambda:principal))
    try:
        tasks = BrowserTaskRepository(runtime.database)
        tasks.reserve_external("capacity-owner", "default", "draft", "run", "", "Old trial", {}, {"bidi_context":"old-tab"})
        response = TestClient(app).post('/v1/platform/agent-calls/runs', json={
            "agent_id":"builtin:web:extract-list", "capability":"web.extract-list",
            "generation_id":"web-foundations/2", "input":{"limit":20},
            "browser_context":{"bidi_context":"new-tab", "profile_key":"default"}})
        assert response.status_code == 422, response.text
        assert "并发名额已满" in response.text
        assert "invalid_agent_invocation" in response.text
        assert len(tasks.list("capacity-owner")) == 1
    finally:
        runtime.stop()
