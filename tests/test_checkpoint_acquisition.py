from __future__ import annotations

import hashlib
from types import SimpleNamespace

import httpx
import pytest

from ai2apps.checkpoint_acquisition import CheckpointAcquisitionService
from ai2apps.checkpoint_distribution import (
    CheckpointCache,
    CheckpointConsentRequiredError,
    CheckpointDownloadError,
    parse_checkpoint_distribution_manifest,
)
from ai2apps.checkpoint_paths import checkpoint_distribution_cache_key


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _manifest(payload: bytes):
    return parse_checkpoint_distribution_manifest(
        {
            "schemaVersion": 1,
            "distributionId": "dist_acquire_test",
            "modelId": "ai2apps.model/test",
            "repoId": "publisher/model",
            "revision": "a" * 40,
            "format": "safetensors",
            "quantization": "mlx-4bit",
            "estimatedSizeBytes": len(payload),
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
                    "size": len(payload),
                    "sha256": _sha(payload),
                }
            ],
            "pieceSize": 1024 * 1024,
            "pieceHashes": [_sha(payload)],
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
    )


def _conditional_manifest(payload: bytes):
    value = _manifest(payload).raw
    value["license"].update(
        redistributionPolicy="conditional",
        redistributionConditions={
            "termsAcceptance": "required",
            "licenseDelivery": "required",
            "downstreamTerms": "license_terms",
            "commercialUse": "separate_license_required",
            "attribution": {
                "required": True,
                "noticeText": "Required notice",
                "noticeFile": "NOTICE",
                "productDisplay": "required",
            },
            "modifiedFilesNotice": "required",
        },
        downloadConsent={
            "required": True,
            "attestationText": "I accept or obtained a separate license.",
            "acceptanceOptions": [
                "accepted_license_terms",
                "obtained_separate_license",
            ],
        },
    )
    return parse_checkpoint_distribution_manifest(value)


@pytest.mark.asyncio
async def test_acquisition_builds_snapshot_then_reuses_it_without_hub_io(tmp_path):
    payload = b"checkpoint"
    manifest = _manifest(payload)
    registry = SimpleNamespace(distribution=lambda _distribution_id: None)

    async def distribution(_distribution_id):
        return manifest

    registry.distribution = distribution
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        value = request.headers["Range"]
        start, end = (int(item) for item in value.removeprefix("bytes=").split("-"))
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
            content=payload[start : end + 1],
        )

    service = CheckpointAcquisitionService(
        registry=registry,
        cache=CheckpointCache(tmp_path / "cache"),
        transport=httpx.MockTransport(respond),
    )
    progress = []

    downloaded = await service.acquire(
        manifest.distribution_id, progress=progress.append
    )
    request_count = len(requests)
    cached = await service.acquire(manifest.distribution_id)

    assert downloaded.cache_hit is False
    assert downloaded.source_bytes == {"modelscope": len(payload)}
    assert progress[-1]["fileName"] == "model.safetensors"
    assert progress[-1]["bytesCompleted"] == len(payload)
    assert progress[-1]["bytesTotal"] == len(payload)
    assert (downloaded.snapshot / "model.safetensors").read_bytes() == payload
    assert cached.cache_hit is True
    assert cached.snapshot == downloaded.snapshot
    assert len(requests) == request_count

    worker_snapshot = service.materialize_worker_snapshot(cached, tmp_path / "hub")
    assert (
        worker_snapshot
        == (
            tmp_path
            / "hub/models--publisher--model/distributions"
            / checkpoint_distribution_cache_key("dist_acquire_test")
        ).resolve()
    )
    assert (worker_snapshot / "model.safetensors").read_bytes() == payload
    assert (
        service.materialize_worker_snapshot(cached, tmp_path / "hub") == worker_snapshot
    )


@pytest.mark.asyncio
async def test_conditional_acquisition_requires_consent_before_any_checkpoint_io(
    tmp_path,
):
    payload = b"checkpoint"
    manifest = _conditional_manifest(payload)

    async def distribution(_distribution_id):
        return manifest

    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        value = request.headers["Range"]
        start, end = (int(item) for item in value.removeprefix("bytes=").split("-"))
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
            content=payload[start : end + 1],
        )

    service = CheckpointAcquisitionService(
        registry=SimpleNamespace(distribution=distribution),
        cache=CheckpointCache(tmp_path / "cache"),
        transport=httpx.MockTransport(respond),
    )

    with pytest.raises(CheckpointConsentRequiredError):
        await service.acquire(manifest.distribution_id)
    assert requests == []

    result = await service.acquire(
        manifest.distribution_id,
        license_consent={
            "distributionId": manifest.distribution_id,
            "manifestDigest": manifest.digest,
            "termsHash": _sha(b"terms"),
            "decision": "accepted_license_terms",
            "confirmed": True,
        },
    )
    assert result.cache_hit is False
    assert requests


@pytest.mark.asyncio
async def test_acquisition_imports_matching_local_snapshot_without_hub_io(tmp_path):
    payload = b"checkpoint"
    manifest = _manifest(payload)

    async def distribution(_distribution_id):
        return manifest

    def reject_request(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("matching local snapshot must avoid Hub I/O")

    local = tmp_path / manifest.revision
    local.mkdir()
    (local / "model.safetensors").write_bytes(payload)
    service = CheckpointAcquisitionService(
        registry=SimpleNamespace(distribution=distribution),
        cache=CheckpointCache(tmp_path / "cache"),
        transport=httpx.MockTransport(reject_request),
    )

    imported = await service.acquire(
        manifest.distribution_id, local_snapshot=local
    )

    assert imported.cache_hit is True
    assert imported.source_bytes == {}
    assert (imported.snapshot / "model.safetensors").read_bytes() == payload


@pytest.mark.asyncio
async def test_acquisition_honors_source_disable_policy(tmp_path):
    manifest = _manifest(b"checkpoint")

    async def distribution(_distribution_id):
        return manifest

    service = CheckpointAcquisitionService(
        registry=SimpleNamespace(distribution=distribution),
        cache=CheckpointCache(tmp_path / "cache"),
    )

    with pytest.raises(CheckpointDownloadError, match="all checkpoint sources"):
        await service.acquire(
            manifest.distribution_id,
            disabled_sources=frozenset({"modelscope"}),
        )


def test_worker_snapshot_rejects_repository_symlink_escape(tmp_path):
    manifest = _manifest(b"checkpoint")
    hub = tmp_path / "hub"
    hub.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (hub / "models--publisher--model").symlink_to(outside, target_is_directory=True)
    service = CheckpointAcquisitionService(
        registry=SimpleNamespace(), cache=CheckpointCache(tmp_path / "cache")
    )

    with pytest.raises(CheckpointDownloadError, match="escapes"):
        service.materialize_worker_snapshot(
            SimpleNamespace(manifest=manifest, snapshot=tmp_path / "unused"), hub
        )
