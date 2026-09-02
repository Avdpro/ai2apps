"""Desktop client bootstrap contract."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import platform
import secrets
import signal
import time
from collections.abc import Callable
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from ai2apps import __version__
from ai2apps.api.identity import PrincipalProvider
from ai2apps.browser.profiles import BrowserProfileRepository
from ai2apps.browser.shell_window import (
    shell_browser_profile_key,
    shell_browser_window_broker,
)
from ai2apps.helper_control import HelperControlClient, HelperControlError
from ai2apps.identity import (
    IdentityBindingError,
    IdentityRepository,
    RequestPrincipal,
)
from ai2apps.managed_browser import (
    managed_browser_broker,
    managed_browser_profile_key,
)
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.supervision import (
    current_supervised_instance_id,
    current_supervision_boot_id,
)

PlatformRuntimeProvider = Callable[[], PlatformRuntime | None]
HelperControlProvider = Callable[[], HelperControlClient | None]
logger = logging.getLogger(__name__)


class ClientBootstrapResponse(BaseModel):
    status: Literal["starting", "ready"]
    product: Literal["ai2apps"]
    product_version: str
    api_version: Literal[1]
    instance_id: str
    installation_id: str | None
    device_name: str
    boot_id: str
    shell_path: Literal["/v1/platform/client/shell"]
    capabilities: list[str]


class BrowserAgentLaunchRequest(BaseModel):
    initial_url: str | None = Field(default=None, max_length=2048)


class BrowserAgentLaunchResponse(BaseModel):
    status: Literal["launched", "focused"]
    profile_id: str
    pid: int


class LocalRestartResponse(BaseModel):
    status: Literal["restarting"]


class ShellSessionResponse(BaseModel):
    status: Literal["ready"]
    shell_path: Literal["/v1/platform/client/shell"]
    cookie_name: str
    cookie_value: str
    expires_at_ms: int


class ManagedBrowserCompleteRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=2_000_000)
    extraction_method: str = Field(default="readability", max_length=100)


class BrowserProfileResponse(BaseModel):
    profile_key: str = Field(pattern=r"^[0-9a-f]{64}$")


def _client_device_name(runtime: PlatformRuntime | None) -> str:
    candidate = ""
    database = None if runtime is None else getattr(runtime, "database", None)
    remote = None if runtime is None else getattr(runtime, "remote", None)
    if database is not None and remote is not None:
        try:
            installation = IdentityRepository(database).get_installation()
            if installation is not None:
                candidate = remote.require_device(
                    installation.cloud_device_id
                ).display_name
        except (AttributeError, IdentityBindingError, RuntimeError, ValueError):
            pass
    if not candidate:
        candidate = platform.node()
    candidate = "".join(character for character in candidate if character >= " ")
    return " ".join(candidate.split())[:120] or "Local Device"


def _request_shell_browser_action(
    actor_user_id: str,
    profile_key: str,
    profile_name: str,
    is_default: bool,
    action: Literal["open", "delete"],
    initial_url: str | None,
) -> dict[str, Any]:
    """Ask the running AppShell to perform its native browser-window action."""
    if initial_url is not None and urlsplit(initial_url).scheme.lower() not in {
        "http",
        "https",
    }:
        raise ValueError("Initial URL must use HTTP or HTTPS")
    request_id = shell_browser_window_broker.enqueue(
        action=action,
        profile_key=shell_browser_profile_key(actor_user_id, profile_key),
        profile_name=profile_name,
        is_default=is_default,
        initial_url=initial_url,
    )
    result = shell_browser_window_broker.wait(request_id)
    return {**result, "profile_id": profile_key}


class ManagedBrowserProfileResponse(BaseModel):
    key: str = Field(pattern=r"^(default|[0-9a-f]{32})$")
    name: str
    is_default: bool
    created_at: str | None = None


class CreateBrowserProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


_SHELL_PATH = "/v1/platform/client/shell"
_HELPER_TOKEN_LENGTH = 64
_SHELL_SESSION_SECONDS = 5 * 60


def _schedule_supervised_self_restart(delay: float = 0.5) -> None:
    """Exit after the HTTP response so the owning Helper respawns Local."""
    pid = os.getpid()

    def _terminate() -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:  # pragma: no cover - best-effort shutdown seam.
            logger.exception("Failed to terminate Local for supervised restart")

    asyncio.get_running_loop().call_later(delay, _terminate)


def _helper_secret() -> bytes | None:
    value = os.environ.get("AI2APPS_HELPER_TOKEN", "")
    if len(value) != _HELPER_TOKEN_LENGTH:
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:
        return None


def _require_helper_authorization(request: Request) -> None:
    supplied = request.headers.get("authorization", "")
    expected = os.environ.get("AI2APPS_HELPER_TOKEN", "")
    if (
        _helper_secret() is None
        or request.headers.get("origin") is not None
        or not supplied.startswith("Bearer ")
        or not hmac.compare_digest(supplied.removeprefix("Bearer "), expected)
    ):
        raise HTTPException(status_code=401, detail="Desktop shell authorization failed")


def _shell_cookie_name(instance_id: str) -> str:
    digest = hashlib.sha256(instance_id.encode("ascii")).hexdigest()[:16]
    return f"ai2apps_desktop_shell_{digest}"


def _encode_shell_session(
    secret: bytes, instance_id: str, boot_id: str, expires_at: int
) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "instance": instance_id,
            "boot": boot_id,
            "exp": expires_at,
            "nonce": secrets.token_hex(16),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _valid_shell_session(
    token: str | None, secret: bytes, instance_id: str, boot_id: str
) -> bool:
    if not token or len(token) > 1024:
        return False
    encoded, separator, supplied_signature = token.partition(".")
    if not separator or len(supplied_signature) != 64:
        return False
    expected_signature = hmac.new(
        secret, encoded.encode("ascii", errors="ignore"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return False
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        return (
            payload.get("v") == 1
            and payload.get("instance") == instance_id
            and payload.get("boot") == boot_id
            and int(payload.get("exp", 0)) >= int(time.time())
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def is_desktop_shell_request(request: Request) -> bool:
    """Return whether *request* belongs to the authenticated desktop shell.

    App surfaces use this server-derived signal for small host-specific UX
    choices, such as letting AceFox open a native Save As panel. Keeping the
    check here avoids brittle User-Agent sniffing and does not expose the
    privileged, HttpOnly shell cookie to App JavaScript.
    """

    secret = _helper_secret()
    if secret is None:
        return False
    instance_id = current_supervised_instance_id(fallback="unconfigured")
    boot_id = str(current_supervision_boot_id())
    token = request.cookies.get(_shell_cookie_name(instance_id))
    return _valid_shell_session(token, secret, instance_id, boot_id)


def create_client_router(
    runtime_provider: PlatformRuntimeProvider | None = None,
    principal_provider: PrincipalProvider | None = None,
    helper_control_provider: HelperControlProvider = HelperControlClient.from_environment,
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/client/bootstrap",
        response_model=ClientBootstrapResponse,
        summary="Bootstrap an AI2Apps desktop client",
    )
    async def client_bootstrap() -> ClientBootstrapResponse:
        runtime = runtime_provider() if runtime_provider is not None else None
        security_identity = None if runtime is None else runtime.security_identity
        installation_id = (
            None if security_identity is None else security_identity.security_instance_id
        )
        fallback = installation_id or "unconfigured"
        instance_id = current_supervised_instance_id(fallback=fallback)
        ready = (
            runtime is not None
            and runtime.database_status.status == "ready"
            and installation_id is not None
        )
        capabilities = ["shell"]
        if runtime is not None and runtime.browser is not None:
            capabilities.append("browser.agent")
        return ClientBootstrapResponse(
            status="ready" if ready else "starting",
            product="ai2apps",
            product_version=__version__,
            api_version=1,
            instance_id=instance_id,
            installation_id=installation_id,
            device_name=_client_device_name(runtime),
            boot_id=str(current_supervision_boot_id()),
            shell_path=_SHELL_PATH,
            capabilities=capabilities,
        )

    @router.post(
        "/client/shell-session",
        response_model=ShellSessionResponse,
        summary="Establish the privileged desktop shell session",
    )
    async def establish_shell_session(
        request: Request, response: Response
    ) -> ShellSessionResponse:
        secret = _helper_secret()
        _require_helper_authorization(request)
        assert secret is not None
        instance_id = current_supervised_instance_id(fallback="unconfigured")
        boot_id = str(current_supervision_boot_id())
        expires_at = int(time.time()) + _SHELL_SESSION_SECONDS
        cookie_name = _shell_cookie_name(instance_id)
        cookie_value = _encode_shell_session(
            secret, instance_id, boot_id, expires_at
        )
        response.set_cookie(
            cookie_name,
            cookie_value,
            max_age=_SHELL_SESSION_SECONDS,
            httponly=True,
            secure=False,
            samesite="strict",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return ShellSessionResponse(
            status="ready",
            shell_path=_SHELL_PATH,
            cookie_name=cookie_name,
            cookie_value=cookie_value,
            expires_at_ms=expires_at * 1000,
        )

    @router.get("/client/managed-browser/next", include_in_schema=False)
    async def next_managed_browser_request(request: Request):
        _require_helper_authorization(request)
        pending = managed_browser_broker.claim_next()
        if pending is None:
            return Response(
                content="null",
                media_type="application/json",
                headers={"Cache-Control": "no-store"},
            )
        return Response(
            content=json.dumps(pending),
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )

    @router.post(
        "/client/managed-browser/{request_id}/complete", include_in_schema=False
    )
    async def complete_managed_browser_request(
        request_id: str,
        body: ManagedBrowserCompleteRequest,
        request: Request,
    ) -> dict[str, Any]:
        _require_helper_authorization(request)
        try:
            return managed_browser_broker.finish(request_id, body.model_dump())
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/client/shell-browser-window/next", include_in_schema=False)
    async def next_shell_browser_window_request(request: Request):
        _require_helper_authorization(request)
        pending = shell_browser_window_broker.claim_next()
        return Response(
            content=json.dumps(pending),
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )

    @router.post(
        "/client/shell-browser-window/{request_id}/complete",
        include_in_schema=False,
    )
    async def complete_shell_browser_window_request(
        request_id: str,
        request: Request,
        status: str,
        pid: int,
        error: str | None = None,
    ) -> dict[str, Any]:
        _require_helper_authorization(request)
        try:
            return shell_browser_window_broker.finish(
                request_id,
                status=status,
                pid=pid,
                error=error,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/client/shell", include_in_schema=False)
    async def enter_shell(request: Request):
        if not is_desktop_shell_request(request):
            raise HTTPException(status_code=401, detail="Desktop shell session required")
        return RedirectResponse(url="/", status_code=303, headers={"Cache-Control": "no-store"})

    if principal_provider is not None:
        principal_dependency = Depends(principal_provider)

        @router.get(
            "/client/browser-profile",
            response_model=BrowserProfileResponse,
            summary="Resolve the current user's in-process browser profile",
        )
        async def current_browser_profile(
            principal: RequestPrincipal = principal_dependency,
        ) -> BrowserProfileResponse:
            return BrowserProfileResponse(
                profile_key=managed_browser_profile_key(principal.actor_user_id)
            )

        @router.post(
            "/client/browser-agent",
            response_model=BrowserAgentLaunchResponse,
            summary="Launch the current user's isolated AceFox Agent",
        )
        async def launch_browser_agent(
            body: BrowserAgentLaunchRequest,
            principal: RequestPrincipal = principal_dependency,
        ) -> BrowserAgentLaunchResponse:
            try:
                client = helper_control_provider()
            except HelperControlError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if client is None:
                raise HTTPException(
                    status_code=503,
                    detail="Desktop Helper control channel is unavailable",
                )
            try:
                result = await asyncio.to_thread(
                    client.launch_browser_agent,
                    actor_user_id=principal.actor_user_id,
                    initial_url=body.initial_url,
                )
                return BrowserAgentLaunchResponse.model_validate(result)
            except (HelperControlError, ValueError) as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

        def browser_profile_repository() -> BrowserProfileRepository:
            runtime = runtime_provider() if runtime_provider is not None else None
            if runtime is None or runtime.database is None:
                raise HTTPException(status_code=503, detail="Browser Profile storage is unavailable")
            return BrowserProfileRepository(runtime.database)

        @router.get(
            "/client/browser-profiles",
            response_model=list[ManagedBrowserProfileResponse],
            summary="List the current user's AceFox Profiles",
        )
        async def list_browser_profiles(
            principal: RequestPrincipal = principal_dependency,
        ) -> list[ManagedBrowserProfileResponse]:
            return [
                ManagedBrowserProfileResponse.model_validate(profile.as_dict())
                for profile in browser_profile_repository().list_for_user(
                    principal.actor_user_id
                )
            ]

        @router.post(
            "/client/browser-profiles",
            response_model=ManagedBrowserProfileResponse,
            status_code=201,
            summary="Create an AceFox Profile for the current user",
        )
        async def create_browser_profile(
            body: CreateBrowserProfileRequest,
            principal: RequestPrincipal = principal_dependency,
        ) -> ManagedBrowserProfileResponse:
            try:
                profile = browser_profile_repository().create(
                    principal.actor_user_id, body.name
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            return ManagedBrowserProfileResponse.model_validate(profile.as_dict())

        @router.post(
            "/client/browser-profiles/{profile_key}/launch",
            response_model=BrowserAgentLaunchResponse,
            summary="Launch or focus one AceFox Profile",
        )
        async def launch_named_browser_profile(
            profile_key: str,
            body: BrowserAgentLaunchRequest,
            principal: RequestPrincipal = principal_dependency,
        ) -> BrowserAgentLaunchResponse:
            try:
                profile = browser_profile_repository().require(
                    principal.actor_user_id, profile_key
                )
                result = await asyncio.to_thread(
                    _request_shell_browser_action,
                    principal.actor_user_id,
                    profile_key,
                    profile.name,
                    profile.is_default,
                    "open",
                    body.initial_url,
                )
                return BrowserAgentLaunchResponse.model_validate(result)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except (RuntimeError, TimeoutError, ValueError) as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

        @router.delete(
            "/client/browser-profiles/{profile_key}",
            status_code=204,
            summary="Close and delete one non-default AceFox Profile",
        )
        async def delete_browser_profile(
            profile_key: str,
            principal: RequestPrincipal = principal_dependency,
        ) -> Response:
            repository = browser_profile_repository()
            try:
                profile = repository.require(principal.actor_user_id, profile_key)
                if profile_key == "default":
                    raise ValueError("The default browser Profile cannot be deleted")
                await asyncio.to_thread(
                    _request_shell_browser_action,
                    principal.actor_user_id,
                    profile_key,
                    profile.name,
                    profile.is_default,
                    "delete",
                    None,
                )
                repository.delete(principal.actor_user_id, profile_key)
                return Response(status_code=204)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except (RuntimeError, TimeoutError) as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc

        @router.post(
            "/client/restart-local",
            response_model=LocalRestartResponse,
            status_code=202,
            summary="Restart the supervised AI2Apps Local",
        )
        async def restart_local(
            principal: RequestPrincipal = principal_dependency,
        ) -> LocalRestartResponse:
            if not principal.is_core:
                raise HTTPException(
                    status_code=403,
                    detail="Only the device owner can restart Local",
                )
            try:
                client = helper_control_provider()
            except HelperControlError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if client is None:
                raise HTTPException(
                    status_code=503,
                    detail="Desktop Helper control channel is unavailable",
                )
            try:
                result = await asyncio.to_thread(
                    client.restart_local,
                    actor_user_id=principal.actor_user_id,
                )
                return LocalRestartResponse.model_validate(result)
            except (HelperControlError, ValueError) as exc:
                # A live Helper can reject a request when an older Local was
                # launched with a token that has since rotated. The request is
                # already restricted to the authenticated device owner. When
                # the Helper is explicitly supervising this process, exit only
                # after returning 202 so that the same Helper respawns Local
                # with its current control credentials.
                if (
                    isinstance(exc, HelperControlError)
                    and str(exc) == "Helper request rejected"
                    and os.environ.get("AI2APPS_SUPERVISED") == "helper"
                ):
                    _schedule_supervised_self_restart()
                    logger.warning(
                        "Helper rejected stale Local credentials; "
                        "falling back to supervised self-restart"
                    )
                    return LocalRestartResponse(status="restarting")
                raise HTTPException(status_code=503, detail=str(exc)) from exc

    return router
