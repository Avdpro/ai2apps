"""Compare CAMPPlus official Torch and MLX style embeddings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .campplus import CAMPPlus


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream))
    from modules.campplus.DTDNN import CAMPPlus as TorchCAMPPlus

    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    reference_model = TorchCAMPPlus(feat_dim=80, embedding_size=192).eval()
    reference_model.load_state_dict(state)
    features = np.random.default_rng(59).normal(size=(1, 201, 80)).astype(np.float32)
    lengths = np.array([100], dtype=np.int64)
    with torch.no_grad():
        reference = reference_model(
            torch.from_numpy(features), torch.from_numpy(lengths)
        ).numpy()
    model = CAMPPlus({name: value.float().numpy() for name, value in state.items()})
    actual = np.asarray(model(mx.array(features), mx.array(lengths)))
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
        raise SystemExit("CAMPPlus parity gate failed")


if __name__ == "__main__":
    main()
