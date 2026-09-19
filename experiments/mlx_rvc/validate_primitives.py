"""Compare actual RVC v2 checkpoint primitives between PyTorch and MLX."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .mlx_layers import conv1d_nct, conv_transpose1d_nct, linear, weight_norm


def _metrics(reference: np.ndarray, actual: np.ndarray) -> dict[str, float]:
    difference = np.asarray(actual, dtype=np.float64) - np.asarray(
        reference, dtype=np.float64
    )
    peak = max(float(np.max(np.abs(reference))), 1e-12)
    reference_rms = max(float(np.sqrt(np.mean(np.square(reference)))), 1e-12)
    return {
        "max_absolute_error": float(np.max(np.abs(difference))),
        "peak_normalized_error": float(np.max(np.abs(difference)) / peak),
        "relative_rmse": float(np.sqrt(np.mean(np.square(difference))) / reference_rms),
    }


def validate(checkpoint: str | Path) -> dict[str, object]:
    import mlx.core as mx
    import torch
    import torch.nn.functional as torch_f

    package = torch.load(Path(checkpoint), map_location="cpu", weights_only=True)
    state = package.get("model") if isinstance(package, dict) else None
    if not isinstance(state, dict):
        raise ValueError("expected an official RVC pretrained generator checkpoint")
    rng = np.random.default_rng(81)

    phone = rng.normal(size=(1, 19, 768)).astype(np.float32)
    linear_weight = state["enc_p.emb_phone.weight"].float().numpy()
    linear_bias = state["enc_p.emb_phone.bias"].float().numpy()
    torch_linear = torch_f.linear(
        torch.from_numpy(phone),
        torch.from_numpy(linear_weight),
        torch.from_numpy(linear_bias),
    ).numpy()
    mlx_linear = linear(mx.array(phone), mx.array(linear_weight), mx.array(linear_bias))

    conv_input = rng.normal(size=(1, 192, 19)).astype(np.float32)
    conv_weight = state["enc_p.proj.weight"].float().numpy()
    conv_bias = state["enc_p.proj.bias"].float().numpy()
    torch_conv = torch_f.conv1d(
        torch.from_numpy(conv_input),
        torch.from_numpy(conv_weight),
        torch.from_numpy(conv_bias),
    ).numpy()
    mlx_conv = conv1d_nct(
        mx.array(conv_input), mx.array(conv_weight), mx.array(conv_bias)
    )

    transpose_input = rng.normal(size=(1, 512, 11)).astype(np.float32)
    gain = state["dec.ups.0.weight_g"].float().numpy()
    direction = state["dec.ups.0.weight_v"].float().numpy()
    transpose_weight = weight_norm(gain, direction)
    transpose_bias = state["dec.ups.0.bias"].float().numpy()
    torch_transpose = torch_f.conv_transpose1d(
        torch.from_numpy(transpose_input),
        torch.from_numpy(transpose_weight),
        torch.from_numpy(transpose_bias),
        stride=12,
        padding=6,
    ).numpy()
    mlx_transpose = conv_transpose1d_nct(
        mx.array(transpose_input),
        mx.array(transpose_weight),
        mx.array(transpose_bias),
        stride=12,
        padding=6,
    )
    mx.eval(mlx_linear, mlx_conv, mlx_transpose)

    outputs = {
        "linear": _metrics(torch_linear, np.asarray(mlx_linear)),
        "conv1d": _metrics(torch_conv, np.asarray(mlx_conv)),
        "conv_transpose1d": _metrics(torch_transpose, np.asarray(mlx_transpose)),
    }
    for name, metrics in outputs.items():
        # MLX Metal reductions use a different accumulation order from the
        # PyTorch CPU oracle. Match the scale-aware 1% primitive gate already
        # used by the validated MLX-Demucs port rather than requiring CPU/GPU
        # bit identity.
        if metrics["relative_rmse"] > 1e-2 or metrics["peak_normalized_error"] > 1e-2:
            raise AssertionError(f"{name} parity failed: {metrics}")
    return {
        "checkpoint": str(Path(checkpoint)),
        "outputs": outputs,
        "shapes": {
            "linear": list(torch_linear.shape),
            "conv1d": list(torch_conv.shape),
            "conv_transpose1d": list(torch_transpose.shape),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(validate(arguments.checkpoint), indent=2))


if __name__ == "__main__":
    main()
