"""Downstream management and discovery of explicitly shared upstream capabilities."""

from __future__ import annotations

import time
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.secrets import MemorySecretBackend
from ai2apps.storage import PlatformDatabase
from ai2apps.upstream import ParentProbe, UpstreamGatewayManager


def _principal(role: MemberRole) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id="user-test", installation_id="installation-test",
        organization_id="organization-test", billing_account_id="billing-test",
        role=role, membership_epoch=1,
    )


def _manager(tmp_path, *, local_node_id=None):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    backend = MemorySecretBackend()
    return UpstreamGatewayManager(database, backend, local_node_id=local_node_id), backend


def _set_online(manager, gateway_id: str, *model_ids: str) -> None:
    with manager.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE upstream_gateways SET health_status='online',capabilities_json=? WHERE id=?",
            (json.dumps({"models": [{"id": item} for item in model_ids], "tools": []}), gateway_id),
        )


def test_upstream_token_is_only_stored_in_secret_backend(tmp_path):
    manager, backend = _manager(tmp_path)
    item = manager.create(
        label="Upstairs gateway",
        openai_base_url="http://127.0.0.1:8011/v1/share/shr_123",
        mcp_url="http://127.0.0.1:8011/v1/share/shr_123/mcp",
        token="share-secret",
        created_by_user_id="owner",
    )

    assert item.health_status == "unknown"
    assert list(backend.values.values()) == ["share-secret"]
    with manager.database.transaction() as connection:
        serialized = " ".join(str(value) for value in connection.execute(
            "SELECT * FROM upstream_gateways WHERE id=?", (item.id,)
        ).fetchone())
    assert "share-secret" not in serialized

    manager.delete(item.id)
    assert backend.values == {}


def test_cloud_relay_rotated_credential_replaces_secret_and_reactivates(tmp_path):
    manager, backend = _manager(tmp_path)
    item = manager.create_cloud_relay(
        label="Cloud parent", cloud_base_url="https://coder.ai2apps.com",
        credential="link-test.old-secret", node_link_id="link-test",
        upstream_installation_id="installation-upstream",
        downstream_installation_id="installation-downstream",
        created_by_user_id="owner",
    )
    with manager.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE upstream_gateways SET status='disabled',health_status='offline' WHERE id=?",
            (item.id,),
        )

    updated = manager.replace_cloud_credential("link-test", "link-test.new-secret")

    assert updated.status == "active"
    assert updated.health_status == "unknown"
    assert manager._load_token(item.id) == "link-test.new-secret"
    assert "old-secret" not in str(backend.values)


def test_cloud_relay_rejects_credential_for_another_link(tmp_path):
    manager, _ = _manager(tmp_path)
    manager.create_cloud_relay(
        label="Cloud parent", cloud_base_url="https://coder.ai2apps.com",
        credential="link-test.secret", node_link_id="link-test",
        upstream_installation_id="installation-upstream",
        downstream_installation_id="installation-downstream",
        created_by_user_id="owner",
    )
    try:
        manager.replace_cloud_credential("link-test", "other-link.secret")
        raise AssertionError("mismatched credential was accepted")
    except Exception as error:
        assert getattr(error, "code", None) == "invalid_cloud_relay_credential"


async def test_probe_projects_models_and_tools_without_secret(monkeypatch, tmp_path):
    manager, _ = _manager(tmp_path)
    item = manager.create(
        label="NAS",
        openai_base_url="http://nas.local:8011/v1/share/shr_123",
        mcp_url="http://nas.local:8011/v1/share/shr_123/mcp",
        token="share-secret",
        created_by_user_id="owner",
    )

    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): return None
        def json(self): return self.payload

    class Client:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def get(self, *_args, **_kwargs):
            return Response({"data": [{"id": "local-model"}]})
        async def post(self, *_args, **_kwargs):
            return Response({"result": {"tools": [{"name": "system.echo", "description": "Echo", "inputSchema": {"type": "object"}}]}})

    monkeypatch.setattr("ai2apps.upstream.transport.httpx.AsyncClient", Client)
    probed = await manager.probe(item.id)

    assert probed.health_status == "online"
    assert probed.capabilities["models"] == [{"id": "local-model"}]
    assert probed.capabilities["tools"][0]["name"] == "system.echo"
    projected = manager.projected_models()
    assert projected[0]["id"] == f"gateway/{item.id}/local-model"
    resolved = manager.resolve_model(projected[0]["id"])
    assert resolved is not None
    assert resolved[1:] == ("local-model", "share-secret")
    activity = manager.list_activity(gateway_id=item.id)
    assert activity[0]["operation"] == "probe"
    assert activity[0]["status"] == "completed"
    assert "share-secret" not in str(activity)


