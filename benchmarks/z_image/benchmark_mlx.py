#!/usr/bin/env python3
"""Deterministic Z-Image MLX baseline for speed and quality comparison."""

import argparse
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
from mflux.models.common.config.model_config import ModelConfig
from mflux.models.z_image.variants.z_image import ZImage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--prompts", type=Path, default=Path(__file__).with_name("prompts.json")
    )
    parser.add_argument("--variant", choices=("turbo", "base"), default="turbo")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--image", type=Path)
    parser.add_argument(
        "--strength",
        type=float,
        help="input-image transformation strength in (0, 1]; defaults to 0.75",
    )
    parser.add_argument("--steps", type=int)
    parser.add_argument("--guidance", type=float)
    parser.add_argument("--quantize", type=int, choices=(4, 8), default=8)
    parser.add_argument("--quant-group-size", type=int, choices=(64, 128), default=64)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--optimized", action="store_true")
    parser.add_argument("--fused-qkv", action="store_true")
    parser.add_argument("--fused-projections", action="store_true")
    parser.add_argument("--step-sync-interval", type=int, default=1)
    parser.add_argument("--fused-rms-block", action="store_true")
    args = parser.parse_args()

    if args.image is None and args.strength is not None:
        parser.error("--strength requires --image")
    if args.strength is not None and not 0.0 < args.strength <= 1.0:
        parser.error("--strength must be greater than 0 and at most 1")

    if args.fused_projections:
        args.fused_qkv = True

    if args.optimized:
        from context_precompute import install_context_precompute

        install_context_precompute()

    if args.fused_qkv:
        from projection_fusion import install_projection_fusion

        install_projection_fusion(fuse_ffn=args.fused_projections)
    if args.fused_rms_block:
        from z_image_fused_rms import install

        if not install():
            parser.error("--fused-rms-block requires Apple Metal")

    turbo = args.variant == "turbo"
    steps = args.steps or (8 if turbo else 50)
    guidance = args.guidance if args.guidance is not None else (0.0 if turbo else 4.0)
    config = ModelConfig.z_image_turbo() if turbo else ModelConfig.z_image()
    from mflux.models.z_image.weights.z_image_weight_definition import (
        ZImageWeightDefinition,
    )

    ZImageWeightDefinition.quantization_group_size = args.quant_group_size
    if args.quant_group_size == 128:
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
    prompts = json.loads(args.prompts.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)

    mx.reset_peak_memory()
    started = time.perf_counter()
    if args.step_sync_interval != 1:
        from lazy_step_pipeline import LazyStepZImage

        LazyStepZImage.sync_interval = args.step_sync_interval
        pipeline_class = LazyStepZImage
    else:
        pipeline_class = ZImage
    pipeline = pipeline_class(
        model_config=config,
        model_path=args.model_path,
        quantize=args.quantize,
    )
    if args.fused_qkv:
        from projection_fusion import prepare_projection_fusion

        prepare_projection_fusion(pipeline, fuse_ffn=args.fused_projections)
    load_seconds = time.perf_counter() - started
    load_peak = mx.get_peak_memory()
    resident_after_load = mx.get_active_memory()
    mx.reset_peak_memory()

    rows = []
    for item in prompts:
        timings = []
        denoise = []
        for repeat in range(args.repeats):
            started = time.perf_counter()
            generation = dict(
                seed=int(item["seed"]),
                prompt=item["prompt"],
                num_inference_steps=steps,
                width=args.width,
                height=args.height,
                guidance=guidance,
            )
            if args.image is not None:
                generation["image_path"] = args.image
                generation["image_strength"] = (
                    0.75 if args.strength is None else args.strength
                )
            result = pipeline.generate_image(**generation)
            timings.append(time.perf_counter() - started)
            denoise.append(float(result.generation_time))
            if repeat == args.repeats - 1:
                result.save(args.output / f"{item['id']}.png", overwrite=True)
        rows.append(
            {
                "id": item["id"],
                "seed": item["seed"],
                "seconds": timings,
                "denoise_seconds": denoise,
                "steady_median_seconds": statistics.median(timings[1:] or timings),
            }
        )
    report = {
        "backend": "mlx",
        "implementation": (
            "experimental-fused-qkv-ffn"
            if args.fused_projections
            else "experimental-fused-qkv"
            if args.fused_qkv
            else "experimental-fused-rms-lazy-steps"
            if args.fused_rms_block and args.step_sync_interval == 0
            else "experimental-context-precompute"
            if args.optimized
            else "experimental-fused-rms-block"
            if args.fused_rms_block
            else f"experimental-step-sync-{args.step_sync_interval}"
            if args.step_sync_interval != 1
            else "mflux-0.19.0-baseline"
        ),
        "model": config.model_name,
        "variant": args.variant,
        "quantization": f"q{args.quantize}",
        "quantization_group_size": args.quant_group_size,
        "width": args.width,
        "height": args.height,
        "steps": steps,
        "operation": "image_edit" if args.image is not None else "image_generation",
        "image_strength": (
            0.75 if args.image is not None and args.strength is None else args.strength
        ),
        "guidance": guidance,
        "load_seconds": load_seconds,
        "load_peak_memory_bytes": load_peak,
        "resident_after_load_bytes": resident_after_load,
        "inference_peak_memory_bytes": mx.get_peak_memory(),
        "resident_after_inference_bytes": mx.get_active_memory(),
        "median_generation_seconds": statistics.median(
            row["steady_median_seconds"] for row in rows
        ),
        "runs": rows,
    }
    (args.output / "metrics.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
