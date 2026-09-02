from __future__ import annotations

import base64
import builtins
import hashlib

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.checkpoint_distribution import (
    CheckpointCache,
    CheckpointConsentRequiredError,
    CheckpointDownloadError,
    CheckpointManifestError,
    CheckpointSource,
    HTTPRangePieceSource,
    HubSourceResolver,
    PieceCompletionMap,
    PieceDownloadScheduler,
    SourceCapability,
    checkpoint_license_consent_challenge,
    parse_checkpoint_distribution_manifest,
    plan_checkpoint_pieces,
    require_checkpoint_license_consent,
    verify_checkpoint_distribution_envelope,
    verify_checkpoint_manifest_signature,
)
from ai2apps.packages.contract_v1 import jcs_bytes, public_key_fingerprint


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _manifest(payload: bytes = b"checkpoint") -> dict:
    return {
        "schemaVersion": 1,
        "distributionId": "dist_test_v1",
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
            {"path": "model.safetensors", "size": len(payload), "sha256": _sha(payload)}
        ],
        "pieceSize": 1024 * 1024,
        "pieceHashes": [_sha(payload)],
        "distribution": {
            "p2p": {"allowed": False},
            "sources": [
                {
                    "type": "modelscope",
                    "repoId": "publisher/model-ms",
                    "revision": "release-2026-08-26",
                    "path": "model.safetensors",
                    "access": "public_anonymous",
                    "verified": True,
                },
                {
                    "type": "huggingface",
                    "repoId": "publisher/model",
                    "revision": "a" * 40,
                    "path": "model.safetensors",
                    "access": "public_anonymous",
                    "verified": True,
                },
            ],
            "managedSources": [],
        },
    }


def _multi_file_manifest(first: bytes, second: bytes) -> dict:
    piece_size = 1024 * 1024
    stream = first + second
    value = _manifest(stream)
    value["estimatedSizeBytes"] = len(stream)
    value["files"] = [
        {"path": "first.bin", "size": len(first), "sha256": _sha(first)},
        {"path": "nested/second.bin", "size": len(second), "sha256": _sha(second)},
    ]
    value["pieceSize"] = piece_size
    value["pieceHashes"] = [
        _sha(stream[offset : offset + piece_size])
        for offset in range(0, len(stream), piece_size)
    ]
    value["distribution"]["sources"] = [
        {
            "type": provider,
            "repoId": f"publisher/model-{provider}",
            "revision": "a" * 40 if provider == "huggingface" else "release-1",
            "path": path,
            "access": "public_anonymous",
            "verified": True,
        }
        for path in ("first.bin", "nested/second.bin")
        for provider in ("modelscope", "huggingface")
    ]
    return value


def _conditional_manifest() -> dict:
    value = _manifest()
    value["license"].update(
        redistributionPolicy="conditional",
        redistributionConditions={
            "termsAcceptance": "required",
            "licenseDelivery": "required",
            "downstreamTerms": "same_or_more_restrictive",
            "commercialUse": "separate_license_required",
            "attribution": {
                "required": True,
                "noticeText": "Required model notice",
                "noticeFile": "NOTICE",
                "productDisplay": "not_required",
            },
            "modifiedFilesNotice": "required",
        },
        downloadConsent={
            "required": True,
            "attestationText": "I accept the terms or obtained a separate license.",
            "acceptanceOptions": [
                "accepted_license_terms",
                "obtained_separate_license",
            ],
        },
    )
    return value


class _MemoryPieceSource:
    def __init__(
        self,
        provider: str,
        file_path: str,
        payload: bytes,
        *,
        latency_ms: float,
        corrupt: bool = False,
        fail: bool = False,
    ) -> None:
        self.provider = provider
        self.file_path = file_path
        self.payload = payload
        self.latency_ms = latency_ms
        self.corrupt = corrupt
        self.fail = fail
        self.requests: list[tuple[int, int]] = []

    async def probe(self) -> SourceCapability:
        return SourceCapability(
            available=True,
            range_supported=True,
            content_length=len(self.payload),
            latency_ms=self.latency_ms,
        )

    async def fetch_piece(self, file_path: str, offset: int, length: int) -> bytes:
        assert file_path == self.file_path
        self.requests.append((offset, length))
        if self.fail:
            raise OSError("source unavailable")
        payload = self.payload[offset : offset + length]
        if self.corrupt and payload:
            payload = bytes([payload[0] ^ 0xFF]) + payload[1:]
        return payload


