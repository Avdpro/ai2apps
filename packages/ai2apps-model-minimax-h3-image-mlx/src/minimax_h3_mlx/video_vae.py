"""MLX port of the MiniMax-H3 video VAE (``AutoencoderKLLegacy`` / ``MiniMaxH3VideoVAE``).

A causal 3D CNN **encoder** (16x spatial, 4x temporal, 24 latent channels) paired with a
non-causal 36-layer **ViT decoder** at dim 2048. There is no CNN decoder: every latent voxel
becomes one token and a single output projection expands it straight into a
``patch_size_t x patch_size x patch_size`` pixel block, doing all the upsampling at once.

Two MLX-specific departures from the reference, both forced by the framework rather than chosen:

* **Channels-last.** MLX convolutions take ``(N, D, H, W, C)`` and weights ``(C_out, kD, kH, kW,
  C_in)``, where torch uses ``(N, C, D, H, W)`` / ``(C_out, C_in, kD, kH, kW)``. The CNN runs
  channels-last internally and transposes only at the public encode/decode boundary, so the
  pipeline still sees the reference's ``(B, C, F, H, W)``.
* **Reflect padding.** ``mx.pad`` has no reflect mode, so it is done by gather (:func:`reflect_pad`).

The module tree reproduces the *original* checkpoint names (``encoder.down.{i}.block.{j}``,
``decoder.x_embedder``, ``attn.to_qkv``, ``ff.w1``), so the released weights load without renaming.
As in the DiT, ``attn.to_qkv`` is per-head interleaved and ``ff.w1`` is a fused ``[gate; up]``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import mlx.core as mx
import mlx.nn as nn


@dataclass
class VideoVAEConfig:
    in_channels: int = 3
    out_channels: int = 3
    latent_channels: int = 24
    block_out_channels: tuple[int, ...] = (128, 256, 256, 512, 512, 1024)
    layers_per_block: int = 2
    spatial_downsample_factors: tuple[int, ...] = (2, 2, 2, 2, 1, 1)
    temporal_downsample_factors: tuple[int, ...] = (1, 2, 2, 1, 1, 1)
    norm_num_groups: int = 32
    norm_eps: float = 1e-6
    decoder_num_layers: int = 36
    decoder_num_attention_heads: int = 32
    decoder_attention_head_dim: int = 64
    decoder_num_register_tokens: int = 4
    decoder_ffn_mult: int = 4
    decoder_rope_theta: float = 100.0
    decoder_rope_dim_ratio: float = 0.75
    decoder_norm_eps: float = 1e-5
    clip_length: int = 17
    token_drop: int = 3
    latents_mean: tuple[float, ...] = field(default_factory=tuple)
    latents_std: tuple[float, ...] = field(default_factory=tuple)

    @property
    def spatial_compression_ratio(self) -> int:
        ratio = 1
        for f in self.spatial_downsample_factors:
            ratio *= f
        return ratio

    @property
    def temporal_compression_ratio(self) -> int:
        ratio = 1
        for f in self.temporal_downsample_factors:
            ratio *= f
        return ratio

    @property
    def decoder_dim(self) -> int:
        return self.decoder_num_attention_heads * self.decoder_attention_head_dim

    @property
    def patch_size(self) -> int:
        return self.spatial_compression_ratio

    @property
    def patch_size_t(self) -> int:
        return self.temporal_compression_ratio


def reflect_pad(x: mx.array, axis: int, left: int, right: int) -> mx.array:
    """Reflect padding without repeating the edge element, matching ``F.pad(mode="reflect")``.

    ``mx.pad`` supports only constant and edge, so the reflection is done by gather.
    """
    if left == 0 and right == 0:
        return x
    n = x.shape[axis]
    idx = list(range(left, 0, -1)) + list(range(n)) + list(range(n - 2, n - 2 - right, -1))
    return mx.take(x, mx.array(idx), axis=axis)


class CausalConv3d(nn.Module):
    """3D convolution over ``(N, D, H, W, C)``.

    Spatial padding is symmetric reflect; temporal padding is **causal** — ``temporal_padding``
    zero frames are prepended and nothing is appended.
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int | tuple[int, int, int] = 3,
        stride: int | tuple[int, int, int] = 1,
        spatial_padding: int = 0,
        temporal_padding: int = 0,
        bias: bool = True,
    ):
        super().__init__()
        if isinstance(kernel_size, int):
            kernel_size = (kernel_size, kernel_size, kernel_size)
        if isinstance(stride, int):
            stride = (stride, stride, stride)
        self.stride = stride
        self.spatial_padding = spatial_padding
        self.temporal_padding = temporal_padding
        # MLX weight layout: (C_out, kD, kH, kW, C_in).
        scale = 1.0 / math.sqrt(in_channels * kernel_size[0] * kernel_size[1] * kernel_size[2])
        self.weight = mx.random.uniform(-scale, scale, (out_channels, *kernel_size, in_channels))
        if bias:
            self.bias = mx.zeros((out_channels,))

    def __call__(self, x: mx.array) -> mx.array:
        if self.spatial_padding > 0:
            p = self.spatial_padding
            x = reflect_pad(x, 2, p, p)
            x = reflect_pad(x, 3, p, p)
        if self.temporal_padding > 0:
            x = mx.pad(x, ((0, 0), (self.temporal_padding, 0), (0, 0), (0, 0), (0, 0)))
        out = mx.conv3d(x, self.weight, stride=self.stride, padding=0)
        if "bias" in self:
            out = out + self.bias
        return out


