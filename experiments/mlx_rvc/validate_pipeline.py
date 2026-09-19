"""Run the complete native MLX RVC path on deterministic source audio."""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .checkpoint import export_hubert_checkpoint, export_rmvpe_checkpoint
from .contentvec import ContentVec
from .pipeline import ConversionOptions, RVCInferencePipeline
from .rmvpe import RMVPE
from .synthesizer import RVCSynthesizer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("generator_checkpoint", type=Path)
    parser.add_argument("hubert_directory", type=Path)
    parser.add_argument("rmvpe_checkpoint", type=Path)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--chunked", action="store_true")
    args = parser.parse_args()
    state = torch.load(
        args.generator_checkpoint, map_location="cpu", weights_only=True
    )["model"]
    numpy_state = {name: value.float().numpy() for name, value in state.items()}
    sample_count = int(args.seconds * 16_000)
    timeline = np.arange(sample_count, dtype=np.float32) / 16_000
    audio = (0.1 * np.sin(2 * np.pi * 180 * timeline)).astype(np.float32)

    with tempfile.TemporaryDirectory(prefix="mlx-rvc-e2e-") as temporary:
        root = Path(temporary)
        hubert = root / "hubert"
        rmvpe = root / "rmvpe"
        export_hubert_checkpoint(
            args.hubert_directory / "pytorch_model.bin",
            args.hubert_directory / "config.json",
            hubert / "model.safetensors",
        )
        export_rmvpe_checkpoint(args.rmvpe_checkpoint, rmvpe / "model.safetensors")
        pipeline = RVCInferencePipeline(
            ContentVec.from_directory(hubert),
            RMVPE.from_directory(rmvpe),
            RVCSynthesizer(numpy_state),
        )
        mx.clear_cache()
        mx.reset_peak_memory()
        started = time.perf_counter()
        convert = (
            pipeline.convert_long_16khz if args.chunked else pipeline.convert_16khz
        )
        output = convert(audio, options=ConversionOptions(seed=17))
        elapsed = time.perf_counter() - started
        duration = output.size / 48_000
        print(f"input_samples={audio.size}")
        print(f"output_samples={output.size}")
        print(f"output_duration={duration:.6f}")
        print(f"elapsed={elapsed:.6f}")
        print(f"rtf={elapsed / args.seconds:.6f}")
        print(f"mlx_peak_bytes={mx.get_peak_memory()}")
        print(f"finite={bool(np.isfinite(output).all())}")
        print(f"peak={float(np.max(np.abs(output))):.8g}")
        if not np.isfinite(output).all() or output.size == 0:
            raise SystemExit("MLX-RVC pipeline gate failed")


if __name__ == "__main__":
    main()
