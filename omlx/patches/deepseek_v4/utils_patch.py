# SPDX-License-Identifier: Apache-2.0
"""Patch ``mlx_lm.utils.load_model`` for DeepSeek V4 support.

Two surgical changes from PR 1192 are applied:

1. Weight loading goes through ``_load_safetensors`` instead of ``mx.load`` so
   safetensors files declaring the F8_E8M0 dtype (used by DeepSeek V4 fp8
   block-scale tensors) can be reinterpreted as U8 in-place.
2. The ``elif quant_method == "fp8" and model_type.startswith("deepseek_v4")``
   branch
   in the quantization config dispatch builds the per-layer quantization
   spec via ``deepseek_v4.make_quantization_config``.

The rest of ``load_model``'s body is identical to the v0.31.3 (``ed1fca4``)
upstream — copied verbatim from PR 1192 head ``5c10538``. mlx-lm is pinned
to a commit, so the body is stable.

When mlx-lm merges PR 1192 upstream this patch should be removed.
"""

from __future__ import annotations

import glob
import importlib.util
import json
import logging
import os
import struct
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import mlx.core as mx
import mlx.nn as nn
import mlx_lm.utils as _utils
import numpy as np
from mlx.utils import tree_map

from .scope_policy import load_scope_policy_from_env, parse_expert_key

logger = logging.getLogger(__name__)

SAFETENSORS_DTYPE_FALLBACKS = {"F8_E8M0": "U8"}
_BENCH_EXPERT_SLOTS_ENV = "OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS"

_PATCHED = False


def _load_safetensors(path: str) -> dict:
    """Load a safetensors file with a dtype fallback for F8_E8M0.

    DeepSeek V4 fp8 checkpoints declare ``F8_E8M0`` for the per-block
    exponent scale tensors. ``mx.load`` rejects unknown dtypes; the
    fallback rewrites the safetensors header in place to advertise the
    bytes as ``U8`` (raw uint8), loads, and restores the original header.
    """
    try:
        return mx.load(path)
    except RuntimeError as e:
        if not any(dtype in str(e) for dtype in SAFETENSORS_DTYPE_FALLBACKS):
            raise
        load_error = e

    with open(path, "r+b") as f:
        header_len = struct.unpack("<Q", f.read(8))[0]
        original_header = f.read(header_len)
        header = json.loads(original_header)
        changed = False

        for tensor_info in header.values():
            if not isinstance(tensor_info, dict):
                continue
            dtype = tensor_info.get("dtype")
            if dtype in SAFETENSORS_DTYPE_FALLBACKS:
                tensor_info["dtype"] = SAFETENSORS_DTYPE_FALLBACKS[dtype]
                changed = True

        if not changed:
            raise load_error

        patched_header = json.dumps(header, separators=(",", ":")).encode("utf-8")
        if len(patched_header) > header_len:
            raise RuntimeError(
                f"Cannot reinterpret unsupported safetensors dtype in {path}: "
                "patched header is larger than the original header."
            )

        try:
            f.seek(8)
            f.write(patched_header)
            f.write(b" " * (header_len - len(patched_header)))
            f.flush()
            return mx.load(path)
        finally:
            f.seek(8)
            f.write(original_header)
            f.flush()


def _benchmark_expert_id(key: str) -> int | None:
    marker = ".ffn.experts."
    if marker not in key:
        return None
    try:
        return int(key.split(marker, 1)[1].split(".", 1)[0])
    except ValueError:
        return None


