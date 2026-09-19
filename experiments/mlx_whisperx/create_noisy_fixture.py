"""Create deterministic white-noise benchmark fixtures at an exact SNR."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .audio import AudioBuffer, read_audio
from .benchmark import file_sha256, load_cases


def add_white_noise(
    audio: AudioBuffer, *, snr_db: float, seed: int
) -> AudioBuffer:
    samples = audio.samples.astype(np.float64)
    signal_rms = float(np.sqrt(np.mean(np.square(samples))))
    if not signal_rms:
        return audio
    generator = np.random.default_rng(seed)
    noise = generator.standard_normal(len(samples))
    noise /= float(np.sqrt(np.mean(np.square(noise))))
    noise_rms = signal_rms / (10.0 ** (snr_db / 20.0))
    mixed = samples + noise * noise_rms
    peak = float(np.max(np.abs(mixed)))
    if peak > 0.999:
        mixed *= 0.999 / peak
    return AudioBuffer(mixed.astype(np.float32), audio.sample_rate)


def case_seed(seed: int, identifier: str) -> int:
    digest = hashlib.sha256(f"{seed}:{identifier}".encode()).digest()
    return int.from_bytes(digest[:8], "little")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--manifest", required=True, type=Path)
    value.add_argument("--audio-root", required=True, type=Path)
    value.add_argument("--output-root", required=True, type=Path)
    value.add_argument("--output-manifest", required=True, type=Path)
    value.add_argument("--snr-db", required=True, type=float)
    value.add_argument("--seed", type=int, default=20260904)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cases = load_cases(manifest, args.audio_root)
    rendered_cases = []
    for case in cases:
        identifier = str(case["id"])
        source = (args.audio_root / str(case["audio"])).resolve(strict=True)
        relative = Path(str(case["audio"]))
        destination = args.output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        noisy = add_white_noise(
            read_audio(source),
            snr_db=args.snr_db,
            seed=case_seed(args.seed, identifier),
        )
        noisy.write_wav(destination)
        rendered_cases.append(
            {
                **case,
                "audio_sha256": file_sha256(destination),
            }
        )
    output = {
        **manifest,
        "dataset": f"{manifest.get('dataset')}/deterministic-white-noise",
        "revision": (
            f"{manifest.get('revision')}+white-noise-snr-{args.snr_db:g}"
            f"-seed-{args.seed}"
        ),
        "noise": {
            "kind": "white",
            "snr_db": args.snr_db,
            "seed": args.seed,
        },
        "cases": rendered_cases,
    }
    args.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output_manifest.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
