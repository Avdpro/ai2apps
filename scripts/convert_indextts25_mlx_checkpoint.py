#!/usr/bin/env python3
"""Convert the pinned IndexTTS 2.5 release into a Torch-free MLX checkpoint.

Conversion is an offline release-engineering step.  The resulting directory
contains only safetensors, NumPy tables, tokenizer/configuration data,
licenses, and a provenance manifest; Torch is never needed by the Runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


INDEXTTS_REPO = "IndexTeam/IndexTTS-2.5"
INDEXTTS_REVISION = "d0aa86e75bb6f3437f3831e95056fa72842d89ef"
WINDEXTTS_REPO = "https://github.com/baicai-1145/WIndexTTS"
WINDEXTTS_REVISION = "eafb98c1b2ba46f6a608f29d8831208b89047681"
AUXILIARY_SOURCES = {
    "facebook/w2v-bert-2.0": "da985ba0987f70aaeb84a80f2851cfac8c697a7b",
    "funasr/campplus": "e4b6ede7ce16997aff4ae69fbca1f0175e2afede",
    "nvidia/bigvgan_v2_22khz_80band_256x": (
        "633ff708ed5b74903e86ff1298cf4a98e921c513"
    ),
}

SOURCE_FILES = (
    "config.yaml",
    "gpt.pth",
    "codec.pth",
    "s2mel.pth",
    "feat1.pt",
    "feat2.pt",
    "wav2vec2bert_stats.pt",
    "multilingual_zh_ja_yue_char_del.tiktoken",
    "qwen0.6bemo4-merge/tokenizer.json",
    "w2v-bert-2.0/model.safetensors",
    "bigvgan/config.json",
    "bigvgan/bigvgan_generator.pt",
    "campplus_cn_common.bin",
    "LICENSE",
)

RUNTIME_FILES = (
    "config.yaml",
    "gpt.safetensors",
    "codec.safetensors",
    "s2mel.safetensors",
    "bigvgan.safetensors",
    "w2v_bert.safetensors",
    "campplus.safetensors",
    "feat.npz",
    "stats.npz",
    "bigvgan_config.json",
    "multilingual_zh_ja_yue_char_del.tiktoken",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def _validate_inputs(source: Path, windextts: Path, output: Path) -> None:
    missing = [name for name in SOURCE_FILES if not (source / name).is_file()]
    if missing:
        raise SystemExit("IndexTTS source is incomplete: " + ", ".join(missing))
    revision = _git_revision(windextts)
    if revision != WINDEXTTS_REVISION:
        raise SystemExit(
            f"WIndexTTS revision mismatch: expected {WINDEXTTS_REVISION}, got {revision}"
        )
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Output directory must be empty: {output}")


def _fp16_converter(tensor):
    import mlx.core as mx
    import numpy as np

    array = tensor.detach().contiguous().cpu().numpy()
    if array.dtype == np.int64:
        array = array.astype(np.int32)
    elif array.dtype == np.float64:
        array = array.astype(np.float32)
    elif np.issubdtype(array.dtype, np.floating) and array.dtype != np.float16:
        array = array.astype(np.float16)
    return mx.array(array)


def convert(source: Path, windextts: Path, output: Path) -> None:
    _validate_inputs(source, windextts, output)
    output.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(windextts))
    from windextts_mlx import weights

    # The reviewed converter intentionally expands inference tensors to FP32.
    # Our released checkpoint stores floating tensors as FP16; the Runtime can
    # still promote selected frontends to FP32 when numerical alignment needs it.
    weights._torch_to_mlx = _fp16_converter

    with tempfile.TemporaryDirectory(prefix="ai2apps-indextts25-convert-") as tmp:
        staging = Path(tmp)
        for child in source.iterdir():
            if child.name == "hf_cache":
                continue
            (staging / child.name).symlink_to(child)
        compatibility = staging / "hf_cache" / "bigvgan"
        compatibility.mkdir(parents=True)
        (compatibility / "config.json").symlink_to(
            source / "bigvgan" / "config.json"
        )
        weights.convert_all(
            staging,
            output,
            models=("gpt", "codec", "s2mel", "bigvgan", "campplus", "w2v_bert"),
        )

    # P0 uses the model's multilingual tiktoken vocabulary and structured
    # numeric emotion vectors. The Qwen emotion model and its tokenizer are a
    # separate P1 capability, so neither belongs in this checkpoint.
    (output / "qwen_tokenizer.json").unlink(missing_ok=True)

    shutil.copy2(source / "config.yaml", output / "config.yaml")
    shutil.copy2(source / "LICENSE", output / "LICENSE-IndexTTS-2.5.txt")
    shutil.copy2(windextts / "LICENSE", output / "LICENSE-WIndexTTS.txt")

    missing = [name for name in RUNTIME_FILES if not (output / name).is_file()]
    if missing:
        raise SystemExit("Converted checkpoint is incomplete: " + ", ".join(missing))

    files = {
        path.relative_to(output).as_posix(): {
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "schema": "ai2apps.indextts25-mlx-checkpoint/v1",
        "format": "fp16",
        "runtime": "pure-mlx",
        "sources": {
            INDEXTTS_REPO: INDEXTTS_REVISION,
            WINDEXTTS_REPO: WINDEXTTS_REVISION,
            **AUXILIARY_SOURCES,
        },
        "excluded": [
            "qwen0.6bemo4-merge/model.safetensors",
            "qwen0.6bemo4-merge/tokenizer.json",
            "Torch checkpoints and optimizer state",
        ],
        "features": {
            "reference_voice": True,
            "numeric_emotion_vector": True,
            "duration_factor": True,
            "text_emotion_model": False,
        },
        "files": files,
    }
    (output / "conversion-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--windextts-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    convert(args.source.resolve(), args.windextts_source.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
