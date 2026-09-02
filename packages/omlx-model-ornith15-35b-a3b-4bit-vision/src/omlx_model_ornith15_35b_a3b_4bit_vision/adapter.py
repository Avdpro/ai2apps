from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from omlx.model_adapters import ModelAdapterContext


def _asset(name: str) -> str:
    return str(
        Path(
            str(
                files("omlx_model_ornith15_35b_a3b_4bit_vision").joinpath(
                    "assets", name
                )
            )
        ).resolve()
    )


RECIPE = {
    "id": "ornith-1.5-35b-a3b-mlx-4bit-vision",
    "name": "Ornith 1.5 35B A3B 4-bit Vision",
    "description": "Mixed MLX Q4 language and BF16 vision checkpoint.",
    "family": "qwen3_6",
    "execution_modes": ("full", "cached"),
    "default_execution_mode": "full",
    "storage_policies": ("keep_source",),
    "engine": {
        "id": "ornith1.5-qwen3.6-vlm",
        "name": "Ornith 1.5 Qwen3.6 VLM",
        "version": 1,
        "scope_asset": _asset("scope-profile.json"),
        "scope_pack": _asset("scope-pack.json"),
        "scope_env": "OMLX_QWEN36_SCOPE_PROFILE",
    },
    "sources": (
        {
            "id": "huggingface",
            "label": "Hugging Face",
            "repo_id": "Avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision",
            "revision": "31428ce8829c277f9255c59662b8efab58898ecf",
        },
        {
            "id": "modelscope",
            "label": "ModelScope",
            "repo_id": "avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision",
            "revision": "2ceda9edec98ac813104d04f1fe05ca1b8fdae58",
        },
    ),
    "scope_name": "general",
    "conversion": {
        "format": "omlx-moe-expert-major-set",
        "version": 1,
        "variant": "qwen3.6-affine-q4-gate-up-fused-direct-v3",
    },
    "arena_tail_slots": 32,
    "memory_tiers": (
        {"id": "compact", "label": "Compact", "experts": 160, "estimated_gb": 20},
        {"id": "performance", "label": "Performance", "experts": 192, "estimated_gb": 22},
    ),
}


class Ornith15CachedMoeAdapter:
    adapter_id = "ornith15-cached-moe"
    priority = 95

    def match(self, context: ModelAdapterContext) -> bool:
        config = context.config
        return (
            config.get("model_type") == "qwen3_5_moe"
            and bool(config.get("vision_config"))
        )

    def installation_recipes(self) -> tuple[dict, ...]:
        return (deepcopy(RECIPE),)
