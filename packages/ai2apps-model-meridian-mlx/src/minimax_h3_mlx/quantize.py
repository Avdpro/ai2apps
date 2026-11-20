"""Quantization for the MiniMax-H3 DiT.

Read the performance note in the README before reaching for this. H3's bottleneck is **attention
FLOPs**, which quantization does not reduce — the linear layers are ~42% of the work for a 5 s clip
and ~20% for 15 s, so a 4-bit DiT is worth roughly 1.2-1.4x end to end. Quantizing H3 is about
fitting it on a smaller Mac, not about making generation quick.

What is and is not quantized, and why:

* **Quantized** — the block stack's `attn.qkv_proj`, `attn.out_proj`, `mlp.fc1`, `mlp.fc2`, and the
  same four in the token refiner. That is essentially all of the 20B core.
* **Never quantized** — the two input patch projections, `condition_proj`, the timestep MLP and the
  two output heads. These are float32 in the release for a reason (`_keep_in_fp32_modules` in the
  reference) and together are well under 1% of the model, so quantizing them buys nothing and costs
  precision exactly where the signal enters and leaves the stack.
* **`adaln_proj` is off by default but 8-bit is measured-safe** (`--quantize-adaln`). Its 13B is the
  largest block of parameters and, left at bfloat16, it dominates the download of every build — a
  3-bit core is 9 GB resident inside a 35 GB repository.

  The first-principles argument against quantizing it is that every block reads the same `temb`, so
  an error there biases all 50 blocks identically. That argument is wrong, and `eval_adaln_quant.py`
  is what showed it: the table is computed **once**, so quantization perturbs it like slightly
  different modulation weights rather than introducing drift that compounds along the trajectory.

  Measured shift in the modulation table, against the velocity error the *core* already carries at
  the same width:

  | adaln bits | table rel-L2 | worst tensor | core velocity rel-L2 |
  |---:|---:|---|---:|
  | 8 | **0.0025** | shift_mlp 0.0035 | 0.0329 |
  | 6 | 0.0031 | shift_mlp 0.0074 | 0.0611 |
  | 4 | 0.0077 | shift_mlp 0.0282 | 0.1649 |

  At 8 bits the table moves an order of magnitude less than the core's own error, for 12.2 GB off
  every download. The published builds use it; 4-bit AdaLN is measurably worse and is not
  recommended even when the core is 4-bit.

Norms and biases stay in their original precision throughout, as MLX's quantizer requires.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_flatten

# Suffixes of the linear layers that carry the DiT's weight mass.
CORE_LINEARS = (
    ".attn.qkv_proj",
    ".attn.out_proj",
    ".attn.gate_compress",
    ".mlp.fc1",
    ".mlp.fc2",
)

# Modules kept at full precision: float32 in the release, and <1% of the parameters.
NEVER_QUANTIZE = (
    "video_patch_proj",
    "audio_patch_proj",
    "condition_proj",
    "time_embedder",
    "final_layer.video_out",
    "final_layer.audio_out",
    "final_layer.adaln_proj",
)


@dataclass
class QuantConfig:
    """How to quantize a DiT."""

    bits: int = 4
    group_size: int = 64
    #: Quantize the per-block AdaLN projections too. Off by default — see the module docstring.
    quantize_adaln: bool = False
    #: Bits for `adaln_proj` when `quantize_adaln` is set; kept higher than the core deliberately.
    adaln_bits: int = 8
    #: Layers whose quantization is overridden, by exact module path.
    overrides: dict[str, int] = field(default_factory=dict)

    def bits_for(self, path: str) -> int | None:
        """Bit width for a module path, or ``None`` to leave it unquantized."""
        if path in self.overrides:
            return self.overrides[path]
        if any(path.endswith(suffix) or f"{suffix}." in path for suffix in NEVER_QUANTIZE):
            return None
        if any(name in path for name in NEVER_QUANTIZE):
            return None
        if ".adaln_proj." in path or path.endswith(".adaln_proj.linear"):
            return self.adaln_bits if self.quantize_adaln else None
        if any(path.endswith(suffix) for suffix in CORE_LINEARS):
            return self.bits
        return None


def _class_predicate(config: QuantConfig, counts: dict[int, int] | None = None, verbose: bool = False):
    """Build the `nn.quantize` predicate for a recipe, shared by conversion and loading."""

    def predicate(path: str, module: nn.Module) -> bool | dict:
        if not isinstance(module, nn.Linear):
            return False
        bits = config.bits_for(path)
        if bits is None:
            return False
        # A layer whose input dimension is not a multiple of the group size cannot be grouped.
        if module.weight.shape[-1] % config.group_size:
            if verbose:
                print(f"  skip {path}: in_features {module.weight.shape[-1]} "
                      f"not divisible by group_size {config.group_size}")
            return False
        if counts is not None:
            counts[bits] = counts.get(bits, 0) + 1
        return {"group_size": config.group_size, "bits": bits}

    return predicate


def apply_quantization_structure(model, config: QuantConfig) -> None:
    """Convert the module tree to quantized layers *without* meaningful weights.

    Loading a quantized checkpoint needs the tree to already hold `QuantizedLinear` layers, since
    those carry packed weights plus scales and biases under different names than `nn.Linear`. This
    replays the recorded recipe so the keys line up; the values are then overwritten by the load.
    """
    nn.quantize(
        model,
        group_size=config.group_size,
        bits=config.bits,
        class_predicate=_class_predicate(config),
    )


def quantize_dit(model, config: QuantConfig | None = None, verbose: bool = False) -> dict[str, object]:
    """Quantize a :class:`~minimax_h3_mlx.dit.MiniMaxH3DiT` in place.

    Returns a summary with the before/after footprint and the per-width layer counts.
    """
    config = config or QuantConfig()
    before = _footprint(model)
    counts: dict[int, int] = {}

    nn.quantize(
        model,
        group_size=config.group_size,
        bits=config.bits,
        class_predicate=_class_predicate(config, counts, verbose),
    )
    mx.eval(model.parameters())
    after = _footprint(model)

    summary = {
        "bits": config.bits,
        "group_size": config.group_size,
        "quantized_layers": dict(sorted(counts.items())),
        "gb_before": before,
        "gb_after": after,
        "ratio": before / after if after else 0.0,
    }
    if verbose:
        layers = ", ".join(f"{n} at {b}-bit" for b, n in sorted(counts.items()))
        print(f"  quantized {layers}")
        print(f"  {before:.1f} GB -> {after:.1f} GB ({before / after:.2f}x)")
    return summary


def _footprint(model) -> float:
    return sum(v.nbytes for _, v in tree_flatten(model.parameters())) / 1e9


def resident_footprint(model) -> dict[str, float]:
    """Footprint split into what stays resident and what is dropped after the cache is built."""
    total = adaln = 0
    for key, value in tree_flatten(model.parameters()):
        total += value.nbytes
        if key.startswith("blocks.") and ".adaln_proj." in key:
            adaln += value.nbytes
    return {
        "total_gb": total / 1e9,
        "adaln_gb": adaln / 1e9,
        "resident_gb": (total - adaln) / 1e9,
    }
