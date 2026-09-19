from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from omlx.model_adapters import ModelAdapterContext


def _asset(name: str) -> str:
    return str(Path(str(files("omlx_model_deepseek_v41_flash").joinpath("assets", name))).resolve())


RECIPE = {
    "id": "deepseek-v41-flash",
    "name": "DeepSeek V4.1 Flash",
    "description": "DeepSeek V4.1 Flash lossless SSD Cached-MoE engine.",
    "family": "deepseek_v41",
    "execution_modes": ("cached",),
    "storage_policies": ("keep_source",),
    "storage_estimates": {"source_gb": 510.4, "prepared_gb": 0, "keep_peak_gb": 510.4},
    "engine": {
        "id": "deepseek-v41-ssd",
        "name": "DeepSeek V4.1 SSD",
        "version": 1,
        "scope_asset": _asset("scope-profile.json"),
        "scope_pack": _asset("scope-pack.json"),
    },
    "sources": ({
        "id": "huggingface",
        "label": "Hugging Face",
        "repo_id": "Avdpro/DeepSeek-V4.1-Flash-SSD",
        "revision": "efb7e03fd718ebbeb3e0d7e60ed037a920d8e441",
    },),
    "scope_name": "standard",
    "conversion": {
        "format": "ai2apps-ssd-checkpoint",
        "version": 1,
        "variant": "dsv41-original-fp4-six-segment-v1",
    },
    "main_slots": 40,
    "hot_slots": 8,
    "prefill_slots": 64,
    "memory_tiers": ({"id": "standard", "label": "Standard", "experts": 40, "estimated_gb": 65},),
}


class DeepSeekV41FlashAdapter:
    adapter_id = "deepseek-v41-flash"
    priority = 100

    def match(self, context: ModelAdapterContext) -> bool:
        return str(context.config.get("model_type", "")) == "deepseek_v41"

    def installation_recipes(self) -> tuple[dict, ...]:
        return (deepcopy(RECIPE),)
