from __future__ import annotations

import asyncio
import copy
import hashlib
from types import SimpleNamespace
from pathlib import Path

import httpx
import pytest

import ai2apps.checkpoint_distribution as checkpoint_distribution
from ai2apps.checkpoint_acquisition import CheckpointAcquisitionService, _download_hf_token
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
@pytest.mark.parametrize("mode", ["default", "explicit", "missing", "denied", "timeout", "all_failed", "isolated"])
async def test_hf_credentials_and_source_fallback(tmp_path, monkeypatch, mode):
    import huggingface_hub

    monkeypatch.setenv("AI2APPS_SUPERVISED", "helper")
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    if mode == "isolated":
        token_file = tmp_path / ".cache/huggingface/token"
        token_file.parent.mkdir(parents=True)
        token_file.write_text("test-default-token\n")

    payload = b"checkpoint"
    raw = copy.deepcopy(_manifest(payload).raw)
    raw["distribution"]["sources"].insert(0, {
        "type": "huggingface", "repoId": "publisher/model",
        "revision": "a" * 40, "path": "model.safetensors",
        "access": "gated_user_token", "verified": True,
    })
    manifest = parse_checkpoint_distribution_manifest(raw)
    default_calls = []

    def get_token():
        default_calls.append(True)
        return None if mode in {"missing", "isolated"} else "test-default-token"

    monkeypatch.setattr(huggingface_hub, "get_token", get_token)

    async def distribution(_):
        return manifest

    requests = []

    def respond(request):
        requests.append(request)
        if request.url.host == "huggingface.co":
            assert request.headers["Authorization"] == (
                "Bearer test-explicit-token" if mode == "explicit" else "Bearer test-default-token"
            )
            if mode == "timeout":
                raise httpx.ReadTimeout("simulated", request=request)
            if mode in {"denied", "all_failed"}:
                return httpx.Response(403)
        else:
            assert "Authorization" not in request.headers
            if mode == "all_failed":
                return httpx.Response(503)
        start, end = map(int, request.headers["Range"].removeprefix("bytes=").split("-"))
        return httpx.Response(206, headers={
            "Content-Range": f"bytes {start}-{end}/{len(payload)}"
        }, content=payload[start:end + 1])

    service = CheckpointAcquisitionService(
        registry=SimpleNamespace(distribution=distribution),
        cache=CheckpointCache(tmp_path / "cache"),
        transport=httpx.MockTransport(respond),
    )
    progress = []
    if mode == "all_failed":
        with pytest.raises(CheckpointDownloadError):
            await service.acquire(manifest.distribution_id, progress=progress.append)
        return
    result = await service.acquire(
        manifest.distribution_id, progress=progress.append,
        hf_token="test-explicit-token" if mode == "explicit" else None,
    )
    assert (result.snapshot / "model.safetensors").read_bytes() == payload
    assert bool(default_calls) == (mode != "explicit")
    if mode in {"missing", "denied", "timeout"}:
        assert result.source_bytes == {"modelscope": len(payload)}
        assert len(progress[-1]["download"]["warnings"]) == 1
    if mode == "missing":
        assert all(r.url.host != "huggingface.co" for r in requests)
    assert "test-default-token" not in str(progress)
    assert "test-explicit-token" not in str(progress)


@pytest.mark.parametrize("contents", ["", "bad\nvalue", "x" * 17000, "\udcff"])
def test_user_hf_token_invalid_is_ignored(tmp_path, monkeypatch, contents):
    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    monkeypatch.setenv("AI2APPS_SUPERVISED", "helper")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    token_file = tmp_path / "huggingface/token"
    token_file.parent.mkdir()
    token_file.write_bytes(contents.encode("utf-8", errors="surrogateescape"))
    assert _download_hf_token() is None


def test_user_hf_token_fallback_is_read_only_and_lower_priority(tmp_path, monkeypatch):
    import huggingface_hub
    monkeypatch.setenv("AI2APPS_SUPERVISED", "helper")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    token_file = tmp_path / "huggingface/token"
    token_file.parent.mkdir()
    token_file.write_text("user-token\n")
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: "app-token")
    assert _download_hf_token() == "app-token"
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    assert _download_hf_token() == "user-token"
    assert token_file.read_text() == "user-token\n"
    monkeypatch.delenv("AI2APPS_SUPERVISED")
    assert _download_hf_token() is None


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
async def test_acquisition_reuses_identical_blobs_across_distribution_identities(
    tmp_path,
):
    payload = b"shared checkpoint bytes"
    first = _manifest(payload)
    second_raw = copy.deepcopy(first.raw)
    second_raw["distributionId"] = "dist_acquire_alias"
    second_raw["modelId"] = "ai2apps.model/another-package"
    second = parse_checkpoint_distribution_manifest(second_raw)

    async def distribution(distribution_id):
        return {
            first.distribution_id: first,
            second.distribution_id: second,
        }[distribution_id]

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
    await service.acquire(first.distribution_id)
    request_count = len(requests)

    reused = await service.acquire(second.distribution_id)

    assert reused.cache_hit is True
    assert reused.source_bytes == {}
    assert reused.manifest.distribution_id == second.distribution_id
    assert (reused.snapshot / "model.safetensors").read_bytes() == payload
    assert len(requests) == request_count


