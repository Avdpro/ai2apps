"""MLX port of ``MiniMaxH3DiTModel`` — the 33B MiniMax-H3 diffusion transformer.

The module tree reproduces the *original* checkpoint names, so the released safetensors load
1:1 with no weight surgery:

    video_patch_proj / audio_patch_proj / condition_proj
    time_embedder.proj_in / .proj_out
    token_refiner.blocks.{i}.{norm1,norm2,attn.*,mlp.*} + token_refiner.final_norm
    blocks.{i}.{norm1,norm2,attn.*,mlp.*,adaln_proj.linear}
    final_layer.{norm,adaln_proj.linear,video_out,audio_out}

Two raw-checkpoint layout quirks are handled by reshape/split in the forward pass rather than by
rewriting weights:

* ``attn.qkv_proj`` rows are three contiguous projections — ``[all Q | all K | all V]`` — so the
  projection output reshapes to ``(..., 3, heads, head_dim)``. This deliberately differs from the
  Video VAE, whose QKV rows are per-head interleaved.
* ``mlp.fc1`` is a fused **``[gate; value]``** SwiGLU projection; the reference computes
  ``fc2(silu(gate) * value)``.

MiniMax-H3 runs one stack over a single packed 1-D sequence holding text, conditioning and
target video rows, and audio rows. Attention is full self-attention over that sequence; there
is no cross-attention and no per-modality block weights. Modality-specific behaviour comes only
from the two input patch projections, the per-row AdaLN modality tag, and the two output heads.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import mlx.core as mx
import mlx.nn as nn

from .config import MODALITY_NUM, DiTConfig
from .fused_ops import residual_rms_adaln, rms_adaln

if TYPE_CHECKING:
    from .adaln import ModulationCache


def param_dtype(layer: nn.Module) -> mx.Dtype:
    """The dtype a layer's *activations* should be aligned to.

    The reference casts each input to its projection's parameter dtype, and reading
    ``layer.weight.dtype`` is the obvious way to do that — but it is wrong the moment the layer is
    quantized. ``QuantizedLinear.weight`` is **packed uint32 storage**, so casting activations to it
    truncates them to integers, silently and identically at every bit width. The scales carry the
    real compute dtype.
    """
    scales = getattr(layer, "scales", None)
    return scales.dtype if scales is not None else layer.weight.dtype


def timestep_embedding(
    timesteps: mx.array,
    dim: int,
    max_period: float = 10000.0,
    flip_sin_to_cos: bool = True,
    downscale_freq_shift: float = 0.0,
) -> mx.array:
    """Sinusoidal timestep embedding matching diffusers ``Timesteps`` / ``get_timestep_embedding``.

    Timesteps are consumed unscaled in ``[0, 1]``.
    """
    half_dim = dim // 2
    exponent = -math.log(max_period) * mx.arange(half_dim, dtype=mx.float32)
    exponent = exponent / (half_dim - downscale_freq_shift)
    emb = mx.exp(exponent)
    emb = timesteps.astype(mx.float32)[:, None] * emb[None, :]
    # diffusers builds [sin, cos] then swaps the halves when `flip_sin_to_cos`.
    if flip_sin_to_cos:
        return mx.concatenate([mx.cos(emb), mx.sin(emb)], axis=-1)
    return mx.concatenate([mx.sin(emb), mx.cos(emb)], axis=-1)


class TimestepEmbedder(nn.Module):
    """The timestep MLP shared by every AdaLN projection (``proj_in`` -> silu -> ``proj_out``).

    Kept in float32: it is a float32 module in the released mixed-precision checkpoint, and every
    block reads the same ``temb``, so a rounding applied here biases every block's modulation
    identically at every sampling step and accumulates coherently over the denoising trajectory.
    """

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.proj_in = nn.Linear(config.timestep_input_dim, config.time_embed_hidden_size, bias=True)
        self.proj_out = nn.Linear(config.time_embed_hidden_size, config.time_embed_dim, bias=True)

    def __call__(self, sinusoid: mx.array) -> mx.array:
        return self.proj_out(nn.silu(self.proj_in(sinusoid)))


class RotaryPosEmbed3D:
    """3-axis rotary embedding over the ``(t, h, w)`` coordinates of the packed sequence.

    One ``inv_freq`` buffer of ``rope_inv_freq_len`` frequencies is shared by the three axes.
    Each axis contributes that many angles; the three blocks are concatenated to
    ``3 * rope_inv_freq_len`` and then concatenated with themselves, so the rotate-half convention
    rotates ``2 * 3 * rope_inv_freq_len`` of the head channels and passes the rest through.
    """

    def __init__(self, config: DiTConfig):
        n = config.rope_inv_freq_len
        self.inv_freq = 1.0 / (
            config.rope_theta ** (mx.arange(0, 2 * n, 2, dtype=mx.float32) / (2 * n))
        )

    def __call__(self, position_ids: mx.array) -> tuple[mx.array, mx.array]:
        # position_ids: (seq_len, 3) -> cos/sin: (seq_len, 2 * 3 * inv_freq_len)
        pos = position_ids.astype(mx.float32)
        freqs = pos[..., None] * self.inv_freq.reshape(1, 1, -1)  # (seq, 3, n)
        freqs = mx.concatenate([freqs[:, 0], freqs[:, 1], freqs[:, 2]], axis=-1)
        freqs = mx.concatenate([freqs, freqs], axis=-1)
        return mx.cos(freqs), mx.sin(freqs)


def apply_rotary(x: mx.array, cos: mx.array, sin: mx.array) -> mx.array:
    """Rotate the leading ``rotary_dim`` channels of every head, pass the rest through.

    ``x`` is ``(batch, heads, seq, head_dim)``; ``cos``/``sin`` are ``(seq, rotary_dim)``.
    """
    rotary_dim = cos.shape[-1]
    x_rot, x_pass = x[..., :rotary_dim], x[..., rotary_dim:]
    cos = cos.astype(x.dtype)[None, None, :, :]
    sin = sin.astype(x.dtype)[None, None, :, :]
    half = rotary_dim // 2
    x1, x2 = x_rot[..., :half], x_rot[..., half:]
    rotated = mx.concatenate([-x2, x1], axis=-1)
    out = x_rot * cos + rotated * sin
    if x_pass.shape[-1] == 0:
        return out
    return mx.concatenate([out, x_pass], axis=-1)


class Attention(nn.Module):
    """Full self-attention over the packed sequence, with per-head q/k RMSNorm."""

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.heads = config.num_attention_heads
        self.head_dim = config.attention_head_dim
        self.scale = self.head_dim**-0.5

        self.qkv_proj = nn.Linear(config.hidden_size, 3 * config.inner_dim, bias=False)
        self.q_norm = nn.RMSNorm(config.attention_head_dim, eps=config.qk_norm_eps)
        self.k_norm = nn.RMSNorm(config.attention_head_dim, eps=config.qk_norm_eps)
        self.out_proj = nn.Linear(config.inner_dim, config.hidden_size, bias=False)
        # Populated only for a converted FastH3 checkpoint. Keeping these as
        # ordinary attributes makes dense H3 checkpoints byte-for-byte unchanged.
        self.vsa_geometry = None
        self.vsa_sparsity = 0.0
        self.gate_compress = None
        # OpenVDN is kept external to the module parameter tree.  A staged
        # loader attaches one block's immutable branch tensors and geometry.
        self.vdn_geometry = None
        self.vdn_weights = None

    def __call__(
        self,
        x: mx.array,
        rotary: tuple[mx.array, mx.array] | None = None,
        mask: mx.array | None = None,
    ) -> mx.array:
        B, S, _ = x.shape
        # DiT/Token-Refiner QKV rows are three contiguous chunks. Do not reuse the Video VAE's
        # per-head-interleaved layout here: it silently mixes Q/K/V and produces texture-only clips.
        qkv = self.qkv_proj(x).reshape(B, S, 3, self.heads, self.head_dim)
        q, k, v = qkv[:, :, 0], qkv[:, :, 1], qkv[:, :, 2]

        q_raw, k_raw, v_raw = q, k, v
        q = self.q_norm(q).transpose(0, 2, 1, 3)
        k = self.k_norm(k).transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)

        if rotary is not None:
            q = apply_rotary(q, *rotary)
            k = apply_rotary(k, *rotary)

        if self.vdn_geometry is not None and self.vdn_weights is not None and B == 1 and mask is None:
            from .openvdn import hybrid_attention

            return hybrid_attention(
                x[0], q_raw[0], k_raw[0], v_raw[0],
                q[0].transpose(1, 0, 2), k[0].transpose(1, 0, 2),
                v[0].transpose(1, 0, 2), self.out_proj,
                self.vdn_weights, self.vdn_geometry,
            )[None]

        if self.vsa_geometry is not None and self.vsa_sparsity > 0 and B == 1 and mask is None:
            from .vsa import vsa_attention

            gate = None
            if self.gate_compress is not None:
                gate = self.gate_compress(x).reshape(B, S, self.heads, self.head_dim)[0]
            out = vsa_attention(
                q[0].transpose(1, 0, 2), k[0].transpose(1, 0, 2),
                v[0].transpose(1, 0, 2), self.vsa_geometry,
                sparsity=self.vsa_sparsity, gate=gate,
            )[None].reshape(B, S, self.heads * self.head_dim)
        else:
            out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale, mask=mask)
            out = out.transpose(0, 2, 1, 3).reshape(B, S, self.heads * self.head_dim)
        return self.out_proj(out.astype(x.dtype))


class FeedForward(nn.Module):
    """SwiGLU feed-forward. ``fc1`` is the fused ``[gate; value]`` projection."""

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.fc1 = nn.Linear(config.hidden_size, 2 * config.ffn_hidden_size, bias=False)
        self.fc2 = nn.Linear(config.ffn_hidden_size, config.hidden_size, bias=False)
        self._ffn = config.ffn_hidden_size

    def __call__(self, x: mx.array) -> mx.array:
        fused = self.fc1(x)
        gate, value = fused[..., : self._ffn], fused[..., self._ffn :]
        return self.fc2(nn.silu(gate) * value)


class AdaLayerNormModulation(nn.Module):
    """Projects the shared timestep embedding into one block's six modulation parameters.

    ``(num_timesteps, time_embed_dim)`` -> six tensors of shape
    ``(num_timesteps * MODALITY_NUM, hidden_size)`` in
    ``shift_msa, scale_msa, gate_msa, shift_mlp, scale_mlp, gate_mlp`` order. Row layout is
    ``[t0_mod0, t0_mod1, t0_mod2, t1_mod0, ...]``, which
    ``timestep_indices * MODALITY_NUM + token_tags`` addresses.

    One projection is shared by ``norm1`` and ``norm2`` and by the three modalities, so it cannot
    be folded into either norm.
    """

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.hidden_size = config.hidden_size
        self.linear = nn.Linear(config.time_embed_dim, config.adaln_out_features, bias=True)

    def __call__(self, temb: mx.array) -> tuple[mx.array, ...]:
        # Activate at `temb`'s own (float32) precision, cast to the projection's dtype after.
        h = nn.silu(temb).astype(param_dtype(self.linear))
        h = self.linear(h).reshape(-1, 6 * self.hidden_size)
        return tuple(h[..., i * self.hidden_size : (i + 1) * self.hidden_size] for i in range(6))


class AdaLayerNormModulationOut(nn.Module):
    """``final_layer.adaln_proj`` — the ``linear`` sub-name matches the checkpoint."""

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.linear = nn.Linear(config.time_embed_dim, config.final_adaln_out_features, bias=True)


class FinalLayer(nn.Module):
    """Checkpoint's ``final_layer``: shared modulated norm plus the two output heads.

    The modulation table holds one row per *timestep* and is addressed per row of the packed
    sequence. The two halves of the projection are ``shift`` then ``scale``.
    """

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.norm = nn.RMSNorm(config.hidden_size, eps=config.final_norm_eps)
        self.adaln_proj = AdaLayerNormModulationOut(config)
        self.video_out = nn.Linear(config.hidden_size, config.video_patch_dim, bias=True)
        self.audio_out = nn.Linear(config.hidden_size, config.audio_latents_dim, bias=True)
        self.hidden_size = config.hidden_size

    def norm_out(self, x: mx.array, temb: mx.array, timestep_indices: mx.array) -> mx.array:
        h = self.adaln_proj.linear(nn.silu(temb).astype(param_dtype(self.adaln_proj.linear)))
        shift, scale = h[..., : self.hidden_size], h[..., self.hidden_size :]
        x = self.norm(x)
        return x * (1.0 + scale[timestep_indices]) + shift[timestep_indices]


class TokenRefinerBlock(nn.Module):
    """Plain pre-norm block used to refine the projected text stream. No AdaLN, no rotary."""

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.norm1 = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)
        self.attn = Attention(config)
        self.norm2 = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)
        self.mlp = FeedForward(config)

    def __call__(self, x: mx.array) -> mx.array:
        x = x + self.attn(self.norm1(x))
        return x + self.mlp(self.norm2(x))


class TokenRefiner(nn.Module):
    def __init__(self, config: DiTConfig):
        super().__init__()
        self.blocks = [TokenRefinerBlock(config) for _ in range(config.token_refiner_num_layers)]
        self.final_norm = nn.RMSNorm(config.hidden_size, eps=config.final_norm_eps)

    def __call__(self, x: mx.array) -> mx.array:
        for block in self.blocks:
            x = block(x)
        return self.final_norm(x)


class TransformerBlock(nn.Module):
    """Pre-norm attention and feed-forward, each modulated by AdaLN parameters selected per row."""

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.norm1 = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)
        self.attn = Attention(config)
        self.norm2 = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)
        self.mlp = FeedForward(config)
        self.adaln_proj = AdaLayerNormModulation(config)
        self.norm_eps = config.norm_eps
        self.use_fused_ops = False

    def __call__(
        self,
        x: mx.array,
        modulation: tuple[mx.array, ...],
        adaln_indices: mx.array,
        rotary: tuple[mx.array, mx.array],
        mask: mx.array | None = None,
        cached_attention: mx.array | None = None,
        return_attention: bool = False,
    ) -> mx.array | tuple[mx.array, mx.array]:
        shift_msa, scale_msa, gate_msa, shift_mlp, scale_mlp, gate_mlp = modulation

        if cached_attention is None:
            if self.use_fused_ops:
                h = rms_adaln(
                    x, self.norm1.weight, shift_msa, scale_msa,
                    adaln_indices, self.norm_eps,
                )
            else:
                h = self.norm1(x)
                h = h * (1.0 + scale_msa[adaln_indices]) + shift_msa[adaln_indices]
            attention = self.attn(h, rotary, mask)
        else:
            # PAB semantics: cache the post-output-projection attention branch, but always apply
            # the current step's AdaLN gate. The MLP branch is never cached.
            attention = cached_attention
        if self.use_fused_ops:
            x, h = residual_rms_adaln(
                x, attention, gate_msa, self.norm2.weight,
                shift_mlp, scale_mlp, adaln_indices, self.norm_eps,
            )
        else:
            x = x + gate_msa[adaln_indices] * attention
            h = self.norm2(x)
            h = h * (1.0 + scale_mlp[adaln_indices]) + shift_mlp[adaln_indices]
        x = x + gate_mlp[adaln_indices] * self.mlp(h)
        return (x, attention) if return_attention else x


class MiniMaxH3DiT(nn.Module):
    """The MiniMax-H3 joint video + audio diffusion transformer.

    The caller builds the packed layout: patchified video latents, row order, the ``(t, h, w)``
    position grid, per-row modality tags and per-row timestep indices. See ``packing.py``.
    """

    def __init__(self, config: DiTConfig):
        super().__init__()
        self.config = config

        # 1. Per-modality input projections.
        self.video_patch_proj = nn.Linear(config.video_patch_dim, config.hidden_size, bias=True)
        self.audio_patch_proj = nn.Linear(config.audio_latents_dim, config.hidden_size, bias=True)
        self.condition_proj = nn.Linear(config.text_dim, config.hidden_size, bias=True)

        # 2. Timestep embedding, shared by every AdaLN projection.
        self.time_embedder = TimestepEmbedder(config)

        # 3. Text stream refiner.
        self.token_refiner = TokenRefiner(config)

        # 4. The block stack.
        self.blocks = [TransformerBlock(config) for _ in range(config.num_layers)]

        # 5. Shared output norm and the two per-modality heads. Both heads run over every row;
        #    the rows of each modality are selected afterwards.
        self.final_layer = FinalLayer(config)

        # Rotary is a computed buffer, not a parameter (`rope.inv_freq` is recomputed bit-exactly).
        self.rope = RotaryPosEmbed3D(config)

    def __call__(
        self,
        video_latents: mx.array,
        audio_latents: mx.array,
        text_embeds: mx.array,
        timestep: mx.array,
        timestep_indices: mx.array,
        token_tags: mx.array,
        position_ids: mx.array,
        video_indices: mx.array,
        audio_indices: mx.array,
        text_indices: mx.array,
        modulation_cache: "ModulationCache | None" = None,
        mask: mx.array | None = None,
        refined_text: mx.array | None = None,
        rotary: tuple[mx.array, mx.array] | None = None,
        final_modulation: tuple[mx.array, mx.array] | None = None,
        attention_cache: list[mx.array | None] | None = None,
        attention_refresh: bool | tuple[bool, ...] | list[bool] = True,
    ) -> tuple[mx.array, mx.array]:
        """Predict the video and audio velocity for one packed sequence.

        Args:
            video_latents: ``(B, num_video_tokens, video_patch_dim)`` patchified rows, ordered to
                match ``video_indices`` (conditioning rows included).
            audio_latents: ``(B, num_audio_tokens, audio_latents_dim)`` ordered as ``audio_indices``.
            text_embeds: ``(B, num_text_tokens, text_dim)`` ordered as ``text_indices``.
            timestep: ``(num_timesteps,)`` the *distinct* noise levels present, unscaled in [0, 1].
            timestep_indices: ``(seq_len,)`` index into ``timestep`` for every row.
            token_tags: ``(seq_len,)`` modality per row (0 video, 1 text, 2 audio, -1 padding).
            position_ids: ``(seq_len, 3)`` the ``(t, h, w)`` rotary coordinates per row.
            modulation_cache: optional precomputed AdaLN table; when supplied the ``adaln_proj``
                weights are never read, which is what lets them be dropped at inference time.
            refined_text: optional output of :meth:`refine_text`. Text conditioning is constant
                throughout denoising, so staged inference computes it once rather than per step.
            rotary: optional precomputed ``(cos, sin)`` pair for the fixed packed position grid.
            final_modulation: optional precomputed final-layer ``(shift, scale)`` table.
            attention_cache: optional per-block PAB cache. On non-refresh steps the cached
                post-projection attention output replaces norm1/QKV/SDPA/out-projection.
            attention_refresh: recompute every entry when a bool, or apply a per-block refresh
                mask for layered PAB.

        Returns:
            ``(video_velocity, audio_velocity)`` in the row order of ``video_indices`` /
            ``audio_indices``.
        """
        seq_len = position_ids.shape[0]
        if position_ids.ndim != 2 or position_ids.shape[-1] != 3:
            raise ValueError(f"`position_ids` must be (seq_len, 3), got {position_ids.shape}.")
        if token_tags.shape != (seq_len,) or timestep_indices.shape != (seq_len,):
            raise ValueError(
                "`token_tags` and `timestep_indices` must be (seq_len,) matching `position_ids`, got "
                f"{token_tags.shape} and {timestep_indices.shape} for seq_len={seq_len}."
            )

        if rotary is None:
            rotary = self.rope(position_ids)

        # 1. Project each modality and scatter the rows into the packed buffer. The text stream
        #    sets the dtype of the packed sequence.
        video_embeds = self.video_patch_proj(video_latents.astype(param_dtype(self.video_patch_proj)))
        audio_embeds = self.audio_patch_proj(audio_latents.astype(param_dtype(self.audio_patch_proj)))
        text = self.refine_text(text_embeds) if refined_text is None else refined_text

        B = text.shape[0]
        x = mx.zeros((B, seq_len, text.shape[-1]), dtype=text.dtype)
        x[:, text_indices] = text
        x[:, video_indices] = video_embeds.astype(text.dtype)
        x[:, audio_indices] = audio_embeds.astype(text.dtype)

        # 2. One timestep embedding per distinct noise level, shared by all AdaLN projections.
        # With both caches supplied no timestep MLP work is needed inside the denoise loop.
        temb = None
        if modulation_cache is None or final_modulation is None:
            temb = self.time_embedder(timestep_embedding(timestep, self.config.timestep_input_dim))

        # 3. Row -> AdaLN table row. `maximum(tags, 0)` mirrors the reference clamp: padding rows
        #    carry tag -1 and must not index backwards. They never reach the outputs.
        adaln_indices = timestep_indices * MODALITY_NUM + mx.maximum(token_tags, 0)

        for i, block in enumerate(self.blocks):
            modulation = (
                modulation_cache.get(i) if modulation_cache is not None else block.adaln_proj(temb)
            )
            if attention_cache is None:
                x = block(x, modulation, adaln_indices, rotary, mask)
            else:
                refresh_block = attention_refresh if isinstance(attention_refresh, bool) \
                    else attention_refresh[i]
                cached = None if refresh_block else attention_cache[i]
                x, attention = block(
                    x, modulation, adaln_indices, rotary, mask,
                    cached_attention=cached, return_attention=True,
                )
                if cached is None:
                    attention_cache[i] = attention

        # 4. Both heads run over every row, then each modality's rows are selected.
        if final_modulation is None:
            x = self.final_layer.norm_out(x, temb, timestep_indices)
        else:
            shift, scale = final_modulation
            x = self.final_layer.norm(x)
            x = x * (1.0 + scale[timestep_indices]) + shift[timestep_indices]
        # The output heads are row-independent linear projections. Select each modality first so
        # the video head is not evaluated for text/audio rows and the audio head is not evaluated
        # for text/video rows. This is mathematically identical to projecting the packed sequence
        # and gathering afterwards, with substantially less output-head work on long videos.
        video_x = x[:, video_indices].astype(param_dtype(self.final_layer.video_out))
        audio_x = x[:, audio_indices].astype(param_dtype(self.final_layer.audio_out))
        return self.final_layer.video_out(video_x), self.final_layer.audio_out(audio_x)

    def refine_text(self, text_embeds: mx.array) -> mx.array:
        """Project and refine request conditioning once for reuse by every denoise step."""
        text = self.condition_proj(text_embeds.astype(param_dtype(self.condition_proj)))
        return self.token_refiner(text)
