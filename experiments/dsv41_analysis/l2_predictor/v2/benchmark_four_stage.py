"""Measure isolated Metal latency for a frozen four-stage predictor set."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import numpy as np

from train_four_stage import STAGES, StageHead


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--suffix", required=True)
    parser.add_argument(
        "--stage-suffix",
        action="append",
        default=[],
        metavar="STAGE=SUFFIX",
        help="override --suffix for one stage; may be repeated",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=200)
    args = parser.parse_args()

    suffixes = {name: args.suffix for name in STAGES}
    for item in args.stage_suffix:
        try:
            name, suffix = item.split("=", 1)
        except ValueError as exc:
            raise SystemExit(f"invalid --stage-suffix {item!r}; expected STAGE=SUFFIX") from exc
        if name not in suffixes or not suffix:
            raise SystemExit(f"invalid --stage-suffix {item!r}; stage must be one of {tuple(STAGES)}")
        suffixes[name] = suffix

    results = {}
    total_parameters = 0
    total_weight_bytes = 0
    for name, stage in STAGES.items():
        model_dir = args.root / f"{name}-{suffixes[name]}"
        manifest = json.loads((model_dir / "manifest.json").read_text())
        model = StageHead(
            len(stage.targets),
            manifest["rank"],
            stage.trigger_layer is not None,
            manifest["blocks"],
            manifest.get("loss", "bce"),
            manifest.get("per_layer", False),
            manifest.get("cache_feature", False),
        )
        model.load_weights(str(model_dir / "model.safetensors"), strict=False)
        history = mx.random.normal((1, len(stage.targets), 5120)).astype(mx.float16)
        trigger = mx.random.normal((1, 5120)).astype(mx.float16)
        token = mx.random.normal((1, 5120)).astype(mx.float16)
        final = mx.random.normal((1, 5120)).astype(mx.float16)
        resident = mx.zeros((1, len(stage.targets), 384), dtype=mx.uint8)
        for _ in range(10):
            mx.eval(model(history, trigger, token, final, resident))
        timings = []
        for _ in range(args.repetitions):
            started = time.perf_counter()
            mx.eval(model(history, trigger, token, final, resident))
            timings.append((time.perf_counter() - started) * 1000)
        parameters = json.loads((model_dir / "result.json").read_text())["parameters"]
        weight_bytes = (model_dir / "model.safetensors").stat().st_size
        total_parameters += parameters
        total_weight_bytes += weight_bytes
        results[name] = {
            "median_ms": float(np.median(timings)),
            "p95_ms": float(np.percentile(timings, 95)),
            "parameters": parameters,
            "weight_bytes": weight_bytes,
        }
        del model
        mx.clear_cache()
    result = {
        "suffix": args.suffix,
        "stage_suffixes": suffixes,
        "repetitions": args.repetitions,
        "stages": results,
        "sum_stage_median_ms": sum(value["median_ms"] for value in results.values()),
        "total_parameters": total_parameters,
        "total_weight_bytes": total_weight_bytes,
        "note": "isolated synchronous single-token latency; not overlapped with the main forward or SSD reads",
    }
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
