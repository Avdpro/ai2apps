"""Validate the complete four-depth convolutional and Transformer shape flow."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types

import mlx.core as mx

from .mlx_layers import (
    add_frequency_embedding,
    channel_projection,
    hdec_frequency,
    hdec_time,
    henc_frequency,
    henc_time,
)
from .mlx_transformer import cross_transformer
from .validate_layers import _error, _numpy_state


def validate(*, model_name: str = "htdemucs") -> dict:
    import torch

    if "torchaudio" not in sys.modules:
        sys.modules["torchaudio"] = types.ModuleType("torchaudio")
    from demucs.pretrained import get_model

    torch.manual_seed(20260905)
    model = get_model(model_name).models[0]
    state = _numpy_state(model, prefix="model")
    started = time.perf_counter()

    frequency_pt = torch.randn(1, 4, 2048, 8) * 0.05
    time_pt = torch.randn(1, 2, 8192) * 0.05
    frequency_mx = mx.array(frequency_pt.permute(0, 2, 3, 1).numpy())
    time_mx = mx.array(time_pt.permute(0, 2, 1).numpy())

    frequency_saved_pt = []
    frequency_saved_mx = []
    time_saved_pt = []
    time_saved_mx = []
    frequency_lengths = []
    time_lengths = []
    layers: dict[str, dict] = {}

    for index in range(4):
        frequency_lengths.append(frequency_pt.shape[-1])
        time_lengths.append(time_pt.shape[-1])
        time_pt = model.tencoder[index](time_pt)
        time_mx = henc_time(time_mx, state, f"model.tencoder.{index}")
        frequency_pt = model.encoder[index](frequency_pt)
        frequency_mx = henc_frequency(
            frequency_mx,
            state,
            f"model.encoder.{index}",
        )
        if index == 0:
            frequencies = torch.arange(frequency_pt.shape[-2])
            embedding = model.freq_emb(frequencies).t()[None, :, :, None]
            frequency_pt = frequency_pt + model.freq_emb_scale * embedding
            frequency_mx = add_frequency_embedding(frequency_mx, state, prefix="model.freq_emb.embedding")
        layers[f"time_encoder_{index}"] = _error(
            time_mx,
            time_pt.permute(0, 2, 1),
        )
        layers[f"frequency_encoder_{index}"] = _error(
            frequency_mx,
            frequency_pt.permute(0, 2, 3, 1),
        )
        time_saved_pt.append(time_pt)
        time_saved_mx.append(time_mx)
        frequency_saved_pt.append(frequency_pt)
        frequency_saved_mx.append(frequency_mx)

    # Validate all four 1x1 projections around the future Transformer boundary.
    batch, frequencies, frames, channels = frequency_mx.shape
    flattened_mx = frequency_mx.reshape((batch, frequencies * frames, channels))
    projected_frequency_mx = channel_projection(
        flattened_mx,
        state,
        "model.channel_upsampler",
    )
    projected_frequency_pt = model.channel_upsampler(frequency_pt.flatten(2)).permute(0, 2, 1)
    layers["channel_upsampler"] = _error(projected_frequency_mx, projected_frequency_pt)
    projected_time_mx = channel_projection(time_mx, state, "model.channel_upsampler_t")
    projected_time_pt = model.channel_upsampler_t(time_pt).permute(0, 2, 1)
    layers["channel_upsampler_t"] = _error(projected_time_mx, projected_time_pt)

    projected_frequency_mx = projected_frequency_mx.reshape(
        (batch, frequencies, frames, 512)
    )
    projected_frequency_pt = projected_frequency_pt.permute(0, 2, 1).reshape(
        (batch, 512, frequencies, frames)
    )
    with torch.no_grad():
        transformed_frequency_pt, transformed_time_pt = model.crosstransformer(
            projected_frequency_pt,
            projected_time_pt.permute(0, 2, 1),
        )
    transformed_frequency_mx, transformed_time_mx = cross_transformer(
        projected_frequency_mx,
        projected_time_mx,
        state,
        "model.crosstransformer",
    )
    layers["cross_transformer_frequency"] = _error(
        transformed_frequency_mx,
        transformed_frequency_pt.permute(0, 2, 3, 1),
    )
    layers["cross_transformer_time"] = _error(
        transformed_time_mx,
        transformed_time_pt.permute(0, 2, 1),
    )

    restored_frequency_mx = channel_projection(
        transformed_frequency_mx.reshape((batch, frequencies * frames, 512)),
        state,
        "model.channel_downsampler",
    )
    restored_frequency_pt = model.channel_downsampler(
        transformed_frequency_pt.flatten(2)
    ).permute(0, 2, 1)
    layers["channel_downsampler"] = _error(restored_frequency_mx, restored_frequency_pt)
    frequency_mx = restored_frequency_mx.reshape((batch, frequencies, frames, channels))
    frequency_pt = restored_frequency_pt.permute(0, 2, 1).reshape(
        (batch, channels, frequencies, frames)
    )

    restored_time_mx = channel_projection(
        transformed_time_mx,
        state,
        "model.channel_downsampler_t",
    )
    restored_time_pt = model.channel_downsampler_t(
        transformed_time_pt
    ).permute(0, 2, 1)
    layers["channel_downsampler_t"] = _error(restored_time_mx, restored_time_pt)
    time_mx = restored_time_mx
    time_pt = restored_time_pt.permute(0, 2, 1)

    for index in range(4):
        frequency_skip_pt = frequency_saved_pt.pop()
        frequency_skip_mx = frequency_saved_mx.pop()
        frequency_pt, _ = model.decoder[index](
            frequency_pt,
            frequency_skip_pt,
            frequency_lengths.pop(),
        )
        frequency_mx, _ = hdec_frequency(
            frequency_mx,
            frequency_skip_mx,
            state,
            f"model.decoder.{index}",
            last=index == 3,
        )
        layers[f"frequency_decoder_{index}"] = _error(
            frequency_mx,
            frequency_pt.permute(0, 2, 3, 1),
        )

        time_skip_pt = time_saved_pt.pop()
        time_skip_mx = time_saved_mx.pop()
        target_length = time_lengths.pop()
        time_pt, _ = model.tdecoder[index](time_pt, time_skip_pt, target_length)
        time_mx, _ = hdec_time(
            time_mx,
            time_skip_mx,
            state,
            f"model.tdecoder.{index}",
            length=target_length,
            last=index == 3,
        )
        layers[f"time_decoder_{index}"] = _error(time_mx, time_pt.permute(0, 2, 1))

    shape_contract = {
        "frequency_output": list(frequency_mx.shape),
        "time_output": list(time_mx.shape),
        "frequency_expected": [1, 2048, 8, 16],
        "time_expected": [1, 8192, 8],
    }
    shapes_pass = (
        shape_contract["frequency_output"] == shape_contract["frequency_expected"]
        and shape_contract["time_output"] == shape_contract["time_expected"]
    )
    # Sequential error naturally compounds over the complete network. This
    # remains looser than isolated-block parity but is tight enough to reject
    # layout, ordering, attention, or skip-connection mistakes.
    numeric_pass = all(
        item["peak_normalized_error"] < 0.03 and item["relative_rmse"] < 0.03
        for item in layers.values()
    )
    return {
        "schema": "ai2apps.mlx-demucs-stack-parity/v1",
        "model": model_name,
        "passed": shapes_pass and numeric_pass,
        "thresholds": {"peak_normalized_error": 0.03, "relative_rmse": 0.03},
        "shape_contract": shape_contract,
        "layers": layers,
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
