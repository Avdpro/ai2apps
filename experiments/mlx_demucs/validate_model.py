"""Validate the MLX-native waveform-to-sources HTDemucs forward path."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types

import mlx.core as mx

from .mlx_model import MlxHTDemucs, load_checkpoint
from .mlx_stft import demucs_ispectro, demucs_spectro
from .validate_layers import _error


def validate(
    *,
    model_name: str = "htdemucs",
    length: int = 8192,
    weights: str | None = None,
) -> dict:
    import torch

    if "torchaudio" not in sys.modules:
        sys.modules["torchaudio"] = types.ModuleType("torchaudio")
    from demucs.pretrained import get_model

    if length <= 3072:
        raise ValueError("length must exceed HTDemucs' reflection padding")
    torch.manual_seed(20260905)
    reference_model = get_model(model_name).models[0]
    reference_model.use_train_segment = False
    reference_model.eval()
    state = (
        load_checkpoint(weights)
        if weights
        else {
            name: value.detach().cpu().numpy()
            for name, value in reference_model.state_dict().items()
        }
    )
    implementation = MlxHTDemucs(state)

    mixture_pt = torch.randn(1, 2, length) * 0.05
    mixture_mx = mx.array(mixture_pt.numpy())
    started = time.perf_counter()

    with torch.inference_mode():
        spectrum_pt = reference_model._spec(mixture_pt)
        restored_pt = reference_model._ispec(spectrum_pt, length)
    spectrum_mx = demucs_spectro(mixture_mx)
    restored_mx = demucs_ispectro(spectrum_mx, length=length)
    spectrum_result = _error(spectrum_mx, spectrum_pt)
    inverse_result = _error(restored_mx, restored_pt)

    with torch.inference_mode():
        output_pt = reference_model(mixture_pt)
    output_mx = implementation(mixture_mx, pad_to_segment=False)
    output_result = _error(output_mx, output_pt)
    shape_contract = {
        "actual": list(output_mx.shape),
        "expected": list(output_pt.shape),
    }
    results = {
        "spectrum": spectrum_result,
        "inverse_spectrum": inverse_result,
        "model_output": output_result,
    }
    thresholds = {
        "spectrum": 0.001,
        "inverse_spectrum": 0.001,
        "model_output": 0.05,
    }
    passed = shape_contract["actual"] == shape_contract["expected"] and all(
        item["peak_normalized_error"] < thresholds[name]
        and item["relative_rmse"] < thresholds[name]
        for name, item in results.items()
    )
    return {
        "schema": "ai2apps.mlx-demucs-model-parity/v1",
        "model": model_name,
        "input_samples": length,
        "checkpoint_format": "reference_memory" if weights is None else weights.rsplit(".", 1)[-1],
        "passed": passed,
        "thresholds": thresholds,
        "shape_contract": shape_contract,
        **results,
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="htdemucs")
    parser.add_argument("--length", type=int, default=8192)
    parser.add_argument("--torch-home")
    parser.add_argument("--weights")
    args = parser.parse_args()
    if args.torch_home:
        os.environ["TORCH_HOME"] = args.torch_home
    report = validate(model_name=args.model, length=args.length, weights=args.weights)
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
