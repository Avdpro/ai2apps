#!/usr/bin/env python3
"""Numerical and performance benchmark for Z-Image Metal RMS fusions."""

import argparse
import json
import time

import mlx.core as mx

from z_image_fused_rms import residual_rms_gate, rms_scale


def measure(function, iterations):
    for _ in range(2):
        mx.eval(function())
    started = time.perf_counter()
    for _ in range(iterations):
        mx.eval(function())
    return (time.perf_counter() - started) / iterations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=4352)
    parser.add_argument("--hidden", type=int, default=3840)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    mx.random.seed(29)
    shape = (1, args.rows, args.hidden)
    x = mx.random.normal(shape).astype(mx.bfloat16)
    branch = mx.random.normal(shape).astype(mx.bfloat16)
    weight = mx.random.normal((args.hidden,)).astype(mx.bfloat16)
    scale = mx.random.normal((1, 1, args.hidden)).astype(mx.bfloat16)
    gate = mx.random.normal((1, 1, args.hidden)).astype(mx.bfloat16)
    eps = 1e-5

    def reference_norm():
        return mx.fast.rms_norm(x, weight, eps) * scale

    def fused_norm():
        return rms_scale(x, weight, scale[0], eps)

    def reference_residual():
        return x + gate * mx.fast.rms_norm(branch, weight, eps)

    def fused_residual():
        return residual_rms_gate(x, branch, weight, gate[0], eps)

    ref_norm, got_norm = reference_norm(), fused_norm()
    ref_residual, got_residual = reference_residual(), fused_residual()
    mx.eval(ref_norm, got_norm, ref_residual, got_residual)
    ref_norm_s = measure(reference_norm, args.iterations)
    fused_norm_s = measure(fused_norm, args.iterations)
    ref_residual_s = measure(reference_residual, args.iterations)
    fused_residual_s = measure(fused_residual, args.iterations)
    print(json.dumps({
        "shape": list(shape),
        "dtype": "bfloat16",
        "norm_max_abs_error": float(mx.max(mx.abs(ref_norm - got_norm)).item()),
        "norm_mean_abs_error": float(mx.mean(mx.abs(ref_norm - got_norm)).item()),
        "residual_max_abs_error": float(mx.max(mx.abs(ref_residual - got_residual)).item()),
        "residual_mean_abs_error": float(mx.mean(mx.abs(ref_residual - got_residual)).item()),
        "reference_norm_seconds": ref_norm_s,
        "fused_norm_seconds": fused_norm_s,
        "norm_speedup": ref_norm_s / fused_norm_s,
        "reference_residual_seconds": ref_residual_s,
        "fused_residual_seconds": fused_residual_s,
        "residual_speedup": ref_residual_s / fused_residual_s,
    }, indent=2))


if __name__ == "__main__":
    main()
