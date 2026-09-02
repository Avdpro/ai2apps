from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from ai2apps.api.packages import create_package_router
from ai2apps.cloud_client import AI2AppsCloudClient, CloudSessionStore
from ai2apps.identity import RequestPrincipal
from ai2apps.packages.contract_v1 import (
    REPOSITORY_PREFIX,
    build_package,
    create_signature_envelope,
    generate_publisher_key,
    jcs_bytes,
    public_key_fingerprint,
)
from ai2apps.packages.models import TrustStatus
from ai2apps.packages.registry import RegistryError, RegistryPackageManager
from ai2apps.secrets import MemorySecretBackend
from ai2apps.storage.database import PlatformDatabase


class _Secrets:
    pass


class _PublishingManager:
    def __init__(self):
        self.bound_clouds: list[str] = []

    def for_cloud(self, cloud):
        self.bound_clouds.append(cloud)
        return _BoundPublishingManager(cloud)


def test_official_punctuation_package_maps_to_model_service_identity():
    assert (
        RegistryPackageManager._service_dependency_key("ai2apps/punctuation-restorer")
        == "ai2apps.model.punctuation-restorer"
    )


class _BoundPublishingManager:
    def __init__(self, cloud):
        self.cloud = cloud

    async def publishers(self):
        return {"cloud": self.cloud}

    async def reauthenticate_admin(self, password):
        return {"cloud": self.cloud, "passwordLength": len(password)}


def _source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.js").write_text("document.body.textContent='verified';\n")
    (source / "ai2apps.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ai2apps.package-manifest.v1",
                "package": {
                    "id": "example/verified-app",
                    "type": "app",
                    "version": "1.2.3",
                    "displayName": "Verified App",
                    "description": "Verified package",
                    "localizations": {
                        "zh-CN": {
                            "displayName": "已验证应用",
                            "description": "已验证的软件包",
                        }
                    },
                },
                "compatibility": {"ai2apps": ">=0.1.0 <2.0.0"},
                "entrypoints": [{"name": "main", "kind": "app", "path": "main.js"}],
                "permissions": [],
                "dependencies": [],
                "files": [],
            }
        )
    )
    return source


def _service_source(tmp_path):
    source = tmp_path / "service-source"
    source.mkdir()
    (source / "worker.py").write_text("def create_adapter():\n    return object()\n")
    (source / "service.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "ai2apps.service/v1",
                "id": "example.model.fixture",
                "name": "Verified Model Service",
                "version": "1.2.3",
                "publisher": {"id": "placeholder"},
                "runtime": {
                    "mode": "process",
                    "protocol": "ai2apps-model-worker/v1",
                    "adapter": "worker.py:create_adapter",
                },
                "models": [],
                "capabilities": [],
                "requires": {"services": [], "python": ">=3.11,<3.14"},
                "permissions": {"network": {"outbound": False}},
                "compatibility": {"os": ["macos"], "architectures": ["arm64"]},
                "health": {"path": "/health", "startup_timeout_seconds": 30},
                "restart": {"max_attempts": 1, "base_delay_seconds": 1},
                "tools": [],
            },
            sort_keys=False,
        )
    )
    (source / "ai2apps.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ai2apps.package-manifest.v1",
                "package": {
                    "id": "example/model-fixture",
                    "type": "service",
                    "version": "1.2.3",
                    "displayName": "Verified Model Service",
                    "description": "Registry Service fixture",
                },
                "compatibility": {
                    "ai2apps": ">=0.1.0 <2.0.0",
                    "platforms": ["darwin"],
                    "architectures": ["arm64"],
                },
                "entrypoints": [
                    {"name": "service", "kind": "service", "path": "service.yaml"}
                ],
                "permissions": [],
                "dependencies": [],
                "files": [],
            }
        )
    )
    return source


def _repository_key():
    private = Ed25519PrivateKey.generate()
    public_pem = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    fingerprint = public_key_fingerprint(public_pem)
    return private, public_pem, fingerprint


def _snapshot(private, fingerprint, release, version=7):
    now = datetime.now(UTC)
    payload = {
        "domain": "ai2apps.repository-snapshot.v1",
        "version": version,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "expiresAt": (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z"),
        "releases": [release],
    }
    signature = (
        base64.urlsafe_b64encode(private.sign(REPOSITORY_PREFIX + jcs_bytes(payload)))
        .decode()
        .rstrip("=")
    )
    return {
        "schemaVersion": "ai2apps.repository-snapshot-envelope.v1",
        "payload": payload,
        "signature": {"keyId": fingerprint, "algorithm": "Ed25519", "value": signature},
    }


def test_registry_rejects_non_reserved_inference_runtime_package_id(tmp_path):
    source = _service_source(tmp_path)
    service_path = source / "service.yaml"
    service = yaml.safe_load(service_path.read_text(encoding="utf-8"))
    service["runtime"] = {
        "mode": "process",
        "protocol": "ai2apps-inference-runtime/v1",
        "role": "inference_provider",
        "descriptor": "META/runtime-manifest.json",
    }
    (source / "META").mkdir()
    (source / "META" / "runtime-manifest.json").write_text("{}")
    service_path.write_text(yaml.safe_dump(service, sort_keys=False))
    artifact_path = tmp_path / "unofficial-runtime.ai2service"
    inspected = build_package(source, artifact_path)
    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint="ab" * 32,
    )

    with pytest.raises(RegistryError) as error:
        manager._service_bundle(
            inspected,
            {"payload": {"publisherId": "third-party"}, "signature": {}},
        )

    assert error.value.code == "runtime_publisher_denied"


def test_registry_reports_signed_os_compatibility_before_install(monkeypatch):
    monkeypatch.setattr("ai2apps.packages.registry.platform.system", lambda: "Darwin")
    monkeypatch.setattr("ai2apps.packages.registry.platform.machine", lambda: "arm64")
    monkeypatch.setattr(
        "ai2apps.packages.registry.platform.mac_ver", lambda: ("15.6.1", (), "")
    )
    compatibility = {
        "ai2apps": ">=0.1.0 <2.0.0",
        "platforms": ["darwin"],
        "architectures": ["arm64"],
        "minimumOsVersion": "26.2",
    }

    status = RegistryPackageManager._compatibility_status(compatibility)

    assert status["installable"] is False
    assert status["blockers"][0]["code"] == "os_version_too_old"
    assert status["blockers"][0]["details"] == {
        "current": "15.6.1",
        "minimum": "26.2",
    }


