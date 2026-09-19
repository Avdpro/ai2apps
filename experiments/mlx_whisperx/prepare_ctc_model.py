"""Prepare a public Hugging Face Wav2Vec2ForCTC checkpoint for mlx-audio."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

SUPPORTING_FILES = (
    "config.json",
    "preprocessor_config.json",
    "feature_extractor_config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "vocab.json",
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--source", required=True)
    value.add_argument("--revision", required=True)
    value.add_argument("--source-dir", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    value.add_argument("--language", action="append", dest="languages")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"Refusing to replace existing output: {args.output}")
    from huggingface_hub import snapshot_download

    source = Path(
        snapshot_download(
            repo_id=args.source,
            revision=args.revision,
            local_dir=args.source_dir,
            allow_patterns=["model.safetensors", *SUPPORTING_FILES],
        )
    )
    args.output.mkdir(parents=True)
    for name in ("model.safetensors", *SUPPORTING_FILES):
        candidate = source / name
        if candidate.is_file():
            shutil.copy2(candidate, args.output / name)
    config_path = args.output / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    original_model_type = config.get("model_type")
    config["model_type"] = "mms"
    config["ai2apps_alignment_languages"] = sorted(set(args.languages or ["en"]))
    config["ai2apps_conversion"] = {
        "kind": "mlx-audio-wav2vec2-ctc-adapter/v1",
        "source": args.source,
        "revision": args.revision,
        "original_model_type": original_model_type,
    }
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
