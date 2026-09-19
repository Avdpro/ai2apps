"""VAD contracts and a deterministic baseline for pipeline bring-up."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .audio import AudioBuffer
from .schema import TimeSpan


class VoiceActivityDetector(Protocol):
    name: str

    def detect(self, audio: AudioBuffer) -> list[TimeSpan]: ...


@dataclass
class FullAudioVAD:
    name: str = "full_audio"

    def detect(self, audio: AudioBuffer) -> list[TimeSpan]:
        return [TimeSpan(0.0, audio.duration)] if audio.duration else []


@dataclass
class EnergyVAD:
    """Simple bring-up VAD; it is not presented as a trained MLX VAD model."""

    frame_seconds: float = 0.03
    threshold_ratio: float = 0.01
    absolute_floor: float = 0.0001
    min_speech_seconds: float = 0.18
    merge_gap_seconds: float = 0.25
    pad_seconds: float = 0.12
    name: str = "energy_baseline"

    def detect(self, audio: AudioBuffer) -> list[TimeSpan]:
        frame = max(1, round(self.frame_seconds * audio.sample_rate))
        if not len(audio.samples):
            return []
        usable = int(np.ceil(len(audio.samples) / frame) * frame)
        padded = np.pad(audio.samples, (0, usable - len(audio.samples)))
        rms = np.sqrt(np.mean(padded.reshape(-1, frame) ** 2, axis=1))
        adaptive = float(np.percentile(rms, 90)) * self.threshold_ratio
        threshold = max(self.absolute_floor, adaptive)
        active = np.flatnonzero(rms >= threshold)
        if not len(active):
            return []
        raw: list[TimeSpan] = []
        start = previous = int(active[0])
        for index_value in active[1:]:
            index = int(index_value)
            if (index - previous - 1) * self.frame_seconds > self.merge_gap_seconds:
                raw.append(self._span(start, previous + 1, audio.duration))
                start = index
            previous = index
        raw.append(self._span(start, previous + 1, audio.duration))
        minimum = self.min_speech_seconds
        return [span for span in raw if span.duration >= minimum]

    def _span(self, first_frame: int, last_frame: int, duration: float) -> TimeSpan:
        return TimeSpan(
            max(0.0, first_frame * self.frame_seconds - self.pad_seconds),
            min(duration, last_frame * self.frame_seconds + self.pad_seconds),
        )


@dataclass
class MeetingEnergyVAD(EnergyVAD):
    """Energy baseline calibrated for persistent room noise in meeting mixes."""

    threshold_ratio: float = 0.15
    merge_gap_seconds: float = 1.0
    pad_seconds: float = 0.15
    name: str = "meeting_energy_baseline"
