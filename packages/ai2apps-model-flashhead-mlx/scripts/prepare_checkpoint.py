#!/usr/bin/env python3
"""Prepare self-contained Lite/Pro checkpoint snapshots; no upload or signing."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "src"))
from flashhead_mlx.checkpoint import SCHEMA, required_files  # noqa: E402


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def prepare(source, output, variant):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError(
            "Output already exists; frozen checkpoints are never overwritten"
        )
    if output == PACKAGE or PACKAGE in output.parents:
        raise ValueError("Checkpoint bytes must remain outside the Package source")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".flashhead-", dir=output.parent))
    try:
        files = []
        for relative in required_files(variant):
            original = source / (
                "wav2vec2" if relative.startswith("wav2vec2/") else "flashhead"
            )
            original = original / (
                relative.removeprefix("wav2vec2/")
                if relative.startswith("wav2vec2/")
                else relative
            )
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            files.append(
                {
                    "path": relative,
                    "size": target.stat().st_size,
                    "sha256": digest(target),
                }
            )
        lock = json.loads((PACKAGE / "upstream-lock.json").read_text())
        origins = {
            name: lock["weights"][name]["revision"]
            for name in (
                "Soul-AILab/SoulX-FlashHead-1_3B",
                "facebook/wav2vec2-base-960h",
            )
        }
        manifest = {
            "schema": SCHEMA,
            "variant": variant,
            "format": "safetensors",
            "files": files,
            "origins": origins,
            "preparation": "Original tensor layout; native MLX mapping on load. Pro Wan VAE converted offline with weights_only=True.",
        }
        (temporary / "ai2apps-checkpoint.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        shutil.copyfile(PACKAGE / "LICENSE.upstream", temporary / "LICENSE")
        (temporary / "NOTICE.md").write_text(
            "SoulX-FlashHead: "
            + lock["sources"]["flashhead"]["origin"]
            + "\nCommit: "
            + lock["sources"]["flashhead"]["commit"]
            + "\nWav2Vec2: facebook/wav2vec2-base-960h\nVAE: LTX-Video (Lite) / Wan 2.1 (Pro), as distributed in the pinned FlashHead repository.\nCheckpoint terms must be finalized from upstream model sources before redistribution. This local staging manifest is not a publication receipt.\n"
        )
        (temporary / "README.md").write_text(
            f"# FlashHead {variant.title()} MLX checkpoint\n\nPrepared local snapshot, not yet published. See ai2apps-checkpoint.json for exact upstream revisions and hashes.\nContains only this variant, its VAE and Wav2Vec2. Use AI2Apps FlashHead Model Package; no Runtime is embedded.\n"
        )
        os.replace(temporary, output)
        return {
            "variant": variant,
            "root": str(output),
            "tensor_bytes": sum(f["size"] for f in files),
            "manifest_sha256": digest(output / "ai2apps-checkpoint.json"),
            "file_count": len(files),
        }
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Root containing flashhead/ and wav2vec2/",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=["lite", "pro"], required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.variant), indent=2))
