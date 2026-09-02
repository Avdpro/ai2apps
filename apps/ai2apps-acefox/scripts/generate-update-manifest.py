#!/usr/bin/env python3
"""Generate one bounded static update manifest from a verified release record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import quote, urlparse


def fail(message: str) -> None:
    raise SystemExit(f"generate-update-manifest: {message}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_url(base_url: str, filename: str) -> str:
    return f"{base_url.rstrip('/')}/{quote(filename)}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-metadata", required=True, type=Path)
    parser.add_argument(
        "--base-url",
        required=True,
        action="append",
        dest="base_urls",
        help="immutable artifact base URL; repeat in client fallback order",
    )
    parser.add_argument("--runtime-profile", required=True, choices=("full", "cloud"))
    parser.add_argument("--rollout-id", required=True)
    parser.add_argument("--percentage-basis-points", required=True, type=int)
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    metadata_path = args.release_metadata.resolve()
    output = args.output.resolve()
    if not 1 <= len(args.base_urls) <= 4 or len(set(args.base_urls)) != len(args.base_urls):
        fail("provide between one and four unique --base-url values")
    for base_url in args.base_urls:
        parsed_url = urlparse(base_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.username:
            fail("every --base-url must be an HTTPS origin/path without credentials")
    if not 0 <= args.percentage_basis_points <= 10_000:
        fail("--percentage-basis-points must be between 0 and 10000")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.rollout_id):
        fail("invalid --rollout-id")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,32}", args.channel):
        fail("invalid --channel")
    if output.exists():
        fail("refusing to overwrite output")
    if not metadata_path.is_file() or metadata_path.stat().st_size > 1024 * 1024:
        fail("release metadata must be an existing file no larger than 1 MiB")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        dmg_record = metadata["artifacts"]["dmg"]
        dmg = metadata_path.parent / dmg_record["filename"]
        required = (
            metadata["bundle_identifier"], metadata["instance_id"],
            metadata["product_version"], metadata["bundle_version"],
            metadata["minimum_system_version"], metadata["architectures"],
            dmg_record["size_bytes"], dmg_record["sha256"],
        )
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        fail(f"invalid release metadata: {error}")
    if metadata.get("schema_version") != 1 or metadata.get("notarization", {}).get("status") != "stapled":
        fail("release metadata must describe a schema-1 stapled release")
    if any(value is None for value in required) or not dmg.is_file():
        fail("release metadata is incomplete or its sibling DMG is missing")
    if dmg.stat().st_size != dmg_record["size_bytes"] or sha256_file(dmg) != dmg_record["sha256"]:
        fail("sibling DMG size or SHA-256 does not match the release record")

    release = {
        "bundle_identifier": metadata["bundle_identifier"],
        "instance_id": metadata["instance_id"],
        "product_version": metadata["product_version"],
        "bundle_version": metadata["bundle_version"],
        "runtime_profile": args.runtime_profile,
        "minimum_system_version": metadata["minimum_system_version"],
        "architectures": metadata["architectures"],
        "rollout": {
            "id": args.rollout_id,
            "percentage_basis_points": args.percentage_basis_points,
        },
        "dmg": {
            "url": artifact_url(args.base_urls[0], dmg.name),
            "urls": [artifact_url(base_url, dmg.name) for base_url in args.base_urls],
            "filename": dmg.name,
            "size": dmg.stat().st_size,
            "sha256": sha256_file(dmg),
        },
        "metadata": {
            "url": artifact_url(args.base_urls[0], metadata_path.name),
            "urls": [
                artifact_url(base_url, metadata_path.name)
                for base_url in args.base_urls
            ],
            "filename": metadata_path.name,
            "size": metadata_path.stat().st_size,
            "sha256": sha256_file(metadata_path),
        },
    }
    manifest = {"schema_version": 1, "channel": args.channel, "releases": [release]}
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, output)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    print(f"Generated update manifest {output}")


if __name__ == "__main__":
    main()
