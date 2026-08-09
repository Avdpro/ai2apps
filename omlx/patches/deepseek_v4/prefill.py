"""Memory-safe long-context prefill sizing for DeepSeek V4.

DeepSeek V4's ratio-4 indexer has a fast native path for query lengths that
are multiples of 64.  Large unaligned tails fall back to the much wider MLX
workspace.  Above 128k this module keeps regular chunks aligned and leaves at
most a 63-token final tail.  Shorter contexts retain a single unaligned tail:
an extra tiny chunk rebuilds the MoE transient banks and costs much more than
the bounded fallback workspace there.  Context bands reduce the configured
step at very long lengths so the model-specific prefill transient stays flat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _get_attr_or_key(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    try:
        value = getattr(obj, name)
    except Exception:
        return None
    if type(value).__module__.startswith("unittest.mock"):
        return None
    return value


def model_declares_deepseek_v4(model: Any) -> bool:
    """Return whether a loaded model/config tree declares DeepSeek V4."""

    seen: set[int] = set()
    stack = [model]
    while stack:
        obj = stack.pop()
        if obj is None:
            continue
        obj_id = id(obj)
        if obj_id in seen:
            continue
        seen.add(obj_id)

        model_type = str(_get_attr_or_key(obj, "model_type") or "")
        if model_type.startswith("deepseek_v4"):
            return True

        for attr in (
            "config",
            "args",
            "text_config",
            "language_config",
            "llm_config",
            "_language_model",
            "language_model",
            "model",
        ):
            child = _get_attr_or_key(obj, attr)
            if child is not None and not isinstance(
                child, (str, bytes, int, float, bool)
            ):
                stack.append(child)
    return False


@dataclass(frozen=True)
class DeepSeekV4PrefillConfig:
    """Context bands chosen to keep the conservative transient near 18 GiB."""

    alignment: int = 64
    align_tail_after: int = 128 * 1024
    context_128k: int = 128 * 1024
    context_256k: int = 256 * 1024
    context_512k: int = 512 * 1024
    step_128k: int = 5120
    step_256k: int = 4096
    step_512k: int = 3072
    step_1m: int = 2048

    def step_for_context(self, context_tokens: int) -> int:
        if context_tokens <= self.context_128k:
            return self.step_128k
        if context_tokens <= self.context_256k:
            return self.step_256k
        if context_tokens <= self.context_512k:
            return self.step_512k
        return self.step_1m


def make_deepseek_v4_prefill_config(model: Any) -> DeepSeekV4PrefillConfig | None:
    # The injected mlx-lm model exposes these two signals directly. Prefer
    # them before walking the module tree: ``nn.Module`` may register the
    # nested ``model`` attribute as a mapping-like module container whose
    # traversal semantics differ from an ordinary Python object.
    direct_types = (
        getattr(model, "model_type", None),
        getattr(getattr(model, "args", None), "model_type", None),
    )
    if any(
        str(model_type or "").startswith("deepseek_v4")
        for model_type in direct_types
    ):
        return DeepSeekV4PrefillConfig()
    if not model_declares_deepseek_v4(model):
        return None
    return DeepSeekV4PrefillConfig()


def deepseek_v4_prefill_step_size(
    *,
    processed_tokens: int,
    remaining_tokens: int,
    base_tokens: int,
    config: DeepSeekV4PrefillConfig,
) -> int:
    """Choose the next aligned chunk, splitting a large unaligned tail.

    ``remaining_tokens`` excludes the one token intentionally left for
    BatchGenerator insertion.  Include it when selecting the context band.
    """

    remaining = max(1, int(remaining_tokens))
    context_tokens = (
        max(0, int(base_tokens))
        + max(0, int(processed_tokens))
        + remaining
        + 1
    )
    step = min(config.step_for_context(context_tokens), remaining)

    alignment = max(1, int(config.alignment))
    if (
        context_tokens > config.align_tail_after
        and remaining <= step
        and remaining > alignment
    ):
        aligned = (remaining // alignment) * alignment
        tail = remaining - aligned
        if aligned > 0 and tail:
            return aligned
    return step


__all__ = [
    "DeepSeekV4PrefillConfig",
    "deepseek_v4_prefill_step_size",
    "make_deepseek_v4_prefill_config",
    "model_declares_deepseek_v4",
]
