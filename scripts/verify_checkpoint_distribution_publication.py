#!/usr/bin/env python3
"""Verify a public Checkpoint Registry publication through Local trust rules."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ai2apps.checkpoint_registry import CheckpointRegistryClient
from ai2apps.cloud_client import (
    DEFAULT_AI2APPS_CLOUD_BASE_URL,
    AI2AppsCloudClient,
    CloudSessionStore,
)
from ai2apps.packages.repository_config import AI2APPS_REPOSITORY_FINGERPRINT
from ai2apps.secrets.backends import MemorySecretBackend


async def verify(args: argparse.Namespace) -> dict[str, object]:
    cloud = AI2AppsCloudClient(
        base_url=args.cloud_base_url,
        session_store=CloudSessionStore(
            MemorySecretBackend(), args.cloud_base_url
        ),
    )
    client = CheckpointRegistryClient(
        cloud=cloud,
        root=args.cache_root,
        repository_fingerprint=AI2APPS_REPOSITORY_FINGERPRINT,
    )
    try:
        index = await client.trusted_index()
        manifest = await client.distribution(args.distribution_id)
        record = index.record(args.distribution_id)
        result: dict[str, object] = {
            "indexVersion": index.version,
            "distributionId": manifest.distribution_id,
            "manifestDigest": manifest.digest,
            "recordCount": len(index.records),
            "publisherId": record.publisher_id,
            "publisherKeyId": record.publisher_key_id,
        }
        if args.envelope is not None:
            local = json.loads(args.envelope.read_text(encoding="utf-8"))
            cached = client.root / "envelopes" / f"{manifest.digest[7:]}.json"
            public = json.loads(cached.read_text(encoding="utf-8"))
            result["envelopeExactJson"] = public == local
            if public != local:
                raise RuntimeError("public envelope differs from the signed local envelope")
        return result
    finally:
        await cloud.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--distribution-id", required=True)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--cloud-base-url", default=DEFAULT_AI2APPS_CLOUD_BASE_URL)
    args = parser.parse_args()
    args.cache_root = args.cache_root.expanduser().resolve()
    if args.envelope is not None:
        args.envelope = args.envelope.expanduser().resolve()
    print(json.dumps(asyncio.run(verify(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
