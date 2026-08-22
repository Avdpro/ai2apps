# SPDX-License-Identifier: Apache-2.0
"""Tests for restart-bound model adapter wheel installation."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.packages.contract_v1 import (
    REPOSITORY_PREFIX,
    jcs_bytes,
    public_key_fingerprint,
)
from omlx.admin import routes
from omlx.model_adapters import (
    ModelAdapterPackageError,
    ModelAdapterPackageManager,
    ModelAdapterRegistry,
    configure_model_adapter_packages,
)
from omlx.model_adapters.catalog import (
    ModelAdapterCatalog,
    validate_checkpoint_record,
)


def _wheel(
    root: Path,
    *,
    version: str = "1.0.0",
    entry_points: bool = True,
    requirement: str | None = None,
    unsafe_member: str | None = None,
) -> Path:
    path = root / f"demo_adapter-{version}-py3-none-any.whl"
    dist_info = f"demo_adapter-{version}.dist-info"
    metadata = [
        "Metadata-Version: 2.4",
        "Name: demo-adapter",
        f"Version: {version}",
    ]
    if requirement:
        metadata.append(f"Requires-Dist: {requirement}")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "demo_adapter/__init__.py",
            "class DemoAdapter:\n"
            "    adapter_id = 'demo-adapter'\n"
            "    priority = 7\n"
            "    def match(self, context): return False\n",
        )
        archive.writestr(f"{dist_info}/METADATA", "\n".join(metadata) + "\n")
        archive.writestr(
            f"{dist_info}/WHEEL", "Wheel-Version: 1.0\nTag: py3-none-any\n"
        )
        if entry_points:
            archive.writestr(
                f"{dist_info}/entry_points.txt",
                "[omlx.model_adapters]\ndemo = demo_adapter:DemoAdapter\n",
            )
        if unsafe_member:
            archive.writestr(unsafe_member, "unsafe")
    return path


def _catalog_fixture(
    wheel: Path, *, metadata_version: int = 1, checkpoints: list[dict] | None = None
):
    private = Ed25519PrivateKey.generate()
    public_pem = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    fingerprint = public_key_fingerprint(public_pem)
    wheel_bytes = wheel.read_bytes()
    now = datetime.now(UTC)
    release = {
        "packageId": "demo-adapter",
        "packageType": "model-adapter",
        "version": "1.0.0",
        "status": "published",
        "displayName": "Demo adapter",
        "artifact": {
            "url": f"/adapters/{wheel.name}",
            "sha256": hashlib.sha256(wheel_bytes).hexdigest(),
            "size": len(wheel_bytes),
        },
    }
    if checkpoints is not None:
        release["checkpoints"] = checkpoints
    payload = {
        "domain": "ai2apps.repository-snapshot.v1",
        "version": metadata_version,
        "generatedAt": (now - timedelta(minutes=1)).isoformat(),
        "expiresAt": (now + timedelta(days=1)).isoformat(),
        "releases": [release],
    }
    signature = private.sign(REPOSITORY_PREFIX + jcs_bytes(payload))
    envelope = {
        "schemaVersion": "ai2apps.repository-snapshot-envelope.v1",
        "payload": payload,
        "signature": {
            "keyId": fingerprint,
            "algorithm": "Ed25519",
            "value": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        },
    }
    return public_pem, fingerprint, envelope, wheel_bytes


def _catalog_transport(public_pem, envelope, wheel_bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("repository-key.json"):
            return httpx.Response(200, json={"publicKeyPem": public_pem})
        if request.url.path.endswith("catalog.json"):
            return httpx.Response(200, json=envelope)
        if request.url.path.endswith(".whl"):
            return httpx.Response(200, content=wheel_bytes)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_install_upgrade_list_and_uninstall_are_restart_bound(tmp_path):
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    first = manager.install(_wheel(tmp_path, version="1.0.0"))

    assert first["operation"] == "installed"
    assert first["restart_required"] is True
    assert manager.installed()[0]["version"] == "1.0.0"

    second = manager.install(_wheel(tmp_path, version="1.1.0"))
    assert second["operation"] == "upgraded"
    assert second["previous_version"] == "1.0.0"
    assert manager.installed()[0]["version"] == "1.1.0"

    removed = manager.uninstall("demo_adapter")
    assert removed["operation"] == "uninstalled"
    assert removed["restart_required"] is True
    assert manager.installed() == []
    assert manager.prune_inactive() == 2
    assert not manager.store.exists() or not any(manager.store.rglob("site-packages"))


def test_configured_package_is_discovered_only_in_explicit_unsafe_mode(
    tmp_path, monkeypatch
):
    base_path = tmp_path / "runtime"
    manager = ModelAdapterPackageManager(base_path)
    manager.install(_wheel(tmp_path))

    assert configure_model_adapter_packages(base_path) == ()
    monkeypatch.setenv("AI2APPS_UNSAFE_IN_PROCESS_MODEL_ADAPTERS", "1")
    added = configure_model_adapter_packages(base_path)
    assert len(added) == 1
    try:
        adapters = ModelAdapterRegistry().adapters()
        assert any(adapter.adapter_id == "demo-adapter" for adapter in adapters)
    finally:
        for path in added:
            if str(path) in sys.path:
                sys.path.remove(str(path))
        sys.modules.pop("demo_adapter", None)


def test_inspect_rejects_missing_adapter_entry_point(tmp_path):
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        manager.inspect(_wheel(tmp_path, entry_points=False))
    assert exc_info.value.code == "adapter_entry_point_missing"


def test_inspect_rejects_path_traversal(tmp_path):
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        manager.inspect(_wheel(tmp_path, unsafe_member="../escape.py"))
    assert exc_info.value.code == "wheel_unsafe"


def test_inspect_rejects_missing_runtime_dependency(tmp_path):
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        manager.inspect(
            _wheel(tmp_path, requirement="definitely-not-installed-omlx-test>=1")
        )
    assert exc_info.value.code == "dependency_missing"


def test_corrupt_manifest_fails_closed(tmp_path):
    manager = ModelAdapterPackageManager(tmp_path)
    manager.root.mkdir(parents=True)
    manager.manifest_path.write_text("not json", encoding="utf-8")

    with pytest.raises(ModelAdapterPackageError) as exc_info:
        manager.installed()
    assert exc_info.value.code == "manifest_invalid"


@pytest.mark.asyncio
async def test_admin_package_api_install_list_and_uninstall(tmp_path, monkeypatch):
    monkeypatch.setattr(
        routes,
        "_get_global_settings",
        lambda: SimpleNamespace(base_path=tmp_path / "runtime"),
    )
    request = routes.ModelAdapterPackageRequest(wheel_path=str(_wheel(tmp_path)))

    installed = await routes.install_model_adapter_package(request, True)
    assert installed["operation"] == "installed"
    listed = await routes.list_model_adapter_packages(True)
    assert listed["items"][0]["name"] == "demo-adapter"
    removed = await routes.uninstall_model_adapter_package("demo-adapter", True)
    assert removed["operation"] == "uninstalled"


@pytest.mark.asyncio
async def test_admin_catalog_api_lists_and_installs(monkeypatch):
    class FakeCatalog:
        async def trusted_catalog(self):
            return {"metadata_version": 7, "items": [{"package_id": "demo-adapter"}]}

        async def install(self, package_name, version):
            return {
                "name": package_name,
                "version": version,
                "operation": "installed",
                "restart_required": True,
            }

    monkeypatch.setattr(routes, "_model_adapter_catalog", FakeCatalog)
    listed = await routes.list_model_adapter_catalog(True)
    assert listed["metadata_version"] == 7
    installed = await routes.install_model_adapter_from_catalog(
        routes.ModelAdapterCatalogInstallRequest(
            package_name="demo-adapter", version="1.0.0"
        ),
        True,
    )
    assert installed["restart_required"] is True


@pytest.mark.asyncio
async def test_admin_catalog_starts_signed_cached_moe_recipe(monkeypatch):
    captured = {}

    class FakeCatalog:
        async def cached_moe_checkpoint(self, package_name, version, recipe_id):
            captured.update(
                package_name=package_name, version=version, recipe_id=recipe_id
            )
            return {
                "source": "huggingface",
                "repo_id": "example/demo-moe",
                "revision": "f" * 40,
            }

    class FakeTask:
        def to_dict(self):
            return {"task_id": "cache-task"}

    class FakeInstaller:
        def _recipe(self, recipe_id):
            return {
                "sources": [
                    {
                        "id": "huggingface",
                        "repo_id": "example/demo-moe",
                        "revision": "f" * 40,
                    }
                ]
            }

        async def start(
            self, recipe_id, source, memory_tier, token, storage_policy=None
        ):
            captured.update(
                started=recipe_id,
                source=source,
                memory_tier=memory_tier,
                token=token,
                storage_policy=storage_policy,
            )
            return FakeTask()

    monkeypatch.setattr(routes, "_model_adapter_catalog", FakeCatalog)
    monkeypatch.setattr(routes, "_get_ai2apps_installer", lambda: FakeInstaller())
    response = await routes.install_model_adapter_checkpoint(
        routes.ModelAdapterCheckpointInstallRequest(
            package_name="omlx-model-cached-moe",
            package_version="0.1.0",
            recipe_id="demo-moe",
        ),
        True,
    )

    assert response == {"success": True, "task": {"task_id": "cache-task"}}
    assert captured["started"] == "demo-moe"
    assert captured["memory_tier"] == "auto"
    assert captured["storage_policy"] is None


@pytest.mark.asyncio
async def test_hf_download_api_forwards_pinned_checkpoint_revision(monkeypatch):
    captured = {}

    class FakeTask:
        def to_dict(self):
            return {"task_id": "task-1"}

    class FakeDownloader:
        async def start_download(self, repo_id, token, *, revision=None):
            captured.update(repo_id=repo_id, token=token, revision=revision)
            return FakeTask()

    monkeypatch.setattr(routes, "_hf_downloader", FakeDownloader())
    response = await routes.start_hf_download(
        routes.HFDownloadRequest(repo_id="example/demo-27b-mlx", revision="c" * 40),
        True,
    )
    assert response["success"] is True
    assert captured == {
        "repo_id": "example/demo-27b-mlx",
        "token": "",
        "revision": "c" * 40,
    }


def test_manifest_contains_only_relative_payload_paths(tmp_path):
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    manager.install(_wheel(tmp_path))

    manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
    record = manifest["packages"]["demo-adapter"]
    assert not Path(record["path"]).is_absolute()


@pytest.mark.asyncio
async def test_signed_catalog_downloads_and_installs_verified_wheel(tmp_path):
    wheel = _wheel(tmp_path)
    public_pem, fingerprint, envelope, wheel_bytes = _catalog_fixture(wheel)
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    catalog = ModelAdapterCatalog(
        manager,
        catalog_url="https://catalog.example/catalog.json",
        key_url="https://catalog.example/repository-key.json",
        repository_fingerprint=fingerprint,
        transport=_catalog_transport(public_pem, envelope, wheel_bytes),
    )

    available = await catalog.trusted_catalog()
    assert available["metadata_version"] == 1
    assert available["items"][0]["package_id"] == "demo-adapter"
    assert available["items"][0]["installed_version"] is None

    installed = await catalog.install("demo-adapter")
    assert installed["operation"] == "installed"
    assert installed["restart_required"] is True
    assert installed["catalog_metadata_version"] == 1


@pytest.mark.asyncio
async def test_signed_catalog_returns_pinned_checkpoint_guidance(tmp_path):
    wheel = _wheel(tmp_path)
    public_pem, fingerprint, envelope, wheel_bytes = _catalog_fixture(
        wheel,
        checkpoints=[
            {
                "source": "huggingface",
                "repoId": "example/demo-27b-mlx",
                "revision": "b" * 40,
                "displayName": "Demo 27B MLX",
                "estimatedSizeBytes": 15_000_000_000,
            }
        ],
    )
    catalog = ModelAdapterCatalog(
        ModelAdapterPackageManager(tmp_path / "runtime"),
        catalog_url="https://catalog.example/catalog.json",
        key_url="https://catalog.example/repository-key.json",
        repository_fingerprint=fingerprint,
        transport=_catalog_transport(public_pem, envelope, wheel_bytes),
    )
    available = await catalog.trusted_catalog()
    checkpoint = available["items"][0]["checkpoints"][0]
    assert checkpoint["repo_id"] == "example/demo-27b-mlx"
    assert checkpoint["revision"] == "b" * 40
    assert checkpoint["install_mode"] == "download"
    assert checkpoint["recipe_id"] is None
    assert checkpoint["package_id"] == "demo-adapter"
    assert checkpoint["package_version"] == "1.0.0"


@pytest.mark.asyncio
async def test_signed_catalog_resolves_cached_moe_recipe_only_after_install(tmp_path):
    wheel = _wheel(tmp_path)
    public_pem, fingerprint, envelope, wheel_bytes = _catalog_fixture(
        wheel,
        checkpoints=[
            {
                "source": "huggingface",
                "repoId": "example/demo-moe",
                "revision": "d" * 40,
                "displayName": "Demo Cached-MoE",
                "installMode": "cache-moe",
                "recipeId": "demo-moe",
            }
        ],
    )
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    catalog = ModelAdapterCatalog(
        manager,
        catalog_url="https://catalog.example/catalog.json",
        key_url="https://catalog.example/repository-key.json",
        repository_fingerprint=fingerprint,
        transport=_catalog_transport(public_pem, envelope, wheel_bytes),
    )

    with pytest.raises(ModelAdapterPackageError):
        await catalog.cached_moe_checkpoint("demo-adapter", "1.0.0", "demo-moe")
    await catalog.install("demo-adapter", "1.0.0")
    checkpoint = await catalog.cached_moe_checkpoint(
        "demo-adapter", "1.0.0", "demo-moe"
    )
    assert checkpoint["repo_id"] == "example/demo-moe"
    assert checkpoint["install_mode"] == "cache-moe"


@pytest.mark.asyncio
async def test_catalog_rejects_tampered_wheel_before_install(tmp_path):
    wheel = _wheel(tmp_path)
    public_pem, fingerprint, envelope, wheel_bytes = _catalog_fixture(wheel)
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    catalog = ModelAdapterCatalog(
        manager,
        catalog_url="https://catalog.example/catalog.json",
        key_url="https://catalog.example/repository-key.json",
        repository_fingerprint=fingerprint,
        transport=_catalog_transport(public_pem, envelope, wheel_bytes + b"tampered"),
    )

    with pytest.raises(ModelAdapterPackageError) as exc_info:
        await catalog.install("demo-adapter")
    assert exc_info.value.code == "artifact_size_mismatch"
    assert manager.installed() == []


@pytest.mark.asyncio
async def test_catalog_rejects_metadata_rollback(tmp_path):
    wheel = _wheel(tmp_path)
    public_pem, fingerprint, envelope, wheel_bytes = _catalog_fixture(
        wheel, metadata_version=2
    )
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    catalog = ModelAdapterCatalog(
        manager,
        catalog_url="https://catalog.example/catalog.json",
        key_url="https://catalog.example/repository-key.json",
        repository_fingerprint=fingerprint,
        transport=_catalog_transport(public_pem, envelope, wheel_bytes),
    )
    await catalog.trusted_catalog()

    old_public, old_fingerprint, old_envelope, old_bytes = _catalog_fixture(
        wheel, metadata_version=1
    )
    old_catalog = ModelAdapterCatalog(
        manager,
        catalog_url="https://catalog.example/catalog.json",
        key_url="https://catalog.example/repository-key.json",
        repository_fingerprint=old_fingerprint,
        transport=_catalog_transport(old_public, old_envelope, old_bytes),
    )
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        await old_catalog.trusted_catalog()
    assert exc_info.value.code == "catalog_metadata_rollback"


def test_catalog_rejects_cross_origin_key(tmp_path):
    manager = ModelAdapterPackageManager(tmp_path / "runtime")
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        ModelAdapterCatalog(
            manager,
            catalog_url="https://catalog.example/catalog.json",
            key_url="https://attacker.example/key.json",
        )
    assert exc_info.value.code == "catalog_url_invalid"


def test_checkpoint_guidance_rejects_mutable_branch_revision():
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        validate_checkpoint_record(
            {
                "source": "huggingface",
                "repoId": "example/demo-27b-mlx",
                "revision": "main",
                "displayName": "Demo 27B MLX",
            }
        )
    assert exc_info.value.code == "catalog_metadata_invalid"


def test_cached_moe_guidance_requires_recipe_id():
    with pytest.raises(ModelAdapterPackageError) as exc_info:
        validate_checkpoint_record(
            {
                "source": "huggingface",
                "repoId": "example/demo-moe",
                "revision": "e" * 40,
                "displayName": "Demo MoE",
                "installMode": "cache-moe",
            }
        )
    assert exc_info.value.code == "catalog_metadata_invalid"
