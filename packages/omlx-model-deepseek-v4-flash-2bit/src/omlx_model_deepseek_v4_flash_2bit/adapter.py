from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from omlx.model_adapters import ModelAdapterContext


def _asset(name: str) -> str:
    return str(Path(str(files("omlx_model_deepseek_v4_flash_2bit").joinpath("assets", name))).resolve())


RECIPE = {
    "id": "deepseek-v4-flash-2bit",
    "name": "DeepSeek V4 Flash 2-bit",
    "description": "MLX 2-bit DQ checkpoint with the dedicated AI2Apps Flesh engine.",
    "family": "deepseek_v4",
    "execution_modes": ("cached", "full"),
    "storage_policies": ("keep_source", "delete_after", "stream_reclaim"),
    "storage_estimates": {"source_gb": 90, "prepared_gb": 90, "keep_peak_gb": 180, "stream_peak_gb": 100},
    "engine": {"id": "deepseek-v4-flesh", "name": "DeepSeek V4 Flesh", "version": 1,
               "scope_asset": _asset("scope-profile.json"), "scope_pack": _asset("scope-pack.json")},
    "sources": ({"id": "huggingface", "label": "HuggingFace", "repo_id": "mlx-community/DeepSeek-V4-Flash-2bit-DQ",
                 "revision": "722bf559b7de93575b2320973cf2002e05bfe6c9"},),
    "scope_name": "general",
    "conversion": {"format": "omlx-moe-expert-major-set", "version": 1, "variant": "deepseek-v4-expert-major-v1"},
    "memory_tiers": ({"id": "lean", "label": "Lean", "experts": 20, "estimated_gb": 17},
                     {"id": "compact", "label": "Compact", "experts": 40, "estimated_gb": 24},
                     {"id": "optimal", "label": "Optimal", "experts": 60, "estimated_gb": 30}),
}


class DeepSeekV4Flash2BitAdapter:
    adapter_id = "deepseek-v4-flash-2bit"
    priority = 90

    def match(self, context: ModelAdapterContext) -> bool:
        config = context.config
        quantization = config.get("quantization") or config.get("quantization_config") or {}
        try:
            bits = int(quantization.get("bits"))
        except (TypeError, ValueError):
            bits = None
        return str(config.get("model_type", "")).startswith("deepseek_v4") and bits == 2

    def installation_recipes(self) -> tuple[dict, ...]:
        return (deepcopy(RECIPE),)