def test_manifest_parses_verified_ms_hf_sources() -> None:
    manifest = parse_checkpoint_distribution_manifest(_manifest())

    assert manifest.digest.startswith("sha256:")
    assert {source.provider for source in manifest.sources} == {
        "modelscope",
        "huggingface",
    }


def test_conditional_manifest_requires_exact_manifest_bound_consent() -> None:
    manifest = parse_checkpoint_distribution_manifest(_conditional_manifest())
    challenge = checkpoint_license_consent_challenge(manifest)

    assert challenge is not None
    assert challenge["license"]["termsHash"] == _sha(b"terms")
    assert challenge["acceptanceOptions"] == [
        "accepted_license_terms",
        "obtained_separate_license",
    ]
    with pytest.raises(CheckpointConsentRequiredError) as missing:
        require_checkpoint_license_consent(manifest, None)
    assert missing.value.challenges == (challenge,)

    require_checkpoint_license_consent(
        manifest,
        {
            "distributionId": manifest.distribution_id,
            "manifestDigest": manifest.digest,
            "termsHash": _sha(b"terms"),
            "decision": "accepted_license_terms",
            "confirmed": True,
        },
    )

    stale = {
        "distributionId": manifest.distribution_id,
        "manifestDigest": "sha256:" + "0" * 64,
        "termsHash": _sha(b"terms"),
        "decision": "accepted_license_terms",
        "confirmed": True,
    }
    with pytest.raises(CheckpointConsentRequiredError):
        require_checkpoint_license_consent(manifest, stale)


def test_conditional_manifest_rejects_incomplete_consent_contract() -> None:
    value = _conditional_manifest()
    del value["license"]["downloadConsent"]

    with pytest.raises(CheckpointManifestError, match="downloadConsent"):
        parse_checkpoint_distribution_manifest(value)


def test_conditional_manifest_rejects_unsafe_terms_url_and_non_string_options() -> None:
    unsafe_url = _conditional_manifest()
    unsafe_url["license"]["termsUrl"] = "javascript:alert(1)"
    with pytest.raises(CheckpointManifestError, match="HTTPS URL"):
        parse_checkpoint_distribution_manifest(unsafe_url)

    invalid_options = _conditional_manifest()
    invalid_options["license"]["downloadConsent"]["acceptanceOptions"] = [{}]
    with pytest.raises(CheckpointManifestError, match="acceptanceOptions"):
        parse_checkpoint_distribution_manifest(invalid_options)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda value: value.update(revision="main"), "immutable"),
        (
            lambda value: value["files"][0].update(path="../weights.bin"),
            "safe relative path",
        ),
        (
            lambda value: value["distribution"]["sources"][0].update(verified=False),
            "must be verified",
        ),
        (
            lambda value: value["distribution"]["p2p"].update(allowed=True),
            "P2P cannot be enabled",
        ),
    ],
)
def test_manifest_rejects_untrusted_identity_or_policy(mutate, message) -> None:
    value = _manifest()
    mutate(value)

    with pytest.raises(CheckpointManifestError, match=message):
        parse_checkpoint_distribution_manifest(value)


def test_manifest_signature_is_domain_separated_and_verified() -> None:
    manifest = parse_checkpoint_distribution_manifest(_manifest())
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = private.sign(manifest.signing_bytes())

    verify_checkpoint_manifest_signature(manifest, signature, public_pem)
    with pytest.raises(CheckpointManifestError, match="signature is invalid"):
        verify_checkpoint_manifest_signature(manifest, b"bad", public_pem)