def _load_safetensors_benchmark_subset(
    path: str,
    expert_slots: int | None = None,
    scope_experts: tuple[tuple[int, ...], ...] | None = None,
) -> dict:
    """Read only the resident expert prefix plus non-expert tensors.

    ``mx.load`` creates arrays for every tensor in a shard before model
    ``sanitize`` can discard nonresident experts.  On the V4 Flash source
    checkpoint that temporarily accounts for the complete 148 GiB file set.
    This explicit offset reader keeps the benchmark-only filter at the I/O
    boundary, so dropped experts never become MLX arrays.
    """
    storage_dtypes = {
        "I8": (np.int8, None),
        "I64": (np.int64, None),
        "U32": (np.uint32, None),
        "F32": (np.float32, None),
        "BF16": (np.uint16, mx.bfloat16),
        # DeepSeek sanitize consumes both FP8 encodings as packed raw bytes.
        "F8_E4M3": (np.uint8, None),
        "F8_E8M0": (np.uint8, None),
    }

    selected = {}
    with open(path, "rb") as f:
        header_len = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(header_len))
        data_start = 8 + header_len
        for key, info in header.items():
            if key == "__metadata__":
                continue
            if scope_experts is not None and key.startswith("mtp."):
                # Scope-cache v1 benchmarks the main model only. MTP has a
                # separate routed stack and needs its own scope policy.
                continue
            expert_id = _benchmark_expert_id(key)
            if expert_id is not None:
                if scope_experts is not None:
                    parsed = parse_expert_key(key)
                    if parsed is None:
                        continue
                    layer, parsed_expert = parsed
                    if parsed_expert not in scope_experts[layer]:
                        continue
                elif expert_slots is not None and expert_id >= expert_slots:
                    continue
            stacked_expert_ids = None
            if scope_experts is not None and ".ffn.switch_mlp." in key:
                parts = key.split(".")
                try:
                    layer_marker = parts.index("layers")
                    layer = int(parts[layer_marker + 1])
                except (ValueError, IndexError):
                    layer = -1
                shape = info.get("shape", [])
                if (
                    0 <= layer < len(scope_experts)
                    and shape
                    and int(shape[0]) == len(scope_experts[layer])
                ):
                    # Already physically compact; no further selection needed.
                    stacked_expert_ids = None
                elif (
                    0 <= layer < len(scope_experts)
                    and shape
                    and int(shape[0]) == 256
                ):
                    stacked_expert_ids = scope_experts[layer]
            dtype = info["dtype"]
            if dtype not in storage_dtypes:
                raise ValueError(
                    f"Unsupported safetensors dtype {dtype!r} in benchmark "
                    f"subset loader for {path}"
                )
            storage_dtype, view_dtype = storage_dtypes[dtype]
            start, end = info["data_offsets"]
            shape = tuple(int(dim) for dim in info["shape"])
            if stacked_expert_ids is not None:
                expert_bytes = (end - start) // shape[0]
                chunks = []
                for selected_expert in stacked_expert_ids:
                    f.seek(data_start + start + selected_expert * expert_bytes)
                    chunks.append(f.read(expert_bytes))
                raw = b"".join(chunks)
                shape = (len(stacked_expert_ids), *shape[1:])
            else:
                f.seek(data_start + start)
                raw = f.read(end - start)
            value = np.frombuffer(raw, dtype=storage_dtype).reshape(shape)
            value = mx.array(value)
            if view_dtype is not None:
                value = value.view(view_dtype)
            selected[key] = value
    return selected