class TIsolatedGroupNorm(nn.GroupNorm):
    """Group norm applied to each latent frame in isolation (``use_t_isolated_gn``).

    The temporal axis is folded into the batch axis so statistics never mix across frames.
    Subclasses ``nn.GroupNorm`` rather than wrapping it so the parameters stay at this module's own
    level and the checkpoint's ``norm1.weight`` / ``norm1.bias`` keep matching 1:1.
    """

    def __init__(self, num_groups: int, num_channels: int, eps: float = 1e-6):
        super().__init__(num_groups, num_channels, eps=eps, affine=True, pytorch_compatible=True)

    def __call__(self, x: mx.array) -> mx.array:
        b, d, h, w, c = x.shape
        folded = x.reshape(b * d, h, w, c)
        return super().__call__(folded).reshape(b, d, h, w, c)


class ResnetBlock3d(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, num_groups: int = 32, eps: float = 1e-6):
        super().__init__()
        self.norm1 = TIsolatedGroupNorm(num_groups, in_channels, eps)
        self.conv1 = CausalConv3d(in_channels, out_channels, 3, spatial_padding=1, temporal_padding=2)
        self.norm2 = TIsolatedGroupNorm(num_groups, out_channels, eps)
        self.conv2 = CausalConv3d(out_channels, out_channels, 3, spatial_padding=1, temporal_padding=2)
        if in_channels != out_channels:
            self.nin_shortcut = CausalConv3d(in_channels, out_channels, 1)

    def __call__(self, x: mx.array) -> mx.array:
        residual = x
        h = self.conv1(nn.silu(self.norm1(x)))
        h = self.conv2(nn.silu(self.norm2(h)))
        if "nin_shortcut" in self:
            residual = self.nin_shortcut(residual)
        return residual + h


class Downsample3d(nn.Module):
    """Strided 3x3x3 downsample. A spatial stride of 2 is preceded by an asymmetric bottom/right
    reflect pad of 1 (the convolution carries no spatial padding), so the output is ``ceil(n / 2)``.
    """

    def __init__(self, in_channels: int, out_channels: int, temporal_stride: int = 1, spatial_stride: int = 2):
        super().__init__()
        self.spatial_stride = spatial_stride
        self.conv = CausalConv3d(
            in_channels,
            out_channels,
            3,
            stride=(temporal_stride, spatial_stride, spatial_stride),
            spatial_padding=0,
            temporal_padding=2,
        )

    def __call__(self, x: mx.array) -> mx.array:
        if self.spatial_stride == 2:
            x = reflect_pad(x, 2, 0, 1)
            x = reflect_pad(x, 3, 0, 1)
        return self.conv(x)