def test_registry_bound_checkpoint_envelope_verifies_publisher_identity() -> None:
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
    manifest = parse_checkpoint_distribution_manifest(_manifest())
    payload = {
        "domain": "ai2apps.checkpoint-distribution.v1",
        "publisherId": "publisher.test",
        "publisherKeyId": fingerprint,
        "manifestDigest": manifest.digest,
        "manifest": manifest.raw,
    }
    signature = private.sign(
        b"AI2APPS-CHECKPOINT-DISTRIBUTION-V1\n" + jcs_bytes(payload)
    )
    envelope = {
        "schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1",
        "payload": payload,
        "signature": {
            "keyId": fingerprint,
            "algorithm": "Ed25519",
            "value": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        },
    }

    verified = verify_checkpoint_distribution_envelope(
        envelope,
        publisher_id="publisher.test",
        publisher_key_id=fingerprint,
        public_key_pem=public_pem,
        expected_fingerprint=fingerprint,
    )

    assert verified.digest == manifest.digest
    with pytest.raises(CheckpointManifestError, match="publisher identity"):
        verify_checkpoint_distribution_envelope(
            envelope,
            publisher_id="publisher.other",
            publisher_key_id=fingerprint,
            public_key_pem=public_pem,
        )


def test_checkpoint_envelope_rejects_manifest_tampering() -> None:
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
    manifest = parse_checkpoint_distribution_manifest(_manifest())
    payload = {
        "domain": "ai2apps.checkpoint-distribution.v1",
        "publisherId": "publisher.test",
        "publisherKeyId": fingerprint,
        "manifestDigest": manifest.digest,
        "manifest": manifest.raw,
    }
    signature = private.sign(
        b"AI2APPS-CHECKPOINT-DISTRIBUTION-V1\n" + jcs_bytes(payload)
    )
    envelope = {
        "schemaVersion": "ai2apps.checkpoint-distribution-envelope.v1",
        "payload": payload,
        "signature": {
            "keyId": fingerprint,
            "algorithm": "Ed25519",
            "value": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        },
    }
    envelope["payload"]["manifest"]["quantization"] = "tampered"

    with pytest.raises(CheckpointManifestError, match="manifest digest"):
        verify_checkpoint_distribution_envelope(
            envelope,
            publisher_id="publisher.test",
            publisher_key_id=fingerprint,
            public_key_pem=public_pem,
        )


def test_cache_promotes_only_verified_bytes(tmp_path) -> None:
    payload = b"verified-checkpoint"
    cache = CheckpointCache(tmp_path / "checkpoint-cache")
    partial = cache.partial_path("dist_test_v1", "model.safetensors")
    partial.parent.mkdir(parents=True)
    partial.write_bytes(payload)

    blob = cache.promote_verified_file(partial, sha256=_sha(payload), size=len(payload))

    assert blob.read_bytes() == payload
    assert not partial.exists()


def test_cache_rejects_wrong_digest_without_promotion(tmp_path) -> None:
    cache = CheckpointCache(tmp_path / "checkpoint-cache")
    partial = cache.partial_path("dist_test_v1", "model.safetensors")
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"corrupt")

    with pytest.raises(CheckpointManifestError, match="digest"):
        cache.promote_verified_file(
            partial, sha256=_sha(b"expected"), size=len(b"corrupt")
        )

    assert partial.exists()


def test_cache_does_not_trust_same_size_existing_blob(tmp_path) -> None:
    expected = b"expected"
    cache = CheckpointCache(tmp_path / "checkpoint-cache")
    blob = cache.blob_path(_sha(expected))
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"corrupt!")
    partial = cache.partial_path("dist_test_v1", "model.safetensors")
    partial.parent.mkdir(parents=True)
    partial.write_bytes(expected)

    with pytest.raises(CheckpointManifestError, match="cache blob is corrupt"):
        cache.promote_verified_file(partial, sha256=_sha(expected), size=len(expected))

    assert partial.exists()


