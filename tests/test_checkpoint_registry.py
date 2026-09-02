from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.checkpoint_distribution import parse_checkpoint_distribution_manifest
from ai2apps.checkpoint_registry import (
    CheckpointRegistryClient,
    CheckpointRegistryError,
)
from ai2apps.packages.contract_v1 import jcs_bytes, public_key_fingerprint


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sign(private: Ed25519PrivateKey, prefix: bytes, payload: dict) -> str:
    return (
        base64.urlsafe_b64encode(private.sign(prefix + jcs_bytes(payload)))
        .decode("ascii")
        .rstrip("=")
    )


def _fixture(
    *, version: int = 1, expired: bool = False, envelope_url: str | None = None
):
    publisher_private = Ed25519PrivateKey.generate()
    publisher_public = (
        publisher_private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    publisher_fingerprint = public_key_fingerprint(publisher_public)
    payload_bytes = b"checkpoint"
    manifest_raw = {
        "schemaVersion": 1,
        "distributionId": "dist_registry_test",
        "modelId": "ai2apps.model/test",
        "repoId": "publisher/model",
        "revision": "a" * 40,
        "format": "safetensors",
        "quantization": "mlx-4bit",
        "estimatedSizeBytes": len(payload_bytes),
        "license": {
            "id": "LicenseRef-Test",
            "name": "Test License",
            "termsUrl": "https://example.test/terms",
            "termsHash": _sha(b"terms"),
            "usagePolicy": "personal_noncommercial",
            "accessPolicy": "user_attestation_required",
            "redistributionPolicy": "prohibited",
        },
        "files": [
            {
                "path": "model.safetensors",
                "size": len(payload_bytes),
                "sha256": _sha(payload_bytes),
            }
        ],
        "pieceSize": 1024 * 1024,
        "pieceHashes": [_sha(payload_bytes)],
        "distribution": {
            "p2p": {"allowed": False},
            "sources": [
                {
                    "type": "modelscope",
                    "repoId": "publisher/model-ms",
                    "revision": "release-1",
                    "path": "model.safetensors",
                    "access": "public_anonymous",
                    "verified": True,
                }
            ],
            "managedSources": [],
        },
    }
    manifest = parse_checkpoint_distribution_manifest(manifest_raw)
    distribution_payload = {
        "domain": "ai2apps.checkpoint-distribution.v1",
        "publisherId": "publisher.test",
        "publisherKeyId": publisher_fingerprint,
        "manifestDigest": manifest.digest,
        "manifest": manifest.raw,
    }
    distribution_envelope = {
        "schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1",
        "payload": distribution_payload,
        "signature": {
            "keyId": publisher_fingerprint,
            "algorithm": "Ed25519",
            "value": _sign(
                publisher_private,
                b"AI2APPS-CHECKPOINT-DISTRIBUTION-V1\n",
                distribution_payload,
            ),
        },
    }

    repository_private = Ed25519PrivateKey.generate()
    repository_public = (
        repository_private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    repository_fingerprint = public_key_fingerprint(repository_public)
    now = datetime.now(UTC)
    index_payload = {
        "domain": "ai2apps.checkpoint-index.v1",
        "version": version,
        "generatedAt": (now - timedelta(minutes=1)).isoformat(),
        "expiresAt": (
            now - timedelta(minutes=1) if expired else now + timedelta(days=1)
        ).isoformat(),
        "distributions": [
            {
                "distributionId": manifest.distribution_id,
                "status": "published",
                "envelopeUrl": envelope_url
                or f"/v1/checkpoint-distributions/{manifest.distribution_id}",
                "manifestDigest": manifest.digest,
                "publisher": {
                    "id": "publisher.test",
                    "key": {
                        "id": publisher_fingerprint,
                        "fingerprintSha256": publisher_fingerprint,
                        "publicKeyPem": publisher_public,
                    },
                },
            }
        ],
    }
    index_envelope = {
        "schemaVersion": "ai2apps.checkpoint-index-envelope.v1",
        "payload": index_payload,
        "signature": {
            "keyId": repository_fingerprint,
            "algorithm": "Ed25519",
            "value": _sign(
                repository_private,
                b"AI2APPS-CHECKPOINT-INDEX-V1\n",
                index_payload,
            ),
        },
    }
    return {
        "manifest": manifest,
        "distribution": distribution_envelope,
        "index": index_envelope,
        "repository_public": repository_public,
        "repository_fingerprint": repository_fingerprint,
    }


class _Cloud:
    base_url = "https://cloud.example"

    def __init__(self, fixture: dict):
        self.fixture = fixture
        self.offline = False
        self.paths: list[str] = []

    async def request(self, _method: str, path: str):
        self.paths.append(path)
        if self.offline:
            raise httpx.ConnectError("offline")
        values = {
            "/v1/registry/repository-key": {
                "publicKeyPem": self.fixture["repository_public"]
            },
            "/v1/checkpoint-distributions/index/latest": self.fixture["index"],
            "/v1/checkpoint-distributions/dist_registry_test": self.fixture[
                "distribution"
            ],
        }
        return httpx.Response(
            200,
            json=values[path],
            request=httpx.Request("GET", self.base_url + path),
        )


@pytest.mark.asyncio
async def test_registry_fetches_then_uses_current_signed_cache_offline(
    tmp_path,
) -> None:
    fixture = _fixture()
    cloud = _Cloud(fixture)
    client = CheckpointRegistryClient(
        cloud=cloud,
        root=tmp_path,
        repository_fingerprint=fixture["repository_fingerprint"],
    )

    online = await client.distribution("dist_registry_test")
    cloud.offline = True
    offline = await client.distribution("dist_registry_test")

    assert online.digest == fixture["manifest"].digest
    assert offline.digest == online.digest
    assert cloud.paths.count("/v1/checkpoint-distributions/dist_registry_test") == 1


@pytest.mark.asyncio
async def test_registry_rejects_metadata_version_rollback(tmp_path) -> None:
    current = _fixture(version=2)
    cloud = _Cloud(current)
    client = CheckpointRegistryClient(
        cloud=cloud,
        root=tmp_path,
        repository_fingerprint=current["repository_fingerprint"],
    )
    await client.trusted_index()
    # Simulate a locally observed newer generation; the still-valid signed v2
    # response must not move state back from v3.
    client._atomic_json(client.state_path, {"version": 3})

    with pytest.raises(CheckpointRegistryError, match="moved backwards"):
        await client.trusted_index()


@pytest.mark.asyncio
async def test_registry_rejects_cross_origin_distribution_url(tmp_path) -> None:
    fixture = _fixture(
        envelope_url="https://evil.example/v1/checkpoint-distributions/x"
    )
    client = CheckpointRegistryClient(
        cloud=_Cloud(fixture),
        root=tmp_path,
        repository_fingerprint=fixture["repository_fingerprint"],
    )

    with pytest.raises(CheckpointRegistryError, match="changes Cloud origin"):
        await client.distribution("dist_registry_test")


@pytest.mark.asyncio
async def test_registry_does_not_use_expired_cached_index_offline(tmp_path) -> None:
    valid = _fixture()
    cloud = _Cloud(valid)
    client = CheckpointRegistryClient(
        cloud=cloud,
        root=tmp_path,
        repository_fingerprint=valid["repository_fingerprint"],
    )
    await client.trusted_index()
    expired = _fixture(expired=True)
    client._atomic_json(
        client.index_cache_path,
        {
            "publicKeyPem": expired["repository_public"],
            "envelope": expired["index"],
        },
    )
    client.repository_fingerprint = expired["repository_fingerprint"]
    cloud.offline = True

    with pytest.raises(CheckpointRegistryError, match="expired"):
        await client.trusted_index()