@pytest.mark.asyncio
async def test_registry_blocks_incompatible_release_before_package_download(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("ai2apps.packages.registry.platform.system", lambda: "Darwin")
    monkeypatch.setattr("ai2apps.packages.registry.platform.machine", lambda: "arm64")
    monkeypatch.setattr(
        "ai2apps.packages.registry.platform.mac_ver", lambda: ("15.6.1", (), "")
    )
    repository_private, repository_public, repository_fingerprint = _repository_key()
    release = {
        "packageId": "ai2apps/runtime-omlx",
        "packageType": "service",
        "version": "1.0.1",
        "status": "published",
        "statusReason": None,
        "compatibility": {
            "ai2apps": ">=0.1.0 <2.0.0",
            "platforms": ["darwin"],
            "architectures": ["arm64"],
            "minimumOsVersion": "26.2",
        },
        "artifact": {
            "sha256": "00" * 32,
            "size": 1,
            "mediaType": "application/vnd.ai2apps.service+zip",
            "url": "https://coder.ai2apps.test/forbidden-artifact",
        },
        "envelopeUrl": "https://coder.ai2apps.test/forbidden-envelope",
        "publisher": {
            "id": "21bfc1af-dfbd-45fb-a648-bc3fe306b569",
            "displayName": "AI2Apps",
            "key": {
                "id": "eff821e4-7612-4c3e-9fb4-6d116e8170c3",
                "algorithm": "Ed25519",
                "fingerprintSha256": "11" * 32,
                "publicKeyPem": "unused",
            },
        },
    }
    snapshot = _snapshot(repository_private, repository_fingerprint, release)
    requested_paths = []

    def handler(request: httpx.Request):
        requested_paths.append(request.url.path)
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(200, json={"publicKeyPem": repository_public})
        if request.url.path.endswith("/metadata/latest"):
            return httpx.Response(200, json=snapshot)
        raise AssertionError(f"package bytes must not be requested: {request.url}")

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=repository_fingerprint,
    )

    with pytest.raises(RegistryError) as error:
        await manager.download_verified("ai2apps", "runtime-omlx", "1.0.1")

    assert error.value.code == "os_version_too_old"
    assert all("forbidden" not in path for path in requested_paths)
    await cloud.close()


@pytest.mark.asyncio
async def test_registry_download_verifies_snapshot_publisher_and_bytes(tmp_path):
    artifact_path = tmp_path / "verified.ai2app"
    inspected = build_package(_source(tmp_path), artifact_path)
    publisher_private, publisher_public, publisher_fingerprint = (
        generate_publisher_key()
    )
    envelope = create_signature_envelope(
        inspected,
        publisher_private,
        publisher_id="21bfc1af-dfbd-45fb-a648-bc3fe306b569",
        publisher_key_id="eff821e4-7612-4c3e-9fb4-6d116e8170c3",
    )
    repository_private, repository_public, repository_fingerprint = _repository_key()
    release = {
        "packageId": "example/verified-app",
        "packageType": "app",
        "version": "1.2.3",
        "status": "published",
        "statusReason": None,
        "artifact": {
            "sha256": inspected.sha256,
            "size": inspected.size,
            "mediaType": inspected.media_type,
            "url": "https://coder.ai2apps.test/v1/registry/packages/example/verified-app/versions/1.2.3/artifact",
        },
        "envelopeUrl": "https://coder.ai2apps.test/v1/registry/packages/example/verified-app/versions/1.2.3/envelope",
        "publisher": {
            "id": "21bfc1af-dfbd-45fb-a648-bc3fe306b569",
            "displayName": "Fixture Publisher",
            "key": {
                "id": "eff821e4-7612-4c3e-9fb4-6d116e8170c3",
                "algorithm": "Ed25519",
                "fingerprintSha256": publisher_fingerprint,
                "publicKeyPem": publisher_public,
            },
        },
    }
    snapshot = _snapshot(repository_private, repository_fingerprint, release)

    def handler(request: httpx.Request):
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(200, json={"publicKeyPem": repository_public})
        if request.url.path.endswith("/metadata/latest"):
            return httpx.Response(200, json=snapshot)
        if request.url.path.endswith("/envelope"):
            return httpx.Response(200, json=envelope)
        if request.url.path.endswith("/artifact"):
            return httpx.Response(
                200,
                content=artifact_path.read_bytes(),
                headers={"content-type": inspected.media_type},
            )
        raise AssertionError(request.url)

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=repository_fingerprint,
    )
    (
        downloaded,
        downloaded_envelope,
        downloaded_release,
        metadata_version,
    ) = await manager.download_verified("example", "verified-app", "1.2.3")
    assert downloaded.sha256 == inspected.sha256
    assert downloaded_envelope == envelope
    assert downloaded_release["publisher"]["displayName"] == "Fixture Publisher"
    assert metadata_version == 7
    runtime_bundle = manager._interactive_bundle(downloaded, envelope)
    assert runtime_bundle.key == "example.verified-app"
    assert runtime_bundle.manifest["id"] == "example.verified-app"
    assert runtime_bundle.manifest["localizations"]["zh-CN"] == {
        "name": "已验证应用",
        "description": "已验证的软件包",
    }
    await cloud.close()


