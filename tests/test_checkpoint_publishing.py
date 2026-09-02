from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.checkpoint_publishing import (
    FULL_DUAL_DOWNLOAD_BUILDER,
    METADATA_VERIFIED_BUILDER,
    CheckpointFileMetadata,
    CheckpointPublishingError,
    build_checkpoint_distribution,
    build_checkpoint_distribution_from_metadata,
    fetch_modelscope_file_metadata,
    verification_receipt_for_envelope,
    write_checkpoint_distribution,
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _spec() -> dict:
    return {
        "schema": "ai2apps.checkpoint-build/v1",
        "distributionId": "dist_test_publish_v1",
        "modelId": "ai2apps.model.test/default",
        "repoId": "publisher/model",
        "revision": "a" * 40,
        "format": "safetensors",
        "quantization": "mlx-4bit",
        "pieceSize": 1024 * 1024,
        "license": {
            "id": "Apache-2.0",
            "name": "Apache License 2.0",
            "termsUrl": "https://www.apache.org/licenses/LICENSE-2.0",
            "termsHash": _sha(b"license terms"),
            "usagePolicy": "license_terms",
            "accessPolicy": "public",
            "redistributionPolicy": "allowed",
        },
        "includePatterns": ["config.json", "weights/*.safetensors"],
        "sourceRepositories": [
            {
                "type": "huggingface",
                "repoId": "publisher/model",
                "revision": "a" * 40,
                "access": "public_anonymous",
            },
            {
                "type": "modelscope",
                "repoId": "publisher/model-ms",
                "revision": "release-1",
                "access": "public_anonymous",
            },
        ],
    }


def _roots(tmp_path, *, different: bool = False):
    roots = {}
    for provider in ("huggingface", "modelscope"):
        root = tmp_path / provider
        (root / "weights").mkdir(parents=True)
        (root / "config.json").write_bytes(b"config")
        payload = (
            b"b" * (1024 * 1024)
            if provider == "modelscope" and different
            else b"a" * (1024 * 1024)
        )
        (root / "weights/model.safetensors").write_bytes(payload)
        (root / "README.md").write_text("not selected")
        roots[provider] = root
    return roots


def test_builder_verifies_both_hubs_signs_and_writes_receipt(tmp_path):
    built = build_checkpoint_distribution(
        _spec(),
        source_roots=_roots(tmp_path),
        private_key=Ed25519PrivateKey.generate(),
        publisher_id="publisher.test",
        publisher_key_id="key.test",
    )

    assert built.file_count == 2
    assert [item.path for item in built.manifest.files] == [
        "config.json",
        "weights/model.safetensors",
    ]
    assert len(built.manifest.piece_hashes) == 2
    assert {item.provider for item in built.manifest.sources} == {
        "huggingface",
        "modelscope",
    }
    receipt = write_checkpoint_distribution(built, tmp_path / "release/envelope.json")
    assert receipt["manifestDigest"] == built.manifest.digest
    assert verification_receipt_for_envelope(built.envelope) == {
        "builder": FULL_DUAL_DOWNLOAD_BUILDER,
        "fileCount": 2,
        "pieceCount": 2,
        "estimatedSizeBytes": str(1024 * 1024 + len(b"config")),
        "verifiedProviders": ["huggingface", "modelscope"],
    }
    assert (tmp_path / "release/envelope.json").is_file()
    assert (tmp_path / "release/envelope.manifest.json").is_file()
    assert (tmp_path / "release/envelope.verification.json").is_file()
    assert receipt["verificationMode"] == FULL_DUAL_DOWNLOAD_BUILDER


def test_builder_signs_conditional_license_and_download_consent(tmp_path):
    spec = _spec()
    spec["license"].update(
        {
            "redistributionPolicy": "conditional",
            "redistributionConditions": {
                "termsAcceptance": "required",
                "licenseDelivery": "required",
                "downstreamTerms": "license_terms",
                "commercialUse": "separate_license_required",
                "attribution": {
                    "required": True,
                    "noticeText": "Built with Example Model",
                    "noticeFile": "NOTICE",
                    "productDisplay": "required",
                },
                "modifiedFilesNotice": "required",
            },
            "downloadConsent": {
                "required": True,
                "attestationText": "I have accepted or obtained the required license.",
                "acceptanceOptions": [
                    "accepted_license_terms",
                    "obtained_separate_license",
                ],
            },
        }
    )

    built = build_checkpoint_distribution(
        spec,
        source_roots=_roots(tmp_path),
        private_key=Ed25519PrivateKey.generate(),
        publisher_id="publisher.test",
        publisher_key_id="key.test",
    )

    signed_license = built.envelope["payload"]["manifest"]["license"]
    assert signed_license["redistributionPolicy"] == "conditional"
    assert signed_license["downloadConsent"]["required"] is True
    assert signed_license["redistributionConditions"]["attribution"]["noticeText"] == (
        "Built with Example Model"
    )


def test_builder_rejects_same_paths_with_different_bytes(tmp_path):
    with pytest.raises(CheckpointPublishingError, match="hashes differ"):
        build_checkpoint_distribution(
            _spec(),
            source_roots=_roots(tmp_path, different=True),
            private_key=Ed25519PrivateKey.generate(),
            publisher_id="publisher.test",
            publisher_key_id="key.test",
        )


def test_builder_rejects_source_file_set_difference(tmp_path):
    roots = _roots(tmp_path)
    (roots["modelscope"] / "config.json").unlink()
    with pytest.raises(CheckpointPublishingError, match="file sets"):
        build_checkpoint_distribution(
            _spec(),
            source_roots=roots,
            private_key=Ed25519PrivateKey.generate(),
            publisher_id="publisher.test",
            publisher_key_id="key.test",
        )


def _metadata_fixture(tmp_path, *, wrong_hash: bool = False):
    root = tmp_path / ("a" * 40)
    (root / "weights").mkdir(parents=True)
    values = {
        "config.json": b"config",
        "weights/model.safetensors": b"a" * (1024 * 1024),
    }
    metadata = []
    for path, payload in values.items():
        (root / path).write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        if wrong_hash and path == "weights/model.safetensors":
            digest = "0" * 64
        metadata.append(
            CheckpointFileMetadata(path=path, size=len(payload), sha256=digest)
        )
    return root, tuple(metadata)


def test_metadata_builder_reads_only_hf_and_matches_modelscope_sha256(tmp_path):
    root, metadata = _metadata_fixture(tmp_path)
    built = build_checkpoint_distribution_from_metadata(
        _spec(),
        huggingface_root=root,
        modelscope_files=metadata,
        private_key=Ed25519PrivateKey.generate(),
        publisher_id="publisher.test",
        publisher_key_id="key.test",
    )

    assert built.verification_builder == METADATA_VERIFIED_BUILDER
    assert built.source_roots == {"huggingface": root}
    assert verification_receipt_for_envelope(
        built.envelope, builder=built.verification_builder
    )["builder"] == METADATA_VERIFIED_BUILDER


def test_metadata_builder_accepts_revision_snapshot_symlink(tmp_path):
    root, metadata = _metadata_fixture(tmp_path)
    materialized = tmp_path / "materialized"
    root.rename(materialized)
    root.symlink_to(materialized, target_is_directory=True)

    built = build_checkpoint_distribution_from_metadata(
        _spec(),
        huggingface_root=root,
        modelscope_files=metadata,
        private_key=Ed25519PrivateKey.generate(),
        publisher_id="publisher.test",
        publisher_key_id="key.test",
    )

    assert built.source_roots == {"huggingface": materialized.resolve()}


def test_metadata_builder_rejects_modelscope_hash_mismatch(tmp_path):
    root, metadata = _metadata_fixture(tmp_path, wrong_hash=True)
    with pytest.raises(CheckpointPublishingError, match="SHA-256 differs"):
        build_checkpoint_distribution_from_metadata(
            _spec(),
            huggingface_root=root,
            modelscope_files=metadata,
            private_key=Ed25519PrivateKey.generate(),
            publisher_id="publisher.test",
            publisher_key_id="key.test",
        )


def test_modelscope_metadata_fetch_requires_sha256_for_every_file():
    class Api:
        def list_repo_files(self, **kwargs):
            assert kwargs == {
                "repo_id": "publisher/model-ms",
                "repo_type": "model",
                "revision": "release-1",
                "recursive": True,
            }
            return [
                SimpleNamespace(
                    path="weights/model.safetensors",
                    size=42,
                    sha256="A" * 64,
                    type="blob",
                    is_dir=False,
                )
            ]

    assert fetch_modelscope_file_metadata(
        "publisher/model-ms", "release-1", api=Api()
    ) == (
        CheckpointFileMetadata(
            path="weights/model.safetensors", size=42, sha256="a" * 64
        ),
    )


def test_modelscope_metadata_fetch_rejects_missing_selected_sha256():
    class Api:
        def list_repo_files(self, **_kwargs):
            return [
                SimpleNamespace(
                    path="weights/model.safetensors",
                    size=42,
                    sha256=None,
                    type="blob",
                    is_dir=False,
                ),
                SimpleNamespace(
                    path="README.md",
                    size=10,
                    sha256=None,
                    type="blob",
                    is_dir=False,
                ),
            ]

    with pytest.raises(CheckpointPublishingError, match="did not provide"):
        fetch_modelscope_file_metadata(
            "publisher/model-ms",
            "release-1",
            include_patterns=("weights/*",),
            api=Api(),
        )
