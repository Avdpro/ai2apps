"""Local-only capability sharing management and data-plane boundaries."""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.router import create_ai2apps_router
from ai2apps.api.sharing import create_sharing_data_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.cloud_gateway import proxy_cloud_chat_completion
from ai2apps.model_manager import ModelManagerStore
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.sharing import CapabilityExport, CapabilityKind, LocalNetworkAccess, SharingError
from ai2apps.sharing.agent_connector import AGENT_OPERATIONS, agent_connector_tools, resolve_agent_connector
from ai2apps.sharing.network import LanAccessApp, LanAccessController


def _runtime(tmp_path):
    runtime = PlatformRuntime(
        PlatformConfig.from_base_path(tmp_path, secret_backend="encrypted-file")
    )
    runtime.start()
    assert runtime.sharing is not None
    return runtime


def _principal(role: MemberRole) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id="user-test",
        installation_id="installation-test",
        organization_id="organization-test",
        billing_account_id="billing-test",
        role=role,
        membership_epoch=1,
    )


def test_agent_cloud_connector_exports_all_session_operations(tmp_path):
    now = datetime.now(UTC)
    export = CapabilityExport(
        id="exp-agent", kind=CapabilityKind.AGENT, target_id="general",
        display_name="General Agent", protocols=("mcp",), status="active",
        created_by_user_id="owner", revision=1, created_at=now, updated_at=now,
    )
    tools = agent_connector_tools(export)
    assert {tool["name"].rsplit(".", 1)[-1] for tool in tools} == set(AGENT_OPERATIONS)
    selected, operation = resolve_agent_connector((export,), "agent.general.cancel")
    assert selected == export
    assert operation == "cancel"


def test_share_token_is_one_time_and_revoke_is_immediate(tmp_path):
    runtime = _runtime(tmp_path)
    export = runtime.sharing.create_export(
        kind=CapabilityKind.TOOL,
        target_id="system.echo",
        display_name="Echo",
        created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="Kitchen client",
        export_ids=(export.id,),
        max_concurrency=1,
        expires_in_seconds=3600,
        created_by_user_id="owner",
    )

    assert runtime.sharing.authenticate(issued.grant.id, issued.token).id == issued.grant.id
    with runtime.database.transaction() as connection:
        row = connection.execute(
            "SELECT token_digest FROM capability_share_grants WHERE id=?",
            (issued.grant.id,),
        ).fetchone()
        assert row["token_digest"] != issued.token

    rotated = runtime.sharing.rotate_grant(issued.grant.id)
    try:
        runtime.sharing.authenticate(issued.grant.id, issued.token)
        raise AssertionError("old token remained valid")
    except SharingError as error:
        assert error.code == "invalid_share_token"
    runtime.sharing.revoke_grant(issued.grant.id)
    try:
        runtime.sharing.authenticate(issued.grant.id, rotated.token)
        raise AssertionError("revoked token remained valid")
    except SharingError as error:
        assert error.code == "share_revoked"


def test_member_cannot_manage_sharing(tmp_path):
    runtime = _runtime(tmp_path)
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: _principal(MemberRole.MEMBER),
        )
    )
    response = TestClient(app).get("/v1/platform/sharing/exports")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "core_account_required"


def test_core_management_api_wires_grant_request_budget(tmp_path):
    runtime = _runtime(tmp_path)
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: _principal(MemberRole.CORE),
        )
    )
    client = TestClient(app)
    exported = client.post(
        "/v1/platform/sharing/exports",
        json={"kind": "tool", "target_id": "system.echo", "display_name": "Echo"},
    )
    assert exported.status_code == 200
    issued = client.post(
        "/v1/platform/sharing/grants",
        json={
            "label": "Budgeted API client",
            "export_ids": [exported.json()["id"]],
            "max_concurrency": 1,
            "max_requests": 3,
        },
    )
    assert issued.status_code == 200
    assert issued.json()["grant"]["max_requests"] == 3


