# ruff: noqa
"""Convert PyTorch state_dicts (from upstream LivePortrait .pth files) into
MLX-compatible state dicts.

Key transforms:
* Conv2d weight (out, in, kH, kW) -> (out, kH, kW, in)
* Conv3d weight (out, in, kD, kH, kW) -> (out, kD, kH, kW, in)
* Spectral-norm reparameterization (weight_orig + weight_u/v) folded into
  a plain `weight` tensor by computing sigma = u^T (W v) and W_eff = W / sigma.
* Linear, BatchNorm, InstanceNorm, GRN parameters pass through.
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np


def _torch_load(path: str):
    import torch  # local import: torch is only required during conversion
    return torch.load(path, map_location="cpu", weights_only=False)


def _to_numpy(t):
    import torch
    if isinstance(t, torch.Tensor):
        return t.detach().cpu().to(torch.float32).numpy()
    return np.asarray(t)


def _resolve_spectral_norm(state_dict: Dict[str, "np.ndarray"]) -> Dict[str, np.ndarray]:
    """Detect `*.weight_orig` triplets and replace with a folded `*.weight`.

    PyTorch's spectral_norm reparameterizes a layer's `weight` as
    W_eff = W_orig / sigma, where sigma is computed via power iteration with
    state vectors `weight_u` and `weight_v`. At inference, we can fold:
        sigma = (u @ W_orig.reshape(out, -1) @ v)
        W_eff = W_orig / sigma
    """
    folded: Dict[str, np.ndarray] = {}
    drop_keys = set()
    for key in list(state_dict.keys()):
        if not key.endswith(".weight_orig"):
            continue
        prefix = key[: -len(".weight_orig")]
        u_key = prefix + ".weight_u"
        v_key = prefix + ".weight_v"
        if u_key not in state_dict or v_key not in state_dict:
            # Some checkpoints store legacy spectral_norm with (.weight, .weight_u/v)
            # style. We'll only touch ones with full triplet.
            continue
        W = state_dict[key]
        u = state_dict[u_key]
        v = state_dict[v_key]
        W2 = W.reshape(W.shape[0], -1)
        sigma = float(u @ W2 @ v)
        if abs(sigma) < 1e-12:
            sigma = 1.0
        W_eff = W / sigma
        folded[prefix + ".weight"] = W_eff
        drop_keys.update({key, u_key, v_key})
    out = dict(state_dict)
    for k in drop_keys:
        out.pop(k, None)
    out.update(folded)
    return out


def _is_conv_weight_shape(arr: np.ndarray, key: str) -> Tuple[bool, int]:
    """Heuristic: detect Conv2d/Conv3d weight tensors by trailing '.weight'
    and ndim. Returns (is_conv, ndim) where ndim is 4 for Conv2d, 5 for Conv3d."""
    if not key.endswith(".weight"):
        return False, 0
    if arr.ndim == 4:
        return True, 4
    if arr.ndim == 5:
        return True, 5
    return False, 0


_DROP_SUFFIXES = (".num_batches_tracked",)


def convert_state_dict(
    pt_state_dict,
    *,
    dropping_prefix: str = "",
    key_renames: tuple = (),
) -> Dict[str, "np.ndarray"]:
    """Convert a PyTorch state_dict to a flat dict of numpy arrays in MLX
    layout (NHWC convs). Caller can pass it to mx.tree_unflatten / model.update.

    `dropping_prefix` is stripped from every key (e.g. "detector." for
    motion_extractor checkpoints whose top-level wraps everything in detector.)

    `key_renames` is an iterable of (regex_pattern, replacement) pairs applied
    in order, used for translating PyTorch's named-Sequential children
    ("3dr0", "3dr1", ...) into MLX list indices ("0", "1", ...).
    """
    import re
    # Resolve spectral norm first so we operate on the folded weights only.
    raw = {k: _to_numpy(v) for k, v in pt_state_dict.items()}
    raw = _resolve_spectral_norm(raw)

    compiled_renames = [(re.compile(p), r) for p, r in key_renames]

    out: Dict[str, np.ndarray] = {}
    for key, arr in raw.items():
        if any(key.endswith(s) for s in _DROP_SUFFIXES):
            continue

        new_key = key
        if dropping_prefix and new_key.startswith(dropping_prefix):
            new_key = new_key[len(dropping_prefix):]
        for pat, rep in compiled_renames:
            new_key = pat.sub(rep, new_key)

        is_conv, ndim = _is_conv_weight_shape(arr, key)
        if is_conv and ndim == 4:
            arr = np.transpose(arr, (0, 2, 3, 1))
        elif is_conv and ndim == 5:
            arr = np.transpose(arr, (0, 2, 3, 4, 1))

        out[new_key] = np.ascontiguousarray(arr.astype(np.float32))
    return out


# Lightweight type alias just for clarity
mxArrayLike = "np.ndarray"


def convert_pth_to_safetensors(pth_path: str, out_path: str, *, dropping_prefix: str = "") -> None:
    import mlx.core as mx
    sd = _torch_load(pth_path)
    if isinstance(sd, dict) and "model" in sd and isinstance(sd["model"], dict):
        sd = sd["model"]
    converted = convert_state_dict(sd, dropping_prefix=dropping_prefix)
    mlx_state = {k: mx.array(v) for k, v in converted.items()}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    mx.save_safetensors(out_path, mlx_state)


def save_converted_npz(
    pth_path: str,
    out_path: str,
    *,
    dropping_prefix: str = "",
    key_renames: tuple = (),
) -> None:
    sd = _torch_load(pth_path)
    if isinstance(sd, dict) and "model" in sd and isinstance(sd["model"], dict):
        sd = sd["model"]
    converted = convert_state_dict(
        sd, dropping_prefix=dropping_prefix, key_renames=key_renames
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    np.savez(out_path, **converted)


def _load_npz_state(path: str):
    import mlx.core as mx

    with np.load(path) as data:
        return {name: mx.array(data[name].astype(np.float32)) for name in data.files}


def load_into_model(
    model,
    path: str,
    *,
    dropping_prefix: str = "",
    key_renames: tuple = (),
    strict: bool = True,
):
    """Load exported MLX runtime weights into an MLX module."""
    import mlx.core as mx
    import mlx.utils as mu

    if not str(path).endswith(".npz"):
        raise ValueError(
            f"MLX runtime models require exported .npz weights, got {path}. "
            "Run scripts/export_mlx_weights.py first."
        )
    mlx_state = _load_npz_state(path)

    expected_keys = {k for k, _ in mu.tree_flatten(model.parameters())}
    if strict:
        missing = expected_keys - set(mlx_state.keys())
        unexpected = set(mlx_state.keys()) - expected_keys
        if missing or unexpected:
            raise ValueError(
                f"state_dict mismatch.\n  missing in checkpoint: {sorted(missing)[:8]}\n"
                f"  unexpected in checkpoint: {sorted(unexpected)[:8]}"
            )

    model.update(mu.tree_unflatten(list(mlx_state.items())))
    return model
