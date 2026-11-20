"""Settings of a conversation and the frame it produces every 133 ms."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .sampling import DryConfig


@dataclass
class DuplexConfig:
    guidance_scale: float = 1.5  # audio guidance (valid range 1-2)
    temperature: float = 0.7
    top_k: int = 25
    top_p: float = 1.0
    dry: DryConfig | None = field(default_factory=DryConfig)
    eop_bias: float = 0.0  # added to the EOP logit: > 0 makes the model start speaking sooner
    speak_first: bool = False  # the model opens the conversation
    max_frames: int = 27_000  # 60 minutes
    reference_seconds: float = 180.0
    seed: int | None = None


@dataclass
class Frame:
    audio: np.ndarray  # float32 [3200] at 24 kHz
    token: int
    text: str  # new text of this frame, "" if none
    index: int
    seconds: float  # compute time
    done: bool = False
