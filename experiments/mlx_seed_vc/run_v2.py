"""Run the Torch-free MLX Seed-VC v2 pipeline on two local audio files."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .pipeline_v2 import SeedVCV2


def _load(path: Path) -> np.ndarray:
    values, rate = sf.read(path, dtype="float32", always_2d=False)
    if values.ndim == 2:
        values = values.mean(axis=1)
    if rate != 22050:
        divisor = np.gcd(rate, 22050)
        values = resample_poly(values, 22050 // divisor, rate // divisor).astype(np.float32)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("timbre", "voice"), default="timbre")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--seconds", type=float)
    args = parser.parse_args()
    source, target = _load(args.source), _load(args.target)
    if args.seconds:
        source = source[: int(args.seconds * 22050)]
        target = target[: int(args.seconds * 22050)]
    started = time.perf_counter()
    model = SeedVCV2(args.model)
    loaded = time.perf_counter()
    mx.reset_peak_memory()
    output = model.convert(source, target, mode=args.mode, diffusion_steps=args.steps)
    elapsed = time.perf_counter() - loaded
    sf.write(args.output, output, 22050)
    print(f"output={args.output}")
    print(f"load_seconds={loaded - started:.3f}")
    print(f"inference_seconds={elapsed:.3f}")
    print(f"audio_seconds={len(output) / 22050:.3f}")
    print(f"rtf={elapsed / max(len(output) / 22050, 1e-9):.4f}")
    print(f"peak_memory_gb={mx.get_peak_memory() / 1e9:.3f}")


if __name__ == "__main__":
    main()
