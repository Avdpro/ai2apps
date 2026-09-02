# SPDX-License-Identifier: Apache-2.0
"""M3 Service Registry, adapters, and Tool Gateway contracts."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import SchemaError

from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PLATFORM_DATABASE_SCHEMA_VERSION, PlatformConfig
from ai2apps.core import ResourceConflictError
from ai2apps.identity import (
    IdentityRepository,
    MemberRole,
    OrganizationType,
    RequestPrincipal,
)
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import (
    MCPServiceAdapter,
    OmlxModelServiceAdapter,
    ServiceDependency,
    ServiceInstanceStatus,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolGatewayError,
    ToolInvocationStatus,
    ToolProviderError,
)


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.database is not None
    assert runtime.events is not None
    assert runtime.services is not None
    assert runtime.service_registry is not None
    assert runtime.tools is not None
    return runtime


def _client(runtime):
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    return TestClient(app)


def test_schema_v6_seeds_a_durable_echo_service_and_tool(tmp_path):
    runtime = _runtime(tmp_path)

    service = runtime.services.get_service("ai2apps.diagnostics")
    instance = runtime.services.get_instance_for_service(service.id)
    tool = runtime.services.get_tool("system.echo")

    assert service.runtime_mode is ServiceRuntimeMode.IN_PROCESS
    assert instance.status is ServiceInstanceStatus.RUNNING
    assert tool.service_id == service.id
    assert tool.effects == ()
    with runtime.database.connect() as connection:
        assert (
            connection.execute("PRAGMA user_version").fetchone()[0]
            == PLATFORM_DATABASE_SCHEMA_VERSION
        )


def test_new_service_provider_supersedes_stale_running_instance(tmp_path):
    runtime = _runtime(tmp_path)
    service = runtime.services.ensure_service(
        service_key="example.browser",
        package_id="example.browser",
        package_version="1.0.0",
        display_name="Browser",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
    )
    old = runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="test:browser-old",
        status=ServiceInstanceStatus.RUNNING,
    )
    current = runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="test:browser-current",
        status=ServiceInstanceStatus.RUNNING,
    )

    assert runtime.services.get_instance_for_service(service.id).id == current.id
    with runtime.database.connect() as connection:
        stale = connection.execute(
            "SELECT status FROM service_instances WHERE id = ?", (old.id,)
        ).fetchone()
    assert stale[0] == "stopped"


def test_tool_context_derives_authoritative_actor_from_session(tmp_path):
    runtime = _runtime(tmp_path)
    identities = IdentityRepository(runtime.database)
    identities.bind_installation(
        installation_id="installation-1",
        cloud_device_id="device-1",
        organization_id="organization-1",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="user-core",
        billing_account_id="billing-core",
        access_epoch=1,
    )
    identities.upsert_membership(
        cloud_user_id="user-alice",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=3,
    )
    principal = identities.principal_for("user-alice")
    _, home, _ = runtime.extension_manager.launch_app(
        "ai2apps.general-chat", principal=principal
    )
    assert home is not None

    context = runtime.tools.context_for_session(
        caller_id="agent:test",
        session_id=home.id,
        trace_id="run-1",
    )

    assert context.actor_user_id == "user-alice"
    assert context.installation_id == "installation-1"
    assert context.organization_id == "organization-1"
    assert context.billing_account_id == "billing-core"
    assert context.membership_epoch == 3


def test_service_dependencies_are_persisted_and_restart_safe(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.services.ensure_service(
        service_key="example.consumer",
        package_id="example.consumer",
        package_version="1.0.0",
        display_name="Consumer",
        runtime_mode=ServiceRuntimeMode.EXTERNAL,
        dependencies=(
            ServiceDependency("ai2apps.model-runtime", ">=1", False),
            ServiceDependency("ai2apps.mcp", "*", True),
        ),
    )
    runtime.stop()

    restarted = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    restarted.start()
    service = restarted.services.get_service("example.consumer")

    assert [(item.service_key, item.optional) for item in service.dependencies] == [
        ("ai2apps.mcp", True),
        ("ai2apps.model-runtime", False),
    ]


def test_echo_api_discovery_invocation_validation_and_audit(tmp_path):
    runtime = _runtime(tmp_path)
    client = _client(runtime)

    services = client.get("/v1/platform/services")
    tools = client.get("/v1/platform/tools")
    invoked = client.post(
        "/v1/platform/tools/system.echo/invoke",
        json={"arguments": {"value": {"hello": "world"}}},
        headers={"x-trace-id": "trace-echo"},
    )
    invalid = client.post(
        "/v1/platform/tools/system.echo/invoke",
        json={"arguments": {}},
    )

    assert services.status_code == 200
    assert "ai2apps.diagnostics" in {
        item["service_key"] for item in services.json()["items"]
    }
    assert "ai2apps.agent-runtime" in {
        item["service_key"] for item in services.json()["items"]
    }
    assert "system.echo" in {item["qualified_name"] for item in tools.json()["items"]}
    assert invoked.status_code == 200
    assert invoked.json()["invocation_id"].startswith("tinv_")
    assert invoked.json()["output"] == {"value": {"hello": "world"}}
    assert invoked.json()["provider_key"] == "builtin:diagnostics"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_tool_input"
    event = runtime.events.latest_for_subject(
        invoked.json()["tool_id"],
        event_type="tool.invocation.completed",
    )
    assert event is not None
    assert event.trace_id == "trace-echo"
    invocation = client.get(
        f"/v1/platform/tool-invocations/{invoked.json()['invocation_id']}"
    )
    assert invocation.status_code == 200
    assert invocation.json()["status"] == "completed"
    assert invocation.json()["output"] == {"value": {"hello": "world"}}


def test_service_lifecycle_is_revisioned_and_controls_tool_visibility(tmp_path):
    runtime = _runtime(tmp_path)
    client = _client(runtime)
    service = client.get("/v1/platform/services/ai2apps.diagnostics").json()

    disabled = client.post(
        "/v1/platform/services/ai2apps.diagnostics/disable",
        json={"expected_revision": service["revision"]},
    )
    stale = client.post(
        "/v1/platform/services/ai2apps.diagnostics/enable",
        json={"expected_revision": service["revision"]},
    )
    hidden = client.get("/v1/platform/tools")
    blocked = client.post(
        "/v1/platform/tools/system.echo/invoke",
        json={"arguments": {"value": 1}},
    )
    enabled = client.post(
        "/v1/platform/services/ai2apps.diagnostics/enable",
        json={"expected_revision": disabled.json()["revision"]},
    )
    restarted = client.post("/v1/platform/services/ai2apps.diagnostics/restart")

    assert disabled.json()["status"] == "disabled"
    assert disabled.json()["instance"]["status"] == "disabled"
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "revision_conflict"
    assert "system.echo" not in {
        item["qualified_name"] for item in hidden.json()["items"]
    }
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "tool_disabled"
    assert enabled.json()["status"] == "enabled"
    assert restarted.json()["instance"]["status"] == "running"


@pytest.mark.asyncio
async def test_gateway_filters_capabilities_and_normalizes_timeout_and_errors(tmp_path):
    runtime = _runtime(tmp_path)
    service = runtime.services.ensure_service(
        service_key="example.secure",
        package_id="example.secure",
        package_version="1.0.0",
        display_name="Secure",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
    )
    instance = runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="local:secure",
        status=ServiceInstanceStatus.RUNNING,
    )
    runtime.services.ensure_tool(
        service_id=service.id,
        qualified_name="secure.wait",
        display_name="Wait",
        description="Test permission and timeout behavior.",
        input_schema={
            "type": "object",
            "properties": {"delay": {"type": "number", "minimum": 0}},
            "required": ["delay"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        required_capabilities=("secure.execute",),
        timeout_ms=20,
    )

    async def wait(arguments, _):
        await asyncio.sleep(arguments["delay"])
        return {"ok": True}

    runtime.service_registry.bind_tool(
        "secure.wait", provider_key=instance.provider_key, handler=wait
    )
    denied_context = ToolCallContext(caller_id="agent:test")
    allowed_context = ToolCallContext(
        caller_id="agent:test",
        granted_capabilities=frozenset({"secure.execute"}),
    )

    assert "secure.wait" not in {
        tool.qualified_name for tool in runtime.tools.list_tools(denied_context)
    }
    assert "secure.wait" in {
        tool.qualified_name for tool in runtime.tools.list_tools(allowed_context)
    }
    with pytest.raises(ToolGatewayError) as denied:
        await runtime.tools.execute("secure.wait", {"delay": 0}, context=denied_context)
    with pytest.raises(ToolGatewayError) as timed_out:
        await runtime.tools.execute(
            "secure.wait", {"delay": 0.1}, context=allowed_context
        )
    with pytest.raises(ToolGatewayError) as invalid:
        await runtime.tools.execute(
            "secure.wait", {"delay": -1}, context=allowed_context
        )

    assert denied.value.code == "capability_denied"
    assert timed_out.value.code == "tool_timeout"
    assert invalid.value.code == "invalid_tool_input"


@pytest.mark.asyncio
async def test_gateway_propagates_cancellation_and_records_it(tmp_path):
    runtime = _runtime(tmp_path)
    tool = runtime.services.get_tool("system.echo")

    async def never_finishes(arguments, context):
        await asyncio.Event().wait()
        return {"value": arguments["value"]}

    runtime.service_registry.bind_tool(
        "system.echo",
        provider_key="builtin:diagnostics",
        handler=never_finishes,
    )
    task = asyncio.create_task(
        runtime.tools.execute(
            "system.echo",
            {"value": "cancel"},
            context=ToolCallContext(caller_id="agent:test"),
        )
    )
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    event = runtime.events.latest_for_subject(
        tool.id,
        event_type="tool.invocation.cancelled",
    )
    assert event is not None
    assert event.payload["code"] == "tool_cancelled"
    invocation = runtime.services.list_invocations()[0]
    assert invocation.status is ToolInvocationStatus.CANCELLED
    assert invocation.error == {"code": "tool_cancelled"}


@pytest.mark.asyncio
async def test_gateway_persists_progress_and_explicit_bounded_retry(tmp_path):
    runtime = _runtime(tmp_path)
    service = runtime.services.ensure_service(
        service_key="example.retry",
        package_id="example.retry",
        package_version="1.0.0",
        display_name="Retry fixture",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
    )
    instance = runtime.services.ensure_instance(
        service_id=service.id,
        provider_key="local:retry",
        status=ServiceInstanceStatus.RUNNING,
    )
    runtime.services.ensure_tool(
        service_id=service.id,
        qualified_name="fixture.retry",
        display_name="Retry",
        description="Report progress and retry one declared provider failure.",
        input_schema={"type": "object", "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {"attempt": {"type": "integer"}},
            "required": ["attempt"],
        },
        retry_policy={
            "max_attempts": 2,
            "backoff_ms": 0,
            "retry_codes": ["provider_error"],
        },
    )
    attempts = 0
    observed_progress = []

    async def retry(_arguments, context):
        nonlocal attempts
        attempts += 1
        await context.report_progress(f"attempt {attempts}", progress=attempts / 2)
        if attempts == 1:
            raise ToolProviderError("transient fixture")
        return {"attempt": attempts}

    runtime.service_registry.bind_tool(
        "fixture.retry", provider_key=instance.provider_key, handler=retry
    )
    result = await runtime.tools.execute(
        "fixture.retry",
        {},
        context=ToolCallContext(
            caller_id="agent:test",
            trace_id="run_retry",
            progress_reporter=observed_progress.append,
        ),
    )
    invocation = runtime.services.get_invocation(result.invocation_id)
    events = runtime.events.list_after(subject_id=result.tool_id, limit=20)

    assert result.output == {"attempt": 2}
    assert invocation.status is ToolInvocationStatus.COMPLETED
    assert invocation.attempt == 2
    assert invocation.progress["text"] == "attempt 2"
    assert [item["text"] for item in observed_progress] == ["attempt 1", "attempt 2"]
    assert "tool.invocation.retrying" in [event.type for event in events]


def test_runtime_marks_unfinished_tool_invocation_interrupted(tmp_path):
    runtime = _runtime(tmp_path)
    tool = runtime.services.get_tool("system.echo")
    invocation = runtime.services.create_invocation(
        tool=tool,
        provider_key="builtin:diagnostics",
        caller_id="agent:restart-fixture",
        session_id=None,
        trace_id="run_interrupted",
        arguments={"value": "pending"},
        timeout_ms=5_000,
    )
    runtime.stop()

    restarted = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    restarted.start()
    recovered = restarted.services.get_invocation(invocation.id)

    assert recovered.status is ToolInvocationStatus.INTERRUPTED
    assert recovered.error == {"code": "runtime_restarted"}
    event = restarted.events.latest_for_subject(
        tool.id, event_type="tool.invocation.interrupted"
    )
    assert event.payload["invocation_id"] == invocation.id


class FakeEnginePool:
    def __init__(self):
        self.entry = SimpleNamespace(engine=None)
        self.loaded = []
        self.unloaded = []

    def get_status(self):
        return {"models": [{"id": "tiny", "loaded": self.entry.engine is not None}]}

    def get_entry(self, model_id):
        return self.entry if model_id == "tiny" else None

    async def get_engine(self, model_id):
        self.loaded.append(model_id)
        self.entry.engine = object()
        return self.entry.engine

    async def _unload_engine(self, model_id):
        self.unloaded.append(model_id)
        self.entry.engine = None


@pytest.mark.asyncio
async def test_model_runtime_adapter_invokes_the_existing_engine_pool(tmp_path):
    runtime = _runtime(tmp_path)
    pool = FakeEnginePool()
    OmlxModelServiceAdapter(lambda: pool).bind(
        runtime.services, runtime.service_registry
    )
    context = ToolCallContext(
        caller_id="system:test",
        granted_capabilities=frozenset({"model.manage"}),
    )

    status = await runtime.tools.execute("model.status", {}, context=context)
    loaded = await runtime.tools.execute(
        "model.load", {"model_id": "tiny"}, context=context
    )
    unloaded = await runtime.tools.execute(
        "model.unload", {"model_id": "tiny"}, context=context
    )

    assert status.output["models"][0]["id"] == "tiny"
    assert loaded.output == {"status": "ok", "model_id": "tiny"}
    assert unloaded.output == {"status": "ok", "model_id": "tiny"}
    assert pool.loaded == ["tiny"]
    assert pool.unloaded == ["tiny"]
    service = runtime.services.get_service("ai2apps.model-runtime")
    assert service.config["inference_contract"] == "openai-compatible"
    assert "/v1/chat/completions" in service.config["compatibility_endpoints"]


class FakeMCPManager:
    def __init__(self):
        self.calls = []

    def get_server_status(self):
        return [
            SimpleNamespace(to_dict=lambda: {"name": "files", "state": "connected"})
        ]

    def get_all_tools(self):
        return [
            SimpleNamespace(
                full_name="files__read",
                name="read",
                description="Read a test resource",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            )
        ]

    async def execute_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(
            is_error=False,
            error_message=None,
            content={"text": f"read:{arguments['path']}"},
        )


@pytest.mark.asyncio
async def test_mcp_adapter_discovers_and_invokes_existing_manager_tools(tmp_path):
    runtime = _runtime(tmp_path)
    manager = FakeMCPManager()
    MCPServiceAdapter(lambda: manager).bind(runtime.services, runtime.service_registry)

    result = await runtime.tools.execute(
        "mcp.files__read",
        {"path": "/sandbox/readme.txt"},
        context=ToolCallContext(caller_id="agent:test"),
    )

    assert result.output == {
        "content": {"text": "read:/sandbox/readme.txt"},
        "is_error": False,
    }
    assert manager.calls == [("files__read", {"path": "/sandbox/readme.txt"})]


def test_provider_identity_cannot_be_spoofed(tmp_path):
    runtime = _runtime(tmp_path)

    with pytest.raises(ToolGatewayError) as error:
        runtime.service_registry.bind_tool(
            "system.echo",
            provider_key="installed:malicious-provider",
            handler=lambda arguments, context: arguments,
        )

    assert error.value.code == "provider_identity_mismatch"


def test_invalid_schema_and_missing_service_are_rejected(tmp_path):
    runtime = _runtime(tmp_path)
    diagnostics = runtime.services.get_service("ai2apps.diagnostics")

    with pytest.raises(SchemaError, match="not valid"):
        runtime.services.ensure_tool(
            service_id=runtime.services.get_service("ai2apps.diagnostics").id,
            qualified_name="invalid.schema",
            display_name="Invalid",
            description="Invalid test schema",
            input_schema={"type": "definitely-not-a-json-type"},
            output_schema={"type": "object"},
        )
    with pytest.raises(ResourceConflictError):
        runtime.services.ensure_tool(
            service_id="svc_" + "f" * 32,
            qualified_name="missing.service",
            display_name="Missing",
            description="Missing Service test",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
    with pytest.raises(ValueError, match="allow_effect_replay"):
        runtime.services.ensure_tool(
            service_id=diagnostics.id,
            qualified_name="invalid.effect-retry",
            display_name="Unsafe retry",
            description="Effectful retries require an explicit declaration.",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            effects=("write",),
            retry_policy={
                "max_attempts": 2,
                "retry_codes": ["provider_error"],
            },
        )
