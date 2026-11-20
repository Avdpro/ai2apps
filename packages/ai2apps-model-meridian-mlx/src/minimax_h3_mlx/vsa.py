"""Video Sparse Attention (VSA) for the FastH3 MLX experiment.

The router matches FastVideo's released H3 VSA contract: segment-pure prefix
tiles, 4x4x4 generated-video tiles, per-head pooled Q/K scores, all prefix keys,
and top-k video keys.  Prefix queries remain dense.  This portable backend uses
grouped MLX SDPA calls and therefore provides a correctness baseline on every
Apple GPU; a custom Metal SIMD kernel can replace only ``_sparse_video`` later.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class VSAGeometry:
    prefix_length: int
    num_prefix_tiles: int
    num_video_tiles: int
    tile_size: int
    total_length: int
    block_sizes: np.ndarray
    gather_index: np.ndarray
    untile_index: np.ndarray

    @property
    def num_tiles(self) -> int:
        return len(self.block_sizes)

    @property
    def padded_length(self) -> int:
        return self.num_tiles * self.tile_size


def build_vsa_geometry(
    prefix_segments: tuple[int, ...], video_shape: tuple[int, int, int], tile_size: int = 64
) -> VSAGeometry:
    """Build FastH3's tiled order for ``prefix + (time,height,width)`` rows."""

    if tile_size != 64:
        raise ValueError("The MLX FastH3 experiment currently supports tile_size=64")
    tile_shape = (4, 4, 4)
    prefix_segments = tuple(int(x) for x in prefix_segments if x)
    prefix_length = sum(prefix_segments)
    prefix_sizes: list[int] = []
    for length in prefix_segments:
        full, remainder = divmod(length, tile_size)
        prefix_sizes.extend([tile_size] * full)
        if remainder:
            prefix_sizes.append(remainder)

    t, h, w = map(int, video_shape)
    video_grid = np.arange(t * h * w, dtype=np.int64).reshape(t, h, w)
    video_parts = []
    video_sizes = []
    for ti in range(math.ceil(t / 4)):
        for hi in range(math.ceil(h / 4)):
            for wi in range(math.ceil(w / 4)):
                part = video_grid[
                    ti * 4:min(ti * 4 + 4, t),
                    hi * 4:min(hi * 4 + 4, h),
                    wi * 4:min(wi * 4 + 4, w),
                ].reshape(-1)
                video_parts.append(part + prefix_length)
                video_sizes.append(len(part))
    tiled_order = np.concatenate([
        np.arange(prefix_length, dtype=np.int64), *video_parts
    ])
    sizes = np.asarray(prefix_sizes + video_sizes, dtype=np.int64)
    padded_to_source = np.full(len(sizes) * tile_size, prefix_length + t * h * w, dtype=np.int64)
    cursor = 0
    for tile, size in enumerate(sizes):
        padded_to_source[tile * tile_size:tile * tile_size + size] = tiled_order[cursor:cursor + size]
        cursor += size
    # source row -> padded tiled row; padded_to_source's final sentinel is excluded.
    source_to_padded = np.empty(prefix_length + t * h * w, dtype=np.int64)
    valid = padded_to_source < len(source_to_padded)
    source_to_padded[padded_to_source[valid]] = np.flatnonzero(valid)
    return VSAGeometry(
        prefix_length=prefix_length,
        num_prefix_tiles=len(prefix_sizes),
        num_video_tiles=len(video_sizes),
        tile_size=tile_size,
        total_length=len(source_to_padded),
        block_sizes=sizes,
        gather_index=padded_to_source,
        untile_index=source_to_padded,
    )


def _tile(x, geometry: VSAGeometry):
    import mlx.core as mx

    sentinel = mx.zeros((1, x.shape[1], x.shape[2]), dtype=x.dtype)
    return mx.concatenate([x, sentinel], axis=0)[mx.array(geometry.gather_index)]


def _pool(x, geometry: VSAGeometry):
    import mlx.core as mx

    tiles = x.reshape(geometry.num_tiles, geometry.tile_size, x.shape[1], x.shape[2])
    pooled = tiles.astype(mx.float32).sum(axis=1)
    pooled = pooled / mx.array(geometry.block_sizes, dtype=mx.float32)[:, None, None]
    return pooled.transpose(1, 0, 2)


def _dense(q, k, v, scale):
    import mlx.core as mx

    return mx.fast.scaled_dot_product_attention(
        q.transpose(1, 0, 2)[None], k.transpose(1, 0, 2)[None],
        v.transpose(1, 0, 2)[None], scale=scale,
    )[0].transpose(1, 0, 2)


def _selected_blocks(scores, geometry: VSAGeometry, sparsity: float):
    import mlx.core as mx

    keep_video = max(1, min(
        geometry.num_video_tiles,
        math.ceil((1.0 - float(sparsity)) * geometry.num_video_tiles),
    ))
    video_scores = scores[:, geometry.num_prefix_tiles:, geometry.num_prefix_tiles:]
    chosen = mx.argpartition(-video_scores, kth=keep_video - 1, axis=-1)[..., :keep_video]
    chosen = chosen.astype(mx.int32) + geometry.num_prefix_tiles
    if not geometry.num_prefix_tiles:
        return chosen
    prefix = mx.broadcast_to(
        mx.arange(geometry.num_prefix_tiles, dtype=mx.int32)[None, None],
        (scores.shape[0], geometry.num_video_tiles, geometry.num_prefix_tiles),
    )
    return mx.concatenate([prefix, chosen], axis=-1)


