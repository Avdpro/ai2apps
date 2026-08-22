# SPDX-License-Identifier: Apache-2.0
"""Tests for the first independently publishable model-adapter package."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import mlx.core as mx
import pytest

PACKAGE_SRC = (
    Path(__file__).parents[1]
    / "packages"
    / "omlx-model-qwen38"
    / "src"
)
sys.path.insert(0, str(PACKAGE_SRC))

from omlx_model_qwen38 import (  # noqa: E402
    Qwen38Adapter,
    dequantize_fp8_weights,
    is_qwen38_config,
)

from omlx.model_adapters import adapter_context  # noqa: E402


def _qwen38_config():
    return {
        "architectures": ["Qwen3_5ForConditionalGeneration"],
        "language_model_only": False,
        "model_type": "qwen3_5",
        "text_config": {
            "hidden_size": 5120,
            "model_type": "qwen3_5_text",
            "num_hidden_layers": 64,
            "output_gate_type": "swish",
        },
        "vision_config": {"hidden_size": 1152},
    }


def test_matches_official_qwen38_contract_and_classifies_vlm(tmp_path):
    config = _qwen38_config()
    adapter = Qwen38Adapter()

    assert is_qwen38_config(config) is True
    context = adapter_context(tmp_path, config)
    assert adapter.match(context) is True
    assert adapter.classify(context) == "vlm"


def test_does_not_misclassify_qwen35_27b(tmp_path):
    config = _qwen38_config()
    config.pop("language_model_only")
    config["text_config"].pop("output_gate_type")

    assert is_qwen38_config(config) is False
    assert Qwen38Adapter().match(adapter_context(tmp_path, config)) is False


def test_adapter_discovery_does_not_import_mlx():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from omlx_model_qwen38.adapter import Qwen38Adapter; "
                "assert 'mlx.core' not in sys.modules; "
                "print(Qwen38Adapter.adapter_id)"
            ),
        ],
        env={"PYTHONPATH": f"{PACKAGE_SRC}:{Path(__file__).parents[1]}"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "qwen38"


def test_block_fp8_dequantization():
    weight_key = "model.language_model.layers.0.self_attn.q_proj.weight"
    weights = {
        weight_key: mx.to_fp8(mx.ones((130, 129), dtype=mx.float32)),
        f"{weight_key}_scale_inv": mx.array(
            [[0.5, 1.0], [2.0, 4.0]], dtype=mx.bfloat16
        ),
    }

    output = dequantize_fp8_weights(weights)
    expected = mx.ones((130, 129), dtype=mx.bfloat16)
    expected[:128, :128] *= 0.5
    expected[:128, 128:] *= 1.0
    expected[128:, :128] *= 2.0
    expected[128:, 128:] *= 4.0

    assert not any(key.endswith("weight_scale_inv") for key in output)
    assert output[weight_key].dtype == mx.bfloat16
    assert mx.array_equal(output[weight_key], expected).item()


def test_block_fp8_rejects_invalid_scale_grid():
    with pytest.raises(ValueError, match="Invalid FP8 scale shape"):
        dequantize_fp8_weights(
            {
                "proj.weight": mx.to_fp8(mx.ones((129, 129))),
                "proj.weight_scale_inv": mx.ones((1, 2)),
            }
        )
