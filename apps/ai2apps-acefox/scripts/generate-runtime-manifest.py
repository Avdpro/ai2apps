#!/usr/bin/env python3
"""Generate the v1 manifest verified by AI2AppsLauncher before Local starts."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path


CRITICAL_ARTIFACTS = (
    "bin/omlx",
    "Python/cpython-3.11/bin/python3",
    "app/ai2apps/__init__.py",
    "app/ai2apps/cli.py",
    "app/omlx/__init__.py",
    "app/omlx/cli.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runtime-version", required=True)
    parser.add_argument("--runtime-profile", choices=("full", "cloud"), default="full")
    args = parser.parse_args()

    root = args.root.resolve(strict=True)
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("runtime manifests currently support macOS arm64 only")

    artifacts = []
    for relative_path in CRITICAL_ARTIFACTS:
        path = root / relative_path
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise SystemExit(f"invalid runtime artifact: {relative_path}")
        artifacts.append(
            {
                "relative_path": relative_path,
                "sha256": sha256(path),
                "size": path.stat().st_size,
            }
        )

    manifest = {
        "schema_version": 1,
        "runtime_version": args.runtime_version,
        "runtime_profile": args.runtime_profile,
        "platform": "macos",
        "architecture": "arm64",
        "entrypoint": "bin/omlx",
        "minimum_shell_protocol": 1,
        "minimum_local_api_version": 1,
        "artifacts": artifacts,
    }
    output = root / "runtime-manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    output.chmod(0o644)


if __name__ == "__main__":
    main()
