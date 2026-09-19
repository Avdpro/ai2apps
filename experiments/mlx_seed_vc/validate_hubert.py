"""Compare Seed-VC's truncated HuBERT frontend between Torch and MLX."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch
from transformers import HubertModel

from .hubert import HubertLayer18


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("converted", type=Path)
    args = parser.parse_args()
    waveform = np.random.default_rng(47).normal(size=(1, 8000)).astype(np.float32)
    waveform = (waveform - waveform.mean(-1, keepdims=True)) / np.sqrt(
        waveform.var(-1, keepdims=True) + 1e-7
    )
    reference_model = HubertModel.from_pretrained(args.source).eval()
    reference_model.encoder.layers = reference_model.encoder.layers[:18]
    reference_model.encoder.layer_norm = torch.nn.Identity()
    with torch.no_grad():
        reference = reference_model(torch.from_numpy(waveform)).last_hidden_state.numpy()
    del reference_model
    model = HubertLayer18.from_directory(args.converted)
    actual = np.asarray(model(mx.array(waveform)))
    relative = float(
        np.sqrt(np.mean((actual - reference) ** 2))
        / max(np.sqrt(np.mean(reference**2)), 1e-12)
    )
    cosine = float(
        np.sum(actual * reference)
        / max(np.linalg.norm(actual) * np.linalg.norm(reference), 1e-12)
    )
    print(f"shape={list(actual.shape)} relative_rmse={relative:.8g} cosine={cosine:.8f}")
    if actual.shape != reference.shape or relative > 0.03 or cosine < 0.999:
        raise SystemExit("HuBERT layer-18 parity gate failed")


if __name__ == "__main__":
    main()
