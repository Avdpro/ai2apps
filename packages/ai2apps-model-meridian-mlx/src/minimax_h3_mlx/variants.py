"""Experimental MiniMax-H3 variant checkpoint support.

This module deliberately contains checkpoint transformation code rather than runtime
LoRA wrappers.  H3 spends enough time in wide linear layers that evaluating every
adapter as two extra matrix multiplications costs about 20% per denoising step.  For
deployment we merge the adapter once and requantize it onto the base checkpoint's
existing affine grid.  The resulting DiT has no adapter work in its hot path.

The mapper accepts both the native MLX names used by this package and PEFT/Diffusers
names used by LightX2V and OpenVDN.  Split Diffusers Q/K/V adapters are applied to the
corresponding row range of this port's fused QKV projection.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


@dataclass(frozen=True)
class LoRATarget:
    """One adapter matrix pair mapped onto an MLX checkpoint weight."""

    weight_key: str
    row_start: int | None = None
    row_end: int | None = None
    swap_halves: bool = False


_BLOCK = re.compile(r"^(?:transformer_blocks|blocks)\.(\d+)\.(.+)$")
_REFINER = re.compile(
    r"^(?:token_refiner\.(?:refiner_blocks|blocks))\.(\d+)\.(.+)$"
)


def _clean_adapter_name(name: str) -> str:
    for prefix in (
        "base_model.model.", "base_model.", "model.diffusion_model.",
        "diffusion_model.", "transformer.",
    ):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name


def split_lora_key(key: str) -> tuple[str, str] | None:
    """Return ``(module_name, A|B)`` for common PEFT/Comfy/native keys."""

    key = _clean_adapter_name(key)
    patterns = (
        (".lora_A.default.weight", "A"),
        (".lora_B.default.weight", "B"),
        (".lora_A.weight", "A"),
        (".lora_B.weight", "B"),
        (".lora_down.weight", "A"),
        (".lora_up.weight", "B"),
    )
    for suffix, side in patterns:
        if key.endswith(suffix):
            return key[:-len(suffix)], side
    # PEFT permits an arbitrary adapter name between lora_A/B and weight
    # (OpenVDN uses ``default`` and ``turbo``).
    named = re.match(r"^(.*)\.lora_([AB])\.[^.]+\.weight$", key)
    if named:
        return named.group(1), named.group(2)
    return None


def _map_tail(prefix: str, tail: str, hidden_size: int) -> LoRATarget:
    replacements = {
        "attn.out_proj": "attn.out_proj",
        "attn.to_out.0": "attn.out_proj",
        "attn.orig.to_out.0": "attn.out_proj",
        "mlp.fc1": "mlp.fc1",
        "ff.net.0.proj": "mlp.fc1",
        "mlp.fc2": "mlp.fc2",
        "ff.net.2": "mlp.fc2",
        "adaln_proj.linear": "adaln_proj.linear",
    }
    if tail in replacements:
        return LoRATarget(
            f"{prefix}.{replacements[tail]}.weight",
            swap_halves=tail in {"ff.net.0.proj"},
        )
    if tail in {"attn.qkv_proj", "attn.orig.qkv_proj"}:
        return LoRATarget(f"{prefix}.attn.qkv_proj.weight")
    qkv = {
        "attn.to_q": 0,
        "attn.orig.to_q": 0,
        "attn.to_k": 1,
        "attn.orig.to_k": 1,
        "attn.to_v": 2,
        "attn.orig.to_v": 2,
    }
    if tail in qkv:
        start = qkv[tail] * hidden_size * 4 // 3
        # H3 inner_dim is 4/3 hidden_size (7168 for hidden_size 5376).
        width = hidden_size * 4 // 3
        return LoRATarget(f"{prefix}.attn.qkv_proj.weight", start, start + width)
    raise KeyError(f"Unsupported H3 LoRA target: {prefix}.{tail}")


def map_lora_module(name: str, hidden_size: int = 5376) -> LoRATarget:
    """Map a native or Diffusers H3 module name to the fused MLX layout."""

    name = _clean_adapter_name(name)
    match = _BLOCK.match(name)
    if match:
        return _map_tail(f"blocks.{match.group(1)}", match.group(2), hidden_size)
    match = _REFINER.match(name)
    if match:
        return _map_tail(
            f"token_refiner.blocks.{match.group(1)}", match.group(2), hidden_size
        )
    if name in {"final_layer.adaln_proj.linear", "norm_out.linear"}:
        return LoRATarget("final_layer.adaln_proj.linear.weight")
    raise KeyError(f"Unsupported H3 LoRA module: {name}")


def collect_lora_pairs(keys: list[str], hidden_size: int = 5376):
    """Validate and map adapter keys without loading their tensor payloads."""

    pairs: dict[str, dict[str, str]] = {}
    targets: dict[str, LoRATarget] = {}
    unsupported = []
    for key in keys:
        parsed = split_lora_key(key)
        if parsed is None:
            unsupported.append(key)
            continue
        module, side = parsed
        pairs.setdefault(module, {})[side] = key
        targets[module] = map_lora_module(module, hidden_size)
    if unsupported:
        raise ValueError(f"Adapter contains unsupported tensors: {unsupported[:4]}")
    missing = [name for name, pair in pairs.items() if set(pair) != {"A", "B"}]
    if missing:
        raise ValueError(f"Adapter contains unpaired LoRA tensors: {missing[:4]}")
    return [(targets[name], pair["A"], pair["B"]) for name, pair in pairs.items()]


def _adapter_alpha(adapter: Path, explicit: float | None) -> float | None:
    if explicit is not None:
        return explicit
    try:
        from safetensors import safe_open
        with safe_open(str(adapter), framework="np") as handle:
            stamped = (handle.metadata() or {}).get("alpha")
        return None if stamped is None else float(stamped)
    except (ImportError, OSError, ValueError):
        return None


def apply_lora_to_weights(
    base: dict,
    adapter: str | Path,
    *,
    scale: float = 1.0,
    alpha: float | None = None,
) -> dict[str, object]:
    """Merge one H3 LoRA into an already loaded Q4/Q8 weight dictionary.

    This is the deployment counterpart of :func:`merge_lora_checkpoint`: it
    performs the same dequantize/add/requantize operation while the staged DiT
    is loading, so an AI2Apps checkpoint may contain only a small overlay plus
    a separately installed base checkpoint.
    """

    import mlx.core as mx

    adapter = Path(adapter)
    lora = mx.load(str(adapter))
    resolved_alpha = _adapter_alpha(adapter, alpha)
    pairs = collect_lora_pairs(list(lora))
    by_weight: dict[str, list[tuple[LoRATarget, str, str]]] = {}
    for item in pairs:
        by_weight.setdefault(item[0].weight_key, []).append(item)

    touched = 0
    for weight_key, entries in by_weight.items():
        if weight_key not in base:
            raise KeyError(f"Adapter target is absent from base: {weight_key}")
        scales_key = weight_key[:-len("weight")] + "scales"
        biases_key = weight_key[:-len("weight")] + "biases"
        packed = base[weight_key]
        if scales_key not in base:
            merged = packed.astype(mx.float32)
            bits = group_size = None
        else:
            scales = base[scales_key]
            biases = base.get(biases_key)
            in_features = int(scales.shape[-1]) * 64
            bits = int(round(32 * int(packed.shape[-1]) / in_features))
            group_size = 64
            merged = mx.dequantize(
                packed, scales, biases, group_size=group_size, bits=bits,
                mode="affine", dtype=mx.float32,
            )
        for target, a_key, b_key in entries:
            a = lora[a_key].astype(mx.float32)
            b = lora[b_key].astype(mx.float32)
            rank = int(a.shape[0])
            effective = float(scale) * (
                float(resolved_alpha) / rank if resolved_alpha is not None else 1.0
            )
            delta = (b @ a) * effective
            if target.swap_halves:
                value, gate = mx.split(delta, 2, axis=0)
                delta = mx.concatenate([gate, value], axis=0)
            if target.row_start is None:
                if delta.shape != merged.shape:
                    raise ValueError(
                        f"LoRA shape mismatch at {weight_key}: {delta.shape} vs {merged.shape}"
                    )
                merged = merged + delta
            else:
                expected = (target.row_end - target.row_start, merged.shape[1])
                if delta.shape != expected:
                    raise ValueError(
                        f"Split QKV LoRA mismatch at {weight_key}: {delta.shape} vs {expected}"
                    )
                merged[target.row_start:target.row_end] = (
                    merged[target.row_start:target.row_end] + delta
                )
        if bits is None:
            base[weight_key] = merged.astype(packed.dtype)
            mx.eval(base[weight_key])
        else:
            quantized = mx.quantize(
                merged.astype(scales.dtype), group_size=group_size, bits=bits, mode="affine"
            )
            base[weight_key], base[scales_key] = quantized[:2]
            if len(quantized) == 3:
                base[biases_key] = quantized[2]
            mx.eval(*quantized)
        touched += 1

    return {
        "adapter_tensors": len(lora),
        "adapter_pairs": len(pairs),
        "target_weights": touched,
        "alpha": "rank" if resolved_alpha is None else resolved_alpha,
    }


def merge_lora_checkpoint(
    base_transformer: str | Path,
    adapter: str | Path,
    output_transformer: str | Path,
    *,
    scale: float = 1.0,
    alpha: float | None = None,
) -> dict[str, object]:
    """Merge an H3 LoRA into a flat Q4/Q8 MLX transformer and requantize.

    The operation is intentionally offline.  It preserves all non-target tensors and
    the base affine recipe, and it never mutates the source checkpoint.
    """

    import mlx.core as mx

    base_transformer = Path(base_transformer)
    adapter = Path(adapter)
    output_transformer = Path(output_transformer)
    if output_transformer.resolve() == base_transformer.resolve():
        raise ValueError("Refusing to overwrite the base checkpoint")

    base = mx.load(str(base_transformer))
    report = apply_lora_to_weights(base, adapter, scale=scale, alpha=alpha)

    output_transformer.parent.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(
        str(output_transformer), base,
        metadata={
            "variant_adapter": adapter.name,
            "variant_merge": "W_eff = W + scale * alpha/rank * B@A",
            "variant_scale": str(scale),
            "variant_alpha": str(report["alpha"]),
        },
    )
    report["output"] = str(output_transformer)
    return report