@pytest.mark.asyncio
async def test_concurrent_instances_share_one_checkpoint_download(tmp_path):
    payload = b"machine-shared-checkpoint"
    manifest = _manifest(payload)

    async def distribution(_distribution_id):
        return manifest

    baseline_requests = []
    requests = []

    async def baseline_respond(request: httpx.Request) -> httpx.Response:
        baseline_requests.append(request)
        value = request.headers["Range"]
        start, end = (
            int(item) for item in value.removeprefix("bytes=").split("-")
        )
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
            content=payload[start : end + 1],
        )

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        await asyncio.sleep(0.05)
        value = request.headers["Range"]
        start, end = (
            int(item) for item in value.removeprefix("bytes=").split("-")
        )
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
            content=payload[start : end + 1],
        )

    baseline_service = CheckpointAcquisitionService(
        registry=SimpleNamespace(distribution=distribution),
        cache=CheckpointCache(tmp_path / "baseline-checkpoint-cache"),
        transport=httpx.MockTransport(baseline_respond),
    )
    baseline = await baseline_service.acquire(manifest.distribution_id)

    shared_root = tmp_path / "shared-checkpoint-cache"
    services = [
        CheckpointAcquisitionService(
            registry=SimpleNamespace(distribution=distribution),
            cache=CheckpointCache(shared_root),
            transport=httpx.MockTransport(respond),
        )
        for _ in range(2)
    ]

    results = await asyncio.gather(
        *(service.acquire(manifest.distribution_id) for service in services)
    )

    assert sorted(result.cache_hit for result in results) == [False, True]
    assert baseline.cache_hit is False
    assert len(requests) == len(baseline_requests)
    assert results[0].snapshot == results[1].snapshot
    assert (results[0].snapshot / "model.safetensors").read_bytes() == payload


@pytest.mark.asyncio
async def test_shared_cache_imports_legacy_instance_snapshot_without_network(
    tmp_path,
):
    payload = b"legacy-instance-checkpoint"
    manifest = _manifest(payload)
    source = tmp_path / "source"
    source.mkdir()
    (source / "model.safetensors").write_bytes(payload)
    legacy = CheckpointCache(tmp_path / "legacy-cache")
    legacy.import_local_snapshot(manifest, source)

    async def distribution(_distribution_id):
        return manifest

    def reject_network(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("legacy checkpoint import must not access the network")

    service = CheckpointAcquisitionService(
        registry=SimpleNamespace(distribution=distribution),
        cache=CheckpointCache(tmp_path / "shared-cache"),
        legacy_caches=(legacy,),
        transport=httpx.MockTransport(reject_network),
    )

    result = await service.acquire(manifest.distribution_id)

    assert result.cache_hit is True
    assert result.source_bytes == {}
    assert (result.snapshot / "model.safetensors").read_bytes() == payload


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


def test_verified_snapshot_receipt_avoids_rehash_and_detects_changes(
    tmp_path, monkeypatch
):
    payload = b"checkpoint"
    manifest = _manifest(payload)
    source = tmp_path / "source"
    source.mkdir()
    (source / "model.safetensors").write_bytes(payload)
    cache = CheckpointCache(tmp_path / "cache")
    snapshot = cache.import_local_snapshot(manifest, source)

    assert (snapshot / ".ai2apps/verification.json").is_file()
    with monkeypatch.context() as context:
        context.setattr(
            checkpoint_distribution,
            "_sha256_file",
            lambda _path: (_ for _ in ()).throw(
                AssertionError("verified snapshot must use its receipt")
            ),
        )
        assert cache.verified_snapshot(manifest) == snapshot
        worker = cache.materialize_snapshot_view(
            manifest, snapshot, tmp_path / "worker"
        )
        assert (worker / "model.safetensors").read_bytes() == payload

    checkpoint = snapshot / "model.safetensors"
    checkpoint.chmod(0o644)
    checkpoint.write_bytes(b"checkpoinx")
    checkpoint.chmod(0o444)
    assert cache.verified_snapshot(manifest) is None