def _multi_source_download_fixture(tmp_path, *, source_count=2):
    artifact_path = tmp_path / "multi-source.ai2app"
    inspected = build_package(_source(tmp_path), artifact_path)
    publisher_private, publisher_public, publisher_fingerprint = (
        generate_publisher_key()
    )
    publisher_id = "21bfc1af-dfbd-45fb-a648-bc3fe306b569"
    publisher_key_id = "eff821e4-7612-4c3e-9fb4-6d116e8170c3"
    envelope = create_signature_envelope(
        inspected,
        publisher_private,
        publisher_id=publisher_id,
        publisher_key_id=publisher_key_id,
    )
    content = artifact_path.read_bytes()
    piece_size = max(1, (len(content) + 1) // 2)
    piece_hashes = [
        hashlib.sha256(content[start : start + piece_size]).hexdigest()
        for start in range(0, len(content), piece_size)
    ]
    sources = [
        {
            "id": "src_cloud",
            "kind": "cloud",
            "url": "https://coder.ai2apps.test/v1/registry/packages/example/verified-app/versions/1.2.3/artifact",
        },
        {
            "id": "src_mirror",
            "kind": "modelscope",
            "url": "https://mirror.ai2apps.test/releases/verified-app.ai2app",
        },
        *[
            {
                "id": f"src_mirror_{index}",
                "kind": "github" if index % 2 == 0 else "other",
                "url": f"https://mirror-{index}.ai2apps.test/releases/verified-app.ai2app",
            }
            for index in range(2, source_count)
        ],
    ][:source_count]
    release = {
        "packageId": "example/verified-app",
        "packageType": "app",
        "version": "1.2.3",
        "status": "published",
        "statusReason": None,
        "artifact": {
            "sha256": inspected.sha256,
            "size": inspected.size,
            "mediaType": inspected.media_type,
            "url": sources[0]["url"],
            "pieces": {
                "schema": "ai2apps.artifact-pieces.v1",
                "algorithm": "sha256",
                "pieceSize": piece_size,
                "hashes": piece_hashes,
            },
            "sources": sources,
        },
        "envelopeUrl": "https://coder.ai2apps.test/v1/registry/packages/example/verified-app/versions/1.2.3/envelope",
        "publisher": {
            "id": publisher_id,
            "displayName": "Fixture Publisher",
            "key": {
                "id": publisher_key_id,
                "algorithm": "Ed25519",
                "fingerprintSha256": publisher_fingerprint,
                "publicKeyPem": publisher_public,
            },
        },
    }
    repository_private, repository_public, repository_fingerprint = _repository_key()
    snapshot = _snapshot(repository_private, repository_fingerprint, release)
    return {
        "content": content,
        "envelope": envelope,
        "inspected": inspected,
        "pieceSize": piece_size,
        "repositoryPublic": repository_public,
        "repositoryFingerprint": repository_fingerprint,
        "snapshot": snapshot,
    }


def _range_response(request: httpx.Request, content: bytes) -> httpx.Response:
    value = request.headers["range"].removeprefix("bytes=")
    start_text, end_text = value.split("-", 1)
    start, end = int(start_text), int(end_text)
    piece = content[start : end + 1]
    return httpx.Response(
        206,
        content=piece,
        headers={
            "content-range": f"bytes {start}-{end}/{len(content)}",
            "content-length": str(len(piece)),
            "content-encoding": "identity",
        },
    )


@pytest.mark.asyncio
async def test_registry_multi_source_disqualifies_bad_cloud_and_uses_valid_mirror(
    tmp_path,
):
    fixture = _multi_source_download_fixture(tmp_path)
    requested_ranges: list[tuple[str, str]] = []
    progress: list[dict] = []

    def handler(request: httpx.Request):
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(
                200, json={"publicKeyPem": fixture["repositoryPublic"]}
            )
        if request.url.path.endswith("/metadata/latest"):
            return httpx.Response(200, json=fixture["snapshot"])
        if request.url.path.endswith("/envelope"):
            return httpx.Response(200, json=fixture["envelope"])
        requested_ranges.append((request.url.host, request.headers.get("range", "")))
        if request.url.host == "coder.ai2apps.test":
            return httpx.Response(200, content=fixture["content"])
        return _range_response(request, fixture["content"])

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=fixture["repositoryFingerprint"],
    )

    downloaded, _envelope, _release, _version = await manager.download_verified(
        "example", "verified-app", "1.2.3", progress=progress.append
    )

    assert downloaded.sha256 == fixture["inspected"].sha256
    assert any(host == "mirror.ai2apps.test" for host, _range in requested_ranges)
    assert all(value.startswith("bytes=") for _host, value in requested_ranges)
    assert progress[-2]["downloadMode"] == "piece_race"
    assert progress[-2]["sourceId"] == "src_mirror"
    await cloud.close()


@pytest.mark.asyncio
async def test_registry_multi_source_supports_more_than_race_concurrency(tmp_path):
    fixture = _multi_source_download_fixture(tmp_path, source_count=5)
    requested_hosts: list[str] = []

    def handler(request: httpx.Request):
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(
                200, json={"publicKeyPem": fixture["repositoryPublic"]}
            )
        if request.url.path.endswith("/metadata/latest"):
            return httpx.Response(200, json=fixture["snapshot"])
        if request.url.path.endswith("/envelope"):
            return httpx.Response(200, json=fixture["envelope"])
        requested_hosts.append(request.url.host)
        if request.url.host == "mirror-4.ai2apps.test":
            return _range_response(request, fixture["content"])
        if request.url.host == "mirror.ai2apps.test":
            return _range_response(request, b"\0" * len(fixture["content"]))
        return httpx.Response(503)

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=fixture["repositoryFingerprint"],
    )

    downloaded, _envelope, _release, _version = await manager.download_verified(
        "example", "verified-app", "1.2.3"
    )

    assert downloaded.sha256 == fixture["inspected"].sha256
    assert "mirror-4.ai2apps.test" in requested_hosts
    await cloud.close()


