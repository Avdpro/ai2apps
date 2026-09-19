"""Validate the combined MLX RVC encoder, reverse flow, and NSF decoder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .synthesizer import RVCSynthesizer
from .validate_primitives import _metrics


def validate(checkpoint: Path, upstream: Path) -> dict[str, object]:
    import mlx.core as mx
    import torch

    sys.path.insert(0, str(upstream))
    try:
        from infer.module.models import GeneratorNSF, ResidualCouplingBlock, TextEncoder
    finally:
        sys.path.pop(0)

    state = torch.load(checkpoint, map_location="cpu", weights_only=True)["model"]
    encoder = TextEncoder(768, 192, 192, 768, 2, 6, 3, 0.0, f0=True).eval()
    encoder.load_state_dict(
        {
            name.removeprefix("enc_p."): value
            for name, value in state.items()
            if name.startswith("enc_p.")
        },
        strict=True,
    )
    flow = ResidualCouplingBlock(192, 192, 5, 1, 3, gin_channels=256).eval()
    flow.load_state_dict(
        {
            name.removeprefix("flow."): value
            for name, value in state.items()
            if name.startswith("flow.")
        },
        strict=True,
    )
    decoder = GeneratorNSF(
        192,
        "1",
        (3, 7, 11),
        ((1, 3, 5),) * 3,
        (12, 10, 2, 2),
        512,
        (24, 20, 4, 4),
        256,
        48_000,
        is_half=False,
    ).eval()
    decoder.load_state_dict(
        {
            name.removeprefix("dec."): value
            for name, value in state.items()
            if name.startswith("dec.")
        },
        strict=True,
    )
    decoder.m_source.l_sin_gen.noise_std = 0.0

    rng = np.random.default_rng(419)
    phone = rng.normal(size=(1, 13, 768)).astype(np.float32)
    pitch = rng.integers(1, 256, size=(1, 13), dtype=np.int64)
    continuous_f0 = np.linspace(130.0, 210.0, 13, dtype=np.float32)[None]
    latent_noise = rng.normal(size=(1, 192, 13)).astype(np.float32)
    speaker_id = 0
    with torch.no_grad():
        mean, log_scale, mask = encoder(
            torch.from_numpy(phone),
            torch.from_numpy(pitch),
            torch.tensor([phone.shape[1]]),
        )
        latent = (
            mean + torch.exp(log_scale) * torch.from_numpy(latent_noise) * 0.66666
        ) * mask
        conditioning = state["emb_g.weight"][speaker_id].float()[None, :, None]
        decoded = flow(latent, mask, g=conditioning, reverse=True)
        expected = decoder(
            decoded * mask, torch.from_numpy(continuous_f0), g=conditioning
        ).numpy()

    numpy_state = {name: value.float().numpy() for name, value in state.items()}
    mlx_model = RVCSynthesizer(numpy_state)
    mlx_trace = {}
    actual = mlx_model(
        mx.array(phone),
        mx.array(pitch),
        mx.array(continuous_f0),
        speaker_id,
        mx.array(latent_noise),
        trace=mlx_trace,
    )
    mx.eval(actual, *mlx_trace.values())
    trace_metrics = {
        "mean": _metrics(mean.numpy(), np.asarray(mlx_trace["mean"])),
        "log_scale": _metrics(log_scale.numpy(), np.asarray(mlx_trace["log_scale"])),
        "latent": _metrics(latent.numpy(), np.asarray(mlx_trace["latent"])),
        "decoded": _metrics(decoded.numpy(), np.asarray(mlx_trace["decoded"])),
    }
    metrics = _metrics(expected, np.asarray(actual))
    metrics["error_snr_db"] = float(
        -20.0 * np.log10(max(metrics["relative_rmse"], 1e-12))
    )
    # The NSF decoder is phase-sensitive: sub-0.04% upstream latent differences
    # amplify in pointwise waveform space while every individual decoder block
    # remains below 0.4%. Use a 5% integrated waveform gate and retain the
    # stricter per-block gates in validate_generator.py.
    if metrics["relative_rmse"] > 0.05 or metrics["peak_normalized_error"] > 0.05:
        raise AssertionError(
            f"RVC synthesizer parity failed: trace={trace_metrics}, output={metrics}"
        )
    return {"trace": trace_metrics, "output": metrics, "shape": list(expected.shape)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(validate(arguments.checkpoint, arguments.upstream), indent=2))


if __name__ == "__main__":
    main()
