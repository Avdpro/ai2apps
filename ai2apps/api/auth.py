"""Host-only Local member authentication for one bound installation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, SecretStr

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.cloud_client import AI2APPS_CLOUD_BROWSER_COOKIE
from ai2apps.http_security import (
    enforce_same_origin_cookie_request,
    has_browser_auth_cookie,
)
from ai2apps.identity import (
    LOCAL_SESSION_COOKIE,
    IdentityBindingError,
    RequestPrincipal,
    local_session_cookie_name,
)
from ai2apps.remote import RemoteAccessError


class MemberHandoffExchangeRequest(BaseModel):
    handoff: str = Field(min_length=24, max_length=200)


class CoreBootstrapRequest(BaseModel):
    display_name: str = Field(alias="displayName", min_length=1, max_length=120)
    owner_password: SecretStr = Field(alias="ownerPassword", min_length=12, max_length=128)


def create_auth_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["platform-auth"])
    principal_dependency = Depends(principal_provider)

    def cloud_browser_session(request: Request, runtime) -> tuple[str, str | None]:
        name_resolver = (
            None
            if runtime is None
            else getattr(runtime, "cloud_browser_cookie_name", None)
        )
        cookie_reader = (
            None
            if runtime is None
            else getattr(runtime, "cloud_browser_session_from_cookies", None)
        )
        cookie_name = (
            name_resolver()
            if name_resolver is not None
            else AI2APPS_CLOUD_BROWSER_COOKIE
        )
        value = (
            cookie_reader(request.cookies)
            if cookie_reader is not None
            else request.cookies.get(cookie_name)
        )
        return cookie_name, value

    def establish_local_session(
        request: Request,
        response: Response,
        token: str,
        principal: RequestPrincipal,
    ) -> dict[str, object]:
        hostname = request.url.hostname
        loopback = hostname in {"127.0.0.1", "localhost", "::1"}
        runtime = runtime_provider()
        cookie_name_resolver = (
            None
            if runtime is None
            else getattr(runtime, "local_session_cookie_name", None)
        )
        cookie_name = (
            cookie_name_resolver()
            if cookie_name_resolver is not None
            else local_session_cookie_name(principal.installation_id)
        )
        response.set_cookie(
            cookie_name,
            token,
            max_age=12 * 60 * 60,
            httponly=True,
            secure=request.url.scheme == "https" or not loopback,
            samesite="strict",
            path="/",
        )
        if cookie_name != LOCAL_SESSION_COOKIE:
            response.delete_cookie(
                LOCAL_SESSION_COOKIE, path="/", samesite="strict"
            )
        # Never leave a dormant administrator session behind the member Cookie.
        admin_cookie_resolver = getattr(
            runtime, "legacy_admin_session_cookie_name", None
        )
        admin_cookie_name = (
            admin_cookie_resolver()
            if admin_cookie_resolver is not None
            else "omlx_admin_session"
        )
        response.delete_cookie(admin_cookie_name, path="/", samesite="strict")
        if admin_cookie_name != "omlx_admin_session":
            response.delete_cookie(
                "omlx_admin_session", path="/", samesite="strict"
            )
        return {
            "actorUserId": principal.actor_user_id,
            "installationId": principal.installation_id,
            "organizationId": principal.organization_id,
            "role": principal.role.value,
            "membershipEpoch": principal.membership_epoch,
            "isCore": principal.is_core,
        }

    @router.post("/handoff/exchange", status_code=201)
    async def exchange_handoff(
        payload: MemberHandoffExchangeRequest,
        request: Request,
        response: Response,
    ):
        runtime = runtime_provider()
        exchanger = (
            None if runtime is None else getattr(runtime, "exchange_member_handoff", None)
        )
        if exchanger is None:
            return platform_error_response(
                status_code=503,
                code="local_member_auth_not_ready",
                message="Local member authentication is not ready.",
                retryable=True,
            )
        try:
            token, principal = await exchanger(payload.handoff)
        except RemoteAccessError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code.lower(),
                message=str(error),
                retryable=error.status_code >= 500,
            )
        except IdentityBindingError as error:
            return platform_error_response(
                status_code=409,
                code="installation_identity_not_ready",
                message=str(error),
                retryable=False,
            )
        return establish_local_session(request, response, token, principal)

    @router.post("/cloud-member/activate", status_code=201)
    async def activate_cloud_member(
        request: Request,
        response: Response,
    ):
        """Exchange a signed-in Cloud Installation member for a Local Session."""
        runtime = runtime_provider()
        _, browser_session_id = cloud_browser_session(request, runtime)
        if browser_session_id or has_browser_auth_cookie(request):
            enforce_same_origin_cookie_request(request)
        activator = (
            None
            if runtime is None
            else getattr(runtime, "activate_current_cloud_member", None)
        )
        if activator is None:
            return platform_error_response(
                status_code=503,
                code="local_member_auth_not_ready",
                message="Local member authentication is not ready.",
                retryable=True,
            )
        browser_cloud_resolver = getattr(runtime, "cloud_for_browser", None)
        if browser_cloud_resolver is None:
            browser_cloud = getattr(runtime, "cloud", None)
        else:
            try:
                browser_cloud = browser_cloud_resolver(browser_session_id or "")
            except (RuntimeError, ValueError):
                browser_cloud = None
        if browser_cloud is None:
            return platform_error_response(
                status_code=409,
                code="cloud_browser_session_required",
                message="Sign in to AI2Apps Cloud in this browser before activating a Local member.",
                retryable=False,
            )
        try:
            token, principal = await activator(cloud=browser_cloud)
        except RemoteAccessError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code.lower(),
                message=str(error),
                retryable=error.status_code >= 500,
            )
        except IdentityBindingError as error:
            return platform_error_response(
                status_code=409,
                code="installation_identity_not_ready",
                message=str(error),
                retryable=False,
            )
        return establish_local_session(request, response, token, principal)

    @router.post("/core/bootstrap", status_code=201)
    async def bootstrap_core(
        payload: CoreBootstrapRequest,
        request: Request,
        response: Response,
    ):
        """Bind an unclaimed Local instance to its first signed-in Core account."""

        runtime = runtime_provider()
        _, browser_session_id = cloud_browser_session(request, runtime)
        if browser_session_id or has_browser_auth_cookie(request):
            enforce_same_origin_cookie_request(request)
        browser_cloud_resolver = (
            None if runtime is None else getattr(runtime, "cloud_for_browser", None)
        )
        try:
            browser_cloud = (
                browser_cloud_resolver(browser_session_id or "")
                if browser_cloud_resolver is not None
                else None if runtime is None else getattr(runtime, "cloud", None)
            )
        except (RuntimeError, ValueError):
            browser_cloud = None
        bootstrapper = (
            None if runtime is None else getattr(runtime, "bootstrap_core_account", None)
        )
        if browser_cloud is None:
            return platform_error_response(
                status_code=409,
                code="cloud_browser_session_required",
                message="Sign in to AI2Apps Cloud in this browser first.",
                retryable=False,
            )
        if bootstrapper is None:
            return platform_error_response(
                status_code=503,
                code="core_bootstrap_not_ready",
                message="Core account bootstrap is not ready.",
                retryable=True,
            )
        try:
            token, principal = await bootstrapper(
                display_name=payload.display_name,
                owner_password=payload.owner_password.get_secret_value(),
                cloud=browser_cloud,
            )
        except RemoteAccessError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code.lower(),
                message=str(error),
                retryable=error.status_code >= 500,
            )
        except IdentityBindingError as error:
            return platform_error_response(
                status_code=409,
                code="installation_already_bound",
                message=str(error),
                retryable=False,
            )
        if not principal.is_core:
            revoker = getattr(runtime, "revoke_local_session", None)
            if revoker is not None:
                revoker(token)
            return platform_error_response(
                status_code=403,
                code="core_account_required",
                message="Cloud did not establish the signed-in account as device Core.",
                retryable=False,
            )
        return establish_local_session(request, response, token, principal)

    @router.get("/me")
    async def me(principal: RequestPrincipal = principal_dependency):
        return {
            "actorUserId": principal.actor_user_id,
            "installationId": principal.installation_id,
            "organizationId": principal.organization_id,
            "role": principal.role.value,
            "membershipEpoch": principal.membership_epoch,
            "isCore": principal.is_core,
            "authenticationType": principal.authentication_type,
        }

    @router.post("/logout", status_code=204)
    async def logout(
        request: Request,
        response: Response,
    ) -> None:
        runtime = runtime_provider()
        cloud_cookie_name, browser_session_id = cloud_browser_session(
            request, runtime
        )
        if browser_session_id or has_browser_auth_cookie(request):
            enforce_same_origin_cookie_request(request)
        cookie_name_resolver = (
            None
            if runtime is None
            else getattr(runtime, "local_session_cookie_name", None)
        )
        cookie_name = (
            cookie_name_resolver()
            if cookie_name_resolver is not None
            else LOCAL_SESSION_COOKIE
        )
        token = request.cookies.get(cookie_name)
        if token is None and cookie_name != LOCAL_SESSION_COOKIE:
            token = request.cookies.get(LOCAL_SESSION_COOKIE)
        revoker = (
            None if runtime is None else getattr(runtime, "revoke_local_session", None)
        )
        if revoker is not None:
            revoker(token)
        browser_cloud_clearer = (
            None if runtime is None else getattr(runtime, "clear_cloud_for_browser", None)
        )
        browser_cloud_resolver = (
            None if runtime is None else getattr(runtime, "cloud_for_browser", None)
        )
        if browser_cloud_clearer is not None and browser_session_id:
            await browser_cloud_clearer(browser_session_id)
        elif browser_cloud_resolver is not None and browser_session_id:
            try:
                browser_cloud = browser_cloud_resolver(browser_session_id)
            except (RuntimeError, ValueError):
                browser_cloud = None
            if browser_cloud is not None:
                await browser_cloud.clear_session()
        response.delete_cookie(cookie_name, path="/", samesite="strict")
        if cookie_name != LOCAL_SESSION_COOKIE:
            response.delete_cookie(
                LOCAL_SESSION_COOKIE, path="/", samesite="strict"
            )
        response.delete_cookie(
            cloud_cookie_name, path="/", samesite="strict"
        )
        if cloud_cookie_name != AI2APPS_CLOUD_BROWSER_COOKIE:
            response.delete_cookie(
                AI2APPS_CLOUD_BROWSER_COOKIE, path="/", samesite="strict"
            )
        admin_cookie_resolver = (
            None
            if runtime is None
            else getattr(runtime, "legacy_admin_session_cookie_name", None)
        )
        admin_cookie_name = (
            admin_cookie_resolver()
            if admin_cookie_resolver is not None
            else "omlx_admin_session"
        )
        response.delete_cookie(admin_cookie_name, path="/", samesite="strict")
        if admin_cookie_name != "omlx_admin_session":
            response.delete_cookie(
                "omlx_admin_session", path="/", samesite="strict"
            )

    return router
