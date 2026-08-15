from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.cloud_client import AI2AppsCloudClient, CloudSessionStore
from ai2apps.packages.contract_v1 import (
    REPOSITORY_PREFIX,
    build_package,
    create_signature_envelope,
    generate_publisher_key,
    jcs_bytes,
    public_key_fingerprint,
)
from ai2apps.packages.registry import RegistryError, RegistryPackageManager
from ai2apps.secrets import MemorySecretBackend


class _Secrets:
    pass


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


def _repository_key():
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    fingerprint = public_key_fingerprint(public_pem)
    return private, public_pem, fingerprint


def _snapshot(private, fingerprint, release, version=7):
    now = datetime.now(timezone.utc)
    payload = {
        "domain": "ai2apps.repository-snapshot.v1",
        "version": version,
        "generatedAt": now.isoformat().replace("+00:00", "Z"),
        "expiresAt": (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z"),
        "releases": [release],
    }
    signature = base64.urlsafe_b64encode(
        private.sign(REPOSITORY_PREFIX + jcs_bytes(payload))
    ).decode().rstrip("=")
    return {
        "schemaVersion": "ai2apps.repository-snapshot-envelope.v1",
        "payload": payload,
        "signature": {"keyId": fingerprint, "algorithm": "Ed25519", "value": signature},
    }


@pytest.mark.asyncio
async def test_registry_download_verifies_snapshot_publisher_and_bytes(tmp_path):
    artifact_path = tmp_path / "verified.ai2app"
    inspected = build_package(_source(tmp_path), artifact_path)
    publisher_private, publisher_public, publisher_fingerprint = generate_publisher_key()
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
            return httpx.Response(200, content=artifact_path.read_bytes(), headers={"content-type": inspected.media_type})
        raise AssertionError(request.url)

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(MemorySecretBackend(), "https://coder.ai2apps.test"),
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
    downloaded, downloaded_envelope, downloaded_release, metadata_version = await manager.download_verified(
        "example", "verified-app", "1.2.3"
    )
    assert downloaded.sha256 == inspected.sha256
    assert downloaded_envelope == envelope
    assert downloaded_release["publisher"]["displayName"] == "Fixture Publisher"
    assert metadata_version == 7
    runtime_bundle = manager._interactive_bundle(downloaded, envelope)
    assert runtime_bundle.key == "example.verified-app"
    assert runtime_bundle.manifest["id"] == "example.verified-app"
    await cloud.close()


@pytest.mark.asyncio
async def test_registry_snapshot_rollback_is_rejected(tmp_path):
    repository_private, repository_public, repository_fingerprint = _repository_key()
    current = {"value": _snapshot(repository_private, repository_fingerprint, {}, version=4)}
    current["value"]["payload"]["releases"] = []
    # Re-sign after changing releases.
    payload = current["value"]["payload"]
    current["value"]["signature"]["value"] = base64.urlsafe_b64encode(
        repository_private.sign(REPOSITORY_PREFIX + jcs_bytes(payload))
    ).decode().rstrip("=")

    def handler(request: httpx.Request):
        if request.url.path.endswith("/repository-key"):
            return httpx.Response(200, json={"publicKeyPem": repository_public})
        return httpx.Response(200, json=current["value"])

    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(MemorySecretBackend(), "https://coder.ai2apps.test"),
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
    current["value"] = _snapshot(repository_private, repository_fingerprint, {}, version=3)
    current["value"]["payload"]["releases"] = []
    payload = current["value"]["payload"]
    current["value"]["signature"]["value"] = base64.urlsafe_b64encode(
        repository_private.sign(REPOSITORY_PREFIX + jcs_bytes(payload))
    ).decode().rstrip("=")
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
        session_store=CloudSessionStore(MemorySecretBackend(), "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=tmp_path / "packages",
        secrets=_Secrets(),
        extension_manager=None,
        service_manager=None,
    )

    await manager.submissions(status="review_pending", limit=25)
    await manager.submission("submission-1")
    await manager.submission_details("submission-1")
    await manager.request_review("submission-1")
    await manager.review_submission("submission-1", "approved", "Verified fixture")
    await manager.publish_submission("submission-1")

    assert requests == [
        ("GET", "/v1/prototype/submissions", None),
        ("GET", "/v1/submissions/submission-1", None),
        ("GET", "/v1/prototype/submissions/submission-1/details", None),
        ("POST", "/v1/prototype/submissions/submission-1/review-request", None),
        (
            "POST",
            "/v1/prototype/submissions/submission-1/reviews",
            {"decision": "approved", "note": "Verified fixture"},
        ),
        ("POST", "/v1/prototype/submissions/submission-1/publication", None),
    ]
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
                created_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                id="sec_other",
                name="Other secret",
                purpose="unrelated",
                metadata={},
                status="active",
                created_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
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
