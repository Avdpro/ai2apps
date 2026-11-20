"""Backends for the two-stem experiment.

The official PyTorch implementation is a quality oracle only.  It deliberately
stays outside the shipped Runtime so the production path can be replaced by an
MLX implementation without changing the public pipeline contract.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from .audio import AudioBuffer


class TwoStemBackend(Protocol):
    name: str
    model_name: str
    sample_rate: int
    channels: int

    def extract_vocals(self, audio: AudioBuffer) -> AudioBuffer: ...

    def extract_sources(self, audio: AudioBuffer) -> dict[str, AudioBuffer]: ...


@dataclass
class TorchDemucsBackend:
    """Official htdemucs reference backend; never a Runtime dependency."""

    model_name: str = "htdemucs"
    device: str = "cpu"
    shifts: int = 0
    overlap: float = 0.25
    segment: float | None = None
    name: str = "torch_demucs_reference"

    def __post_init__(self) -> None:
        if not 0 <= self.overlap < 1:
            raise ValueError("overlap must be in [0, 1)")
        self._model = None
        self._torch = None

    def _load(self):
        if self._model is not None:
            return self._model
        if importlib.util.find_spec("demucs") is None:
            raise RuntimeError("Demucs is not installed in the experiment environment")
        import torch

        # Demucs inference below does not call torchaudio.  openunmix imports it
        # eagerly from an unrelated utility module, so a minimal module avoids
        # making the reference experiment depend on a version-coupled wheel.
        if importlib.util.find_spec("torchaudio") is None:
            sys.modules.setdefault("torchaudio", types.ModuleType("torchaudio"))
        from demucs.pretrained import get_model

        model = get_model(self.model_name)
        model.to(self.device)
        model.eval()
        self._model = model
        self._torch = torch
        return model

    @property
    def sample_rate(self) -> int:
        model = self._load()
        return int(model.samplerate)

    @property
    def channels(self) -> int:
        model = self._load()
        return int(model.audio_channels)

    def extract_sources(self, audio: AudioBuffer) -> dict[str, AudioBuffer]:
        model = self._load()
        torch = self._torch
        assert torch is not None
        if audio.sample_rate != self.sample_rate or audio.channels != self.channels:
            raise ValueError("Audio must be adapted to the backend before inference")
        if not audio.frames:
            return audio

        from demucs.apply import apply_model

        mix = torch.from_numpy(np.asarray(audio.samples, dtype=np.float32)).to(self.device)
        reference = mix.mean(dim=0)
        mean = reference.mean()
        std = reference.std().clamp_min(1e-8)
        normalized = (mix - mean) / std
        with torch.inference_mode():
            estimates = apply_model(
                model,
                normalized[None],
                shifts=self.shifts,
                split=True,
                overlap=self.overlap,
                segment=self.segment,
                device=self.device,
                progress=False,
            )[0]
        sources = list(model.sources)
        try:
            vocals_index = sources.index("vocals")
        except ValueError as error:
            raise RuntimeError(f"Model has no vocals source: {sources}") from error
        del vocals_index
        values = (estimates * std + mean).detach().to("cpu").numpy()
        return {
            source: AudioBuffer(
                values[index, :, : audio.frames].astype(np.float32, copy=False),
                audio.sample_rate,
            )
            for index, source in enumerate(sources)
        }

    def extract_vocals(self, audio: AudioBuffer) -> AudioBuffer:
        return self.extract_sources(audio)["vocals"]


def _triangle_weight(length: int, power: float = 1.0) -> np.ndarray:
    if length <= 0:
        raise ValueError("weight length must be positive")
    if power < 1:
        raise ValueError("transition power must be at least one")
    rising = np.arange(1, length // 2 + 1, dtype=np.float32)
    falling = np.arange(length - length // 2, 0, -1, dtype=np.float32)
    weight = np.concatenate([rising, falling])
    return np.power(weight / weight.max(), power).astype(np.float32, copy=False)


def _centered_chunk(values: np.ndarray, offset: int, target_length: int):
    """Return Demucs-compatible centered context and its retained center slice."""
    available = min(values.shape[-1] - offset, target_length)
    delta = target_length - available
    start = offset - delta // 2
    end = start + target_length
    correct_start = max(0, start)
    correct_end = min(values.shape[-1], end)
    left = correct_start - start
    right = end - correct_end
    padded = np.pad(values[..., correct_start:correct_end], ((0, 0), (left, right)))
    retained = slice(delta // 2, delta // 2 + available)
    return padded, retained, available


@dataclass
class MlxDemucsBackend:
    """MLX-native two-stem backend backed by a converted raw NPZ checkpoint."""

    weights_path: str | Path
    overlap: float = 0.25
    transition_power: float = 1.0
    model_name: str = "htdemucs"
    name: str = "mlx_demucs"
    sample_rate: int = 44_100
    channels: int = 2

    def __post_init__(self) -> None:
        if not 0 <= self.overlap < 1:
            raise ValueError("overlap must be in [0, 1)")
        if self.transition_power < 1:
            raise ValueError("transition_power must be at least one")
        self._model = None

    def _load(self):
        if self._model is None:
            from .mlx_model import MlxHTDemucs, load_checkpoint

            self._model = MlxHTDemucs(load_checkpoint(self.weights_path))
        return self._model

    def extract_sources(self, audio: AudioBuffer) -> dict[str, AudioBuffer]:
        if audio.sample_rate != self.sample_rate or audio.channels != self.channels:
            raise ValueError("Audio must be adapted to the backend before inference")
        if not audio.frames:
            return audio
        import mlx.core as mx

        model = self._load()
        mixture = np.asarray(audio.samples, dtype=np.float32)
        reference = mixture.mean(axis=0)
        mean = float(reference.mean())
        standard_deviation = float(reference.std(ddof=1)) if reference.size > 1 else 0.0
        if not np.isfinite(standard_deviation):
            standard_deviation = 0.0
        standard_deviation = max(standard_deviation, 1e-8)
        normalized = (mixture - mean) / standard_deviation

        segment_length = model.segment_samples
        stride = int((1 - self.overlap) * segment_length)
        if stride <= 0:
            raise ValueError("overlap leaves no forward progress")
        weight = _triangle_weight(segment_length, self.transition_power)
        output = np.zeros(
            (len(model.sources), *normalized.shape), dtype=np.float32
        )
        sum_weight = np.zeros(audio.frames, dtype=np.float32)
        for offset in range(0, audio.frames, stride):
            chunk, retained, available = _centered_chunk(
                normalized,
                offset,
                segment_length,
            )
            estimates = model(mx.array(chunk[None]), pad_to_segment=False)
            chunk_sources = np.asarray(estimates[0])[..., retained]
            output[..., offset : offset + available] += (
                chunk_sources * weight[:available]
            )
            sum_weight[offset : offset + available] += weight[:available]
            del estimates
            mx.clear_cache()
        if not np.all(sum_weight > 0):
            raise RuntimeError("Chunk overlap left uncovered output samples")
        output /= sum_weight[None, None, :]
        output = output * standard_deviation + mean
        return {
            source: AudioBuffer(
                output[index].astype(np.float32, copy=False), audio.sample_rate
            )
            for index, source in enumerate(model.sources)
        }

    def extract_vocals(self, audio: AudioBuffer) -> AudioBuffer:
        return self.extract_sources(audio)["vocals"]


@dataclass
class OracleMaskBackend:
    """Deterministic test backend using a caller-supplied time-domain mask."""

    mask: np.ndarray
    sample_rate: int
    channels: int
    name: str = "oracle_mask_test"
    model_name: str = "oracle"

    def extract_vocals(self, audio: AudioBuffer) -> AudioBuffer:
        if audio.sample_rate != self.sample_rate or audio.channels != self.channels:
            raise ValueError("Oracle input shape mismatch")
        mask = np.asarray(self.mask, dtype=np.float32)
        if mask.ndim == 1:
            mask = mask[None, :]
        if mask.shape[1] != audio.frames or mask.shape[0] not in (1, audio.channels):
            raise ValueError("Oracle mask must broadcast to [channels, frames]")
        return AudioBuffer(audio.samples * mask, audio.sample_rate)

    def extract_sources(self, audio: AudioBuffer) -> dict[str, AudioBuffer]:
        return {"vocals": self.extract_vocals(audio)}
