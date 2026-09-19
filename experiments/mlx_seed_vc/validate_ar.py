"""Compare the MLX Seed-VC v2 AR logits with the official Torch model."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .ar import SeedVCAR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    state = checkpoint["net"]["ar"]
    spec = importlib.util.spec_from_file_location("seed_vc_v2_ar", args.upstream / "modules/v2/ar.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    config = module.NaiveModelArgs(
        dim=768, head_dim=64, n_local_heads=2, intermediate_size=2304,
        n_head=12, n_layer=12, vocab_size=2049, dropout=0.0,
    )
    reference_model = module.NaiveWrapper(module.NaiveTransformer(config)).eval()
    reference_model.load_state_dict(state, strict=False)
    inputs = torch.tensor(np.random.default_rng(41).normal(size=(1, 11, 768)).astype(np.float32))
    positions = torch.tensor([[0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 5]])
    with torch.no_grad():
        reference_result = module.BaseTransformer.forward(
            reference_model.model, inputs, input_pos=positions
        )
        # Generation deliberately uses the independently trained output head,
        # whereas the training forward path uses tied input embeddings.
        normalized = reference_model.model.norm(reference_result.hidden_states)
        reference = reference_model.model.output(normalized).numpy()
    model = SeedVCAR({name: value.numpy() for name, value in state.items()})
    actual, _ = model.forward(mx.array(inputs.numpy()), mx.array(positions.numpy()))
    actual = np.asarray(actual)
    relative = float(
        np.sqrt(np.mean((actual - reference) ** 2))
        / max(np.sqrt(np.mean(reference**2)), 1e-12)
    )
    top1 = float(np.mean(actual.argmax(-1) == reference.argmax(-1)))
    print(f"shape={list(actual.shape)} relative_rmse={relative:.8g} top1_parity={top1:.3%}")
    if actual.shape != reference.shape or relative > 0.01 or top1 != 1.0:
        raise SystemExit("Seed-VC v2 AR parity gate failed")


if __name__ == "__main__":
    main()
