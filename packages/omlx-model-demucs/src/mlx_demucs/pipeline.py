"""Two-stem separation pipeline with an exact residual background stem."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio import AudioBuffer, read_audio
from .backends import TwoStemBackend
from .capabilities import htdemucs_audio_capabilities, separation_profile
from .schema import SeparationResult, Stem


@dataclass(frozen=True)
class SeparationConfig:
    float32_wav: bool = True
    profile: str = "dialogue_background"


def _adapt_audio(audio: AudioBuffer, backend: TwoStemBackend) -> AudioBuffer:
    if audio.channels > 2:
        raise ValueError("The two-stem MVP accepts mono or stereo input only")
    return audio.resample(backend.sample_rate).with_channels(backend.channels)


def _validate_vocals(vocals: AudioBuffer, mixture: AudioBuffer) -> None:
    if vocals.sample_rate != mixture.sample_rate:
        raise ValueError("Backend changed the sample rate")
    if vocals.samples.shape != mixture.samples.shape:
        raise ValueError(
            f"Backend changed the audio shape: {vocals.samples.shape} != {mixture.samples.shape}"
        )
    if not np.isfinite(vocals.samples).all():
        raise ValueError("Backend returned non-finite samples")


def _stem(kind: str, path: Path, audio: AudioBuffer) -> Stem:
    return Stem(
        type=kind,
        # Result manifests are exported outside the Worker request directory.
        # Keep paths container-relative instead of leaking a temporary host path.
        path=path.name,
        channels=audio.channels,
        sample_rate=audio.sample_rate,
        frames=audio.frames,
        duration=audio.duration,
        rms=audio.rms,
    )


def separate_audio(
    audio: AudioBuffer,
    output_dir: str | Path,
    *,
    backend: TwoStemBackend,
    config: SeparationConfig | None = None,
) -> SeparationResult:
    config = config or SeparationConfig()
    capabilities = htdemucs_audio_capabilities()
    profile = separation_profile(capabilities, config.profile)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    mixture = _adapt_audio(audio, backend)
    if profile["id"] == "music_4stem":
        outputs = backend.extract_sources(mixture)
        required = tuple(profile["stems"])
        if set(outputs) != set(required):
            raise ValueError(f"Backend sources {sorted(outputs)} do not match {required}")
    else:
        vocals = backend.extract_vocals(mixture)
        _validate_vocals(vocals, mixture)
        residual_name = (
            "instrumental" if profile["id"] == "vocals_instrumental" else "background"
        )
        primary_name = "vocals" if profile["id"] == "vocals_instrumental" else "dialogue"
        outputs = {
            primary_name: vocals,
            residual_name: AudioBuffer(
                mixture.samples - vocals.samples, mixture.sample_rate
            ),
        }
    for value in outputs.values():
        _validate_vocals(value, mixture)

    reconstructed = np.sum(
        [value.samples for value in outputs.values()], axis=0, dtype=np.float32
    )
    reconstruction_max_error = float(np.max(np.abs(reconstructed - mixture.samples), initial=0))

    stem_results = []
    for kind, value in outputs.items():
        path = destination / f"{kind}.wav"
        value.write_wav(path, float32=config.float32_wav)
        stem_results.append(_stem(kind, path, value))

    mixture_energy = float(np.mean(np.square(mixture.samples, dtype=np.float64)))
    primary = outputs[profile["stems"][0]]
    primary_energy = float(np.mean(np.square(primary.samples, dtype=np.float64)))
    result = SeparationResult(
        duration=mixture.duration,
        sample_rate=mixture.sample_rate,
        channels=mixture.channels,
        stems=stem_results,
        model={"backend": backend.name, "name": backend.model_name},
        metrics={
            "reconstruction_max_error": reconstruction_max_error,
            "primary_stem_energy_ratio": primary_energy / max(mixture_energy, 1e-12),
        },
        features={
            "source_separation": {
                "feature": "source_separation",
                "status": profile["mode"],
                "requested": {"profile": config.profile},
                "effective": {
                    "profile": profile["id"],
                    "stems": profile["stems"],
                    "derivation": profile.get(
                        "derivation", {stem: stem for stem in profile["stems"]}
                    ),
                },
                "provider": backend.name,
                "native_stems": capabilities["processing"]["separation"][
                    "native_stems"
                ],
                "preserves_timeline": capabilities["processing"]["separation"][
                    "preserves_timeline"
                ],
            }
        },
    )
    (destination / "separation.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def separate_file(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    backend: TwoStemBackend,
    config: SeparationConfig | None = None,
) -> SeparationResult:
    return separate_audio(read_audio(input_path), output_dir, backend=backend, config=config)
