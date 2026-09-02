"""End-to-end native MLX Ideogram 4 baseline pipeline."""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import numpy as np
from mlx_model import (
    LLM_TOKEN_INDICATOR,
    OUTPUT_IMAGE_INDICATOR,
    load_quantized_transformer,
)
from PIL import Image
from scheduler import schedule_for_resolution, steps_for_strength
from text_encoder import load_quantized_text_encoder
from transformers import AutoTokenizer
from vae import decode_packed, encode_image, load_vae

IMAGE_POSITION_OFFSET = 65536


@dataclass(frozen=True)
class PipelinePaths:
    derived_root: Path
    qwen_config_root: Path


class Ideogram4MLXPipeline:
    def __init__(
        self,
        paths: PipelinePaths,
        *,
        bits: int = 8,
        group_size: int = 64,
        staged: bool = True,
        compile_denoisers: bool = False,
    ):
        self.paths = paths
        self.bits = bits
        self.text_bits = bits if bits in (4, 8) else 4
        self.group_size = group_size
        self.staged = staged
        self.compile_denoisers = compile_denoisers
        self.tokenizer = AutoTokenizer.from_pretrained(
            paths.qwen_config_root, local_files_only=True
        )
        self.text_encoder = None
        self.conditional = None
        self.unconditional = None
        self.vae = None
        if not staged:
            self._load_text_encoder()
            self._load_generation_models()

    def _load_text_encoder(self) -> None:
        if self.text_encoder is None:
            self.text_encoder = load_quantized_text_encoder(
                self.paths.derived_root / f"text_encoder-q{self.text_bits}.safetensors",
                self.paths.qwen_config_root / "config.json",
                bits=self.text_bits,
                group_size=self.group_size,
            )

    def _load_generation_models(self) -> None:
        if self.conditional is None:
            self.conditional = load_quantized_transformer(
                self.paths.derived_root / f"conditional-q{self.bits}.safetensors",
                bits=self.bits,
                group_size=self.group_size,
            )
        if self.unconditional is None:
            self.unconditional = load_quantized_transformer(
                self.paths.derived_root / f"unconditional-q{self.bits}.safetensors",
                bits=self.bits,
                group_size=self.group_size,
            )
        if self.vae is None:
            self.vae = load_vae(
                self.paths.derived_root / f"vae-q{self.text_bits}.safetensors"
            )

    @staticmethod
    def _reclaim_metal() -> None:
        # Evaluation is a required barrier before buffers may be returned to
        # Metal's cache. Clearing without it can race in-flight command buffers.
        mx.synchronize()
        gc.collect()
        mx.clear_cache()

    def _release_text_encoder(self) -> None:
        self.text_encoder = None
        self._reclaim_metal()

    def _release_generation_models(self) -> None:
        self.conditional = None
        self.unconditional = None
        self.vae = None
        self._reclaim_metal()

    def tokenize(self, prompt: str) -> mx.array:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        text = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
        )
        token_ids = self.tokenizer(text, add_special_tokens=False)["input_ids"]
        if len(token_ids) > 2048:
            raise ValueError("Ideogram 4 prompt exceeds 2048 tokens")
        return mx.array(token_ids, dtype=mx.int32)[None, :]

    @staticmethod
    def positions(text_tokens: int, grid_h: int, grid_w: int) -> mx.array:
        text = mx.arange(text_tokens, dtype=mx.int32)
        text = mx.stack((text, text, text), axis=-1)
        height = mx.repeat(mx.arange(grid_h, dtype=mx.int32), grid_w)
        width = mx.tile(mx.arange(grid_w, dtype=mx.int32), grid_h)
        image = mx.stack((mx.zeros_like(height), height, width), axis=-1)
        image += IMAGE_POSITION_OFFSET
        return mx.concatenate((text, image), axis=0)[None, :, :]

    def generate(
        self,
        prompt: str,
        *,
        height: int,
        width: int,
        seed: int,
        steps: int = 12,
        mu: float = 0.5,
        std: float = 1.75,
        guidance_schedule: list[float] | None = None,
        image: Image.Image | None = None,
        strength: float | None = None,
    ) -> tuple[Image.Image, dict[str, object]]:
        if not (256 <= height <= 2048 and 256 <= width <= 2048):
            raise ValueError("height and width must be in [256, 2048]")
        if height % 16 or width % 16:
            raise ValueError("height and width must be divisible by 16")
        if image is None and strength is not None:
            raise ValueError("strength requires an input image")
        image_strength = 0.75 if image is not None and strength is None else strength
        effective_steps = (
            steps
            if image_strength is None
            else steps_for_strength(steps, image_strength)
        )
        token_ids = self.tokenize(prompt)
        stage_seconds: dict[str, float] = {}
        if self.staged:
            transition_started = time.perf_counter()
            self._release_generation_models()
            stage_seconds["release_generation_models"] = (
                time.perf_counter() - transition_started
            )
        load_started = time.perf_counter()
        self._load_text_encoder()
        stage_seconds["load_text_encoder"] = time.perf_counter() - load_started
        assert self.text_encoder is not None
        encode_started = time.perf_counter()
        text_features = self.text_encoder(token_ids)
        mx.eval(text_features)
        stage_seconds["encode_prompt"] = time.perf_counter() - encode_started
        if self.staged:
            transition_started = time.perf_counter()
            self._release_text_encoder()
            stage_seconds["release_text_encoder"] = (
                time.perf_counter() - transition_started
            )
        load_started = time.perf_counter()
        self._load_generation_models()
        stage_seconds["load_generation_models"] = time.perf_counter() - load_started
        assert self.conditional is not None
        assert self.unconditional is not None
        assert self.vae is not None
        text_tokens = token_ids.shape[1]
        grid_h, grid_w = height // 16, width // 16
        image_tokens = grid_h * grid_w
        sequence = text_tokens + image_tokens

        if image is not None:
            image_encode_started = time.perf_counter()
            clean_latent = encode_image(
                self.vae,
                image,
                width=width,
                height=height,
            )
            mx.eval(clean_latent)
            stage_seconds["encode_image"] = time.perf_counter() - image_encode_started
            if clean_latent.shape != (1, image_tokens, 128):
                raise ValueError(
                    "encoded input image has unexpected latent shape "
                    f"{clean_latent.shape}; expected {(1, image_tokens, 128)}"
                )

        llm_features = mx.concatenate(
            (
                text_features,
                mx.zeros(
                    (1, image_tokens, text_features.shape[-1]),
                    dtype=text_features.dtype,
                ),
            ),
            axis=1,
        )
        position_ids = self.positions(text_tokens, grid_h, grid_w)
        indicator = mx.array(
            [
                [LLM_TOKEN_INDICATOR] * text_tokens
                + [OUTPUT_IMAGE_INDICATOR] * image_tokens
            ],
            dtype=mx.int32,
        )
        segment_ids = mx.ones((1, sequence), dtype=mx.int32)
        negative_position_ids = position_ids[:, text_tokens:]
        negative_indicator = indicator[:, text_tokens:]
        negative_segments = segment_ids[:, text_tokens:]
        negative_features = mx.zeros(
            (1, image_tokens, text_features.shape[-1]), dtype=text_features.dtype
        )
        positive_static = self.conditional.prepare_conditioning(
            llm_features=llm_features,
            value=mx.concatenate(
                (
                    mx.zeros((1, text_tokens, 128), dtype=mx.float32),
                    mx.zeros((1, image_tokens, 128), dtype=mx.float32),
                ),
                axis=1,
            ),
            position_ids=position_ids,
            segment_ids=segment_ids,
            indicator=indicator,
            uniform_segments=True,
        )
        negative_static = self.unconditional.prepare_conditioning(
            llm_features=negative_features,
            value=mx.zeros((1, image_tokens, 128), dtype=mx.float32),
            position_ids=negative_position_ids,
            segment_ids=negative_segments,
            indicator=negative_indicator,
            uniform_segments=True,
        )

        def positive_predict(current: mx.array, timestep: mx.array) -> mx.array:
            positive_input = mx.concatenate((text_latent, current), axis=1)
            return self.conditional(
                llm_features=llm_features,
                value=positive_input,
                timestep=timestep,
                position_ids=position_ids,
                segment_ids=segment_ids,
                indicator=indicator,
                prepared=positive_static,
            )[:, text_tokens:]

        def negative_predict(current: mx.array, timestep: mx.array) -> mx.array:
            return self.unconditional(
                llm_features=negative_features,
                value=current,
                timestep=timestep,
                position_ids=negative_position_ids,
                segment_ids=negative_segments,
                indicator=negative_indicator,
                prepared=negative_static,
            )

        if self.compile_denoisers:
            positive_predict = mx.compile(positive_predict)
            negative_predict = mx.compile(negative_predict)

        mx.random.seed(seed)
        noise = mx.random.normal((1, image_tokens, 128), dtype=mx.float32)
        text_latent = mx.zeros((1, text_tokens, 128), dtype=mx.float32)
        times = schedule_for_resolution(steps, height, width, known_mean=mu, std=std)
        if image is None:
            latent = noise
        else:
            start_time = float(times[effective_steps])
            latent = start_time * clean_latent + (1.0 - start_time) * noise
        guidance = np.array(
            guidance_schedule or ([3.0] + [7.0] * (steps - 1)),
            dtype=np.float32,
        )
        if guidance.shape != (steps,):
            raise ValueError(f"guidance_schedule must contain {steps} values")

        step_seconds = []
        started = time.perf_counter()
        for index in range(effective_steps - 1, -1, -1):
            step_started = time.perf_counter()
            timestep = mx.array([float(times[index + 1])], dtype=mx.float32)
            positive = positive_predict(latent, timestep)
            negative = negative_predict(latent, timestep)
            velocity = guidance[index] * positive + (1.0 - guidance[index]) * negative
            latent = latent + velocity * float(times[index] - times[index + 1])
            mx.eval(latent)
            step_seconds.append(time.perf_counter() - step_started)
        denoise_seconds = time.perf_counter() - started

        decode_started = time.perf_counter()
        decoded = decode_packed(self.vae, latent, grid_h, grid_w)
        decoded = mx.clip(decoded.astype(mx.float32), -1.0, 1.0)
        decoded = mx.round((decoded + 1.0) * 127.5).astype(mx.uint8)
        decoded = decoded.transpose(0, 2, 3, 1)
        mx.eval(decoded)
        image = Image.fromarray(np.array(decoded[0]))
        report = {
            "height": height,
            "width": width,
            "seed": seed,
            "steps": steps,
            "effective_steps": effective_steps,
            "operation": "image_edit" if image is not None else "image_generation",
            "image_strength": image_strength,
            "text_tokens": text_tokens,
            "image_tokens": image_tokens,
            "denoise_seconds": denoise_seconds,
            "decode_seconds": time.perf_counter() - decode_started,
            "step_seconds": step_seconds,
            "stage_seconds": stage_seconds,
            "staged_model_lifecycle": self.staged,
            "compiled_denoisers": self.compile_denoisers,
            "latent_mean": float(mx.mean(latent).item()),
            "latent_std": float(mx.std(latent).item()),
            "latent_absmax": float(mx.max(mx.abs(latent)).item()),
            "active_memory_bytes": mx.get_active_memory(),
            "peak_memory_bytes": mx.get_peak_memory(),
        }
        return image, report
