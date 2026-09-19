"""Validate HTDemucs positional embeddings and cross-domain Transformer."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types

import mlx.core as mx

from .mlx_transformer import cross_transformer, sin_embedding, sin_embedding_2d
from .validate_layers import _error, _numpy_state


def validate(*, model_name: str = "htdemucs") -> dict:
    import torch

    if "torchaudio" not in sys.modules:
        sys.modules["torchaudio"] = types.ModuleType("torchaudio")
    from demucs.pretrained import get_model
    from demucs.transformer import create_2d_sin_embedding, create_sin_embedding

    torch.manual_seed(20260905)
    model = get_model(model_name).models[0]
    transformer = model.crosstransformer
    state = _numpy_state(transformer, prefix="transformer")
    started = time.perf_counter()

    reference_1d = create_sin_embedding(7, 512).permute(1, 0, 2)
    actual_1d = sin_embedding(7, 512)
    embedding_1d = _error(actual_1d, reference_1d)

    reference_2d = create_2d_sin_embedding(512, 3, 5).permute(0, 2, 3, 1)
    actual_2d = sin_embedding_2d(3, 5, 512)
    embedding_2d = _error(actual_2d, reference_2d)

    frequency_pt = torch.randn(1, 512, 3, 5) * 0.05
    time_pt = torch.randn(1, 512, 7) * 0.05
    with torch.inference_mode():
        frequency_reference, time_reference = transformer(frequency_pt, time_pt)
    frequency_actual, time_actual = cross_transformer(
        mx.array(frequency_pt.permute(0, 2, 3, 1).numpy()),
        mx.array(time_pt.permute(0, 2, 1).numpy()),
        state,
        "transformer",
    )
    frequency_result = _error(
        frequency_actual,
        frequency_reference.permute(0, 2, 3, 1),
    )
    time_result = _error(time_actual, time_reference.permute(0, 2, 1))
    results = {
        "embedding_1d": embedding_1d,
        "embedding_2d": embedding_2d,
        "frequency_output": frequency_result,
        "time_output": time_result,
    }
    passed = all(
        item["peak_normalized_error"] < 0.01 and item["relative_rmse"] < 0.01
        for item in results.values()
    )
    return {
        "schema": "ai2apps.mlx-demucs-transformer-parity/v1",
        "model": model_name,
        "passed": passed,
        "thresholds": {"peak_normalized_error": 0.01, "relative_rmse": 0.01},
        **results,
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
