"""I/O-boundary expert filtering for Qwen3.6 Cache-MoE checkpoints."""

from __future__ import annotations

import contextlib
import json
import logging
import re
import struct
from pathlib import Path

import mlx.core as mx
import numpy as np

from .scope_policy import NUM_EXPERTS, Qwen36ScopePolicy, load_qwen36_scope_policy

logger = logging.getLogger(__name__)

_VLM_PATCHED = False

_STACKED_EXPERT_RE = re.compile(
    r"(?:^|\.)layers\.(\d+)\.mlp\.switch_mlp\."
    r"(?:gate_proj|up_proj|down_proj)\.(?:weight|scales|biases)$"
)

_STORAGE_DTYPES = {
    "I8": (np.int8, None),
    "I16": (np.int16, None),
    "I32": (np.int32, None),
    "I64": (np.int64, None),
    "U8": (np.uint8, None),
    "U16": (np.uint16, None),
    "U32": (np.uint32, None),
    "U64": (np.uint64, None),
    "F16": (np.float16, None),
    "F32": (np.float32, None),
    "F64": (np.float64, None),
    # NumPy has no portable bfloat16 dtype. Preserve the payload as uint16
    # and reinterpret it after constructing the MLX array.
    "BF16": (np.uint16, mx.bfloat16),
}


def _physical_expert_ids(policy: Qwen36ScopePolicy, layer: int) -> tuple[int, ...]:
    protected = policy.experts(layer, phase="decode")
    if policy.backend not in ("arena", "tiered"):
        return protected
    protected_set = set(protected)
    tail = tuple(
        expert for expert in range(NUM_EXPERTS) if expert not in protected_set
    )[: policy.arena_tail_slots]
    return protected + tail


def _load_qwen36_scope_safetensors(
    path: str | Path,
    policy: Qwen36ScopePolicy | None = None,
) -> dict[str, mx.array]:
    """Load non-expert tensors and only the physical Qwen expert bank.

    Stock ``mlx-vlm`` calls ``mx.load`` for every shard and discards unused
    experts later in ``Model.sanitize``. MLX arrays are lazy, so those sliced
    tensors can retain the complete 256-expert source allocation. Reading the
    selected expert byte ranges here prevents the unused experts from ever
    becoming MLX arrays.
    """

    policy = policy or load_qwen36_scope_policy()
    if policy is None:
        raise RuntimeError("Qwen3.6 scope safetensors loader requires a policy")

    selected: dict[str, mx.array] = {}
    with open(path, "rb") as handle:
        header_len = struct.unpack("<Q", handle.read(8))[0]
        header = json.loads(handle.read(header_len))
        data_start = 8 + header_len

        for key, info in header.items():
            if key == "__metadata__":
                continue
            dtype = info["dtype"]
            if dtype not in _STORAGE_DTYPES:
                raise ValueError(
                    f"Unsupported safetensors dtype {dtype!r} in Qwen3.6 "
                    f"scope loader for {path}"
                )
            storage_dtype, view_dtype = _STORAGE_DTYPES[dtype]
            start, end = (int(value) for value in info["data_offsets"])
            shape = tuple(int(dim) for dim in info["shape"])

            match = _STACKED_EXPERT_RE.search(key)
            expert_ids: tuple[int, ...] | None = None
            if match and shape and shape[0] == NUM_EXPERTS:
                layer = int(match.group(1))
                expert_ids = _physical_expert_ids(policy, layer)

            if expert_ids is None:
                handle.seek(data_start + start)
                raw = handle.read(end - start)
            else:
                expert_bytes = (end - start) // NUM_EXPERTS
                chunks = []
                for expert_id in expert_ids:
                    handle.seek(data_start + start + expert_id * expert_bytes)
                    chunks.append(handle.read(expert_bytes))
                raw = b"".join(chunks)
                shape = (len(expert_ids), *shape[1:])

            value = np.frombuffer(raw, dtype=storage_dtype).reshape(shape)
            mlx_value = mx.array(value)
            if view_dtype is not None:
                mlx_value = mlx_value.view(view_dtype)
            selected[key] = mlx_value

    return selected


def _is_qwen36_moe_model(model_path: str | Path) -> bool:
    try:
        config = json.loads((Path(model_path) / "config.json").read_text())
    except (OSError, ValueError, TypeError):
        return False
    return config.get("model_type") == "qwen3_5_moe"


def _initialize_scope_block(block, policy, layer: int) -> None:
    protected = policy.experts(layer, phase="decode")
    tail = _physical_expert_ids(policy, layer)[len(protected) :]
    expert_ids = protected + tail if policy.backend == "arena" else protected
    block.scope_layer = layer
    block.scope_expert_ids = expert_ids
    block.scope_protected_expert_ids = protected
    lookup = [-1] * NUM_EXPERTS
    for slot, expert_id in enumerate(expert_ids):
        lookup[expert_id] = slot
    block.scope_expert_to_slot_values = tuple(lookup)
    if policy.backend == "arena":
        from .arena_cache import get_qwen36_decode_arena

        get_qwen36_decode_arena(str(policy.store_path)).initialize_layer(
            layer, expert_ids, policy.resident_experts
        )
    elif policy.backend == "tiered":
        from .tiered_cache import get_qwen36_tiered_cache

        block.scope_tail_expert_ids = tail
        tail_lookup = [-1] * NUM_EXPERTS
        for slot, expert_id in enumerate(tail):
            tail_lookup[expert_id] = slot
        block.scope_tail_to_slot_values = tuple(tail_lookup)
        get_qwen36_tiered_cache(str(policy.store_path)).initialize_layer(
            layer, protected, tail
        )
    block.scope_prefill_model_key = None