@pytest.mark.asyncio
async def test_registry_multi_source_does_not_wait_for_hanging_loser(tmp_path):
    fixture = _multi_source_download_fixture(tmp_path)

    class HangingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(60)
            yield b""

        async def aclose(self):
            return None

    def handler(request: httpx.Request):
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(
                200, json={"publicKeyPem": fixture["repositoryPublic"]}
            )
        if request.url.path.endswith("/metadata/latest"):
            return httpx.Response(200, json=fixture["snapshot"])
        if request.url.path.endswith("/envelope"):
            return httpx.Response(200, json=fixture["envelope"])
        if request.url.host == "coder.ai2apps.test":
            value = request.headers["range"].removeprefix("bytes=")
            start_text, end_text = value.split("-", 1)
            start, end = int(start_text), int(end_text)
            return httpx.Response(
                206,
                stream=HangingStream(),
                headers={
                    "content-range": f'bytes {start}-{end}/{len(fixture["content"])}',
                    "content-length": str(end - start + 1),
                },
            )
        return _range_response(request, fixture["content"])

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=fixture["repositoryFingerprint"],
    )

    downloaded, _envelope, _release, _version = await asyncio.wait_for(
        manager.download_verified("example", "verified-app", "1.2.3"),
        timeout=1,
    )

    assert downloaded.sha256 == fixture["inspected"].sha256
    await cloud.close()


@pytest.mark.asyncio
async def test_registry_multi_source_resumes_from_last_verified_piece(tmp_path):
    fixture = _multi_source_download_fixture(tmp_path, source_count=1)
    requested_ranges: list[str] = []
    fail_second_piece = {"value": True}

    def handler(request: httpx.Request):
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(
                200, json={"publicKeyPem": fixture["repositoryPublic"]}
            )
        if request.url.path.endswith("/metadata/latest"):
            return httpx.Response(200, json=fixture["snapshot"])
        if request.url.path.endswith("/envelope"):
            return httpx.Response(200, json=fixture["envelope"])
        requested_ranges.append(request.headers["range"])
        if (
            fail_second_piece["value"]
            and request.headers["range"].startswith(
                f'bytes={fixture["pieceSize"]}-'
            )
        ):
            return httpx.Response(503)
        return _range_response(request, fixture["content"])

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=fixture["repositoryFingerprint"],
    )

    with pytest.raises(RegistryError) as error:
        await manager.download_verified("example", "verified-app", "1.2.3")
    assert error.value.code == "artifact_sources_exhausted"
    first_range = f'bytes=0-{fixture["pieceSize"] - 1}'
    assert requested_ranges.count(first_range) == 1

    fail_second_piece["value"] = False
    downloaded, _envelope, _release, _version = await manager.download_verified(
        "example", "verified-app", "1.2.3"
    )

    assert downloaded.sha256 == fixture["inspected"].sha256
    assert requested_ranges.count(first_range) == 1
    assert not list((tmp_path / "packages" / "registry-v1" / "quarantine").glob("*.part*"))
    await cloud.close()


@pytest.mark.asyncio
async def test_registry_service_install_registers_verified_publisher_first(
    tmp_path, monkeypatch
):
    artifact_path = tmp_path / "verified-service.ai2service"
    inspected = build_package(_service_source(tmp_path), artifact_path)
    publisher_private, publisher_public, publisher_fingerprint = (
        generate_publisher_key()
    )
    publisher_id = "21bfc1af-dfbd-45fb-a648-bc3fe306b569"
    publisher_key_id = "eff821e4-7612-4c3e-9fb4-6d116e8170c3"
    envelope = create_signature_envelope(
        inspected,
        publisher_private,
        publisher_id=publisher_id,
        publisher_key_id=publisher_key_id,
    )
    release = {
        "publisher": {
            "id": publisher_id,
            "displayName": "Fixture Publisher",
            "key": {
                "id": publisher_key_id,
                "algorithm": "Ed25519",
                "fingerprintSha256": publisher_fingerprint,
                "publicKeyPem": publisher_public,
            },
        }
    }

    class Packages:
        publisher = None

        def upsert_publisher(self, **values):
            self.publisher = values

    class ServiceManager:
        def __init__(self):
            self.packages = Packages()

        async def install_verified_package(
            self, package, verification, *, approve_audit_review=False
        ):
            assert self.packages.publisher is not None
            assert package.manifest.publisher_key == (
                f"registry.{publisher_id}.{publisher_key_id}"
            )
            assert verification["publisher_id"] == publisher_id
            assert approve_audit_review is True
            return SimpleNamespace(package_digest=package.digest)

    service_manager = ServiceManager()
    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=service_manager,
        repository_fingerprint="ab" * 32,
    )

    async def downloaded(*_args, **_kwargs):
        return inspected, envelope, release, 7

    monkeypatch.setattr(manager, "download_verified", downloaded)
    record = await manager.install(
        "example", "model-fixture", "1.2.3", approve_review=True
    )

    assert record.package_digest == f"sha256:{inspected.sha256}"
    assert service_manager.packages.publisher == {
        "publisher_key": f"registry.{publisher_id}.{publisher_key_id}",
        "display_name": "Fixture Publisher",
        "key_id": publisher_key_id,
        "public_key": publisher_public,
        "trust_status": TrustStatus.TRUSTED,
        "source": "organization",
        "metadata": {
            "trust": "ai2apps-cloud-registry-v1",
            "cloud_publisher_id": publisher_id,
            "cloud_publisher_key_id": publisher_key_id,
            "fingerprint_sha256": publisher_fingerprint,
        },
    }


def test_registry_service_publisher_identity_supports_key_rotation(tmp_path):
    calls = []

    class Packages:
        def upsert_publisher(self, **values):
            calls.append(values)

    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=SimpleNamespace(packages=Packages()),
        repository_fingerprint="ab" * 32,
    )
    publisher_id = "21bfc1af-dfbd-45fb-a648-bc3fe306b569"

    def release(key_id):
        return {
            "publisher": {
                "id": publisher_id,
                "displayName": "Fixture Publisher",
                "key": {
                    "id": key_id,
                    "publicKeyPem": f"public-{key_id}",
                    "fingerprintSha256": "ab" * 32,
                },
            }
        }

    first_key = "eff821e4-7612-4c3e-9fb4-6d116e8170c3"
    second_key = "8afc0a51-f7f8-4fef-b3d0-8d30abe2a5bc"
    manager._register_service_publisher(release(first_key))
    manager._register_service_publisher(release(second_key))

    assert [item["publisher_key"] for item in calls] == [
        f"registry.{publisher_id}.{first_key}",
        f"registry.{publisher_id}.{second_key}",
    ]


