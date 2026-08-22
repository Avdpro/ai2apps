# SPDX-License-Identifier: Apache-2.0
"""Tests for the independently packaged Qwen3.8 mixed ModelOpt loader."""

from __future__ import annotations

import copy
import sys
import tomllib
from pathlib import Path
from unittest.mock import MagicMock

import mlx.core as mx
import pytest
import yaml

PACKAGE_SRC = Path(__file__).parents[1] / "packages" / "omlx-model-qwen38" / "src"
sys.path.insert(0, str(PACKAGE_SRC))

from omlx_model_qwen38 import Qwen38Adapter  # noqa: E402
from omlx_model_qwen38 import modelopt_config as config_gate  # noqa: E402
from omlx_model_qwen38 import modelopt_mixed as bridge  # noqa: E402

from omlx.model_adapters import adapter_context  # noqa: E402
from ai2apps.packages.archive import ServicePackageArchive  # noqa: E402


def _config() -> dict:
    return {
        "architectures": ["Qwen3_5ForConditionalGeneration"],
        "language_model_only": False,
        "model_type": "qwen3_5",
        "text_config": {
            "hidden_size": 5120,
            "num_hidden_layers": 64,
            "output_gate_type": "swish",
        },
        "vision_config": {
            "model_type": "qwen3_5_vision",
            "hidden_size": 1152,
            "out_hidden_size": 5120,
        },
        "quantization_config": {
            "quant_method": "compressed-tensors",
            "format": "mixed-precision",
            "config_groups": {
                "group_0": {
                    "format": "float-quantized",
                    "targets": list(config_gate._FP8_TARGETS),
                    "weights": {
                        "type": "float",
                        "num_bits": 8,
                        "strategy": "channel",
                        "group_size": None,
                        "dynamic": False,
                        "symmetric": True,
                    },
                },
                "group_1": {
                    "format": "nvfp4-pack-quantized",
                    "targets": list(config_gate._NVFP4_TARGETS),
                    "weights": {
                        "type": "float",
                        "num_bits": 4,
                        "strategy": "tensor_group",
                        "group_size": 16,
                        "dynamic": False,
                        "symmetric": True,
                    },
                },
            },
        },
    }


def test_config_gate_accepts_validated_qwen38_shape():
    assert bridge.is_supported_config(_config())


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("model_type",), "llama"),
        (("text_config", "num_hidden_layers"), 63),
        (("text_config", "num_experts"), 128),
        (("vision_config", "hidden_size"), 1024),
        (("quantization_config", "format"), "nvfp4-pack-quantized"),
        (
            (
                "quantization_config",
                "config_groups",
                "group_1",
                "weights",
                "group_size",
            ),
            32,
        ),
    ],
)
def test_config_gate_rejects_unvalidated_variants(path, value):
    config = _config()
    target = config
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    assert not bridge.is_supported_config(config)


def test_config_group_order_keeps_late_mlp_in_fp8():
    rules = bridge._rules_from_config(_config())
    assert bridge.quantization_kind_for_path(
        "language_model.model.layers.55.mlp.down_proj", rules
    ) == "scaled_nvfp4"
    assert bridge.quantization_kind_for_path(
        "language_model.model.layers.56.mlp.down_proj", rules
    ) == "scaled_mxfp8_channel"
    assert bridge.quantization_kind_for_path(
        "language_model.model.layers.0.self_attn.q_proj", rules
    ) == "scaled_mxfp8_channel"
    assert bridge.quantization_kind_for_path(
        "language_model.mtp.layers.0.mlp.down_proj", rules
    ) is None


def test_exact_transform_preserves_codes_and_scales():
    nv_prefix = "model.language_model.layers.0.mlp.down_proj"
    fp8_prefix = "model.language_model.layers.0.self_attn.q_proj"
    nv_codes = mx.arange(16, dtype=mx.uint8).reshape(2, 8)
    nv_scales = mx.array([[1], [127]], dtype=mx.uint8)
    fp8_codes = mx.arange(64, dtype=mx.uint8).reshape(2, 32)
    fp8_scales = mx.array([0.5, 1.5], dtype=mx.bfloat16)

    output = bridge.transform_weights_exact(
        {
            f"{nv_prefix}.weight_scale": nv_scales,
            f"{nv_prefix}.weight_global_scale": mx.array([2.0]),
            f"{nv_prefix}.input_global_scale": mx.array([1.0]),
            f"{nv_prefix}.weight_packed": nv_codes,
            f"{fp8_prefix}.weight": fp8_codes,
            f"{fp8_prefix}.weight_scale": fp8_scales,
        }
    )

    assert mx.array_equal(output[f"{nv_prefix}.weight"].view(mx.uint8), nv_codes).item()
    assert mx.array_equal(output[f"{nv_prefix}.scales"], nv_scales).item()
    assert output[f"{nv_prefix}.global_scale"].item() == pytest.approx(0.5)
    assert mx.array_equal(
        output[f"{fp8_prefix}.weight"].view(mx.uint8), fp8_codes
    ).item()
    assert output[f"{fp8_prefix}.scales"].shape == (2, 1)
    assert mx.array_equal(output[f"{fp8_prefix}.global_scale"], fp8_scales).item()


def test_adapter_dispatch_is_vlm_only(tmp_path, monkeypatch):
    adapter = Qwen38Adapter()
    load_mock = MagicMock(return_value=("MODEL", "PROCESSOR"))
    monkeypatch.setattr(bridge, "load", load_mock)

    context = adapter_context(tmp_path, _config(), for_vlm=True)
    assert adapter.match(context)
    assert adapter.load(context) == ("MODEL", "PROCESSOR")
    load_mock.assert_called_once_with(tmp_path)

    with pytest.raises(ValueError, match="refusing the text-only fallback"):
        adapter.load(adapter_context(tmp_path, _config(), for_vlm=False))


def test_config_gate_does_not_mutate_input():
    config = _config()
    original = copy.deepcopy(config)
    assert bridge.is_supported_config(config)
    assert config == original


def test_qwen38_is_an_isolated_model_worker_package():
    package_root = PACKAGE_SRC.parent
    manifest = ServicePackageArchive._manifest(
        yaml.safe_load((package_root / "service.yaml").read_text())
    )
    project = tomllib.loads((package_root / "pyproject.toml").read_text())

    assert manifest.protocol == "ai2apps-model-worker/v1"
    assert manifest.command == ()
    assert manifest.raw["runtime"]["adapter"] == "src/worker_adapter.py:create_adapter"
    assert manifest.models[0]["weights"]["revision"] == (
        "16b6615af3548b88e2d8e382457bc705b00479cf"
    )
    assert "entry-points" not in project["project"]
