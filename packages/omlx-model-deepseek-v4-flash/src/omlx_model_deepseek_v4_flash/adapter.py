from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from omlx.model_adapters import ModelAdapterContext


def _asset(name: str) -> str:
    return str(Path(str(files("omlx_model_deepseek_v4_flash").joinpath("assets", name))).resolve())


RECIPE = {
    "id": "deepseek-v4-flash",
    "name": "DeepSeek V4 Flash",
    "description": "DeepSeek V4 Flash with the dedicated AI2Apps Flesh engine.",
    "family": "deepseek_v4",
    "execution_modes": ("cached", "full"),
    "storage_policies": ("keep_source", "delete_after", "stream_reclaim"),
    "storage_estimates": {"source_gb": 148, "prepared_gb": 143, "keep_peak_gb": 291, "stream_peak_gb": 155},
    "engine": {"id": "deepseek-v4-flesh", "name": "DeepSeek V4 Flesh", "version": 1,
               "scope_asset": _asset("scope-profile.json"), "scope_pack": _asset("scope-pack.json")},
    "sources": ({"id": "huggingface", "label": "HuggingFace", "repo_id": "deepseek-ai/DeepSeek-V4-Flash",
                 "revision": "60d8d70770c6776ff598c94bb586a859a38244f1"},),
    "scope_name": "general",
    "conversion": {"format": "omlx-moe-expert-major-set", "version": 1, "variant": "deepseek-v4-expert-major-v1"},
    "memory_tiers": ({"id": "lean", "label": "Lean", "experts": 20, "estimated_gb": 33},
                     {"id": "compact", "label": "Compact", "experts": 40, "estimated_gb": 43},
                     {"id": "optimal", "label": "Optimal", "experts": 60, "estimated_gb": 54}),
}


def _bits(config: dict) -> int | None:
    quantization = config.get("quantization") or config.get("quantization_config") or {}
    try:
        return int(quantization.get("bits"))
    except (TypeError, ValueError):
        return None


class DeepSeekV4FlashAdapter:
    adapter_id = "deepseek-v4-flash"
    priority = 90

    def match(self, context: ModelAdapterContext) -> bool:
        return str(context.config.get("model_type", "")).startswith("deepseek_v4") and _bits(context.config) != 2

    def installation_recipes(self) -> tuple[dict, ...]:
        return (deepcopy(RECIPE),)
