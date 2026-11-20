"""The gated delta rule: the recurrence inside a Gated DeltaNet layer.

Each value head keeps a fast-weight matrix ``S [Dv, Dk]`` that maps keys to
values. One position decays it, writes the part of the value the memory does
not predict yet, and reads it with the query::

    S = g * S
    S = S + (beta * (v - S k)) k^T
    y = S q

On Apple GPUs the recurrence runs as one Metal kernel, with one thread per
state row and the row's keys spread over a SIMD group. Elsewhere the same
update is written with array operations.
"""

from __future__ import annotations

import mlx.core as mx

_KERNEL_SOURCE = """
    auto n = thread_position_in_grid.z;
    auto b_idx = n / Hv;
    auto hv_idx = n % Hv;
    auto hk_idx = hv_idx / (Hv / Hk);
    constexpr int n_per_t = Dk / 32;

    // q, k: [B, T, Hk, Dk]
    auto q_ = q + b_idx * T * Hk * Dk + hk_idx * Dk;
    auto k_ = k + b_idx * T * Hk * Dk + hk_idx * Dk;

    // v, y: [B, T, Hv, Dv]
    auto v_ = v + b_idx * T * Hv * Dv + hv_idx * Dv;
    y += b_idx * T * Hv * Dv + hv_idx * Dv;

    auto dk_idx = thread_position_in_threadgroup.x;
    auto dv_idx = thread_position_in_grid.y;

    // state_in, state_out: [B, Hv, Dv, Dk]
    auto i_state = state_in + (n * Dv + dv_idx) * Dk;
    auto o_state = state_out + (n * Dv + dv_idx) * Dk;

    float state[n_per_t];
    for (int i = 0; i < n_per_t; ++i) {
      auto s_idx = n_per_t * dk_idx + i;
      state[i] = static_cast<float>(i_state[s_idx]);
    }

    // g, beta: [B, T, Hv]
    auto g_ = g + b_idx * T * Hv;
    auto beta_ = beta + b_idx * T * Hv;

    for (int t = 0; t < T; ++t) {
      float kv_mem = 0.0f;
      for (int i = 0; i < n_per_t; ++i) {
        auto s_idx = n_per_t * dk_idx + i;
        state[i] = state[i] * g_[hv_idx];
        kv_mem += state[i] * k_[s_idx];
      }
      kv_mem = simd_sum(kv_mem);

      auto delta = (v_[dv_idx] - kv_mem) * beta_[hv_idx];

      float out = 0.0f;
      for (int i = 0; i < n_per_t; ++i) {
        auto s_idx = n_per_t * dk_idx + i;
        state[i] = state[i] + k_[s_idx] * delta;
        out += state[i] * q_[s_idx];
      }
      out = simd_sum(out);
      if (thread_index_in_simdgroup == 0) {
        y[dv_idx] = static_cast<InT>(out);
      }
      q_ += Hk * Dk;
      k_ += Hk * Dk;
      v_ += Hv * Dv;
      y += Hv * Dv;
      g_ += Hv;
      beta_ += Hv;
    }
    for (int i = 0; i < n_per_t; ++i) {
      auto s_idx = n_per_t * dk_idx + i;
      o_state[s_idx] = static_cast<StT>(state[i]);
    }
"""

_kernel = None


def _metal_update(q, k, v, g, beta, state):
    global _kernel
    if _kernel is None:
        _kernel = mx.fast.metal_kernel(
            name="gated_delta_rule",
            input_names=["q", "k", "v", "g", "beta", "state_in", "T"],
            output_names=["y", "state_out"],
            source=_KERNEL_SOURCE,
        )
    batch, steps, key_heads, key_dim = k.shape
    value_heads, value_dim = v.shape[2:]
    return _kernel(
        inputs=[q, k, v, g, beta, state, steps],
        template=[
            ("InT", q.dtype),
            ("StT", state.dtype),
            ("Dk", key_dim),
            ("Dv", value_dim),
            ("Hk", key_heads),
            ("Hv", value_heads),
        ],
        grid=(32, value_dim, batch * value_heads),
        threadgroup=(32, 4, 1),
        output_shapes=[(batch, steps, value_heads, value_dim), state.shape],
        output_dtypes=[q.dtype, state.dtype],
    )


def _array_update(q, k, v, g, beta, state):
    repeat = v.shape[2] // k.shape[2]
    if repeat > 1:
        q = mx.repeat(q, repeat, axis=2)
        k = mx.repeat(k, repeat, axis=2)
    outputs = []
    for t in range(q.shape[1]):
        key = k[:, t, :, None, :]
        state = state * g[:, t, :, None, None]
        delta = (v[:, t] - (state * key).sum(axis=-1)) * beta[:, t, :, None]
        state = state + key * delta[..., None]
        outputs.append((state * q[:, t, :, None, :]).sum(axis=-1))
    return mx.stack(outputs, axis=1).astype(q.dtype), state


def uses_metal_kernel() -> bool:
    return mx.metal.is_available() and mx.default_device() == mx.gpu


def gated_delta_rule(
    q: mx.array, k: mx.array, v: mx.array, g: mx.array, beta: mx.array, state: mx.array
) -> tuple[mx.array, mx.array]:
    """Run the recurrence over ``T`` positions.

    ``q, k [B, T, Hk, Dk]`` (each key head serves ``Hv / Hk`` value heads),
    ``v [B, T, Hv, Dv]``, decay ``g`` and write strength ``beta [B, T, Hv]``,
    ``state [B, Hv, Dv, Dk]`` in float32. Returns ``y [B, T, Hv, Dv]`` in the
    dtype of ``q`` and the new state.
    """
    if uses_metal_kernel():
        return _metal_update(q, k, v, g, beta, state)
    return _array_update(q, k, v, g, beta, state)
