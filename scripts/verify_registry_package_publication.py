#!/usr/bin/env python3
"""Verify a public Package Registry release through Local trust rules."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from ai2apps.cloud_client import (
    DEFAULT_AI2APPS_CLOUD_BASE_URL,
    AI2AppsCloudClient,
    CloudSessionStore,
)
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.packages.repository_config import AI2APPS_REPOSITORY_FINGERPRINT
from ai2apps.secrets.backends import MemorySecretBackend


async def verify(args: argparse.Namespace) -> dict[str, object]:
    cloud = AI2AppsCloudClient(
        base_url=args.cloud_base_url,
        session_store=CloudSessionStore(
            MemorySecretBackend(), args.cloud_base_url
        ),
    )
    manager = RegistryPackageManager(
        cloud=cloud,
        root=args.cache_root,
        secrets=None,
        extension_manager=None,
        service_manager=None,
        repository_fingerprint=AI2APPS_REPOSITORY_FINGERPRINT,
    )
    try:
        namespace, name = args.package_id.split("/", 1)
        inspected, envelope, release, snapshot_version = (
            await manager.download_verified(namespace, name, args.version)
        )
        result: dict[str, object] = {
            "repositoryMetadataVersion": snapshot_version,
            "packageId": inspected.manifest["package"]["id"],
            "version": inspected.manifest["package"]["version"],
            "sha256": inspected.sha256,
            "size": inspected.size,
            "publisherId": release["publisher"]["id"],
            "publisherKeyId": release["publisher"]["key"]["id"],
        }
        if args.artifact is not None:
            digest = hashlib.sha256(args.artifact.read_bytes()).hexdigest()
            result["artifactExactBytes"] = (
                digest == inspected.sha256
                and args.artifact.stat().st_size == inspected.size
            )
            if not result["artifactExactBytes"]:
                raise RuntimeError("public artifact differs from the local artifact")
        if args.envelope is not None:
            local_envelope = json.loads(args.envelope.read_text(encoding="utf-8"))
            result["envelopeExactJson"] = envelope == local_envelope
            if not result["envelopeExactJson"]:
                raise RuntimeError("public envelope differs from the local envelope")
        return result
    finally:
        await cloud.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--envelope", type=Path)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--cloud-base-url", default=DEFAULT_AI2APPS_CLOUD_BASE_URL)
    args = parser.parse_args()
    args.cache_root = args.cache_root.expanduser().resolve()
    if args.artifact is not None:
        args.artifact = args.artifact.expanduser().resolve(strict=True)
    if args.envelope is not None:
        args.envelope = args.envelope.expanduser().resolve(strict=True)
    print(json.dumps(asyncio.run(verify(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
