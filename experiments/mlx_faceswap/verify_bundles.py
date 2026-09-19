#!/usr/bin/env python3
"""Verify parser-free bundle manifests without importing ONNX or MLX."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_bundle(path: Path) -> dict[str, object]:
    manifest = json.loads((path / "bundle.json").read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("format") != "ai2apps.omlx.graph"
    ):
        raise ValueError(f"unsupported bundle manifest: {path}")
    result: dict[str, object] = {"bundle": str(path), "valid": True, "files": {}}
    for field in ("graph", "weights"):
        spec = manifest[field]
        artifact = path / spec["filename"]
        actual_size = artifact.stat().st_size
        actual_hash = _sha256(artifact)
        if actual_size != spec["size"] or actual_hash != spec["sha256"]:
            raise ValueError(f"bundle integrity mismatch: {artifact}")
        result["files"][field] = {"size": actual_size, "sha256": actual_hash}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps([verify_bundle(path) for path in args.paths], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
