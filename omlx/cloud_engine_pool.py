"""Inference-free engine-pool contract for the AI2Apps Base App.

The desktop Base App owns the Local control plane, package management, Cloud
providers, and managed Service processes.  It deliberately does not load MLX
in its own Python process.  Keeping this small null implementation behind the
same server contract lets the existing HTTP/UI surface report zero in-process
models while installed model Service Packages remain available through the
AI2Apps provider registry.
"""

from __future__ import annotations

from typing import Any

from .exceptions import ModelNotFoundError


class CloudEnginePool:
    """An EnginePool-compatible object with no in-process inference engines."""

    def __init__(self, scheduler_config: object | None = None) -> None:
        self._entries: dict[str, Any] = {}
        self._settings_manager: object | None = None
        self._scheduler_config = scheduler_config
        self._process_memory_enforcer: object | None = None
        self._get_final_ceiling = lambda: 0
        self._get_admission_ceiling = lambda: 0
        self._get_admission_soft_target = lambda: 0

    @property
    def model_count(self) -> int:
        return 0

    @property
    def loaded_model_count(self) -> int:
        return 0

    @property
    def current_model_memory(self) -> int:
        return 0

    def discover_models(self, model_dirs, pinned_models=None) -> list[str]:
        return []

    def apply_settings_overrides(self, settings_manager: object) -> None:
        self._settings_manager = settings_manager

    def get_model_ids(self) -> list[str]:
        return []

    def get_loaded_model_ids(self) -> list[str]:
        return []

    def get_entry(self, model_id: str):
        return None

    def resolve_model_id(self, model_id_or_alias: str, settings_manager) -> str:
        return model_id_or_alias

    async def get_engine(self, model_id: str, *args, **kwargs):
        raise ModelNotFoundError(model_id, [])

    async def release_engine(self, model_id: str) -> None:
        return None

    async def _unload_engine(self, model_id: str) -> None:
        return None

    async def preload_pinned_models(self) -> None:
        return None

    async def check_ttl_expirations(
        self,
        settings_manager: object,
        global_idle_timeout_seconds: int | None = None,
    ) -> list[str]:
        return []

    async def shutdown(self) -> None:
        return None

    def get_status(self) -> dict[str, Any]:
        return {
            "runtime_profile": "cloud",
            "local_inference": False,
            "final_ceiling": 0,
            "current_model_memory": 0,
            "model_count": 0,
            "loaded_count": 0,
            "load_seconds_per_gb_estimate": None,
            "load_time_observations": 0,
            "models": [],
        }
