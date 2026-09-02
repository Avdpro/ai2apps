#!/usr/bin/env python3
"""Materialize a source Z-Image checkpoint as native persistent MLX weights."""

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

from mflux.models.common.config.model_config import ModelConfig
from mflux.models.z_image.variants.z_image import ZImage


def complete(root: Path, bits: int, group_size: int) -> bool:
    required = [
        root / name / "model.safetensors.index.json"
        for name in ("vae", "transformer", "text_encoder")
    ] + [root / "tokenizer" / "tokenizer.json"]
    if not all(path.is_file() for path in required):
        return False
    marker = root / ".ai2apps-derived.json"
    marker_data = json.loads(marker.read_text()) if marker.is_file() else {}
    return all(
        int(json.loads(path.read_text())["metadata"]["quantization_level"]) == bits
        for path in required[:3]
    ) and int(marker_data.get("quantization_group_size", 64)) == group_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=("turbo", "base"), default="turbo")
    parser.add_argument("--bits", type=int, choices=(4, 8), default=8)
    parser.add_argument("--group-size", type=int, choices=(64, 128), default=64)
    args = parser.parse_args()
    if complete(args.output, args.bits, args.group_size):
        print(json.dumps({"status": "already-complete", "path": str(args.output)}))
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{args.output.name}-", dir=args.output.parent))
    started = time.perf_counter()
    config = ModelConfig.z_image_turbo() if args.variant == "turbo" else ModelConfig.z_image()
    from mflux.models.z_image.weights.z_image_weight_definition import ZImageWeightDefinition

    ZImageWeightDefinition.quantization_group_size = args.group_size
    if args.group_size == 128:
        base_predicate = ZImageWeightDefinition.quantization_predicate

        def mixed_group_predicate(path, module, bits=None):
            decision = base_predicate(path, module)
            if not decision:
                return decision
            shape = getattr(getattr(module, "weight", None), "shape", None)
            if shape and shape[-1] % 128:
                return {"group_size": 64}
            return decision

        ZImageWeightDefinition.quantization_predicate = staticmethod(
            mixed_group_predicate
        )
    pipeline = ZImage(
        model_config=config,
        model_path=str(args.source),
        quantize=args.bits,
    )
    pipeline.save_model(str(staging))
    (staging / ".ai2apps-derived.json").write_text(
        json.dumps(
            {
                "format": "ai2apps.z-image-mlx-quantized/v1",
                "source": str(args.source.resolve()),
                "variant": args.variant,
                "quantization_bits": args.bits,
                "quantization_group_size": args.group_size,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not complete(staging, args.bits, args.group_size):
        raise RuntimeError("native Z-Image checkpoint is incomplete")
    if args.output.exists():
        raise RuntimeError(f"refusing to replace existing output: {args.output}")
    os.replace(staging, args.output)
    print(
        json.dumps(
            {
                "status": "created",
                "path": str(args.output),
                "seconds": time.perf_counter() - started,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
