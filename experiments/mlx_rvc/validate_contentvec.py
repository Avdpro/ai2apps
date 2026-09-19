"""Compare MLX ContentVec with the pinned Transformers HuBERT oracle."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch
from transformers import HubertModel

from .checkpoint import export_hubert_checkpoint
from .contentvec import ContentVec


def metrics(reference: np.ndarray, actual: np.ndarray) -> tuple[float, float]:
    error = actual - reference
    rmse = np.sqrt(np.mean(error**2))
    relative = rmse / max(np.sqrt(np.mean(reference**2)), 1e-12)
    peak = np.max(np.abs(error)) / max(np.max(np.abs(reference)), 1e-12)
    return float(relative), float(peak)


def cosine_similarity(reference: np.ndarray, actual: np.ndarray) -> float:
    reference_flat = reference.reshape(-1).astype(np.float64)
    actual_flat = actual.reshape(-1).astype(np.float64)
    return float(
        np.dot(reference_flat, actual_flat)
        / (np.linalg.norm(reference_flat) * np.linalg.norm(actual_flat))
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("--seconds", type=float, default=1.25)
    args = parser.parse_args()
    torch.manual_seed(7)
    audio = torch.randn(1, int(16_000 * args.seconds), dtype=torch.float32)
    audio = (audio - audio.mean(-1, keepdim=True)) / torch.sqrt(
        audio.var(-1, keepdim=True, unbiased=False) + 1e-7
    )

    oracle = (
        HubertModel.from_pretrained(args.model_dir, local_files_only=True)
        .float()
        .eval()
    )
    with torch.no_grad():
        oracle_output = oracle(audio, output_hidden_states=True)
        reference = oracle_output.last_hidden_state.cpu().numpy()

    with tempfile.TemporaryDirectory(prefix="mlx-rvc-hubert-") as temporary:
        output = Path(temporary)
        manifest = export_hubert_checkpoint(
            args.model_dir / "pytorch_model.bin",
            args.model_dir / "config.json",
            output / "model.safetensors",
        )
        model = ContentVec.from_directory(output)
        actual = np.asarray(model(mx.array(audio.numpy()), version="v2"))
        mlx_output = model.model(
            mx.array(audio.numpy()), output_hidden_states=True, return_dict=True
        )
        for index, (torch_hidden, mlx_hidden) in enumerate(
            zip(oracle_output.hidden_states, mlx_output.hidden_states, strict=True)
        ):
            layer_relative, _ = metrics(
                torch_hidden.detach().cpu().numpy(), np.asarray(mlx_hidden)
            )
            print(f"layer_{index}_relative_rmse={layer_relative:.8g}")
        relative, peak = metrics(reference, actual)
        cosine = cosine_similarity(reference, actual)
        print(f"shape={list(actual.shape)}")
        print(f"relative_rmse={relative:.8g}")
        print(f"peak_normalized_error={peak:.8g}")
        print(f"cosine_similarity={cosine:.8g}")
        print(f"parameter_count={manifest['weights']['parameter_count']}")
        if (
            actual.shape != reference.shape
            or relative > 0.03
            or peak > 0.03
            or cosine < 0.999
        ):
            raise SystemExit("ContentVec parity gate failed")


if __name__ == "__main__":
    main()
