"""Convert and execute a final user-style RVC checkpoint plus retrieval index."""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf

from .checkpoint import (
    export_faiss_index,
    export_hubert_checkpoint,
    export_legacy_checkpoint,
    export_rmvpe_checkpoint,
)
from .contentvec import ContentVec
from .pipeline import ConversionOptions, RVCInferencePipeline
from .rmvpe import RMVPE
from .synthesizer import RVCSynthesizer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("index", type=Path)
    parser.add_argument("hubert_directory", type=Path)
    parser.add_argument("rmvpe_checkpoint", type=Path)
    parser.add_argument("source_audio", type=Path)
    parser.add_argument("output_audio", type=Path)
    args = parser.parse_args()
    source, sample_rate = sf.read(args.source_audio, dtype="float32")
    if sample_rate != 16_000 or source.ndim != 1:
        raise SystemExit("source fixture must be 16 kHz mono")

    with tempfile.TemporaryDirectory(prefix="mlx-rvc-target-") as temporary:
        root = Path(temporary)
        model_root = root / "model"
        hubert_root = root / "hubert"
        rmvpe_root = root / "rmvpe"
        export_legacy_checkpoint(args.checkpoint, model_root / "model.safetensors")
        index_manifest = export_faiss_index(
            args.index, model_root / "index.safetensors"
        )
        export_hubert_checkpoint(
            args.hubert_directory / "pytorch_model.bin",
            args.hubert_directory / "config.json",
            hubert_root / "model.safetensors",
        )
        export_rmvpe_checkpoint(args.rmvpe_checkpoint, rmvpe_root / "model.safetensors")
        state = {
            name: np.asarray(value)
            for name, value in mx.load(
                str(model_root / "model.safetensors"), format="safetensors"
            ).items()
        }
        vectors = mx.load(str(model_root / "index.safetensors"), format="safetensors")[
            "vectors"
        ]
        pipeline = RVCInferencePipeline(
            ContentVec.from_directory(hubert_root),
            RMVPE.from_directory(rmvpe_root),
            RVCSynthesizer(state),
        )
        mx.clear_cache()
        mx.reset_peak_memory()
        started = time.perf_counter()
        output = pipeline.convert_long_16khz(
            source,
            options=ConversionOptions(retrieval_rate=0.75, seed=23),
            retrieval_vectors=vectors,
        )
        elapsed = time.perf_counter() - started
        args.output_audio.parent.mkdir(parents=True, exist_ok=True)
        sf.write(args.output_audio, output, 48_000)
        print(f"retrieval_vectors={index_manifest['vectors']['count']}")
        print(f"retrieval_dimensions={index_manifest['vectors']['dimensions']}")
        print(f"input_duration={source.size / 16000:.6f}")
        print(f"output_duration={output.size / 48000:.6f}")
        print(f"rtf={elapsed / (source.size / 16000):.6f}")
        print(f"mlx_peak_bytes={mx.get_peak_memory()}")
        print(f"output={args.output_audio}")
        if output.size == 0 or not np.isfinite(output).all():
            raise SystemExit("target checkpoint pipeline gate failed")


if __name__ == "__main__":
    main()
