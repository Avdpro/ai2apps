"""Cache-aware patch for mlx-lm's native Qwen3.5/3.6 MoE model."""

from __future__ import annotations

import logging
import os
import copy
import threading
from functools import cache
from typing import Any

import mlx.core as mx
import mlx.nn as nn

from .scope_cache import get_qwen36_fallback_loader
from .scope_policy import NUM_EXPERTS, load_qwen36_scope_policy
from .boost import Qwen36LossyPolicy

logger = logging.getLogger(__name__)
_PATCHED = False
_TIERED_TXN = threading.local()
_STRICT_ARENA_RECORDS: list[tuple[int, mx.array, mx.array]] | None = None
_ROUTE_OBSERVER = None
_PARITY_OBSERVER = None


class Qwen36StrictArenaMiss(RuntimeError):
    """Fail-closed oracle miss carrying only the first trustworthy layer."""

    def __init__(
        self,
        misses: int,
        layer: int,
        expert_ids: tuple[int, ...],
        requested_ids: tuple[int, ...],
    ):
        self.misses = misses
        self.layer = layer
        self.expert_ids = expert_ids
        self.requested_ids = requested_ids
        super().__init__(
            f"Qwen strict Arena run had {misses} unresolved expert routes; "
            f"discard its output; first miss layer={layer}, ids={expert_ids}"
        )


def set_qwen36_route_observer(observer) -> None:
    """Install a host-route observer used only at existing miss boundaries."""

    global _ROUTE_OBSERVER
    _ROUTE_OBSERVER = observer


def set_qwen36_parity_observer(observer) -> None:
    """Install an opt-in per-layer tensor observer for diagnostic replay."""

    global _PARITY_OBSERVER
    _PARITY_OBSERVER = observer


def qwen36_parity_observer_active() -> bool:
    """Return whether an exact route diagnostic must see every MoE layer."""

    return _PARITY_OBSERVER is not None


def begin_qwen36_strict_arena_run() -> None:
    """Start a fail-closed all-device Arena miss transaction."""

    global _STRICT_ARENA_RECORDS
    if _STRICT_ARENA_RECORDS is not None:
        raise RuntimeError("Qwen strict Arena transaction is already active")
    _STRICT_ARENA_RECORDS = []


def validate_qwen36_strict_arena_run() -> int:
    """Synchronize once, rejecting any speculative run that touched a miss."""

    global _STRICT_ARENA_RECORDS
    records = _STRICT_ARENA_RECORDS
    if records is None:
        raise RuntimeError("Qwen strict Arena transaction is not active")
    try:
        if not records:
            return 0
        all_mapped = mx.concatenate([record[2].reshape(-1) for record in records])
        total = mx.sum((all_mapped < 0).astype(mx.int32))
        mx.eval(total)
        misses = int(total.item())
        if misses:
            mx.eval(*(array for _, inds, mapped in records for array in (inds, mapped)))
            details = []
            for layer, inds, mapped in records:
                host_ids = [int(value) for value in inds.reshape(-1).tolist()]
                host_slots = [int(value) for value in mapped.reshape(-1).tolist()]
                if min(host_slots) >= 0:
                    continue
                details.append(
                    {
                        "layer": layer,
                        "requested": sorted(set(host_ids)),
                        "ids": [
                            expert_id
                            for expert_id, slot in zip(host_ids, host_slots, strict=True)
                            if slot < 0
                        ],
                    }
                )
            first = details[0]
            raise Qwen36StrictArenaMiss(
                misses,
                int(first["layer"]),
                tuple(int(value) for value in first["ids"]),
                tuple(int(value) for value in first["requested"]),
            )
        return 0
    finally:
        _STRICT_ARENA_RECORDS = None


def _observe_host_routes(block: Any, host_ids: list[int]) -> None:
    observer = _ROUTE_OBSERVER
    if observer is not None:
        observer(block.scope_layer, host_ids)


@cache
def _lookup(values: tuple[int, ...]) -> mx.array:
    return mx.array(values, dtype=mx.int32)


@cache
def _inverse_lookup(expert_ids: tuple[int, ...]) -> mx.array:
    values = [-1] * NUM_EXPERTS
    for slot, expert_id in enumerate(expert_ids):
        values[expert_id] = slot
    return mx.array(values, dtype=mx.int32)


def _weighted_switch(switch: Any, x: mx.array, inds: mx.array, scores: mx.array):
    routes = switch(x, inds)
    return (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)


def _available_experts(block: Any) -> mx.array:
    available = mx.array(block.scope_expert_to_slot_values, dtype=mx.int32) >= 0
    if block.scope_policy.backend == "tiered":
        available = available | (
            mx.array(block.scope_tail_to_slot_values, dtype=mx.int32) >= 0
        )
    elif block.scope_policy.backend == "flesh":
        loader = get_qwen36_fallback_loader(str(block.scope_policy.store_path))
        hot_ids = loader.hot_ids(block.scope_layer)
        if hot_ids:
            ids = mx.arange(NUM_EXPERTS, dtype=mx.int32)
            hot = mx.array(hot_ids, dtype=mx.int32)
            available = available | mx.any(ids[:, None] == hot[None, :], axis=1)
    return available


