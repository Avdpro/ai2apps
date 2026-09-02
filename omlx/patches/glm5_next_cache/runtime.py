"""mlx-vlm integration for the exact GLM-5 Next dynamic expert cache.

The language graph comes from mlx-vlm commit
``7c1cf01077f0a938fa36182943a931f3fc863206``.  This patch changes only the
routed MoE construction, expert checkpoint reader, and MoE call; attention,
Hyper-Connection, router selection, and the outer VLM remain upstream code.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import logging
import os
import re
import sys
from functools import cache
from pathlib import Path
from typing import Any

import mlx.core as mx
import mlx.nn as nn

from omlx.custom_kernels.glm_moe_dsa import fast as glm_fast
from omlx.patches.deepseek_v4.switch_layers import SwitchGLU, _gather_sort

from .boost import available_experts, glm5_lossy_policy, replace_missed_routes
from .dynamic_cache import Glm5DynamicCache

logger = logging.getLogger(__name__)

_EXPERT_RE = re.compile(
    r"(?:^|\.)layers\.(\d+)\.mlp\.experts\.(\d+)\."
    r"(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$"
)
_VENDOR_MODELS = Path(__file__).resolve().parent / "vendor" / "mlx_vlm" / "models"
_APPLIED = False


def _install_vendor_namespace() -> None:
    """Expose post-pin GLM5 modules while retaining pinned mlx-vlm support."""

    import mlx_vlm.models
    from mlx_vlm import prompt_utils

    package_path = getattr(mlx_vlm.models, "__path__", None)
    vendor_path = str(_VENDOR_MODELS)
    if package_path is not None and vendor_path not in package_path:
        # The GLM5 snapshot also needs the newer rope_utils API, so its small
        # coherent module set must precede the older pinned package. Modules
        # not present in the snapshot still resolve from installed mlx-vlm.
        package_path.insert(0, vendor_path)
    # ``mlx_vlm.models.rope_utils`` is commonly imported while the engine
    # module initializes, before the GLM patch gets a chance to prepend its
    # vendor directory.  Replacing only that already-cached compatibility
    # module keeps a true cold Engine start coherent with the vendored GLM5 /
    # DeepSeek snapshot (which requires initialize_rope).
    rope_name = "mlx_vlm.models.rope_utils"
    rope_module = sys.modules.get(rope_name)
    if rope_module is None or not hasattr(rope_module, "initialize_rope"):
        rope_path = _VENDOR_MODELS / "rope_utils.py"
        spec = importlib.util.spec_from_file_location(rope_name, rope_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load GLM5 rope compatibility: {rope_path}")
        rope_module = importlib.util.module_from_spec(spec)
        sys.modules[rope_name] = rope_module
        spec.loader.exec_module(rope_module)
    # mlx-vlm 0.6.3 predates GLM-5. Without this registration its generic
    # formatter strips image parts, so the processor never expands <|image|>
    # into visual tokens even though the checkpoint and model contain a full
    # Vision Tower. GLM-5's native Jinja template expects list content with
    # the image part before text, matching GLM-4V/Qwen-style formatting.
    prompt_utils.MODEL_CONFIG.setdefault(
        "glm5_next", prompt_utils.MessageFormat.LIST_WITH_IMAGE_FIRST
    )
    from .processor import install_glm5_next_processor_patch

    install_glm5_next_processor_patch()


class _LimitedSwiGLU(nn.Module):
    def __init__(self, limit: float):
        super().__init__()
        self.limit = float(limit)

    def __call__(self, up: mx.array, gate: mx.array) -> mx.array:
        if self.limit > 0:
            gate = mx.minimum(gate, self.limit)
            up = mx.clip(up, -self.limit, self.limit)
        return nn.silu(gate) * up


class _LimitedMLP(nn.Module):
    def __init__(self, config: Any, intermediate_size: int):
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_size, intermediate_size, bias=False)
        self.up_proj = nn.Linear(config.hidden_size, intermediate_size, bias=False)
        self.down_proj = nn.Linear(intermediate_size, config.hidden_size, bias=False)
        self.swiglu_limit = float(config.swiglu_limit)

    def __call__(self, x: mx.array) -> mx.array:
        gate = self.gate_proj(x)
        up = self.up_proj(x)
        if self.swiglu_limit > 0:
            gate = mx.minimum(gate, self.swiglu_limit)
            up = mx.clip(up, -self.swiglu_limit, self.swiglu_limit)
        return self.down_proj(nn.silu(gate) * up)


def _enabled_store() -> Path | None:
    value = os.environ.get("OMLX_GLM5_DYNAMIC_STORE", "").strip()
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _tail_slots() -> int:
    slots = int(os.environ.get("OMLX_GLM5_TAIL_SLOTS", "16"))
    if not 0 <= slots <= 32:
        raise ValueError("GLM5 Tail slots must be in [0, 32]")
    return slots


def _slots() -> int:
    total = int(os.environ.get("OMLX_GLM5_DYNAMIC_SLOTS", "96"))
    tail = _tail_slots()
    reserve = 0
    if os.environ.get("OMLX_GLM5_MTP_ENABLED", "0") == "1":
        # A speculative verifier keeps the pre-block KDA state alive until
        # acceptance is known (~2.4 GiB in bf16).  Reserve eight Main slots
        # by default so Top80+Hot16 remains below the 64 GiB product gate.
        reserve = int(os.environ.get("OMLX_GLM5_MTP_L1_RESERVE_SLOTS", "8"))
        if not 0 <= reserve <= 32:
            raise ValueError("GLM5 MTP L1 reserve must be in [0, 32]")
    # GLM-5.3 is a native VLM. Top80+Hot16 fits text decode but leaves only
    # ~3 GiB above the 60.8 GiB resident floor; a same-image follow-up needs
    # ~8 GiB of transient MoE/prefill workspace and an appended second image
    # needs ~10 GiB. Reserve 16 Main slots for the default multimodal profile,
    # yielding Top64+Hot16 and a measured 61.96 GiB three-turn peak. Dedicated
    # text deployments can explicitly set the reserve to zero.
    vision_reserve = int(
        os.environ.get("OMLX_GLM5_VISION_L1_RESERVE_SLOTS", "16")
    )
    if not 0 <= vision_reserve <= 32:
        raise ValueError("GLM5 vision L1 reserve must be in [0, 32]")
    slots = total - tail - reserve - vision_reserve
    if not 8 <= total <= 96 or slots < 8:
        raise ValueError(
            "GLM5 total slots must be in [8, 96] with L1 >= 8 after reserves"
        )
    return slots


def _io_workers() -> int:
    return int(os.environ.get("OMLX_GLM5_DYNAMIC_IO_WORKERS", "4"))


def _l1_promotions_per_layer() -> int:
    value = int(os.environ.get("OMLX_GLM5_L1_PROMOTIONS_PER_LAYER", "0"))
    if not 0 <= value <= 8:
        raise ValueError("GLM5 L1 promotions per layer must be in [0, 8]")
    return value


def _boost_mode() -> str:
    return os.environ.get("OMLX_GLM5_BOOST_MODE", "natural")


def _weighted_switch(
    switch: Any,
    x: mx.array,
    inds: mx.array,
    scores: mx.array,
) -> mx.array:
    """Optionally consume sorted Top-8 routes in the native reducer."""

    enabled = os.environ.get("OMLX_GLM5_WEIGHTED_SUM", "0") == "1"
    if not enabled or inds.size != scores.size or scores.shape[-1] != 8:
        routes = switch(x, inds)
        return (routes * scores[..., None].astype(routes.dtype)).sum(axis=-2)
    if not glm_fast.has_symbol("glm_moe_weighted_sum"):
        raise RuntimeError("GLM5 weighted-sum experiment requires its Metal kernel")
    x_sorted, idx, inv_order = _gather_sort(mx.expand_dims(x, (-2, -3)), inds)
    gate_up = switch.gate_up_proj(x_sorted, idx, sorted_indices=True)
    hidden = gate_up.shape[-1] // 2
    x_gate = gate_up[..., :hidden]
    x_up = gate_up[..., hidden:]
    routed = switch.down_proj(switch.activation(x_up, x_gate), idx, sorted_indices=True)
    return glm_fast.glm_moe_weighted_sum(
        mx.contiguous(routed),
        mx.contiguous(inv_order.astype(mx.uint32)),
        mx.contiguous(scores.astype(mx.float32)),
    )


@cache
def get_glm5_dynamic_cache(directory: str) -> Glm5DynamicCache:
    return Glm5DynamicCache(
        directory,
        capacity=_slots(),
        tail_slots=_tail_slots(),
        l1_promotions_per_layer=_l1_promotions_per_layer(),
        num_experts=288,
        io_workers=_io_workers(),
    )


def _is_glm5_next(path: str | os.PathLike[str]) -> bool:
    try:
        config = json.loads((Path(path) / "config.json").read_text())
    except (OSError, TypeError, ValueError):
        return False
    return config.get("model_type") == "glm5_next"


def _compact_safetensors(
    path: str,
    original: Any,
    *,
    slots: int,
) -> dict[str, mx.array]:
    """Retain non-experts and alias one cold placeholder into every L1 slot."""

    loaded = original(path)
    compact: dict[str, mx.array] = {}
    for key, value in loaded.items():
        match = _EXPERT_RE.search(key)
        if match is None:
            compact[key] = value
            continue
        layer = int(match.group(1))
        expert = int(match.group(2))
        # Layer 45 belongs to the optional MTP head and upstream GLM5 sanitize
        # discards it for the baseline.  All other routed tensors are sourced
        # from the expert-major store after routing.
        mtp_enabled = os.environ.get("OMLX_GLM5_MTP_ENABLED", "0") == "1"
        if layer > 45 or (layer == 45 and not mtp_enabled) or expert != 0:
            continue
        marker = ".experts.0."
        for physical in range(slots):
            compact[key.replace(marker, f".experts.{physical}.")] = value
    return compact


def apply_glm5_dynamic_patch() -> bool:
    """Install the compact MoE class before mlx-vlm constructs GLM5."""

    global _APPLIED
    if _APPLIED:
        return False
    directory = _enabled_store()
    if directory is None:
        return False
    if not (directory / "layer-003.moe").is_file():
        raise FileNotFoundError(
            f"GLM5 expert store is incomplete or missing: {directory}"
        )

    _install_vendor_namespace()
    from mlx_vlm.models.deepseek_v32.language import MoEGate, group_expert_select
    from mlx_vlm.models.glm5_next import language as glm_language

    slots = _slots()

    class Glm5DynamicMoE(nn.Module):
        def __init__(self, config):
            super().__init__()
            self.config = config
            self.num_experts_per_tok = config.num_experts_per_tok
            self.gate = MoEGate(config)
            self.switch_mlp = SwitchGLU(
                config.hidden_size,
                config.moe_intermediate_size,
                slots,
                activation=_LimitedSwiGLU(config.swiglu_limit),
                global_num_experts=slots,
                fused_gate_up=True,
            )
            intermediate = config.moe_intermediate_size * config.n_shared_experts
            self.shared_experts = _LimitedMLP(config, intermediate)
            self.sharding_group = None
            self.dynamic_layer = -1
            self.dynamic_cache: Glm5DynamicCache | None = None
            self.dynamic_lookup_values = tuple([-1] * config.n_routed_experts)
            self.dynamic_tail_lookup_values = tuple([-1] * config.n_routed_experts)
            self._dynamic_slot_counts = None
            self.boost_policy = glm5_lossy_policy(_boost_mode())
            self.boost_stats = {
                "routes_replaced": 0,
                "misses_before": 0,
                "misses_after": 0,
                "prefill_routes_replaced": 0,
                "prefill_misses_before": 0,
                "prefill_misses_after": 0,
                "decode_routes_replaced": 0,
                "decode_misses_before": 0,
                "decode_misses_after": 0,
            }

        def __call__(self, x):
            if self.sharding_group is not None:
                raise RuntimeError("GLM5 dynamic baseline does not support sharding")
            if self.dynamic_layer < 0 or self.dynamic_cache is None:
                raise RuntimeError("GLM5 dynamic MoE layer was not initialized")

            single_decode = x.shape[0] == 1 and x.shape[1] == 1
            mtp_microdecode = (
                os.environ.get("OMLX_GLM5_MTP_ENABLED", "0") == "1"
                and x.shape[0] == 1
                and 1 < x.shape[1]
                <= int(os.environ.get("OMLX_GLM5_MTP_VERIFY_MAX_TOKENS", "4"))
                and self.dynamic_cache.tail_slots > 0
            )
            decode_like = single_decode or mtp_microdecode
            if decode_like:
                self.dynamic_cache.release_prefill_workspaces()
            shared = self.shared_experts(x)
            policy = self.boost_policy
            router_choice_scores = None
            if policy is None:
                inds, scores = self.gate(x)
            else:
                gates = x @ self.gate.weight.T
                inds, scores = group_expert_select(
                    gates,
                    self.gate.e_score_correction_bias,
                    self.gate.top_k,
                    self.gate.n_group,
                    self.gate.topk_group,
                    self.gate.routed_scaling_factor,
                    self.gate.norm_topk_prob,
                )
                router_choice_scores = (
                    mx.sigmoid(gates.astype(mx.float32))
                    + self.gate.e_score_correction_bias
                )
            cache_instance = self.dynamic_cache
            cache_instance.observe_routes(
                self.dynamic_layer,
                inds,
                scores,
                "decode" if decode_like else "prefill",
            )
            phase = "decode" if decode_like else "prefill"
            lookup = mx.array(self.dynamic_lookup_values, dtype=mx.int32)
            tail_lookup = mx.array(
                self.dynamic_tail_lookup_values, dtype=mx.int32
            )
            if policy is not None and router_choice_scores is not None:
                inds, counters = replace_missed_routes(
                    inds,
                    scores,
                    router_choice_scores,
                    available_experts(lookup, tail_lookup),
                    policy,
                )
                mx.eval(*counters)
                replaced, before, after = (int(value.item()) for value in counters)
                self.boost_stats["routes_replaced"] += replaced
                self.boost_stats["misses_before"] += before
                self.boost_stats["misses_after"] += after
                self.boost_stats[f"{phase}_routes_replaced"] += replaced
                self.boost_stats[f"{phase}_misses_before"] += before
                self.boost_stats[f"{phase}_misses_after"] += after
            if mtp_microdecode:
                host_ids = tuple(
                    dict.fromkeys(int(value) for value in inds.reshape(-1).tolist())
                )
                main_lookup_host = self.dynamic_cache.lookup(self.dynamic_layer)
                tail_union = tuple(
                    expert for expert in host_ids if main_lookup_host[expert] < 0
                )
                if len(tail_union) > self.dynamic_cache.tail_slots:
                    # A verifier block can touch >Hot16 experts even though
                    # every individual token is Top8. Keep the target
                    # attention/linear layers batched, but execute its MoE
                    # positions through the normal per-token Tail pipeline.
                    routed_parts = []
                    for position in range(int(x.shape[1])):
                        token_inds = inds[:, position : position + 1]
                        token_scores = scores[:, position : position + 1]
                        token_x = x[:, position : position + 1]
                        token_lookup = mx.array(
                            self.dynamic_lookup_values, dtype=mx.int32
                        )
                        token_mapped = token_lookup[token_inds]
                        requested = tuple(
                            dict.fromkeys(
                                int(value)
                                for value in token_inds.reshape(-1).tolist()
                            )
                        )
                        routed, main_values, tail_values = (
                            cache_instance.decode_tiered(
                                self.dynamic_layer,
                                requested,
                                self.switch_mlp,
                                token_x,
                                token_inds,
                                token_scores,
                                token_mapped,
                                shared[:, position : position + 1],
                            )
                        )
                        self.dynamic_lookup_values = main_values
                        self.dynamic_tail_lookup_values = tail_values
                        routed_parts.append(routed)
                    return mx.concatenate(routed_parts, axis=1) + shared
            if not decode_like:
                routed = cache_instance.prefill(
                    self.dynamic_layer,
                    self.switch_mlp,
                    x,
                    inds,
                    scores,
                )
                self.dynamic_lookup_values = cache_instance.lookup(self.dynamic_layer)
                self.dynamic_tail_lookup_values = cache_instance.tail_lookup(
                    self.dynamic_layer
                )
                self._dynamic_slot_counts = None
            else:
                mapped = lookup[inds]
                if os.environ.get("OMLX_GLM5_NOSYNC_PROBE", "0") == "1":
                    cache_instance.record_all_hit()
                    safe = mx.maximum(mapped, mx.array(0, dtype=mx.int32))
                    routed = _weighted_switch(self.switch_mlp, x, safe, scores)
                    return routed + shared
                slot_axis = mx.arange(slots, dtype=mx.int32)
                counts = mx.sum(
                    mapped.reshape(-1)[:, None] == slot_axis[None, :], axis=0
                ).astype(mx.int32)
                self._dynamic_slot_counts = (
                    counts
                    if self._dynamic_slot_counts is None
                    else self._dynamic_slot_counts + counts
                )
                mx.async_eval(self._dynamic_slot_counts)
                tail_mapped = tail_lookup[inds]
                main_miss_count = mx.sum((mapped < 0).astype(mx.int32))
                missing_count = mx.sum(
                    ((mapped < 0) & (tail_mapped < 0)).astype(mx.int32)
                )
                mx.eval(main_miss_count, missing_count)
                if int(main_miss_count.item()) and cache_instance.tail_slots:
                    mx.eval(inds, self._dynamic_slot_counts)
                    cache_instance.observe_slot_counts(
                        self.dynamic_layer,
                        tuple(
                            int(value) for value in self._dynamic_slot_counts.tolist()
                        ),
                    )
                    self._dynamic_slot_counts = None
                    requested = tuple(
                        dict.fromkeys(int(value) for value in inds.reshape(-1).tolist())
                    )
                    (
                        routed,
                        self.dynamic_lookup_values,
                        self.dynamic_tail_lookup_values,
                    ) = cache_instance.decode_tiered(
                        self.dynamic_layer,
                        requested,
                        self.switch_mlp,
                        x,
                        inds,
                        scores,
                        mapped,
                        shared,
                    )
                elif int(missing_count.item()):
                    mx.eval(inds, self._dynamic_slot_counts)
                    cache_instance.observe_slot_counts(
                        self.dynamic_layer,
                        tuple(
                            int(value) for value in self._dynamic_slot_counts.tolist()
                        ),
                    )
                    self._dynamic_slot_counts = None
                    requested = tuple(
                        dict.fromkeys(int(value) for value in inds.reshape(-1).tolist())
                    )
                    hit_count = int(mx.sum((mapped >= 0).astype(mx.int32)).item())
                    if hit_count and cache_instance.direct_enabled():
                        routed, self.dynamic_lookup_values = (
                            cache_instance.resolve_split(
                                self.dynamic_layer,
                                requested,
                                self.switch_mlp,
                                x,
                                inds,
                                scores,
                                mapped,
                                shared,
                            )
                        )
                    else:
                        self.dynamic_lookup_values = cache_instance.resolve(
                            self.dynamic_layer,
                            requested,
                            self.switch_mlp,
                        )
                        lookup = mx.array(self.dynamic_lookup_values, dtype=mx.int32)
                        mapped = lookup[inds]
                        routed = _weighted_switch(self.switch_mlp, x, mapped, scores)
                else:
                    cache_instance.record_all_hit()
                    routed = _weighted_switch(self.switch_mlp, x, mapped, scores)
            return routed + shared

    Glm5DynamicMoE.__name__ = "Glm5DynamicMoE"
    Glm5DynamicMoE.__qualname__ = "Glm5DynamicMoE"
    glm_language.DeepseekV32MoE = Glm5DynamicMoE

    if os.environ.get("OMLX_GLM5_MTP_ENABLED", "0") == "1":
        from types import SimpleNamespace

        from mlx_vlm.models.cache import CacheList, KVCache
        from mlx_vlm.speculative.drafters.qwen3_5_mtp.qwen3_5_mtp import (
            Qwen3_5MTPDraftModel,
        )

        class Glm5MTPDecoder(nn.Module):
            """Checkpoint layer 45: a sparse decoder without main-stack mHC."""

            def __init__(self, config):
                super().__init__()
                self.self_attn = glm_language.Glm5NextSparseAttention(config)
                self.mlp = Glm5DynamicMoE(config)
                self.input_layernorm = nn.RMSNorm(
                    config.hidden_size, eps=config.rms_norm_eps
                )
                self.post_attention_layernorm = nn.RMSNorm(
                    config.hidden_size, eps=config.rms_norm_eps
                )

            def __call__(self, x, mask=None, cache=None):
                x = x + self.self_attn(self.input_layernorm(x), mask, cache)
                return x + self.mlp(self.post_attention_layernorm(x))

        class Glm5MTPDraftModel(Qwen3_5MTPDraftModel):
            """Native GLM-5.3 NextN head using the shared target embedding/head."""

            def __init__(self, config):
                nn.Module.__init__(self)
                hidden = config.hidden_size
                self.config = SimpleNamespace(
                    model_type="glm5_next_mtp", block_size=3
                )
                self.enorm = nn.RMSNorm(hidden, eps=config.rms_norm_eps)
                self.hnorm = nn.RMSNorm(hidden, eps=config.rms_norm_eps)
                self.eh_proj = nn.Linear(2 * hidden, hidden, bias=False)
                self.decoder = Glm5MTPDecoder(config)
                self.norm = nn.RMSNorm(hidden, eps=config.rms_norm_eps)
                self._input_embed = None
                self._input_embed_scale = 1.0
                self._lm_head_fn = None
                self._cache = []
                self._seed_token = None
                self._seed_hidden = None
                self._next_position = 0
                self._round_appended = 0
                self._kv_valid_len = 0
                self._position = 0
                self._draft_round = 0
                self.accept_lens = []
                self.draft_lens = []

            def make_cache(self, left_padding=None):
                del left_padding
                return [CacheList(KVCache(), KVCache())]

            def _forward_hidden(self, token_embed, hidden, cache, position_ids):
                del position_ids
                h = self.eh_proj(
                    mx.concatenate((self.enorm(token_embed), self.hnorm(hidden)), -1)
                )
                layer_cache = cache[0] if cache else None
                mask_cache = layer_cache[0] if layer_cache is not None else None
                mask = glm_language.create_attention_mask(
                    h, mask_cache, return_array=True
                )
                return self.norm(self.decoder(h, mask=mask, cache=layer_cache))

            def prefill_from_target_hidden(self, *args, **kwargs):
                dynamic = self.decoder.mlp.dynamic_cache
                if dynamic is None:
                    raise RuntimeError("GLM5 MTP dynamic cache is not attached")
                original_slots = dynamic.prefill_bank_slots
                dynamic.release_prefill_workspaces()
                # The MTP head is only one layer; trade extra groups for a
                # small transient bank so the integrated path stays <64 GiB.
                dynamic.prefill_bank_slots = min(16, original_slots)
                try:
                    result = super().prefill_from_target_hidden(*args, **kwargs)
                    state = [
                        value for value in self.draft_eval_state() if value is not None
                    ]
                    mx.eval(*state)
                    return result
                finally:
                    dynamic.release_prefill_workspaces()
                    dynamic.prefill_bank_slots = original_slots

        language_cls = glm_language.LanguageModel
        original_init = language_cls.__init__

        def mtp_init(self, args, config=None):
            original_init(self, args, config)
            self.mtp = Glm5MTPDraftModel(args)

        mtp_init._omlx_glm5_mtp = True
        language_cls.__init__ = mtp_init

    language_cls = glm_language.LanguageModel
    original_sanitize = language_cls.sanitize

    def compact_sanitize(self, weights):
        mtp_prefix = f"model.layers.{self.args.num_hidden_layers}."
        mtp_weights = {
            key.replace(mtp_prefix, "model.layers.3."): value
            for key, value in weights.items()
            if key.startswith(mtp_prefix)
        }
        already_mapped_mtp = any(
            key.startswith("mtp.") or ".mtp." in key for key in weights
        )
        if already_mapped_mtp and not mtp_weights:
            return weights
        if hasattr(self, "mtp") and not mtp_weights and not already_mapped_mtp:
            layer45_keys = tuple(key for key in weights if ".layers.45." in key)
            raise RuntimeError(
                "GLM5 MTP layer 45 was not found at the expected model path; "
                f"observed={layer45_keys[:3]}"
            )
        main_weights = {
            key: value for key, value in weights.items() if not key.startswith(mtp_prefix)
        }
        original_count = self.args.n_routed_experts
        self.args.n_routed_experts = slots
        try:
            sanitized = original_sanitize(self, main_weights)
            if hasattr(self, "mtp") and mtp_weights:
                mtp_sanitized = original_sanitize(self, mtp_weights)
                for key, value in mtp_sanitized.items():
                    mapped = key.replace("model.layers.3.", "mtp.decoder.")
                    mapped = mapped.replace(
                        "mtp.decoder.eh_proj.", "mtp.eh_proj."
                    ).replace("mtp.decoder.enorm.", "mtp.enorm.")
                    mapped = mapped.replace("mtp.decoder.hnorm.", "mtp.hnorm.")
                    mapped = mapped.replace(
                        "mtp.decoder.shared_head.norm.", "mtp.norm."
                    )
                    sanitized[mapped] = value
        finally:
            self.args.n_routed_experts = original_count

        # Upstream GLM5 remaps only f_a/f_b ``.weight`` into forget_gate.
        # MLX affine checkpoints also carry ``.scales`` and ``.biases``;
        # preserve the identical module-path rewrite for that metadata.
        fixed: dict[str, mx.array] = {}
        for key, value in sanitized.items():
            mapped = key
            for projection in ("f_a_proj", "f_b_proj"):
                marker = f".self_attn.{projection}."
                if marker in mapped:
                    mapped = mapped.replace(
                        marker,
                        f".self_attn.forget_gate.{projection}.",
                    )
                    break
            fixed[mapped] = value
        sanitized = fixed

        # The on-disk L2 records and the mutable L1 use the same fused
        # gate/up row layout.  Only the single cold placeholder is fused here;
        # every runtime miss is already compute-ready on SSD.
        fused: dict[str, mx.array] = {}
        consumed: set[str] = set()
        marker = ".switch_mlp.gate_proj."
        for key, gate in sanitized.items():
            if marker not in key:
                continue
            up_key = key.replace(marker, ".switch_mlp.up_proj.")
            up = sanitized.get(up_key)
            if up is None:
                raise ValueError(f"GLM5 fused cache is missing {up_key}")
            fused_key = key.replace(marker, ".switch_mlp.gate_up_proj.")
            fused[fused_key] = mx.concatenate((gate, up), axis=1)
            consumed.update((key, up_key))
        sanitized = {
            key: value for key, value in sanitized.items() if key not in consumed
        }
        sanitized.update(fused)

        dynamic = get_glm5_dynamic_cache(str(directory))
        for layer, decoder in enumerate(self.model.layers):
            block = decoder.mlp
            if not isinstance(block, Glm5DynamicMoE):
                continue
            block.dynamic_layer = layer
            block.dynamic_cache = dynamic
            block.dynamic_lookup_values = dynamic.lookup(layer)
            block.dynamic_tail_lookup_values = dynamic.tail_lookup(layer)
            decoder.compile_ffn = False
        mtp = getattr(self, "mtp", None)
        if mtp is not None:
            mtp.decoder.mlp.dynamic_layer = self.args.num_hidden_layers
            mtp.decoder.mlp.dynamic_cache = dynamic
            mtp.decoder.mlp.dynamic_lookup_values = dynamic.lookup(
                self.args.num_hidden_layers
            )
            mtp.decoder.mlp.dynamic_tail_lookup_values = dynamic.tail_lookup(
                self.args.num_hidden_layers
            )
        return sanitized

    compact_sanitize._omlx_glm5_dynamic = True
    compact_sanitize._omlx_original = original_sanitize
    language_cls.sanitize = compact_sanitize
    language_cls._omlx_glm5_dynamic = True
    _APPLIED = True
    logger.info(
        "GLM5 exact dynamic cache patch applied: slots=%d store=%s",
        slots,
        directory,
    )
    return True


@contextlib.contextmanager
def glm5_dynamic_safetensors_on_load(model_path: str | os.PathLike[str]):
    """Install the cold-placeholder reader for one serialized VLM load."""

    if _enabled_store() is None or not _is_glm5_next(model_path):
        yield
        return
    apply_glm5_dynamic_patch()

    import mlx_vlm.utils as vlm_utils

    original = vlm_utils._load_safetensors

    def compact_loader(path: str):
        return _compact_safetensors(path, original, slots=_slots())

    vlm_utils._load_safetensors = compact_loader
    try:
        yield
    finally:
        if vlm_utils._load_safetensors is compact_loader:
            vlm_utils._load_safetensors = original


__all__ = [
    "apply_glm5_dynamic_patch",
    "get_glm5_dynamic_cache",
    "glm5_dynamic_safetensors_on_load",
]
