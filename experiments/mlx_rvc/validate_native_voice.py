#!/usr/bin/env python3
"""Run a native MLX-trained RVC voice bundle through the shipping pipeline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf

from .contentvec import ContentVec
from .pipeline import ConversionOptions, RVCInferencePipeline
from .rmvpe import RMVPE
from .synthesizer import RVCSynthesizer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("voice", type=Path)
    parser.add_argument("contentvec", type=Path)
    parser.add_argument("rmvpe", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    audio, rate = sf.read(args.source, dtype="float32")
    if rate != 16_000 or audio.ndim != 1:
        raise SystemExit("source must be 16 kHz mono")
    state = {
        name: np.asarray(value)
        for name, value in mx.load(
            str(args.voice / "model.safetensors"), format="safetensors"
        ).items()
    }
    vectors = mx.load(str(args.voice / "index.safetensors"), format="safetensors")[
        "vectors"
    ]
    pipeline = RVCInferencePipeline(
        ContentVec.from_directory(args.contentvec),
        RMVPE.from_directory(args.rmvpe),
        RVCSynthesizer(state),
    )
    mx.clear_cache()
    mx.reset_peak_memory()
    started = time.perf_counter()
    output = pipeline.convert_long_16khz(
        audio,
        options=ConversionOptions(retrieval_rate=0.75, seed=23),
        retrieval_vectors=vectors,
    )
    elapsed = time.perf_counter() - started
    sf.write(args.output, output, 48_000, subtype="PCM_16")
    print(
        json.dumps(
            {
                "input_seconds": audio.size / 16_000,
                "output_seconds": output.size / 48_000,
                "rtf": elapsed / (audio.size / 16_000),
                "peak_memory_bytes": mx.get_peak_memory(),
                "retrieval_vectors": int(vectors.shape[0]),
                "finite": bool(np.isfinite(output).all()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