async def test_share_grant_request_budget_is_enforced_atomically(tmp_path):
    runtime = _runtime(tmp_path)
    export = runtime.sharing.create_export(
        kind=CapabilityKind.TOOL, target_id="system.echo",
        display_name="Echo", created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="Budgeted client", export_ids=(export.id,), max_concurrency=2,
        expires_in_seconds=None, created_by_user_id="owner", max_requests=1,
    )
    async with runtime.sharing.acquire(issued.grant):
        pass
    with pytest.raises(SharingError) as raised:
        runtime.sharing.authenticate(issued.grant.id, issued.token)
    assert raised.value.code == "share_request_limit"
    assert runtime.sharing.list_grants()[0].request_count == 1


def test_mcp_only_lists_and_calls_tools_in_grant(tmp_path):
    runtime = _runtime(tmp_path)
    export = runtime.sharing.create_export(
        kind=CapabilityKind.TOOL,
        target_id="system.echo",
        display_name="Echo",
        created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="MCP client",
        export_ids=(export.id,),
        max_concurrency=2,
        expires_in_seconds=None,
        created_by_user_id="owner",
    )
    app = FastAPI()
    app.include_router(create_sharing_data_router(lambda: runtime))
    client = TestClient(app)
    url = f"/v1/share/{issued.grant.id}/mcp"
    headers = {"Authorization": f"Bearer {issued.token}"}

    listed = client.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()["result"]["tools"]] == ["system.echo"]
    called = client.post(
        url,
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "system.echo", "arguments": {"value": "LAN"}}},
    )
    assert called.json()["result"]["structuredContent"] == {"value": "LAN"}
    assert client.post(url, json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"}).status_code == 401


def test_service_export_projects_only_its_safe_mcp_methods(tmp_path):
    runtime = _runtime(tmp_path)
    export = runtime.sharing.create_export(
        kind=CapabilityKind.SERVICE,
        target_id="ai2apps.diagnostics",
        display_name="Diagnostics Service",
        created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="Service client", export_ids=(export.id,), max_concurrency=1,
        expires_in_seconds=None, created_by_user_id="owner",
    )
    app = FastAPI()
    app.include_router(create_sharing_data_router(lambda: runtime))
    client = TestClient(app)
    url = f"/v1/share/{issued.grant.id}/mcp"
    headers = {"Authorization": f"Bearer {issued.token}"}
    listed = client.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert [item["name"] for item in listed.json()["result"]["tools"]] == ["system.echo"]
    called = client.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "system.echo", "arguments": {"value": "service-ok"}},
    })
    assert called.json()["result"]["structuredContent"] == {"value": "service-ok"}


