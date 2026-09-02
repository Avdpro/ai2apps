#!/usr/bin/env python3
"""Run a real generation or edit request through the packaged Worker adapter."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / "src"
sys.path.insert(0, str(SOURCE))

from worker_adapter import (  # noqa: E402
    PACKAGE_MODEL_ID,
    WEIGHTS_REVISION,
    Ideogram4Adapter,
)

from ai2apps.model_worker import ModelWorkerRequest  # noqa: E402


class SmokeContext:
    def __init__(self, checkpoint: Path, data_root: Path) -> None:
        self._checkpoint = checkpoint
        self.data_root = data_root
        self.package_root = PACKAGE

    def checkpoint_for(self, _model_id: str):
        return SimpleNamespace(path=self._checkpoint, revision=WEIGHTS_REVISION)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--prompt", default="A precise Swiss design poster")
    parser.add_argument("--size", default="512x512")
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strength", type=float, default=0.85)
    parser.add_argument("--compile-denoisers", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    output_root = args.output.parent / f".{args.output.stem}-worker"
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": PACKAGE_MODEL_ID,
        "prompt": args.prompt,
        "size": args.size,
        "steps": args.steps,
        "seed": args.seed,
        "compileDenoisers": args.compile_denoisers,
    }
    operation = "image_generation"
    if args.reference is not None:
        mime = {".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}.get(
            args.reference.suffix.lower(), "png"
        )
        payload["imageDataUrls"] = [
            f"data:image/{mime};base64,"
            + base64.b64encode(args.reference.read_bytes()).decode("ascii")
        ]
        payload["strength"] = args.strength
        operation = "image_edit"
    adapter = Ideogram4Adapter(
        SmokeContext(args.checkpoint.resolve(), output_root / "data")
    )
    request = ModelWorkerRequest(
        operation,
        payload,
        "ideogram4-worker-smoke",
        output_root=output_root,
    )
    result = await adapter.invoke(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(base64.b64decode(result["data"][0]["b64_json"]))
    summary = {k: v for k, v in result.items() if k != "data"}
    summary["image"] = {
        key: value for key, value in result["image"].items() if key != "dataUrl"
    }
    summary["output"] = str(args.output.resolve())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