@pytest.mark.asyncio
async def test_http_source_probes_and_fetches_exact_ranges() -> None:
    payload = b"checkpoint-bytes"
    manifest = parse_checkpoint_distribution_manifest(_manifest(payload))
    source = next(item for item in manifest.sources if item.provider == "modelscope")

    def respond(request: httpx.Request) -> httpx.Response:
        value = request.headers["Range"]
        start, end = (int(item) for item in value.removeprefix("bytes=").split("-"))
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {start}-{end}/{len(payload)}"},
            content=payload[start : end + 1],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = HTTPRangePieceSource(
            source, "https://modelscope.example/object", client
        )
        capability = await adapter.probe()
        piece = await adapter.fetch_piece(source.path, 2, 5)

    assert capability.available is True
    assert capability.range_supported is True
    assert capability.content_length == len(payload)
    assert piece == payload[2:7]


@pytest.mark.asyncio
async def test_http_source_rejects_ignored_or_mismatched_ranges() -> None:
    manifest = parse_checkpoint_distribution_manifest(_manifest())
    source = manifest.sources[0]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"whole file")
        )
    ) as client:
        adapter = HTTPRangePieceSource(
            source, "https://modelscope.example/object", client
        )
        capability = await adapter.probe()
        with pytest.raises(CheckpointManifestError, match="did not honor"):
            await adapter.fetch_piece(source.path, 0, 4)

    assert capability.available is True
    assert capability.range_supported is False


@pytest.mark.asyncio
async def test_hub_resolver_uses_pinned_revisions_and_encodes_paths(
    monkeypatch,
) -> None:
    hf = CheckpointSource(
        provider="huggingface",
        repo_id="publisher/model",
        revision="a" * 40,
        path="nested/model weights.safetensors",
        access="gated_user_token",
    )
    ms = CheckpointSource(
        provider="modelscope",
        repo_id="publisher/model-ms",
        revision="release-1",
        path="nested/model weights.safetensors",
        access="public_anonymous",
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: None)
    ) as client:
        resolver = HubSourceResolver(client)
        with pytest.raises(CheckpointDownloadError, match="requires a user credential"):
            resolver.resolve(hf)
        hf_adapter = resolver.resolve(hf, user_token="secret-token")
        original_import = builtins.__import__

        def reject_modelscope_import(name, *args, **kwargs):
            if name == "modelscope" or name.startswith("modelscope."):
                raise AssertionError("public ModelScope URLs must not require its SDK")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", reject_modelscope_import)
        ms_adapter = resolver.resolve(ms)

    assert (
        f"/resolve/{'a' * 40}/nested/model%20weights.safetensors"
        in hf_adapter.endpoint_url
    )
    assert hf_adapter.headers == {"Authorization": "Bearer secret-token"}
    assert "Revision=release-1" in ms_adapter.endpoint_url
    assert "FilePath=nested%2Fmodel+weights.safetensors" in ms_adapter.endpoint_url
    assert "secret-token" not in ms_adapter.endpoint_url


@pytest.mark.asyncio
async def test_hub_resolver_rejects_authenticated_modelscope_in_phase_one() -> None:
    source = CheckpointSource(
        provider="modelscope",
        repo_id="publisher/private-model",
        revision="release-1",
        path="model.safetensors",
        access="private_user_token",
    )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: None)
    ) as client:
        resolver = HubSourceResolver(client)
        with pytest.raises(CheckpointDownloadError, match="not enabled in Phase 1"):
            resolver.resolve(source, user_token="secret-token")


def test_piece_planner_maps_a_piece_across_file_boundaries() -> None:
    first = b"a" * 700_000
    second = b"b" * 600_000
    manifest = parse_checkpoint_distribution_manifest(
        _multi_file_manifest(first, second)
    )

    pieces = plan_checkpoint_pieces(manifest)

    assert len(pieces) == 2
    assert [
        (item.file_path, item.file_offset, item.length) for item in pieces[0].segments
    ] == [
        ("first.bin", 0, len(first)),
        ("nested/second.bin", 0, 1024 * 1024 - len(first)),
    ]
    assert pieces[1].segments[0].file_offset == 1024 * 1024 - len(first)


