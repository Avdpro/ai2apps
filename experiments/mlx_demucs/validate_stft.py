"""Run PyTorch-vs-MLX STFT parity on a Metal-capable process."""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from .mlx_stft import ispectro, spectro


def validate(*, n_fft: int = 4096, length: int = 44032) -> dict:
    import mlx.core as mx
    import torch

    generator = np.random.default_rng(20260905)
    values = generator.standard_normal((2, length), dtype=np.float32) * 0.05
    torch_values = torch.from_numpy(values)
    torch_window = torch.hann_window(n_fft)
    reference = torch.stft(
        torch_values,
        n_fft,
        hop_length=n_fft // 4,
        window=torch_window,
        normalized=True,
        center=True,
        return_complex=True,
        pad_mode="reflect",
    )
    started = time.perf_counter()
    actual = spectro(mx.array(values), n_fft=n_fft)
    reconstructed = ispectro(actual, length=length)
    mx.eval(actual, reconstructed)
    elapsed = time.perf_counter() - started
    actual_np = np.asarray(actual)
    reconstructed_np = np.asarray(reconstructed)
    reference_np = reference.numpy()
    return {
        "schema": "ai2apps.mlx-demucs-stft-parity/v1",
        "n_fft": n_fft,
        "length": length,
        "spectrum_shape": list(actual_np.shape),
        "spectrum_max_abs_error": float(np.max(np.abs(actual_np - reference_np))),
        "round_trip_max_abs_error": float(np.max(np.abs(reconstructed_np - values))),
        "elapsed_seconds": elapsed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-fft", type=int, default=4096)
    parser.add_argument("--length", type=int, default=44032)
    args = parser.parse_args()
    print(json.dumps(validate(n_fft=args.n_fft, length=args.length), indent=2))


if __name__ == "__main__":
    main()
