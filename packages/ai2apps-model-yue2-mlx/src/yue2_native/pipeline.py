"""Staged local YuE2 pipeline. Preserves exact ABC token IDs between stages."""

from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import numpy as np

from .model import Model
from .nar import synthesize
from .protocol import (
    CODEC_OFFSET,
    GenerationConfig,
    SongRequest,
    negative_prefix,
    resolve_sampling,
    token_prefixes,
)
from .sampling import generate_tokens
from .tokenization_yue2 import YuE2TextTokenizer
from .vae import VAE


@dataclass
class Plan:
    request: SongRequest
    abc: str | None
    abc_ids: list
    prefix: list
    timing: dict
    truncated: bool = False


@dataclass
class Semantic:
    plan: Plan
    tokens: list
    timing: dict
    truncated: bool = False


class Pipeline:
    def __init__(
        self, model_path, vae_path, config=None, dtype=mx.bfloat16, memory_mode="staged"
    ):
        self.model_path = Path(model_path)
        self.vae_path = Path(vae_path)
        self.config = config or GenerationConfig()
        self.dtype = dtype
        if memory_mode not in {"staged", "resident"}:
            raise ValueError("Unknown memory mode")
        self.memory_mode = memory_mode
        self.memory_events = []
        self.tokenizer = YuE2TextTokenizer(self.model_path / "qwen.tiktoken")
        self.model = None
        self.vae = None

    def record_memory(self, stage):
        self.memory_events.append(
            {
                "stage": stage,
                "activeGiB": mx.get_active_memory() / 2**30,
                "cacheGiB": mx.get_cache_memory() / 2**30,
                "peakGiB": mx.get_peak_memory() / 2**30,
            }
        )

    def load_model(self):
        if self.model is None:
            self.vae = None
            mx.clear_cache()
            self.model = Model.load(
                self.model_path,
                self.dtype,
                phase="ar" if self.memory_mode == "staged" else "all",
            )
        self.model.activate("ar")
        self.record_memory("ar_ready")
        return self.model

    def plan(self, request, abc_sampling=None, cancelled=None, on_token=None):
        if request.cot == "off":
            return Plan(request, None, [], token_prefixes(request, self.tokenizer), {})
        if request.abc is not None:
            ids = self.tokenizer.encode(request.abc)
            return Plan(
                request,
                request.abc,
                ids,
                token_prefixes(request, self.tokenizer, ids),
                {},
            )
        ids, timing, truncated = generate_tokens(
            self.load_model(),
            token_prefixes(request, self.tokenizer),
            resolve_sampling(abc_sampling, self.config.abc),
            request.seed,
            "abc",
            cancelled=cancelled,
            on_token=on_token,
        )
        return Plan(
            request,
            self.tokenizer.decode(ids),
            ids,
            token_prefixes(request, self.tokenizer, ids),
            timing,
            truncated,
        )

    def generate_semantic(self, plan, sampling=None, cancelled=None, on_token=None):
        if token_prefixes(plan.request, self.tokenizer, plan.abc_ids) != plan.prefix:
            raise ValueError("Plan token identity changed")
        r = plan.request
        negative = (
            negative_prefix(r, self.tokenizer, plan.abc_ids)
            if r.guidance != 1
            else None
        )
        ids, timing, truncated = generate_tokens(
            self.load_model(),
            plan.prefix,
            resolve_sampling(sampling, self.config.semantic),
            r.seed,
            "semantic",
            negative=negative,
            cfg_scale=r.guidance,
            legacy_off=r.cot == "off",
            cancelled=cancelled,
            on_token=on_token,
        )
        return Semantic(plan, [i - CODEC_OFFSET for i in ids], timing, truncated)

    def synthesize(self, semantic, noise=None, cancelled=None, progress=None):
        if (
            token_prefixes(semantic.plan.request, self.tokenizer, semantic.plan.abc_ids)
            != semantic.plan.prefix
        ):
            raise ValueError("Plan token identity changed")
        return synthesize(
            self.load_model(),
            semantic.plan.prefix,
            semantic.tokens,
            semantic.plan.request.seed,
            self.config.ode_steps,
            noise,
            cancelled,
            progress,
        )

    def decode(self, latents, core_frames=256, cancelled=None, progress=None):
        if self.memory_mode == "staged":
            self.model = None
            mx.clear_cache()
        self.record_memory("before_vae")
        if self.vae is None:
            self.vae = VAE.load(self.vae_path)
        z = np.asarray(latents, np.float32)
        if z.ndim != 2 or z.shape[1] != 64 or z.shape[0] < 1:
            raise ValueError("Expected latents [T,64]")
        audio = self.vae.decode_tiled(
            z[None], core_frames=core_frames, cancelled=cancelled, progress=progress
        )[0]
        self.record_memory("decoded")
        if not np.isfinite(audio).all():
            raise FloatingPointError("Nonfinite decoded waveform")
        return np.clip(audio, -1, 1)

    def close(self):
        self.model = self.vae = None
        mx.clear_cache()
