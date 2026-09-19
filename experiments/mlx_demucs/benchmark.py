"""Deterministic speech-plus-accompaniment smoke benchmark."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import numpy as np

from .audio import AudioBuffer, read_audio
from .backends import MlxDemucsBackend, TorchDemucsBackend
from .pipeline import separate_audio


def compose_fixture(clean: AudioBuffer, *, sample_rate: int = 44100) -> tuple[AudioBuffer, AudioBuffer, AudioBuffer]:
    speech = clean.resample(sample_rate).with_channels(2)
    times = np.arange(speech.frames, dtype=np.float32) / sample_rate
    # A deterministic, amplitude-modulated chord is intentionally simple. It
    # is a smoke fixture for regressions, not a substitute for licensed movie
    # and music evaluation data.
    envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 1.7 * times) ** 2
    chord = (
        np.sin(2 * np.pi * 110 * times)
        + 0.65 * np.sin(2 * np.pi * 220 * times + 0.3)
        + 0.35 * np.sin(2 * np.pi * 440 * times + 0.8)
    )
    chord = chord * envelope
    chord_rms = float(np.sqrt(np.mean(np.square(chord, dtype=np.float64))))
    target_rms = max(speech.rms * 0.7, 0.01)
    chord = chord * (target_rms / max(chord_rms, 1e-12))
    background = AudioBuffer(np.stack([chord, np.roll(chord, 17)]).astype(np.float32), sample_rate)
    mixture = AudioBuffer(speech.samples + background.samples, sample_rate)
    return mixture, speech, background


def _si_sdr(reference: np.ndarray, estimate: np.ndarray) -> float:
    reference64 = np.asarray(reference, dtype=np.float64).reshape(-1)
    estimate64 = np.asarray(estimate, dtype=np.float64).reshape(-1)
    reference_energy = float(np.dot(reference64, reference64))
    if reference_energy <= 1e-12:
        return float("nan")
    scale = float(np.dot(estimate64, reference64)) / reference_energy
    target = scale * reference64
    noise = estimate64 - target
    return 10 * math.log10(
        max(float(np.dot(target, target)), 1e-12) / max(float(np.dot(noise, noise)), 1e-12)
    )


def run_benchmark(
    clean_path: str | Path,
    output_dir: str | Path,
    *,
    backend_name: str = "torch",
    device: str = "cpu",
    weights: str | Path | None = None,
) -> dict:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    mixture, clean, background = compose_fixture(read_audio(clean_path))
    mixture.write_wav(destination / "mixture.wav")
    clean.write_wav(destination / "reference-dialogue.wav")
    background.write_wav(destination / "reference-background.wav")

    if backend_name == "mlx":
        if weights is None:
            raise ValueError("weights are required for the MLX benchmark")
        backend = MlxDemucsBackend(weights)
    elif backend_name == "torch":
        backend = TorchDemucsBackend(device=device)
    else:
        raise ValueError(f"Unsupported backend: {backend_name}")
    started = time.perf_counter()
    result = separate_audio(mixture, destination / "separated", backend=backend)
    elapsed = time.perf_counter() - started
    estimated_dialogue = read_audio(destination / "separated" / "dialogue.wav")
    input_si_sdr = _si_sdr(clean.samples, mixture.samples)
    output_si_sdr = _si_sdr(clean.samples, estimated_dialogue.samples)
    report = {
        "schema": "ai2apps.audio-separation-benchmark/v1",
        "fixture": "deterministic_speech_plus_synthetic_chord",
        "backend": backend.name,
        "duration": mixture.duration,
        "elapsed_seconds": elapsed,
        "rtf": elapsed / max(mixture.duration, 1e-12),
        "input_dialogue_si_sdr_db": input_si_sdr,
        "output_dialogue_si_sdr_db": output_si_sdr,
        "dialogue_si_sdr_improvement_db": output_si_sdr - input_si_sdr,
        "reconstruction_max_error": result.metrics["reconstruction_max_error"],
    }
    (destination / "benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("clean_speech")
    parser.add_argument("output_dir")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--backend", choices=("torch", "mlx"), default="torch")
    parser.add_argument("--weights")
    parser.add_argument("--torch-home")
    args = parser.parse_args()
    if args.torch_home:
        os.environ["TORCH_HOME"] = args.torch_home
    print(
        json.dumps(
            run_benchmark(
                args.clean_speech,
                args.output_dir,
                backend_name=args.backend,
                device=args.device,
                weights=args.weights,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