class DownBlock3d(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        num_layers: int,
        temporal_factor: int,
        spatial_factor: int,
        num_groups: int = 32,
        eps: float = 1e-6,
    ):
        super().__init__()
        self.block = [
            ResnetBlock3d(in_channels if i == 0 else out_channels, out_channels, num_groups, eps)
            for i in range(num_layers)
        ]
        if temporal_factor * spatial_factor > 1:
            self.downsample = Downsample3d(out_channels, out_channels, temporal_factor, spatial_factor)

    def __call__(self, x: mx.array) -> mx.array:
        for resnet in self.block:
            x = resnet(x)
        if "downsample" in self:
            x = self.downsample(x)
        return x


class Encoder3d(nn.Module):
    """Causal 3D CNN encoder."""

    def __init__(self, config: VideoVAEConfig):
        super().__init__()
        ch = config.block_out_channels
        self.conv_in = CausalConv3d(config.in_channels, ch[0], 3, spatial_padding=1, temporal_padding=2)
        block_in = (ch[0],) + tuple(ch[:-1])
        self.down = [
            DownBlock3d(
                block_in[i],
                ch[i],
                config.layers_per_block,
                config.temporal_downsample_factors[i],
                config.spatial_downsample_factors[i],
                config.norm_num_groups,
                config.norm_eps,
            )
            for i in range(len(ch))
        ]
        self.norm_out = TIsolatedGroupNorm(config.norm_num_groups, ch[-1], config.norm_eps)
        self.conv_out = CausalConv3d(
            ch[-1], 2 * config.latent_channels, 3, spatial_padding=1, temporal_padding=2
        )

    def __call__(self, x: mx.array) -> mx.array:
        x = self.conv_in(x)
        for block in self.down:
            x = block(x)
        return self.conv_out(nn.silu(self.norm_out(x)))


class ViTRotaryPosEmbed:
    """3-axis rotary embedding for the ViT decoder.

    Coordinates are length-normalized to ``[-1, 1)`` per axis and scaled by ``2*pi``; the ``(t, h, w)``
    angle blocks are concatenated then duplicated, so the first ``rope_dim_ratio * head_dim``
    channels of every head are rotated.
    """

    def __init__(self, dim: int, theta: float = 100.0, num_axes: int = 3):
        if dim % (2 * num_axes) != 0:
            raise ValueError(f"`dim` {dim} must be divisible by `2 * num_axes` {2 * num_axes}.")
        step = 2 * num_axes / dim
        exponents = mx.array([i * step for i in range(int(math.ceil(1.0 / step)))], dtype=mx.float32)
        self.inv_freq = 1.0 / (theta**exponents)

    def __call__(self, position_ids: mx.array) -> tuple[mx.array, mx.array]:
        # position_ids: (B, N, 3) -> angles (B, N, 1, 2 * 3 * len(inv_freq))
        angles = 2.0 * math.pi * position_ids[..., None] * self.inv_freq.reshape(1, 1, 1, -1)
        b, n = angles.shape[0], angles.shape[1]
        angles = angles.reshape(b, n, -1)
        angles = mx.concatenate([angles, angles], axis=-1)[:, :, None, :]
        return mx.cos(angles), mx.sin(angles)


def _apply_vit_rotary(x: mx.array, cos: mx.array, sin: mx.array) -> mx.array:
    """``x`` is ``(B, N, heads, head_dim)``; ``cos``/``sin`` are ``(B, N, 1, rotary_dim)``."""
    rotary_dim = cos.shape[-1]
    x_rot, x_pass = x[..., :rotary_dim], x[..., rotary_dim:]
    half = rotary_dim // 2
    first, second = x_rot[..., :half], x_rot[..., half:]
    rotated = mx.concatenate([-second, first], axis=-1)
    out = x_rot * cos.astype(x.dtype) + rotated * sin.astype(x.dtype)
    if x_pass.shape[-1] == 0:
        return out
    return mx.concatenate([out, x_pass], axis=-1)


