"""Validate both Seed-VC v2 discrete length regulators against PyTorch."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .length_regulator import DiscreteLengthRegulator


def _oracle(tokens: torch.Tensor, state: dict[str, torch.Tensor], output_length: int | None):
    values = torch.nn.functional.embedding(tokens, state["embedding.weight"])
    if output_length is None:
        return values
    values = torch.nn.functional.interpolate(
        values.transpose(1, 2), size=output_length, mode="nearest"
    )
    conv_indices = sorted(
        int(name.split(".")[1])
        for name, value in state.items()
        if name.startswith("model.") and name.endswith(".weight") and value.ndim == 3
    )
    for conv_index in conv_indices:
        values = torch.nn.functional.conv1d(
            values,
            state[f"model.{conv_index}.weight"],
            state.get(f"model.{conv_index}.bias"),
            padding=1,
        )
        norm_index = conv_index + 1
        if f"model.{norm_index}.weight" in state:
            values = torch.nn.functional.group_norm(
                values,
                1,
                state[f"model.{norm_index}.weight"],
                state[f"model.{norm_index}.bias"],
            )
            values = torch.nn.functional.mish(values)
    return values.transpose(1, 2)


def _validate(path: Path, component: str, codebook: int, output_length: int | None) -> None:
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    raw = checkpoint["net"][component]
    state = {name.removeprefix("module."): value.float() for name, value in raw.items()}
    tokens = torch.tensor(np.random.default_rng(codebook).integers(0, codebook, (1, 31)))
    reference = _oracle(tokens, state, output_length).numpy()
    actual = np.asarray(
        DiscreteLengthRegulator({name: value.numpy() for name, value in state.items()})(
            mx.array(tokens.numpy()), output_length
        )
    )
    relative = float(
        np.sqrt(np.mean((actual - reference) ** 2))
        / max(np.sqrt(np.mean(reference**2)), 1e-12)
    )
    print(f"{component}: shape={list(actual.shape)} relative_rmse={relative:.8g}")
    if actual.shape != reference.shape or relative > 0.01:
        raise SystemExit(f"{component} parity gate failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cfm_checkpoint", type=Path)
    parser.add_argument("ar_checkpoint", type=Path)
    args = parser.parse_args()
    _validate(args.cfm_checkpoint, "length_regulator", 2048, 47)
    _validate(args.ar_checkpoint, "length_regulator", 32, None)


if __name__ == "__main__":
    main()
