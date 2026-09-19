from __future__ import annotations

import hashlib

from ai2apps.checkpoint_distribution import (
    CheckpointCache,
    parse_checkpoint_distribution_manifest,
)
from scripts.consolidate_ai2apps_checkpoint_caches import consolidate


def _manifest(payload: bytes):
    digest = hashlib.sha256(payload).hexdigest()
    return parse_checkpoint_distribution_manifest(
        {
            "schemaVersion": 1,
            "distributionId": "dist_shared_migration_test_v1",
            "modelId": "ai2apps.model/test",
            "repoId": "publisher/test",
            "revision": "a" * 40,
            "format": "safetensors",
            "quantization": "mlx-4bit",
            "estimatedSizeBytes": len(payload),
            "license": {
                "id": "MIT",
                "name": "MIT",
                "termsUrl": "https://example.test/license",
                "termsHash": "sha256:" + "b" * 64,
                "usagePolicy": "commercial_allowed",
                "accessPolicy": "public",
                "redistributionPolicy": "allowed",
            },
            "files": [
                {
                    "path": "model.safetensors",
                    "size": len(payload),
                    "sha256": f"sha256:{digest}",
                }
            ],
            "pieceSize": 1024 * 1024,
            "pieceHashes": [f"sha256:{digest}"],
            "distribution": {
                "p2p": {"allowed": False},
                "sources": [
                    {
                        "type": "huggingface",
                        "repoId": "publisher/test",
                        "revision": "a" * 40,
                        "path": "model.safetensors",
                        "access": "public_anonymous",
                        "verified": True,
                    }
                ],
            },
        }
    )


def _populate(cache_root, manifest, payload, source_root):
    source_root.mkdir(parents=True)
    (source_root / "model.safetensors").write_bytes(payload)
    CheckpointCache(cache_root).import_local_snapshot(manifest, source_root)


def test_consolidation_deduplicates_and_deletes_verified_sources(tmp_path) -> None:
    payload = b"shared-checkpoint"
    manifest = _manifest(payload)
    instances = tmp_path / "instances"
    preserved = tmp_path / "shared/legacy-checkpoint-cache-v1"
    first = instances / "dev/data/platform/packages/checkpoint-cache-v1"
    second = instances / "app-dev/data/platform/packages/checkpoint-cache-v1"
    _populate(first, manifest, payload, tmp_path / "source-a")
    _populate(second, manifest, payload, tmp_path / "source-b")
    incomplete = instances / "test/data/platform/packages/checkpoint-cache-v1"
    (incomplete / "partial").mkdir(parents=True)
    (incomplete / "partial/unverified").write_bytes(b"partial")

    shared = tmp_path / "shared/checkpoint-cache-v1"
    report = consolidate(
        shared_root=shared,
        instances_root=instances,
        preserved_root=preserved,
        delete_sources=True,
    )

    assert report["status"] == "complete"
    assert report["source_manifest_count"] == 2
    assert report["unique_distribution_count"] == 1
    assert len(report["deleted_source_roots"]) == 3
    assert CheckpointCache(shared).verified_snapshot(manifest) is not None
    assert not first.exists()
    assert not second.exists()
    assert not incomplete.exists()


def test_consolidation_retains_every_source_when_verification_fails(tmp_path) -> None:
    payload = b"missing-checkpoint"
    manifest = _manifest(payload)
    instances = tmp_path / "instances"
    broken = instances / "dev/data/platform/packages/checkpoint-cache-v1"
    CheckpointCache(broken).write_manifest(manifest)

    report = consolidate(
        shared_root=tmp_path / "shared/checkpoint-cache-v1",
        instances_root=instances,
        preserved_root=tmp_path / "shared/legacy-checkpoint-cache-v1",
        delete_sources=True,
    )

    assert report["status"] == "failed"
    assert report["deleted_source_roots"] == []
    assert broken.is_dir()
