"""Metal parity validation for first encoder and final decoder blocks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types

import numpy as np

from .mlx_layers import hdec_frequency, hdec_time, henc_frequency, henc_time


def _numpy_state(module, prefix: str = "layer") -> dict[str, np.ndarray]:
    return {
        f"{prefix}.{name}": value.detach().cpu().numpy()
        for name, value in module.state_dict().items()
    }


def _error(actual, expected) -> dict[str, float | list[int]]:
    import mlx.core as mx

    mx.eval(actual)
    actual_np = np.asarray(actual)
    expected_np = expected.detach().cpu().numpy()
    difference = np.abs(actual_np - expected_np)
    expected_peak = float(np.max(np.abs(expected_np), initial=0))
    rmse = float(np.sqrt(np.mean(np.square(difference, dtype=np.float64))))
    reference_rms = float(
        np.sqrt(np.mean(np.square(np.abs(expected_np), dtype=np.float64)))
    )
    return {
        "shape": list(actual_np.shape),
        "max_abs_error": float(np.max(difference, initial=0)),
        "mean_abs_error": float(np.mean(difference)),
        "peak_normalized_error": float(np.max(difference, initial=0))
        / max(expected_peak, 1e-12),
        "relative_rmse": rmse / max(reference_rms, 1e-12),
    }


def validate(*, model_name: str = "htdemucs") -> dict:
    import mlx.core as mx
    import torch

    if "torchaudio" not in sys.modules:
        sys.modules["torchaudio"] = types.ModuleType("torchaudio")
    from demucs.pretrained import get_model

    torch.manual_seed(20260905)
    model = get_model(model_name).models[0]
    started = time.perf_counter()

    time_input = torch.randn(1, 2, 4096) * 0.05
    torch_time_encoder = model.tencoder[0](time_input)
    mlx_time_encoder = henc_time(
        mx.array(time_input.permute(0, 2, 1).numpy()),
        _numpy_state(model.tencoder[0]),
        "layer",
    )
    time_encoder = _error(mlx_time_encoder, torch_time_encoder.permute(0, 2, 1))

    frequency_input = torch.randn(1, 4, 65, 19) * 0.05
    torch_frequency_encoder = model.encoder[0](frequency_input)
    mlx_frequency_encoder = henc_frequency(
        mx.array(frequency_input.permute(0, 2, 3, 1).numpy()),
        _numpy_state(model.encoder[0]),
        "layer",
    )
    frequency_encoder = _error(
        mlx_frequency_encoder,
        torch_frequency_encoder.permute(0, 2, 3, 1),
    )

    time_values = torch.randn(1, 48, 64) * 0.05
    time_skip = torch.randn(1, 48, 64) * 0.05
    torch_time_decoder, torch_time_saved = model.tdecoder[3](
        time_values,
        time_skip,
        256,
    )
    mlx_time_decoder, mlx_time_saved = hdec_time(
        mx.array(time_values.permute(0, 2, 1).numpy()),
        mx.array(time_skip.permute(0, 2, 1).numpy()),
        _numpy_state(model.tdecoder[3]),
        "layer",
        length=256,
        last=True,
    )
    time_decoder = _error(mlx_time_decoder, torch_time_decoder.permute(0, 2, 1))
    time_decoder_saved = _error(mlx_time_saved, torch_time_saved.permute(0, 2, 1))

    frequency_values = torch.randn(1, 48, 17, 11) * 0.05
    frequency_skip = torch.randn(1, 48, 17, 11) * 0.05
    torch_frequency_decoder, torch_frequency_saved = model.decoder[3](
        frequency_values,
        frequency_skip,
        None,
    )
    mlx_frequency_decoder, mlx_frequency_saved = hdec_frequency(
        mx.array(frequency_values.permute(0, 2, 3, 1).numpy()),
        mx.array(frequency_skip.permute(0, 2, 3, 1).numpy()),
        _numpy_state(model.decoder[3]),
        "layer",
        last=True,
    )
    frequency_decoder = _error(
        mlx_frequency_decoder,
        torch_frequency_decoder.permute(0, 2, 3, 1),
    )
    frequency_decoder_saved = _error(
        mlx_frequency_saved,
        torch_frequency_saved.permute(0, 2, 3, 1),
    )

    layers = {
        "time_encoder_0": time_encoder,
        "frequency_encoder_0": frequency_encoder,
        "time_decoder_3": time_decoder,
        "time_decoder_3_saved": time_decoder_saved,
        "frequency_decoder_3": frequency_decoder,
        "frequency_decoder_3_saved": frequency_decoder_saved,
    }
    # Metal and CPU convolution reductions do not have identical accumulation
    # order. Gate on normalized error rather than impossible bit identity.
    passed = all(
        item["peak_normalized_error"] < 0.01 and item["relative_rmse"] < 0.01
        for item in layers.values()
    )
    return {
        "schema": "ai2apps.mlx-demucs-layer-parity/v1",
        "model": model_name,
        "passed": passed,
        "thresholds": {"peak_normalized_error": 0.01, "relative_rmse": 0.01},
        **layers,
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="htdemucs")
    parser.add_argument("--torch-home")
    args = parser.parse_args()
    if args.torch_home:
        os.environ["TORCH_HOME"] = args.torch_home
    report = validate(model_name=args.model)
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