class ViTAttention(nn.Module):
    """Full self-attention with unaffine Q/K RMSNorm, computed in float32 as the reference does."""

    def __init__(self, dim: int, heads: int, dim_head: int, eps: float = 1e-5, bias: bool = True):
        super().__init__()
        self.heads = heads
        self.dim_head = dim_head
        self.eps = eps
        self.scale = dim_head**-0.5
        inner = heads * dim_head
        self.to_qkv = nn.Linear(dim, 3 * inner, bias=bias)
        self.to_out = nn.Linear(inner, dim, bias=bias)

    def _rms_norm_f32(self, x: mx.array) -> mx.array:
        x32 = x.astype(mx.float32)
        normed = x32 * mx.rsqrt(mx.mean(x32 * x32, axis=-1, keepdims=True) + self.eps)
        return normed.astype(x.dtype)

    def __call__(self, x: mx.array, rotary: tuple[mx.array, mx.array] | None = None) -> mx.array:
        b, n, _ = x.shape
        # Per-head interleaved, as in the DiT: (..., heads, 3, head_dim).
        qkv = self.to_qkv(x).reshape(b, n, self.heads, 3, self.dim_head)
        q, k, v = qkv[:, :, :, 0], qkv[:, :, :, 1], qkv[:, :, :, 2]

        q = self._rms_norm_f32(q)
        k = self._rms_norm_f32(k)
        if rotary is not None:
            q = _apply_vit_rotary(q, *rotary)
            k = _apply_vit_rotary(k, *rotary)

        q = q.transpose(0, 2, 1, 3)
        k = k.transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)
        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale)
        out = out.transpose(0, 2, 1, 3).reshape(b, n, self.heads * self.dim_head)
        return self.to_out(out)


class ViTFeedForward(nn.Module):
    """Gated SwiGLU FFN. ``w1`` is the fused ``[gate; up]`` projection."""

    def __init__(self, dim: int, mult: int = 4, bias: bool = True):
        super().__init__()
        inner = dim * mult
        self.w1 = nn.Linear(dim, 2 * inner, bias=bias)
        self.w2 = nn.Linear(inner, dim, bias=bias)
        self._inner = inner

    def __call__(self, x: mx.array) -> mx.array:
        fused = self.w1(x)
        gate, up = fused[..., : self._inner], fused[..., self._inner :]
        return self.w2(nn.silu(gate) * up)


class ViTBlock(nn.Module):
    """Pre-norm block with learned per-channel output scales (``scale1`` / ``scale2``, init 0).

    Both norms run in float32 regardless of the compute dtype, as in the reference.
    """

    def __init__(self, dim: int, heads: int, dim_head: int, ffn_mult: int = 4, eps: float = 1e-5):
        super().__init__()
        self.norm1 = nn.RMSNorm(dim, eps=eps)
        self.attn = ViTAttention(dim, heads, dim_head, eps=eps, bias=True)
        self.scale1 = mx.zeros((dim,))
        self.norm2 = nn.RMSNorm(dim, eps=eps)
        self.ff = ViTFeedForward(dim, ffn_mult, bias=True)
        self.scale2 = mx.zeros((dim,))

    def __call__(self, x: mx.array, rotary: tuple[mx.array, mx.array] | None = None) -> mx.array:
        h = self.norm1(x.astype(mx.float32)).astype(x.dtype)
        x = x + self.attn(h, rotary) * self.scale1
        h = self.norm2(x.astype(mx.float32)).astype(x.dtype)
        return x + self.ff(h) * self.scale2


