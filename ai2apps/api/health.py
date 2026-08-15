"""Health contract for the AI2Apps Harness backend."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ai2apps import __version__
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformDatabaseStatus, PlatformRuntime

PlatformConfigProvider = Callable[[], PlatformConfig]
PlatformRuntimeProvider = Callable[[], PlatformRuntime | None]


class RuntimeHealth(BaseModel):
    """Runtime adapter attached to the platform API."""

    provider: str
    attached: bool


class DatabaseHealth(BaseModel):
    """Platform database bootstrap state."""

    configured: bool
    status: Literal["unconfigured", "not_initialized", "ready"]
    schema_version: int
    target_schema_version: int
    filename: str
    journal_mode: str | None = None


class PlatformHealthResponse(BaseModel):
    """Versioned health response for the AI2Apps platform layer."""

    status: Literal["ok"]
    product: Literal["ai2apps"]
    version: str
    api_version: Literal["v1"]
    runtime: RuntimeHealth
    database: DatabaseHealth


def _unconfigured_platform() -> PlatformConfig:
    return PlatformConfig.unconfigured()


def create_health_router(
    config_provider: PlatformConfigProvider | None = None,
    runtime_provider: PlatformRuntimeProvider | None = None,
) -> APIRouter:
    """Create the health router without importing the embedded oMLX runtime."""

    router = APIRouter()
    provide_config = config_provider or _unconfigured_platform

    def database_status() -> PlatformDatabaseStatus:
        runtime = runtime_provider() if runtime_provider is not None else None
        if runtime is not None:
            return runtime.database_status
        return PlatformRuntime.status_before_start(provide_config())

    @router.get(
        "/health",
        response_model=PlatformHealthResponse,
        summary="Get AI2Apps platform health",
    )
    async def platform_health() -> PlatformHealthResponse:
        database = database_status()
        return PlatformHealthResponse(
            status="ok",
            product="ai2apps",
            version=__version__,
            api_version="v1",
            runtime=RuntimeHealth(provider="omlx", attached=True),
            database=DatabaseHealth(
                configured=database.configured,
                status=database.status,
                schema_version=database.schema_version,
                target_schema_version=database.target_schema_version,
                filename=database.filename,
                journal_mode=database.journal_mode,
            ),
        )

    return router