async def test_probe_accepts_mcp_only_grant_without_models(monkeypatch, tmp_path):
    manager, _ = _manager(tmp_path)
    item = manager.create(
        label="MCP only",
        openai_base_url="http://nas.local:8011/v1/share/shr_123",
        mcp_url="http://nas.local:8011/v1/share/shr_123/mcp",
        token="share-secret",
        created_by_user_id="owner",
    )

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.payload = payload
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")
        def json(self): return self.payload

    class Client:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def get(self, *_args, **_kwargs):
            return Response(404, {"detail": {"code": "models_not_shared"}})
        async def post(self, *_args, **_kwargs):
            return Response(200, {"result": {"tools": [{"name": "agent.demo.create_session"}]}})

    monkeypatch.setattr("ai2apps.upstream.transport.httpx.AsyncClient", Client)
    probed = await manager.probe(item.id)

    assert probed.health_status == "online"
    assert probed.capabilities["models"] == []
    assert probed.capabilities["tools"] == [
        {"name": "agent.demo.create_session", "description": None, "inputSchema": {}}
    ]


def test_member_cannot_manage_upstream_gateways(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path, secret_backend="encrypted-file"))
    runtime.start()
    app = FastAPI()
    app.include_router(create_ai2apps_router(
        runtime_provider=lambda: runtime,
        principal_provider=lambda: _principal(MemberRole.MEMBER),
    ))
    response = TestClient(app).get("/v1/platform/upstreams")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "core_account_required"


def test_transport_failure_degrades_gateway_without_recording_payload(tmp_path):
    manager, _ = _manager(tmp_path)
    item = manager.create(
        label="NAS",
        openai_base_url="http://nas.local:8011/v1/share/shr_123",
        mcp_url="http://nas.local:8011/v1/share/shr_123/mcp",
        token="share-secret",
        created_by_user_id="owner",
    )

    manager.mark_unavailable(
        gateway_id=item.id,
        operation="model",
        capability_id="local-model",
        started_at=time.monotonic(),
        error_code="upstream_unavailable",
        message="connection refused",
    )

    assert manager.get(item.id).health_status == "offline"
    activity = manager.list_activity(gateway_id=item.id)
    assert activity[0]["status"] == "failed"
    assert activity[0]["error_code"] == "upstream_unavailable"
    assert "share-secret" not in str(activity)


def test_parent_identity_rejects_direct_and_transitive_cycles(tmp_path):
    manager, _ = _manager(tmp_path, local_node_id="node-local-1234")

    for remote_node_id, ancestors in (
        ("node-local-1234", ()),
        ("node-remote-123", ("node-local-1234",)),
    ):
        try:
            manager.create(
                label="Loop", openai_base_url="http://nas.local/v1/share/shr_loop",
                mcp_url="http://nas.local/v1/share/shr_loop/mcp", token="secret",
                created_by_user_id="owner", remote_node_id=remote_node_id,
                ancestor_node_ids=ancestors,
            )
        except Exception as error:
            assert getattr(error, "code", None) == "upstream_cycle_detected"
        else:
            raise AssertionError("A parent cycle must be rejected")