def test_registry_service_bundle_normalizes_cloud_dependency_range(tmp_path):
    source = _service_source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dependencies"] = [
        {
            "packageId": "ai2apps/runtime-omlx",
            "version": ">=1.0.0 <2.0.0",
            "optional": False,
        }
    ]
    manifest_path.write_text(json.dumps(manifest))
    inspected = build_package(source, tmp_path / "service-with-runtime.ai2service")
    publisher_private, _publisher_public, _fingerprint = generate_publisher_key()
    envelope = create_signature_envelope(
        inspected,
        publisher_private,
        publisher_id="21bfc1af-dfbd-45fb-a648-bc3fe306b569",
        publisher_key_id="eff821e4-7612-4c3e-9fb4-6d116e8170c3",
    )
    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint="ab" * 32,
    )

    bundle = manager._service_bundle(inspected, envelope)

    assert bundle.manifest.dependencies[0].service_key == "ai2apps.runtime.omlx"
    assert bundle.manifest.dependencies[0].version_spec == ">=1.0.0,<2.0.0"


@pytest.mark.asyncio
async def test_registry_snapshot_rollback_is_rejected(tmp_path):
    repository_private, repository_public, repository_fingerprint = _repository_key()
    current = {
        "value": _snapshot(repository_private, repository_fingerprint, {}, version=4)
    }
    current["value"]["payload"]["releases"] = []
    # Re-sign after changing releases.
    payload = current["value"]["payload"]
    current["value"]["signature"]["value"] = (
        base64.urlsafe_b64encode(
            repository_private.sign(REPOSITORY_PREFIX + jcs_bytes(payload))
        )
        .decode()
        .rstrip("=")
    )

    def handler(request: httpx.Request):
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(200, json={"publicKeyPem": repository_public})
        return httpx.Response(200, json=current["value"])

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=repository_fingerprint,
    )
    assert (await manager.trusted_snapshot())["version"] == 4
    current["value"] = _snapshot(
        repository_private, repository_fingerprint, {}, version=3
    )
    current["value"]["payload"]["releases"] = []
    payload = current["value"]["payload"]
    current["value"]["signature"]["value"] = (
        base64.urlsafe_b64encode(
            repository_private.sign(REPOSITORY_PREFIX + jcs_bytes(payload))
        )
        .decode()
        .rstrip("=")
    )
    with pytest.raises(RegistryError) as error:
        await manager.trusted_snapshot()
    assert error.value.code == "repository_metadata_rollback"
    await cloud.close()


@pytest.mark.asyncio
async def test_publishing_workflow_proxies_cloud_state_transitions(tmp_path):
    requests: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        return httpx.Response(200, json={"id": "submission-1", "status": "ok"})

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
    )

    await manager.publishing_context()
    await manager.reauthenticate_admin("correct horse battery staple")
    await manager.publisher_submissions(limit=25)
    await manager.review_submissions(status="review_pending", limit=25)
    await manager.submission("submission-1")
    await manager.submission_details("submission-1")
    await manager.request_review("submission-1")
    await manager.review_submission("submission-1", "approved", "Verified fixture")
    await manager.review_submission("submission-1", "rejected", "Rejected fixture")
    await manager.publish_submission("submission-1")

    assert requests == [
        ("GET", "/v1/auth/me", None),
        (
            "POST",
            "/v1/admin/reauth",
            {"password": "correct horse battery staple"},
        ),
        ("GET", "/v1/publisher-submissions", None),
        ("GET", "/v1/prototype/submissions", None),
        ("GET", "/v1/submissions/submission-1", None),
        ("GET", "/v1/prototype/submissions/submission-1/details", None),
        ("POST", "/v1/prototype/submissions/submission-1/review-request", None),
        (
            "POST",
            "/v1/prototype/submissions/submission-1/reviews",
            {"decision": "approved", "note": "Verified fixture"},
        ),
        (
            "POST",
            "/v1/prototype/submissions/submission-1/reviews",
            {"decision": "rejected", "note": "Rejected fixture"},
        ),
        ("POST", "/v1/prototype/submissions/submission-1/publication", None),
    ]
    await cloud.close()


@pytest.mark.asyncio
async def test_checkpoint_publishing_workflow_proxies_cloud_state_transitions(tmp_path):
    requests: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        return httpx.Response(200, json={"id": "checkpoint-submission-1"})

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
    )
    envelope = {"schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1"}
    receipt = {
        "builder": "ai2apps-local/1",
        "fileCount": 2,
        "pieceCount": 3,
        "estimatedSizeBytes": "42",
        "verifiedProviders": ["huggingface", "modelscope"],
    }

    await manager.submit_checkpoint_distribution(envelope, receipt)
    await manager.publisher_checkpoint_submissions(limit=25)
    await manager.review_checkpoint_submissions(status="review_pending", limit=25)
    await manager.checkpoint_submission("checkpoint-submission-1")
    await manager.request_checkpoint_review("checkpoint-submission-1")
    await manager.review_checkpoint_submission(
        "checkpoint-submission-1", "approved", "Verified fixture"
    )
    await manager.publish_checkpoint_submission("checkpoint-submission-1")
    await manager.change_checkpoint_distribution_status(
        "qwen-image-2512", "yank", "Superseded"
    )

    assert requests == [
        (
            "POST",
            "/v1/checkpoint-distribution-submissions",
            {"envelope": envelope, "verificationReceipt": receipt},
        ),
        ("GET", "/v1/publisher-checkpoint-distribution-submissions", None),
        ("GET", "/v1/prototype/checkpoint-distribution-submissions", None),
        (
            "GET",
            "/v1/checkpoint-distribution-submissions/checkpoint-submission-1",
            None,
        ),
        (
            "POST",
            "/v1/prototype/checkpoint-distribution-submissions/checkpoint-submission-1/review-request",
            None,
        ),
        (
            "POST",
            "/v1/prototype/checkpoint-distribution-submissions/checkpoint-submission-1/reviews",
            {"decision": "approved", "note": "Verified fixture"},
        ),
        (
            "POST",
            "/v1/prototype/checkpoint-distribution-submissions/checkpoint-submission-1/publication",
            None,
        ),
        (
            "POST",
            "/v1/prototype/checkpoint-distributions/qwen-image-2512/yank",
            {"reason": "Superseded"},
        ),
    ]
    await cloud.close()


