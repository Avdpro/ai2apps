"""Compare the MLX Seed-VC length regulator with its PyTorch oracle."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .length_regulator import ContinuousLengthRegulator


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    state = checkpoint["net"]["length_regulator"]
    state = {name.removeprefix("module."): value.float() for name, value in state.items()}
    rng = np.random.default_rng(29)
    content = rng.normal(size=(1, 31, 768)).astype(np.float32)
    with torch.no_grad():
        values = torch.nn.functional.linear(
            torch.from_numpy(content),
            state["content_in_proj.weight"],
            state["content_in_proj.bias"],
        )
        values = torch.nn.functional.interpolate(
            values.transpose(1, 2), size=47, mode="nearest"
        )
        for conv_index, norm_index in ((0, 1), (3, 4), (6, 7), (9, 10)):
            values = torch.nn.functional.conv1d(
                values,
                state[f"model.{conv_index}.weight"],
                state[f"model.{conv_index}.bias"],
                padding=1,
            )
            values = torch.nn.functional.group_norm(
                values,
                1,
                state[f"model.{norm_index}.weight"],
                state[f"model.{norm_index}.bias"],
            )
            values = torch.nn.functional.mish(values)
        reference = torch.nn.functional.conv1d(
            values, state["model.12.weight"], state["model.12.bias"]
        ).transpose(1, 2).numpy()
    actual = np.asarray(
        ContinuousLengthRegulator(
            {name: value.numpy() for name, value in state.items()}
        )(mx.array(content), 47)
    )
    relative = float(
        np.sqrt(np.mean((actual - reference) ** 2))
        / max(np.sqrt(np.mean(reference**2)), 1e-12)
    )
    print(f"shape={list(actual.shape)}")
    print(f"relative_rmse={relative:.8g}")
    if actual.shape != reference.shape or relative > 0.01:
        raise SystemExit("Seed-VC length regulator parity gate failed")


if __name__ == "__main__":
    main()
