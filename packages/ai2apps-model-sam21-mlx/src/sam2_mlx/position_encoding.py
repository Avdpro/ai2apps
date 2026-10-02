"""Position encoding utilities for SAM2, ported to MLX."""

import math
from typing import Optional, Tuple

import mlx.core as mx
import mlx.nn as nn


class PositionEmbeddingSine(nn.Module):
    """2D sine/cosine position embedding for FPN neck and memory encoder."""

    def __init__(
        self,
        num_pos_feats: int,
        temperature: int = 10000,
        normalize: bool = True,
        scale: Optional[float] = None,
    ):
        super().__init__()
        assert num_pos_feats % 2 == 0
        self.num_pos_feats = num_pos_feats // 2
        self.temperature = temperature
        self.normalize = normalize
        self.scale = scale if scale is not None else 2 * math.pi
        self._cache = {}

    def __call__(self, x: mx.array) -> mx.array:
        """x: [B, C, H, W] channels-first. Returns [B, C_pos, H, W]."""
        _, _, H, W = x.shape
        cache_key = (H, W)
        if cache_key in self._cache:
            pos = self._cache[cache_key]
            return mx.broadcast_to(pos[None], (x.shape[0], *pos.shape))

        y_embed = mx.arange(1, H + 1, dtype=mx.float32).reshape(1, -1, 1)
        y_embed = mx.broadcast_to(y_embed, (1, H, W))
        x_embed = mx.arange(1, W + 1, dtype=mx.float32).reshape(1, 1, -1)
        x_embed = mx.broadcast_to(x_embed, (1, H, W))

        if self.normalize:
            eps = 1e-6
            y_embed = y_embed / (y_embed[:, -1:, :] + eps) * self.scale
            x_embed = x_embed / (x_embed[:, :, -1:] + eps) * self.scale

        dim_t = mx.arange(self.num_pos_feats, dtype=mx.float32)
        dim_t = self.temperature ** (2 * (dim_t // 2) / self.num_pos_feats)

        pos_x = x_embed[:, :, :, None] / dim_t
        pos_y = y_embed[:, :, :, None] / dim_t

        pos_x = mx.stack(
            [mx.sin(pos_x[:, :, :, 0::2]), mx.cos(pos_x[:, :, :, 1::2])], axis=4
        ).reshape(1, H, W, -1)
        pos_y = mx.stack(
            [mx.sin(pos_y[:, :, :, 0::2]), mx.cos(pos_y[:, :, :, 1::2])], axis=4
        ).reshape(1, H, W, -1)

        pos = mx.concatenate([pos_y, pos_x], axis=3).transpose(0, 3, 1, 2)
        self._cache[cache_key] = pos[0]
        return mx.broadcast_to(pos, (x.shape[0], *pos.shape[1:]))


class PositionEmbeddingRandom(nn.Module):
    """Positional encoding using random spatial frequencies (for prompt encoder)."""

    def __init__(self, num_pos_feats: int = 64, scale: Optional[float] = None):
        super().__init__()
        if scale is None or scale <= 0.0:
            scale = 1.0
        self.gaussian_matrix = scale * mx.random.normal((2, num_pos_feats))

    def _pe_encoding(self, coords: mx.array) -> mx.array:
        """Encode normalized [0,1] coords. coords: [..., 2]."""
        coords = 2 * coords - 1
        coords = coords @ self.gaussian_matrix
        coords = 2 * math.pi * coords
        return mx.concatenate([mx.sin(coords), mx.cos(coords)], axis=-1)

    def forward_with_coords(
        self, coords_input: mx.array, image_size: Tuple[int, int]
    ) -> mx.array:
        """Encode pixel-space coords. coords: [B, N, 2]."""
        coords = coords_input.astype(mx.float32)
        coords = coords.at[:, :, 0].divide(image_size[1])
        coords = coords.at[:, :, 1].divide(image_size[0])
        return self._pe_encoding(coords)

    def __call__(self, size: Tuple[int, int]) -> mx.array:
        """Generate PE grid. Returns [C, H, W]."""
        H, W = size
        y_embed = mx.arange(1, H + 1, dtype=mx.float32).reshape(H, 1) - 0.5
        x_embed = mx.arange(1, W + 1, dtype=mx.float32).reshape(1, W) - 0.5
        y_embed = y_embed / H
        x_embed = x_embed / W
        grid = mx.stack(
            [mx.broadcast_to(x_embed, (H, W)), mx.broadcast_to(y_embed, (H, W))],
            axis=-1,
        )
        pe = self._pe_encoding(grid)
        return pe.transpose(2, 0, 1)


def _get_1d_sine_pe(pos_inds: mx.array, dim: int, temperature: float = 10000.0) -> mx.array:
    """1D sine positional embedding (Vaswani et al.).

    Used in sam2.1 to embed temporal distances between frames for the
    obj_ptr cross-attention. `pos_inds: [N]`, returns `[N, dim]`.
    """
    pe_dim = dim // 2
    dim_t = mx.arange(pe_dim, dtype=mx.float32)
    dim_t = temperature ** (2 * (dim_t // 2) / pe_dim)
    pos_embed = pos_inds.reshape(-1, 1) / dim_t
    return mx.concatenate([mx.sin(pos_embed), mx.cos(pos_embed)], axis=-1)


# ── RoPE utilities for memory attention ──
#
# PT's `compute_axial_cis(dim=head_dim, end_x, end_y)` returns a COMPLEX
# tensor of shape `(end_x*end_y, dim/2)`. RoPE is then applied as
# elementwise complex multiplication: each pair (xq_{2i}, xq_{2i+1}) is
# treated as a complex number xq[i] = xq_{2i} + i*xq_{2i+1} and rotated by
# the corresponding `freqs_cis[L, i]`. We mirror PT exactly using MLX's
# native complex64 dtype.

def compute_axial_cis(dim: int, end_x: int, end_y: int, theta: float = 10000.0) -> mx.array:
    """2D axial RoPE freqs_cis as COMPLEX `(end_x*end_y, dim/2)`.

    `dim` here is the per-head feature dimension that RoPE is applied to
    (NOT half of it). Matches PT's `sam2.modeling.position_encoding.compute_axial_cis`.
    """
    quarter = dim // 4
    base = mx.arange(0, dim, 4)[:quarter].astype(mx.float32) / dim
    freqs_x = 1.0 / (theta ** base)  # (dim/4,)
    freqs_y = 1.0 / (theta ** base)

    L = end_x * end_y
    t = mx.arange(L, dtype=mx.float32)
    t_x = t % end_x
    t_y = t // end_x

    fx = mx.outer(t_x, freqs_x)  # (L, dim/4)
    fy = mx.outer(t_y, freqs_y)  # (L, dim/4)

    cis_x = (mx.cos(fx) + 1j * mx.sin(fx)).astype(mx.complex64)  # (L, dim/4)
    cis_y = (mx.cos(fy) + 1j * mx.sin(fy)).astype(mx.complex64)
    return mx.concatenate([cis_x, cis_y], axis=-1)  # (L, dim/2)


def _view_as_complex(x: mx.array) -> mx.array:
    """[..., D] real → [..., D/2] complex (last dim halved, paired as Re/Im)."""
    new = list(x.shape[:-1]) + [x.shape[-1] // 2, 2]
    parts = mx.reshape(x, new)
    return (parts[..., 0] + 1j * parts[..., 1]).astype(mx.complex64)


def _view_as_real_flat(z: mx.array) -> mx.array:
    """[..., D/2] complex → [..., D] real (interleaved Re,Im pairs)."""
    re = mx.real(z)
    im = mx.imag(z)
    stacked = mx.stack([re, im], axis=-1)  # [..., D/2, 2]
    return stacked.reshape(*stacked.shape[:-2], -1)


def apply_rotary_enc(
    xq: mx.array,
    xk: mx.array,
    freqs_cis: mx.array,
    repeat_freqs_k: bool = False,
):
    """Apply 2D-axial RoPE to Q (and K, optionally tiled).

    Args:
        xq: [..., L_q, D]   — leading dims unconstrained (e.g. [B, N, L, D])
        xk: [..., L_k, D]   — pass an empty array (shape last==0) to skip K
        freqs_cis: complex `(L_q, D/2)` from `compute_axial_cis`
        repeat_freqs_k: if True, tile freqs along seq dim to match L_k
    """
    xq_c = _view_as_complex(xq)              # [..., L_q, D/2] complex
    L_q = xq_c.shape[-2]
    # Reshape freqs_cis to broadcast over leading dims of xq.
    # freqs_cis is (L_q, D/2). xq_c last two dims are also (L_q, D/2).
    # Insert leading 1s.
    ndim = xq_c.ndim
    f = freqs_cis.reshape((1,) * (ndim - 2) + freqs_cis.shape)
    xq_out = _view_as_real_flat(xq_c * f)

    if xk.shape[-1] == 0:
        return xq_out.astype(xq.dtype), xk

    xk_c = _view_as_complex(xk)
    L_k = xk_c.shape[-2]
    if repeat_freqs_k:
        r = L_k // L_q
        # Tile along seq dim to (L_q*r, D/2) = (L_k, D/2)
        f_k = mx.tile(freqs_cis, (r, 1))
    else:
        f_k = freqs_cis[:L_k]
    f_k = f_k.reshape((1,) * (xk_c.ndim - 2) + f_k.shape)
    xk_out = _view_as_real_flat(xk_c * f_k)
    return xq_out.astype(xq.dtype), xk_out.astype(xk.dtype)