@pytest.mark.asyncio
async def test_platform_runtime_submission_uses_admin_large_artifact_route(tmp_path):
    source = _service_source(tmp_path)
    manifest_path = source / "ai2apps.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["package"]["id"] = "ai2apps/runtime-omlx"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    artifact_path = tmp_path / "runtime.ai2service"
    build_package(source, artifact_path)
    paths: list[str] = []

    async def handler(request: httpx.Request):
        paths.append(request.url.path)
        await request.aread()
        return httpx.Response(201, json={"id": "runtime-submission"})

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(
            MemorySecretBackend(), "https://coder.ai2apps.test"
        ),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
    )

    await manager.submit(str(artifact_path), {})

    assert paths == ["/v1/platform-runtime-submissions"]
    await cloud.close()


def test_publisher_key_listing_exposes_metadata_but_not_private_material(tmp_path):
    secrets = SimpleNamespace(
        list=lambda: (
            SimpleNamespace(
                id="sec_signing",
                name="Publisher key: Release",
                purpose="AI2Apps package signing",
                metadata={
                    "algorithm": "Ed25519",
                    "fingerprintSha256": "ab" * 32,
                    "publicKeyPem": "PUBLIC",
                },
                status="active",
                created_at=datetime(2026, 8, 14, tzinfo=UTC),
            ),
            SimpleNamespace(
                id="sec_other",
                name="Other secret",
                purpose="unrelated",
                metadata={},
                status="active",
                created_at=datetime(2026, 8, 14, tzinfo=UTC),
            ),
        )
    )
    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=secrets,
        extension_manager=None,
        service_manager=None,
    )

    assert manager.keys() == {
        "items": [
            {
                "keyRef": "sec_signing",
                "name": "Release",
                "algorithm": "Ed25519",
                "fingerprintSha256": "ab" * 32,
                "publicKeyPem": "PUBLIC",
                "status": "active",
                "createdAt": "2026-08-14T00:00:00+00:00",
            }
        ]
    }


def test_registry_manager_can_bind_request_scoped_cloud_without_splitting_state(
    tmp_path,
):
    original_cloud = object()
    browser_cloud = object()
    manager = RegistryPackageManager(
        cloud=original_cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=object(),
        service_manager=object(),
        repository_fingerprint="ab" * 32,
    )

    bound = manager.for_cloud(browser_cloud)

    assert bound is not manager
    assert bound.cloud is browser_cloud
    assert bound.root == manager.root
    assert bound.state_path == manager.state_path
    assert bound.secrets is manager.secrets
    assert bound.extension_manager is manager.extension_manager
    assert bound.service_manager is manager.service_manager


@pytest.mark.asyncio
async def test_registry_installs_required_dependency_before_root(tmp_path, monkeypatch):
    installed_order = []

    class ExtensionManager:
        async def install_verified_bundle(
            self, bundle, verification, *, approve_review=False
        ):
            installed_order.append(bundle.key)
            return SimpleNamespace(key=bundle.key)

    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=ExtensionManager(),
        service_manager=None,
        repository_fingerprint="ab" * 32,
    )
    publisher = {
        "id": "publisher",
        "displayName": "Publisher",
        "key": {
            "id": "key",
            "fingerprintSha256": "ab" * 32,
            "publicKeyPem": "PUBLIC",
        },
    }

    def inspected(package_id, version, dependencies):
        return SimpleNamespace(
            sha256=f"digest-{package_id}-{version}",
            manifest={
                "package": {
                    "id": package_id,
                    "type": "app",
                    "version": version,
                    "displayName": package_id,
                },
                "compatibility": {"ai2apps": ">=0.1.0 <2.0.0"},
                "dependencies": dependencies,
            },
        )

    async def download(namespace, name, version=None):
        package_id = f"{namespace}/{name}"
        if package_id == "example/root":
            item = inspected(
                package_id,
                "1.0.0",
                [
                    {
                        "packageId": "example/runtime",
                        "version": ">=1.0.0,<2.0.0",
                        "optional": False,
                    }
                ],
            )
        else:
            item = inspected(package_id, str(version), [])
        return item, {"payload": {}, "signature": {}}, {"publisher": publisher}, 1

    snapshot = {
        "releases": [
            {
                "packageId": "example/runtime",
                "packageType": "app",
                "version": "1.1.0",
                "status": "published",
            },
            {
                "packageId": "example/runtime",
                "packageType": "app",
                "version": "2.0.0",
                "status": "published",
            },
        ]
    }
    monkeypatch.setattr(manager, "download_verified", download)

    async def trusted_snapshot():
        return snapshot

    monkeypatch.setattr(manager, "trusted_snapshot", trusted_snapshot)
    monkeypatch.setattr(
        manager,
        "_interactive_bundle",
        lambda item, _envelope: SimpleNamespace(
            key=item.manifest["package"]["id"].replace("/", ".")
        ),
    )

    await manager.install("example", "root", "1.0.0")

    assert installed_order == ["example.runtime", "example.root"]
    assert manager.installed()[0]["packageId"] == "example/root"
    runtime = next(
        item for item in manager.installed() if item["packageId"] == "example/runtime"
    )
    assert runtime["version"] == "1.1.0"


