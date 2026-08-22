# SPDX-License-Identifier: Apache-2.0
"""Trusted Worker-side engine selection for prepared Cache-MoE checkpoints."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .omlx_chat import OmlxChatAdapter
from .protocol import ModelWorkerCheckpoint, ModelWorkerError


def _prepared_manifest(checkpoint: ModelWorkerCheckpoint) -> dict[str, Any] | None:
    if checkpoint.path is None:
        return None
    path = checkpoint.path / "ai2apps-model.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelWorkerError(
            "Prepared model manifest is unreadable",
            code="invalid_prepared_checkpoint",
            status_code=503,
        ) from exc
    source = value.get("source", {})
    if (
        value.get("format") != "ai2apps-cache-moe-model"
        or source.get("repo_id") != checkpoint.repo_id
        or source.get("revision") != checkpoint.revision
    ):
        raise ModelWorkerError(
            "Prepared model manifest does not match the pinned checkpoint",
            code="invalid_prepared_checkpoint",
            status_code=503,
        )
    return value


def _authorized_path(checkpoint: ModelWorkerCheckpoint, raw: Any, label: str) -> Path:
    if checkpoint.path is None or not isinstance(raw, str):
        raise ModelWorkerError(
            f"Prepared model {label} is missing",
            code="invalid_prepared_checkpoint",
            status_code=503,
        )
    candidate = Path(raw).expanduser().resolve()
    # snapshot = <repo>/snapshots/<commit>; the repository root is the narrow
    # sandbox grant and contains both snapshots and their blob targets.
    repository_root = checkpoint.path.parents[1]
    try:
        candidate.relative_to(repository_root)
    except ValueError as exc:
        raise ModelWorkerError(
            f"Prepared model {label} escapes the authorized repository",
            code="invalid_prepared_checkpoint",
            status_code=503,
        ) from exc
    return candidate


class DeepseekV4ChatAdapter(OmlxChatAdapter):
    """Select full or exact Cached-MoE DeepSeek execution inside the Worker."""

    async def create_engine(
        self,
        checkpoint: ModelWorkerCheckpoint,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> Any:
        if checkpoint.path is None:
            return await super().create_engine(checkpoint, runtime_options)
        options = dict(runtime_options or {})
        mode = str(options.get("moe_execution_mode", "cached")).lower()
        if mode not in {"cached", "full"}:
            raise ModelWorkerError(
                f"Unsupported MoE execution mode: {mode}",
                code="invalid_request_error",
                status_code=400,
            )
        prepared = _prepared_manifest(checkpoint)
        from omlx.engine.batched import BatchedEngine
        from omlx.patches.deepseek_v4.scope_policy import (
            configure_scope_policy,
            disable_scope_policy,
        )

        if prepared is None:
            if mode == "cached":
                raise ModelWorkerError(
                    "Checkpoint must be prepared before Cached-MoE execution",
                    code="model_not_prepared",
                    status_code=503,
                )
            disable_scope_policy()
            return BatchedEngine(str(checkpoint.path), trust_remote_code=False)

        scope = prepared.get("scope", {})
        profile = _authorized_path(checkpoint, scope.get("profile"), "scope profile")
        expert_store = _authorized_path(
            checkpoint, prepared.get("expert_store"), "expert store"
        )
        default_scope = str(scope.get("default") or "")
        if not profile.is_file() or not expert_store.is_dir() or not default_scope:
            raise ModelWorkerError(
                "Prepared Cached-MoE assets are incomplete",
                code="invalid_prepared_checkpoint",
                status_code=503,
            )

        if mode == "full":
            layout = prepared.get("checkpoint_layout", {})
            if layout.get("format") == "ai2apps-backbone-expert-store":
                configure_scope_policy(profile, default_scope, expert_store, 256)
            else:
                disable_scope_policy()
            return BatchedEngine(str(checkpoint.path), trust_remote_code=False)

        from omlx.engine.flesh import DeepseekV4FleshEngine
        from omlx.model_discovery import resolve_deepseek_cache_moe_experts

        tier = str(options.get("cache_moe_memory_tier", "auto") or "auto")
        resident_experts = resolve_deepseek_cache_moe_experts(
            checkpoint.path, tier, prepared
        )
        configure_scope_policy(
            profile, default_scope, expert_store, resident_experts
        )
        return DeepseekV4FleshEngine(str(checkpoint.path), trust_remote_code=False)


class Qwen36ChatAdapter(OmlxChatAdapter):
    """Select full or Tiered Cached-MoE Qwen3.6 execution."""

    async def create_engine(
        self,
        checkpoint: ModelWorkerCheckpoint,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> Any:
        if checkpoint.path is None:
            return await super().create_engine(checkpoint, runtime_options)
        options = dict(runtime_options or {})
        mode = str(options.get("moe_execution_mode", "cached")).lower()
        if mode not in {"cached", "full"}:
            raise ModelWorkerError(
                f"Unsupported MoE execution mode: {mode}",
                code="invalid_request_error",
                status_code=400,
            )
        prepared = _prepared_manifest(checkpoint)
        from omlx.engine.batched import BatchedEngine
        from omlx.patches.qwen3_6_flesh.scope_policy import (
            configure_qwen36_scope_policy,
            disable_qwen36_scope_policy,
        )

        if prepared is None:
            if mode == "cached":
                raise ModelWorkerError(
                    "Checkpoint must be prepared before Cached-MoE execution",
                    code="model_not_prepared",
                    status_code=503,
                )
            disable_qwen36_scope_policy()
            return BatchedEngine(str(checkpoint.path), trust_remote_code=False)

        scope = prepared.get("scope", {})
        profile = _authorized_path(checkpoint, scope.get("profile"), "scope profile")
        expert_store = _authorized_path(
            checkpoint, prepared.get("expert_store"), "expert store"
        )
        default_scope = str(scope.get("default") or "")
        if not profile.is_file() or not expert_store.is_dir() or not default_scope:
            raise ModelWorkerError(
                "Prepared Cached-MoE assets are incomplete",
                code="invalid_prepared_checkpoint",
                status_code=503,
            )

        if mode == "full":
            configure_qwen36_scope_policy(
                profile,
                default_scope,
                expert_store,
                256,
                backend="flesh",
                arena_tail_slots=0,
            )
            return BatchedEngine(str(checkpoint.path), trust_remote_code=False)

        from omlx.engine.qwen36_tiered import Qwen36TieredEngine
        from omlx.model_discovery import resolve_qwen36_cache_moe_experts

        tier = str(options.get("cache_moe_memory_tier", "auto") or "auto")
        resident_experts = resolve_qwen36_cache_moe_experts(
            checkpoint.path, tier, prepared
        )
        tail_slots = int(prepared.get("arena_tail_slots", 24))
        configure_qwen36_scope_policy(
            profile,
            default_scope,
            expert_store,
            resident_experts,
            backend="tiered",
            arena_tail_slots=tail_slots,
        )
        return Qwen36TieredEngine(str(checkpoint.path), trust_remote_code=False)
