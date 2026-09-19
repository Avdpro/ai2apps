"""Validate RVC's complete reverse residual coupling flow on real weights."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .flow import ReverseResidualCouplingFlow
from .validate_primitives import _metrics


def validate(checkpoint: Path, upstream: Path) -> dict[str, object]:
    import mlx.core as mx
    import torch

    sys.path.insert(0, str(upstream))
    try:
        from infer.module.models import ResidualCouplingBlock
    finally:
        sys.path.pop(0)

    state = torch.load(checkpoint, map_location="cpu", weights_only=True)["model"]
    torch_model = ResidualCouplingBlock(192, 192, 5, 1, 3, gin_channels=256)
    torch_state = {
        name.removeprefix("flow."): value
        for name, value in state.items()
        if name.startswith("flow.")
    }
    torch_model.load_state_dict(torch_state, strict=True)
    torch_model.eval()
    numpy_state = {name: value.float().numpy() for name, value in state.items()}
    mlx_model = ReverseResidualCouplingFlow(numpy_state)

    rng = np.random.default_rng(211)
    values = rng.normal(size=(1, 192, 23)).astype(np.float32)
    mask = np.ones((1, 1, 23), dtype=np.float32)
    conditioning = rng.normal(size=(1, 256, 1)).astype(np.float32)
    with torch.no_grad():
        expected = torch_model(
            torch.from_numpy(values),
            torch.from_numpy(mask),
            g=torch.from_numpy(conditioning),
            reverse=True,
        ).numpy()
    actual = mlx_model(mx.array(values), mx.array(mask), mx.array(conditioning))
    mx.eval(actual)
    metrics = _metrics(expected, np.asarray(actual))
    if metrics["relative_rmse"] > 0.03 or metrics["peak_normalized_error"] > 0.03:
        raise AssertionError(f"reverse flow parity failed: {metrics}")
    return {"output": metrics, "shape": list(expected.shape)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(validate(arguments.checkpoint, arguments.upstream), indent=2))


if __name__ == "__main__":
    main()
