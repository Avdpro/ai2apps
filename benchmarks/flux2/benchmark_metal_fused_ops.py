#!/usr/bin/env python3
"""Numerical and performance benchmark for FLUX.2 Metal fusions."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def _measure(mx, function, iterations: int) -> float:
    for _ in range(2):
        mx.eval(*function())
    started = time.perf_counter()
    for _ in range(iterations):
        mx.eval(*function())
    return (time.perf_counter() - started) / iterations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=4352)
    parser.add_argument("--hidden", type=int, default=4096)
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "packages/ai2apps-model-flux2-klein-mlx/src"))

    import mlx.core as mx

    from flux2_fused_ops import layer_norm_adaln, residual_layer_norm_adaln

    mx.random.seed(17)
    shape = (1, args.rows, args.hidden)
    x = mx.random.normal(shape).astype(mx.bfloat16)
    branch = mx.random.normal(shape).astype(mx.bfloat16)
    shift = (0.05 * mx.random.normal((1, 1, args.hidden))).astype(mx.bfloat16)
    scale = (0.05 * mx.random.normal((1, 1, args.hidden))).astype(mx.bfloat16)
    gate = (0.2 * mx.random.normal((1, 1, args.hidden))).astype(mx.bfloat16)
    eps = 1e-6

    def reference_norm():
        normalized = mx.fast.layer_norm(x, None, None, eps)
        return (normalized * (1.0 + scale) + shift,)

    def fused_norm():
        return (layer_norm_adaln(x, shift, scale, eps),)

    def reference_residual():
        residual = x + gate * branch
        normalized = mx.fast.layer_norm(residual, None, None, eps)
        return residual, normalized * (1.0 + scale) + shift

    def fused_residual():
        return residual_layer_norm_adaln(x, branch, gate, shift, scale, eps)

    ref_norm = reference_norm()[0]
    got_norm = fused_norm()[0]
    ref_residual, ref_out = reference_residual()
    got_residual, got_out = fused_residual()
    mx.eval(ref_norm, got_norm, ref_residual, ref_out, got_residual, got_out)
    report = {
        "shape": list(shape),
        "dtype": "bfloat16",
        "norm_max_abs_error": float(mx.max(mx.abs(ref_norm - got_norm)).item()),
        "norm_mean_abs_error": float(mx.mean(mx.abs(ref_norm - got_norm)).item()),
        "residual_max_abs_error": float(mx.max(mx.abs(ref_residual - got_residual)).item()),
        "residual_mean_abs_error": float(mx.mean(mx.abs(ref_residual - got_residual)).item()),
        "residual_norm_max_abs_error": float(mx.max(mx.abs(ref_out - got_out)).item()),
        "residual_norm_mean_abs_error": float(mx.mean(mx.abs(ref_out - got_out)).item()),
    }
    ref_norm_s = _measure(mx, reference_norm, args.iterations)
    fused_norm_s = _measure(mx, fused_norm, args.iterations)
    ref_residual_s = _measure(mx, reference_residual, args.iterations)
    fused_residual_s = _measure(mx, fused_residual, args.iterations)
    report.update({
        "reference_norm_seconds": ref_norm_s,
        "fused_norm_seconds": fused_norm_s,
        "norm_speedup": ref_norm_s / fused_norm_s,
        "reference_residual_seconds": ref_residual_s,
        "fused_residual_seconds": fused_residual_s,
        "residual_speedup": ref_residual_s / fused_residual_s,
    })
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
