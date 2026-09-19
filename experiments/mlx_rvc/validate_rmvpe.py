"""Compare the native MLX RMVPE network with the pinned PyTorch oracle."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
from pathlib import Path

import mlx.core as mx
import numpy as np
import torch

from .checkpoint import export_rmvpe_checkpoint
from .rmvpe import RMVPE


def metric(reference: np.ndarray, actual: np.ndarray) -> float:
    return float(
        np.sqrt(np.mean((actual - reference) ** 2))
        / max(np.sqrt(np.mean(reference**2)), 1e-12)
    )


def load_oracle(upstream: Path, checkpoint: Path):
    sys.path.insert(0, str(upstream))
    spec = importlib.util.spec_from_file_location(
        "rvc_rmvpe_oracle", upstream / "infer/rmvpe.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    model = module.E2E(4, 1, (2, 2))
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    return model.float().eval(), module.MelSpectrogram(
        False, 128, 16000, 1024, 160, None, 30, 8000
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    args = parser.parse_args()
    oracle, oracle_mel = load_oracle(args.upstream, args.checkpoint)
    rng = np.random.default_rng(11)
    audio = rng.normal(0, 0.1, 16000).astype(np.float32)
    with torch.no_grad():
        reference_mel = oracle_mel(torch.from_numpy(audio)[None]).numpy()
        frames = reference_mel.shape[-1]
        pad = 32 * ((frames - 1) // 32 + 1) - frames
        padded = torch.nn.functional.pad(torch.from_numpy(reference_mel), (0, pad))
        oracle_input = padded.transpose(-1, -2).unsqueeze(1)
        reference_unet = oracle.unet(oracle_input)
        reference_cnn = oracle.cnn(reference_unet).transpose(1, 2).flatten(-2)
        reference_gru = oracle.fc[0](reference_cnn)
        reference = oracle.fc(reference_cnn).numpy()[:, :frames]
    with tempfile.TemporaryDirectory(prefix="mlx-rvc-rmvpe-") as temporary:
        root = Path(temporary)
        export_rmvpe_checkpoint(args.checkpoint, root / "model.safetensors")
        model = RMVPE.from_directory(root)
        actual_mel = np.asarray(model.mel_spectrogram(mx.array(audio)))
        actual = np.asarray(
            model.model(mx.array(np.pad(reference_mel, ((0, 0), (0, 0), (0, pad)))))
        )[:, :frames]
        mlx_input = mx.array(
            np.pad(reference_mel, ((0, 0), (0, 0), (0, pad)))
        ).transpose(0, 2, 1)[..., None]
        mlx_unet = model.model.unet(mlx_input)
        mlx_cnn = (
            model.model.cnn(mlx_unet)
            .transpose(0, 1, 3, 2)
            .reshape(1, mlx_input.shape[1], 384)
        )
        mlx_gru = mx.concatenate(
            (
                model.model.gru_forward(mlx_cnn),
                mx.flip(model.model.gru_reverse(mx.flip(mlx_cnn, axis=1)), axis=1),
            ),
            axis=-1,
        )
        mel_error = metric(reference_mel, actual_mel)
        network_error = metric(reference, actual)
        print(f"mel_shape={list(actual_mel.shape)}")
        print(f"mel_relative_rmse={mel_error:.8g}")
        print(f"network_shape={list(actual.shape)}")
        print(f"network_relative_rmse={network_error:.8g}")
        print(
            "unet_relative_rmse="
            f"{metric(reference_unet.numpy().transpose(0, 2, 3, 1), np.asarray(mlx_unet)):.8g}"
        )
        print(
            f"cnn_relative_rmse={metric(reference_cnn.numpy(), np.asarray(mlx_cnn)):.8g}"
        )
        print(
            f"gru_relative_rmse={metric(reference_gru.numpy(), np.asarray(mlx_gru)):.8g}"
        )
        if actual.shape != reference.shape or mel_error > 0.001 or network_error > 0.01:
            raise SystemExit("RMVPE parity gate failed")


if __name__ == "__main__":
    main()
