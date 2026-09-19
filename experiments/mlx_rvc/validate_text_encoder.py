"""Validate the complete RVC v2 TextEncoder against its PyTorch oracle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .text_encoder import TextEncoder
from .validate_primitives import _metrics


def validate(checkpoint: Path, upstream: Path) -> dict[str, object]:
    import mlx.core as mx
    import torch

    sys.path.insert(0, str(upstream))
    try:
        from infer.module.models import TextEncoder as TorchTextEncoder
    finally:
        sys.path.pop(0)

    package = torch.load(checkpoint, map_location="cpu", weights_only=True)
    state = package["model"]
    torch_model = TorchTextEncoder(768, 192, 192, 768, 2, 6, 3, 0.0, f0=True)
    encoder_state = {
        name.removeprefix("enc_p."): value
        for name, value in state.items()
        if name.startswith("enc_p.")
    }
    torch_model.load_state_dict(encoder_state, strict=True)
    torch_model.eval()
    numpy_state = {name: value.float().numpy() for name, value in state.items()}
    mlx_model = TextEncoder(numpy_state)

    rng = np.random.default_rng(117)
    phone = rng.normal(size=(1, 31, 768)).astype(np.float32)
    pitch = rng.integers(1, 256, size=(1, 31), dtype=np.int64)
    lengths = np.array([31], dtype=np.int64)
    with torch.no_grad():
        torch_outputs = torch_model(
            torch.from_numpy(phone), torch.from_numpy(pitch), torch.from_numpy(lengths)
        )
    mlx_outputs = mlx_model(mx.array(phone), mx.array(pitch), mx.array(lengths))
    mx.eval(*mlx_outputs)

    names = ("mean", "log_scale", "mask")
    metrics = {
        name: _metrics(expected.numpy(), np.asarray(actual))
        for name, expected, actual in zip(names, torch_outputs, mlx_outputs)
    }
    for name in ("mean", "log_scale"):
        if (
            metrics[name]["relative_rmse"] > 0.03
            or metrics[name]["peak_normalized_error"] > 0.03
        ):
            raise AssertionError(f"TextEncoder {name} parity failed: {metrics[name]}")
    if not np.array_equal(torch_outputs[2].numpy(), np.asarray(mlx_outputs[2])):
        raise AssertionError("TextEncoder mask parity failed")
    return {"outputs": metrics, "shape": list(torch_outputs[0].shape)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(validate(arguments.checkpoint, arguments.upstream), indent=2))


if __name__ == "__main__":
    main()
