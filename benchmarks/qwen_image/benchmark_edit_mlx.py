#!/usr/bin/env python3
"""Deterministic Qwen Image Edit 2511 MLX speed/quality baseline."""

import argparse
import copy
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
from mflux.models.common.config.model_config import ModelConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--guidance", type=float, default=2.5)
    parser.add_argument("--quantize", type=int, choices=(4, 8), default=8)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--optimized", action="store_true")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    config = copy.copy(ModelConfig.qwen_image_edit())
    config.model_name = "Qwen/Qwen-Image-Edit-2511"
    mx.reset_peak_memory()
    load_started = time.perf_counter()
    if args.optimized:
        from optimized_pipeline import OptimizedQwenImageEdit as Pipeline
    else:
        from mflux.models.qwen.variants.edit.qwen_image_edit import QwenImageEdit as Pipeline
    pipeline = Pipeline(
        model_config=config,
        model_path=args.model_path,
        quantize=args.quantize,
    )
    load_seconds = time.perf_counter() - load_started
    load_peak_memory_bytes = mx.get_peak_memory()
    resident_after_load_bytes = mx.get_active_memory()
    mx.reset_peak_memory()

    rows = []
    for case_index, item in enumerate(cases):
        reference_paths = [str((args.cases.parent / value).resolve()) for value in item["images"]]
        timings = []
        denoise_timings = []
        for repeat in range(args.repeats):
            started = time.perf_counter()
            result = pipeline.generate_image(
                seed=3000 + case_index,
                prompt=item["prompt"],
                negative_prompt="blurry, distorted, unreadable text, watermark",
                image_paths=reference_paths,
                num_inference_steps=args.steps,
                width=args.width,
                height=args.height,
                guidance=args.guidance,
            )
            timings.append(time.perf_counter() - started)
            denoise_timings.append(float(result.generation_time))
            if repeat == args.repeats - 1:
                result.save(args.output / f"{item['id']}.png", overwrite=True)
        rows.append(
            {
                "id": item["id"],
                "prompt": item["prompt"],
                "images": reference_paths,
                "seed": 3000 + case_index,
                "seconds": timings,
                "denoise_seconds": denoise_timings,
                "first_seconds": timings[0],
                "steady_median_seconds": statistics.median(timings[1:] or timings),
            }
        )

    report = {
        "backend": "mlx",
        "model": "Qwen/Qwen-Image-Edit-2511",
        "implementation": "ai2apps-optimized" if args.optimized else "mflux-0.19.0-baseline",
        "quantization": f"q{args.quantize}",
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
    (args.output / "metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
