"""Native MLX image denoising with the MiniMax H3 transformer components."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn

from .config import MODALITY_NUM, TAG_TEXT, DiTConfig
from .dit import (
    FinalLayer,
    RotaryPosEmbed3D,
    TimestepEmbedder,
    TokenRefiner,
    TransformerBlock,
    param_dtype,
    timestep_embedding,
)
from .packing import RefImage, build_packed_sequence, patchify_video_latents, unpatchify_video_tokens
from .scheduler import MiniMaxH3Scheduler


@dataclass(frozen=True)
class ImageStepModulation:
    blocks: tuple[tuple[mx.array, ...], ...]
    output: mx.array


@dataclass(frozen=True)
class ImageModulation:
    has_references: bool
    steps: tuple[ImageStepModulation, ...]


class ImageOutput(FinalLayer):
    """Final RMS normalization and a bank of PDD velocity projections."""

    def __init__(self, config: DiTConfig, steps: int):
        super().__init__(config)
        del self["audio_out"]
        self.video_out = nn.Linear(config.hidden_size, steps * config.video_patch_dim)
        self.patch_dim = config.video_patch_dim

    def modulation(self, temb: mx.array) -> mx.array:
        linear = self.adaln_proj.linear
        return linear(nn.silu(temb).astype(param_dtype(linear)))

    def __call__(self, x: mx.array, modulation: mx.array, step: int) -> mx.array:
        shift, scale = mx.split(modulation, 2, axis=-1)
        timestep_indices = mx.zeros((x.shape[-2],), dtype=mx.int32)
        x = self.norm(x) * (1.0 + scale[timestep_indices]) + shift[timestep_indices]
        lo, hi = step * self.patch_dim, (step + 1) * self.patch_dim
        head_weight = self.video_out.weight[lo:hi]
        head_bias = self.video_out.bias[lo:hi]
        return x.astype(mx.float32) @ head_weight.T + head_bias


class MiniMaxH3ImageDiT(nn.Module):
    """Text-to-image transformer over precomputed H3 text embeddings and initial noise."""

    def __init__(self, config: DiTConfig, sigmas: Sequence[float]):
        super().__init__()
        if len(sigmas) != 7 or sigmas[0] != 1 or sigmas[-1] != 0 or not all(
            a > b for a, b in zip(sigmas, sigmas[1:])
        ):
            raise ValueError("Expected the checkpoint's seven decreasing PDD sigma boundaries.")
        self.config = config
        self.sigmas = tuple(sigmas)
        self.video_patch_proj = nn.Linear(config.video_patch_dim, config.hidden_size)
        self.condition_proj = nn.Linear(config.text_dim, config.hidden_size)
        self.time_embedder = TimestepEmbedder(config)
        self.token_refiner = TokenRefiner(config)
        self.blocks = [TransformerBlock(config) for _ in range(config.num_layers)]
        self.final_layer = ImageOutput(config, len(sigmas) - 1)
        self.rope = RotaryPosEmbed3D(config)

    def _time_embedding(self, time: float, has_references: bool) -> mx.array:
        values = [time, 0.999] if has_references else [time]
        return self.time_embedder(timestep_embedding(
            mx.array(values, dtype=mx.float32), self.config.timestep_input_dim,
        ))

    def prepare_modulation(self, *, has_references: bool) -> ImageModulation:
        """Cache AdaLN for these weights and this request mode, preserving per-step GEMM shapes."""
        scheduler = MiniMaxH3Scheduler()
        scheduler.set_timesteps(sigmas=list(self.sigmas))
        tables = []
        for time in scheduler.timesteps.tolist():
            temb = self._time_embedding(time, has_references)
            blocks = tuple(block.adaln_proj(temb) for block in self.blocks)
            output = self.final_layer.modulation(temb)
            mx.eval(blocks, output)
            tables.append(ImageStepModulation(blocks, output))
        return ImageModulation(has_references, tuple(tables))

    def denoise(
        self,
        text_embeds: mx.array,
        noise: mx.array,
        *,
        text_tags: Sequence[int] | None = None,
        reference_latents: Sequence[mx.array] = (),
        reference_seed: int = 0,
        modulation: ImageModulation | None = None,
        on_step: Callable[[int, mx.array], None] | None = None,
    ) -> mx.array:
        """Return the denoised latent in (1, C, 1, H, W) layout."""
        config = self.config
        if noise.ndim != 5 or noise.shape[:3] != (1, config.latents_dim, 1):
            raise ValueError("Expected single-image noise of shape (1, C, 1, H, W).")
        if text_embeds.ndim != 3 or text_embeds.shape[0] != 1 or text_embeds.shape[2] != config.text_dim:
            raise ValueError("Expected text conditioning of shape (1, tokens, text_dim).")
        height, width = noise.shape[-2:]
        patch_size = config.patch_size
        sample = patchify_video_latents(noise, patch_size)[None]
        text_length = text_embeds.shape[1]
        tags = [TAG_TEXT] * text_length if text_tags is None else list(text_tags)
        if len(tags) != text_length or not text_length:
            raise ValueError("Expected one modality tag per text token.")
        references = tuple(RefImage(*ref.shape[-2:]) for ref in reference_latents)
        if modulation is not None and modulation.has_references != bool(references):
            raise ValueError("Cached modulation was prepared for a different request mode.")
        layout = build_packed_sequence(tags, 1, height, width, 0, patch_size, references=references)
        rotary = self.rope(layout.position_ids)
        text = self.token_refiner(self.condition_proj(text_embeds.astype(param_dtype(self.condition_proj))))
        projection_dtype = param_dtype(self.video_patch_proj)
        reference_embeddings = []
        for ref in reference_latents:
            if ref.ndim != 5 or ref.shape[:3] != noise.shape[:3]:
                raise ValueError("Expected single-image reference latents.")
            rows = patchify_video_latents(ref.astype(mx.float32), patch_size)[None]
            augmentation = mx.random.normal(rows.shape, key=mx.random.key(reference_seed))
            augmented = 0.999 * rows + 0.001 * augmentation
            reference_embeddings.append(self.video_patch_proj(augmented.astype(projection_dtype)).astype(text.dtype))
        prefix = mx.concatenate([text, *reference_embeddings], axis=1)
        target_start = prefix.shape[1]
        modulation_rows = layout.token_tags
        if reference_latents:
            row_ids = mx.arange(layout.sequence_length)
            modulation_rows = modulation_rows + MODALITY_NUM * (
                (row_ids >= text_length) & (row_ids < target_start)
            ).astype(mx.int32)
        mx.eval(prefix, *rotary, modulation_rows)
        scheduler = MiniMaxH3Scheduler()
        scheduler.set_timesteps(sigmas=list(self.sigmas))

        for step, time in enumerate(scheduler.timesteps.tolist()):
            cached = modulation.steps[step] if modulation is not None else None
            if cached is None:
                temb = self._time_embedding(time, bool(references))
            image = self.video_patch_proj(sample.astype(projection_dtype))
            rows = mx.concatenate([prefix, image.astype(prefix.dtype)], axis=1)
            for index, block in enumerate(self.blocks):
                block_modulation = cached.blocks[index] if cached is not None else block.adaln_proj(temb)
                rows = block(rows, block_modulation, modulation_rows, rotary)
            output_modulation = cached.output if cached is not None else self.final_layer.modulation(temb)
            velocity = self.final_layer(rows[:, target_start:], output_modulation, step)
            sample = scheduler.step(velocity, time, sample)
            mx.eval(sample)
            if on_step is not None:
                on_step(step, sample)
        return unpatchify_video_tokens(sample, 1, height, width, config.latents_dim, patch_size)


def load_image_dit(model_dir: str | Path) -> MiniMaxH3ImageDiT:
    """Load an official original-format image checkpoint and its fused PDD heads."""
    from .load import SKIP_KEYS, is_fp32_key, shard_paths

    root = Path(model_dir)
    transformer = root / "transformer"
    config = DiTConfig.from_json(transformer / "config.json")
    schedule = json.loads((root / "pdd_config.json").read_text())
    model = MiniMaxH3ImageDiT(config, schedule["sigmas"])
    heads = mx.load(str(root / "pdd_fused_heads.safetensors"))
    weight_shape = (6, config.video_patch_dim, config.hidden_size)
    head_weight = heads["video_out.weight"]
    head_bias = heads["video_out.bias"]
    if head_weight.shape != weight_shape or head_bias.shape != weight_shape[:2]:
        raise ValueError("PDD output heads do not match the transformer configuration.")
    weights = {
        "final_layer.video_out.weight": head_weight.reshape(-1, config.hidden_size).astype(mx.float32),
        "final_layer.video_out.bias": head_bias.reshape(-1).astype(mx.float32),
    }
    for path in shard_paths(transformer):
        for key, tensor in mx.load(str(path)).items():
            if key in SKIP_KEYS or key in ("final_layer.video_out.weight", "final_layer.video_out.bias"):
                continue
            if key.endswith(".attn.qkv_proj.weight"):
                # Original shards interleave Q/K/V inside each head. The shared MLX
                # attention module consumes the contiguous Q, K and V groups.
                with mx.stream(mx.cpu):
                    tensor = mx.contiguous(tensor.reshape(
                        config.num_attention_heads, 3, config.attention_head_dim, config.hidden_size,
                    ).transpose(1, 0, 2, 3)).reshape(3 * config.inner_dim, config.hidden_size)
                    mx.eval(tensor)
            weights[key] = tensor.astype(mx.float32) if is_fp32_key(key) else tensor
    model.load_weights(list(weights.items()), strict=True)
    mx.eval(model.parameters())
    return model