@pytest.mark.asyncio
async def test_piece_scheduler_completes_with_modelscope_only(tmp_path) -> None:
    first = b"a" * 700_000
    second = b"b" * 600_000
    manifest = parse_checkpoint_distribution_manifest(
        _multi_file_manifest(first, second)
    )
    sources = [
        _MemoryPieceSource("modelscope", "first.bin", first, latency_ms=2),
        _MemoryPieceSource("modelscope", "nested/second.bin", second, latency_ms=2),
    ]
    scheduler = PieceDownloadScheduler(
        manifest,
        CheckpointCache(tmp_path / "cache"),
        sources,
        concurrency=2,
    )

    blobs = await scheduler.download()

    assert blobs["first.bin"].read_bytes() == first
    assert blobs["nested/second.bin"].read_bytes() == second
    assert scheduler.source_bytes == {"modelscope": len(first) + len(second)}


@pytest.mark.asyncio
async def test_piece_scheduler_reports_current_file_and_byte_progress(tmp_path) -> None:
    first = b"a" * 700_000
    second = b"b" * 600_000
    manifest = parse_checkpoint_distribution_manifest(
        _multi_file_manifest(first, second)
    )
    events = []
    scheduler = PieceDownloadScheduler(
        manifest,
        CheckpointCache(tmp_path / "cache"),
        [
            _MemoryPieceSource("modelscope", "first.bin", first, latency_ms=1),
            _MemoryPieceSource(
                "modelscope", "nested/second.bin", second, latency_ms=1
            ),
        ],
        concurrency=1,
        progress=events.append,
    )

    await scheduler.download()

    assert events
    assert events[-1]["stage"] == "downloading_checkpoint"
    assert events[-1]["fileName"] == "nested/second.bin"
    assert events[-1]["bytesCompleted"] == len(second)
    assert events[-1]["bytesTotal"] == len(second)
    assert events[-1]["totalBytesCompleted"] == len(first) + len(second)
    assert events[-1]["totalBytesTotal"] == len(first) + len(second)
    assert events[-1]["percent"] == 100


@pytest.mark.asyncio
async def test_verified_blobs_materialize_as_atomic_read_only_snapshot(
    tmp_path,
) -> None:
    first = b"a" * 700_000
    second = b"b" * 600_000
    manifest = parse_checkpoint_distribution_manifest(
        _multi_file_manifest(first, second)
    )
    cache = CheckpointCache(tmp_path / "cache")
    sources = [
        _MemoryPieceSource("modelscope", "first.bin", first, latency_ms=1),
        _MemoryPieceSource("modelscope", "nested/second.bin", second, latency_ms=1),
    ]
    blobs = await PieceDownloadScheduler(manifest, cache, sources).download()

    snapshot = cache.materialize_snapshot(manifest, blobs)

    assert (snapshot / "first.bin").read_bytes() == first
    assert (snapshot / "nested/second.bin").read_bytes() == second
    assert (snapshot / "first.bin").stat().st_ino == blobs["first.bin"].stat().st_ino
    assert snapshot.stat().st_mode & 0o222 == 0
    assert (snapshot / "first.bin").stat().st_mode & 0o222 == 0
    assert cache.materialize_snapshot(manifest, blobs) == snapshot


def test_snapshot_rejects_unlisted_or_unverified_blob(tmp_path) -> None:
    payload = b"checkpoint"
    manifest = parse_checkpoint_distribution_manifest(_manifest(payload))
    cache = CheckpointCache(tmp_path / "cache")
    unverified = tmp_path / "unverified"
    unverified.write_bytes(payload)

    with pytest.raises(CheckpointManifestError, match="not verified"):
        cache.materialize_snapshot(manifest, {"model.safetensors": unverified})


@pytest.mark.asyncio
async def test_existing_snapshot_with_extra_file_is_rejected(tmp_path) -> None:
    payload = b"checkpoint"
    manifest = parse_checkpoint_distribution_manifest(_manifest(payload))
    cache = CheckpointCache(tmp_path / "cache")
    source = _MemoryPieceSource(
        "modelscope", "model.safetensors", payload, latency_ms=1
    )
    blobs = await PieceDownloadScheduler(manifest, cache, [source]).download()
    snapshot = cache.materialize_snapshot(manifest, blobs)
    snapshot.chmod(0o755)
    extra = snapshot / "unexpected.txt"
    extra.write_text("unexpected")

    with pytest.raises(CheckpointManifestError, match="snapshot is corrupt"):
        cache.materialize_snapshot(manifest, blobs)


