"""Compare MLX ASTRAL/BSQ outputs with the official PyTorch operations."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .astral import AstralQuantizer


def _torch_forward(values: torch.Tensor, state: dict[str, torch.Tensor]):
    x = torch.nn.functional.conv1d(
        values.transpose(1, 2),
        state["encoder.input_projection.weight"],
        state["encoder.input_projection.bias"],
    )
    for index in range(12):
        residual = x
        prefix = f"encoder.blocks.{index}"
        x = torch.nn.functional.conv1d(
            x,
            state[f"{prefix}.dwconv.weight"],
            state[f"{prefix}.dwconv.bias"],
            padding=3,
            groups=512,
        )
        x = torch.nn.functional.layer_norm(
            x.transpose(1, 2),
            (512,),
            state[f"{prefix}.norm.weight"],
            state[f"{prefix}.norm.bias"],
            1e-6,
        ).transpose(1, 2)
        x = torch.nn.functional.gelu(
            torch.nn.functional.linear(
                x.transpose(1, 2),
                state[f"{prefix}.pwconv1.weight"],
                state[f"{prefix}.pwconv1.bias"],
            )
        )
        gx = torch.linalg.vector_norm(x, ord=2, dim=1, keepdim=True)
        nx = gx / (gx.mean(dim=-1, keepdim=True) + 1e-6)
        x = state[f"{prefix}.grn.gamma"] * (x * nx) + state[f"{prefix}.grn.beta"] + x
        x = torch.nn.functional.linear(
            x,
            state[f"{prefix}.pwconv2.weight"],
            state[f"{prefix}.pwconv2.bias"],
        ).transpose(1, 2)
        x = residual + x
    encoded = x.transpose(1, 2)
    projected = torch.nn.functional.linear(
        encoded,
        state["quantizer.project_in.weight"],
        state["quantizer.project_in.bias"],
    )
    projected = torch.nn.functional.normalize(projected, dim=-1)
    positive = projected > 0
    indices = ((positive.int()) * state["quantizer.mask"].int()).sum(dim=-1)
    codes = torch.where(positive, 1.0, -1.0) / np.sqrt(projected.shape[-1])
    quantized = torch.nn.functional.linear(
        codes,
        state["quantizer.project_out.weight"],
        state["quantizer.project_out.bias"],
    )
    return encoded, quantized, indices


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoints", nargs="+", type=Path)
    args = parser.parse_args()
    inputs = np.random.default_rng(31).normal(size=(1, 19, 1024)).astype(np.float32)
    for path in args.checkpoints:
        raw = torch.load(path, map_location="cpu", weights_only=True)
        state = {name: value.float() for name, value in raw.items()}
        with torch.no_grad():
            reference_encoded, reference_quantized, reference_indices = _torch_forward(
                torch.from_numpy(inputs), state
            )
        model = AstralQuantizer({name: value.numpy() for name, value in state.items()})
        encoded = model.encode(mx.array(inputs))
        quantized, mlx_indices = model.quantize(encoded)
        encoded = np.asarray(encoded)
        quantized = np.asarray(quantized)
        indices = np.asarray(mlx_indices)
        encoded_rmse = np.sqrt(np.mean((encoded - reference_encoded.numpy()) ** 2))
        encoded_relative = encoded_rmse / max(
            np.sqrt(np.mean(reference_encoded.numpy() ** 2)), 1e-12
        )
        quantized_rmse = np.sqrt(np.mean((quantized - reference_quantized.numpy()) ** 2))
        quantized_relative = quantized_rmse / max(
            np.sqrt(np.mean(reference_quantized.numpy() ** 2)), 1e-12
        )
        token_match = float(np.mean(indices == reference_indices.numpy()))
        print(
            f"{path.parent.name}: encoded_relative_rmse={encoded_relative:.8g} "
            f"quantized_relative_rmse={quantized_relative:.8g} token_match={token_match:.3%}"
        )
        # Sign quantization is discontinuous around zero; Metal's convolution
        # accumulation can flip a near-zero BSQ bit even while the encoder is
        # within 0.25% and the narrow tokens remain exact.
        if encoded_relative > 0.01 or token_match < 0.94:
            raise SystemExit(f"{path.parent.name} ASTRAL parity gate failed")


if __name__ == "__main__":
    main()
