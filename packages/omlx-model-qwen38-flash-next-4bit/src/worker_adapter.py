from collections.abc import Mapping
from typing import Any

from ai2apps.model_worker.cache_moe import Qwen4ExpChatAdapter
from ai2apps.model_worker.protocol import ModelWorkerCheckpoint, ModelWorkerError
from omlx.utils.hardware import get_total_memory_bytes


_GIB = 1024**3


def _resolve_memory_tier(requested: object) -> str:
    tier = str(requested or "auto").strip().lower()
    estimates_gib = {"lean": 41, "balanced": 44, "performance": 50}
    if tier != "auto":
        if tier not in estimates_gib:
            raise ModelWorkerError(
                f"Unsupported Qwen4 memory tier: {tier}",
                code="invalid_request_error",
                status_code=400,
            )
        return tier

    physical = get_total_memory_bytes()
    reserve = max(8 * _GIB, int(physical * 0.20))
    usable = max(0, physical - reserve)
    # Keep Balanced as the automatic ceiling so existing high-memory systems
    # retain the same default. Performance is still available explicitly.
    for candidate in ("balanced", "lean"):
        if estimates_gib[candidate] * _GIB <= usable:
            return candidate
    raise ModelWorkerError(
        "No Qwen Next Cache-MoE memory tier fits this device with the required "
        "system and KV-cache reserve",
        code="insufficient_memory",
        status_code=503,
    )


class Qwen4ExpAutoTierChatAdapter(Qwen4ExpChatAdapter):
    async def create_engine(
        self,
        checkpoint: ModelWorkerCheckpoint,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> Any:
        options = dict(runtime_options or {})
        mode = str(options.get("moe_execution_mode", "cached")).lower()
        if mode == "cached":
            options["cache_moe_memory_tier"] = _resolve_memory_tier(
                options.get("cache_moe_memory_tier", "auto")
            )
        return await super().create_engine(checkpoint, options)


def create_adapter(context):
    return Qwen4ExpAutoTierChatAdapter(context)
