"""Validate the complete RVC v2 NSF generator using official weights."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .generator import NSFGenerator
from .validate_primitives import _metrics


def validate(checkpoint: Path, upstream: Path) -> dict[str, object]:
    import mlx.core as mx
    import torch

    sys.path.insert(0, str(upstream))
    try:
        from infer.module.models import GeneratorNSF
    finally:
        sys.path.pop(0)

    state = torch.load(checkpoint, map_location="cpu", weights_only=True)["model"]
    rates = (12, 10, 2, 2)
    kernels = (24, 20, 4, 4)
    torch_model = GeneratorNSF(
        192,
        "1",
        (3, 7, 11),
        ((1, 3, 5),) * 3,
        rates,
        512,
        kernels,
        256,
        48_000,
        is_half=False,
    )
    torch_state = {
        name.removeprefix("dec."): value
        for name, value in state.items()
        if name.startswith("dec.")
    }
    torch_model.load_state_dict(torch_state, strict=True)
    torch_model.eval()
    torch_model.m_source.l_sin_gen.noise_std = 0.0
    numpy_state = {name: value.float().numpy() for name, value in state.items()}
    mlx_model = NSFGenerator(
        numpy_state,
        sample_rate=48_000,
        upsample_rates=rates,
        upsample_kernel_sizes=kernels,
    )

    rng = np.random.default_rng(307)
    latent = rng.normal(size=(1, 192, 6)).astype(np.float32)
    f0 = np.linspace(120.0, 180.0, 6, dtype=np.float32)[None]
    conditioning = rng.normal(size=(1, 256, 1)).astype(np.float32)
    torch_trace = {}
    with torch.no_grad():
        torch_source = (
            torch_model.m_source(torch.from_numpy(f0), torch_model.upp)[0]
            .transpose(1, 2)
            .numpy()
        )
        torch_values = torch_model.conv_pre(torch.from_numpy(latent))
        torch_values += torch_model.cond(torch.from_numpy(conditioning))
        torch_trace["conditioned"] = torch_values.numpy()
        for stage, (upsample, noise_conv) in enumerate(
            zip(torch_model.ups, torch_model.noise_convs)
        ):
            torch_values = torch.nn.functional.leaky_relu(torch_values, 0.1)
            torch_trace[f"stage_{stage}_activated"] = torch_values.numpy()
            torch_values = upsample(torch_values)
            torch_trace[f"stage_{stage}_upsample"] = torch_values.numpy().copy()
            source_stage = noise_conv(torch.from_numpy(torch_source))
            torch_trace[f"stage_{stage}_source"] = source_stage.numpy()
            torch_values += source_stage
            torch_trace[f"stage_{stage}_excited"] = torch_values.numpy()
            branches = [
                torch_model.resblocks[stage * 3 + branch](torch_values)
                for branch in range(3)
            ]
            torch_values = sum(branches) / 3
            torch_trace[f"stage_{stage}_resblocks"] = torch_values.numpy()
        torch_values = torch.nn.functional.leaky_relu(torch_values, 0.1)
        expected = torch.tanh(torch_model.conv_post(torch_values)).numpy()
        torch_weight = torch_model.ups[0].weight.detach().numpy()
    mlx_source = mlx_model._sine_source(mx.array(f0))
    mlx_trace = {}
    actual = mlx_model(
        mx.array(latent), mx.array(f0), mx.array(conditioning), trace=mlx_trace
    )
    mx.eval(mlx_source, actual, *mlx_trace.values())
    source_metrics = _metrics(torch_source, np.asarray(mlx_source))
    weight_metrics = _metrics(
        torch_weight,
        np.asarray(mlx_model._get("ups.0.weight")),
    )
    metrics = _metrics(expected, np.asarray(actual))
    trace_metrics = {
        name: _metrics(torch_trace[name], np.asarray(value))
        for name, value in mlx_trace.items()
    }
    if metrics["relative_rmse"] > 0.03 or metrics["peak_normalized_error"] > 0.03:
        raise AssertionError(
            "NSF generator parity failed: "
            f"weight={weight_metrics}, source={source_metrics}, "
            f"trace={trace_metrics}, output={metrics}"
        )
    return {
        "source": source_metrics,
        "weight": weight_metrics,
        "trace": trace_metrics,
        "output": metrics,
        "shape": list(expected.shape),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--upstream", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(validate(arguments.checkpoint, arguments.upstream), indent=2))


if __name__ == "__main__":
    main()
