"""Hiera backbone for SAM2, ported to MLX.

Reference: https://arxiv.org/abs/2306.00989
Ported from ref_only_code/MiniMax-Remover/gradio_demo/sam2/modeling/backbones/hieradet.py

All internal tensors use channels-last [B, H, W, C] to match MLX 0.31+ convention.
"""

import math
from functools import partial
from typing import List, Optional, Tuple, Union

import mlx.core as mx
import mlx.nn as nn

from .sam2_utils import DropPath, MLP, window_partition, window_unpartition


def _do_pool(x, pool, norm=None):
    """Apply 2D pooling. x: [B, H, W, C] → pool → [B, H', W', C]."""
    if pool is None:
        return x
    # MLX conv ops use channels-last, MaxPool2d uses channels-last [N, H, W, C]
    x = pool(x)
    if norm:
        x = norm(x)
    return x


def _bicubic_resize(x: mx.array, size: Tuple[int, int]) -> mx.array:
    """Bicubic resize via OpenCV. `size` is (h, w), matching PyTorch's
    F.interpolate(..., size=(h, w)). MLX has no bicubic op.

    CAREFUL: cv2.resize expects dsize=(width, height). Passing (h, w) there
    silently swaps axes when h != w. For Hiera pos_embed (7→64) the shapes
    are square so the swap wasn't visible, but semantically the call must
    be (w, h).
    """
    import cv2
    import numpy as np

    h, w = size
    arr = np.array(x)
    if arr.ndim == 4:
        B, C, H, W = arr.shape
        resized = []
        for i in range(B):
            ch_resized = []
            for j in range(C):
                ch = cv2.resize(arr[i, j], (w, h), interpolation=cv2.INTER_CUBIC)
                ch_resized.append(ch)
            resized.append(np.stack(ch_resized))
        return mx.array(np.stack(resized))
    return mx.array(cv2.resize(arr, (w, h), interpolation=cv2.INTER_CUBIC))


class MultiScaleAttention(nn.Module):
    def __init__(self, dim: int, dim_out: int, num_heads: int, q_pool=None):
        super().__init__()
        self.dim = dim
        self.dim_out = dim_out
        self.num_heads = num_heads
        head_dim = dim_out // num_heads
        self.scale = head_dim**-0.5
        self.q_pool = q_pool
        self.qkv = nn.Linear(dim, dim_out * 3)
        self.proj = nn.Linear(dim_out, dim_out)

    def __call__(self, x: mx.array) -> mx.array:
        B, H, W, C = x.shape
        n, hd = self.num_heads, self.dim_out // self.num_heads

        qkv = self.qkv(x)  # [B, H, W, dim_out*3]
        qkv = qkv.reshape(B, H * W, 3, n, hd)
        q = qkv[:, :, 0]
        k = qkv[:, :, 1]
        v = qkv[:, :, 2]

        # Q pooling
        if self.q_pool is not None:
            q = q.reshape(B, H, W, n * hd)
            q = _do_pool(q, self.q_pool)
            H, W = q.shape[1:3]
            q = q.reshape(B, H * W, n, hd)

        # SDPA: [B, N, L, D]
        q_t = q.transpose(0, 2, 1, 3)
        k_t = k.transpose(0, 2, 1, 3)
        v_t = v.transpose(0, 2, 1, 3)
        out = mx.fast.scaled_dot_product_attention(q_t, k_t, v_t, scale=self.scale)
        out = out.transpose(0, 2, 1, 3).reshape(B, H, W, -1)
        return self.proj(out)


class MultiScaleBlock(nn.Module):
    def __init__(
        self,
        dim: int,
        dim_out: int,
        num_heads: int,
        mlp_ratio: float = 4.0,
        drop_path: float = 0.0,
        q_stride: Optional[Tuple[int, int]] = None,
        window_size: int = 0,
    ):
        super().__init__()
        self.dim = dim
        self.dim_out = dim_out
        self.window_size = window_size

        self.norm1 = nn.LayerNorm(dim, eps=1e-6)

        self.pool = None
        self.q_stride = q_stride
        if self.q_stride:
            self.pool = nn.MaxPool2d(
                kernel_size=q_stride, stride=q_stride
            )

        self.attn = MultiScaleAttention(dim, dim_out, num_heads, q_pool=self.pool)
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()

        self.norm2 = nn.LayerNorm(dim_out, eps=1e-6)
        self.mlp = MLP(
            dim_out,
            int(dim_out * mlp_ratio),
            dim_out,
            num_layers=2,
            activation=nn.GELU,
        )

        if dim != dim_out:
            self.proj = nn.Linear(dim, dim_out)

    def __call__(self, x: mx.array) -> mx.array:
        shortcut = x
        x = self.norm1(x)

        # Skip connection projection
        if self.dim != self.dim_out:
            shortcut = self.proj(x)
            if self.pool:
                shortcut = _do_pool(shortcut, self.pool)

        # Window partition
        window_size = self.window_size
        original_hw = None
        if window_size > 0:
            H, W = x.shape[1], x.shape[2]
            original_hw = (H, W)
            x, pad_hw = window_partition(x, window_size)

        # Attention
        x = self.attn(x)

        # Update HW/pad_hw after Q pooling changes spatial dims
        if self.q_stride:
            window_size = self.window_size // self.q_stride[0]
            H, W = shortcut.shape[1:3]
            pad_h = (window_size - H % window_size) % window_size
            pad_w = (window_size - W % window_size) % window_size
            pad_hw = (H + pad_h, W + pad_w)

        # Reverse window partition
        if self.window_size > 0 and window_size > 0:
            if self.q_stride:
                # HW comes from shortcut after Q pooling
                x = window_unpartition(x, window_size, pad_hw, shortcut.shape[1:3])
            else:
                x = window_unpartition(x, window_size, pad_hw, original_hw)

        x = shortcut + self.drop_path(x)
        x = x + self.drop_path(self.mlp(self.norm2(x)))
        return x