def test_agents_are_private_by_default_and_core_export_enables_isolated_mcp_sessions(tmp_path):
    runtime = _runtime(tmp_path)
    tool_export = runtime.sharing.create_export(
        kind=CapabilityKind.TOOL, target_id="system.echo",
        display_name="Echo", created_by_user_id="owner",
    )
    private_grant = runtime.sharing.create_grant(
        label="No Agents", export_ids=(tool_export.id,), max_concurrency=2,
        expires_in_seconds=None, created_by_user_id="owner",
    )
    app = FastAPI()
    app.include_router(create_sharing_data_router(lambda: runtime))
    client = TestClient(app)
    private_url = f"/v1/share/{private_grant.grant.id}/mcp"
    private_headers = {"Authorization": f"Bearer {private_grant.token}"}
    private_tools = client.post(private_url, headers=private_headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]
    assert not any(item["name"].startswith("agent.") for item in private_tools)

    agent_export = runtime.sharing.create_export(
        kind=CapabilityKind.AGENT, target_id="ai2apps.general-agent",
        display_name="General Agent", created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="Agent client", export_ids=(agent_export.id,), max_concurrency=2,
        expires_in_seconds=None, created_by_user_id="owner",
    )
    other = runtime.sharing.create_grant(
        label="Other Agent client", export_ids=(agent_export.id,), max_concurrency=2,
        expires_in_seconds=None, created_by_user_id="owner",
    )
    url = f"/v1/share/{issued.grant.id}/mcp"
    headers = {"Authorization": f"Bearer {issued.token}"}
    prefix = "agent.ai2apps.general-agent"
    tools = client.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()["result"]["tools"]
    assert {item["name"] for item in tools} == {
        f"{prefix}.create_session", f"{prefix}.send_message",
        f"{prefix}.get_status", f"{prefix}.get_messages",
        f"{prefix}.cancel", f"{prefix}.close_session",
    }
    created = client.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": f"{prefix}.create_session", "arguments": {"title": "Isolated"}},
    }).json()["result"]["structuredContent"]
    sent = client.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": f"{prefix}.send_message", "arguments": {"session_id": created["session_id"], "prompt": "Reply OK"}},
    }).json()["result"]["structuredContent"]
    assert sent["status"] == "queued"
    status = client.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": f"{prefix}.get_status", "arguments": {"session_id": created["session_id"], "run_id": sent["run_id"]}},
    }).json()["result"]["structuredContent"]
    assert status["run_id"] == sent["run_id"]

    other_url = f"/v1/share/{other.grant.id}/mcp"
    other_headers = {"Authorization": f"Bearer {other.token}"}
    crossed = client.post(other_url, headers=other_headers, json={
        "jsonrpc": "2.0", "id": 6, "method": "tools/call",
        "params": {"name": f"{prefix}.get_status", "arguments": {"session_id": created["session_id"], "run_id": sent["run_id"]}},
    }).json()["result"]
    assert crossed["isError"] is True
    assert "not found" in crossed["content"][0]["text"].lower()

    closed = client.post(url, headers=headers, json={
        "jsonrpc": "2.0", "id": 7, "method": "tools/call",
        "params": {"name": f"{prefix}.close_session", "arguments": {"session_id": created["session_id"]}},
    }).json()["result"]["structuredContent"]
    assert closed["status"] == "deleted"
    with runtime.database.transaction() as connection:
        assert connection.execute(
            "SELECT status FROM agent_runs WHERE id=?", (sent["run_id"],)
        ).fetchone()["status"] == "cancelled"

    second = runtime.sharing.create_agent_session(issued.grant, "ai2apps.general-agent")
    second_run = runtime.sharing.send_agent_message(
        issued.grant, "ai2apps.general-agent", second["session_id"], prompt="Wait"
    )
    runtime.sharing.revoke_grant(issued.grant.id)
    with runtime.database.transaction() as connection:
        session_status = connection.execute(
            "SELECT status FROM sessions WHERE id=?", (second["session_id"],)
        ).fetchone()["status"]
        run_status = connection.execute(
            "SELECT status FROM agent_runs WHERE id=?", (second_run["run_id"],)
        ).fetchone()["status"]
    assert session_status == "deleted"
    assert run_status == "cancelled"


def test_openai_data_plane_filters_models_and_rejects_unshared_model(tmp_path):
    runtime = _runtime(tmp_path)
    export = runtime.sharing.create_export(
        kind=CapabilityKind.MODEL,
        target_id="local-model",
        display_name="Local Model",
        created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="OpenAI client",
        export_ids=(export.id,),
        max_concurrency=1,
        expires_in_seconds=None,
        created_by_user_id="owner",
    )

    async def list_models(_grant):
        return {"object": "list", "data": [{"id": "local-model"}, {"id": "private-model"}]}

    async def chat(payload, _request, _grant):
        return {"id": "chatcmpl-test", "model": payload["model"]}

    app = FastAPI()
    app.include_router(
        create_sharing_data_router(
            lambda: runtime,
            model_list_handler=list_models,
            model_chat_handler=chat,
        )
    )
    client = TestClient(app)
    base = f"/v1/share/{issued.grant.id}"
    headers = {"Authorization": f"Bearer {issued.token}"}
    assert client.get(f"{base}/models", headers=headers).json()["data"] == [{"id": "local-model"}]
    assert client.post(f"{base}/chat/completions", headers=headers, json={"model": "local-model", "messages": []}).status_code == 200
    denied = client.post(f"{base}/chat/completions", headers=headers, json={"model": "private-model", "messages": []})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "capability_not_shared"


