"""Composition root for AI2Apps platform resource APIs."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ai2apps.api.agents import create_agent_router
from ai2apps.api.agent_builder import create_agent_builder_router
from ai2apps.api.agent_platform import create_agent_platform_router
from ai2apps.api.auth import create_auth_router
from ai2apps.api.browser import create_browser_router
from ai2apps.api.capabilities import create_capability_router
from ai2apps.api.chat import create_chat_router
from ai2apps.api.client import create_client_router
from ai2apps.api.cloud import create_cloud_router
from ai2apps.api.coder import create_coder_router
from ai2apps.api.documents import create_document_router
from ai2apps.api.event_stream import create_event_stream_router
from ai2apps.api.extensions import create_extension_router
from ai2apps.api.gallery import create_gallery_router
from ai2apps.api.health import (
    PlatformConfigProvider,
    PlatformRuntimeProvider,
    create_health_router,
)
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.api.knowledge import create_knowledge_router
from ai2apps.api.messager import create_messager_router
from ai2apps.api.model_share import create_model_share_router
from ai2apps.api.packages import create_package_router
from ai2apps.api.provisioning import create_provisioning_router
from ai2apps.api.readaloud import create_readaloud_router
from ai2apps.api.remote import create_remote_router
from ai2apps.api.resources import create_resource_router
from ai2apps.api.secrets import create_secret_router
from ai2apps.api.services import create_service_router
from ai2apps.api.sharing import create_sharing_management_router
from ai2apps.api.upstreams import create_upstream_router
from ai2apps.api.video_studio import create_video_studio_router
from ai2apps.api.workers import create_worker_router
from ai2apps.api.workspace import create_workspace_router


def create_ai2apps_router(
    *,
    config_provider: PlatformConfigProvider | None = None,
    runtime_provider: PlatformRuntimeProvider | None = None,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    """Create the versioned AI2Apps platform router."""

    router = APIRouter(prefix="/v1/platform", tags=["platform"])
    router.include_router(create_health_router(config_provider, runtime_provider))
    effective_principal_provider = principal_provider
    if runtime_provider is not None:
        if principal_provider is resolve_request_principal:

            def resolve_runtime_principal(request: Request):
                principal = resolve_request_principal(request)
                if principal.authentication_type != "legacy_api_key":
                    return principal
                runtime = runtime_provider()
                resolver = (
                    None
                    if runtime is None
                    else getattr(runtime, "legacy_api_key_principal", None)
                )
                return principal if resolver is None else resolver()

            effective_principal_provider = resolve_runtime_principal
    router.include_router(
        create_client_router(
            runtime_provider,
            effective_principal_provider if runtime_provider is not None else None,
        )
    )
    if runtime_provider is not None:
        router.include_router(
            create_cloud_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_auth_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_chat_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_coder_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_resource_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_messager_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_model_share_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_gallery_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_knowledge_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_readaloud_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_video_studio_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_imagine_studio_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_provisioning_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_event_stream_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_extension_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_service_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_sharing_management_router(
                runtime_provider, effective_principal_provider
            )
        )
        router.include_router(
            create_upstream_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_agent_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_agent_platform_router(
                runtime_provider, effective_principal_provider
            )
        )
        router.include_router(
            create_agent_builder_router(
                runtime_provider, effective_principal_provider
            )
        )
        router.include_router(
            create_capability_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_workspace_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_package_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_document_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(create_browser_router(runtime_provider))
        router.include_router(
            create_secret_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_remote_router(runtime_provider, effective_principal_provider)
        )
        router.include_router(
            create_worker_router(runtime_provider, effective_principal_provider)
        )
    return router