def _sparse_video(q_tiled, k_tiled, v_tiled, selected, geometry: VSAGeometry, scale):
    """Memory-bounded grouped gather + SDPA for all generated-video query tiles."""

    import mlx.core as mx

    n, tile, heads, dim = geometry.num_tiles, geometry.tile_size, q_tiled.shape[1], q_tiled.shape[2]
    q_tiles = q_tiled.reshape(n, tile, heads, dim).transpose(2, 0, 1, 3)
    k_tiles = k_tiled.reshape(n, tile, heads, dim).transpose(2, 0, 1, 3)
    v_tiles = v_tiled.reshape(n, tile, heads, dim).transpose(2, 0, 1, 3)
    q_video = q_tiles[:, geometry.num_prefix_tiles:]
    k_select = int(selected.shape[-1])
    # Keep gathered K+V under about 1 GiB; unlike a full token mask this scales
    # with selected blocks rather than sequence squared.
    bytes_per_query = max(1, 4 * heads * k_select * tile * dim)
    chunk = max(1, min(geometry.num_video_tiles, (1024**3) // bytes_per_query))
    outputs = []
    block_sizes = mx.array(geometry.block_sizes, dtype=mx.int32)
    offsets = mx.arange(tile, dtype=mx.int32)
    head_ids = mx.arange(heads)[:, None, None]
    for start in range(0, geometry.num_video_tiles, chunk):
        end = min(start + chunk, geometry.num_video_tiles)
        idx = selected[:, start:end]
        count = end - start
        gathered_k = k_tiles[head_ids, idx].reshape(heads, count, k_select * tile, dim)
        gathered_v = v_tiles[head_ids, idx].reshape(heads, count, k_select * tile, dim)
        valid = offsets[None, None, None] < block_sizes[idx][..., None]
        valid = valid.reshape(1, heads * count, 1, k_select * tile)
        qq = mx.contiguous(q_video[:, start:end].reshape(heads * count, tile, dim)[None])
        kk = mx.contiguous(gathered_k.reshape(heads * count, k_select * tile, dim)[None])
        vv = mx.contiguous(gathered_v.reshape(heads * count, k_select * tile, dim)[None])
        out = mx.fast.scaled_dot_product_attention(qq, kk, vv, scale=scale, mask=valid)[0]
        out = out.reshape(heads, count, tile, dim)
        mx.eval(out)
        outputs.append(out)
    return mx.concatenate(outputs, axis=1).transpose(1, 2, 0, 3).reshape(
        geometry.num_video_tiles * tile, heads, dim
    )


def vsa_attention(q, k, v, geometry: VSAGeometry, *, sparsity: float = 0.9, gate=None):
    """Run FastH3 VSA on packed ``[sequence, heads, head_dim]`` Q/K/V."""

    import mlx.core as mx

    if q.shape[0] != geometry.total_length:
        raise ValueError(f"VSA geometry has {geometry.total_length} rows, got {q.shape[0]}")
    scale = q.shape[-1] ** -0.5
    q_tiled, k_tiled, v_tiled = (_tile(x, geometry) for x in (q, k, v))
    qp, kp = _pool(q_tiled, geometry), _pool(k_tiled, geometry)
    scores = (qp @ kp.transpose(0, 2, 1)) * scale
    selected = _selected_blocks(scores, geometry, sparsity)
    prefix = _dense(q[:geometry.prefix_length], k, v, scale) if geometry.prefix_length else q[:0]
    try:
        from .vsa_simd import simd_block_sparse
        video = simd_block_sparse(
            q_tiled, k_tiled, v_tiled, selected, geometry, scale
        )[geometry.num_prefix_tiles * geometry.tile_size:]
    except Exception:
        # Unsupported GPU/shape and custom-kernel compile errors retain the
        # portable correctness path.
        video = _sparse_video(q_tiled, k_tiled, v_tiled, selected, geometry, scale)
    prefix_pad = geometry.num_prefix_tiles * geometry.tile_size
    prefix_tiled = mx.zeros((prefix_pad, q.shape[1], q.shape[2]), dtype=q.dtype)
    if geometry.prefix_length:
        prefix_tiled[mx.array(geometry.untile_index[:geometry.prefix_length])] = prefix
    out_tiled = mx.concatenate([prefix_tiled, video.astype(q.dtype)], axis=0)
    if gate is not None:
        gate_tiled = _tile(gate, geometry).reshape(
            geometry.num_tiles, geometry.tile_size, q.shape[1], q.shape[2]
        )
        pooled_v = _pool(v_tiled, geometry)
        compressed = (mx.softmax(scores, axis=-1) @ pooled_v).transpose(1, 0, 2)
        out_tiled = out_tiled + (
            compressed[:, None] * gate_tiled
        ).reshape(geometry.padded_length, q.shape[1], q.shape[2]).astype(q.dtype)
    return out_tiled[mx.array(geometry.untile_index)]
