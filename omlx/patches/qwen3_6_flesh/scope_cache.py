"""Exact Qwen3.6 expert fallback backed by expert-major stores."""

from __future__ import annotations

import copy
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import mlx.core as mx

from omlx.cache.moe_expert_store import ExpertMajorStore


@dataclass
class _HotBank:
    ids: tuple[int, ...]
    recency: list[int]
    records: dict[int, dict[str, mx.array]]
    switch: Any


class Qwen36FallbackLoader:
    """Build compact transient Qwen SwitchGLUs only at an exact miss."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._stores: dict[int, ExpertMajorStore] = {}
        self._staging: list[bytearray] = []
        self._arena: dict[int, _HotBank] = {}
        self._hot: dict[int, _HotBank] = {}
        self._lock = threading.RLock()
        self.io_workers = int(os.environ.get("OMLX_QWEN36_IO_WORKERS", "4"))
        if not 1 <= self.io_workers <= 16:
            raise ValueError("OMLX_QWEN36_IO_WORKERS must be 1..16")
        self._io_pool = (
            ThreadPoolExecutor(
                max_workers=self.io_workers,
                thread_name_prefix="qwen36-moe-read",
            )
            if self.io_workers > 1
            else None
        )
        self.fallback_calls = 0
        self.experts_loaded = 0
        self.bytes_loaded = 0
        self.load_seconds = 0.0
        self.hot_only_calls = 0
        self.hot_slots = int(os.environ.get("OMLX_QWEN36_HOT_SLOTS", "8"))
        if not 0 <= self.hot_slots <= 64:
            raise ValueError("OMLX_QWEN36_HOT_SLOTS must be 0..64")
        # Opt-in until an in-place Metal slot update removes mixed-bank costs.
        self.arena_slots = int(os.environ.get("OMLX_QWEN36_ARENA_SLOTS", "0"))
        if not 0 <= self.arena_slots <= 136:
            raise ValueError("OMLX_QWEN36_ARENA_SLOTS must be 0..136")
        self.prefill_experts_loaded = 0
        self.decode_experts_loaded = 0
        self._prefill_workspace: Any | None = None
        self._prefill_global_workspace: Any | None = None
        self._prefill_models: dict[int, tuple[Any, ...]] = {}
        self._prefill_global_blocks: tuple[Any, ...] = ()
        self._prefill_global_offsets: tuple[int, ...] = ()
        self._prefill_global_staging_start = 0
        self._prefill_layer_workspaces: dict[int, tuple[Any, tuple[Any, ...], int]] = {}
        self._prefill_dual_staging: dict[int, Any] = {}
        self._prefill_dual_shared: Any | None = None
        self.prefill_workspace_calls = 0
        self.prefill_workspace_fallbacks = 0
        self.prefill_workspace_resident_experts = 0
        self.prefill_workspace_ssd_experts = 0
        self.prefill_workspace_patch_seconds = 0.0
        self.prefill_workspace_compute_seconds = 0.0
        self.prefill_workspace_packed_calls = 0
        self.prefill_global_calls = 0
        self.prefill_global_fallbacks = 0
        self.prefill_global_ssd_experts = 0
        self.prefill_global_build_seconds = 0.0
        self.prefill_global_patch_seconds = 0.0
        self.prefill_global_compute_seconds = 0.0
        self.prefill_layer_calls = 0
        self.prefill_layer_fallbacks = 0
        self.prefill_layer_ssd_experts = 0
        self.prefill_layer_build_seconds = 0.0
        self.prefill_layer_patch_seconds = 0.0
        self.prefill_layer_submit_seconds = 0.0
        self.prefill_dual_calls = 0
        self.prefill_dual_fallbacks = 0
        self.prefill_dual_ssd_experts = 0
        self.prefill_dual_build_seconds = 0.0
        self.prefill_dual_patch_seconds = 0.0
        self.prefill_dual_submit_seconds = 0.0

    def register_prefill_blocks(
        self, model_key: int, blocks: tuple[Any, ...]
    ) -> None:
        """Keep the model graph out of MLX Module attributes."""

        self._prefill_models[model_key] = blocks

    def prepare_layer_workspaces(self, model: Any, staging_slots: int) -> None:
        """Allocate private prefill banks during engine startup."""

        for decoder in model.language_model.model.layers:
            block = decoder.mlp
            layer = int(block.scope_layer)
            signature = (
                id(block.switch_mlp),
                tuple(block.scope_expert_ids),
                staging_slots,
            )
            state = self._prefill_layer_workspaces.get(layer)
            if state is not None and state[1] == signature:
                continue
            started = time.perf_counter()
            workspace, staging_start = self._layer_workspace_switch(
                block.switch_mlp, staging_slots
            )
            self._prefill_layer_workspaces[layer] = (
                workspace,
                signature,
                staging_start,
            )
            self.prefill_layer_build_seconds += time.perf_counter() - started

    def prepare_dual_staging(self, model: Any, staging_slots: int) -> None:
        """Allocate staging-only banks without duplicating resident weights."""

        for decoder in model.language_model.model.layers:
            block = decoder.mlp
            layer = int(block.scope_layer)
            if layer in self._prefill_dual_staging:
                continue
            started = time.perf_counter()
            self._prefill_dual_staging[layer] = self._workspace_switch_slots(
                block.switch_mlp, staging_slots
            )
            self.prefill_dual_build_seconds += time.perf_counter() - started

    def prepare_shared_dual_staging(self, model: Any, staging_slots: int) -> None:
        if self._prefill_dual_shared is not None:
            return
        block = model.language_model.model.layers[0].mlp
        started = time.perf_counter()
        self._prefill_dual_shared = self._workspace_switch_slots(
            block.switch_mlp, staging_slots
        )
        self.prefill_dual_build_seconds += time.perf_counter() - started

    def _store(self, layer: int) -> ExpertMajorStore:
        store = self._stores.get(layer)
        if store is None:
            store = ExpertMajorStore(self.directory / f"layer-{layer:03d}.moe")
            self._stores[layer] = store
        return store

    def expert_record_bytes(self, layer: int) -> int:
        return self._store(layer).record_bytes

    def hot_ids(self, layer: int) -> tuple[int, ...]:
        """Return the currently materialized exact Decode hot-bank IDs."""

        with self._lock:
            state = self._hot.get(layer)
            return state.ids if state is not None else ()

    @staticmethod
    def _make_switch(
        resident: Any,
        tensors: dict[str, mx.array],
    ) -> Any:
        fallback = copy.copy(resident)
        # Qwen's post-load gate/up fusion is preserved for the resident bank.
        # Recreate the same layout for transient experts from the separate
        # gate/up records on disk.
        gate_up = getattr(resident, "gate_up_proj", None)
        projection_names = (
            ("gate_up_proj", "down_proj")
            if gate_up is not None
            else ("gate_proj", "up_proj", "down_proj")
        )
        for projection_name in projection_names:
            template = getattr(resident, projection_name)
            projection = copy.copy(template)
            if projection_name == "gate_up_proj":
                for tensor_name in ("weight", "scales", "biases"):
                    value = tensors.get(f"gate_up_proj.{tensor_name}")
                    if value is None:
                        gate_value = tensors.get(f"gate_proj.{tensor_name}")
                        up_value = tensors.get(f"up_proj.{tensor_name}")
                        if gate_value is None or up_value is None:
                            continue
                        value = mx.concatenate([gate_value, up_value], axis=1)
                    current = template.get(tensor_name)
                    if current is not None and value.dtype != current.dtype:
                        value = value.astype(current.dtype)
                    setattr(projection, tensor_name, value)
            else:
                for tensor_name in ("weight", "scales", "biases"):
                    value = tensors.get(f"{projection_name}.{tensor_name}")
                    if value is None:
                        continue
                    current = template.get(tensor_name)
                    if current is not None and value.dtype != current.dtype:
                        value = value.astype(current.dtype)
                    setattr(projection, tensor_name, value)
            setattr(fallback, projection_name, projection)
        return fallback

    def build_switch(
        self,
        layer: int,
        expert_ids: list[int],
        resident: Any,
        *,
        persist: bool = False,
    ) -> tuple[Any, tuple[int, ...]]:
        ids = tuple(dict.fromkeys(int(value) for value in expert_ids))
        if not ids:
            raise ValueError("cannot build an empty Qwen3.6 fallback bank")
        started = time.perf_counter()
        with self._lock:
            store = self._store(layer)
            records_by_id = self._read_records(store, ids)
            records = [records_by_id[expert_id] for expert_id in ids]
            tensors = {
                name: mx.stack([record[name] for record in records])
                for name in records[0]
            }
            mx.eval(*tensors.values())
            fallback = self._make_switch(resident, tensors)
            if persist and self.arena_slots:
                arena_ids = ids[-self.arena_slots :]
                arena_records = {
                    expert_id: records_by_id[expert_id] for expert_id in arena_ids
                }
                arena_tensors = (
                    tensors
                    if arena_ids == ids
                    else self._stack_records(arena_ids, arena_records)
                )
                if arena_tensors is not tensors:
                    mx.eval(*arena_tensors.values())
                arena_switch = (
                    fallback
                    if arena_ids == ids
                    else self._make_switch(resident, arena_tensors)
                )
                self._arena[layer] = _HotBank(
                    ids=arena_ids,
                    recency=list(arena_ids),
                    records=arena_records,
                    switch=arena_switch,
                )
        elapsed = time.perf_counter() - started
        self.fallback_calls += 1
        self.experts_loaded += len(ids)
        self.bytes_loaded += len(ids) * store.record_bytes
        self.load_seconds += elapsed
        if persist:
            self.prefill_experts_loaded += len(ids)
        else:
            self.decode_experts_loaded += len(ids)
        return fallback, ids

    def _read_records(
        self, store: ExpertMajorStore, ids: tuple[int, ...]
    ) -> dict[int, dict[str, mx.array]]:
        while len(self._staging) < len(ids):
            self._staging.append(store.allocate_staging())
        pairs = list(zip(ids, self._staging, strict=False))
        if self._io_pool is not None and len(pairs) > 1:
            futures = [
                self._io_pool.submit(store.read_into, expert_id, staging)
                for expert_id, staging in pairs
            ]
            raw_records = [future.result() for future in futures]
        else:
            raw_records = [
                store.read_into(expert_id, staging)
                for expert_id, staging in pairs
            ]
        result = {}
        for (expert_id, _), record in zip(pairs, raw_records, strict=True):
            result[expert_id] = store.mlx_tensor_views(record, copy_record=True)
        return result

    @staticmethod
    def _workspace_switch(resident: Any) -> Any:
        """Allocate one full-ID scratch bank shared by all prefill layers."""

        workspace = copy.copy(resident)
        projections = (
            ("gate_up_proj",)
            if getattr(resident, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        arrays = []
        for projection_name in projections:
            template = getattr(resident, projection_name)
            projection = copy.copy(template)
            for tensor_name in ("weight", "scales", "biases"):
                value = template.get(tensor_name)
                if value is None:
                    continue
                backing = mx.zeros((256, *value.shape[1:]), dtype=value.dtype)
                setattr(projection, tensor_name, backing)
                arrays.append(backing)
            setattr(workspace, projection_name, projection)
        mx.eval(*arrays)
        return workspace

    @staticmethod
    def _workspace_switch_slots(resident: Any, slots: int) -> Any:
        workspace = copy.copy(resident)
        projections = (
            ("gate_up_proj",)
            if getattr(resident, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        arrays = []
        for projection_name in projections:
            template = getattr(resident, projection_name)
            projection = copy.copy(template)
            for tensor_name in ("weight", "scales", "biases"):
                value = template.get(tensor_name)
                if value is None:
                    continue
                backing = mx.zeros((slots, *value.shape[1:]), dtype=value.dtype)
                setattr(projection, tensor_name, backing)
                arrays.append(backing)
            setattr(workspace, projection_name, projection)
        mx.eval(*arrays)
        return workspace

    @staticmethod
    def _dual_projection(
        projection: Any,
        staging_projection: Any,
        x: mx.array,
        segment_ids: mx.array,
        segment_starts: mx.array,
        segment_counts: mx.array,
        max_rows: int,
    ) -> mx.array:
        from omlx.custom_kernels.qwen35_prefill import fast

        if int(getattr(projection, "bits", 0)) != 4 or int(
            getattr(projection, "group_size", 0)
        ) != 64:
            raise RuntimeError("dual-source QMM requires affine q4/group64")
        try:
            return fast.qwen35_q4_dual_gather_qmm_t(
                mx.contiguous(x),
                segment_ids,
                segment_starts,
                segment_counts,
                max_rows,
                projection.weight,
                projection.scales,
                projection.biases,
                staging_projection.weight,
                staging_projection.scales,
                staging_projection.biases,
            )
        except Exception as exc:
            raise RuntimeError(
                "dual-source projection submission failed: "
                f"x={x.shape}/{x.dtype}, segments={segment_ids.shape}, "
                f"resident={projection.weight.shape}/{projection.weight.dtype}, "
                f"staging={staging_projection.weight.shape}/"
                f"{staging_projection.weight.dtype}"
            ) from exc

    def prefill_dual_forward(
        self,
        block: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
        *,
        staging_slots: int = 128,
        shared: bool = False,
    ) -> mx.array | None:
        """Exact-intent dual resident/staging MoE prefill prototype."""

        from omlx.custom_kernels.qwen35_prefill import fast

        if not fast.has_symbol("qwen35_q4_dual_gather_qmm_t"):
            self.prefill_dual_fallbacks += 1
            return None
        layer = int(block.scope_layer)
        staging = (
            self._prefill_dual_shared
            if shared
            else self._prefill_dual_staging.get(layer)
        )
        if staging is None:
            started = time.perf_counter()
            staging = self._workspace_switch_slots(block.switch_mlp, staging_slots)
            if shared:
                self._prefill_dual_shared = staging
            else:
                self._prefill_dual_staging[layer] = staging
            self.prefill_dual_build_seconds += time.perf_counter() - started

        mx.eval(inds)
        requested = tuple(sorted({int(value) for value in inds.reshape(-1).tolist()}))
        resident_lookup = {
            expert_id: slot
            for slot, expert_id in enumerate(tuple(block.scope_expert_ids))
        }
        missing_ids = tuple(
            expert_id for expert_id in requested if expert_id not in resident_lookup
        )
        if len(missing_ids) > staging_slots:
            self.prefill_dual_fallbacks += 1
            return None

        patch_started = time.perf_counter()
        if missing_ids:
            store = self._store(layer)
            records = self._read_records(store, missing_ids)
            from .arena_cache import Qwen36DecodeArena

            Qwen36DecodeArena._patch_switch(
                staging,
                list(range(len(missing_ids))),
                missing_ids,
                records,
                evaluate=False,
            )
            self.experts_loaded += len(missing_ids)
            self.prefill_experts_loaded += len(missing_ids)
            self.bytes_loaded += len(missing_ids) * store.record_bytes
            self.prefill_dual_ssd_experts += len(missing_ids)
        self.prefill_dual_patch_seconds += time.perf_counter() - patch_started

        lookup = [0] * 256
        for expert_id, slot in resident_lookup.items():
            lookup[expert_id] = slot
        for slot, expert_id in enumerate(missing_ids):
            lookup[expert_id] = 0x80000000 | slot
        flat_global = [int(value) for value in inds.reshape(-1).tolist()]
        flat_encoded = [lookup[expert_id] for expert_id in flat_global]
        host_order = sorted(range(len(flat_encoded)), key=flat_encoded.__getitem__)
        sorted_ids = [flat_encoded[index] for index in host_order]
        segment_ids_host: list[int] = []
        segment_starts_host: list[int] = []
        segment_counts_host: list[int] = []
        for position, encoded_id in enumerate(sorted_ids):
            if not segment_ids_host or encoded_id != segment_ids_host[-1]:
                segment_ids_host.append(encoded_id)
                segment_starts_host.append(position)
                segment_counts_host.append(1)
            else:
                segment_counts_host[-1] += 1
        order = mx.array(host_order, dtype=mx.uint32)
        inv_order = mx.argsort(order)
        top_k = int(inds.shape[-1])
        expanded = mx.expand_dims(x, (-2, -3))
        x_sorted = expanded.flatten(0, -3)[order // top_k]
        segment_ids = mx.array(segment_ids_host, dtype=mx.uint32)
        segment_starts = mx.array(segment_starts_host, dtype=mx.uint32)
        segment_counts = mx.array(segment_counts_host, dtype=mx.uint32)
        max_rows = max(segment_counts_host)

        from omlx.patches.qwen35_moe_weighted_sum import _native_weighted_sum

        weighted_sum = _native_weighted_sum()
        if weighted_sum is None:
            self.prefill_dual_fallbacks += 1
            return None
        submit_started = time.perf_counter()
        gate_up = self._dual_projection(
            block.switch_mlp.gate_up_proj,
            staging.gate_up_proj,
            x_sorted,
            segment_ids,
            segment_starts,
            segment_counts,
            max_rows,
        )
        if os.environ.get("OMLX_QWEN36_DUAL_DEBUG_SYNC", "0") == "1":
            try:
                mx.eval(gate_up)
            except Exception as exc:
                raise RuntimeError(
                    f"dual128 gate-up failed at layer {layer}: "
                    f"x={x_sorted.shape}, segments={segment_ids.shape}"
                ) from exc
        x_gate, x_up = mx.split(gate_up, 2, axis=-1)
        hidden = block.switch_mlp.activation(x_up, x_gate)
        routed = self._dual_projection(
            block.switch_mlp.down_proj,
            staging.down_proj,
            hidden,
            segment_ids,
            segment_starts,
            segment_counts,
            max_rows,
        )
        if os.environ.get("OMLX_QWEN36_DUAL_DEBUG_SYNC", "0") == "1":
            try:
                mx.eval(routed)
            except Exception as exc:
                raise RuntimeError(
                    f"dual128 down failed at layer {layer}: "
                    f"hidden={hidden.shape}, segments={segment_ids.shape}"
                ) from exc
        output = weighted_sum(
            mx.contiguous(routed),
            mx.contiguous(inv_order.astype(mx.uint32)),
            mx.contiguous(scores.astype(mx.float32)),
        )
        self.prefill_dual_submit_seconds += time.perf_counter() - submit_started
        self.prefill_dual_calls += 1
        return output

    @staticmethod
    def _global_workspace_switch(
        blocks: tuple[Any, ...], staging_slots: int
    ) -> tuple[Any, tuple[int, ...], int]:
        """Build a DMoE-style global resident arena plus shared miss slots."""

        switches = tuple(block.switch_mlp for block in blocks)
        workspace = copy.copy(switches[0])
        offsets = []
        cursor = 0
        for switch in switches:
            offsets.append(cursor)
            cursor += int(switch.down_proj.weight.shape[0])
        staging_start = cursor
        arrays = []
        projections = (
            ("gate_up_proj",)
            if getattr(switches[0], "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        for projection_name in projections:
            template = getattr(switches[0], projection_name)
            projection = copy.copy(template)
            for tensor_name in ("weight", "scales", "biases"):
                first = template.get(tensor_name)
                if first is None:
                    continue
                resident = [
                    getattr(switch, projection_name).get(tensor_name)
                    for switch in switches
                ]
                staging = mx.zeros(
                    (staging_slots, *first.shape[1:]), dtype=first.dtype
                )
                backing = mx.concatenate((*resident, staging), axis=0)
                setattr(projection, tensor_name, backing)
                arrays.append(backing)
            setattr(workspace, projection_name, projection)
        mx.eval(*arrays)
        return workspace, tuple(offsets), staging_start

    def prefill_global_forward(
        self,
        block: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
        *,
        staging_slots: int = 96,
        packed: bool = False,
    ) -> mx.array | None:
        """Exact prefill through one global resident arena and shared staging."""

        blocks = self._prefill_models.get(
            int(getattr(block, "scope_prefill_model_key", -1)), ()
        )
        if not blocks:
            self.prefill_global_fallbacks += 1
            return None
        # The Decode banks can be restored to a session-owned adaptive layout
        # after prefill.  The duplicate global arena intentionally keeps the
        # stable prefill layout.  Rebuild only when that layout itself changes.
        signature = tuple(
            (id(item.switch_mlp), tuple(item.scope_expert_ids))
            for item in blocks
        )
        if (
            self._prefill_global_workspace is None
            or self._prefill_global_blocks != signature
        ):
            build_started = time.perf_counter()
            (
                self._prefill_global_workspace,
                self._prefill_global_offsets,
                self._prefill_global_staging_start,
            ) = self._global_workspace_switch(blocks, staging_slots)
            self._prefill_global_blocks = signature
            self.prefill_global_build_seconds += time.perf_counter() - build_started

        mx.eval(inds)
        requested = tuple(sorted({int(value) for value in inds.reshape(-1).tolist()}))
        resident_lookup = {
            expert_id: slot
            for slot, expert_id in enumerate(tuple(block.scope_expert_ids))
        }
        missing_ids = tuple(
            expert_id for expert_id in requested if expert_id not in resident_lookup
        )
        if len(missing_ids) > staging_slots:
            self.prefill_global_fallbacks += 1
            return None

        patch_started = time.perf_counter()
        if missing_ids:
            store = self._store(block.scope_layer)
            records = self._read_records(store, missing_ids)
            slots = list(
                range(
                    self._prefill_global_staging_start,
                    self._prefill_global_staging_start + len(missing_ids),
                )
            )
            from .arena_cache import Qwen36DecodeArena

            Qwen36DecodeArena._patch_switch(
                self._prefill_global_workspace,
                slots,
                missing_ids,
                records,
            )
            self.experts_loaded += len(missing_ids)
            self.prefill_experts_loaded += len(missing_ids)
            self.bytes_loaded += len(missing_ids) * store.record_bytes
            self.prefill_global_ssd_experts += len(missing_ids)
        self.prefill_global_patch_seconds += time.perf_counter() - patch_started

        layer_offset = self._prefill_global_offsets[block.scope_layer]
        lookup = [-1] * 256
        for expert_id, slot in resident_lookup.items():
            lookup[expert_id] = layer_offset + slot
        for slot, expert_id in enumerate(missing_ids):
            lookup[expert_id] = self._prefill_global_staging_start + slot
        local = mx.array(lookup, dtype=mx.int32)[inds]

        compute_started = time.perf_counter()
        if packed:
            from omlx.patches.qwen35_moe_weighted_sum import (
                _native_switch_weighted_sum,
                _native_weighted_sum,
            )

            weighted_sum = _native_weighted_sum()
            if weighted_sum is None:
                self.prefill_global_fallbacks += 1
                return None
            output = _native_switch_weighted_sum(
                self._prefill_global_workspace,
                x,
                local,
                scores,
                weighted_sum,
            )
        else:
            routes = self._prefill_global_workspace(x, local)
            output = (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)
        mx.eval(output)
        self.prefill_global_compute_seconds += time.perf_counter() - compute_started
        self.prefill_global_calls += 1
        return output

    @staticmethod
    def _layer_workspace_switch(
        resident: Any, staging_slots: int
    ) -> tuple[Any, int]:
        """Duplicate one compact resident bank and append private miss slots."""

        workspace = copy.copy(resident)
        staging_start = int(resident.down_proj.weight.shape[0])
        arrays = []
        projections = (
            ("gate_up_proj",)
            if getattr(resident, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        for projection_name in projections:
            template = getattr(resident, projection_name)
            projection = copy.copy(template)
            for tensor_name in ("weight", "scales", "biases"):
                value = template.get(tensor_name)
                if value is None:
                    continue
                staging = mx.zeros(
                    (staging_slots, *value.shape[1:]), dtype=value.dtype
                )
                backing = mx.concatenate((value, staging), axis=0)
                setattr(projection, tensor_name, backing)
                arrays.append(backing)
            setattr(workspace, projection_name, projection)
        mx.eval(*arrays)
        return workspace, staging_start

    def prefill_layer_forward(
        self,
        block: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
        *,
        staging_slots: int = 96,
        packed: bool = False,
    ) -> mx.array | None:
        """Exact prefill using a persistent compact workspace per MoE layer."""

        layer = int(block.scope_layer)
        state = self._prefill_layer_workspaces.get(layer)
        protected_ids = tuple(block.scope_protected_expert_ids)
        state_ids = tuple(state[1][1]) if state is not None else ()
        state_matches = (
            state is not None
            and state[1][0] == id(block.switch_mlp)
            and state[1][2] == staging_slots
            and state_ids[: len(protected_ids)] == protected_ids
        )
        if not state_matches:
            signature = (
                id(block.switch_mlp),
                tuple(block.scope_expert_ids),
                staging_slots,
            )
            build_started = time.perf_counter()
            workspace, staging_start = self._layer_workspace_switch(
                block.switch_mlp, staging_slots
            )
            state = (workspace, signature, staging_start)
            self._prefill_layer_workspaces[layer] = state
            self.prefill_layer_build_seconds += time.perf_counter() - build_started
        workspace, _, staging_start = state

        mx.eval(inds)
        requested = tuple(sorted({int(value) for value in inds.reshape(-1).tolist()}))
        # The private prefill bank owns its resident-ID mapping. Decode L0
        # replacement must not force a rebuild on the next turn; only an L1
        # promotion invalidates the protected prefix and reaches the branch
        # above.
        workspace_ids = tuple(state[1][1])
        resident_lookup = {
            expert_id: slot
            for slot, expert_id in enumerate(workspace_ids)
        }
        missing_ids = tuple(
            expert_id for expert_id in requested if expert_id not in resident_lookup
        )
        if len(missing_ids) > staging_slots:
            self.prefill_layer_fallbacks += 1
            return None

        patch_started = time.perf_counter()
        if missing_ids:
            store = self._store(layer)
            records = self._read_records(store, missing_ids)
            from .arena_cache import Qwen36DecodeArena

            # This bank is private to the layer and is not reused until the
            # next request, after the current generation has completed.  Keep
            # the patch and QMM in one lazy GPU graph instead of synchronizing
            # at every layer boundary.
            Qwen36DecodeArena._patch_switch(
                workspace,
                list(range(staging_start, staging_start + len(missing_ids))),
                missing_ids,
                records,
                evaluate=False,
            )
            self.experts_loaded += len(missing_ids)
            self.prefill_experts_loaded += len(missing_ids)
            self.bytes_loaded += len(missing_ids) * store.record_bytes
            self.prefill_layer_ssd_experts += len(missing_ids)
        self.prefill_layer_patch_seconds += time.perf_counter() - patch_started

        lookup = [-1] * 256
        for expert_id, slot in resident_lookup.items():
            lookup[expert_id] = slot
        for slot, expert_id in enumerate(missing_ids):
            lookup[expert_id] = staging_start + slot
        local = mx.array(lookup, dtype=mx.int32)[inds]

        submit_started = time.perf_counter()
        if packed:
            from omlx.patches.qwen35_moe_weighted_sum import (
                _native_switch_weighted_sum,
                _native_weighted_sum,
            )

            weighted_sum = _native_weighted_sum()
            if weighted_sum is None:
                self.prefill_layer_fallbacks += 1
                return None
            output = _native_switch_weighted_sum(
                workspace, x, local, scores, weighted_sum
            )
        else:
            routes = workspace(x, local)
            output = (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)
        self.prefill_layer_submit_seconds += time.perf_counter() - submit_started
        self.prefill_layer_calls += 1
        return output

    @staticmethod
    def _snapshot_resident_records(
        sources: dict[int, tuple[Any, int]], expert_ids: tuple[int, ...]
    ) -> dict[int, dict[str, mx.array]]:
        records = {expert_id: {} for expert_id in expert_ids}
        groups: dict[int, tuple[Any, list[tuple[int, int]]]] = {}
        for expert_id in expert_ids:
            switch, slot = sources[expert_id]
            groups.setdefault(id(switch), (switch, []))[1].append((expert_id, slot))
        snapshots = []
        for switch, members in groups.values():
            projections = (
                ("gate_up_proj",)
                if getattr(switch, "gate_up_proj", None) is not None
                else ("gate_proj", "up_proj")
            ) + ("down_proj",)
            slots = mx.array([slot for _, slot in members], dtype=mx.int32)
            for projection_name in projections:
                projection = getattr(switch, projection_name)
                for tensor_name in ("weight", "scales", "biases"):
                    value = projection.get(tensor_name)
                    if value is None:
                        continue
                    snapshot = mx.zeros_like(value[slots])
                    snapshot[:] = value[slots]
                    snapshots.append(snapshot)
                    key = f"{projection_name}.{tensor_name}"
                    for index, (expert_id, _) in enumerate(members):
                        records[expert_id][key] = snapshot[index]
        if snapshots:
            mx.eval(*snapshots)
        return records

    def prefill_workspace_forward(
        self,
        block: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
        *,
        max_missing: int = 96,
        packed: bool = False,
    ) -> mx.array | None:
        """Exact single-SwitchGLU prefill through resident reuse + SSD scratch."""

        mx.eval(inds)
        requested = tuple(sorted({int(value) for value in inds.reshape(-1).tolist()}))
        sources = {
            expert_id: (block.switch_mlp, slot)
            for slot, expert_id in enumerate(tuple(block.scope_expert_ids))
        }
        tail_ids = tuple(getattr(block, "scope_tail_expert_ids", ()) or ())
        tail_switch = getattr(block, "tail_switch_mlp", None)
        if tail_switch is not None:
            sources.update(
                {
                    expert_id: (tail_switch, slot)
                    for slot, expert_id in enumerate(tail_ids)
                }
            )
        resident_ids = tuple(expert for expert in requested if expert in sources)
        missing_ids = tuple(expert for expert in requested if expert not in sources)
        if len(missing_ids) > max_missing:
            self.prefill_workspace_fallbacks += 1
            return None

        if self._prefill_workspace is None:
            self._prefill_workspace = self._workspace_switch(block.switch_mlp)

        started = time.perf_counter()
        records = self._snapshot_resident_records(sources, resident_ids)
        if missing_ids:
            store = self._store(block.scope_layer)
            records.update(self._read_records(store, missing_ids))
            self.experts_loaded += len(missing_ids)
            self.prefill_experts_loaded += len(missing_ids)
            self.bytes_loaded += len(missing_ids) * store.record_bytes
        from .arena_cache import Qwen36DecodeArena

        slots = list(range(len(requested)))
        Qwen36DecodeArena._patch_switch(
            self._prefill_workspace, slots, requested, records
        )
        self.prefill_workspace_patch_seconds += time.perf_counter() - started

        lookup = [-1] * 256
        for slot, expert_id in enumerate(requested):
            lookup[expert_id] = slot
        local = mx.array(lookup, dtype=mx.int32)[inds]
        compute_started = time.perf_counter()
        if packed:
            from omlx.patches.qwen35_moe_weighted_sum import (
                _native_switch_weighted_sum,
                _native_weighted_sum,
            )

            weighted_sum = _native_weighted_sum()
            if weighted_sum is None:
                self.prefill_workspace_fallbacks += 1
                return None
            output = _native_switch_weighted_sum(
                self._prefill_workspace,
                x,
                local,
                scores,
                weighted_sum,
            )
            self.prefill_workspace_packed_calls += 1
        else:
            routes = self._prefill_workspace(x, local)
            output = (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)
        # The workspace backing is overwritten by the following model layer.
        mx.eval(output)
        self.prefill_workspace_compute_seconds += time.perf_counter() - compute_started
        self.prefill_workspace_calls += 1
        self.prefill_workspace_resident_experts += len(resident_ids)
        self.prefill_workspace_ssd_experts += len(missing_ids)
        return output

    @staticmethod
    def _stack_records(
        ids: tuple[int, ...], records: dict[int, dict[str, mx.array]]
    ) -> dict[str, mx.array]:
        return {
            name: mx.stack([records[expert_id][name] for expert_id in ids])
            for name in records[ids[0]]
        }

    def resolve_hot_switch(
        self,
        layer: int,
        expert_ids: list[int],
        resident: Any,
    ) -> tuple[Any, tuple[int, ...]]:
        """Resolve Decode misses through a Qwen-owned rolling Hot8."""

        requested = tuple(dict.fromkeys(int(value) for value in expert_ids))
        if self.hot_slots == 0 and self.arena_slots == 0:
            return self.build_switch(layer, list(requested), resident)
        started = time.perf_counter()
        loaded_ids: tuple[int, ...] = ()
        with self._lock:
            store = self._store(layer)
            arena = self._arena.get(layer)
            arena_ids = arena.ids if arena is not None else ()
            arena_set = set(arena_ids)
            outside_arena = tuple(
                expert_id for expert_id in requested if expert_id not in arena_set
            )
            if not outside_arena:
                assert arena is not None
                self.hot_only_calls += 1
                self.fallback_calls += 1
                return arena.switch, arena.ids
            # A mixed arena/hot dispatch would require two SwitchGLU calls.
            # Keep the decode fast path to one kernel bank and use the arena
            # only when it satisfies the complete layer request.
            hot_requested = requested
            if self.hot_slots == 0 or len(hot_requested) > self.hot_slots:
                # This is uncommon for single-token decode, but remains exact.
                return self.build_switch(layer, list(requested), resident)

            state = self._hot.get(layer)
            records = dict(state.records) if state is not None else {}
            recency = list(state.recency) if state is not None else []
            for expert_id in hot_requested:
                if expert_id in recency:
                    recency.remove(expert_id)
                recency.append(expert_id)
            loaded_ids = tuple(
                expert_id for expert_id in hot_requested if expert_id not in records
            )
            if not loaded_ids:
                assert state is not None
                state.recency = recency[-self.hot_slots :]
                self.hot_only_calls += 1
                self.fallback_calls += 1
                return state.switch, state.ids

            records.update(self._read_records(store, loaded_ids))
            bank_ids = tuple(recency[-self.hot_slots :])
            records = {expert_id: records[expert_id] for expert_id in bank_ids}
            tensors = self._stack_records(bank_ids, records)
            mx.eval(*tensors.values())
            switch = self._make_switch(resident, tensors)
            self._hot[layer] = _HotBank(
                ids=bank_ids,
                recency=list(bank_ids),
                records=records,
                switch=switch,
            )
        elapsed = time.perf_counter() - started
        self.fallback_calls += 1
        self.experts_loaded += len(loaded_ids)
        self.bytes_loaded += len(loaded_ids) * store.record_bytes
        self.load_seconds += elapsed
        self.decode_experts_loaded += len(loaded_ids)
        return switch, bank_ids

    def stats(self) -> dict[str, float | int]:
        return {
            "fallback_calls": self.fallback_calls,
            "experts_loaded": self.experts_loaded,
            "bytes_loaded": self.bytes_loaded,
            "load_seconds": self.load_seconds,
            "hot_only_calls": self.hot_only_calls,
            "hot_layers": len(self._hot),
            "arena_layers": len(self._arena),
            "hot_slots": self.hot_slots,
            "arena_slots": self.arena_slots,
            "io_workers": self.io_workers,
            "prefill_experts_loaded": self.prefill_experts_loaded,
            "decode_experts_loaded": self.decode_experts_loaded,
            "prefill_workspace_calls": self.prefill_workspace_calls,
            "prefill_workspace_fallbacks": self.prefill_workspace_fallbacks,
            "prefill_workspace_resident_experts": self.prefill_workspace_resident_experts,
            "prefill_workspace_ssd_experts": self.prefill_workspace_ssd_experts,
            "prefill_workspace_patch_seconds": self.prefill_workspace_patch_seconds,
            "prefill_workspace_compute_seconds": self.prefill_workspace_compute_seconds,
            "prefill_workspace_packed_calls": self.prefill_workspace_packed_calls,
            "prefill_global_calls": self.prefill_global_calls,
            "prefill_global_fallbacks": self.prefill_global_fallbacks,
            "prefill_global_ssd_experts": self.prefill_global_ssd_experts,
            "prefill_global_build_seconds": self.prefill_global_build_seconds,
            "prefill_global_patch_seconds": self.prefill_global_patch_seconds,
            "prefill_global_compute_seconds": self.prefill_global_compute_seconds,
            "prefill_layer_calls": self.prefill_layer_calls,
            "prefill_layer_fallbacks": self.prefill_layer_fallbacks,
            "prefill_layer_ssd_experts": self.prefill_layer_ssd_experts,
            "prefill_layer_build_seconds": self.prefill_layer_build_seconds,
            "prefill_layer_patch_seconds": self.prefill_layer_patch_seconds,
            "prefill_layer_submit_seconds": self.prefill_layer_submit_seconds,
            "prefill_dual_calls": self.prefill_dual_calls,
            "prefill_dual_fallbacks": self.prefill_dual_fallbacks,
            "prefill_dual_ssd_experts": self.prefill_dual_ssd_experts,
            "prefill_dual_build_seconds": self.prefill_dual_build_seconds,
            "prefill_dual_patch_seconds": self.prefill_dual_patch_seconds,
            "prefill_dual_submit_seconds": self.prefill_dual_submit_seconds,
        }


@cache
def get_qwen36_fallback_loader(directory: str) -> Qwen36FallbackLoader:
    return Qwen36FallbackLoader(Path(directory).expanduser().resolve())


__all__ = ["Qwen36FallbackLoader", "get_qwen36_fallback_loader"]
