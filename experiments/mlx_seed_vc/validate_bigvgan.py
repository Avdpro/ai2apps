"""Compare NVIDIA BigVGAN v2 waveform output between Torch and MLX."""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .bigvgan import load_bigvgan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("converted", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.upstream))
    utility = types.ModuleType("modules.bigvgan.utils")
    utility.get_padding = lambda kernel_size, dilation=1: int(
        (kernel_size * dilation - dilation) / 2
    )
    utility.init_weights = lambda module, mean=0.0, std=0.01: None
    sys.modules["modules.bigvgan.utils"] = utility
    from modules.bigvgan.bigvgan import BigVGAN
    from modules.bigvgan.env import AttrDict

    configuration = AttrDict(json.loads((args.source / "config.json").read_text()))
    reference_model = BigVGAN(configuration, use_cuda_kernel=False).eval()
    checkpoint = torch.load(
        args.source / "bigvgan_generator.pt", map_location="cpu", weights_only=True
    )
    reference_model.load_state_dict(checkpoint["generator"])
    mel = np.random.default_rng(61).normal(size=(1, 80, 4)).astype(np.float32)
    with torch.no_grad():
        reference = reference_model(torch.from_numpy(mel)).numpy()
    del reference_model
    model = load_bigvgan(args.converted)
    actual = np.asarray(model(mx.array(mel)))
    relative = float(
        np.sqrt(np.mean((actual - reference) ** 2))
        / max(np.sqrt(np.mean(reference**2)), 1e-12)
    )
    cosine = float(
        np.sum(actual * reference)
        / max(np.linalg.norm(actual) * np.linalg.norm(reference), 1e-12)
    )
    print(f"shape={list(actual.shape)} relative_rmse={relative:.8g} cosine={cosine:.8f}")
    if actual.shape != reference.shape or relative > 0.05 or cosine < 0.998:
        raise SystemExit("BigVGAN parity gate failed")


if __name__ == "__main__":
    main()
