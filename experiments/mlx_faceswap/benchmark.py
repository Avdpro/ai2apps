#!/usr/bin/env python3
"""Repeatable warm inference comparison for the locked face model stack."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort

from .onnx_mlx import MLXOnnxGraph
from .validate_parity import inputs_for


def summary(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    p95_index = min(len(ordered) - 1, int(np.ceil(len(ordered) * 0.95)) - 1)
    return {
        "median_ms": statistics.median(samples) * 1000,
        "p95_ms": ordered[p95_index] * 1000,
        "min_ms": min(samples) * 1000,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "model",
        choices=(
            "arcface",
            "scrfd",
            "yunet",
            "inswapper",
            "xseg",
            "simswap",
            "simswap_arcface",
            "gfpgan",
            "liveportrait_appearance",
            "liveportrait_motion",
            "liveportrait_warping",
        ),
    )
    parser.add_argument("model_path", type=Path)
    parser.add_argument("--source-image", type=Path)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument(
        "--float16-mode",
        choices=("fp16_compatible", "bf16"),
        default="fp16_compatible",
        help="Map ONNX FP16 tensors to compatible FP16 or native BF16 storage.",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Compile the complete MLX graph after its first trace.",
    )
    args = parser.parse_args()
    feeds = inputs_for(args.model, args.model_path, 20260905, args.source_image)

    session = ort.InferenceSession(
        str(args.model_path), providers=["CPUExecutionProvider"]
    )
    graph = MLXOnnxGraph(args.model_path, float16_mode=args.float16_mode)
    mlx_feeds = {name: graph.mx.array(value) for name, value in feeds.items()}
    call_graph = graph
    if args.compile:
        names = tuple(mlx_feeds)
        compiled = graph.mx.compile(
            lambda *values: tuple(graph(dict(zip(names, values, strict=True))))
        )

        def call_graph(current):
            return list(compiled(*(current[name] for name in names)))

    for _ in range(args.warmup):
        session.run(None, feeds)
        values = call_graph(mlx_feeds)
        graph.evaluate(values)

    ort_times = []
    mlx_times = []
    for _ in range(args.runs):
        started = time.perf_counter()
        session.run(None, feeds)
        ort_times.append(time.perf_counter() - started)
        started = time.perf_counter()
        values = call_graph(mlx_feeds)
        graph.evaluate(values)
        mlx_times.append(time.perf_counter() - started)
    report = {
        "model": args.model,
        "shape_profile": (
            "320x320"
            if args.model == "scrfd"
            else "640x640"
            if args.model == "yunet"
            else "native"
        ),
        "warmup": args.warmup,
        "runs": args.runs,
        "float16_mode": args.float16_mode,
        "compiled": args.compile,
        "onnxruntime_cpu": summary(ort_times),
        "mlx": summary(mlx_times),
        "median_speedup": statistics.median(ort_times) / statistics.median(mlx_times),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
