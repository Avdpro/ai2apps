"""OpenVDN hybrid attention for MiniMax-H3 on MLX.

This is a direct inference port of the released VDN-H3 arithmetic: exact
chunk-window softmax for near-field detail plus the bidirectional delta-state
branch for everything outside that window.  It intentionally uses ordinary MLX
operators first; Metal fusion is an optimization layer, not a model definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np


@dataclass(frozen=True)
class VDNGeometry:
    video_start: int
    video_end: int
    num_frames: int
    frame_height: int
    frame_width: int
    text_start: int = 0
    text_length: int = 0
    radius: int = 1
    chunk: int = 5
    anchors: str = "both"
    solver_iterations: int = 8

    @property
    def tokens_per_frame(self):
        return self.frame_height * self.frame_width

    @property
    def bounds(self):
        return window_bounds(self.num_frames, self.radius, self.chunk)


def window_bounds(num_frames: int, radius: int, chunk: int = 0):
    if chunk <= 0:
        return [(t - radius, t + radius) for t in range(num_frames)]
    return [(((t // chunk) - radius) * chunk,
             ((t // chunk) + radius + 1) * chunk - 1) for t in range(num_frames)]


def _sdpa(q, k, v):
    import mlx.core as mx
    return mx.fast.scaled_dot_product_attention(
        q.transpose(1, 0, 2)[None], k.transpose(1, 0, 2)[None],
        v.transpose(1, 0, 2)[None], scale=q.shape[-1] ** -0.5,
    )[0].transpose(1, 0, 2)


@lru_cache(maxsize=16)
def _simd_window_plan(geometry: VDNGeometry):
    """Tile OpenVDN's deterministic temporal window for the VSA Metal kernel."""
    from .vsa import VSAGeometry

    tile = 64
    seq = geometry.video_end
    prefix = geometry.video_start
    if geometry.tokens_per_frame % tile:
        raise ValueError("OpenVDN SIMD needs final video rows and 64-aligned frames")
    prefix_sizes = [tile] * (prefix // tile)
    if prefix % tile:
        prefix_sizes.append(prefix % tile)
    num_prefix_tiles = len(prefix_sizes)
    tiles_per_frame = geometry.tokens_per_frame // tile
    num_video_tiles = geometry.num_frames * tiles_per_frame
    block_sizes = np.asarray(prefix_sizes + [tile] * num_video_tiles, dtype=np.int64)
    sentinel = seq
    gather = np.full(len(block_sizes) * tile, sentinel, dtype=np.int64)
    if prefix:
        gather[:prefix] = np.arange(prefix, dtype=np.int64)
    video_pad_start = num_prefix_tiles * tile
    gather[video_pad_start:video_pad_start + geometry.video_end - prefix] = np.arange(
        prefix, geometry.video_end, dtype=np.int64
    )
    untile = np.empty(seq, dtype=np.int64)
    valid = gather < seq
    untile[gather[valid]] = np.flatnonzero(valid)
    tiled_geometry = VSAGeometry(
        prefix_length=prefix,
        num_prefix_tiles=num_prefix_tiles,
        num_video_tiles=num_video_tiles,
        tile_size=tile,
        total_length=seq,
        block_sizes=block_sizes,
        gather_index=gather,
        untile_index=untile,
    )

    anchor_rows = {0, geometry.num_frames - 1} \
        if geometry.anchors in {"rows", "both"} else set()
    rows = []
    counts = []
    for frame, (raw_lo, raw_hi) in enumerate(geometry.bounds):
        if frame in anchor_rows:
            selected = []  # evaluated by one dense SDPA below
        else:
            lo, hi = max(0, raw_lo), min(geometry.num_frames - 1, raw_hi)
            key_frames = set(range(lo, hi + 1))
            if geometry.anchors in {"columns", "both"}:
                key_frames.update((0, geometry.num_frames - 1))
            selected = list(range(num_prefix_tiles))
            for key_frame in sorted(key_frames):
                first = num_prefix_tiles + key_frame * tiles_per_frame
                selected.extend(range(first, first + tiles_per_frame))
        for _ in range(tiles_per_frame):
            rows.append(selected)
            counts.append(len(selected))
    width = max(counts)
    block_index = np.zeros((num_video_tiles, width), dtype=np.int32)
    for row, selected in enumerate(rows):
        if selected:
            block_index[row, :len(selected)] = selected
    dense_idx = np.concatenate([
        np.arange(prefix, dtype=np.int32),
        *[
            np.arange(
                prefix + frame * geometry.tokens_per_frame,
                prefix + (frame + 1) * geometry.tokens_per_frame,
                dtype=np.int32,
            )
            for frame in sorted(anchor_rows)
        ],
    ])
    return tiled_geometry, block_index, np.asarray(counts, dtype=np.int32), dense_idx


def _simd_window_softmax(q, k, v, geometry: VDNGeometry):
    import mlx.core as mx
    from .vsa import _tile
    from .vsa_simd import simd_block_sparse

    if q.shape[0] != geometry.video_end:
        raise ValueError("OpenVDN SIMD requires generated video to end the sequence")
    tiled_geometry, block_index, counts, dense_idx = _simd_window_plan(geometry)
    # The tile kernel wins only once the temporal window is genuinely sparse.
    # At five seconds OpenVDN still keeps about half the keys and MLX's dense
    # grouped SDPA is substantially faster. Long clips cross this threshold.
    if block_index.shape[-1] / tiled_geometry.num_tiles > 0.25:
        raise ValueError("OpenVDN window is too dense for the SIMD tile kernel")
    q_tiled, k_tiled, v_tiled = (_tile(x, tiled_geometry) for x in (q, k, v))
    heads = q.shape[1]
    selected = mx.broadcast_to(
        mx.array(block_index)[None], (heads, *block_index.shape)
    )
    block_counts = mx.broadcast_to(
        mx.array(counts)[None], (heads, counts.shape[0])
    )
    tiled_out = simd_block_sparse(
        q_tiled, k_tiled, v_tiled, selected, tiled_geometry,
        q.shape[-1] ** -0.5, block_counts=block_counts,
    )
    source_out = tiled_out[mx.array(tiled_geometry.untile_index)]
    if len(dense_idx):
        dense = mx.array(dense_idx)
        source_out[dense] = _sdpa(q[dense], k, v)
    return source_out


def window_softmax(q, k, v, geometry: VDNGeometry):
    """Exact grouped window attention; all non-target-video rows remain global."""
    # OpenVDN windows are contiguous temporal spans. MLX's native SDPA is much
    # faster here than repurposing FastH3's arbitrary-block kernel, even at the
    # 17% density of a 15-second clip (0.57 s vs 4.10 s in the measured shape).
    return _portable_window_softmax(q, k, v, geometry)


def _portable_window_softmax(q, k, v, geometry: VDNGeometry):
    """Grouped MLX SDPA correctness path for OpenVDN's temporal windows."""
    import mlx.core as mx

    seq = q.shape[0]
    start, end = geometry.video_start, geometry.video_end
    global_idx = np.concatenate((np.arange(start), np.arange(end, seq))).astype(np.int32)
    pieces = []
    # Packed H3 places generated video last, but retain general scatter semantics.
    out = mx.zeros_like(q)
    if len(global_idx):
        gi = mx.array(global_idx)
        out[gi] = _sdpa(q[gi], k, v)
    anchor_rows = {0, geometry.num_frames - 1} if geometry.anchors in {"rows", "both"} else set()
    grouped = {}
    for frame, bound in enumerate(geometry.bounds):
        if frame in anchor_rows:
            a = start + frame * geometry.tokens_per_frame
            b = a + geometry.tokens_per_frame
            out[a:b] = _sdpa(q[a:b], k, v)
            continue
        lo, hi = max(0, bound[0]), min(geometry.num_frames - 1, bound[1])
        grouped.setdefault((lo, hi), []).append(frame)
    for (lo, hi), frames in grouped.items():
        keys = list(range(lo, hi + 1))
        if geometry.anchors in {"columns", "both"}:
            keys = sorted(set(keys) | {0, geometry.num_frames - 1})
        q_idx = np.concatenate([
            np.arange(start + f * geometry.tokens_per_frame,
                      start + (f + 1) * geometry.tokens_per_frame) for f in frames
        ]).astype(np.int32)
        win_idx = np.concatenate([
            np.arange(start + f * geometry.tokens_per_frame,
                      start + (f + 1) * geometry.tokens_per_frame) for f in keys
        ]).astype(np.int32)
        all_k = np.concatenate((global_idx, win_idx)).astype(np.int32)
        qi, ki = mx.array(q_idx), mx.array(all_k)
        out[qi] = _sdpa(q[qi], k[ki], v[ki])
    return out


def _linear(x, weight, bias=None):
    y = x @ weight.T
    return y if bias is None else y + bias


def _linear_from(weights, key, x, bias_key=None):
    """Linear projection accepting either BF16 or affine-quantized branch weights."""
    import mlx.core as mx

    weight = weights[key]
    stem = key[:-len("weight")]
    scales = weights.get(stem + "scales")
    if scales is None:
        value = x @ weight.T
    else:
        in_features = int(scales.shape[-1]) * 64
        bits = int(round(32 * int(weight.shape[-1]) / in_features))
        value = mx.quantized_matmul(
            x.astype(scales.dtype), weight, scales, weights.get(stem + "biases"),
            transpose=True, group_size=64, bits=bits, mode="affine",
        )
    return value if bias_key is None else value + weights[bias_key]


def _l2_silu(x):
    import mlx.core as mx
    import mlx.nn as nn
    x = nn.silu(x)
    return x * mx.rsqrt(mx.sum(x.astype(mx.float32) ** 2, axis=-1, keepdims=True) + 1e-6).astype(x.dtype)


def _shift_axis(x, offset, axis):
    """Zero-padded shift with static slicing, avoiding a giant im2col tensor."""
    import mlx.core as mx
    n = x.shape[axis]
    if abs(offset) >= n:
        return mx.zeros_like(x)
    zshape = list(x.shape)
    zshape[axis] = abs(offset)
    zeros = mx.zeros(zshape, dtype=x.dtype)
    sl = [slice(None)] * x.ndim
    if offset < 0:
        sl[axis] = slice(-offset, n)
        return mx.concatenate([x[tuple(sl)], zeros], axis=axis)
    if offset > 0:
        sl[axis] = slice(0, n - offset)
        return mx.concatenate([zeros, x[tuple(sl)]], axis=axis)
    return x


def _conv_features(tokens, spatial, temporal, geometry: VDNGeometry, l2: bool):
    import mlx.core as mx
    import mlx.nn as nn
    f, h, w = geometry.num_frames, geometry.frame_height, geometry.frame_width
    channels = tokens.shape[-2] * tokens.shape[-1]
    volume = tokens.reshape(f, h, w, channels)
    # Source weights are PyTorch [C,1,K...] while MLX grouped convolution wants
    # [C,K...,1].  Native grouped conv replaces 30 elementwise shift kernels.
    sw = spatial.transpose(0, 2, 3, 1)
    spatial_out = mx.conv_general(volume, sw, padding=(2, 2), groups=channels)
    try:
        from .openvdn_simd import temporal_conv_activate

        return temporal_conv_activate(
            spatial_out, temporal, tokens.shape[-2], tokens.shape[-1], l2
        ).reshape(tokens.shape)
    except Exception:
        # Keep the ordinary MLX implementation for unsupported devices, shapes,
        # and custom-kernel compilation failures.
        pass
    temporal_input = spatial_out.transpose(1, 2, 0, 3).reshape(h * w, f, channels)
    tw = temporal.transpose(0, 2, 1)
    temporal_out = mx.conv_general(
        temporal_input, tw, padding=2, groups=channels
    ).reshape(h, w, f, channels).transpose(2, 0, 1, 3)
    result = nn.silu(temporal_out.reshape(tokens.shape))
    if l2:
        result = result * mx.rsqrt(
            mx.sum(result.astype(mx.float32) ** 2, axis=-1, keepdims=True) + 1e-6
        ).astype(result.dtype)
    return result


def _statistics_impl(k, v, beta):
    import mlx.core as mx
    scaled = k.astype(mx.float32) * beta[..., None].astype(mx.float32)
    a = scaled.transpose(0, 1, 3, 2) @ k.astype(mx.float32)
    a = 0.5 * (a + a.transpose(0, 1, 3, 2))
    b = (v * beta[..., None].astype(v.dtype)).transpose(0, 1, 3, 2).astype(mx.float32) @ k.astype(mx.float32)
    return a, b


_STATISTICS_COMPILED = None


def _statistics(k, v, beta):
    """Fuse casts, beta scaling and symmetrization around the two GEMMs."""
    global _STATISTICS_COMPILED
    try:
        import mlx.core as mx

        if _STATISTICS_COMPILED is None:
            _STATISTICS_COMPILED = mx.compile(_statistics_impl)
        return _STATISTICS_COMPILED(k, v, beta)
    except (AttributeError, RuntimeError, ValueError):
        return _statistics_impl(k, v, beta)


def _factor_impl(alpha, a, b, iterations: int):
    import mlx.core as mx
    eye = mx.eye(a.shape[-1], dtype=mx.float32)
    matrix = a + eye
    # MLX 0.29 does not expose Cholesky/inverse on Metal.  Batched conjugate
    # gradient solves M X = I entirely on the GPU; M is SPD by construction.
    # Eight iterations reaches ~4e-5 RMS residual on representative 128-wide
    # frame statistics; later iterations are already at the float32 plateau.
    inv = mx.zeros_like(matrix)
    residual = mx.broadcast_to(eye, matrix.shape)
    direction = residual
    rr = mx.sum(residual * residual, axis=-2)
    for _ in range(iterations):
        product = matrix @ direction
        step = rr / mx.maximum(mx.sum(direction * product, axis=-2), 1e-20)
        inv = inv + direction * step[..., None, :]
        residual = residual - product * step[..., None, :]
        next_rr = mx.sum(residual * residual, axis=-2)
        direction = residual + direction * (next_rr / mx.maximum(rr, 1e-20))[..., None, :]
        rr = next_rr
    return alpha[..., None] * inv, b @ inv


_FACTOR_CACHE = {}


def _factor(alpha, a, b, iterations: int = 8):
    """Run the fixed-shape CG graph through MLX's compile cache when available."""
    try:
        import mlx.core as mx

        fn = _FACTOR_CACHE.get(iterations)
        if fn is None:
            fn = mx.compile(
                lambda alpha_, a_, b_: _factor_impl(alpha_, a_, b_, iterations)
            )
            _FACTOR_CACHE[iterations] = fn
        return fn(alpha, a, b)
    except (AttributeError, RuntimeError, ValueError):
        return _factor_impl(alpha, a, b, iterations)


def _text_state(w, x, k, v, heads, dim):
    import mlx.core as mx
    import mlx.nn as nn
    if x.shape[0] == 0:
        return None
    kk, vv = _l2_silu(k), nn.silu(v)
    beta = mx.sigmoid(_linear_from(w, "linear_attention.beta_proj.weight", x))
    beta = beta.reshape(1, x.shape[0], heads).transpose(0, 2, 1)
    kk = kk.reshape(1, x.shape[0], heads, dim).transpose(0, 2, 1, 3)
    vv = vv.reshape(1, x.shape[0], heads, dim).transpose(0, 2, 1, 3)
    a, b = _statistics(kk, vv, beta)
    _, injection = _factor(mx.ones((1, heads, dim), dtype=mx.float32), a, b)
    return 0.5 * injection[0]


def _scan_states_impl(transition, injection, initial):
    """Inclusive forward/reverse affine scans for the bidirectional state."""
    import mlx.core as mx

    frames = transition.shape[0]
    state = initial
    prefix = []
    for i in range(frames):
        state = state @ transition[i] + injection[i]
        prefix.append(state)
    state = initial
    suffix = [None] * frames
    for i in range(frames - 1, -1, -1):
        state = state @ transition[i] + injection[i]
        suffix[i] = state
    return mx.stack(prefix), mx.stack(suffix)


_SCAN_CACHE = {}


def _scan_states(transition, injection, initial):
    """Compile each fixed frame-count scan once to reduce per-layer dispatch."""
    try:
        import mlx.core as mx

        frames = int(transition.shape[0])
        fn = _SCAN_CACHE.get(frames)
        if fn is None:
            fn = mx.compile(_scan_states_impl)
            _SCAN_CACHE[frames] = fn
        return fn(transition, injection, initial)
    except (AttributeError, RuntimeError, ValueError):
        return _scan_states_impl(transition, injection, initial)


def _gather_states(prefix, suffix, alpha, text_state, bounds):
    """Gather all outside-window states in one vectorized MLX graph."""
    import mlx.core as mx

    frames = prefix.shape[0]
    lo = np.asarray([bound[0] for bound in bounds], dtype=np.int32)
    hi = np.asarray([bound[1] for bound in bounds], dtype=np.int32)
    before, after = lo - 1, hi + 1
    left = prefix[mx.array(np.clip(before, 0, frames - 1))]
    right = suffix[mx.array(np.clip(after, 0, frames - 1))]
    left_missing = mx.array(before < 0)[:, None, None, None]
    right_missing = mx.array(after >= frames)[:, None, None, None]
    if text_state is None:
        left = mx.where(left_missing, mx.zeros_like(left), left)
        right = mx.where(right_missing, mx.zeros_like(right), right)
    else:
        seed = mx.broadcast_to(text_state[None], left.shape)
        left = mx.where(left_missing, seed, left)
        right = mx.where(right_missing, seed, right)

    log_prefix = mx.concatenate([
        mx.zeros_like(alpha[:1]),
        mx.cumsum(mx.log(mx.maximum(alpha, 1e-12)), axis=0),
    ])
    frame = np.arange(frames, dtype=np.int32)
    left_scale = mx.exp(
        log_prefix[mx.array(frame + 1)]
        - log_prefix[mx.array(np.maximum(lo, 0))]
    )[..., None, :]
    right_scale = mx.exp(
        log_prefix[mx.array(np.minimum(after, frames))]
        - log_prefix[mx.array(frame)]
    )[..., None, :]
    return left * left_scale + right * right_scale


def linear_branch(x, q_raw, k_raw, v_raw, w, g: VDNGeometry):
    import mlx.core as mx
    import mlx.nn as nn
    s, e, f, p = g.video_start, g.video_end, g.num_frames, g.tokens_per_frame
    xv = x[s:e]
    qv, kv, vv = q_raw[s:e], k_raw[s:e], v_raw[s:e]
    # Both anchor frames are handled densely and contribute no linear correction.
    inner = slice(p, (f - 1) * p)
    xv, qv, kv, vv = xv[inner], qv[inner], kv[inner], vv[inner]
    fi = f - 2
    if fi <= 0:
        return mx.zeros((e - s, q_raw.shape[1] * q_raw.shape[2]), dtype=x.dtype)
    gi = VDNGeometry(0, fi * p, fi, g.frame_height, g.frame_width,
                     radius=g.radius, chunk=g.chunk, anchors="none",
                     solver_iterations=g.solver_iterations)
    query = _l2_silu(qv)
    key = _conv_features(kv, w["linear_attention.short_conv.k_sp.weight"],
                         w["linear_attention.short_conv.k_tm.weight"], gi, True)
    value = _conv_features(vv, w["linear_attention.short_conv.v_sp.weight"],
                           w["linear_attention.short_conv.v_tm.weight"], gi, False)
    shape = (fi, p, q_raw.shape[1], q_raw.shape[2])
    kf = key.reshape(shape).transpose(0, 2, 1, 3)
    vf = value.reshape(shape).transpose(0, 2, 1, 3)
    beta = mx.sigmoid(_linear_from(w, "linear_attention.beta_proj.weight", xv))
    beta = beta.reshape(fi, p, q_raw.shape[1]).transpose(0, 2, 1)
    a, b = _statistics(kf, vf, beta)
    mean = xv.reshape(fi, p, -1).astype(mx.float32).mean(axis=1)
    delta = _linear_from(
        w, "linear_attention.alpha.up.weight",
        _linear_from(w, "linear_attention.alpha.down.weight", mean),
    ) + w["linear_attention.alpha.dt_bias"].astype(mx.float32)
    delta = delta.reshape(fi, q_raw.shape[1], q_raw.shape[2])
    alpha = mx.exp(-mx.exp(
        w["linear_attention.alpha.A_log"].astype(mx.float32)
    )[None, :, None] * mx.logaddexp(mx.array(0.0, dtype=mx.float32), delta))
    transition, injection = _factor(alpha, a, b, g.solver_iterations)
    ts, tl = g.text_start, g.text_length
    text_state = _text_state(w, x[ts:ts + tl], k_raw[ts:ts + tl],
                             v_raw[ts:ts + tl],
                             q_raw.shape[1], q_raw.shape[2])
    initial = mx.zeros_like(injection[0]) if text_state is None else text_state
    prefix, suffix = _scan_states(transition, injection, initial)
    bounds = [(lo - 1, hi - 1) for lo, hi in g.bounds[1:f - 1]]
    linear_state = _gather_states(prefix, suffix, alpha, text_state, bounds).astype(query.dtype)
    qf = query.reshape(shape).transpose(0, 2, 1, 3)
    readout = qf @ linear_state.transpose(0, 1, 3, 2)
    norm = w["linear_attention.norm.weight"].astype(readout.dtype)
    readout = readout * mx.rsqrt(mx.mean(readout.astype(mx.float32) ** 2, axis=-1, keepdims=True) + 1e-6).astype(readout.dtype) * norm
    gate = mx.sigmoid(_linear_from(
        w, "linear_attention.output_gate.up.weight",
        _linear_from(w, "linear_attention.output_gate.down.weight", xv),
        "linear_attention.output_gate.up.bias",
    ))
    readout = readout.transpose(0, 2, 1, 3).reshape(fi * p, -1) * gate
    result = mx.zeros((e - s, readout.shape[-1]), dtype=readout.dtype)
    result[inner] = readout
    return result


def hybrid_attention(x, q_raw, k_raw, v_raw, q, k, v, out_proj, w, geometry):
    import mlx.core as mx
    softmax = window_softmax(q, k, v, geometry)
    gate = mx.sigmoid(_linear_from(
        w, "softmax_gate.up.weight", x, "softmax_gate.up.bias"
    ))
    out = out_proj((softmax * gate[..., None]).reshape(x.shape[0], -1).astype(x.dtype))
    correction = linear_branch(x, q_raw, k_raw, v_raw, w, geometry)
    projected = _linear_from(w, "to_out_linear.weight", correction.astype(x.dtype))
    out[geometry.video_start:geometry.video_end] = out[geometry.video_start:geometry.video_end] + projected
    return out