class ViTDecoder3d(nn.Module):
    """Non-causal ViT decoder.

    Every latent voxel becomes one token; ``num_register_tokens`` learned register tokens plus a
    single all-zero token are appended (all at position 0), attended over with full self-attention,
    and dropped again before the output projection expands each token into a
    ``patch_size_t x patch_size x patch_size`` pixel block.
    """

    def __init__(self, config: VideoVAEConfig, *, rope_axes: int = 3):
        super().__init__()
        dim = config.decoder_dim
        self.patch_size = config.patch_size
        self.patch_size_t = config.patch_size_t
        self.out_channels = config.out_channels
        self.num_register_tokens = config.decoder_num_register_tokens
        self.rope_axes = rope_axes

        self.rope = ViTRotaryPosEmbed(
            int(config.decoder_attention_head_dim * config.decoder_rope_dim_ratio),
            theta=config.decoder_rope_theta,
            num_axes=rope_axes,
        )
        self.x_embedder = nn.Linear(config.latent_channels, dim)
        self.register_tokens = mx.zeros((1, config.decoder_num_register_tokens, dim))
        self.transformer_blocks = [
            ViTBlock(
                dim,
                config.decoder_num_attention_heads,
                config.decoder_attention_head_dim,
                config.decoder_ffn_mult,
                config.decoder_norm_eps,
            )
            for _ in range(config.decoder_num_layers)
        ]
        self.norm_out = nn.LayerNorm(dim, eps=config.decoder_norm_eps, affine=True)
        self.proj_out = nn.Linear(
            dim, config.out_channels * config.patch_size_t * config.patch_size * config.patch_size
        )

    def __call__(self, x: mx.array) -> mx.array:
        """``x`` is ``(B, D, H, W, C)``; returns ``(B, D*pt, H*p, W*p, out_channels)``."""
        b, d, h, w, c = x.shape
        tokens = self.x_embedder(x.reshape(b, d * h * w, c))
        num_patches = tokens.shape[1]

        registers = mx.broadcast_to(self.register_tokens, (b, self.num_register_tokens, tokens.shape[-1]))
        cls_token = mx.zeros((b, 1, tokens.shape[-1]), dtype=tokens.dtype)
        tokens = mx.concatenate([tokens, registers.astype(tokens.dtype), cls_token], axis=1)

        grids = [2.0 * ((mx.arange(size, dtype=mx.float32) + 0.5) / size) - 1.0 for size in (d, h, w)]
        tt = mx.broadcast_to(grids[0].reshape(d, 1, 1), (d, h, w))
        hh = mx.broadcast_to(grids[1].reshape(1, h, 1), (d, h, w))
        ww = mx.broadcast_to(grids[2].reshape(1, 1, w), (d, h, w))
        position_ids = mx.stack([tt, hh, ww], axis=-1).reshape(1, d * h * w, 3)
        position_ids = mx.broadcast_to(position_ids, (b, d * h * w, 3))
        suffix = mx.zeros((b, self.num_register_tokens + 1, 3), dtype=mx.float32)
        position_ids = mx.concatenate([position_ids, suffix], axis=1)
        rotary = self.rope(position_ids[..., -self.rope_axes:])

        for block in self.transformer_blocks:
            tokens = block(tokens, rotary)

        tokens = self.proj_out(self.norm_out(tokens))[:, :num_patches, :]

        p, pt = self.patch_size, self.patch_size_t
        out = tokens.reshape(b, d, h, w, self.out_channels, pt, p, p)
        out = out.transpose(0, 1, 5, 2, 6, 3, 7, 4)
        return out.reshape(b, d * pt, h * p, w * p, self.out_channels)


