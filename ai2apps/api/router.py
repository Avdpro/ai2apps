"""Composition root for AI2Apps platform resource APIs."""

from __future__ import annotations

from fastapi import APIRouter

from ai2apps.api.agents import create_agent_router
from ai2apps.api.browser import create_browser_router
from ai2apps.api.capabilities import create_capability_router
from ai2apps.api.chat import create_chat_router
from ai2apps.api.cloud import create_cloud_router
from ai2apps.api.documents import create_document_router
from ai2apps.api.event_stream import create_event_stream_router
from ai2apps.api.extensions import create_extension_router
from ai2apps.api.health import (
    PlatformConfigProvider,
    PlatformRuntimeProvider,
    create_health_router,
)
from ai2apps.api.packages import create_package_router
from ai2apps.api.resources import create_resource_router
from ai2apps.api.remote import create_remote_router
from ai2apps.api.secrets import create_secret_router
from ai2apps.api.services import create_service_router
from ai2apps.api.workspace import create_workspace_router


def create_ai2apps_router(
    *,
    config_provider: PlatformConfigProvider | None = None,
    runtime_provider: PlatformRuntimeProvider | None = None,
) -> APIRouter:
    """Create the versioned AI2Apps platform router."""

    router = APIRouter(prefix="/v1/platform", tags=["platform"])
    router.include_router(create_health_router(config_provider, runtime_provider))
    if runtime_provider is not None:
        router.include_router(create_cloud_router(runtime_provider))
        router.include_router(create_chat_router(runtime_provider))
        router.include_router(create_resource_router(runtime_provider))
        router.include_router(create_event_stream_router(runtime_provider))
        router.include_router(create_extension_router(runtime_provider))
        router.include_router(create_service_router(runtime_provider))
        router.include_router(create_agent_router(runtime_provider))
        router.include_router(create_capability_router(runtime_provider))
        router.include_router(create_workspace_router(runtime_provider))
        router.include_router(create_package_router(runtime_provider))
        router.include_router(create_document_router(runtime_provider))
        router.include_router(create_browser_router(runtime_provider))
        router.include_router(create_secret_router(runtime_provider))
        router.include_router(create_remote_router(runtime_provider))
    return router
