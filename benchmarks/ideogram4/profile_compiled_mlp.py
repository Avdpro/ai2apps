#!/usr/bin/env python3
"""Profile a cross-layer compiled Q4 Ideogram MLP graph."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from mlx_model import load_quantized_transformer


@mx.compile
def compiled_q4_mlp(
    value,
    w1,
    s1,
    b1,
    w2,
    s2,
    b2,
    w3,
    s3,
    b3,
):
    value = value.astype(mx.bfloat16)
    gate = mx.quantized_matmul(
        value, w1, scales=s1, biases=b1, group_size=64, bits=4
    )
    up = mx.quantized_matmul(
        value, w3, scales=s3, biases=b3, group_size=64, bits=4
    )
    hidden = nn.silu(gate) * up
    output = mx.quantized_matmul(
        hidden, w2, scales=s2, biases=b2, group_size=64, bits=4
    )
    return output.astype(mx.float32)


@mx.compile
def compiled_batched_q4_mlp(
    value,
    gate_up_weight,
    gate_up_scales,
    gate_up_biases,
    w2,
    s2,
    b2,
):
    value = value.astype(mx.bfloat16)
    gate_up = mx.quantized_matmul(
        value,
        gate_up_weight,
        scales=gate_up_scales,
        biases=gate_up_biases,
        group_size=64,
        bits=4,
    )
    hidden = nn.silu(gate_up[0]) * gate_up[1]
    output = mx.quantized_matmul(
        hidden, w2, scales=s2, biases=b2, group_size=64, bits=4
    )
    return output.astype(mx.float32)


def call_compiled(layer, value):
    mlp = layer.feed_forward
    return compiled_q4_mlp(
        value,
        mlp.w1.weight,
        mlp.w1.scales,
        mlp.w1.biases,
        mlp.w2.weight,
        mlp.w2.scales,
        mlp.w2.biases,
        mlp.w3.weight,
        mlp.w3.scales,
        mlp.w3.biases,
    )


def measure(function, warmup: int, repeats: int):
    started = time.perf_counter()
    mx.eval(function())
    first = time.perf_counter() - started
    for _ in range(warmup):
        mx.eval(function())
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        mx.eval(function())
        samples.append(time.perf_counter() - started)
    return {
        "first_seconds": first,
        "median_seconds": statistics.median(samples),
        "minimum_seconds": min(samples),
        "samples_seconds": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sequence", type=int, default=1235)
    parser.add_argument("--warmup", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=15)
    args = parser.parse_args()

    model = load_quantized_transformer(args.checkpoint, bits=4, group_size=64)
    value = mx.random.normal((1, args.sequence, model.config.emb_dim))
    mx.eval(value)
    reference = model.layers[0].feed_forward(value)
    candidate = call_compiled(model.layers[0], value)
    mlp = model.layers[0].feed_forward
    gate_up_weight = mx.stack((mlp.w1.weight, mlp.w3.weight))
    gate_up_scales = mx.stack((mlp.w1.scales, mlp.w3.scales))
    gate_up_biases = mx.stack((mlp.w1.biases, mlp.w3.biases))
    mx.eval(gate_up_weight, gate_up_scales, gate_up_biases)
    batched_candidate = compiled_batched_q4_mlp(
        value,
        gate_up_weight,
        gate_up_scales,
        gate_up_biases,
        mlp.w2.weight,
        mlp.w2.scales,
        mlp.w2.biases,
    )
    mx.eval(reference, candidate, batched_candidate)
    error = mx.max(mx.abs(reference - candidate)).item()
    batched_error = mx.max(mx.abs(reference - batched_candidate)).item()

    report = {
        "max_absolute_error": error,
        "batched_max_absolute_error": batched_error,
        "eager": measure(
            lambda: model.layers[0].feed_forward(value),
            args.warmup,
            args.repeats,
        ),
        "compiled_layer_0": measure(
            lambda: call_compiled(model.layers[0], value),
            args.warmup,
            args.repeats,
        ),
        "compiled_layer_1": measure(
            lambda: call_compiled(model.layers[1], value),
            args.warmup,
            args.repeats,
        ),
        "compiled_batched_layer_0": measure(
            lambda: compiled_batched_q4_mlp(
                value,
                gate_up_weight,
                gate_up_scales,
                gate_up_biases,
                mlp.w2.weight,
                mlp.w2.scales,
                mlp.w2.biases,
            ),
            args.warmup,
            args.repeats,
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
