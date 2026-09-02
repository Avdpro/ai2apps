import os
from collections.abc import Mapping
from typing import Any

from ai2apps.model_worker.cache_moe import _authorized_path, _prepared_manifest
from ai2apps.model_worker.omlx_chat import OmlxChatAdapter
from ai2apps.model_worker.protocol import ModelWorkerCheckpoint, ModelWorkerError


class Glm5DynamicChatAdapter(OmlxChatAdapter):
    """Select full or exact dynamic Cached-MoE GLM-5.3 VLM execution."""

    _TIER_SLOTS = {"lean": 80, "balanced": 96}

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

        from omlx.engine.vlm import VLMBatchedEngine

        if mode == "full":
            os.environ.pop("OMLX_GLM5_DYNAMIC_STORE", None)
            return VLMBatchedEngine(str(checkpoint.path), trust_remote_code=False)

        prepared = _prepared_manifest(checkpoint)
        if prepared is None:
            raise ModelWorkerError(
                "Checkpoint must be prepared before GLM-5 Cached-MoE execution",
                code="model_not_prepared",
                status_code=503,
            )
        expert_store = _authorized_path(
            checkpoint, prepared.get("expert_store"), "expert store"
        )
        if not (expert_store / "layer-003.moe").is_file():
            raise ModelWorkerError(
                "Prepared GLM-5 fused-v2 expert store is incomplete",
                code="invalid_prepared_checkpoint",
                status_code=503,
            )

        tier = str(options.get("cache_moe_memory_tier", "balanced") or "balanced")
        if tier == "auto":
            tier = "balanced"
        slots = self._TIER_SLOTS.get(tier)
        if slots is None:
            raise ModelWorkerError(
                f"Unsupported GLM-5 memory tier: {tier}",
                code="invalid_request_error",
                status_code=400,
            )

        os.environ["OMLX_GLM5_DYNAMIC_STORE"] = str(expert_store)
        os.environ["OMLX_GLM5_DYNAMIC_SLOTS"] = str(slots)
        os.environ["OMLX_GLM5_TAIL_SLOTS"] = str(
            int(prepared.get("hot_slots", 16))
        )
        os.environ["OMLX_GLM5_VISION_L1_RESERVE_SLOTS"] = str(
            int(prepared.get("vision_l1_reserve_slots", 16))
        )
        os.environ["OMLX_GLM5_DYNAMIC_IO_WORKERS"] = "4"
        os.environ["OMLX_GLM5_L1_PROMOTIONS_PER_LAYER"] = "1"
        os.environ["OMLX_GLM5_BOOST_MODE"] = "natural"
        os.environ["OMLX_GLM5_PREFILL_RESIDENT_FIRST"] = "1"
        os.environ["OMLX_GLM5_PREFILL_RETAIN_L1"] = "1"
        os.environ.setdefault("OMLX_GLM5_MTP_ENABLED", "0")
        os.environ.setdefault("OMLX_MOE_DIRECT_L1", "1")

        from omlx.engine.glm5_dynamic import Glm5DynamicVLMEngine

        return Glm5DynamicVLMEngine(
            str(checkpoint.path), trust_remote_code=False
        )


def create_adapter(context):
    return Glm5DynamicChatAdapter(context)