def _lossy_replace_routes(
    inds: mx.array,
    scores: mx.array,
    router_scores: mx.array,
    available: mx.array,
    policy: Qwen36LossyPolicy,
) -> tuple[mx.array, tuple[mx.array, mx.array, mx.array]]:
    """Replace eligible misses with the best cached experts on the GPU."""

    top_k = int(inds.shape[-1])
    count = min(policy.replace_count, top_k)
    all_ids = mx.arange(NUM_EXPERTS, dtype=inds.dtype)
    selected = mx.any(all_ids[None, None, None, :] == inds[..., None], axis=-2)
    candidates = available[None, None, :] & ~selected
    masked_scores = mx.where(candidates, router_scores, -mx.inf)
    candidate_ids = mx.argpartition(-masked_scores, kth=count - 1, axis=-1)[
        ..., :count
    ]
    candidate_values = mx.take_along_axis(masked_scores, candidate_ids, axis=-1)
    candidate_ids = mx.take_along_axis(
        candidate_ids, mx.argsort(-candidate_values, axis=-1), axis=-1
    )

    # Router Top-K ordering is unspecified. Select the actual lowest-weight
    # routes; Head2 uses count=6 and therefore protects the true highest two.
    positions = mx.argsort(scores, axis=-1)[..., :count]
    route_ids = mx.take_along_axis(inds, positions, axis=-1)
    eligible = ~available[route_ids]
    rank_positions = mx.arange(count, dtype=mx.int32)
    higher_weight = rank_positions[None, :] > rank_positions[:, None]
    candidate_rank = mx.sum(
        eligible[..., None, :] & higher_weight,
        axis=-1,
    ).astype(mx.int32)
    replacements = mx.take_along_axis(candidate_ids, candidate_rank, axis=-1)
    output = inds
    replaced_mask = mx.zeros(inds.shape, dtype=mx.bool_)
    top_positions = mx.arange(top_k, dtype=positions.dtype)
    for offset in range(count):
        apply = (top_positions == positions[..., offset, None]) & eligible[
            ..., offset, None
        ]
        output = mx.where(apply, replacements[..., offset, None], output)
        replaced_mask = replaced_mask | apply

    before = mx.sum((~available[inds]).astype(mx.int32))
    after = mx.sum((~available[output]).astype(mx.int32))
    replaced = mx.sum(replaced_mask.astype(mx.int32))
    return output, (replaced, before, after)


def _record_lossy(block: Any, counters: tuple[mx.array, mx.array, mx.array] | None):
    if counters is None:
        return
    replaced, before, after = (int(value.item()) for value in counters)
    stats = block.scope_lossy_stats
    stats["routes_replaced"] += replaced
    stats["misses_before"] += before
    stats["misses_after"] += after