def test_default_parent_priority_and_parent_first_model_routing(tmp_path):
    manager, _ = _manager(tmp_path, local_node_id="node-local-1234")
    first = manager.create(
        label="First", openai_base_url="http://one.local/v1/share/shr_one",
        mcp_url="http://one.local/v1/share/shr_one/mcp", token="one",
        created_by_user_id="owner", remote_node_id="node-parent-one", priority=200,
    )
    second = manager.create(
        label="Second", openai_base_url="http://two.local/v1/share/shr_two",
        mcp_url="http://two.local/v1/share/shr_two/mcp", token="two",
        created_by_user_id="owner", remote_node_id="node-parent-two", priority=10,
    )
    assert first.is_default is True
    assert second.is_default is False
    _set_online(manager, first.id, "shared-model")
    _set_online(manager, second.id, "shared-model")
    manager.update_routing(
        model_policy="parent_first", expected_revision=1, updated_by_user_id="owner"
    )

    resolved = manager.resolve_model("shared-model")
    assert resolved is not None and resolved[0].id == first.id

    first = manager.get(first.id)
    manager.update(first.id, expected_revision=first.revision, status="disabled")
    resolved = manager.resolve_model("shared-model")
    assert resolved is not None and resolved[0].id == second.id
    assert manager.resolve_model("local-only-model") is None

    second = manager.get(second.id)
    manager.update(second.id, expected_revision=second.revision, is_default=True)
    states = manager.list()
    assert sum(item.is_default for item in states) == 1
    assert states[0].id == second.id


async def test_probe_rechecks_live_parent_ancestry(monkeypatch, tmp_path):
    manager, _ = _manager(tmp_path, local_node_id="node-local-1234")
    item = manager.create(
        label="Parent", openai_base_url="http://nas.local/v1/share/shr_parent",
        mcp_url="http://nas.local/v1/share/shr_parent/mcp", token="secret",
        created_by_user_id="owner", remote_node_id="node-parent-123",
    )

    class Response:
        status_code = 200
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): return None
        def json(self): return self.payload

    class Client:
        def __init__(self, **_kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return None
        async def get(self, *_args, **_kwargs): return Response({"data": []})
        async def post(self, _url, **kwargs):
            if kwargs["json"]["method"] == "initialize":
                return Response({"result": {"serverInfo": {
                    "nodeId": "node-parent-123", "ancestorNodeIds": ["node-local-1234"]
                }}})
            return Response({"result": {"tools": []}})

    monkeypatch.setattr("ai2apps.upstream.transport.httpx.AsyncClient", Client)
    probed = await manager.probe(item.id)
    assert probed.health_status == "offline"
    assert "cycle" in (probed.last_error or "").lower()


async def test_parent_transport_is_replaceable_without_changing_routing(tmp_path):
    calls = []

    class RelayTransport:
        async def probe(self, gateway, token):
            calls.append(("probe", gateway.id, token))
            return ParentProbe(
                models=({"id": "relay-model"},),
                tools=({"name": "relay.echo", "inputSchema": {"type": "object"}},),
                node_id="node-relay-parent",
                ancestor_node_ids=("node-root-parent",),
            )

        async def invoke_tool(self, gateway, token, name, arguments):
            calls.append(("tool", gateway.id, token, name, arguments))
            return {"result": {"structuredContent": {"echo": arguments}}}

        async def open_model(self, gateway, token, payload, *, stream):
            raise AssertionError("not used by this test")

    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    backend = MemorySecretBackend()
    manager = UpstreamGatewayManager(
        database, backend, local_node_id="node-local-1234", transport=RelayTransport()
    )
    item = manager.create(
        label="Cloud-relayed parent",
        openai_base_url="https://relay.invalid/v1/share/shr_parent",
        mcp_url="https://relay.invalid/v1/share/shr_parent/mcp",
        token="relay-credential", created_by_user_id="owner",
        remote_node_id="node-relay-parent",
    )

    probed = await manager.probe(item.id)
    assert probed.health_status == "online"
    assert probed.ancestor_node_ids == ("node-root-parent",)
    assert manager.projected_models()[0]["remote_id"] == "relay-model"
    result = await manager.invoke_tool(item.id, "relay.echo", {"value": "ok"})
    assert result == {"echo": {"value": "ok"}}
    assert [call[0] for call in calls] == ["probe", "tool"]