def _build_patched_load_model() -> Callable:
    """Build the replacement ``load_model`` closure.

    Captures ``_get_classes`` from the live ``mlx_lm.utils`` module so the
    default behaves the same as upstream. Internal helpers (``load_config``,
    ``_transform_awq_weights``) are looked up dynamically at call time so
    they pick up any other patches applied to ``mlx_lm.utils``.
    """
    default_get_classes = _utils._get_classes

    def patched_load_model(
        model_path: Path,
        lazy: bool = False,
        strict: bool = True,
        model_config: dict[str, Any] | None = None,
        get_model_classes: Callable = default_get_classes,
        trust_remote_code: bool = False,
    ) -> tuple[nn.Module, dict]:
        config = _utils.load_config(model_path)
        if model_config is not None:
            config.update(model_config)

        weight_files = glob.glob(str(model_path / "model*.safetensors"))

        if not weight_files and strict:
            raise FileNotFoundError(f"No safetensors found in {model_path}")

        benchmark_slots = None
        scope_policy = None
        if str(config.get("model_type", "")).startswith("deepseek_v4"):
            raw_slots = os.environ.get(_BENCH_EXPERT_SLOTS_ENV, "").strip()
            if raw_slots:
                benchmark_slots = int(raw_slots)
            scope_policy = load_scope_policy_from_env()
            if scope_policy is not None and benchmark_slots is not None:
                raise ValueError(
                    "scope cache and benchmark expert folding are mutually exclusive"
                )

        scope_experts = (
            tuple(tuple(ids) for ids in scope_policy.experts_by_layer)
            if scope_policy is not None
            else None
        )

        weights = {}
        for wf in weight_files:
            if benchmark_slots is None and scope_experts is None:
                weights.update(_load_safetensors(wf))  # PR 1192 change
            else:
                weights.update(
                    _load_safetensors_benchmark_subset(
                        wf,
                        benchmark_slots,
                        scope_experts,
                    )
                )

        if (model_file := config.get("model_file")) is not None:
            if not trust_remote_code:
                raise ValueError(
                    f"The model at {model_path} requires executing custom model "
                    f"code ({model_file!r}). Pass trust_remote_code=True if you "
                    "trust this model."
                )
            spec = importlib.util.spec_from_file_location(
                "custom_model",
                model_path / model_file,
            )
            arch = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(arch)
            model_class, model_args_class = arch.Model, arch.ModelArgs
        else:
            model_class, model_args_class = get_model_classes(config=config)

        if "quantization_config" not in config:
            text_config = config.get("text_config", {})
            if "quantization_config" in text_config:
                config["quantization_config"] = text_config["quantization_config"]

        model_args = model_args_class.from_dict(config)
        model = model_class(model_args)

        if hasattr(model, "sanitize"):
            weights = model.sanitize(weights)

        def _quantize(quantization):
            def class_predicate(p, m):
                if p in config["quantization"]:
                    return config["quantization"][p]
                if not hasattr(m, "to_quantized"):
                    return False
                return f"{p}.scales" in weights

            nn.quantize(
                model,
                group_size=quantization["group_size"],
                bits=quantization["bits"],
                mode=quantization.get("mode", "affine"),
                class_predicate=class_predicate,
            )

        if (quantization := config.get("quantization", None)) is not None:
            _quantize(quantization)
        elif quantization_config := config.get("quantization_config", False):
            quant_method = quantization_config["quant_method"]
            if quant_method == "bitnet":
                from mlx_lm.models.bitlinear_layers import bitnet_quantize

                model = bitnet_quantize(model, quantization_config)
            elif quant_method == "mxfp4":
                quantization = {"group_size": 32, "bits": 4, "mode": "mxfp4"}
                config["quantization"] = quantization
                config["quantization_config"] = quantization
                _quantize(quantization)
            elif quant_method == "compressed-tensors":
                quantization = {"group_size": 32, "bits": 4, "mode": "affine"}
                config["quantization"] = quantization
                config["quantization_config"] = quantization
                _quantize(quantization)
            elif quant_method in ("awq", "gptq"):
                weights, quantization = _utils._transform_awq_weights(
                    weights, quantization_config
                )
                config["quantization"] = quantization
                config["quantization_config"] = quantization
                _quantize(quantization)
            elif quant_method == "fp8" and str(config.get("model_type", "")).startswith(
                "deepseek_v4"
            ):  # PR 1192 new branch
                from mlx_lm.models.deepseek_v4 import make_quantization_config

                quantization = make_quantization_config(model)
                config["quantization"] = quantization
                config["quantization_config"] = quantization
                _quantize(quantization)

        if config.get("quantize_activations", False):

            def _maybe_qq(m):
                if isinstance(m, nn.QuantizedLinear):
                    if m.mode not in ("nvfp4", "mxfp8"):
                        raise ValueError(
                            f"Mode ({m.mode}) does not support activation quantization"
                        )
                    if m.get("bias", False):
                        raise ValueError(
                            "Linear layer with bias does not support activation quantization"
                        )
                    out_dims, in_dims = m.weight.shape
                    in_dims *= 32 // m.bits
                    return nn.QQLinear(in_dims, out_dims, m.group_size, m.bits, m.mode)
                return m

            leaves = tree_map(
                _maybe_qq, model.leaf_modules(), is_leaf=nn.Module.is_module
            )
            model.update_modules(leaves)

        model.eval()
        model.load_weights(list(weights.items()), strict=strict)

        if not lazy:
            mx.eval(model.parameters())

        return model, config

    return patched_load_model


def apply_utils_patch() -> bool:
    """Replace ``mlx_lm.utils.load_model`` and inject ``_load_safetensors``.

    Idempotent. Also updates other ``mlx_lm.*`` modules that imported
    ``load_model`` directly via ``from .utils import load_model``.
    """
    global _PATCHED
    if _PATCHED:
        return False

    patched = _build_patched_load_model()

    _utils.SAFETENSORS_DTYPE_FALLBACKS = SAFETENSORS_DTYPE_FALLBACKS
    _utils._load_safetensors = _load_safetensors
    _utils.load_model = patched

    # Update any module that has a stale binding to the original load_model.
    for mod_name, mod in list(sys.modules.items()):
        if mod is None or not mod_name.startswith("mlx_lm"):
            continue
        if mod_name == "mlx_lm.utils":
            continue
        existing = getattr(mod, "load_model", None)
        if existing is not None and existing is not patched:
            try:
                mod.load_model = patched
            except Exception:
                pass

    _PATCHED = True
    logger.info("mlx_lm.utils.load_model replaced (deepseek_v4 fp8 + F8_E8M0 fallback)")
    return True
