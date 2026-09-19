"""End-to-end MLX RVC v2 synthesizer after content and F0 extraction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from .flow import ReverseResidualCouplingFlow
from .generator import NSFGenerator
from .text_encoder import TextEncoder


class RVCSynthesizer:
    def __init__(self, state: Mapping[str, np.ndarray]) -> None:
        import mlx.core as mx

        self.mx = mx
        self.state = {name: mx.array(value) for name, value in state.items()}
        self.encoder = TextEncoder(state)
        self.flow = ReverseResidualCouplingFlow(state)
        self.generator = NSFGenerator(
            state,
            sample_rate=48_000,
            upsample_rates=(12, 10, 2, 2),
            upsample_kernel_sizes=(24, 20, 4, 4),
        )

    def __call__(
        self,
        phone: Any,
        pitch: Any,
        continuous_f0: Any,
        speaker_id: int,
        latent_noise: Any,
        *,
        trace: dict[str, Any] | None = None,
    ) -> Any:
        mx = self.mx
        if not 0 <= speaker_id < self.state["emb_g.weight"].shape[0]:
            raise ValueError("speaker id is outside the checkpoint speaker table")
        lengths = mx.array([phone.shape[1]], dtype=mx.int32)
        mean, log_scale, mask = self.encoder(phone, pitch, lengths)
        if latent_noise.shape != mean.shape:
            raise ValueError("latent noise must match the encoder distribution shape")
        latent = (mean + mx.exp(log_scale) * latent_noise * 0.66666) * mask
        conditioning = self.state["emb_g.weight"][speaker_id][None, :, None]
        decoded = self.flow(latent, mask, conditioning)
        if trace is not None:
            trace.update(
                mean=mean,
                log_scale=log_scale,
                latent=latent,
                decoded=decoded,
            )
        return self.generator(decoded * mask, continuous_f0, conditioning)
