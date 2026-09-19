#!/usr/bin/env python3
"""Compare the auditable graph baseline with a specialized native MLX port."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from .liveportrait import MLXLivePortrait


def _median_ms(function, runs: int) -> float:
    samples = []
    for _ in range(2):
        function()
    for _ in range(runs):
        started = time.perf_counter()
        function()
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples)


def _error(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    delta = np.abs(reference.astype(np.float32) - candidate.astype(np.float32))
    return {"max_abs": float(delta.max()), "mean_abs": float(delta.mean())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--native-weights", type=Path, required=True)
    parser.add_argument("--graph-models", type=Path, required=True)
    parser.add_argument("--dtype", choices=("fp32", "fp16", "bf16"), default="bf16")
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()

    sys.path.insert(0, str(args.native_root))
    from src.models import (  # noqa: PLC0415
        MlxAppearanceFeatureExtractorModel,
        MlxMotionExtractorModel,
        MlxWarpingSpadeModel,
    )

    weights = args.native_weights / "liveportrait_mlx"
    native_appearance = MlxAppearanceFeatureExtractorModel(
        dtype=args.dtype,
        model_path=str(weights / "appearance_feature_extractor.npz"),
    )
    native_motion = MlxMotionExtractorModel(
        dtype=args.dtype,
        model_path=str(weights / "motion_extractor.npz"),
    )
    native_warp = MlxWarpingSpadeModel(
        dtype=args.dtype,
        model_path=[
            str(weights / "warping_module.npz"),
            str(weights / "spade_generator.npz"),
        ],
    )
    baseline = MLXLivePortrait(args.graph_models)
    rng = np.random.default_rng(20260905)
    bgr = rng.integers(0, 256, size=(256, 256, 3), dtype=np.uint8)
    rgb = np.ascontiguousarray(bgr[..., ::-1])

    baseline_appearance = np.asarray(baseline.appearance(bgr), dtype=np.float32)
    native_appearance_value = native_appearance.predict(rgb)
    appearance_error = _error(baseline_appearance, native_appearance_value)

    baseline_motion = baseline.motion(bgr)
    native_motion_value = native_motion.predict(rgb)
    native_motion_names = ("pitch", "yaw", "roll", "t", "exp", "scale", "kp")
    motion_error = {
        name: _error(
            np.asarray(baseline_motion[name], dtype=np.float32).reshape(-1),
            np.asarray(value, dtype=np.float32).reshape(-1),
        )
        for name, value in zip(native_motion_names, native_motion_value, strict=True)
    }

    keypoint_source = rng.normal(size=(1, 21, 3)).astype(np.float32) * 0.05
    keypoint_driving = keypoint_source + (
        rng.normal(size=(1, 21, 3)).astype(np.float32) * 0.01
    )
    baseline_warp = baseline.warp_decode(
        baseline_appearance, keypoint_source, keypoint_driving
    )
    native_warp_value = native_warp.predict(
        baseline_appearance,
        keypoint_source,
        keypoint_driving,
        return_numpy=True,
        return_uint8=True,
    )
    warp_error = _error(baseline_warp[..., ::-1], native_warp_value)

    report = {
        "dtype": args.dtype,
        "errors": {
            "appearance": appearance_error,
            "motion": motion_error,
            "warping_spade_uint8": warp_error,
        },
        "median_ms": {
            "baseline_appearance": _median_ms(
                lambda: baseline.appearance(bgr), args.runs
            ),
            "native_appearance": _median_ms(
                lambda: native_appearance.predict(rgb), args.runs
            ),
            "baseline_motion": _median_ms(lambda: baseline.motion(bgr), args.runs),
            "native_motion": _median_ms(lambda: native_motion.predict(rgb), args.runs),
            "baseline_warping_spade": _median_ms(
                lambda: baseline.warp_decode(
                    baseline_appearance, keypoint_source, keypoint_driving
                ),
                args.runs,
            ),
            "native_warping_spade": _median_ms(
                lambda: native_warp.predict(
                    baseline_appearance,
                    keypoint_source,
                    keypoint_driving,
                    return_numpy=True,
                    return_uint8=True,
                ),
                args.runs,
            ),
        },
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