class SpatialVAETiling:
    """Aligned tile layout and blending shared by the H3 VAEs."""

    # -- tiling -----------------------------------------------------------------------------

    def _split_tiles(self, length: int, tile_size: int, min_overlap: int):
        """Lay ``tile_size``-wide tiles over ``length`` pixels.

        The tile count is the smallest whose union covers ``length`` while keeping every overlap at
        least ``min_overlap``; the slack is distributed round-robin over the overlaps in whole
        ``spatial_compression_ratio`` steps so every boundary stays latent-aligned.
        """
        if tile_size >= length:
            return [0], [length], []
        ratio = self.config.spatial_compression_ratio
        num_tiles = math.ceil(length / tile_size)
        while tile_size * num_tiles - min_overlap * (num_tiles - 1) - length < 0:
            num_tiles += 1
        overlaps = [min_overlap] * (num_tiles - 1)
        remaining = tile_size * num_tiles - sum(overlaps) - length
        for i in range(remaining // ratio):
            overlaps[i % (num_tiles - 1)] += ratio
        starts = [0]
        for i in range(num_tiles - 1):
            starts.append(starts[-1] + tile_size - overlaps[i])
        return starts, [tile_size] * num_tiles, overlaps

    @staticmethod
    def _blend(a: mx.array, b: mx.array, blend_extent: int, axis: int) -> mx.array:
        blend_extent = min(a.shape[axis], b.shape[axis], blend_extent)
        if blend_extent <= 0:
            return b
        pos = mx.arange(blend_extent, dtype=mx.float32)
        shape = [1] * a.ndim
        shape[axis] = blend_extent
        wa = (1.0 - pos / blend_extent).reshape(shape).astype(b.dtype)
        wb = (pos / blend_extent).reshape(shape).astype(b.dtype)

        a_tail = mx.take(a, mx.arange(a.shape[axis] - blend_extent, a.shape[axis]), axis=axis)
        b_head = mx.take(b, mx.arange(blend_extent), axis=axis)
        blended = a_tail * wa + b_head * wb
        if blend_extent == b.shape[axis]:
            return blended
        rest = mx.take(b, mx.arange(blend_extent, b.shape[axis]), axis=axis)
        return mx.concatenate([blended, rest], axis=axis)

    def _stitch_tiles(self, tiles, height_overlaps, width_overlaps, h_axis: int, w_axis: int):
        rows = []
        for i, row in enumerate(tiles):
            out_row = []
            for j, tile in enumerate(row):
                if i > 0:
                    tile = self._blend(tiles[i - 1][j], tile, height_overlaps[i - 1], axis=h_axis)
                if j > 0:
                    tile = self._blend(row[j - 1], tile, width_overlaps[j - 1], axis=w_axis)
                if i < len(tiles) - 1:
                    tile = mx.take(tile, mx.arange(tile.shape[h_axis] - height_overlaps[i]), axis=h_axis)
                if j < len(row) - 1:
                    tile = mx.take(tile, mx.arange(tile.shape[w_axis] - width_overlaps[j]), axis=w_axis)
                out_row.append(tile)
            rows.append(mx.concatenate(out_row, axis=w_axis))
        return mx.concatenate(rows, axis=h_axis)

class VideoVAE(nn.Module, SpatialVAETiling):
    """The MiniMax-H3 video autoencoder: causal CNN encoder + ViT decoder, tiled and chunked.

    The public :meth:`encode` / :meth:`decode` take and return the reference's ``(B, C, F, H, W)``;
    everything internal is channels-last.
    """

    def __init__(self, config: VideoVAEConfig):
        super().__init__()
        self.config = config
        self.encoder = Encoder3d(config)
        self.decoder = ViTDecoder3d(config)
        self.quant_conv = CausalConv3d(2 * config.latent_channels, 2 * config.latent_channels, 1)
        self.post_quant_conv = CausalConv3d(config.latent_channels, config.latent_channels, 1)

        ratio_t = config.temporal_compression_ratio
        self.frame_pre_padding = (-config.clip_length) % ratio_t
        self.tokens_chunk_size = math.ceil(config.clip_length / ratio_t)
        self.token_overlap = (-config.token_drop) % self.tokens_chunk_size
        self.frame_overlap = max(self.token_overlap * ratio_t - self.frame_pre_padding, 0)

        self.use_tiling = True
        self.tile_sample_min_height = 256
        self.tile_sample_min_width = 256
        self.tile_sample_min_overlap_height = 64
        self.tile_sample_min_overlap_width = 64
        # MLX builds lazy graphs.  Evaluating each decoder tile as soon as it is produced can
        # reduce the size of the pending graph and lets the Metal allocator recycle temporary
        # buffers before the next tile.  Keep this opt-in because the fastest choice is sensitive
        # to the GPU generation and tile geometry.
        self.materialize_decoder_tiles = False
        # Equal-sized spatial tiles can be folded into the batch dimension and decoded by one
        # graph. This cuts Python/kernel-dispatch overhead and gives wide Apple GPUs more parallel
        # work, at the cost of a larger instantaneous decoder working set.
        self.batch_decoder_tiles = False

    # -- clip-level encode / decode ---------------------------------------------------------

    def _encode_clip(self, x: mx.array) -> mx.array:
        """``x`` is channels-last ``(B, D, H, W, C)``."""
        if not self.use_tiling:
            return self.quant_conv(self.encoder(x))
        h, w = x.shape[2], x.shape[3]
        y_idx, y_len, y_ov = self._split_tiles(h, self.tile_sample_min_height, self.tile_sample_min_overlap_height)
        x_idx, x_len, x_ov = self._split_tiles(w, self.tile_sample_min_width, self.tile_sample_min_overlap_width)

        rows = []
        for i_pos, i_len in zip(y_idx, y_len):
            row = []
            for j_pos, j_len in zip(x_idx, x_len):
                tile = x[:, :, i_pos : i_pos + i_len, j_pos : j_pos + j_len, :]
                row.append(self.quant_conv(self.encoder(tile)))
            rows.append(row)

        ratio = self.config.spatial_compression_ratio
        return self._stitch_tiles(rows, [o // ratio for o in y_ov], [o // ratio for o in x_ov], 2, 3)

    def _decode_clip(self, z: mx.array) -> mx.array:
        if not self.use_tiling:
            return self.decoder(self.post_quant_conv(z))
        ratio = self.config.spatial_compression_ratio
        h, w = z.shape[2] * ratio, z.shape[3] * ratio
        y_idx, y_len, y_ov = self._split_tiles(h, self.tile_sample_min_height, self.tile_sample_min_overlap_height)
        x_idx, x_len, x_ov = self._split_tiles(w, self.tile_sample_min_width, self.tile_sample_min_overlap_width)

        latent_tiles = []
        for i_pos, i_len in zip(y_idx, y_len):
            for j_pos, j_len in zip(x_idx, x_len):
                latent_tiles.append(z[
                    :,
                    :,
                    i_pos // ratio : i_pos // ratio + i_len // ratio,
                    j_pos // ratio : j_pos // ratio + j_len // ratio,
                    :,
                ])

        if self.batch_decoder_tiles and len(latent_tiles) > 1:
            batch_size = z.shape[0]
            decoded_batch = self.decoder(
                self.post_quant_conv(mx.concatenate(latent_tiles, axis=0)))
            if self.materialize_decoder_tiles:
                mx.eval(decoded_batch)
            decoded_tiles = [
                decoded_batch[i * batch_size : (i + 1) * batch_size]
                for i in range(len(latent_tiles))
            ]
        else:
            decoded_tiles = []
            for tile in latent_tiles:
                decoded_tile = self.decoder(self.post_quant_conv(tile))
                if self.materialize_decoder_tiles:
                    mx.eval(decoded_tile)
                decoded_tiles.append(decoded_tile)

        columns = len(x_idx)
        rows = [decoded_tiles[i : i + columns] for i in range(0, len(decoded_tiles), columns)]
        return self._stitch_tiles(rows, y_ov, x_ov, 2, 3)

    # -- public API (channels-first, matching the reference) --------------------------------

    def encode(self, x: mx.array) -> mx.array:
        """Encode ``(B, C, F, H, W)`` pixels into ``(B, 2*latent_channels, F', H', W')`` moments.

        The video is encoded in ``clip_length``-frame chunks and the ``token_drop`` trailing latent
        frames are dropped.
        """
        clip_length = self.config.clip_length
        x = x.transpose(0, 2, 3, 4, 1)  # -> (B, D, H, W, C)
        num_frames = x.shape[1]
        if num_frames % clip_length != 0:
            pad = (-num_frames) % clip_length
            tail = mx.broadcast_to(x[:, -1:], (x.shape[0], pad, *x.shape[2:]))
            x = mx.concatenate([x, tail], axis=1)

        moments = mx.concatenate(
            [
                self._encode_clip(x[:, i * clip_length : (i + 1) * clip_length])
                for i in range(x.shape[1] // clip_length)
            ],
            axis=1,
        )
        if self.config.token_drop > 0:
            moments = moments[:, : -self.config.token_drop]
        return moments.transpose(0, 4, 1, 2, 3)

    def decode(self, z: mx.array) -> mx.array:
        """Decode ``(B, latent_channels, F, H, W)`` latents into ``(B, C, F', H', W')`` pixels.

        Mirrors the chunking ``encode`` applied: ``token_drop`` removed the tail of every encoded
        chunk, so consecutive decoded chunks overlap by ``frame_overlap`` pixel frames and are
        linearly cross-faded. Latent frames are repeated at the end when the length is not a whole
        number of chunks, and the extra pixel frames are cut off again.
        """
        z = z.transpose(0, 2, 3, 4, 1)  # -> (B, D, H, W, C)
        chunk_tokens = self.tokens_chunk_size
        token_drop = self.config.token_drop
        ratio_t = self.config.temporal_compression_ratio
        chunk_num_frames = chunk_tokens * ratio_t

        num_tokens = z.shape[1] + token_drop
        pad_tokens = (-num_tokens) % chunk_tokens
        num_chunks = (num_tokens + pad_tokens) // chunk_tokens - int(token_drop > 0)
        if num_chunks < 1:
            # `token_drop` consumes a whole chunk's worth of lead-in, so the shortest decodable
            # latent is one full chunk beyond it. The reference has the same floor; it just fails
            # with an empty concatenate instead of saying so.
            minimum = 2 * chunk_tokens - token_drop
            raise ValueError(
                f"Too few latent frames to decode: got {z.shape[1]}, need at least {minimum} "
                f"(chunk {chunk_tokens} latent frames, token_drop {token_drop})."
            )
        if pad_tokens > 0:
            tail = mx.broadcast_to(z[:, -1:], (z.shape[0], pad_tokens, *z.shape[2:]))
            z = mx.concatenate([z, tail], axis=1)

        decoded, overlap = [], None
        for i in range(num_chunks):
            start = i * chunk_tokens
            clip = self._decode_clip(z[:, start : start + chunk_tokens + self.token_overlap])
            for j in range(int(token_drop > 0) + 1):
                frame_start = j * chunk_num_frames
                chunk = clip[:, frame_start : frame_start + chunk_num_frames]
                chunk = chunk[:, self.frame_pre_padding :]
                if j == 0:
                    if overlap is not None:
                        chunk = self._blend(overlap, chunk, self.frame_overlap, axis=1)
                    decoded.append(chunk)
                else:
                    overlap = chunk
        if overlap is not None:
            decoded.append(overlap)

        out = mx.concatenate(decoded, axis=1)

        # The repeated latent frames produced trailing pixel frames that were never requested. A
        # chunk's last latent frame only covers `clip_length % ratio_t` pixel frames; others cover
        # `ratio_t`.
        if pad_tokens > 0:
            intra_tail = self.config.clip_length % ratio_t
            before_pad = z.shape[1] - pad_tokens
            pad_frames = sum(
                intra_tail if intra_tail and (before_pad + k) % chunk_tokens == 0 else ratio_t
                for k in range(pad_tokens)
            )
            out = out[:, :-pad_frames]
        return out.transpose(0, 4, 1, 2, 3)
