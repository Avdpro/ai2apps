"""Trusted request-principal resolution shared by platform API routers."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request

from ai2apps.apps.access import has_app_capability
from ai2apps.http_security import (
    enforce_same_origin_cookie_request,
    has_local_session_cookie,
)
from ai2apps.identity import RequestPrincipal

PrincipalProvider = Callable[..., RequestPrincipal]


def resolve_request_principal(request: Request) -> RequestPrincipal:
    """Resolve only identity established by trusted authentication middleware."""

    if has_local_session_cookie(request):
        enforce_same_origin_cookie_request(request)
    principal = getattr(request.state, "ai2apps_principal", None)
    if principal is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "local_session_required",
                "message": "An authenticated Local Session is required",
            },
        )
    if not isinstance(principal, RequestPrincipal):
        raise RuntimeError("Request auth state contains an invalid AI2Apps principal")
    return principal


def require_app_capability(
    principal_provider: PrincipalProvider,
    capability: str,
):
    """Build a FastAPI dependency that guards a sensitive App backend API."""

    principal_dependency = Depends(principal_provider)

    def authorize(
        principal: RequestPrincipal = principal_dependency,
    ) -> RequestPrincipal:
        if not has_app_capability(principal, capability):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "app_access_denied",
                    "message": "Current account cannot access this App backend",
                    "required_capability": capability,
                },
            )
        return principal

    return authorize