class Hiera(nn.Module):
    """Hiera hierarchical vision transformer backbone."""

    def __init__(
        self,
        embed_dim: int = 144,
        num_heads: int = 2,
        drop_path_rate: float = 0.0,
        q_pool: int = 3,
        q_stride: Tuple[int, int] = (2, 2),
        stages: Tuple[int, ...] = (2, 6, 36, 4),
        dim_mul: float = 2.0,
        head_mul: float = 2.0,
        window_pos_embed_bkg_spatial_size: Tuple[int, int] = (7, 7),
        window_spec: Tuple[int, ...] = (8, 4, 16, 8),
        global_att_blocks: Tuple[int, ...] = (23, 33, 43),
        return_interm_layers: bool = True,
    ):
        super().__init__()
        assert len(stages) == len(window_spec)
        self.window_spec = window_spec
        self.q_stride = q_stride
        self.return_interm_layers = return_interm_layers

        depth = sum(stages)
        self.stage_ends = [sum(stages[:i]) - 1 for i in range(1, len(stages) + 1)]
        self.q_pool_blocks = [x + 1 for x in self.stage_ends[:-1]][:q_pool]
        self.global_att_blocks = global_att_blocks

        self.window_pos_embed_bkg_spatial_size = window_pos_embed_bkg_spatial_size

        # Patch embedding: Conv2d(3→144, k=7, s=4, p=3) with channels-last
        self.patch_embed = nn.Conv2d(3, embed_dim, kernel_size=7, stride=4, padding=3)

        # Positional embeddings (stored as parameters)
        self.pos_embed = mx.zeros(
            (1, embed_dim, *window_pos_embed_bkg_spatial_size)
        )
        self.pos_embed_window = mx.zeros(
            (1, embed_dim, window_spec[0], window_spec[0])
        )

        # Stochastic depth
        dpr = [float(x) for x in mx.linspace(0, drop_path_rate, depth)]

        cur_stage = 1
        self.blocks = []
        for i in range(depth):
            dim_out = embed_dim
            window_size = self.window_spec[cur_stage - 1]
            if global_att_blocks is not None:
                window_size = 0 if i in global_att_blocks else window_size
            if i - 1 in self.stage_ends:
                dim_out = int(embed_dim * dim_mul)
                num_heads = int(num_heads * head_mul)
                cur_stage += 1

            block = MultiScaleBlock(
                dim=embed_dim,
                dim_out=dim_out,
                num_heads=num_heads,
                drop_path=dpr[i],
                q_stride=self.q_stride if i in self.q_pool_blocks else None,
                window_size=window_size,
            )
            embed_dim = dim_out
            self.blocks.append(block)

        self.channel_list = (
            [self.blocks[i].dim_out for i in self.stage_ends[::-1]]
            if return_interm_layers
            else [self.blocks[-1].dim_out]
        )

    def _get_pos_embed(self, hw: Tuple[int, int]) -> mx.array:
        h, w = hw
        pos_embed = _bicubic_resize(self.pos_embed, (h, w))
        window_embed = self.pos_embed_window
        # Tile window embed to match spatial size
        rep_h = (pos_embed.shape[2] + window_embed.shape[2] - 1) // window_embed.shape[2]
        rep_w = (pos_embed.shape[3] + window_embed.shape[3] - 1) // window_embed.shape[3]
        window_tiled = mx.tile(window_embed, (1, 1, rep_h, rep_w))
        window_tiled = window_tiled[:, :, :h, :w]
        pos_embed = pos_embed + window_tiled
        # [1, C, H, W] → [1, H, W, C]
        return pos_embed.transpose(0, 2, 3, 1)

    def __call__(self, x: mx.array) -> List[mx.array]:
        """
        Args:
            x: [B, C_img, H, W] (channels-first image input, [-1, 1])
        Returns:
            List of feature maps [B, C, H, W] (channels-first), one per stage
        """
        # Patch embedding: Conv2d expects channels-last [B, H, W, C]
        B = x.shape[0]
        x = x.transpose(0, 2, 3, 1)  # [B, C, H, W] → [B, H, W, C]
        x = self.patch_embed(x)  # [B, H', W', embed_dim]
        x = x + self._get_pos_embed(x.shape[1:3])

        outputs = []
        for i, blk in enumerate(self.blocks):
            x = blk(x)
            if (i == self.stage_ends[-1]) or (
                i in self.stage_ends and self.return_interm_layers
            ):
                # [B, H, W, C] → [B, C, H, W] (channels-first for FPN neck)
                feats = x.transpose(0, 3, 1, 2)
                outputs.append(feats)

        return outputs