def _arena_route_ids(
    host_ids: list[int], host_slots: list[int]
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return all routes to pin and the subset that needs loading."""

    requested = tuple(sorted(set(host_ids)))
    missing = tuple(
        sorted(
            {
                expert_id
                for expert_id, slot in zip(host_ids, host_slots, strict=True)
                if slot < 0
            }
        )
    )
    return requested, missing


def _arena_scope_moe(
    block: Any,
    x: mx.array,
    inds: mx.array,
    scores: mx.array,
    lossy_counters: tuple[mx.array, mx.array, mx.array] | None = None,
) -> mx.array:
    """Exact decode through one fixed-capacity SwitchGLU invocation."""

    # Arena mappings change after replacement; do not retain every historical
    # tuple in the static lookup cache during long generations.
    strict_records = _STRICT_ARENA_RECORDS
    expert_to_slot = (
        getattr(block, "scope_expert_to_slot_device")
        if strict_records is not None
        and getattr(block, "scope_expert_to_slot_device", None) is not None
        else mx.array(block.scope_expert_to_slot_values, dtype=mx.int32)
    )
    mapped = expert_to_slot[inds]
    if strict_records is not None:
        # Oracle-only optimistic execution. A safe placeholder keeps a missed
        # graph executable, but validation rejects the complete output.
        strict_records.append((block.scope_layer, inds, mapped))
        # Strict-oracle layouts are validated before their output is accepted.
        # Using the mapped vector directly keeps the all-hit compute graph
        # identical to the ordinary compact SwitchGLU path; -1 is only a
        # temporary last-slot placeholder in a run that will be discarded.
        return _weighted_switch(block.switch_mlp, x, mapped, scores)
    missing = mapped < 0
    missing_count = mx.sum(missing.astype(mx.int32))
    mx.eval(missing_count, *(lossy_counters or ()))
    _record_lossy(block, lossy_counters)
    count = int(missing_count.item())
    if count:
        # Decode has only Top-K entries. Materialize the already-required host
        # synchronization and preserve the complete route set: resident tail
        # hits must be pinned while the missing subset is loaded.
        mx.eval(inds, mapped)
        host_ids = [int(value) for value in inds.reshape(-1).tolist()]
        _observe_host_routes(block, host_ids)
        host_slots = [int(value) for value in mapped.reshape(-1).tolist()]
        requested_ids, missing_ids = _arena_route_ids(host_ids, host_slots)
        if not missing_ids or len(missing_ids) > count:
            raise RuntimeError("Qwen arena miss extraction disagrees with miss count")
        from .arena_cache import get_qwen36_decode_arena

        arena = get_qwen36_decode_arena(str(block.scope_policy.store_path))
        block.scope_expert_to_slot_values = arena.resolve(
            block.scope_layer,
            requested_ids,
            block.switch_mlp,
            expert_count=NUM_EXPERTS,
        )
        block.scope_expert_ids = arena.expert_ids(block.scope_layer)
        expert_to_slot = mx.array(
            block.scope_expert_to_slot_values, dtype=mx.int32
        )
        mapped = expert_to_slot[inds]
        mx.eval(mapped)
        if int(mx.min(mapped).item()) < 0:
            post_ids = tuple(int(value) for value in inds.reshape(-1).tolist())
            post_slots = tuple(int(value) for value in mapped.reshape(-1).tolist())
            unresolved = tuple(
                expert_id
                for expert_id, slot in zip(post_ids, post_slots, strict=True)
                if slot < 0
            )
            raise RuntimeError(
                f"Qwen arena layer {block.scope_layer} left unresolved routes "
                f"{unresolved}; pre_ids={tuple(host_ids)}, "
                f"pre_slots={tuple(host_slots)}, requested={requested_ids}, "
                f"missing={missing_ids}, "
                f"post_ids={post_ids}, post_slots={post_slots}"
            )
        if os.environ.get("OMLX_QWEN36_ARENA_ROUTE_VALIDATE", "0") == "1":
            requested = tuple(sorted({int(value) for value in inds.reshape(-1).tolist()}))
            loader = get_qwen36_fallback_loader(str(block.scope_policy.store_path))
            reference, reference_ids = loader.build_switch(
                block.scope_layer, list(requested), block.switch_mlp
            )
            reference_lookup = [-1] * NUM_EXPERTS
            for slot, expert_id in enumerate(reference_ids):
                reference_lookup[expert_id] = slot
            reference_slots = mx.array(reference_lookup, dtype=mx.int32)[inds]
            arena_routes = block.switch_mlp(x, mapped)
            reference_routes = reference(x, reference_slots)
            equal = mx.all(arena_routes == reference_routes)
            mx.eval(equal)
            if not bool(equal.item()):
                mx.eval(mapped, reference_slots)
                expanded = mx.expand_dims(x, (-2, -3))
                arena_gate_up = block.switch_mlp.gate_up_proj(expanded, mapped)
                reference_gate_up = reference.gate_up_proj(
                    expanded, reference_slots
                )
                arena_gate_nonfinite = mx.sum(
                    (~mx.isfinite(arena_gate_up)).astype(mx.int32)
                )
                reference_gate_nonfinite = mx.sum(
                    (~mx.isfinite(reference_gate_up)).astype(mx.int32)
                )
                arena_f32 = arena_routes.astype(mx.float32)
                reference_f32 = reference_routes.astype(mx.float32)
                finite = mx.isfinite(arena_f32) & mx.isfinite(reference_f32)
                abs_delta = mx.abs(arena_f32 - reference_f32)
                finite_delta = mx.max(mx.where(finite, abs_delta, 0))
                close = mx.allclose(
                    arena_f32, reference_f32, rtol=1e-4, atol=1e-4
                )
                arena_nonfinite = mx.sum((~mx.isfinite(arena_f32)).astype(mx.int32))
                reference_nonfinite = mx.sum(
                    (~mx.isfinite(reference_f32)).astype(mx.int32)
                )
                mx.eval(
                    finite_delta,
                    close,
                    arena_nonfinite,
                    reference_nonfinite,
                    arena_gate_nonfinite,
                    reference_gate_nonfinite,
                )
                raise RuntimeError(
                    f"Qwen arena route mismatch at layer {block.scope_layer}: "
                    f"requested={requested}, "
                    f"mapped={mapped.reshape(-1).tolist()}, "
                    f"reference_mapped={reference_slots.reshape(-1).tolist()}, "
                    f"max_finite_abs={float(finite_delta.item())}, "
                    f"allclose={bool(close.item())}, "
                    f"arena_nonfinite={int(arena_nonfinite.item())}, "
                    f"reference_nonfinite={int(reference_nonfinite.item())}, "
                    f"arena_gate_nonfinite={int(arena_gate_nonfinite.item())}, "
                    f"reference_gate_nonfinite={int(reference_gate_nonfinite.item())}"
                )
    return _weighted_switch(block.switch_mlp, x, mapped, scores)


def _tiered_scope_moe(
    block: Any,
    x: mx.array,
    inds: mx.array,
    scores: mx.array,
    lossy_counters: tuple[mx.array, mx.array, mx.array] | None = None,
) -> mx.array:
    """Compute resident routes first, then load and merge only SSD misses."""

    l1_lookup = _lookup(block.scope_expert_to_slot_values)
    tail_lookup = mx.array(block.scope_tail_to_slot_values, dtype=mx.int32)
    l1_mapped = l1_lookup[inds]
    tail_mapped = tail_lookup[inds]
    transaction = getattr(_TIERED_TXN, "current", None)
    if transaction is not None:
        missing = (l1_mapped < 0) & (tail_mapped < 0)
        miss_count = mx.sum(missing.astype(mx.int32))
        transaction.append(
            (block, inds, l1_mapped, tail_mapped, miss_count)
        )
        safe_l1 = mx.maximum(l1_mapped, mx.array(0, dtype=mx.int32))
        safe_tail = mx.maximum(tail_mapped, mx.array(0, dtype=mx.int32))
        l1_routes = block.switch_mlp(x, safe_l1)
        tail_routes = block.tail_switch_mlp(x, safe_tail)
        use_tail = (l1_mapped < 0) & (tail_mapped >= 0)
        routes = mx.where(use_tail[..., None], tail_routes, l1_routes)
        return (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)
    if os.environ.get("OMLX_QWEN36_TIERED_NOSYNC_PROBE", "0") == "1":
        # Diagnostic ceiling only: eliminate every per-layer host read and
        # deliberately substitute L1 slot zero for unavailable experts. This
        # is never an exact serving path; it quantifies whether a resumable
        # GPU pipeline is worth its scheduler/cache complexity.
        safe_l1 = mx.maximum(l1_mapped, mx.array(0, dtype=mx.int32))
        return _weighted_switch(block.switch_mlp, x, safe_l1, scores)
    l1_miss_count = mx.sum((l1_mapped < 0).astype(mx.int32))
    missing = (l1_mapped < 0) & (tail_mapped < 0)
    miss_count = mx.sum(missing.astype(mx.int32))
    mx.eval(
        inds,
        l1_mapped,
        tail_mapped,
        l1_miss_count,
        miss_count,
        *(lossy_counters or ()),
    )
    _record_lossy(block, lossy_counters)

    # Most scope-matched layers route all Top-8 experts through L1. Avoid
    # host ID materialization and Python grouping on that dominant path.
    if int(l1_miss_count.item()) == 0:
        from .tiered_cache import get_qwen36_tiered_cache

        get_qwen36_tiered_cache(str(block.scope_policy.store_path)).advance(
            block.scope_layer
        )
        return _weighted_switch(block.switch_mlp, x, l1_mapped, scores)

    host_ids = [int(value) for value in inds.reshape(-1).tolist()]
    _observe_host_routes(block, host_ids)
    host_l1 = [int(value) for value in l1_mapped.reshape(-1).tolist()]
    host_tail = [int(value) for value in tail_mapped.reshape(-1).tolist()]
    requested_ids = tuple(sorted(set(host_ids)))
    missing_ids = tuple(
        sorted(
            {
                expert_id
                for expert_id, l1_slot, tail_slot in zip(
                    host_ids, host_l1, host_tail, strict=True
                )
                if l1_slot < 0 and tail_slot < 0
            }
        )
    )
    if len(missing_ids) > int(miss_count.item()):
        raise RuntimeError("Qwen tiered miss extraction disagrees with miss count")

    tail_positions = [
        position
        for position, (l1_slot, tail_slot) in enumerate(zip(host_l1, host_tail))
        if l1_slot < 0 and tail_slot >= 0
    ]
    l1_positions = [
        position
        for position, l1_slot in enumerate(host_l1)
        if l1_slot >= 0
    ]
    missing_positions = [
        position
        for position, (l1_slot, tail_slot) in enumerate(zip(host_l1, host_tail))
        if l1_slot < 0 and tail_slot < 0
    ]

    batch, length, hidden = x.shape
    top_k = inds.shape[-1]
    flat_x = x.reshape(batch * length, hidden)
    route_x = mx.broadcast_to(
        flat_x[:, None, :], (batch * length, top_k, hidden)
    ).reshape(-1, hidden)

    def run_group(switch: Any, positions: list[int], slots: list[int]) -> mx.array:
        position_array = mx.array(positions, dtype=mx.int32)
        slot_array = mx.array(slots, dtype=mx.int32).reshape(1, -1, 1)
        return switch(route_x[position_array][None], slot_array).reshape(-1, hidden)

    ordered_positions: list[int] = []
    parts: list[mx.array] = []
    if tail_positions:
        ordered_positions.extend(tail_positions)
        parts.append(
            run_group(
                block.tail_switch_mlp,
                tail_positions,
                [host_tail[position] for position in tail_positions],
            )
        )
    if l1_positions:
        ordered_positions.extend(l1_positions)
        parts.append(
            run_group(
                block.switch_mlp,
                l1_positions,
                [host_l1[position] for position in l1_positions],
            )
        )

    # Submit hit computation before the blocking SSD read. The resulting
    # arrays remain live and are merged with only the missing route outputs.
    if missing_positions and parts:
        mx.async_eval(*parts)

    from .tiered_cache import get_qwen36_tiered_cache

    cache = get_qwen36_tiered_cache(str(block.scope_policy.store_path))
    block.scope_tail_to_slot_values = cache.resolve(
        block.scope_layer,
        requested_ids,
        block.tail_switch_mlp,
        expert_count=NUM_EXPERTS,
    )
    block.scope_tail_expert_ids = cache.tail_ids(block.scope_layer)
    if missing_positions:
        updated_tail = block.scope_tail_to_slot_values
        missing_slots = [updated_tail[host_ids[position]] for position in missing_positions]
        if min(missing_slots) < 0:
            raise RuntimeError(
                f"Qwen tiered layer {block.scope_layer} left an unresolved route"
            )
        ordered_positions.extend(missing_positions)
        parts.append(
            run_group(block.tail_switch_mlp, missing_positions, missing_slots)
        )

    inverse = [0] * len(host_ids)
    for ordered, original in enumerate(ordered_positions):
        inverse[original] = ordered
    routes = mx.concatenate(parts, axis=0)[mx.array(inverse, dtype=mx.int32)]
    routes = routes.reshape(batch, length, top_k, hidden)
    return (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)


def _shadow_prompt_cache(prompt_cache: list[Any]) -> list[Any]:
    """Clone cache metadata while sharing already-committed device buffers."""

    shadow = []
    for current in prompt_cache:
        clone = copy.copy(current)
        if hasattr(current, "cache"):
            clone.cache = list(current.cache)
        for name in ("lengths", "left_padding"):
            value = getattr(current, name, None)
            if isinstance(value, mx.array):
                setattr(clone, name, value + 0)
        shadow.append(clone)
    return shadow


def _make_model_call(original_call):
    """Wrap one-token decode in a single speculative cache transaction.

    MLX has no device-side conditional that can stop the graph at the first
    cache miss.  The all-hit path therefore evaluates the whole token and
    performs one host read at the token boundary.  If a miss occurred, only
    the first failed layer is trustworthy: its experts are installed in L0,
    the shadow KV is discarded, and the normal exact path recomputes the
    token.  In particular, this is not multi-token speculation and it never
    retries a chain of potentially-invalid downstream router decisions.
    """

    def patched(self, inputs, *args, **kwargs):
        policy = load_qwen36_scope_policy()
        stable_prefill = getattr(self, "_qwen36_stable_prefill", None)
        if (
            stable_prefill is not None
            and getattr(inputs, "shape", (0, 0))[-1] > 1
        ):
            return stable_prefill(
                lambda: original_call(self, inputs, *args, **kwargs)
            )
        prompt_cache = kwargs.get("cache")
        enabled = os.environ.get("OMLX_QWEN36_TIERED_TOKEN_TXN", "0") == "1"
        if (
            not enabled
            or policy is None
            or policy.backend != "tiered"
            or getattr(inputs, "shape", (0, 0))[-1] != 1
            or not isinstance(prompt_cache, list)
        ):
            return original_call(self, inputs, *args, **kwargs)

        shadow = _shadow_prompt_cache(prompt_cache)
        records: list[tuple[Any, mx.array, mx.array, mx.array, mx.array]] = []
        _TIERED_TXN.current = records
        call_kwargs = dict(kwargs)
        call_kwargs["cache"] = shadow
        try:
            result = original_call(self, inputs, *args, **call_kwargs)
        finally:
            _TIERED_TXN.current = None

        # One GPU -> CPU boundary and one small host transfer per token.  Keep
        # the per-layer flags and route metadata in device vectors instead of
        # issuing forty scalar .item() calls after evaluation.
        miss_counts = mx.stack([record[-1] for record in records])
        route_ids = mx.stack([record[1].reshape(-1) for record in records])
        l1_slots = mx.stack([record[2].reshape(-1) for record in records])
        tail_slots = mx.stack([record[3].reshape(-1) for record in records])
        mx.eval(result, miss_counts, route_ids, l1_slots, tail_slots)
        host_miss_counts = [int(value) for value in miss_counts.tolist()]
        first_failed_index = next(
            (index for index, count in enumerate(host_miss_counts) if count), None
        )
        if first_failed_index is None:
            prompt_cache[:] = shadow
            return result

        # Router decisions after the first failed layer were produced from an
        # incomplete residual and are not valid prefetch hints.  Prime only
        # this layer, then let the existing exact path recompute the token.
        block = records[first_failed_index][0]
        host_ids = [int(value) for value in route_ids[first_failed_index].tolist()]
        host_l1 = [int(value) for value in l1_slots[first_failed_index].tolist()]
        host_tail = [int(value) for value in tail_slots[first_failed_index].tolist()]
        requested = tuple(
            sorted(
                {
                    expert_id
                    for expert_id, l1_slot, tail_slot in zip(
                        host_ids, host_l1, host_tail, strict=True
                    )
                    if l1_slot < 0 and tail_slot < 0
                }
            )
        )
        if requested:
            from .tiered_cache import get_qwen36_tiered_cache

            cache = get_qwen36_tiered_cache(str(policy.store_path))
            block.scope_tail_to_slot_values = cache.resolve(
                block.scope_layer,
                requested,
                block.tail_switch_mlp,
                expert_count=NUM_EXPERTS,
            )
            block.scope_tail_expert_ids = cache.tail_ids(block.scope_layer)

        # Exact fail-closed recomputation: the real KV cache was not advanced.
        return original_call(self, inputs, *args, **kwargs)

    patched._dynamoe_qwen36_tiered_txn = True
    return patched


def _exact_scope_moe(
    block: Any,
    x: mx.array,
    inds: mx.array,
    scores: mx.array,
    lossy_counters: tuple[mx.array, mx.array, mx.array] | None = None,
) -> mx.array:
    batch, length, hidden = x.shape
    if length == 1 and block.scope_policy.backend == "arena":
        return _arena_scope_moe(block, x, inds, scores, lossy_counters)
    if length == 1 and block.scope_policy.backend == "tiered":
        return _tiered_scope_moe(block, x, inds, scores, lossy_counters)
    prefill_backend = os.environ.get(
        "OMLX_QWEN36_PREFILL_BACKEND", "stable-swap"
    ).strip().lower()
    if length > 1 and prefill_backend in ("dual128", "dual128-shared"):
        loader = get_qwen36_fallback_loader(str(block.scope_policy.store_path))
        dual_output = loader.prefill_dual_forward(
            block,
            x,
            inds,
            scores,
            staging_slots=128,
            shared=prefill_backend == "dual128-shared",
        )
        if dual_output is not None:
            return dual_output
    if length > 1 and prefill_backend in (
        "layer216",
        "layer216-packed",
        "layer248",
        "layer248-packed",
    ):
        default_staging_slots = 128 if prefill_backend.startswith("layer248") else 96
        loader = get_qwen36_fallback_loader(str(block.scope_policy.store_path))
        layer_output = loader.prefill_layer_forward(
            block,
            x,
            inds,
            scores,
            staging_slots=int(
                os.environ.get(
                    "OMLX_QWEN36_PREFILL_WORKSPACE_SLOTS",
                    str(default_staging_slots),
                )
            ),
            packed=prefill_backend.endswith("-packed"),
        )
        if layer_output is not None:
            return layer_output
    if length > 1 and prefill_backend in ("global96", "global96-packed"):
        loader = get_qwen36_fallback_loader(str(block.scope_policy.store_path))
        global_output = loader.prefill_global_forward(
            block,
            x,
            inds,
            scores,
            staging_slots=int(
                os.environ.get("OMLX_QWEN36_PREFILL_WORKSPACE_SLOTS", "96")
            ),
            packed=prefill_backend == "global96-packed",
        )
        if global_output is not None:
            return global_output
    if length > 1 and prefill_backend in ("workspace96", "packed96"):
        loader = get_qwen36_fallback_loader(str(block.scope_policy.store_path))
        workspace_output = loader.prefill_workspace_forward(
            block,
            x,
            inds,
            scores,
            max_missing=int(
                os.environ.get("OMLX_QWEN36_PREFILL_WORKSPACE_SLOTS", "96")
            ),
            packed=prefill_backend == "packed96",
        )
        if workspace_output is not None:
            return workspace_output
    top_k = inds.shape[-1]
    # Multi-token prefill must not change its numerical grouping when an
    # Arena/Tiered L0 happens to contain additional experts.  All backends use
    # the same stable scope-L1 partition; mutable L0 is decode-only.
    expert_to_slot = _inverse_lookup(tuple(block.scope_protected_expert_ids))
    flat_inds = inds.reshape(-1)
    mapped = expert_to_slot[flat_inds]
    miss_mask = mapped < 0
    miss_count_array = mx.sum(miss_mask.astype(mx.int32))
    mx.eval(miss_count_array, *(lossy_counters or ()))
    _record_lossy(block, lossy_counters)
    miss_count = int(miss_count_array.item())
    if miss_count == 0:
        return _weighted_switch(block.switch_mlp, x, expert_to_slot[inds], scores)

    hit_count = flat_inds.size - miss_count
    order = mx.argsort(miss_mask.astype(mx.int32))
    inverse_order = mx.argsort(order)
    ordered_global = flat_inds[order]
    missing_routes = ordered_global[hit_count:]
    mx.eval(missing_routes, inds)
    _observe_host_routes(
        block, [int(value) for value in inds.reshape(-1).tolist()]
    )
    missing_ids = sorted({int(value) for value in missing_routes.tolist()})

    flat_x = x.reshape(batch * length, hidden)
    route_x = mx.broadcast_to(
        flat_x[:, None, :], (batch * length, top_k, hidden)
    ).reshape(-1, hidden)
    ordered_x = route_x[order]
    ordered_slots = mapped[order]
    parts = []
    if hit_count:
        hit = block.switch_mlp(
            ordered_x[:hit_count][None],
            ordered_slots[:hit_count].reshape(1, -1, 1),
        ).reshape(hit_count, hidden)
        parts.append(hit)

    loader = get_qwen36_fallback_loader(str(block.scope_policy.store_path))
    if length == 1:
        fallback, fallback_ids = loader.resolve_hot_switch(
            block.scope_layer, missing_ids, block.switch_mlp
        )
    else:
        fallback, fallback_ids = loader.build_switch(
            block.scope_layer,
            missing_ids,
            block.switch_mlp,
            persist=True,
        )
    missing_lookup = [-1] * NUM_EXPERTS
    for slot, expert_id in enumerate(fallback_ids):
        missing_lookup[expert_id] = slot
    missing_slots = mx.array(missing_lookup, dtype=mx.int32)[
        ordered_global[hit_count:]
    ]
    missed = fallback(
        ordered_x[hit_count:][None],
        missing_slots.reshape(1, -1, 1),
    ).reshape(miss_count, hidden)
    parts.append(missed)

    routes = mx.concatenate(parts, axis=0)[inverse_order]
    routes = routes.reshape(batch, length, top_k, hidden)
    return (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)


def _make_init(original_init):
    from mlx_lm.models.qwen3_next import Qwen3NextMLP
    from mlx_lm.models.switch_layers import SwitchGLU

    def patched(self, args):
        policy = load_qwen36_scope_policy()
        if policy is None:
            return original_init(self, args)
        nn.Module.__init__(self)
        dim = args.hidden_size
        self.norm_topk_prob = args.norm_topk_prob
        self.num_experts = args.num_experts
        self.top_k = args.num_experts_per_tok
        self.gate = nn.Linear(dim, args.num_experts, bias=False)
        primary_experts = (
            policy.resident_experts
            if policy.backend == "tiered"
            else policy.physical_experts
        )
        self.switch_mlp = SwitchGLU(
            dim,
            args.moe_intermediate_size,
            primary_experts,
        )
        if policy.backend == "tiered":
            self.tail_switch_mlp = SwitchGLU(
                dim,
                args.moe_intermediate_size,
                policy.arena_tail_slots,
            )
        self.shared_expert = Qwen3NextMLP(
            dim, args.shared_expert_intermediate_size
        )
        self.shared_expert_gate = nn.Linear(dim, 1, bias=False)
        self.sharding_group = None
        self.scope_policy = policy
        self.scope_layer = -1  # Assigned deterministically by Model.sanitize.
        self.scope_expert_ids = None
        self.scope_expert_to_slot_values = None
        self.scope_protected_expert_ids = None
        self.scope_tail_expert_ids = None
        self.scope_tail_to_slot_values = None
        self.scope_lossy_policy = None
        self.scope_lossy_stats = {
            "routes_replaced": 0,
            "misses_before": 0,
            "misses_after": 0,
        }

    return patched


def _make_call(original_call):
    def patched(self, x: mx.array):
        if getattr(self, "scope_policy", None) is None:
            return original_call(self, x)
        if self.scope_layer < 0 or self.scope_expert_to_slot_values is None:
            raise RuntimeError("Qwen3.6 scope layer was not initialized")
        if self.sharding_group is not None:
            raise RuntimeError("Qwen3.6 Flesh does not yet support sharding")

        gates = mx.softmax(self.gate(x), axis=-1, precise=True)
        inds = mx.argpartition(gates, kth=-self.top_k, axis=-1)[..., -self.top_k :]
        scores = mx.take_along_axis(gates, inds, axis=-1)
        if self.norm_topk_prob:
            scores = scores / scores.sum(axis=-1, keepdims=True)
        lossy_counters = None
        policy = self.scope_lossy_policy
        if policy is not None and x.shape[-2] == 1:
            inds, lossy_counters = _lossy_replace_routes(
                inds,
                scores,
                gates,
                _available_experts(self),
                policy,
            )
        routed_y = _exact_scope_moe(
            self, x, inds, scores, lossy_counters=lossy_counters
        )
        shared_y = self.shared_expert(x)
        y = routed_y + mx.sigmoid(self.shared_expert_gate(x)) * shared_y
        observer = _PARITY_OBSERVER
        if observer is not None:
            observer(self, x, inds, scores, routed_y, y)
        return y

    return patched


def _make_sanitize(original_sanitize):
    def patched(self, weights):
        sanitized = original_sanitize(self, weights)
        policy = load_qwen36_scope_policy()
        if policy is None:
            return sanitized
        layers = self.language_model.model.layers
        for layer, decoder in enumerate(layers):
            block = decoder.mlp
            block.scope_layer = layer
            protected_ids = policy.experts(layer, phase="decode")
            expert_ids = protected_ids
            if policy.backend == "arena":
                filler = tuple(
                    expert
                    for expert in range(NUM_EXPERTS)
                    if expert not in set(protected_ids)
                )[: policy.arena_tail_slots]
                expert_ids = protected_ids + filler
            tail_ids = (
                tuple(
                    expert
                    for expert in range(NUM_EXPERTS)
                    if expert not in set(protected_ids)
                )[: policy.arena_tail_slots]
                if policy.backend == "tiered"
                else ()
            )
            block.scope_expert_ids = expert_ids
            block.scope_protected_expert_ids = protected_ids
            lookup = [-1] * NUM_EXPERTS
            for slot, expert_id in enumerate(expert_ids):
                lookup[expert_id] = slot
            block.scope_expert_to_slot_values = tuple(lookup)
            if policy.backend == "arena":
                from .arena_cache import get_qwen36_decode_arena

                get_qwen36_decode_arena(str(policy.store_path)).initialize_layer(
                    layer,
                    expert_ids,
                    policy.resident_experts,
                )
            elif policy.backend == "tiered":
                from .tiered_cache import get_qwen36_tiered_cache

                block.scope_tail_expert_ids = tail_ids
                tail_lookup = [-1] * NUM_EXPERTS
                for slot, expert_id in enumerate(tail_ids):
                    tail_lookup[expert_id] = slot
                block.scope_tail_to_slot_values = tuple(tail_lookup)
                get_qwen36_tiered_cache(str(policy.store_path)).initialize_layer(
                    layer,
                    protected_ids,
                    tail_ids,
                )
            prefix = f"language_model.model.layers.{layer}.mlp.switch_mlp"
            for projection in ("gate_proj", "up_proj", "down_proj"):
                for tensor_name in ("weight", "scales", "biases"):
                    key = f"{prefix}.{projection}.{tensor_name}"
                    value = sanitized.get(key)
                    if value is not None:
                        if policy.backend == "tiered":
                            tail_key = key.replace(
                                ".switch_mlp.", ".tail_switch_mlp."
                            )
                            sanitized[tail_key] = value[list(tail_ids)]
                        sanitized[key] = value[list(expert_ids)]
        all_blocks = tuple(decoder.mlp for decoder in layers)
        model_key = id(self)
        loader = get_qwen36_fallback_loader(str(policy.store_path))
        loader.register_prefill_blocks(model_key, all_blocks)
        for block in all_blocks:
            block.scope_prefill_model_key = model_key
        return sanitized

    patched._dynamoe_qwen36_flesh = True
    return patched


def apply_qwen36_flesh_model_patch() -> bool:
    global _PATCHED
    if load_qwen36_scope_policy() is None:
        return False
    from mlx_lm.models.qwen3_5_moe import Model
    from mlx_lm.models.qwen3_next import Qwen3NextSparseMoeBlock

    if not getattr(Qwen3NextSparseMoeBlock, "_dynamoe_qwen36_flesh", False):
        Qwen3NextSparseMoeBlock.__init__ = _make_init(
            Qwen3NextSparseMoeBlock.__init__
        )
        Qwen3NextSparseMoeBlock.__call__ = _make_call(
            Qwen3NextSparseMoeBlock.__call__
        )
        Qwen3NextSparseMoeBlock._dynamoe_qwen36_flesh = True
    if not getattr(Model.sanitize, "_dynamoe_qwen36_flesh", False):
        Model.sanitize = _make_sanitize(Model.sanitize)
    if not getattr(Model.__call__, "_dynamoe_qwen36_tiered_txn", False):
        Model.__call__ = _make_model_call(Model.__call__)
    _PATCHED = True
    logger.info("Qwen3.6 Flesh model patch applied")
    return True


__all__ = [
    "apply_qwen36_flesh_model_patch",
    "begin_qwen36_strict_arena_run",
    "set_qwen36_parity_observer",
    "qwen36_parity_observer_active",
    "Qwen36StrictArenaMiss",
    "set_qwen36_route_observer",
    "validate_qwen36_strict_arena_run",
]
