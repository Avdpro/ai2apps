#!/usr/bin/env python3
"""Deterministic FLUX.2 Klein MLX speed/quality benchmark."""

import argparse
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from mflux.models.common.config.model_config import ModelConfig


def _install_mixed_quantization(mode: str, bits: int) -> None:
    """Patch the initializer for component-level mixed-precision experiments.

    This is intentionally benchmark-only.  Product checkpoint support is added
    only after a configuration demonstrates a useful speed/memory trade-off.
    """
    from mflux.models.common.weights.loading.weight_applier import WeightApplier
    from mflux.models.flux2.flux2_initializer import Flux2Initializer
    from mflux.models.flux2.weights.flux2_weight_definition import Flux2KleinWeightDefinition

    quantized_components = {
        "transformer-bf16": {"vae", "text_encoder"},
        "transformer-q": {"transformer"},
        "double-q": {"vae", "text_encoder"},
        "single-half-q": {"vae", "text_encoder"},
    }[mode]

    def apply_weights(model, weights, quantize):
        del quantize
        models = {
            "vae": model.vae,
            "transformer": model.transformer,
            "text_encoder": model.text_encoder,
        }
        components = {c.name: c for c in Flux2KleinWeightDefinition.get_components()}
        WeightApplier._set_weights(weights, models, components)
        predicate = Flux2KleinWeightDefinition.quantization_predicate
        for name in quantized_components:
            nn.quantize(models[name], group_size=64, class_predicate=predicate, bits=bits)
        if mode in {"double-q", "single-half-q"}:
            def transformer_predicate(path, module):
                if not predicate(path, module):
                    return False
                if mode == "double-q":
                    return path.startswith("transformer_blocks.")
                if not path.startswith("single_transformer_blocks."):
                    return False
                return int(path.split(".", 2)[1]) < 12

            nn.quantize(
                model.transformer,
                group_size=64,
                class_predicate=transformer_predicate,
                bits=bits,
            )
        model.bits = bits

    Flux2Initializer._apply_weights = staticmethod(apply_weights)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("4b", "9b"), required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompts", type=Path, default=Path(__file__).with_name("prompts.json"))
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--quantize", type=int, choices=(4, 8))
    parser.add_argument(
        "--mixed-quantization",
        choices=("transformer-bf16", "transformer-q", "double-q", "single-half-q"),
        help="Benchmark-only component split; --quantize selects the quantized side's bit width",
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--baseline", action="store_true", help="Use unmodified mflux pipeline")
    args = parser.parse_args()

    if args.mixed_quantization and args.quantize is None:
        parser.error("--mixed-quantization requires --quantize")
    if args.mixed_quantization:
        _install_mixed_quantization(args.mixed_quantization, args.quantize)

    args.output.mkdir(parents=True, exist_ok=True)
    prompts = json.loads(args.prompts.read_text())
    config = ModelConfig.flux2_klein_4b() if args.model == "4b" else ModelConfig.flux2_klein_9b()
    mx.reset_peak_memory()
    load_start = time.perf_counter()
    if args.baseline:
        from mflux.models.flux2.variants import Flux2Klein as Pipeline
    else:
        from optimized_pipeline import OptimizedFlux2Klein as Pipeline
    pipeline = Pipeline(
        model_config=config, model_path=args.model_path, quantize=args.quantize
    )
    load_seconds = time.perf_counter() - load_start
    load_peak_memory_bytes = mx.get_peak_memory()
    resident_after_load_bytes = mx.get_active_memory()
    mx.reset_peak_memory()

    rows = []
    for prompt_index, item in enumerate(prompts):
        timings = []
        denoise_timings = []
        for repeat in range(args.repeats):
            seed = 1000 + prompt_index
            started = time.perf_counter()
            result = pipeline.generate_image(
                seed=seed,
                prompt=item["prompt"],
                num_inference_steps=args.steps,
                width=args.width,
                height=args.height,
                guidance=1.0,
            )
            elapsed = time.perf_counter() - started
            timings.append(elapsed)
            denoise_timings.append(float(result.generation_time))
            if repeat == args.repeats - 1:
                result.save(args.output / f"{item['id']}.png", overwrite=True)
        rows.append({
            "id": item["id"], "prompt": item["prompt"], "seed": 1000 + prompt_index,
            "seconds": timings,
            "denoise_seconds": denoise_timings,
            "first_seconds": timings[0],
            "steady_median_seconds": statistics.median(timings[1:] or timings),
            "steady_median_denoise_seconds": statistics.median(
                denoise_timings[1:] or denoise_timings
            ),
        })
    report = {
        "backend": "mlx", "model": args.model,
        "implementation": "mflux-baseline" if args.baseline else "ai2apps-optimized",
        "quantization": (
            f"{args.mixed_quantization}-q{args.quantize}"
            if args.mixed_quantization
            else ("bf16" if args.quantize is None else f"q{args.quantize}")
        ),
        "width": args.width, "height": args.height, "steps": args.steps,
        "load_seconds": load_seconds,
        "load_peak_memory_bytes": load_peak_memory_bytes,
        "resident_after_load_bytes": resident_after_load_bytes,
        "inference_peak_memory_bytes": mx.get_peak_memory(),
        "resident_after_inference_bytes": mx.get_active_memory(),
        "median_generation_seconds": statistics.median(row["steady_median_seconds"] for row in rows),
        "median_denoise_seconds": statistics.median(
            row["steady_median_denoise_seconds"] for row in rows
        ),
        "optimization_stats": (
            pipeline.ai2apps_optimization_stats()
            if hasattr(pipeline, "ai2apps_optimization_stats") else None
        ),
        "runs": rows,
    }
    (args.output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
