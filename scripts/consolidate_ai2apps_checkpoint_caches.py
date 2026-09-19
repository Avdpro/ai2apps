#!/usr/bin/env python3
"""Consolidate verified per-instance checkpoint caches into the shared cache."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ai2apps.checkpoint_distribution import (  # noqa: E402
    CheckpointCache,
    CheckpointDistributionManifest,
    parse_checkpoint_distribution_manifest,
)


@dataclass(frozen=True)
class ManifestSource:
    cache_root: Path
    manifest_path: Path
    manifest: CheckpointDistributionManifest


def _contained(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def discover_cache_roots(instances_root: Path, preserved_root: Path) -> tuple[Path, ...]:
    roots: set[Path] = set()
    if instances_root.is_dir() and not instances_root.is_symlink():
        for instance in instances_root.iterdir():
            candidate = instance / "data/platform/packages/checkpoint-cache-v1"
            if instance.is_dir() and not instance.is_symlink() and candidate.is_dir():
                roots.add(candidate.resolve())
    if preserved_root.is_dir() and not preserved_root.is_symlink():
        for candidate in preserved_root.iterdir():
            if candidate.is_dir() and not candidate.is_symlink():
                roots.add(candidate.resolve())
    return tuple(sorted(roots))


def load_manifests(cache_roots: tuple[Path, ...]) -> tuple[ManifestSource, ...]:
    found: list[ManifestSource] = []
    for cache_root in cache_roots:
        for manifest_path in sorted((cache_root / "manifests").glob("*.json")):
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            found.append(
                ManifestSource(
                    cache_root=cache_root,
                    manifest_path=manifest_path,
                    manifest=parse_checkpoint_distribution_manifest(raw),
                )
            )
    return tuple(found)


def _acquire_lock(cache: CheckpointCache, manifest: CheckpointDistributionManifest) -> int:
    while (descriptor := cache.try_acquire_distribution_lock(manifest)) is None:
        time.sleep(0.05)
    return descriptor


def _make_removable(root: Path) -> None:
    for current, directories, _files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        if current_path.is_symlink():
            directories.clear()
            continue
        current_path.chmod(current_path.stat().st_mode | 0o700)
        directories[:] = [
            name for name in directories if not (current_path / name).is_symlink()
        ]


def consolidate(
    *,
    shared_root: Path,
    instances_root: Path,
    preserved_root: Path,
    delete_sources: bool,
) -> dict[str, Any]:
    shared_root = shared_root.expanduser().resolve()
    instances_root = instances_root.expanduser().resolve()
    preserved_root = preserved_root.expanduser().resolve()
    sources = discover_cache_roots(instances_root, preserved_root)
    if shared_root in sources:
        raise ValueError("shared cache cannot also be a migration source")
    for source in sources:
        if not (
            _contained(source, instances_root) or _contained(source, preserved_root)
        ):
            raise ValueError(f"checkpoint cache source escaped its allowed root: {source}")
        if source.is_symlink():
            raise ValueError(f"checkpoint cache source is a symbolic link: {source}")

    manifest_sources = load_manifests(sources)
    by_identity: dict[tuple[str, str], list[ManifestSource]] = {}
    for item in manifest_sources:
        identity = (item.manifest.distribution_id, item.manifest.digest)
        by_identity.setdefault(identity, []).append(item)

    shared_cache = CheckpointCache(shared_root)
    migrated: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for identity, candidates in sorted(by_identity.items()):
        manifest = candidates[0].manifest
        descriptor = _acquire_lock(shared_cache, manifest)
        try:
            snapshot = shared_cache.verified_snapshot(manifest)
            imported_from: Path | None = None
            verified = snapshot
            if snapshot is None:
                candidate_errors: list[str] = []
                for candidate in candidates:
                    source_cache = CheckpointCache(candidate.cache_root)
                    source_snapshot = source_cache.snapshot_path(manifest)
                    if not source_snapshot.is_dir():
                        candidate_errors.append(
                            f"{candidate.cache_root}: expected snapshot is missing"
                        )
                        continue
                    try:
                        snapshot = shared_cache.import_local_snapshot(
                            manifest, source_snapshot
                        )
                    except Exception as error:  # noqa: BLE001
                        candidate_errors.append(
                            f"{candidate.cache_root}: {type(error).__name__}: {error}"
                        )
                        continue
                    imported_from = candidate.cache_root
                    break
                if snapshot is None:
                    errors.append(
                        {
                            "distribution_id": identity[0],
                            "manifest_digest": identity[1],
                            "errors": candidate_errors,
                        }
                    )
                    continue
                verified = shared_cache.verified_snapshot(manifest)
            if verified is None:
                errors.append(
                    {
                        "distribution_id": identity[0],
                        "manifest_digest": identity[1],
                        "errors": ["shared snapshot failed final verification"],
                    }
                )
                continue
            migrated.append(
                {
                    "distribution_id": manifest.distribution_id,
                    "manifest_digest": manifest.digest,
                    "file_count": len(manifest.files),
                    "logical_bytes": sum(item.size for item in manifest.files),
                    "imported_from": str(imported_from) if imported_from else None,
                    "shared_snapshot": str(verified),
                }
            )
        finally:
            shared_cache.release_distribution_lock(descriptor)

    deleted: list[str] = []
    if delete_sources and not errors:
        for source in sources:
            _make_removable(source)
            shutil.rmtree(source)
            deleted.append(str(source))

    return {
        "schema_version": 1,
        "status": "complete" if not errors else "failed",
        "shared_root": str(shared_root),
        "source_roots": [str(item) for item in sources],
        "source_manifest_count": len(manifest_sources),
        "unique_distribution_count": len(by_identity),
        "unique_logical_bytes": sum(item["logical_bytes"] for item in migrated),
        "migrated": migrated,
        "errors": errors,
        "delete_sources_requested": delete_sources,
        "deleted_source_roots": deleted,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shared-root", type=Path, required=True)
    parser.add_argument("--instances-root", type=Path, required=True)
    parser.add_argument("--preserved-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--delete-sources", action="store_true")
    arguments = parser.parse_args()

    report = consolidate(
        shared_root=arguments.shared_root,
        instances_root=arguments.instances_root,
        preserved_root=arguments.preserved_root,
        delete_sources=arguments.delete_sources,
    )
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = arguments.report.with_suffix(arguments.report.suffix + ".partial")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, arguments.report)
    print(json.dumps({key: report[key] for key in (
        "status",
        "source_manifest_count",
        "unique_distribution_count",
        "unique_logical_bytes",
        "deleted_source_roots",
        "errors",
    )}, indent=2, sort_keys=True))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