@pytest.mark.asyncio
async def test_registry_blocks_target_before_restart_required_runtime_install(
    tmp_path, monkeypatch
):
    installs = []

    class Packages:
        @staticmethod
        def active(_key):
            return None

    class ServiceManager:
        packages = Packages()

        async def install_verified_package(self, *_args, **_kwargs):
            installs.append("service")

    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=ServiceManager(),
        repository_fingerprint="ab" * 32,
    )
    root = SimpleNamespace(
        manifest={
            "package": {
                "id": "ai2apps/model-sensevoice-small",
                "type": "service",
                "version": "0.2.0",
                "displayName": "SenseVoice Small",
            },
            "compatibility": {"ai2apps": ">=0.1.0 <2.0.0"},
            "dependencies": [
                {
                    "packageId": "ai2apps/runtime-omlx",
                    "version": ">=1.3.0 <2.0.0",
                    "optional": False,
                }
            ],
        },
        sha256="root",
    )
    release = {
        "packageId": "ai2apps/runtime-omlx",
        "packageType": "service",
        "version": "1.3.0",
        "status": "published",
        "displayName": "AI2Apps oMLX Runtime",
    }

    async def download(*_args, **_kwargs):
        return root, {"payload": {}, "signature": {}}, {"publisher": {}}, 1

    async def snapshot():
        return {"releases": [release]}

    monkeypatch.setattr(manager, "download_verified", download)
    monkeypatch.setattr(manager, "trusted_snapshot", snapshot)

    with pytest.raises(RegistryError) as blocked:
        await manager.install("ai2apps", "model-sensevoice-small", "0.2.0")

    assert blocked.value.code == "dependency_restart_required"
    assert blocked.value.details["targetPackageId"] == (
        "ai2apps/model-sensevoice-small"
    )
    assert blocked.value.details["dependency"] == {
        "packageId": "ai2apps/runtime-omlx",
        "displayName": "AI2Apps oMLX Runtime",
        "packageType": "service",
        "requiredVersion": ">=1.3.0 <2.0.0",
        "installedVersion": None,
        "activeVersion": None,
        "availableVersion": "1.3.0",
        "restartScope": "local",
        "pendingRestart": False,
    }
    assert installs == []


@pytest.mark.asyncio
async def test_registry_tells_user_to_restart_when_runtime_is_already_staged(
    tmp_path, monkeypatch
):
    class Packages:
        @staticmethod
        def active(_key):
            return SimpleNamespace(package_version="1.1.1")

    manager = RegistryPackageManager(
        cloud=None,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=SimpleNamespace(packages=Packages()),
        repository_fingerprint="ab" * 32,
    )
    manager._save_state(
        {
            "metadataVersion": 1,
            "installed": {
                "ai2apps/runtime-omlx": {
                    "packageId": "ai2apps/runtime-omlx",
                    "packageType": "service",
                    "version": "1.3.0",
                    "sha256": "new-runtime",
                    "runtimeKey": "ai2apps.runtime.omlx",
                    "activationStatus": "pending_restart",
                }
            },
        }
    )
    root = SimpleNamespace(
        manifest={
            "package": {
                "id": "ai2apps/model-sensevoice-small",
                "type": "service",
                "version": "0.2.0",
            },
            "compatibility": {"ai2apps": ">=0.1.0 <2.0.0"},
            "dependencies": [
                {
                    "packageId": "ai2apps/runtime-omlx",
                    "version": ">=1.3.0 <2.0.0",
                    "optional": False,
                }
            ],
        },
        sha256="root",
    )

    async def download(*_args, **_kwargs):
        return root, {"payload": {}, "signature": {}}, {"publisher": {}}, 1

    async def snapshot():
        return {
            "releases": [
                {
                    "packageId": "ai2apps/runtime-omlx",
                    "packageType": "service",
                    "version": "1.3.0",
                    "status": "published",
                }
            ]
        }

    monkeypatch.setattr(manager, "download_verified", download)
    monkeypatch.setattr(manager, "trusted_snapshot", snapshot)

    with pytest.raises(RegistryError) as blocked:
        await manager.install("ai2apps", "model-sensevoice-small", "0.2.0")

    dependency = blocked.value.details["dependency"]
    assert dependency["pendingRestart"] is True
    assert dependency["installedVersion"] == "1.3.0"
    assert dependency["activeVersion"] == "1.1.1"


