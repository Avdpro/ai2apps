"""FastAPI ownership guards for resources rooted in an AppInstance."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider
from ai2apps.core import RepositoryError, ResourceNotFoundError
from ai2apps.extensions import ExtensionError
from ai2apps.identity import RequestPrincipal


def _runtime(runtime_provider: PlatformRuntimeProvider):
    runtime = runtime_provider()
    if runtime is None or runtime.database is None or runtime.extension_manager is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "platform_not_ready"},
        )
    return runtime


def _not_found(resource_type: str, resource_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": f"{resource_type}_not_found",
            "message": f"{resource_type} not found: {resource_id}",
        },
    )


def authorize_app_instance(
    runtime,
    principal: RequestPrincipal,
    app_instance_id: str,
) -> None:
    try:
        runtime.extension_manager.require_instance_access(
            app_instance_id,
            principal,
        )
    except (ResourceNotFoundError, ExtensionError) as error:
        raise _not_found("app_instance", app_instance_id) from error


def authorize_session(
    runtime,
    principal: RequestPrincipal,
    session_id: str,
) -> None:
    try:
        session = runtime.extension_manager.sessions.get(session_id)
        authorize_app_instance(runtime, principal, session.app_instance_id)
    except (RepositoryError, ExtensionError) as error:
        raise _not_found("session", session_id) from error


def authorize_agent_run(
    runtime,
    principal: RequestPrincipal,
    run_id: str,
) -> None:
    try:
        run = runtime.agents.get_run(run_id)
        authorize_session(runtime, principal, run.session_id)
    except (RepositoryError, ExtensionError) as error:
        raise _not_found("agent_run", run_id) from error


def require_app_instance_access(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider,
):
    principal_dependency = Depends(principal_provider)

    def authorize(
        app_instance_id: str,
        principal: RequestPrincipal = principal_dependency,
    ) -> None:
        authorize_app_instance(
            _runtime(runtime_provider),
            principal,
            app_instance_id,
        )

    return authorize


def require_session_access(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider,
):
    principal_dependency = Depends(principal_provider)

    def authorize(
        session_id: str,
        principal: RequestPrincipal = principal_dependency,
    ) -> None:
        authorize_session(_runtime(runtime_provider), principal, session_id)

    return authorize


def require_agent_run_access(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider,
):
    principal_dependency = Depends(principal_provider)

    def authorize(
        run_id: str,
        principal: RequestPrincipal = principal_dependency,
    ) -> None:
        authorize_agent_run(_runtime(runtime_provider), principal, run_id)

    return authorize
