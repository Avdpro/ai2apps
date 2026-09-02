from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from ai2apps.model_worker.cache_moe import _authorized_path, _prepared_manifest
from ai2apps.model_worker.omlx_chat import OmlxChatAdapter
from ai2apps.model_worker.protocol import ModelWorkerCheckpoint, ModelWorkerError


_FULL_RESIDENT_MIN_BYTES = 32 * 1024**3


def _physical_memory_bytes() -> int:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, TypeError, ValueError):
        return 0


def _execution_mode(options: Mapping[str, Any]) -> str:
    mode = str(options.get("moe_execution_mode", "cached")).lower()
    tier = str(options.get("cache_moe_memory_tier", "auto") or "auto").lower()
    # The current Host emits its historical cached/auto defaults even when a
    # Package declares a full-resident default. Resolve that untouched pair
    # here using the product's measured 32-GiB fit threshold. Selecting a
    # concrete Cached-MoE tier remains an explicit request on larger machines.
    if (
        mode == "cached"
        and tier == "auto"
        and _physical_memory_bytes() >= _FULL_RESIDENT_MIN_BYTES
    ):
        return "full"
    return mode


class Ornith15VisionChatAdapter(OmlxChatAdapter):
    """Select full or exact Top-N Cached-MoE execution for Ornith VLM."""

    async def create_engine(
        self,
        checkpoint: ModelWorkerCheckpoint,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> Any:
        if checkpoint.path is None:
            return await super().create_engine(checkpoint, runtime_options)

        options = dict(runtime_options or {})
        mode = _execution_mode(options)
        if mode not in {"cached", "full"}:
            raise ModelWorkerError(
                f"Unsupported MoE execution mode: {mode}",
                code="invalid_request_error",
                status_code=400,
            )

        from omlx.engine.vlm import VLMBatchedEngine
        from omlx.patches.qwen3_6_flesh.scope_policy import (
            configure_qwen36_scope_policy,
            disable_qwen36_scope_policy,
        )

        if mode == "full":
            disable_qwen36_scope_policy()
            return VLMBatchedEngine(str(checkpoint.path), trust_remote_code=False)

        prepared = _prepared_manifest(checkpoint)
        if prepared is None:
            raise ModelWorkerError(
                "Checkpoint must be prepared before Ornith Cached-MoE execution",
                code="model_not_prepared",
                status_code=503,
            )
        scope = prepared.get("scope", {})
        profile = _authorized_path(checkpoint, scope.get("profile"), "scope profile")
        expert_store = _authorized_path(
            checkpoint, prepared.get("expert_store"), "expert store"
        )
        default_scope = str(scope.get("default") or "")
        if not profile.is_file() or not expert_store.is_dir() or not default_scope:
            raise ModelWorkerError(
                "Prepared Ornith Cached-MoE assets are incomplete",
                code="invalid_prepared_checkpoint",
                status_code=503,
            )

        from omlx.model_discovery import resolve_qwen36_cache_moe_experts

        tier = str(options.get("cache_moe_memory_tier", "compact") or "compact")
        if tier == "auto":
            tier = "compact"
        resident_experts = resolve_qwen36_cache_moe_experts(
            checkpoint.path, tier, prepared
        )
        tail_slots = int(prepared.get("arena_tail_slots", 32))
        configure_qwen36_scope_policy(
            profile,
            default_scope,
            expert_store,
            resident_experts,
            backend="tiered",
            arena_tail_slots=tail_slots,
        )
        os.environ["OMLX_QWEN36_HOT_SLOTS"] = str(tail_slots)
        os.environ["OMLX_QWEN36_PREFILL_BACKEND"] = "workspace256-direct"
        os.environ["OMLX_QWEN36_TIERED_TOKEN_TXN"] = "0"
        os.environ.setdefault("OMLX_MOE_DIRECT_L1", "1")
        os.environ.setdefault("OMLX_QWEN36_ADAPTIVE_L1", "0")
        return VLMBatchedEngine(str(checkpoint.path), trust_remote_code=False)


def create_adapter(context):
    return Ornith15VisionChatAdapter(context)