@pytest.mark.asyncio
async def test_publishing_routes_use_the_current_browser_cloud_session():
    manager = _PublishingManager()
    runtime = SimpleNamespace(
        registry_packages=manager,
        cloud_browser_session_from_cookies=lambda cookies: cookies.get(
            "test_cloud_browser"
        ),
        cloud_for_browser=lambda session_id: f"cloud:{session_id}",
    )
    app = FastAPI()
    app.include_router(
        create_package_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        missing = await client.get("/packages/publishing/publishers")
        missing_reauth = await client.post(
            "/packages/publishing/admin/reauth",
            json={"password": "correct horse battery staple"},
        )
        browser_a = await client.get(
            "/packages/publishing/publishers",
            cookies={"test_cloud_browser": "browser_session_a_1234567890123456"},
        )
        browser_b = await client.get(
            "/packages/publishing/publishers",
            cookies={"test_cloud_browser": "browser_session_b_1234567890123456"},
        )
        reauth = await client.post(
            "/packages/publishing/admin/reauth",
            cookies={"test_cloud_browser": "browser_session_b_1234567890123456"},
            json={"password": "correct horse battery staple"},
        )

    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "cloud_browser_session_required"
    assert missing_reauth.status_code == 409
    assert missing_reauth.json()["error"]["code"] == "cloud_browser_session_required"
    assert browser_a.json() == {"cloud": "cloud:browser_session_a_1234567890123456"}
    assert browser_b.json() == {"cloud": "cloud:browser_session_b_1234567890123456"}
    assert reauth.json() == {
        "cloud": "cloud:browser_session_b_1234567890123456",
        "passwordLength": 28,
    }
    assert manager.bound_clouds == [
        "cloud:browser_session_a_1234567890123456",
        "cloud:browser_session_b_1234567890123456",
        "cloud:browser_session_b_1234567890123456",
    ]


@pytest.mark.asyncio
async def test_registry_install_operation_reports_progress_and_result():
    class InstallManager:
        async def install(
            self,
            namespace,
            name,
            version,
            *,
            approve_review,
            progress,
        ):
            progress(
                {
                    "currentStep": 2,
                    "stage": "downloading_package",
                    "packageId": f"{namespace}/{name}",
                    "bytesCompleted": 4,
                    "bytesTotal": 8,
                }
            )
            await asyncio.sleep(0)
            return SimpleNamespace(
                unit_key="example.progress-app",
                kind=SimpleNamespace(value="app"),
                version=version,
                digest="sha256:fixture",
                status=SimpleNamespace(value="active"),
                manifest={},
            )

    runtime = SimpleNamespace(registry_packages=InstallManager())
    app = FastAPI()
    app.include_router(
        create_package_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/packages/example/progress-app/install-operations",
            json={"version": "1.0.0"},
        )
        assert started.status_code == 202
        operation_id = started.json()["operationId"]
        for _ in range(10):
            status = await client.get(f"/packages/install-operations/{operation_id}")
            if status.json()["status"] == "completed":
                break
            await asyncio.sleep(0)

    payload = status.json()
    assert payload["status"] == "completed"
    assert payload["currentStep"] == 6
    assert payload["totalSteps"] == 6
    assert payload["result"]["packageId"] == "example.progress-app"


@pytest.mark.asyncio
async def test_registry_install_operation_preserves_restart_dependency_details():
    dependency = {
        "packageId": "ai2apps/runtime-omlx",
        "displayName": "AI2Apps oMLX Runtime",
        "availableVersion": "1.3.0",
        "restartScope": "local",
        "pendingRestart": False,
    }

    class InstallManager:
        async def install(self, *_args, **_kwargs):
            raise RegistryError(
                "dependency_restart_required",
                "Install or upgrade Runtime first",
                details={
                    "targetPackageId": "ai2apps/model-sensevoice-small",
                    "dependency": dependency,
                },
            )

    runtime = SimpleNamespace(registry_packages=InstallManager())
    app = FastAPI()
    app.include_router(
        create_package_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/packages/ai2apps/model-sensevoice-small/install-operations",
            json={"version": "0.2.0"},
        )
        operation_id = started.json()["operationId"]
        for _ in range(10):
            status = await client.get(f"/packages/install-operations/{operation_id}")
            if status.json()["status"] == "failed":
                break
            await asyncio.sleep(0)

    error = status.json()["error"]
    assert error["code"] == "dependency_restart_required"
    assert error["details"]["dependency"] == dependency


@pytest.mark.asyncio
async def test_registry_install_continuation_survives_restart_and_clears_on_success(
    tmp_path,
):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    dependency = {
        "packageId": "ai2apps/runtime-omlx",
        "availableVersion": "1.5.7",
        "restartScope": "local",
        "pendingRestart": False,
    }

    class BlockedManager:
        async def install(self, *_args, **_kwargs):
            raise RegistryError(
                "dependency_restart_required",
                "Install or upgrade Runtime first",
                details={"dependency": dependency},
            )

    first_app = FastAPI()
    first_app.include_router(
        create_package_router(
            lambda: SimpleNamespace(
                registry_packages=BlockedManager(), database=database
            ),
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=first_app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/packages/ai2apps/model-sensevoice-small/install-operations",
            json={"version": "0.2.0"},
        )
        operation_id = started.json()["operationId"]
        for _ in range(10):
            status = await client.get(f"/packages/install-operations/{operation_id}")
            if status.json()["status"] == "failed":
                break
            await asyncio.sleep(0)
        continuation = await client.get("/packages/install-continuation")

    pending = continuation.json()["continuation"]
    assert pending["packageId"] == "ai2apps/model-sensevoice-small"
    assert pending["version"] == "0.2.0"
    assert pending["approveReview"] is False
    assert pending["dependency"] == dependency
    assert pending["createdAt"].endswith("Z")
    assert pending["updatedAt"].endswith("Z")

    class RuntimeManager:
        async def install(self, _namespace, _name, version, **_kwargs):
            return SimpleNamespace(
                package_version=version,
                package_digest="sha256:runtime",
                service_key="ai2apps.runtime.omlx",
                status=SimpleNamespace(value="installed"),
                manifest={},
            )

    runtime_app = FastAPI()
    runtime_app.include_router(
        create_package_router(
            lambda: SimpleNamespace(
                registry_packages=RuntimeManager(), database=database
            ),
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=runtime_app), base_url="http://test"
    ) as client:
        started = await client.post(
            "/packages/ai2apps/runtime-omlx/install-operations",
            json={"version": "1.5.7"},
        )
        operation_id = started.json()["operationId"]
        for _ in range(10):
            status = await client.get(f"/packages/install-operations/{operation_id}")
            if status.json()["status"] == "completed":
                break
            await asyncio.sleep(0)
        still_pending = await client.get("/packages/install-continuation")

    assert status.json()["result"]["restartRequired"] is True
    assert still_pending.json()["continuation"]["packageId"] == (
        "ai2apps/model-sensevoice-small"
    )

    class ResumedManager:
        async def install(self, _namespace, _name, version, **_kwargs):
            return SimpleNamespace(
                package_version=version,
                package_digest="sha256:resumed",
                service_key="ai2apps.model.sensevoice-small",
                status=SimpleNamespace(value="active"),
                manifest={},
            )

    restarted_app = FastAPI()
    restarted_app.include_router(
        create_package_router(
            lambda: SimpleNamespace(
                registry_packages=ResumedManager(), database=database
            ),
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=restarted_app), base_url="http://test"
    ) as client:
        restored = await client.get("/packages/install-continuation")
        assert restored.json()["continuation"]["packageId"] == (
            "ai2apps/model-sensevoice-small"
        )
        started = await client.post(
            "/packages/ai2apps/model-sensevoice-small/install-operations",
            json={"version": "0.2.0"},
        )
        operation_id = started.json()["operationId"]
        for _ in range(10):
            status = await client.get(f"/packages/install-operations/{operation_id}")
            if status.json()["status"] == "completed":
                break
            await asyncio.sleep(0)
        cleared = await client.get("/packages/install-continuation")

    assert status.json()["status"] == "completed"
    assert cleared.json() == {"continuation": None}
