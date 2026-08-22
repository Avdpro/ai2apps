# SPDX-License-Identifier: Apache-2.0
"""M9 installable Agent/App and local Patch stack acceptance tests."""

from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from dataclasses import replace

import httpx
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.core import ResourceNotFoundError
from ai2apps.extensions import (
    ExtensionError,
    InteractivePackageManager,
    PatchStatus,
    UnitKind,
)
from ai2apps.extensions.patching import canonical_digest
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.packages import PackageFile, TrustStatus, package_digest
from ai2apps.platform_runtime import PlatformRuntime


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()
    return runtime


def _principal(user_id: str, role: MemberRole) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id=user_id,
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-core",
        role=role,
        membership_epoch=1,
    )


def _publisher(runtime, private):
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    runtime.package_repository.upsert_publisher(
        publisher_key="example.publisher",
        display_name="Example",
        key_id="example.publisher:main",
        public_key=base64.b64encode(public).decode(),
        trust_status=TrustStatus.TRUSTED,
    )


def _write_bundle(directory, private, manifest, suffix, resources=None, device=None):
    name = {
        ".ai2agent": "agent.yaml",
        ".ai2app": "app.yaml",
        ".ai2patch": "patch.yaml",
    }[suffix]
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": manifest.get("id", "patch"),
        "dataLicense": "CC0-1.0",
    }
    immutable = {
        name: yaml.safe_dump(manifest, sort_keys=True).encode(),
        "META/sbom.spdx.json": json.dumps(sbom, sort_keys=True).encode(),
        **(resources or {}),
    }
    files = tuple(
        PackageFile(path, f"sha256:{hashlib.sha256(data).hexdigest()}", len(data))
        for path, data in immutable.items()
    )
    digest = package_digest(manifest, files)
    index = {
        "files": [
            {"path": item.path, "sha256": item.content_hash, "size": item.size_bytes}
            for item in files
        ]
    }
    if suffix == ".ai2patch":
        attestation_name = "attestations/device.json"
        signature_name = "signatures/device.sig"
        attestation = {"package_digest": digest, "device": True}
        signature = {
            "algorithm": "ed25519",
            "public_key": device.public_key,
            "signature": device.sign(digest),
        }
    else:
        attestation_name = "attestations/publisher.json"
        signature_name = "signatures/publisher.sig"
        attestation = {
            "package_digest": digest,
            "publisher_id": "example.publisher",
            "key_id": "example.publisher:main",
        }
        signature = {
            "algorithm": "ed25519",
            "key_id": "example.publisher:main",
            "signature": base64.b64encode(private.sign(digest.encode())).decode(),
        }
    path = (
        directory
        / f"{manifest.get('id', manifest.get('target', {}).get('id', 'patch'))}-{manifest['version']}{suffix}"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, data in immutable.items():
            archive.writestr(item, data)
        archive.writestr("META/files.json", json.dumps(index, sort_keys=True))
        archive.writestr(attestation_name, json.dumps(attestation, sort_keys=True))
        archive.writestr(signature_name, json.dumps(signature, sort_keys=True))
    return path, digest


def _agent(version="1.0.0", status=None):
    return {
        "schema": "ai2apps.agent/v1",
        "id": "example.writer",
        "name": "Writer",
        "version": version,
        "publisher": {"id": "example.publisher"},
        "executor": {"key": "builtin:diagnostic-agent"},
        "status": {
            "primary": status
            if status is not None
            else {"kind": "text", "text": "Writing…"}
        },
        "runtime": {"max_steps": 5, "timeout_seconds": 30},
    }


def _app(version="1.0.0", state_version=1, migrations=None):
    value = {
        "schema": "ai2apps.app/v1",
        "id": "example.notes",
        "name": "Notes",
        "version": version,
        "publisher": {"id": "example.publisher"},
        "instances": {"mode": "singleton", "scope": "system"},
        "entry": {"kind": "sandbox", "resource": "ui/entry.html"},
        "mini_entry": {
            "kind": "schema",
            "resource": "ui/mini.json",
            "placements": ["inline", "sidebar"],
        },
        "state": {"version": state_version, "defaults": {"title": "Untitled"}},
    }
    if migrations is not None:
        value["migrations"] = migrations
    return value


def test_runtime_registers_authoritative_builtin_app_catalog(tmp_path):
    runtime = _runtime(tmp_path)
    catalog = {item["app_key"]: item for item in runtime.extension_manager.list_apps()}

    assert {
        "ai2apps.dashboard",
        "ai2apps.account",
        "ai2apps.models",
        "ai2apps.agents",
        "ai2apps.trust-center",
        "ai2apps.general-chat",
        "ai2apps.settings",
        "ai2apps.logs",
        "ai2apps.benchmark",
    }.issubset(catalog)
    assert catalog["ai2apps.general-chat"]["running_count"] == 1
    assert catalog["ai2apps.dashboard"]["entry"] == {
        "kind": "host",
        "resource": "ai2apps:system/dashboard",
    }
    assert catalog["ai2apps.account"]["singleton_scope"] == "user"
    assert catalog["ai2apps.account"]["entry"] == {
        "kind": "host",
        "resource": "ai2apps:system/account",
    }

    zh_catalog = {
        item["app_key"]: item
        for item in runtime.extension_manager.list_apps(locale="zh-CN")
    }
    assert zh_catalog["ai2apps.account"]["display_name"] == "账户"
    assert zh_catalog["ai2apps.account"]["navigation"]["category"] == "系统"


def test_mobile_catalog_is_explicit_and_excludes_desktop_only_apps(tmp_path):
    runtime = _runtime(tmp_path)
    catalog = {
        item["app_key"]: item
        for item in runtime.extension_manager.list_mobile_apps()
    }

    assert set(catalog) == {
        "ai2apps.dashboard",
        "ai2apps.account",
        "ai2apps.agents",
        "ai2apps.general-chat",
        "ai2apps.trust-center",
    }
    assert catalog["ai2apps.general-chat"]["entry_source"] == "mobile_entry"
    assert catalog["ai2apps.general-chat"]["mobile_renderer"] == "host"
    assert "ai2apps.terminal" not in catalog
    assert "ai2apps.coder" not in catalog


def test_builtin_app_catalog_and_launch_are_filtered_by_role(tmp_path):
    runtime = _runtime(tmp_path)
    member = _principal("user-member", MemberRole.MEMBER)
    developer = _principal("user-developer", MemberRole.DEVELOPER)
    core = _principal("user-core", MemberRole.CORE)

    member_catalog = {
        item["app_key"]
        for item in runtime.extension_manager.list_apps(principal=member)
    }
    developer_catalog = {
        item["app_key"]
        for item in runtime.extension_manager.list_apps(principal=developer)
    }
    core_catalog = {
        item["app_key"]
        for item in runtime.extension_manager.list_apps(principal=core)
    }

    assert member_catalog == {"ai2apps.account", "ai2apps.general-chat"}
    assert "ai2apps.coder" in developer_catalog
    assert "ai2apps.agents" not in developer_catalog
    assert {
        "ai2apps.agents",
        "ai2apps.coder",
        "ai2apps.models",
        "ai2apps.terminal",
    }.issubset(core_catalog)

    with pytest.raises(ExtensionError) as denied:
        runtime.extension_manager.launch_app(
            "ai2apps.agents", principal=member
        )
    assert denied.value.code == "app_access_denied"


def test_user_app_instance_ownership_blocks_direct_id_access(tmp_path):
    runtime = _runtime(tmp_path)
    alice = _principal("user-alice", MemberRole.MEMBER)
    bob = _principal("user-bob", MemberRole.MEMBER)
    alice_chat, _, _ = runtime.extension_manager.launch_app(
        "ai2apps.general-chat", principal=alice
    )

    assert alice_chat.owner_user_id == "user-alice"
    assert runtime.extension_manager.instance_entry(
        alice_chat.id, principal=alice
    )["app_key"] == "ai2apps.general-chat"
    with pytest.raises(ResourceNotFoundError):
        runtime.extension_manager.instance_entry(alice_chat.id, principal=bob)
    with pytest.raises(ResourceNotFoundError):
        runtime.extension_manager.focus_instance(alice_chat.id, principal=bob)


def test_core_launch_claims_legacy_chat_instance(tmp_path):
    runtime = _runtime(tmp_path)
    legacy, _, _ = runtime.extension_manager.launch_app("ai2apps.general-chat")
    core = _principal("user-core", MemberRole.CORE)

    before = {
        item["app_key"]: item
        for item in runtime.extension_manager.list_apps(principal=core)
    }
    assert before["ai2apps.general-chat"]["running_count"] == 0

    claimed, _, created = runtime.extension_manager.launch_app(
        "ai2apps.general-chat", principal=core
    )

    assert created is False
    assert claimed.id == legacy.id
    assert claimed.owner_user_id == "user-core"
    assert claimed.singleton_key == "ai2apps.general-chat:user:user-core"
    after = {
        item["app_key"]: item
        for item in runtime.extension_manager.list_apps(principal=core)
    }
    assert [item["id"] for item in after["ai2apps.general-chat"]["instances"]] == [
        claimed.id
    ]


def test_mobile_chat_mount_uses_exact_client_scoped_principal(tmp_path):
    runtime = _runtime(tmp_path)
    mobile = replace(
        _principal("user-core", MemberRole.CORE),
        client_scope="mobile-browser-one",
    )

    instance, _, created = runtime.extension_manager.launch_app(
        "ai2apps.general-chat",
        principal=mobile,
    )
    mount = runtime.extension_manager.mount_mobile(
        instance.id,
        principal=mobile,
    )

    assert created is False
    assert instance.singleton_key.endswith(":client:mobile-browser-one")
    assert mount["app_instance_id"] == instance.id
    assert mount["placement"] == "mobile"


@pytest.mark.asyncio
async def test_mobile_entry_resolution_and_durable_mount_fallback(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    manifest = _app()
    manifest["mobile"] = {"ready": True}
    resources = {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"}
    archive, _ = _write_bundle(tmp_path, private, manifest, ".ai2app", resources)
    await runtime.extension_manager.install(archive, approve_review=True)

    mobile = {
        item["app_key"]: item
        for item in runtime.extension_manager.list_mobile_apps()
    }
    assert mobile["example.notes"]["entry_source"] == "mini_entry"
    instance, _, _ = runtime.extension_manager.launch_app("example.notes")
    first = runtime.extension_manager.mount_mobile(instance.id)
    restored = runtime.extension_manager.mount_mobile(instance.id)

    assert first["placement"] == "mobile"
    assert first["entry_source"] == "mini_entry"
    assert first["renderer"] == "schema"
    assert first["source"] == "installed"
    assert restored["id"] == first["id"]
    assert restored["reused"] is True
    assert runtime.extension_manager.list_mobile_mounts()[0]["id"] == first["id"]


def test_mobile_entry_resolver_uses_fixed_priority_and_requires_opt_in():
    manager = InteractivePackageManager.resolve_mobile_entry
    entry = {"kind": "sandbox", "resource": "ui/entry.html"}
    mini = {"kind": "schema", "resource": "ui/mini.json"}
    mobile = {"kind": "sandbox", "resource": "ui/mobile.html"}

    assert manager({"entry": entry}) is None
    assert manager({"mobile": {"ready": True}, "entry": entry}) == (
        "entry",
        entry,
    )
    assert manager(
        {"mobile": {"ready": True}, "entry": entry, "mini_entry": mini}
    ) == ("mini_entry", mini)
    assert manager(
        {
            "mobile": {"ready": True},
            "entry": entry,
            "mini_entry": mini,
            "mobile_entry": mobile,
        }
    ) == ("mobile_entry", mobile)


@pytest.mark.asyncio
async def test_agent_package_rejects_non_object_invocation_schema(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    manifest = _agent()
    manifest["invocation_schema"] = {"type": "array"}
    archive, _ = _write_bundle(tmp_path, private, manifest, ".ai2agent")

    with pytest.raises(ExtensionError) as error:
        await runtime.extension_manager.install(archive, approve_review=True)

    assert error.value.code == "invalid_agent_invocation"


def test_builtin_singleton_can_close_and_reopen_without_key_conflict(tmp_path):
    runtime = _runtime(tmp_path)
    first, home, created = runtime.extension_manager.launch_app("ai2apps.dashboard")
    assert created is True and home is not None

    closed = runtime.extension_manager.close_instance(first.id)
    reopened, same_home, created_again = runtime.extension_manager.launch_app(
        "ai2apps.dashboard"
    )

    assert closed.status.value == "closed"
    assert reopened.id == first.id
    assert reopened.status.value == "active"
    assert same_home.id == home.id
    assert created_again is False


@pytest.mark.asyncio
async def test_multiple_app_instances_focus_close_and_verified_resource(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    manifest = _app()
    manifest["instances"] = {"mode": "multiple"}
    resources = {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"}
    archive, _ = _write_bundle(tmp_path, private, manifest, ".ai2app", resources)
    await runtime.extension_manager.install(archive, approve_review=True)

    first, _, _ = runtime.extension_manager.launch_app("example.notes")
    second, _, _ = runtime.extension_manager.launch_app("example.notes")
    assert first.id != second.id
    catalog = {
        item["app_key"]: item for item in runtime.extension_manager.list_apps()
    }
    assert catalog["example.notes"]["running_count"] == 2

    resource = runtime.extension_manager.resolve_app_resource(
        first.id, "ui/entry.html"
    )
    assert resource.read_bytes() == b"<main>Notes</main>"
    runtime.extension_manager.close_instance(first.id)
    runtime.extension_manager.focus_instance(first.id)
    assert runtime.extension_manager.apps.get_instance(first.id).status.value == "active"

    resource.chmod(0o644)
    resource.write_bytes(b"<main>Tampered</main>")
    with pytest.raises(ExtensionError) as error:
        runtime.extension_manager.resolve_app_resource(first.id, "ui/entry.html")
    assert error.value.code == "app_resource_integrity_failed"


def test_formal_app_install_requires_owner_or_root_publisher(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    runtime.package_repository.upsert_publisher(
        publisher_key="example.publisher",
        display_name="Example Organization",
        key_id="example.publisher:main",
        public_key=base64.b64encode(public).decode(),
        trust_status=TrustStatus.TRUSTED,
        source="organization",
    )
    archive, _ = _write_bundle(
        tmp_path,
        private,
        _app(),
        ".ai2app",
        {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"},
    )

    with pytest.raises(ExtensionError) as error:
        runtime.extension_manager.inspect(archive)

    assert error.value.code == "publisher_not_install_authority"


@pytest.mark.asyncio
async def test_agent_patch_effective_digest_upgrade_conflict_and_resolution(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    first, first_digest = _write_bundle(tmp_path, private, _agent(), ".ai2agent")
    await runtime.extension_manager.install(first, approve_review=True)
    original = runtime.extension_repository.effective(UnitKind.AGENT, "example.writer")
    assert original.upstream_digest == first_digest
    old_status = _agent()["status"]["primary"]
    patch_manifest = {
        "schema": "ai2apps.patch/v1",
        "version": "1.0.0",
        "target": {"kind": "agent", "id": "example.writer"},
        "base_digest": first_digest,
        "intent": "Use an HTML status card",
        "rebase_policy": "strict",
        "operations": [
            {
                "op": "replace",
                "target": "status.primary",
                "expected_kind": "object",
                "expected_digest": canonical_digest(old_status),
                "value": {
                    "kind": "safe-html",
                    "fallback": "Writing…",
                    "resource": "ui/status.html",
                },
            }
        ],
    }
    patch_path, _ = _write_bundle(
        tmp_path,
        private,
        patch_manifest,
        ".ai2patch",
        device=runtime.extension_manager.device,
    )
    patch = await runtime.extension_manager.install(patch_path, approve_review=True)
    effective = runtime.extension_repository.effective(UnitKind.AGENT, "example.writer")
    assert effective.effective_digest != original.effective_digest
    assert effective.effective_version.endswith("+local.1")
    assert effective.manifest["status"]["primary"]["kind"] == "safe-html"

    upgrade, upgrade_digest = _write_bundle(
        tmp_path,
        private,
        _agent("2.0.0", {"kind": "sandbox", "resource": "ui/upstream.html"}),
        ".ai2agent",
    )
    with pytest.raises(ExtensionError) as conflict:
        await runtime.extension_manager.install(upgrade, approve_review=True)
    assert conflict.value.code == "patch_rebase_conflict"
    assert (
        runtime.extension_repository.active_package(
            UnitKind.AGENT, "example.writer"
        ).digest
        == first_digest
    )
    assert (
        runtime.extension_repository.patches(UnitKind.AGENT, "example.writer")[0].status
        is PatchStatus.CONFLICTED
    )

    resolution = runtime.extension_manager.resolve_patch_and_activate(
        patch.id, "preserve-local", candidate_digest=upgrade_digest
    )
    assert resolution["activated"] is True
    assert resolution["package"].digest == upgrade_digest
    assert (
        runtime.extension_repository.effective(
            UnitKind.AGENT, "example.writer"
        ).manifest["status"]["primary"]["kind"]
        == "safe-html"
    )


@pytest.mark.asyncio
async def test_app_singleton_entry_mini_entry_and_atomic_state_migration(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    resources = {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"}
    first, _ = _write_bundle(tmp_path, private, _app(), ".ai2app", resources)
    await runtime.extension_manager.install(first, approve_review=True)
    instance, home, created = runtime.extension_manager.launch_app(
        "example.notes", state={"title": "Mine"}
    )
    same, same_home, created_again = runtime.extension_manager.launch_app(
        "example.notes"
    )
    assert (
        created
        and not created_again
        and same.id == instance.id
        and same_home.id == home.id
    )
    entry = runtime.extension_manager.mount(instance.id)
    mini = runtime.extension_manager.mount(
        instance.id, mini=True, placement="sidebar", interaction_session_id=home.id
    )
    assert entry["renderer"] == "sandbox" and mini["placement"] == "sidebar"

    migration = [
        {
            "from": 1,
            "to": 2,
            "operations": [{"op": "add", "target": "archived", "value": False}],
        }
    ]
    second, _ = _write_bundle(
        tmp_path, private, _app("2.0.0", 2, migration), ".ai2app", resources
    )
    await runtime.extension_manager.install(second, approve_review=True)
    migrated = runtime.extension_manager.apps.get_instance(instance.id)
    assert (
        migrated.state == {"title": "Mine", "archived": False}
        and migrated.state_schema_version == 2
    )
    with runtime.database.transaction() as connection:
        snapshot = connection.execute(
            "SELECT * FROM app_state_snapshots WHERE app_instance_id=?", (instance.id,)
        ).fetchone()
    assert json.loads(snapshot["state_json"]) == {"title": "Mine"}
    rolled_back = runtime.extension_manager.rollback(UnitKind.APP, "example.notes")
    assert rolled_back.version == "1.0.0"
    restored = runtime.extension_manager.apps.get_instance(instance.id)
    assert restored.state_schema_version == 1 and restored.state == {"title": "Mine"}


@pytest.mark.asyncio
async def test_safe_mode_temporarily_disables_local_patch_stack(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    first, digest = _write_bundle(tmp_path, private, _agent(), ".ai2agent")
    await runtime.extension_manager.install(first, approve_review=True)
    patch_manifest = {
        "schema": "ai2apps.patch/v1",
        "version": "1.0.0",
        "target": {"kind": "agent", "id": "example.writer"},
        "base_digest": digest,
        "intent": "Rename",
        "rebase_policy": "strict",
        "operations": [{"op": "replace", "target": "name", "value": "Local Writer"}],
    }
    patch_path, _ = _write_bundle(
        tmp_path,
        private,
        patch_manifest,
        ".ai2patch",
        device=runtime.extension_manager.device,
    )
    patch = await runtime.extension_manager.install(patch_path, approve_review=True)
    assert runtime.extension_manager.safe_mode(True)["active"] is True
    assert (
        runtime.extension_repository.patches(UnitKind.AGENT, "example.writer")[0].status
        is PatchStatus.DISABLED
    )
    runtime.extension_manager.safe_mode(False)
    assert (
        runtime.extension_repository.patches(UnitKind.AGENT, "example.writer")[0].status
        == patch.status
    )


@pytest.mark.asyncio
async def test_device_patch_creation_agent_rollback_and_audit_fail_closed(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    first, first_digest = _write_bundle(tmp_path, private, _agent(), ".ai2agent")
    second, _ = _write_bundle(tmp_path, private, _agent("2.0.0"), ".ai2agent")
    await runtime.extension_manager.install(first, approve_review=True)
    output = runtime.extension_manager.create_patch(
        tmp_path / "local.ai2patch",
        target_kind=UnitKind.AGENT,
        target_key="example.writer",
        intent="Rename locally",
        operations=[{"op": "replace", "target": "name", "value": "Device Writer"}],
        tests=[{"target": "name", "equals": "Device Writer"}],
    )
    await runtime.extension_manager.install(output, approve_review=True)
    assert (
        runtime.extension_repository.effective(
            UnitKind.AGENT, "example.writer"
        ).manifest["name"]
        == "Device Writer"
    )
    await runtime.extension_manager.install(second, approve_review=True)
    rolled_back = runtime.extension_manager.rollback(UnitKind.AGENT, "example.writer")
    assert rolled_back.digest == first_digest

    async def reject(_request):
        return {"decision": "reject", "risk": "high"}

    runtime.extension_manager.bind_local_ai_auditor(reject)
    third, _ = _write_bundle(tmp_path, private, _agent("3.0.0"), ".ai2agent")
    with pytest.raises(ExtensionError) as error:
        await runtime.extension_manager.install(third, approve_review=True)
    assert error.value.code == "audit_rejected"


@pytest.mark.asyncio
async def test_failed_app_migration_retains_old_effective_state_and_package(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    resources = {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"}
    first, first_digest = _write_bundle(tmp_path, private, _app(), ".ai2app", resources)
    await runtime.extension_manager.install(first, approve_review=True)
    old_effective = runtime.extension_repository.effective(
        UnitKind.APP, "example.notes"
    ).effective_digest
    instance, _, _ = runtime.extension_manager.launch_app(
        "example.notes", state={"title": "Safe"}
    )
    broken, _ = _write_bundle(tmp_path, private, _app("2.0.0", 2), ".ai2app", resources)
    with pytest.raises(ExtensionError) as error:
        await runtime.extension_manager.install(broken, approve_review=True)
    assert error.value.code == "state_migration_missing"
    assert (
        runtime.extension_repository.active_package(
            UnitKind.APP, "example.notes"
        ).digest
        == first_digest
    )
    assert (
        runtime.extension_repository.effective(
            UnitKind.APP, "example.notes"
        ).effective_digest
        == old_effective
    )
    assert runtime.extension_manager.apps.get_instance(instance.id).state == {
        "title": "Safe"
    }


@pytest.mark.asyncio
async def test_app_api_enforces_principal_catalog_and_launch_policy(tmp_path):
    runtime = _runtime(tmp_path)
    member = _principal("user-member", MemberRole.MEMBER)
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: member,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        catalog = await client.get("/v1/platform/apps")
        denied = await client.post(
            "/v1/platform/apps/ai2apps.agents/launch", json={}
        )
        launched = await client.post(
            "/v1/platform/apps/ai2apps.general-chat/launch", json={}
        )
        agents_api = await client.get("/v1/platform/agents")
        secrets_api = await client.get("/v1/platform/secrets")
        services_api = await client.get("/v1/platform/services")

    assert [item["app_key"] for item in catalog.json()["items"]] == [
        "ai2apps.account",
        "ai2apps.general-chat",
    ]
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "app_access_denied"
    assert agents_api.status_code == 403
    assert agents_api.json()["detail"]["code"] == "app_access_denied"
    assert secrets_api.status_code == 403
    assert secrets_api.json()["detail"]["code"] == "app_access_denied"
    assert services_api.status_code == 403
    assert services_api.json()["detail"]["code"] == "app_access_denied"
    assert launched.status_code == 200
    instance = runtime.extension_manager.apps.get_instance(
        launched.json()["instance_id"]
    )
    assert instance.owner_user_id == "user-member"


@pytest.mark.asyncio
async def test_m9_management_api_installs_launches_mounts_and_reports_effective(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    resources = {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"}
    archive, _ = _write_bundle(tmp_path, private, _app(), ".ai2app", resources)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        installed = await client.post(
            "/v1/platform/interactive-packages/install",
            json={"archive_path": str(archive), "approve_review": True},
        )
        launched = await client.post("/v1/platform/apps/example.notes/launch", json={})
        mounted = await client.post(
            f"/v1/platform/app-instances/{launched.json()['instance_id']}/mounts",
            json={
                "mini": True,
                "placement": "inline",
                "interaction_session_id": launched.json()["home_session_id"],
            },
        )
        effective = await client.get(
            "/v1/platform/effective-definitions/app/example.notes"
        )
        entry = await client.get(
            f"/v1/platform/app-instances/{launched.json()['instance_id']}/entry"
        )
        suspended = await client.post(
            f"/v1/platform/app-instances/{launched.json()['instance_id']}/suspend"
        )
        focused = await client.post(
            f"/v1/platform/app-instances/{launched.json()['instance_id']}/focus"
        )
        closed = await client.delete(
            f"/v1/platform/app-instances/{launched.json()['instance_id']}"
        )
    assert installed.status_code == 200 and installed.json()["status"] == "active"
    assert launched.status_code == 200 and launched.json()["created"] is True
    assert mounted.status_code == 200 and mounted.json()["renderer"] == "schema"
    assert effective.status_code == 200 and effective.json()["key"] == "example.notes"
    assert entry.status_code == 200 and entry.json()["renderer"] == "sandbox"
    assert suspended.json()["status"] == "suspended"
    assert focused.json()["status"] == "active"
    assert closed.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_w4_mini_entry_mount_context_restore_and_unmount(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    resources = {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"}
    manifest = _app()
    manifest["activation"] = {
        "description": "Take quick notes",
        "examples": ["remember this for me"],
        "behavior": "auto-mount",
    }
    archive, _ = _write_bundle(tmp_path, private, manifest, ".ai2app", resources)
    await runtime.extension_manager.install(archive, approve_review=True)
    instance, home, _ = runtime.extension_manager.launch_app("example.notes")

    mount = runtime.extension_manager.mount(
        instance.id,
        mini=True,
        placement="inline",
        interaction_session_id=home.id,
        context={"message_id": "msg_" + "a" * 32},
    )
    restored = runtime.extension_manager.list_mounts(home.id)

    assert restored[0]["id"] == mount["id"]
    assert restored[0]["context"]["message_id"] == "msg_" + "a" * 32
    assert runtime.extension_manager.instance_can_use_session(instance.id, home.id)
    suggestions = runtime.extension_manager.suggest_apps("Please remember this for me")
    assert suggestions[0]["app_key"] == "example.notes"
    assert suggestions[0]["behavior"] == "suggest"
    assert runtime.extension_manager.unmount(mount["id"])["status"] == "unmounted"
    assert runtime.extension_manager.list_mounts(home.id) == ()


def test_w4_safe_mode_status_and_control_snapshot_are_recoverable(tmp_path):
    runtime = _runtime(tmp_path)
    assert runtime.extension_manager.safe_mode_status()["active"] is False
    enabled = runtime.extension_manager.safe_mode(True, "test-recovery")
    snapshot = runtime.extension_manager.control_snapshot()
    assert enabled["active"] is True
    assert snapshot["safe_mode"]["active"] is True
    assert snapshot["safe_mode"]["reason"] == "test-recovery"


@pytest.mark.asyncio
async def test_app_patch_and_safe_mode_switch_effective_definition(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    resources = {"ui/entry.html": b"<main>Notes</main>", "ui/mini.json": b"{}"}
    archive, _ = _write_bundle(tmp_path, private, _app(), ".ai2app", resources)
    await runtime.extension_manager.install(archive, approve_review=True)
    patch_path = runtime.extension_manager.create_patch(
        tmp_path / "notes.ai2patch",
        target_kind=UnitKind.APP,
        target_key="example.notes",
        intent="Rename Notes",
        operations=[{"op": "replace", "target": "name", "value": "My Notes"}],
    )
    await runtime.extension_manager.install(patch_path, approve_review=True)
    assert (
        runtime.extension_repository.effective(UnitKind.APP, "example.notes").manifest[
            "name"
        ]
        == "My Notes"
    )
    runtime.extension_manager.safe_mode(True)
    assert (
        runtime.extension_repository.effective(UnitKind.APP, "example.notes").manifest[
            "name"
        ]
        == "Notes"
    )
    runtime.extension_manager.safe_mode(False)
    assert (
        runtime.extension_repository.effective(UnitKind.APP, "example.notes").manifest[
            "name"
        ]
        == "My Notes"
    )
