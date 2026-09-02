from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from omlx.model_adapters import ModelAdapterContext


def _asset(name: str) -> str:
    return str(
        Path(
            str(
                files("omlx_model_qwen38_flash_next_4bit").joinpath(
                    "assets", name
                )
            )
        ).resolve()
    )


RECIPE = {
    "id": "qwen3.8-flash-next-mlx-4bit",
    "name": "Qwen3.8 Flash Next 4-bit",
    "description": "MLX Q4 multimodal checkpoint with Cached-MoE execution.",
    "family": "qwen4_exp",
    "execution_modes": ("cached", "full"),
    "storage_policies": ("keep_source",),
    "engine": {
        "id": "qwen3.8-flash-next-cached-moe",
        "name": "Qwen3.8 Flash Next Cached-MoE",
        "version": 1,
        "scope_asset": _asset("scope-profile.json"),
        "scope_pack": _asset("scope-pack.json"),
        "scope_env": "OMLX_QWEN4_SCOPE_PROFILE",
    },
    "sources": (
        {
            "id": "huggingface",
            "label": "Hugging Face",
            "repo_id": "Vontra/Qwen3.8-Flash-Next-MLX-4bit",
            "revision": "de597762aa61387c89590a46582222a261ce0387",
        },
    ),
    "scope_name": "general",
    "conversion": {
        "format": "omlx-moe-expert-major-set",
        "version": 1,
        "variant": "qwen4-exp-affine-q4-gate-up-fused-v1",
    },
    "hot_slots": 10,
    "memory_tiers": (
        {"id": "lean", "label": "Lean", "experts": 128, "estimated_gb": 41},
        {
            "id": "balanced",
            "label": "Balanced",
            "experts": 160,
            "estimated_gb": 44,
        },
        {
            "id": "performance",
            "label": "Performance",
            "experts": 224,
            "estimated_gb": 50,
        },
    ),
}


class Qwen38FlashNextCachedMoeAdapter:
    adapter_id = "qwen38-flash-next-cached-moe"
    priority = 95

    def match(self, context: ModelAdapterContext) -> bool:
        return context.config.get("model_type") == "qwen4_exp"

    def installation_recipes(self) -> tuple[dict, ...]:
        return (deepcopy(RECIPE),)