def test_cloud_and_upstream_models_cannot_be_reexported(tmp_path):
    runtime = _runtime(tmp_path)
    for model_id, code in (
        ("cloud/ai2apps/openai/model", "cloud_model_not_shareable"),
        ("cloud/openai/model", "cloud_model_not_shareable"),
        ("gateway/upg_test/model", "upstream_model_not_shareable"),
    ):
        with pytest.raises(SharingError) as raised:
            runtime.sharing.create_export(
                kind=CapabilityKind.MODEL,
                target_id=model_id,
                display_name="Nested gateway",
                created_by_user_id="owner",
            )
        assert raised.value.code == code


def test_local_byok_model_can_be_shared_without_exposing_provider_key(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud("openai", {
        "base_url": "https://provider.test/v1",
        "protocol": "openai",
        "models": ["gpt-byok"],
        "api_key": "sk-provider-secret",
    })
    store.set_cloud_model_enabled("openai", "gpt-byok", True)
    runtime = _runtime(tmp_path)
    model_id = "cloud/openai/gpt-byok"
    assert runtime.sharing.model_source(model_id) == "local_byok"
    export = runtime.sharing.create_export(
        kind=CapabilityKind.MODEL,
        target_id=model_id,
        display_name="Family OpenAI",
        created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="Family client", export_ids=(export.id,), max_concurrency=1,
        expires_in_seconds=3600, created_by_user_id="owner",
    )
    captured = {}

    def provider(request: httpx.Request):
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"id": "byok-ok", "choices": []})

    async def chat(payload, _request, _grant):
        request = type("ByokRequest", (), {
            "model": payload["model"], "stream": False,
            "model_dump": lambda self, **_kwargs: payload,
        })()
        return await proxy_cloud_chat_completion(
            request, base_path=tmp_path, transport=httpx.MockTransport(provider)
        )

    app = FastAPI()
    app.include_router(create_sharing_data_router(lambda: runtime, model_chat_handler=chat, model_list_handler=lambda _grant: {"data": [{"id": model_id}]}))
    response = TestClient(app).post(
        f"/v1/share/{issued.grant.id}/chat/completions",
        headers={"Authorization": f"Bearer {issued.token}"},
        json={"model": model_id, "messages": [{"role": "user", "content": "hello"}], "stream": False},
    )

    assert response.status_code == 200
    assert captured["authorization"] == "Bearer sk-provider-secret"
    assert "sk-provider-secret" not in response.text
    assert "sk-provider-secret" not in captured["body"]


