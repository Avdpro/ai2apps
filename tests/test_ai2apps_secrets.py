"""Secret Store value isolation, Tool scoping, injection, and redaction."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.identity import RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.secrets import (
    EncryptedFileSecretBackend,
    MemorySecretBackend,
    NamespacedSecretBackend,
    SecretBackendError,
    SecretRepository,
    select_secret_backend_name,
)
from ai2apps.services import ServiceRuntimeMode, ToolCallContext


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    backend = MemorySecretBackend()
    runtime.secrets = SecretRepository(runtime.database, runtime.events, backend)
    runtime.tools.bind_secret_resolver(runtime.secrets.inject_arguments)
    return runtime, backend


@pytest.mark.asyncio
async def test_secret_metadata_never_persists_value_and_tool_output_is_redacted(tmp_path):
    runtime, backend = _runtime(tmp_path)
    secret = runtime.secrets.create(
        name="demo", value="never-log-this", purpose="test",
        allowed_tools=("system.echo",),
    )
    assert secret.uri == f"secret://{secret.id}"
    assert backend.values[secret.id] == "never-log-this"

    with runtime.database.transaction() as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(secret_records)")
        }
        stored = connection.execute(
            "SELECT * FROM secret_records WHERE id = ?", (secret.id,)
        ).fetchone()
    assert "value" not in columns
    assert "never-log-this" not in str(tuple(stored))

    result = await runtime.tools.execute(
        "system.echo", {"value": secret.uri},
        context=ToolCallContext(caller_id="agent:test"),
    )
    assert result.output == {"value": "[secret]"}
    invocation = runtime.services.get_invocation(result.invocation_id)
    assert invocation.arguments == {"value": secret.uri}
    assert invocation.output == {"value": "[secret]"}
    event = runtime.events.latest_for_subject(
        secret.id, event_type="secret.injected"
    )
    assert event is not None
    assert event.payload == {"tool_name": "system.echo"}
    assert "never-log-this" not in str(event.payload)
    last_used_at, last_used_by = runtime.secrets.last_use(secret.id)
    assert last_used_at == event.occurred_at
    assert last_used_by == "system.echo"


def test_secret_get_and_replace_remain_metadata_safe(tmp_path):
    runtime, backend = _runtime(tmp_path)
    secret = runtime.secrets.create(
        name="replaceable",
        value="old-secret-value",
        purpose="rotation test",
        allowed_tools=("system.echo",),
    )

    assert runtime.secrets.get(secret.id).name == "replaceable"
    replaced = runtime.secrets.replace(secret.id, "new-secret-value")
    assert replaced.id == secret.id
    assert backend.values[secret.id] == "new-secret-value"

    with pytest.raises(ValueError, match="cannot appear in metadata"):
        runtime.secrets.replace(secret.id, "rotation test")


def test_secret_is_rejected_outside_allowed_tool_scope(tmp_path):
    runtime, _ = _runtime(tmp_path)
    secret = runtime.secrets.create(
        name="scoped", value="credential", allowed_tools=("browser.*",)
    )
    with pytest.raises(Exception, match="not allowed"):
        runtime.secrets.inject_arguments({"value": secret.uri}, "system.echo")
    denied = runtime.events.latest_for_subject(
        secret.id, event_type="secret.injection_denied"
    )
    assert denied is not None
    assert denied.payload == {"tool_name": "system.echo", "reason": "tool_scope"}


def test_installed_external_service_cannot_receive_secret_values(tmp_path):
    runtime, _ = _runtime(tmp_path)
    service = runtime.services.ensure_service(
        service_key="test.external",
        package_id="test.external",
        package_version="1.0.0",
        display_name="External test Service",
        runtime_mode=ServiceRuntimeMode.EXTERNAL,
        source="installed",
    )
    runtime.services.ensure_tool(
        service_id=service.id,
        qualified_name="test.external.send",
        display_name="Send",
        description="External Tool",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )
    secret = runtime.secrets.create(
        name="external-denied",
        value="do-not-disclose",
        allowed_tools=("test.external.send",),
    )

    with pytest.raises(Exception, match="external Services cannot receive"):
        runtime.secrets.inject_arguments(
            {"value": secret.uri}, "test.external.send"
        )
    denied = runtime.events.latest_for_subject(
        secret.id, event_type="secret.injection_denied"
    )
    assert denied is not None
    assert denied.payload["reason"] == "external_service"


def test_secret_value_cannot_be_persisted_through_metadata(tmp_path):
    runtime, _ = _runtime(tmp_path)
    with pytest.raises(ValueError, match="cannot appear in metadata"):
        runtime.secrets.create(
            name="provider",
            value="secret-value",
            allowed_tools=("system.echo",),
            metadata={"note": "copied secret-value by mistake"},
        )


@pytest.mark.asyncio
async def test_secret_api_returns_metadata_only(tmp_path):
    runtime, backend = _runtime(tmp_path)
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/platform/secrets", json={
            "name": "api", "value": "api-value",
            "purpose": "API test", "allowed_tools": ["system.echo"],
        })
        assert response.status_code == 201
        body = response.json()
        assert "value" not in body
        assert body["uri"].startswith("secret://sec_")
        listed = (await client.get("/v1/platform/secrets")).json()["items"]
        assert listed == [body]
        assert "api-value" not in str(body)
        assert body["last_used_at"] is None
        assert body["last_used_by_tool"] is None
        assert backend.values[body["id"]] == "api-value"
        provider = (await client.get("/v1/platform/secrets/backend")).json()
        assert provider == {"provider": "memory", "portable": False}


def test_platform_backend_selection_is_deterministic():
    assert select_secret_backend_name(system="Darwin", environ={}) == "macos-keychain"
    assert select_secret_backend_name(
        system="Linux", environ={}, executable_lookup=lambda _: "/usr/bin/secret-tool"
    ) == "encrypted-file"
    assert select_secret_backend_name(
        system="Linux",
        environ={"DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1/bus"},
        executable_lookup=lambda _: "/usr/bin/secret-tool",
    ) == "linux-secret-service"
    assert select_secret_backend_name(
        system="Darwin", environ={"AI2APPS_SECRET_BACKEND": "encrypted-file"}
    ) == "encrypted-file"


def test_namespaced_secret_backends_isolate_instances_and_migrate_safe_legacy():
    raw = MemorySecretBackend()
    instance_a = NamespacedSecretBackend(raw, "local_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    instance_b = NamespacedSecretBackend(raw, "local_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    instance_a.store("provider-openai", "key-a")
    instance_b.store("provider-openai", "key-b")

    assert instance_a.load("provider-openai") == "key-a"
    assert instance_b.load("provider-openai") == "key-b"
    assert raw.values[instance_a.scoped_key("provider-openai")] == "key-a"
    assert raw.values[instance_b.scoped_key("provider-openai")] == "key-b"

    raw.store("sec_legacy_owned_by_database", "legacy-value")
    assert instance_a.load("sec_legacy_owned_by_database") == "legacy-value"
    assert raw.values[instance_a.scoped_key("sec_legacy_owned_by_database")] == (
        "legacy-value"
    )
    instance_a.delete("sec_legacy_owned_by_database")
    with pytest.raises(KeyError):
        instance_a.load("sec_legacy_owned_by_database")


def test_namespaced_secret_backend_does_not_claim_ambiguous_cloud_session():
    raw = MemorySecretBackend()
    backend = NamespacedSecretBackend(
        raw, "local_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    raw.store("ai2apps-cloud-session-deadbeefdeadbeef", "other-instance-session")

    with pytest.raises(KeyError):
        backend.load("ai2apps-cloud-session-deadbeefdeadbeef")


def test_encrypted_file_backend_persists_ciphertext_and_rejects_wrong_key(tmp_path):
    directory = tmp_path / "secrets"
    backend = EncryptedFileSecretBackend(directory, key_material="correct-key")
    backend.store("sec_test", "not-plaintext")
    assert backend.load("sec_test") == "not-plaintext"
    assert b"not-plaintext" not in backend.vault_path.read_bytes()
    assert backend.vault_path.stat().st_mode & 0o777 == 0o600

    reopened = EncryptedFileSecretBackend(directory, key_material="correct-key")
    assert reopened.load("sec_test") == "not-plaintext"
    wrong = EncryptedFileSecretBackend(directory, key_material="wrong-key")
    with pytest.raises(SecretBackendError, match="locked or corrupted"):
        wrong.load("sec_test")


def test_runtime_can_explicitly_use_portable_vault(tmp_path):
    runtime = PlatformRuntime(
        PlatformConfig.from_base_path(tmp_path, secret_backend="encrypted-file")
    )
    runtime.start()
    assert runtime.secrets.backend.provider_name == "encrypted-file"
    assert runtime.model_manager.secret_backend is runtime.secrets.backend

    runtime.model_manager.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "provider-secret",
        },
    )
    assert "provider-secret" not in runtime.model_manager.cloud_path.read_text()
    assert b"provider-secret" not in runtime.secrets.backend.vault_path.read_bytes()
