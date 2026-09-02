#!/usr/bin/env python3
"""Verify existing snapshots into the AI2Apps checkpoint cache."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ai2apps.checkpoint_distribution import CheckpointCache
from ai2apps.checkpoint_registry import CheckpointRegistryClient
from ai2apps.cloud_client import (
    DEFAULT_AI2APPS_CLOUD_BASE_URL,
    AI2AppsCloudClient,
    CloudSessionStore,
)
from ai2apps.packages.repository_config import AI2APPS_REPOSITORY_FINGERPRINT
from ai2apps.secrets.backends import MemorySecretBackend


def _binding(value: str) -> tuple[str, Path]:
    distribution_id, separator, source = value.partition("=")
    if not separator or not distribution_id or not source:
        raise argparse.ArgumentTypeError(
            "bindings must use DISTRIBUTION_ID=/absolute/snapshot/path"
        )
    path = Path(source).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("snapshot path must be absolute")
    return distribution_id, path


async def import_snapshots(args: argparse.Namespace) -> dict[str, object]:
    cache = CheckpointCache(args.cache_root)
    cloud = AI2AppsCloudClient(
        base_url=args.cloud_base_url,
        session_store=CloudSessionStore(
            MemorySecretBackend(), args.cloud_base_url
        ),
    )
    registry = CheckpointRegistryClient(
        cloud=cloud,
        root=args.registry_cache_root,
        repository_fingerprint=AI2APPS_REPOSITORY_FINGERPRINT,
    )
    results: list[dict[str, object]] = []
    try:
        for distribution_id, source in args.binding:
            print(f"Verifying {distribution_id} from {source}", flush=True)
            try:
                manifest = await registry.distribution(distribution_id)
                existing = await asyncio.to_thread(cache.verified_snapshot, manifest)
                if existing is not None:
                    results.append(
                        {
                            "distributionId": distribution_id,
                            "status": "already_cached",
                            "snapshot": str(existing),
                            "bytes": manifest.estimated_size_bytes,
                        }
                    )
                    print(f"Already cached: {distribution_id}", flush=True)
                    continue
                imported = await asyncio.to_thread(
                    cache.import_local_snapshot, manifest, source
                )
                results.append(
                    {
                        "distributionId": distribution_id,
                        "status": "imported",
                        "snapshot": str(imported),
                        "bytes": manifest.estimated_size_bytes,
                        "manifestDigest": manifest.digest,
                    }
                )
                print(f"Imported: {distribution_id}", flush=True)
            except Exception as error:
                results.append(
                    {
                        "distributionId": distribution_id,
                        "status": "failed",
                        "source": str(source),
                        "error": str(error),
                    }
                )
                print(f"Failed: {distribution_id}: {error}", flush=True)
    finally:
        await cloud.close()
    return {
        "cacheRoot": str(args.cache_root),
        "results": results,
        "importedBytes": sum(
            int(item["bytes"])
            for item in results
            if item["status"] == "imported"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--registry-cache-root", type=Path, required=True)
    parser.add_argument(
        "--binding",
        action="append",
        type=_binding,
        required=True,
        help="DISTRIBUTION_ID=/absolute/snapshot/path; repeat as needed",
    )
    parser.add_argument(
        "--cloud-base-url", default=DEFAULT_AI2APPS_CLOUD_BASE_URL
    )
    args = parser.parse_args()
    args.cache_root = args.cache_root.expanduser().resolve()
    args.registry_cache_root = args.registry_cache_root.expanduser().resolve()
    print(
        json.dumps(
            asyncio.run(import_snapshots(args)), ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
