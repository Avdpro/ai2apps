"""Audio-to-audio MLX-RVC inference pipeline for 16 kHz mono input."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import mlx.core as mx
import numpy as np
from scipy import signal

from .contentvec import ContentVec
from .pitch import coarse_f0
from .retrieval import blend_retrieved, retrieve_mlx
from .rmvpe import RMVPE
from .synthesizer import RVCSynthesizer


@dataclass(frozen=True)
class ConversionOptions:
    speaker_id: int = 0
    semitones: float = 0.0
    retrieval_rate: float = 0.0
    protect: float = 0.33
    noise_scale: float = 0.66666
    seed: int = 0

    def validate(self) -> None:
        if not 0 <= self.retrieval_rate <= 1:
            raise ValueError("retrieval_rate must be between zero and one")
        if not 0 <= self.protect <= 0.5:
            raise ValueError("protect must be between zero and 0.5")
        if self.noise_scale < 0:
            raise ValueError("noise_scale must be non-negative")


class RVCInferencePipeline:
    """Compose ContentVec, optional retrieval, RMVPE, and the RVC synthesizer."""

    def __init__(
        self, contentvec: ContentVec, rmvpe: RMVPE, synthesizer: RVCSynthesizer
    ):
        self.contentvec = contentvec
        self.rmvpe = rmvpe
        self.synthesizer = synthesizer
        self._highpass = signal.butter(5, 48, btype="high", fs=16_000)

    def convert_16khz(
        self,
        audio: np.ndarray,
        *,
        options: ConversionOptions | None = None,
        retrieval_vectors: Any | None = None,
    ) -> np.ndarray:
        options = options or ConversionOptions()
        options.validate()
        source = np.asarray(audio, dtype=np.float32)
        if source.ndim != 1 or source.size < 1024:
            raise ValueError(
                "audio must be one-dimensional 16 kHz mono with at least 1024 samples"
            )
        source = signal.filtfilt(*self._highpass, source).astype(np.float32)

        content = self.contentvec(mx.array(source), version="v2")
        original = content
        if retrieval_vectors is not None and options.retrieval_rate > 0:
            retrieved = retrieve_mlx(content[0], retrieval_vectors, k=8).features[None]
            content = blend_retrieved(content, retrieved, options.retrieval_rate)
        content = mx.repeat(content, 2, axis=1)
        original = mx.repeat(original, 2, axis=1)

        raw_f0 = np.asarray(self.rmvpe(mx.array(source)))
        coarse, continuous = coarse_f0(raw_f0, options.semitones)
        frame_count = min(source.size // 160, content.shape[1], continuous.size)
        if frame_count < 1:
            raise ValueError("audio did not produce any RVC frames")
        content = content[:, :frame_count]
        continuous = continuous[:frame_count]
        coarse = coarse[:frame_count]

        if options.protect < 0.5:
            original = original[:, :frame_count]
            voiced = mx.array((continuous > 0).astype(np.float32))[None, :, None]
            protection = mx.where(voiced > 0, 1.0, options.protect)
            content = content * protection + original * (1 - protection)

        mx.random.seed(options.seed)
        noise = mx.random.normal((1, 192, frame_count))
        if options.noise_scale != 0.66666:
            noise = noise * (options.noise_scale / 0.66666)
        output = self.synthesizer(
            content,
            mx.array(coarse[None], dtype=mx.int32),
            mx.array(continuous[None], dtype=mx.float32),
            options.speaker_id,
            noise,
        )
        mx.eval(output)
        return np.asarray(output[0, 0], dtype=np.float32)

    def convert_long_16khz(
        self,
        audio: np.ndarray,
        *,
        options: ConversionOptions | None = None,
        retrieval_vectors: Any | None = None,
        chunk_seconds: float = 10.0,
        context_seconds: float = 1.0,
        crossfade_seconds: float = 0.04,
    ) -> np.ndarray:
        """Bound peak memory by converting overlapping, context-padded chunks."""

        options = options or ConversionOptions()
        source = np.asarray(audio, dtype=np.float32)
        chunk = int(round(chunk_seconds * 16_000))
        context = int(round(context_seconds * 16_000))
        overlap = int(round(crossfade_seconds * 16_000))
        if chunk <= overlap or context < overlap or overlap < 0:
            raise ValueError("chunk/context/crossfade durations are inconsistent")
        if source.size <= chunk:
            return self.convert_16khz(
                source, options=options, retrieval_vectors=retrieval_vectors
            )

        converted: list[np.ndarray] = []
        core_ranges: list[tuple[int, int]] = []
        start = 0
        index = 0
        while start < source.size:
            end = min(start + chunk, source.size)
            extended_start = max(0, start - context)
            extended_end = min(source.size, end + context)
            piece = self.convert_16khz(
                source[extended_start:extended_end],
                options=replace(options, seed=options.seed + index),
                retrieval_vectors=retrieval_vectors,
            )
            crop_start = (start - extended_start) * 3
            desired = (end - start) * 3
            converted.append(piece[crop_start : crop_start + desired])
            core_ranges.append((start, end))
            if end == source.size:
                break
            start = end - overlap
            index += 1

        output = converted[0]
        previous_end = core_ranges[0][1]
        for piece, (start, end) in zip(converted[1:], core_ranges[1:], strict=True):
            overlap_output = min((previous_end - start) * 3, output.size, piece.size)
            if overlap_output:
                fade_in = np.linspace(
                    0, 1, overlap_output, endpoint=False, dtype=np.float32
                )
                blended = (
                    output[-overlap_output:] * (1 - fade_in)
                    + piece[:overlap_output] * fade_in
                )
                output = np.concatenate(
                    (output[:-overlap_output], blended, piece[overlap_output:])
                )
            else:
                output = np.concatenate((output, piece))
            previous_end = end
        return output