def apply_qwen36_vlm_flesh_patch() -> bool:
    """Give mlx-vlm's independent Qwen MoE classes the compact runtime."""

    global _VLM_PATCHED
    if _VLM_PATCHED:
        return False
    policy = load_qwen36_scope_policy()
    if policy is None:
        return False

    from mlx_lm.models.switch_layers import SwitchGLU
    from mlx_vlm.models.qwen3_5_moe import language as vlm_language
    from mlx_vlm.models.qwen3_5_moe import qwen3_5_moe as vlm_outer

    from .model_patch import _exact_scope_moe, _lossy_replace_routes
    from .scope_cache import get_qwen36_fallback_loader

    block_cls = vlm_language.Qwen3_5MoeSparseMoeBlock
    original_init = block_cls.__init__

    def compact_init(self, args):
        original_init(self, args)
        active = load_qwen36_scope_policy()
        if active is None:
            return
        primary = (
            active.resident_experts
            if active.backend == "tiered"
            else active.physical_experts
        )
        self.switch_mlp = SwitchGLU(
            args.hidden_size, args.moe_intermediate_size, primary
        )
        if active.backend == "tiered":
            self.tail_switch_mlp = SwitchGLU(
                args.hidden_size,
                args.moe_intermediate_size,
                active.arena_tail_slots,
            )
        self.scope_policy = active
        self.scope_layer = -1
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

    original_call = block_cls.__call__

    def compact_call(self, x, target_verify=False):
        if getattr(self, "scope_policy", None) is None:
            return original_call(self, x, target_verify)
        gates = mx.softmax(self.gate(x), axis=-1, precise=True)
        inds = mx.argpartition(gates, kth=-self.top_k, axis=-1)[..., -self.top_k :]
        scores = mx.take_along_axis(gates, inds, axis=-1)
        scores = scores / scores.sum(axis=-1, keepdims=True)
        counters = None
        if self.scope_lossy_policy is not None:
            from .model_patch import _available_experts

            inds, counters = _lossy_replace_routes(
                inds,
                scores,
                gates,
                _available_experts(self),
                self.scope_lossy_policy,
            )
        routed = _exact_scope_moe(self, x, inds, scores, lossy_counters=counters)
        shared = self.shared_expert(x, target_verify)
        shared = mx.sigmoid(self.shared_expert_gate(x)) * shared
        return routed + shared

    block_cls.__init__ = compact_init
    block_cls.__call__ = compact_call
    block_cls._ai2apps_qwen36_flesh = True

    outer_cls = vlm_outer.Model
    original_sanitize = outer_cls.sanitize

    def compact_sanitize(self, weights):
        sanitized = original_sanitize(self, weights)
        active = load_qwen36_scope_policy()
        if active is None:
            return sanitized
        blocks = tuple(layer.mlp for layer in self.language_model.model.layers)
        for layer, block in enumerate(blocks):
            _initialize_scope_block(block, active, layer)
            protected_count = active.resident_experts
            physical_count = active.physical_experts
            prefix = f"language_model.model.layers.{layer}.mlp.switch_mlp"
            for projection in ("gate_proj", "up_proj", "down_proj"):
                for tensor_name in ("weight", "scales", "biases"):
                    key = f"{prefix}.{projection}.{tensor_name}"
                    value = sanitized.get(key)
                    if value is None:
                        continue
                    count = int(value.shape[0])
                    if count != physical_count:
                        raise ValueError(
                            f"Qwen3.6 VLM layer {layer} {projection}.{tensor_name} "
                            f"has {count} compact experts; expected {physical_count}"
                        )
                    if active.backend == "tiered":
                        tail_key = key.replace(".switch_mlp.", ".tail_switch_mlp.")
                        sanitized[tail_key] = value[protected_count:]
                        sanitized[key] = value[:protected_count]
        model_key = id(self)
        loader = get_qwen36_fallback_loader(str(active.store_path))
        loader.register_prefill_blocks(model_key, blocks)
        for block in blocks:
            block.scope_prefill_model_key = model_key
        return sanitized

    outer_cls.sanitize = compact_sanitize
    outer_cls._ai2apps_qwen36_flesh = True
    _VLM_PATCHED = True
    logger.info("mlx-vlm Qwen3.6 compact Cache-MoE runtime patch applied")
    return True


@contextlib.contextmanager
def qwen36_scope_safetensors_on_load(model_path: str | Path):
    """Temporarily install the subset reader for one serialized VLM load."""

    policy = load_qwen36_scope_policy()
    if policy is None or not _is_qwen36_moe_model(model_path):
        yield
        return

    apply_qwen36_vlm_flesh_patch()

    import mlx_vlm.utils as vlm_utils

    original = vlm_utils._load_safetensors

    def scoped_loader(path: str):
        return _load_qwen36_scope_safetensors(path, policy)

    vlm_utils._load_safetensors = scoped_loader
    logger.info(
        "Qwen3.6 scope safetensors reader enabled: Top%d + %d tail (%s)",
        policy.resident_experts,
        policy.arena_tail_slots if policy.backend in ("arena", "tiered") else 0,
        policy.backend,
    )
    try:
        yield
    finally:
        if vlm_utils._load_safetensors is scoped_loader:
            vlm_utils._load_safetensors = original