def test_local_byok_provider_error_redacts_api_key_from_shared_client(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud("openai", {
        "base_url": "https://provider.test/v1", "models": ["gpt-byok"],
        "api_key": "sk-provider-secret",
    })
    store.set_cloud_model_enabled("openai", "gpt-byok", True)
    runtime = _runtime(tmp_path)
    model_id = "cloud/openai/gpt-byok"
    export = runtime.sharing.create_export(
        kind=CapabilityKind.MODEL, target_id=model_id,
        display_name="Family OpenAI", created_by_user_id="owner",
    )
    issued = runtime.sharing.create_grant(
        label="Family client", export_ids=(export.id,), max_concurrency=1,
        expires_in_seconds=None, created_by_user_id="owner",
    )

    async def chat(payload, _request, _grant):
        request = type("ByokRequest", (), {
            "model": payload["model"], "stream": False,
            "model_dump": lambda self, **_kwargs: payload,
        })()
        transport = httpx.MockTransport(lambda _request: httpx.Response(
            401, json={"error": {"message": "bad key sk-provider-secret"}}
        ))
        return await proxy_cloud_chat_completion(request, base_path=tmp_path, transport=transport)

    app = FastAPI()
    app.include_router(create_sharing_data_router(lambda: runtime, model_chat_handler=chat, model_list_handler=lambda _grant: {"data": [{"id": model_id}]}))
    response = TestClient(app, raise_server_exceptions=False).post(
        f"/v1/share/{issued.grant.id}/chat/completions",
        headers={"Authorization": f"Bearer {issued.token}"},
        json={"model": model_id, "messages": [], "stream": False},
    )
    assert response.status_code == 401
    assert "sk-provider-secret" not in response.text
    assert "[redacted]" in response.text


async def test_core_controls_persisted_lan_mode_and_runtime_apply(tmp_path):
    runtime = _runtime(tmp_path)
    applied = []

    async def apply(settings):
        applied.append(settings)

    runtime.sharing.bind_network_apply(apply)
    initial = runtime.sharing.network_access()
    assert initial.mode == "disabled"
    updated = await runtime.sharing.update_network_access(
        mode="share_only",
        bind_host="0.0.0.0",
        port=18011,
        expected_revision=initial.revision,
        updated_by_user_id="owner",
    )
    assert updated.mode == "share_only"
    assert updated.port == 18011
    assert applied == [updated]


async def test_lan_listener_failure_persists_disabled_mode(tmp_path):
    runtime = _runtime(tmp_path)

    async def fail(_settings):
        raise OSError("port is already in use")

    runtime.sharing.bind_network_apply(fail)
    initial = runtime.sharing.network_access()
    with pytest.raises(SharingError, match="port is already in use"):
        await runtime.sharing.update_network_access(
            mode="full",
            bind_host="0.0.0.0",
            port=18012,
            expected_revision=initial.revision,
            updated_by_user_id="owner",
        )
    assert runtime.sharing.network_access().mode == "disabled"


def test_lan_asgi_boundary_separates_share_only_and_full_access():
    state = {"mode": "share_only"}
    inner = FastAPI()

    @inner.get("/{path:path}")
    def echo(path: str):
        return {"path": path}

    def settings():
        return type("Settings", (), {"mode": state["mode"]})()
    client = TestClient(LanAccessApp(inner, settings))
    assert client.get("/v1/share/grant/models").status_code == 200
    assert client.get("/apps/ai2apps.account").status_code == 404
    state["mode"] = "full"
    assert client.get("/apps/ai2apps.account").status_code == 200
    state["mode"] = "disabled"
    assert client.get("/v1/share/grant/models").status_code == 404


async def test_dedicated_lan_listener_starts_and_stops():
    inner = FastAPI()

    @inner.get("/v1/share/ping")
    def ping():
        return {"ok": True}

    probe = socket.socket()
    try:
        probe.bind(("127.0.0.1", 0))
    except PermissionError:
        probe.close()
        pytest.skip("sandbox does not permit loopback listeners")
    port = probe.getsockname()[1]
    probe.close()
    now = datetime.now(UTC)
    settings = LocalNetworkAccess(
        mode="share_only",
        bind_host="127.0.0.1",
        port=port,
        revision=1,
        updated_by_user_id="owner",
        created_at=now,
        updated_at=now,
    )
    controller = LanAccessController(inner, lambda: settings)
    await controller.apply(settings)
    try:
        response = None
        async with httpx.AsyncClient(trust_env=False) as client:
            for _ in range(20):
                try:
                    response = await client.get(
                        f"http://127.0.0.1:{port}/v1/share/ping"
                    )
                    break
                except httpx.ConnectError:
                    await asyncio.sleep(0.01)
            assert response is not None
            assert response.json() == {"ok": True}
    finally:
        await controller.stop()
