#!/usr/bin/env python3
"""Invoke the packaged GhostV2 adapter against a local checkpoint."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

PACKAGE_SOURCE = Path(__file__).resolve().parents[1] / "src"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACKAGE_SOURCE))
sys.path.insert(1, str(REPOSITORY_ROOT))

from mlx_faceswap.worker_adapter import create_adapter  # noqa: E402


class SmokeRequest:
    def __init__(self, args) -> None:
        self.operation = "video_generation" if args.video else "image_edit"
        self.request_id = "ghostv2-package-smoke"
        self.output_root = args.output
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.progress = None
        target_role = "source_video" if args.video else "source_image"
        self.payload = {
            "model": "ai2apps.model.face-swap-mlx/default",
            "inputs": {
                "reference_image": {"part_name": "identity"},
                target_role: {"part_name": "target"},
            },
            "parameters": {
                "precision": "fp16",
                **(
                    {
                        "batch_size": args.batch_size,
                        "detection_interval": args.detection_interval,
                        "audio_output_mode": "auto",
                    }
                    if args.video
                    else {}
                ),
            },
        }
        self._parts = {
            "identity": SimpleNamespace(path=args.identity),
            "target": SimpleNamespace(path=args.video or args.image),
        }

    def part(self, name: str):
        return self._parts[name]


async def run(args) -> None:
    context = SimpleNamespace(
        checkpoint_for=lambda model_id: SimpleNamespace(path=args.checkpoint)
    )
    adapter = create_adapter(context)
    artifact = await adapter.invoke(SmokeRequest(args))
    print(
        json.dumps(
            {
                "path": str(artifact.path),
                "media_type": artifact.media_type,
                "metadata": artifact.metadata,
            },
            indent=2,
        )
    )
    await adapter.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--image", type=Path)
    target.add_argument("--video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--detection-interval", type=int, default=1)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
