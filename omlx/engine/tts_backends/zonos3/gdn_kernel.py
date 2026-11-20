# Copyright © 2025 Apple Inc.
# SPDX-License-Identifier: MIT
#
# The scalar-gate, unmasked gated-delta Metal kernel of mlx-lm (mlx_lm/models/gated_delta.py,
# _make_gated_delta_kernel(has_mask=False, vectorized=False)) and its ops-loop step, adapted for the ZONOS3 GDN layers:
# q, k [B, T, Hk, Dk], v [B, T, Hv, Dv], g / beta [B, T, Hv], state [B, Hv, Dv, Dk] (FLA state_v_first), all float32.
# q arrives pre-scaled by Dk**-0.5. mlx-lm itself is not a dependency (it pins transformers>=5.7).
"""Gated delta rule recurrence of the GDN layers: a Metal kernel for prefill, an ops step for decode."""

from __future__ import annotations

import mlx.core as mx

_SOURCE = """
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

        // g: [B, T, Hv]
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
          // Increment data pointers to next time step
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


def _metal_kernel():
    global _kernel
    if _kernel is None and mx.metal.is_available():
        _kernel = mx.fast.metal_kernel(
            name="zonos3_gated_delta_step",
            input_names=["q", "k", "v", "g", "beta", "state_in", "T"],
            output_names=["y", "state_out"],
            source=_SOURCE,
        )
    return _kernel


@mx.compile
def gated_delta_step(q, k, v, g, beta, state):
    """One recurrent step: q, k [B, H, Dk]; v [B, H, Dv]; g, beta [B, H]; state [B, H, Dv, Dk] -> (y, state)."""
    state = state * g[..., None, None]
    kv_mem = (state * k[..., None, :]).sum(axis=-1)
    delta = (v - kv_mem) * beta[..., None]
    state = state + k[..., None, :] * delta[..., None]
    y = (state * q[..., None, :]).sum(axis=-1)
    return y, state


def gated_delta_ops(q, k, v, g, beta, state):
    ys = []
    for t in range(q.shape[1]):
        y, state = gated_delta_step(
            q[:, t], k[:, t], v[:, t], g[:, t], beta[:, t], state
        )
        ys.append(y)
    return mx.stack(ys, axis=1), state


def gated_delta(q, k, v, g, beta, state):
    """y [B, T, Hv, Dv], state: the Metal kernel for multi-row calls, the ops step for one row / no Metal."""
    B, T, Hk, Dk = k.shape
    Hv, Dv = v.shape[2:]
    kernel = _metal_kernel() if T > 1 and Dk % 32 == 0 else None
    if kernel is None:
        return gated_delta_ops(q, k, v, g, beta, state)
    y, out = kernel(
        inputs=[q, k, v, g, beta, state, T],
        template=[
            ("InT", q.dtype),
            ("StT", state.dtype),
            ("Dk", Dk),
            ("Dv", Dv),
            ("Hk", Hk),
            ("Hv", Hv),
        ],
        grid=(32, Dv, B * Hv),
        threadgroup=(32, 4, 1),
        output_shapes=[(B, T, Hv, Dv), state.shape],
        output_dtypes=[q.dtype, state.dtype],
    )
    return y, out
