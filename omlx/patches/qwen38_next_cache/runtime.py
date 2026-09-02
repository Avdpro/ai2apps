"""Exact Top-N Cached-MoE runtime for Qwen3.8 Flash Next.

This first baseline changes only routed-expert residency.  Router scores,
Top-10 selection, shared experts, attention, Hyper-Connection, and PLE remain
the upstream Qwen4 implementation.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import time
from functools import cache
from pathlib import Path
from typing import Any

import mlx.core as mx
import mlx.nn as nn

from omlx.patches.deepseek_v4.switch_layers import SwitchGLU
from omlx.patches.glm5_next_cache.boost import replace_missed_routes
from omlx.patches.glm5_next_cache.dynamic_cache import Glm5DynamicCache
from omlx.patches.glm5_next_cache.policy import EMPTY, LayerState

from .boost import normalize_qwen4_boost, qwen4_boost_policy

logger = logging.getLogger(__name__)

_EXPERT_RE = re.compile(
    r"(?:^|\.)layers\.(\d+)\.mlp\.switch_mlp\."
    r"(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$"
)
_APPLIED = False


class Qwen4DynamicCache(Glm5DynamicCache):
    """Qwen geometry on the shared exact-cache executor."""

    def __init__(self, *args, **kwargs):
        self.promotion_enable_after = int(
            kwargs.pop("promotion_enable_after", _promotion_enable_after())
        )
        super().__init__(*args, **kwargs)
        self._decode_steps_by_layer: dict[int, int] = {}
        self.preserve_route_order = True
        # Canonical grouping keeps repeated requests bit-identical.  The
        # resident-first prefill A/B changes QMM batch shapes and is therefore
        # an explicitly opt-in performance experiment for Qwen4.
        self.prefill_resident_first = (
            os.environ.get("OMLX_QWEN4_PREFILL_RESIDENT_FIRST", "0") == "1"
        )
        # Preserve canonical QMM grouping while sourcing already-resident
        # records from L1/Hot instead of rereading them from SSD. Unlike the
        # resident-first A/B this does not split route computation by tier.
        self.prefill_canonical_reuse = (
            os.environ.get("OMLX_QWEN4_PREFILL_CANONICAL_REUSE", "1") == "1"
        )
        # Keep the session/Scope L1 fixed while Prefill chunks are processed.
        # Replaying each chunk into L1 only reshuffles identical resident
        # records and prevents the canonical bank from reusing them directly.
        self.prefill_retain_l1 = (
            os.environ.get("OMLX_QWEN4_PREFILL_RETAIN_L1", "1") == "1"
        )

    def _decode_scratch_switch(self, template: Any) -> Any:
        # GLM routes Top-8; Qwen4 routes Top-10 and can miss all ten experts
        # on the first token.  Keep this bank fixed-shape for the same direct
        # SSD-to-unified-memory ABI.
        if self._decode_scratch is None:
            self._decode_scratch = self._make_fixed_switch(template, 10)
        return self._decode_scratch

    def reset_hot(self, layer: int) -> None:
        """Invalidate request-local L0 tags without disturbing the reusable L1.

        A fresh prefill starts a new route sequence.  Keeping the previous
        decode's Hot tags makes the prefill planner treat mutable L0 storage as
        request-independent residency, which is unsafe when its pending Metal
        work and the next request overlap.  L1 remains warm across requests;
        only the previous-token Hot tier is request-local.
        """

        if self.tail_policy is None:
            return
        with self._lock:
            self._decode_steps_by_layer.pop(layer, None)
            self.tail_policy.install(
                layer,
                LayerState(
                    expert_ids=[-1] * self.tail_slots,
                    segments=[EMPTY] * self.tail_slots,
                    last_used=[0] * self.tail_slots,
                ),
            )
            self._pending_l1_promotions.pop(layer, None)

    def decode_promotion_limit(self, layer: int) -> int:
        """Advance one request-local layer step and gate delayed L1 promotion."""

        with self._lock:
            step = self._decode_steps_by_layer.get(layer, 0) + 1
            self._decode_steps_by_layer[layer] = step
        if step <= self.promotion_enable_after:
            return 0
        return self.l1_promotions_per_layer

    def stats(self) -> dict[str, Any]:
        result = super().stats()
        result.update(
            {
                "promotion_enable_after": self.promotion_enable_after,
                "decode_steps_by_layer": dict(self._decode_steps_by_layer),
            }
        )
        return result

    def prime_main(
        self,
        layer: int,
        switch: Any,
        requested: tuple[int, ...],
    ) -> tuple[int, ...]:
        """Materialize a Scope-selected L1 bank at the decode boundary."""

        if not requested:
            return self.policy.lookup(layer)
        with self._lock:
            self._prepare_switch(layer, switch)
            plan = self.policy.plan(layer, requested[: self.capacity])
            if plan.missing:
                mx.synchronize()
                store = self._store(layer)
                started = time.perf_counter()
                if not self._direct_load(store, switch, plan.slots, plan.missing):
                    raise RuntimeError("Qwen4 Scope prime requires Direct L1")
                self.read_seconds += time.perf_counter() - started
                self.experts_loaded += len(plan.missing)
                self.bytes_loaded += len(plan.missing) * store.record_bytes
            self.policy.publish(layer, plan)
            return self.policy.lookup(layer)

    def decode_hotset(
        self,
        layer: int,
        requested: tuple[int, ...],
        switch: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
    ) -> tuple[mx.array, tuple[int, ...], tuple[int, ...]]:
        """Materialize the complete current Top-10 in one fixed L0 bank."""

        if self.tail_policy is None or self.tail_slots < 10:
            raise RuntimeError("Qwen4 Hotset decode requires at least Hot10")
        self.calls += 1
        with self._lock:
            self._prepare_switch(layer, switch)
            hot = self._tail_switch(layer, switch)
            main_lookup = self.policy.lookup(layer)
            plan = self.tail_policy.plan(layer, requested)

            if plan.missing:
                # The route-ID read above is already a graph boundary, but a
                # full synchronization is required before mutating the fixed
                # bank consumed by the previous token.
                sync_started = time.perf_counter()
                mx.synchronize()
                self.sync_seconds += time.perf_counter() - sync_started
                slot_for = dict(zip(plan.missing, plan.slots, strict=True))
                from_main = tuple(
                    expert for expert in plan.missing if main_lookup[expert] >= 0
                )
                from_ssd = tuple(
                    expert for expert in plan.missing if main_lookup[expert] < 0
                )
                if from_main:
                    self._copy_switch_slots(
                        switch,
                        tuple(main_lookup[expert] for expert in from_main),
                        hot,
                        tuple(slot_for[expert] for expert in from_main),
                    )
                if from_ssd:
                    store = self._store(layer)
                    read_started = time.perf_counter()
                    if not self._direct_load(
                        store,
                        hot,
                        tuple(slot_for[expert] for expert in from_ssd),
                        from_ssd,
                    ):
                        raise RuntimeError(
                            "Qwen4 Hotset requires the native direct loader"
                        )
                    self.read_seconds += time.perf_counter() - read_started
                    self.experts_loaded += len(from_ssd)
                    self.bytes_loaded += len(from_ssd) * store.record_bytes
                self.tail_policy.publish(layer, plan)
                self.miss_calls += 1
            else:
                self.tail_policy.publish(layer, plan)
                self.hit_calls += 1

            hot_lookup = self.tail_policy.lookup(layer)
            local = mx.array(hot_lookup, dtype=mx.int32)[inds]
            output = _weighted_switch(hot, x, local, scores)
            return output, main_lookup, hot_lookup


def _store_path() -> Path | None:
    value = os.environ.get("OMLX_QWEN4_DYNAMIC_STORE", "").strip()
    return Path(value).expanduser().resolve() if value else None


def _slots() -> int:
    value = int(os.environ.get("OMLX_QWEN4_DYNAMIC_SLOTS", "80"))
    if not 10 <= value <= 480:
        raise ValueError("Qwen4 dynamic slots must be in [10, 480]")
    return value


def _io_workers() -> int:
    return int(os.environ.get("OMLX_QWEN4_DYNAMIC_IO_WORKERS", "4"))


def _hot_slots() -> int:
    value = int(os.environ.get("OMLX_QWEN4_HOT_SLOTS", "0"))
    if not 0 <= value <= 32:
        raise ValueError("Qwen4 Hot slots must be in [0, 32]")
    return value


def _promotions_per_layer() -> int:
    value = int(os.environ.get("OMLX_QWEN4_L1_PROMOTIONS_PER_LAYER", "4"))
    if not 0 <= value <= 10:
        raise ValueError("Qwen4 L1 promotions per layer must be in [0, 10]")
    return value


def _promotion_enable_after() -> int:
    value = int(os.environ.get("OMLX_QWEN4_L1_PROMOTION_ENABLE_AFTER", "128"))
    if not 0 <= value <= 1_000_000:
        raise ValueError("Qwen4 L1 promotion delay must be in [0, 1000000]")
    return value


def _hotset_mode() -> bool:
    # Experimental single-kernel L0 materialization is retained for A/B only.
    # It is exact on an isolated request but slower than resident/SSD overlap.
    return os.environ.get("OMLX_QWEN4_HOTSET_MODE", "0") == "1"


def _boost_mode() -> str:
    return normalize_qwen4_boost(os.environ.get("OMLX_QWEN4_BOOST_MODE"))


def _record_boost(block: Any, counters) -> None:
    if counters is None:
        return
    replaced, before, after = (int(value.item()) for value in counters)
    stats = block.boost_stats
    stats["routes_replaced"] += replaced
    stats["misses_before"] += before
    stats["misses_after"] += after


@cache
def _scope_layers() -> dict[int, tuple[int, ...]]:
    path_value = os.environ.get("OMLX_QWEN4_SCOPE_PROFILE", "").strip()
    if not path_value:
        return {}
    profile = json.loads(Path(path_value).expanduser().read_text())
    scope_name = os.environ.get("OMLX_QWEN4_SCOPE", "general")
    scope = profile["scopes"][scope_name]
    phase_layers = scope.get("phase_layers", {})
    source = phase_layers.get("decode") or scope["layers"]
    return {
        int(layer): tuple(int(expert) for expert in experts)
        for layer, experts in source.items()
    }


@cache
def get_qwen4_dynamic_cache(directory: str) -> Qwen4DynamicCache:
    # The GLM cache executor is architecture-neutral: it owns fixed SwitchGLU
    # slots and consumes the shared expert-major ABI.  Qwen supplies its own
    # geometry, expert count, router, and model integration below.
    return Qwen4DynamicCache(
        directory,
        capacity=_slots(),
        tail_slots=_hot_slots(),
        l1_promotions_per_layer=_promotions_per_layer(),
        promotion_enable_after=_promotion_enable_after(),
        num_experts=512,
        io_workers=_io_workers(),
    )


def _is_qwen4(path: str | os.PathLike[str]) -> bool:
    try:
        config = json.loads((Path(path) / "config.json").read_text())
    except (OSError, TypeError, ValueError):
        return False
    return config.get("model_type") == "qwen4_exp"


def _is_checkpoint_safetensor(filename: Any, target_dir: Path) -> bool:
    """Match the model view path without resolving its Hub-cache symlink."""

    try:
        path = Path(os.path.abspath(os.path.expanduser(os.fspath(filename))))
    except TypeError:
        return False
    return path.parent == target_dir and path.suffix == ".safetensors"


def _compact_safetensors(path: str, original: Any, *, slots: int):
    """Keep non-experts and expand one cold expert to fixed L1 shape."""

    loaded = original(path)
    compact = {}
    for key, value in loaded.items():
        match = _EXPERT_RE.search(key)
        if match is None:
            compact[key] = value
            continue
        if value.shape[0] != 512:
            raise ValueError(f"unexpected Qwen4 routed tensor shape: {key} {value.shape}")
        compact[key] = mx.broadcast_to(value[:1], (slots, *value.shape[1:]))
    return compact


def _weighted_switch(switch, x, inds, scores):
    routes = switch(x, inds)
    return (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)


def apply_qwen4_dynamic_patch() -> bool:
    """Install the Qwen4 Top-N cache before model construction."""

    global _APPLIED
    if _APPLIED:
        return False
    directory = _store_path()
    if directory is None:
        return False
    if not (directory / "layer-000.moe").is_file():
        raise FileNotFoundError(f"Qwen4 expert store is missing: {directory}")

    from omlx.patches.mlx_vlm_qwen4_exp_compat import (
        apply_mlx_vlm_qwen4_exp_compat_patch,
    )

    apply_mlx_vlm_qwen4_exp_compat_patch()

    from mlx_vlm.models.qwen3_5.language import Qwen3_5MLP
    from mlx_vlm.models.qwen4_exp import language as qwen_language
    from mlx_vlm.models.qwen4_exp.qwen4_exp import Model

    slots = _slots()
    dynamic = get_qwen4_dynamic_cache(str(directory))

    class Qwen4DynamicMoE(nn.Module):
        def __init__(self, args):
            super().__init__()
            dim = args.hidden_size
            self.top_k = args.num_experts_per_tok
            self.gate = nn.Linear(dim, args.num_experts, bias=False)
            self.switch_mlp = SwitchGLU(
                dim,
                args.moe_intermediate_size,
                slots,
                global_num_experts=slots,
                fused_gate_up=True,
            )
            self.shared_expert = Qwen3_5MLP(
                dim, args.shared_expert_intermediate_size
            )
            self.shared_expert_gate = nn.Linear(dim, 1, bias=False)
            self.dynamic_layer = -1
            self.dynamic_cache = dynamic
            self.dynamic_lookup_values = tuple([-1] * args.num_experts)
            self.dynamic_tail_lookup_values = tuple([-1] * args.num_experts)
            self._scope_primed = False
            self.boost_mode = _boost_mode()
            self.boost_policy = qwen4_boost_policy(self.boost_mode)
            self.boost_stats = {
                "routes_replaced": 0,
                "misses_before": 0,
                "misses_after": 0,
            }

        def __call__(self, x, **kwargs):
            # Vendored Qwen4 forwards target_verify for optional Lightning
            # MTP.  Cached-MoE currently runs the ordinary exact path.
            del kwargs
            gates = mx.softmax(self.gate(x), axis=-1, precise=True)
            inds = mx.argpartition(gates, kth=-self.top_k, axis=-1)[
                ..., -self.top_k :
            ]
            scores = mx.take_along_axis(gates, inds, axis=-1)
            scores = scores / scores.sum(axis=-1, keepdims=True)
            is_decode = x.shape[0] == x.shape[1] == 1

            if not is_decode:
                self._scope_primed = False
                self.dynamic_cache.reset_hot(self.dynamic_layer)
                self.dynamic_tail_lookup_values = self.dynamic_cache.tail_lookup(
                    self.dynamic_layer
                )
            elif not self._scope_primed:
                scope_ids = _scope_layers().get(self.dynamic_layer, ())
                if scope_ids:
                    self.dynamic_lookup_values = self.dynamic_cache.prime_main(
                        self.dynamic_layer, self.switch_mlp, scope_ids
                    )
                self._scope_primed = True

            boost_counters = None
            if self.boost_policy is not None:
                l1_lookup = mx.array(
                    self.dynamic_lookup_values, dtype=mx.int32
                )
                hot_lookup = mx.array(
                    self.dynamic_tail_lookup_values, dtype=mx.int32
                )
                available = (l1_lookup >= 0) | (hot_lookup >= 0)
                inds, boost_counters = replace_missed_routes(
                    inds,
                    scores,
                    gates,
                    available,
                    self.boost_policy,
                )
            self.dynamic_cache.observe_routes(
                self.dynamic_layer,
                inds,
                scores,
                "decode" if is_decode else "prefill",
            )
            shared = mx.sigmoid(self.shared_expert_gate(x)) * self.shared_expert(x)

            if not is_decode:
                if boost_counters is not None:
                    mx.eval(*boost_counters)
                    _record_boost(self, boost_counters)
                routed = self.dynamic_cache.prefill(
                    self.dynamic_layer, self.switch_mlp, x, inds, scores
                )
                self.dynamic_lookup_values = self.dynamic_cache.lookup(
                    self.dynamic_layer
                )
                self.dynamic_tail_lookup_values = self.dynamic_cache.tail_lookup(
                    self.dynamic_layer
                )
                return routed + shared

            lookup = mx.array(self.dynamic_lookup_values, dtype=mx.int32)
            mapped = lookup[inds]
            tail_lookup = mx.array(
                self.dynamic_tail_lookup_values, dtype=mx.int32
            )
            tail_mapped = tail_lookup[inds]
            promotion_limit = self.dynamic_cache.decode_promotion_limit(
                self.dynamic_layer
            )
            main_miss_count = mx.sum((mapped < 0).astype(mx.int32))
            missing_count = mx.sum(
                ((mapped < 0) & (tail_mapped < 0)).astype(mx.int32)
            )
            mx.eval(main_miss_count, missing_count, *(boost_counters or ()))
            _record_boost(self, boost_counters)
            if not int(main_miss_count.item()):
                self.dynamic_cache.record_all_hit()
                return _weighted_switch(self.switch_mlp, x, mapped, scores) + shared

            mx.eval(inds)
            requested = tuple(
                dict.fromkeys(int(value) for value in inds.reshape(-1).tolist())
            )
            if self.dynamic_cache.tail_slots and _hotset_mode():
                (
                    routed,
                    self.dynamic_lookup_values,
                    self.dynamic_tail_lookup_values,
                ) = self.dynamic_cache.decode_hotset(
                    self.dynamic_layer,
                    requested,
                    self.switch_mlp,
                    x,
                    inds,
                    scores,
                )
                return routed + shared
            if self.dynamic_cache.tail_slots:
                (
                    routed,
                    self.dynamic_lookup_values,
                    self.dynamic_tail_lookup_values,
                ) = self.dynamic_cache.decode_tiered(
                    self.dynamic_layer,
                    requested,
                    self.switch_mlp,
                    x,
                    inds,
                    scores,
                    mapped,
                    shared,
                    promotion_limit=promotion_limit,
                )
                return routed + shared
            hit_count = int(mx.sum((mapped >= 0).astype(mx.int32)).item())
            if hit_count and self.dynamic_cache.direct_enabled():
                routed, self.dynamic_lookup_values = self.dynamic_cache.resolve_split(
                    self.dynamic_layer,
                    requested,
                    self.switch_mlp,
                    x,
                    inds,
                    scores,
                    mapped,
                    shared,
                )
            else:
                self.dynamic_lookup_values = self.dynamic_cache.resolve(
                    self.dynamic_layer, requested, self.switch_mlp
                )
                mapped = mx.array(self.dynamic_lookup_values, dtype=mx.int32)[inds]
                routed = _weighted_switch(self.switch_mlp, x, mapped, scores)
            return routed + shared

    Qwen4DynamicMoE.__name__ = "Qwen4DynamicMoE"
    Qwen4DynamicMoE.__qualname__ = "Qwen4DynamicMoE"
    qwen_language.Qwen3_5MoeSparseMoeBlock = Qwen4DynamicMoE

    original_sanitize = Model.sanitize

    def cached_sanitize(self, weights):
        sanitized = original_sanitize(self, weights)
        fused = {}
        consumed = set()
        marker = ".switch_mlp.gate_proj."
        for key, gate in sanitized.items():
            if marker not in key:
                continue
            up_key = key.replace(marker, ".switch_mlp.up_proj.")
            up = sanitized.get(up_key)
            if up is None:
                raise ValueError(f"Qwen4 cached runtime is missing {up_key}")
            fused[key.replace(marker, ".switch_mlp.gate_up_proj.")] = mx.concatenate(
                (gate, up), axis=1
            )
            consumed.update((key, up_key))
        sanitized = {
            key: value for key, value in sanitized.items() if key not in consumed
        }
        sanitized.update(fused)
        for layer_index, decoder in enumerate(self.language_model.model.layers):
            block = decoder.mlp
            if isinstance(block, Qwen4DynamicMoE):
                block.dynamic_layer = layer_index
                block.dynamic_lookup_values = dynamic.lookup(layer_index)
                block.dynamic_tail_lookup_values = dynamic.tail_lookup(layer_index)
        return sanitized

    cached_sanitize._omlx_qwen4_dynamic = True
    Model.sanitize = cached_sanitize
    _APPLIED = True
    logger.info("Qwen4 exact dynamic cache applied: slots=%d store=%s", slots, directory)
    return True


@contextlib.contextmanager
def qwen4_dynamic_safetensors_on_load(model_path: str | os.PathLike[str]):
    """Install Qwen4 sanitize compatibility and optional compact MoE read."""

    if not _is_qwen4(model_path):
        yield
        return
    from omlx.patches.mlx_vlm_qwen4_exp_compat import (
        configure_qwen4_exp_runtime,
    )

    configure_qwen4_exp_runtime(model_path, mtp_enabled=False)
    dynamic_enabled = _store_path() is not None
    if dynamic_enabled:
        apply_qwen4_dynamic_patch()
    import mlx_vlm.utils as vlm_utils
    import safetensors

    original = vlm_utils._load_safetensors
    original_safe_open = safetensors.safe_open
    target_dir = Path(model_path).expanduser().resolve()

    class _SafeOpenMetadataWrapper:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def metadata(self):
            metadata = self._inner.metadata()
            if isinstance(metadata, dict) and metadata.get("format") == "mlx":
                metadata = dict(metadata)
                metadata.pop("format", None)
            return metadata

    def patched_safe_open(filename, *args, **kwargs):
        handle = original_safe_open(filename, *args, **kwargs)
        # Prepared models are no-copy views whose shard paths are symlinks to
        # Hub blobs. Resolving ``filename`` here changes its parent to
        # ``.../blobs`` and leaves the MLX metadata untouched, causing mlx-vlm
        # to skip Qwen4 sanitize and reject hundreds of expert/PLE parameters.
        if _is_checkpoint_safetensor(filename, target_dir):
            return _SafeOpenMetadataWrapper(handle)
        return handle

    def compact_loader(path: str):
        return _compact_safetensors(path, original, slots=_slots())

    if dynamic_enabled:
        vlm_utils._load_safetensors = compact_loader
    safetensors.safe_open = patched_safe_open
    try:
        yield
    finally:
        if safetensors.safe_open is patched_safe_open:
            safetensors.safe_open = original_safe_open
        if dynamic_enabled and vlm_utils._load_safetensors is compact_loader:
            vlm_utils._load_safetensors = original


__all__ = [
    "apply_qwen4_dynamic_patch",
    "get_qwen4_dynamic_cache",
    "qwen4_dynamic_safetensors_on_load",
]
