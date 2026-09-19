#!/usr/bin/env python3
"""Validate parser-free MLX execution of exported GhostV2 graphs."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from PIL import Image

from .onnx_mlx import MLXOnnxGraph


def _input(path: Path, size: int) -> np.ndarray:
    with Image.open(path) as image:
        rgb = np.asarray(
            image.convert("RGB").resize((size, size), Image.Resampling.BILINEAR),
            dtype=np.float32,
        )
    return np.ascontiguousarray((rgb.transpose(2, 0, 1)[None] / 127.5) - 1.0)


def _rgb(value: np.ndarray) -> np.ndarray:
    return np.clip(
        np.rint((value[0].transpose(1, 2, 0) + 1.0) * 127.5), 0, 255
    ).astype(np.uint8)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--embedding", type=Path)
    parser.add_argument("--embedding-reference", type=Path)
    parser.add_argument("--tensor-reference", type=Path)
    parser.add_argument(
        "--precision", choices=("fp32", "fp16", "bf16"), default="fp32"
    )
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()

    mx.reset_peak_memory()
    started = time.perf_counter()
    storage_mode = "bf16" if args.precision == "bf16" else "fp16_compatible"
    recognizer = MLXOnnxGraph(
        args.models / "ghostv2_cvlface.omlx", float16_mode=storage_mode
    )
    generator = MLXOnnxGraph(
        args.models / "ghostv2_generator.omlx", float16_mode=storage_mode
    )
    call_recognizer = recognizer
    call_generator = generator
    if args.compile:
        compiled_recognizer = mx.compile(
            lambda image: tuple(
                recognizer({recognizer.inputs[0]: image})
            )
        )
        compiled_generator = mx.compile(
            lambda target_value, identity_value: tuple(
                generator(
                    {
                        generator.inputs[0]: target_value,
                        generator.inputs[1]: identity_value,
                    }
                )
            )
        )

        def call_recognizer(feeds):
            return list(compiled_recognizer(feeds[recognizer.inputs[0]]))

        def call_generator(feeds):
            return list(
                compiled_generator(
                    feeds[generator.inputs[0]], feeds[generator.inputs[1]]
                )
            )
    load_seconds = time.perf_counter() - started
    source_256 = mx.array(_input(args.source, 256))
    source = mx.transpose(
        nn.Upsample(
            scale_factor=(112 / 256, 112 / 256),
            mode="linear",
            align_corners=False,
        )(mx.transpose(source_256, (0, 2, 3, 1))),
        (0, 3, 1, 2),
    )
    target = _input(args.target, 256)
    dtype = {
        "fp32": mx.float32,
        "fp16": mx.float16,
        "bf16": mx.bfloat16,
    }[args.precision]
    source = source.astype(dtype)
    target = mx.array(target).astype(dtype)

    started = time.perf_counter()
    embedding_metrics = None
    if args.embedding is None:
        embedding = call_recognizer({recognizer.inputs[0]: source})[0]
        embedding = embedding / mx.maximum(
            mx.sqrt(mx.sum(embedding * embedding, axis=1, keepdims=True)), 1e-12
        )
        mx.eval(embedding)
        if args.embedding_reference is not None:
            reference_embedding = np.load(args.embedding_reference).astype(np.float32)
            mlx_embedding = np.asarray(embedding, dtype=np.float32)
            delta = mlx_embedding - reference_embedding
            embedding_metrics = {
                "cosine": float(np.sum(mlx_embedding * reference_embedding)),
                "max_abs": float(np.max(np.abs(delta))),
                "mean_abs": float(np.mean(np.abs(delta))),
            }
    else:
        embedding = mx.array(np.load(args.embedding)).astype(dtype)
        mx.eval(embedding)
    identity_seconds = time.perf_counter() - started
    generator_timings = []
    output = None
    for _ in range(max(1, args.runs)):
        started = time.perf_counter()
        output = call_generator(
            {generator.inputs[0]: target, generator.inputs[1]: embedding}
        )[0]
        mx.eval(output)
        generator_timings.append(time.perf_counter() - started)
    assert output is not None
    inference_seconds = identity_seconds + sum(generator_timings)
    output_rgb = _rgb(np.asarray(output, dtype=np.float32))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output_rgb, mode="RGB").save(args.output)

    metrics = None
    if args.reference is not None:
        with Image.open(args.reference) as image:
            reference = np.asarray(image.convert("RGB"), dtype=np.float32)
        delta = output_rgb.astype(np.float32) - reference
        metrics = {
            "max_abs": float(np.max(np.abs(delta))),
            "mean_abs": float(np.mean(np.abs(delta))),
            "rmse": float(np.sqrt(np.mean(delta * delta))),
        }
    tensor_metrics = None
    if args.tensor_reference is not None:
        reference_tensor = np.load(args.tensor_reference).astype(np.float32)
        delta = np.asarray(output, dtype=np.float32) - reference_tensor
        tensor_metrics = {
            "max_abs": float(np.max(np.abs(delta))),
            "mean_abs": float(np.mean(np.abs(delta))),
            "rmse": float(np.sqrt(np.mean(delta * delta))),
        }
    print(
        json.dumps(
            {
                "output": str(args.output),
                "load_seconds": load_seconds,
                "inference_seconds": inference_seconds,
                "identity_seconds": identity_seconds,
                "generator_runs": generator_timings,
                "warm_generator_fps": 1.0 / generator_timings[-1],
                "peak_memory_bytes": mx.get_peak_memory(),
                "reference": metrics,
                "tensor_reference": tensor_metrics,
                "embedding_reference": embedding_metrics,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