@pytest.mark.asyncio
async def test_piece_scheduler_falls_back_after_bad_source_bytes(tmp_path) -> None:
    payload = b"x" * 900_000
    manifest = parse_checkpoint_distribution_manifest(_manifest(payload))
    ms = _MemoryPieceSource(
        "modelscope",
        "model.safetensors",
        payload,
        latency_ms=1,
        corrupt=True,
    )
    hf = _MemoryPieceSource("huggingface", "model.safetensors", payload, latency_ms=10)
    scheduler = PieceDownloadScheduler(
        manifest, CheckpointCache(tmp_path / "cache"), [ms, hf], concurrency=2
    )

    blobs = await scheduler.download()

    assert blobs["model.safetensors"].read_bytes() == payload
    assert ms.requests
    assert hf.requests


@pytest.mark.asyncio
async def test_cross_file_piece_can_mix_healthy_sources(tmp_path) -> None:
    first = b"a" * 700_000
    second = b"b" * 600_000
    manifest = parse_checkpoint_distribution_manifest(
        _multi_file_manifest(first, second)
    )
    sources = [
        _MemoryPieceSource("modelscope", "first.bin", first, latency_ms=1),
        _MemoryPieceSource(
            "huggingface", "first.bin", first, latency_ms=2, corrupt=True
        ),
        _MemoryPieceSource(
            "modelscope",
            "nested/second.bin",
            second,
            latency_ms=1,
            corrupt=True,
        ),
        _MemoryPieceSource("huggingface", "nested/second.bin", second, latency_ms=2),
    ]
    scheduler = PieceDownloadScheduler(
        manifest,
        CheckpointCache(tmp_path / "cache"),
        sources,
        concurrency=1,
    )

    blobs = await scheduler.download()

    assert blobs["first.bin"].read_bytes() == first
    assert blobs["nested/second.bin"].read_bytes() == second
    assert scheduler.source_bytes["modelscope"] > 0
    assert scheduler.source_bytes["huggingface"] > 0


@pytest.mark.asyncio
async def test_piece_scheduler_resumes_only_hash_valid_completed_pieces(
    tmp_path,
) -> None:
    first = b"a" * 700_000
    second = b"b" * 600_000
    manifest = parse_checkpoint_distribution_manifest(
        _multi_file_manifest(first, second)
    )
    cache = CheckpointCache(tmp_path / "cache")
    scheduler = PieceDownloadScheduler(manifest, cache, [], concurrency=1)
    scheduler._prepare_partial_files()
    first_piece = scheduler.pieces[0]
    scheduler._write_piece(first_piece, (first + second)[: 1024 * 1024])
    piece_map = PieceCompletionMap(cache, manifest)
    piece_map.mark(0)
    sources = [
        _MemoryPieceSource("modelscope", "first.bin", first, latency_ms=1),
        _MemoryPieceSource("modelscope", "nested/second.bin", second, latency_ms=1),
    ]
    resumed = PieceDownloadScheduler(manifest, cache, sources, concurrency=1)

    await resumed.download()

    assert sources[0].requests == []
    assert sources[1].requests == [
        (
            1024 * 1024 - len(first),
            len(second) - (1024 * 1024 - len(first)),
        )
    ]


@pytest.mark.asyncio
async def test_piece_scheduler_rejects_when_no_verified_range_source(tmp_path) -> None:
    manifest = parse_checkpoint_distribution_manifest(_manifest())
    source = _MemoryPieceSource(
        "modelscope",
        "model.safetensors",
        b"short",
        latency_ms=1,
    )
    scheduler = PieceDownloadScheduler(
        manifest, CheckpointCache(tmp_path / "cache"), [source]
    )

    with pytest.raises(CheckpointDownloadError, match="no usable range source"):
        await scheduler.download()
