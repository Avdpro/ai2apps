#!/usr/bin/env python3
"""Deterministic Qwen Image MLX baseline for speed and quality comparison."""

import argparse
import copy
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
from mflux.models.common.config.model_config import ModelConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, default=Path(__file__).with_name("prompts.json"))
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--guidance", type=float, default=4.0)
    parser.add_argument("--quantize", type=int, choices=(4, 6, 8), default=8)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--optimized", action="store_true")
    parser.add_argument("--batched-cfg", action="store_true")
    parser.add_argument("--single-pass", action="store_true")
    parser.add_argument("--shared-cfg", action="store_true")
    parser.add_argument("--compiled-shared-cfg", action="store_true")
    parser.add_argument("--fused-rope", action="store_true")
    parser.add_argument("--fused-block", action="store_true")
    parser.add_argument("--negative-cache", action="store_true")
    parser.add_argument("--fused-qkv", action="store_true")
    parser.add_argument("--metal-capture", type=Path)
    parser.add_argument("--quant-group-size", type=int, choices=(32, 64, 128), default=64)
    args = parser.parse_args()
    if args.single_pass and args.guidance != 1.0:
        parser.error("--single-pass requires --guidance 1")

    args.output.mkdir(parents=True, exist_ok=True)
    prompts = json.loads(args.prompts.read_text())
    if args.fused_rope:
        from qwen_fused_rope import install_fused_rope

        if not install_fused_rope():
            parser.error("--fused-rope requires Apple Metal")
    if args.fused_block:
        from qwen_fused_block import install_fused_blocks

        if not install_fused_blocks():
            parser.error("--fused-block requires Apple Metal")
    if args.fused_qkv:
        from qwen_fused_qkv import install_fused_qkv

        install_fused_qkv()
    config = copy.copy(ModelConfig.qwen_image())
    config.model_name = "Qwen/Qwen-Image-2512"
    from mflux.models.qwen.weights.qwen_weight_definition import QwenWeightDefinition

    QwenWeightDefinition.quantization_group_size = args.quant_group_size
    if args.quant_group_size == 128:
        base_quantization_predicate = QwenWeightDefinition.quantization_predicate

        def mixed_group_quantization_predicate(path, module, bits=None):
            decision = base_quantization_predicate(path, module, bits)
            if not decision:
                return decision
            weight = getattr(module, "weight", None)
            shape = getattr(weight, "shape", None)
            if shape and shape[-1] % 128:
                if isinstance(decision, dict):
                    return {**decision, "group_size": 64}
                return {"group_size": 64}
            return decision

        QwenWeightDefinition.quantization_predicate = staticmethod(
            mixed_group_quantization_predicate
        )
    mx.reset_peak_memory()
    load_started = time.perf_counter()
    if args.negative_cache:
        from negative_cache_pipeline import NegativeCacheQwenImage as Pipeline
    elif args.compiled_shared_cfg:
        from shared_cfg_pipeline import CompiledSharedCFGQwenImage as Pipeline
    elif args.shared_cfg:
        from shared_cfg_pipeline import SharedCFGQwenImage as Pipeline
    elif args.batched_cfg or args.single_pass:
        from batched_cfg_pipeline import BatchedCFGQwenImage as Pipeline
    elif args.optimized:
        from optimized_pipeline import OptimizedQwenImage as Pipeline
    else:
        from mflux.models.qwen.variants.txt2img.qwen_image import QwenImage as Pipeline
    pipeline = Pipeline(
        model_config=config,
        model_path=args.model_path,
        quantize=args.quantize,
    )
    if args.fused_qkv:
        from qwen_fused_qkv import prepare_fused_qkv

        prepare_fused_qkv(pipeline)
    load_seconds = time.perf_counter() - load_started
    load_peak_memory_bytes = mx.get_peak_memory()
    resident_after_load_bytes = mx.get_active_memory()
    mx.reset_peak_memory()

    rows = []
    for prompt_index, item in enumerate(prompts):
        timings = []
        denoise_timings = []
        for repeat in range(args.repeats):
            seed = int(item.get("seed", 2000 + prompt_index))
            capture_this_request = (
                args.metal_capture is not None and prompt_index == 0 and repeat == 0
            )
            if capture_this_request:
                args.metal_capture.parent.mkdir(parents=True, exist_ok=True)
                mx.metal.start_capture(str(args.metal_capture))
            started = time.perf_counter()
            try:
                result = pipeline.generate_image(
                    seed=seed,
                    prompt=item["prompt"],
                    negative_prompt="blurry, distorted, unreadable text, watermark",
                    num_inference_steps=args.steps,
                    width=args.width,
                    height=args.height,
                    guidance=args.guidance,
                )
            finally:
                if capture_this_request:
                    mx.metal.stop_capture()
            elapsed = time.perf_counter() - started
            timings.append(elapsed)
            denoise_timings.append(float(result.generation_time))
            if repeat == args.repeats - 1:
                result.save(args.output / f"{item['id']}.png", overwrite=True)
        rows.append(
            {
                "id": item["id"],
                "prompt": item["prompt"],
                "seed": int(item.get("seed", 2000 + prompt_index)),
                "seconds": timings,
                "denoise_seconds": denoise_timings,
                "first_seconds": timings[0],
                "steady_median_seconds": statistics.median(timings[1:] or timings),
            }
        )
    report = {
        "backend": "mlx",
        "model": "Qwen/Qwen-Image-2512",
        "implementation": (
            "experimental-fused-qkv"
            if args.fused_qkv
            else "experimental-negative-cache"
            if args.negative_cache
            else "experimental-fused-block"
            if args.fused_block
            else "experimental-fused-rope"
            if args.fused_rope
            else "experimental-compiled-shared-cfg"
            if args.compiled_shared_cfg
            else "experimental-shared-cfg"
            if args.shared_cfg
            else
            ("experimental-single-pass" if args.single_pass else "experimental-batched-cfg")
            if args.batched_cfg or args.single_pass
            else ("ai2apps-optimized" if args.optimized else "mflux-0.19.0-baseline")
        ),
        "quantization": f"q{args.quantize}",
        "quantization_group_size": args.quant_group_size,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "guidance": args.guidance,
        "load_seconds": load_seconds,
        "load_peak_memory_bytes": load_peak_memory_bytes,
        "resident_after_load_bytes": resident_after_load_bytes,
        "inference_peak_memory_bytes": mx.get_peak_memory(),
        "resident_after_inference_bytes": mx.get_active_memory(),
        "median_generation_seconds": statistics.median(
            row["steady_median_seconds"] for row in rows
        ),
        "optimization_stats": (
            pipeline.ai2apps_optimization_stats()
            if hasattr(pipeline, "ai2apps_optimization_stats")
            else None
        ),
        "runs": rows,
    }
    (args.output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
