#!/usr/bin/env python3
"""Generate a reproducible synthetic RVC training corpus with Qwen3-TTS."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
import wave
from pathlib import Path

import mlx.core as mx

from omlx.engine.tts import TTSEngine


def _records(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) != {"id", "language", "text"}:
            raise ValueError(f"invalid corpus row {line_number}")
        if row["id"] in seen or row["language"] not in {"zh", "en"}:
            raise ValueError(f"invalid corpus identity at row {line_number}")
        seen.add(row["id"])
        rows.append(row)
    if not rows:
        raise ValueError("corpus is empty")
    return rows


def _inspect_wav(path: Path) -> tuple[int, int, float]:
    with wave.open(str(path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            raise ValueError(f"{path.name} is not mono PCM16")
        rate = audio.getframerate()
        frames = audio.getnframes()
    return rate, frames, frames / rate


async def generate(args: argparse.Namespace) -> dict[str, object]:
    rows = _records(args.corpus)
    audio_root = args.output / "audio"
    audio_root.mkdir(parents=True, exist_ok=True)
    engine = TTSEngine(str(args.model))
    started = time.monotonic()
    manifest: list[dict[str, object]] = []
    await engine.start()
    try:
        for index, row in enumerate(rows):
            destination = audio_root / f"{row['id']}.wav"
            if not destination.is_file() or args.overwrite:
                mx.random.seed(args.seed + index)
                content = await engine.synthesize(
                    row["text"],
                    voice=args.voice,
                    language=row["language"],
                    instructions=args.instructions,
                    temperature=args.temperature,
                    top_k=args.top_k,
                    top_p=args.top_p,
                )
                temporary = destination.with_suffix(".wav.tmp")
                temporary.write_bytes(content)
                temporary.replace(destination)
            rate, frames, duration = _inspect_wav(destination)
            if not args.minimum_seconds <= duration <= args.maximum_seconds:
                raise ValueError(
                    f"{destination.name} duration {duration:.3f}s is outside "
                    f"[{args.minimum_seconds}, {args.maximum_seconds}]"
                )
            manifest.append(
                {
                    **row,
                    "path": destination.relative_to(args.output).as_posix(),
                    "sample_rate": rate,
                    "frames": frames,
                    "duration_seconds": round(duration, 6),
                    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    "generator": {
                        "model": str(args.model),
                        "voice": args.voice,
                        "seed": args.seed + index,
                    },
                }
            )
            print(
                f"[{index + 1:03d}/{len(rows):03d}] {row['id']} {duration:.2f}s",
                flush=True,
            )
    finally:
        await engine.stop()

    manifest_path = args.output / "manifest.json"
    payload = {
        "schema": "ai2apps.synthetic-voice-dataset/v1",
        "purpose": "local MLX-RVC training and validation",
        "synthetic": True,
        "sourceModel": str(args.model),
        "sourceVoice": args.voice,
        "instructions": args.instructions,
        "utterances": manifest,
        "summary": {
            "count": len(manifest),
            "languages": {
                language: sum(row["language"] == language for row in manifest)
                for language in ("zh", "en")
            },
            "duration_seconds": round(
                sum(float(row["duration_seconds"]) for row in manifest), 6
            ),
            "elapsed_seconds": round(time.monotonic() - started, 6),
        },
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload["summary"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(__file__).with_name("qwen_serena_corpus.jsonl"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice", default="serena")
    parser.add_argument(
        "--instructions",
        default="Speak in a calm, neutral, clear studio voice with consistent volume and natural pacing.",
    )
    parser.add_argument("--seed", type=int, default=20260905)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--top-p", type=float, default=0.8)
    parser.add_argument("--minimum-seconds", type=float, default=2.0)
    parser.add_argument("--maximum-seconds", type=float, default=25.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    args.model = args.model.expanduser().resolve(strict=True)
    args.corpus = args.corpus.expanduser().resolve(strict=True)
    args.output = args.output.expanduser().resolve()
    print(json.dumps(asyncio.run(generate(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
