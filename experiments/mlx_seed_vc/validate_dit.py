"""Compare the Seed-VC v2 CFM DiT between official Torch and MLX."""

from __future__ import annotations

import argparse
import sys
import types
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .dit import SeedVCDiT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream))
    commons = types.ModuleType("modules.commons")
    commons.sequence_mask = lambda lengths, max_length=None: (
        torch.arange(max_length or int(lengths.max()))[None].to(lengths.device)
        < lengths[:, None]
    )
    sys.modules["modules.commons"] = commons
    from modules.v2.dit_wrapper import DiT

    raw = torch.load(args.checkpoint, map_location="cpu", weights_only=True)["net"]["cfm"]
    state = {
        name.removeprefix("module.estimator."): value
        for name, value in raw.items()
        if name.startswith("module.estimator.")
    }
    reference_model = DiT(
        time_as_token=True, style_as_token=True, uvit_skip_connection=False,
        block_size=8192, depth=13, num_heads=8, hidden_dim=512,
        in_channels=80, content_dim=512, style_encoder_dim=192,
        class_dropout_prob=0.1, dropout_rate=0.0, attn_dropout_rate=0.0,
    ).eval()
    reference_model.load_state_dict(state, strict=False)
    rng = np.random.default_rng(53)
    x = rng.normal(size=(1, 80, 17)).astype(np.float32)
    prompt = rng.normal(size=(1, 80, 17)).astype(np.float32)
    condition = rng.normal(size=(1, 17, 512)).astype(np.float32)
    style = rng.normal(size=(1, 192)).astype(np.float32)
    lengths = np.array([15], dtype=np.int64)
    time = np.array([0.37], dtype=np.float32)
    with torch.no_grad():
        reference = reference_model(
            torch.from_numpy(x), torch.from_numpy(prompt), torch.from_numpy(lengths),
            torch.from_numpy(time), torch.from_numpy(style), torch.from_numpy(condition),
        ).numpy()
    model = SeedVCDiT({name: value.float().numpy() for name, value in raw.items()})
    actual = np.asarray(model(
        mx.array(x), mx.array(prompt), mx.array(lengths), mx.array(time),
        mx.array(style), mx.array(condition),
    ))
    relative = float(
        np.sqrt(np.mean((actual - reference) ** 2))
        / max(np.sqrt(np.mean(reference**2)), 1e-12)
    )
    cosine = float(
        np.sum(actual * reference)
        / max(np.linalg.norm(actual) * np.linalg.norm(reference), 1e-12)
    )
    print(f"shape={list(actual.shape)} relative_rmse={relative:.8g} cosine={cosine:.8f}")
    if actual.shape != reference.shape or relative > 0.02 or cosine < 0.999:
        raise SystemExit("Seed-VC v2 DiT parity gate failed")


if __name__ == "__main__":
    main()
