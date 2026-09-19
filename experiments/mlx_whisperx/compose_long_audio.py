"""Compose a deterministic multi-minute WAV from a benchmark manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .audio import AudioBuffer, read_audio
from .benchmark import file_sha256, load_cases


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--manifest", required=True, type=Path)
    value.add_argument("--audio-root", required=True, type=Path)
    value.add_argument("--duration-seconds", type=float, default=600.0)
    value.add_argument("--silence-seconds", type=float, default=0.3)
    value.add_argument("--output", required=True, type=Path)
    return value


def compose(
    *,
    cases: list[dict],
    audio_root: Path,
    duration_seconds: float,
    silence_seconds: float,
) -> tuple[AudioBuffer, list[dict]]:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if silence_seconds < 0:
        raise ValueError("silence_seconds cannot be negative")
    sample_rate = 16000
    silence = np.zeros(round(silence_seconds * sample_rate), dtype=np.float32)
    chunks: list[np.ndarray] = []
    sequence: list[dict] = []
    sample_count = 0
    index = 0
    while sample_count / sample_rate < duration_seconds:
        case = cases[index % len(cases)]
        audio = read_audio(audio_root / str(case["audio"]), target_rate=sample_rate)
        start = sample_count / sample_rate
        chunks.append(audio.samples)
        sample_count += len(audio.samples)
        end = sample_count / sample_rate
        sequence.append(
            {
                "index": index,
                "id": str(case["id"]),
                "start": start,
                "end": end,
                "reference": str(case["reference"]),
            }
        )
        chunks.append(silence)
        sample_count += len(silence)
        index += 1
    return AudioBuffer(np.concatenate(chunks), sample_rate), sequence


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cases = load_cases(manifest, args.audio_root)
    audio, sequence = compose(
        cases=cases,
        audio_root=args.audio_root,
        duration_seconds=args.duration_seconds,
        silence_seconds=args.silence_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    audio.write_wav(args.output)
    sidecar = args.output.with_suffix(args.output.suffix + ".json")
    sidecar.write_text(
        json.dumps(
            {
                "schema": "ai2apps.mlx-whisperx-long-audio/v1",
                "source_manifest": str(args.manifest),
                "duration_seconds": audio.duration,
                "sample_rate": audio.sample_rate,
                "audio_sha256": file_sha256(args.output),
                "sequence": sequence,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
