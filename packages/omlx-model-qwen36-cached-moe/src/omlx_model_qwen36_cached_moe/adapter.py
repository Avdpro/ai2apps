from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from omlx.model_adapters import ModelAdapterContext


def _asset(name: str) -> str:
    return str(Path(str(files("omlx_model_qwen36_cached_moe").joinpath("assets", name))).resolve())


RECIPE = {
    "id": "qwen3.6-35b-a3b-4bit",
    "name": "Qwen3.6 35B A3B 4-bit",
    "description": "MLX 4-bit checkpoint with the dedicated AI2Apps Tiered engine.",
    "family": "qwen3_6",
    "execution_modes": ("cached", "full"),
    "storage_policies": ("keep_source",),
    "engine": {"id": "qwen3.6-tiered", "name": "Qwen3.6 Tiered", "version": 1,
               "scope_asset": _asset("scope-profile.json"), "scope_pack": _asset("scope-pack.json"),
               "scope_env": "OMLX_QWEN36_SCOPE_PROFILE"},
    "sources": ({"id": "huggingface", "label": "HuggingFace", "repo_id": "mlx-community/Qwen3.6-35B-A3B-4bit",
                 "revision": "38740b847e4cb78f352aba30aa41c76e08e6eb46"},),
    "scope_name": "general",
    "conversion": {"format": "omlx-moe-expert-major-set", "version": 1, "variant": "qwen3.6-affine-q4-gate-up-fused-v2"},
    "arena_tail_slots": 24,
    "memory_tiers": ({"id": "lean", "label": "Lean", "experts": 80, "estimated_gb": 9},
                     {"id": "compact", "label": "Compact", "experts": 96, "estimated_gb": 10},
                     {"id": "optimal", "label": "Optimal", "experts": 120, "estimated_gb": 12}),
}


class Qwen36CachedMoeAdapter:
    adapter_id = "qwen36-cached-moe"
    priority = 90

    def match(self, context: ModelAdapterContext) -> bool:
        return context.config.get("model_type") == "qwen3_5_moe"

    def installation_recipes(self) -> tuple[dict, ...]:
        return (deepcopy(RECIPE),)
