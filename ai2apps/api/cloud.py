"""Local native-network facade for the AI2Apps Cloud v1 API."""

from __future__ import annotations

import json
import logging
import re
import secrets
from contextvars import ContextVar
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai2apps.account_capacity import capacity_policy_payload
from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.cloud_client import AI2APPS_CLOUD_BROWSER_COOKIE
from ai2apps.cloud_requests import (
    CloudAIRequestRepository,
    CloudRequestOwnershipError,
)
from ai2apps.http_security import enforce_same_origin_cookie_request
from ai2apps.identity import IdentityBindingError, RequestPrincipal
from ai2apps.messager import (
    MessagerIdempotencyConflictError,
    MessagerRepository,
)
from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.qr import svg_qr_data_url
from ai2apps.remote import RemoteAccessError

_RESERVED_IDENTITY_FIELDS = frozenset(
    {
        "actorUserId",
        "actor_user_id",
        "billingAccountId",
        "billing_account_id",
        "installationId",
        "installation_id",
        "membershipEpoch",
        "membership_epoch",
        "organizationId",
        "organization_id",
    }
)

logger = logging.getLogger(__name__)

_BROWSER_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_REQUEST_CLOUD: ContextVar[Any | None] = ContextVar(
    "ai2apps_request_cloud", default=None
)
_PENDING_BROWSER_COOKIE: ContextVar[tuple[str, str, bool] | None] = ContextVar(
    "ai2apps_pending_browser_cookie", default=None
)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    display_name: str = Field(alias="displayName", min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)


class AdminReauthRequest(BaseModel):
    password: str = Field(min_length=12, max_length=128)
    duration_minutes: Literal[5, 15, 60, 180] = Field(
        default=15, alias="durationMinutes"
    )


class UserProfilePatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    public_handle: str | None = Field(
        default=None,
        alias="publicHandle",
        pattern=r"^[a-z0-9][a-z0-9-]{2,31}$",
    )
    display_name: str | None = Field(
        default=None, alias="displayName", min_length=1, max_length=120
    )
    avatar_url: str | None = Field(default=None, alias="avatarUrl", max_length=2048)
    bio: str | None = Field(default=None, max_length=1000)
    gender: str | None = Field(default=None, max_length=80)
    visibility: Literal["private", "public"] | None = None
    discoverable_by_email: bool | None = Field(
        default=None, alias="discoverableByEmail"
    )
    friend_request_policy: Literal["everyone", "mutuals", "nobody"] | None = Field(
        default=None, alias="friendRequestPolicy"
    )


class PrimaryProfileDeviceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    device_id: str | None = Field(
        alias="deviceId",
        min_length=32,
        max_length=80,
    )


ProfileSocialPlatform = Literal[
    "x",
    "instagram",
    "facebook",
    "github",
    "tiktok",
    "discord",
    "reddit",
    "xiaohongshu",
    "douyin",
    "weibo",
    "bilibili",
]


class ProfileSocialLinkRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    handle: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=1, max_length=2048)


class PublicProfileLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=1, max_length=320)


class OfflineMessageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    recipient_user_id: str = Field(alias="recipientUserId", min_length=32, max_length=80)
    client_message_id: str = Field(
        alias="clientMessageId",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
    )
    body: str | None = Field(default=None, min_length=1, max_length=4000)
    attachment_id: str | None = Field(
        default=None,
        alias="attachmentId",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
    )

    @model_validator(mode="after")
    def require_content(self):
        if self.body is None and self.attachment_id is None:
            raise ValueError("body or attachmentId is required")
        return self


class CoreDeviceRevokeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    owner_password: str = Field(
        alias="ownerPassword", min_length=12, max_length=128
    )


class CoreDeviceRenameRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    display_name: str = Field(alias="displayName", min_length=1, max_length=120)


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class EmailCodeRequest(EmailRequest):
    code: str = Field(pattern=r"^[0-9]{8}$")


class PasswordResetRequest(EmailCodeRequest):
    model_config = ConfigDict(populate_by_name=True)

    new_password: str = Field(alias="newPassword", min_length=12, max_length=128)


class PromotionCodeRedeemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=128)


class MemberInvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["admin", "developer", "member", "child", "guest"]


class MemberChangeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: Literal["admin", "developer", "member", "child", "guest"] | None = None
    status: Literal["active", "suspended", "revoked"] | None = None
    owner_password: str | None = Field(
        default=None,
        alias="ownerPassword",
        min_length=12,
        max_length=128,
    )


class OrganizationPolicyChangeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    allowed_app_ids: list[str] | None = Field(alias="allowedAppIds", max_length=200)
    allowed_model_ids: list[str] | None = Field(alias="allowedModelIds", max_length=200)
    default_monthly_point_limit: str | None = Field(
        alias="defaultMonthlyPointLimit",
        pattern=r"^(0|[1-9][0-9]{0,18})$",
    )
    default_concurrency_limit: int = Field(
        alias="defaultConcurrencyLimit", ge=1, le=100
    )
    offline_grace_seconds: int = Field(alias="offlineGraceSeconds", ge=0, le=86400)
    owner_password: str = Field(
        alias="ownerPassword", min_length=12, max_length=128
    )


class MemberQuotaChangeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    allowed_model_ids: list[str] | None = Field(alias="allowedModelIds", max_length=200)
    monthly_point_limit: str | None = Field(
        alias="monthlyPointLimit",
        pattern=r"^(0|[1-9][0-9]{0,18})$",
    )
    concurrency_limit: int | None = Field(
        alias="concurrencyLimit", default=None, ge=1, le=100
    )
    owner_password: str = Field(
        alias="ownerPassword", min_length=12, max_length=128
    )


def _cloud_or_error(runtime_provider: PlatformRuntimeProvider):
    selected = _REQUEST_CLOUD.get()
    if selected is not None:
        return selected
    runtime = runtime_provider()
    cloud = None if runtime is None else getattr(runtime, "cloud", None)
    if cloud is None:
        return platform_error_response(
            status_code=503,
            code="cloud_client_not_ready",
            message="AI2Apps Cloud client is not ready.",
            retryable=True,
        )
    return cloud


def _apply_browser_cookie(response: Response) -> Response:
    pending = _PENDING_BROWSER_COOKIE.get()
    if pending is not None:
        cookie_name, value, secure = pending
        response.set_cookie(
            cookie_name,
            value,
            max_age=30 * 24 * 60 * 60,
            httponly=True,
            secure=secure,
            samesite="strict",
            path="/",
        )
    return response


def _forward_response(response: httpx.Response) -> Response:
    headers = {}
    content_type = response.headers.get("content-type")
    retry_after = response.headers.get("retry-after")
    if content_type:
        headers["content-type"] = content_type
    if retry_after:
        headers["retry-after"] = retry_after
    etag = response.headers.get("etag")
    if etag:
        headers["etag"] = etag
    return _apply_browser_cookie(
        Response(content=response.content, status_code=response.status_code, headers=headers)
    )


def _transport_error(error: httpx.HTTPError) -> JSONResponse:
    if isinstance(error, httpx.TimeoutException):
        response = platform_error_response(
            status_code=504,
            code="cloud_timeout",
            message="AI2Apps Cloud did not respond in time.",
            retryable=True,
        )
        return _apply_browser_cookie(response)
    response = platform_error_response(
        status_code=502,
        code="cloud_unavailable",
        message="AI2Apps Cloud is unavailable.",
        retryable=True,
    )
    return _apply_browser_cookie(response)


def _invitation_response_with_qr(response: Response) -> Response:
    if response.status_code >= 400:
        return response
    try:
        payload = json.loads(bytes(response.body))
        invite_url = str(payload["inviteUrl"])
        parsed_invite_url = urlsplit(invite_url)
        if (
            parsed_invite_url.scheme != "https"
            or not parsed_invite_url.netloc
            or parsed_invite_url.username is not None
            or parsed_invite_url.password is not None
            or parsed_invite_url.path != "/invitations/accept"
            or not parsed_invite_url.fragment
        ):
            raise ValueError("unexpected invitation URL")
        payload["inviteQrDataUrl"] = svg_qr_data_url(invite_url)
        return _apply_browser_cookie(
            JSONResponse(content=payload, status_code=response.status_code)
        )
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "invitation_response_invalid",
                "message": "Cloud returned an invalid invitation response",
            },
        ) from error


def create_cloud_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    async def select_browser_cloud(
        request: Request,
    ):
        enforce_same_origin_cookie_request(request)
        runtime = runtime_provider()
        cookie_name_resolver = (
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
            cookie_name_resolver()
            if cookie_name_resolver is not None
            else AI2APPS_CLOUD_BROWSER_COOKIE
        )
        browser_session_id = (
            cookie_reader(request.cookies)
            if cookie_reader is not None
            else request.cookies.get(AI2APPS_CLOUD_BROWSER_COOKIE)
        )
        resolver = (
            None if runtime is None else getattr(runtime, "cloud_for_browser", None)
        )
        created = not (
            browser_session_id is not None
            and _BROWSER_SESSION_ID.fullmatch(browser_session_id)
        )
        if created:
            browser_session_id = secrets.token_urlsafe(32)
        try:
            cloud = (
                resolver(browser_session_id)
                if resolver is not None
                else None if runtime is None else getattr(runtime, "cloud", None)
            )
        except (RuntimeError, ValueError) as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "cloud_client_not_ready",
                    "message": str(error),
                },
            ) from error
        cloud_token = _REQUEST_CLOUD.set(cloud)
        cookie_token = _PENDING_BROWSER_COOKIE.set(
            (
                cookie_name,
                browser_session_id,
                request.url.scheme == "https"
                or request.url.hostname not in {"127.0.0.1", "localhost", "::1"},
            )
            if created
            else None
        )
        try:
            yield
        finally:
            _PENDING_BROWSER_COOKIE.reset(cookie_token)
            _REQUEST_CLOUD.reset(cloud_token)

    router = APIRouter(
        prefix="/cloud",
        tags=["platform-cloud"],
        dependencies=[Depends(select_browser_cloud)],
    )
    principal_dependency = Depends(principal_provider)

    def require_core_account(
        principal: RequestPrincipal = principal_dependency,
    ) -> RequestPrincipal:
        if not principal.is_core:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "core_account_required",
                    "message": "Only the installation core account may manage Cloud account state",
                },
            )
        return principal

    core_account_only = [Depends(require_core_account)]

    def bound_installation(principal: RequestPrincipal):
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        if database is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "installation_identity_not_ready",
                    "message": "Local installation identity is not ready",
                },
            )
        from ai2apps.identity import IdentityRepository

        installation = IdentityRepository(database).get_installation()
        if (
            installation is None
            or installation.id != principal.installation_id
            or installation.core_user_id != principal.actor_user_id
        ):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "core_installation_required",
                    "message": "The bound installation core account is required",
                },
            )
        return installation

    async def refresh_local_access_projection() -> None:
        runtime = runtime_provider()
        remote = None if runtime is None else getattr(runtime, "remote", None)
        refresher = (
            None if remote is None else getattr(remote, "refresh_access_projection", None)
        )
        if refresher is None:
            return
        try:
            await refresher()
        except (RemoteAccessError, httpx.HTTPError):
            logger.warning(
                "Cloud member change succeeded but Local projection refresh failed",
                exc_info=True,
            )

    def request_repository() -> CloudAIRequestRepository | None:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        return None if database is None else CloudAIRequestRepository(database)

    def messager_repository() -> MessagerRepository | None:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        events = None if runtime is None else getattr(runtime, "events", None)
        return None if database is None else MessagerRepository(database, events)

    def begin_owned_request(
        principal: RequestPrincipal,
        *,
        idempotency_key: str,
        operation: str,
        model: Any,
    ) -> CloudAIRequestRepository | None:
        repository = request_repository()
        if repository is None:
            return None
        try:
            repository.begin(
                principal,
                idempotency_key=idempotency_key,
                operation=operation,
                model=str(model or ""),
            )
        except CloudRequestOwnershipError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "cloud_request_idempotency_conflict",
                    "message": str(error),
                },
            ) from error
        return repository

    def authorize_cloud_request(
        principal: RequestPrincipal,
        cloud_request_id: str,
        *,
        allow_core_override: bool,
    ):
        repository = request_repository()
        if repository is None:
            if allow_core_override and principal.is_core:
                return None, None
        else:
            record = repository.authorize(
                principal,
                cloud_request_id,
                allow_core_override=allow_core_override,
            )
            if record is not None:
                return repository, record
            if allow_core_override and principal.is_core and repository.get_by_cloud_request_id(
                cloud_request_id
            ) is None:
                # Preserve core cancellation for requests created before the ledger.
                return repository, None
        raise HTTPException(
            status_code=404,
            detail={
                "code": "cloud_request_not_found",
                "message": "Cloud model request was not found",
            },
        )

    def bind_response_identity(
        repository: CloudAIRequestRepository | None,
        idempotency_key: str,
        payload: Any,
        *,
        status: str,
    ) -> None:
        if repository is None or not isinstance(payload, dict):
            return
        request_id = payload.get("requestId")
        if isinstance(request_id, str) and request_id:
            repository.bind_cloud_request_id(
                idempotency_key,
                request_id,
                status=status,
            )

    def normalized_request_status(value: Any) -> str | None:
        status = str(value or "")
        if status == "canceled":
            status = "cancelled"
        if status in {
            "requested",
            "in_progress",
            "completed",
            "failed",
            "cancel_requested",
            "cancelled",
        }:
            return status
        return None

    class SSEOwnershipTracker:
        def __init__(
            self,
            repository: CloudAIRequestRepository | None,
            idempotency_key: str,
        ) -> None:
            self.repository = repository
            self.idempotency_key = idempotency_key
            self.buffer = b""

        def feed(self, chunk: bytes) -> None:
            if self.repository is None:
                return
            self.buffer += chunk
            normalized = self.buffer.replace(b"\r\n", b"\n")
            frames = normalized.split(b"\n\n")
            self.buffer = frames.pop()
            for frame in frames:
                event = "message"
                data_lines = []
                for line in frame.split(b"\n"):
                    if line.startswith(b"event:"):
                        event = line[6:].strip().decode("ascii", errors="ignore")
                    elif line.startswith(b"data:"):
                        data_lines.append(line[5:].strip())
                if not data_lines:
                    continue
                try:
                    payload = json.loads(b"\n".join(data_lines))
                except (TypeError, ValueError):
                    continue
                status = {
                    "response.created": "in_progress",
                    "response.completed": "completed",
                    "response.failed": "failed",
                    "response.cancelled": "cancelled",
                }.get(event)
                if status is None:
                    continue
                bind_response_identity(
                    self.repository,
                    self.idempotency_key,
                    payload,
                    status=status,
                )
                if not isinstance(payload, dict) or not payload.get("requestId"):
                    self.repository.set_status(self.idempotency_key, status)

    def trusted_ai_payload(payload: dict[str, Any]) -> dict[str, Any]:
        supplied = sorted(_RESERVED_IDENTITY_FIELDS.intersection(payload))
        if supplied:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "reserved_identity_field",
                    "message": "Model identity and billing fields are server-managed",
                    "fields": supplied,
                },
            )
        return payload

    def cloud_ai_headers(
        principal: RequestPrincipal,
        headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        result = dict(headers or {})
        if principal.authentication_type == "legacy_api_key":
            return result
        runtime = runtime_provider()
        resolver = (
            None
            if runtime is None
            else getattr(runtime, "cloud_ai_authorization_headers", None)
        )
        if resolver is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "cloud_device_auth_not_ready",
                    "message": "Cloud Device authorization is not ready",
                },
            )
        try:
            device_headers = resolver(principal)
        except (IdentityBindingError, RemoteAccessError) as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "cloud_device_auth_not_ready",
                    "message": str(error),
                },
            ) from error
        forbidden = {
            "authorization",
            "x-ai2apps-actor-user-id",
            "x-ai2apps-membership-epoch",
        }
        if forbidden.intersection(key.lower() for key in result):
            raise RuntimeError("Cloud Device identity headers are server-managed")
        result.update(device_headers)
        return result

    def audit_model_request(
        principal: RequestPrincipal,
        *,
        request_key: str,
        model: Any,
        operation: str,
    ) -> None:
        runtime = runtime_provider()
        events = None if runtime is None else getattr(runtime, "events", None)
        if events is None:
            return
        context = ModelInvocationContext.from_principal(
            principal,
            session_id=f"cloud-request:{request_key}",
        )
        events.append(
            event_type="cloud.model.invocation.requested",
            subject_id=request_key,
            trace_id=request_key,
            payload={
                **context.audit_payload(),
                "model": str(model or ""),
                "operation": operation,
            },
        )

    async def call(
        method: str,
        path: str,
        *,
        payload: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
        principal: RequestPrincipal | None = None,
    ) -> Response:
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            return cloud
        try:
            response = await cloud.request(
                method,
                path,
                json=payload,
                files=files,
                params=params,
                headers=(
                    cloud_ai_headers(principal, headers)
                    if principal is not None
                    else headers
                ),
            )
        except httpx.HTTPError as error:
            return _transport_error(error)
        try:
            return _forward_response(response)
        finally:
            await response.aclose()

    async def owner_grant(
        installation_id: str,
        *,
        purpose: str,
        password: str,
    ) -> str | Response:
        response = await call(
            "POST",
            "/v1/owner-reauth/grants",
            payload={
                "purpose": purpose,
                "resourceType": "installation",
                "resourceId": installation_id,
                "password": password,
            },
        )
        if response.status_code >= 400:
            return response
        try:
            payload = json.loads(bytes(response.body))
            grant = str(payload["grant"])
            if not grant:
                raise ValueError("empty grant")
            return grant
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "owner_reauth_invalid_response",
                    "message": "Cloud returned an invalid owner reauthentication response",
                },
            ) from error

    @router.post("/auth/register")
    async def register(request: RegisterRequest):
        return await call(
            "POST", "/v1/auth/register", payload=request.model_dump(by_alias=True)
        )

    @router.post("/auth/email/verify")
    async def verify_email(request: EmailCodeRequest):
        return await call("POST", "/v1/auth/email/verify", payload=request.model_dump())

    @router.post("/auth/email/resend")
    async def resend_email(request: EmailRequest):
        return await call("POST", "/v1/auth/email/resend", payload=request.model_dump())

    @router.post("/auth/login")
    async def login(request: LoginRequest):
        return await call("POST", "/v1/auth/login", payload=request.model_dump())

    @router.post("/auth/logout", dependencies=core_account_only)
    async def logout():
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            return cloud
        response = await call("POST", "/v1/auth/logout")
        # Local logout is authoritative for this client. Even if Cloud cannot
        # invalidate the server-side session, never retain its local cookie.
        await cloud.clear_session()
        return response

    @router.get("/auth/me", dependencies=core_account_only)
    async def auth_me():
        return await call("GET", "/v1/auth/me")

    @router.get("/profile", dependencies=core_account_only)
    async def get_profile():
        return await call("GET", "/v1/profile")

    @router.patch("/profile", dependencies=core_account_only)
    async def update_profile(request: UserProfilePatchRequest):
        payload = request.model_dump(
            by_alias=True,
            exclude_unset=True,
        )
        if not payload:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "profile_patch_empty",
                    "message": "At least one profile field is required",
                },
            )
        return await call("PATCH", "/v1/profile", payload=payload)

    @router.put("/profile/primary-device", dependencies=core_account_only)
    async def set_profile_primary_device(request: PrimaryProfileDeviceRequest):
        return await call(
            "PUT",
            "/v1/profile/primary-device",
            payload=request.model_dump(by_alias=True),
        )

    @router.get("/profile/social-link-platforms", dependencies=core_account_only)
    async def profile_social_link_platforms():
        return await call("GET", "/v1/profile/social-link-platforms")

    @router.put(
        "/profile/social-links/{platform}", dependencies=core_account_only
    )
    async def put_profile_social_link(
        request: ProfileSocialLinkRequest,
        platform: ProfileSocialPlatform,
    ):
        payload = request.model_dump(exclude_unset=True)
        if not payload or not any(value for value in payload.values()):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "profile_social_link_empty",
                    "message": "A social handle or URL is required",
                },
            )
        return await call(
            "PUT",
            f"/v1/profile/social-links/{platform}",
            payload=payload,
        )

    @router.delete(
        "/profile/social-links/{platform}", dependencies=core_account_only
    )
    async def delete_profile_social_link(platform: ProfileSocialPlatform):
        return await call("DELETE", f"/v1/profile/social-links/{platform}")

    @router.post("/public/profiles/lookup", dependencies=core_account_only)
    async def lookup_public_profile(request: PublicProfileLookupRequest):
        return await call(
            "POST",
            "/v1/public/profiles/lookup",
            payload=request.model_dump(),
        )

    @router.get(
        "/social/relationships/{user_id}", dependencies=core_account_only
    )
    async def social_relationship(
        user_id: str = Path(min_length=32, max_length=80),
    ):
        return await call("GET", f"/v1/social/relationships/{user_id}")

    @router.get("/social/friends", dependencies=core_account_only)
    async def social_friends(
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=2048),
    ):
        return await call(
            "GET",
            "/v1/social/friends",
            params={"limit": limit, **({"cursor": cursor} if cursor else {})},
        )

    @router.get("/social/friend-requests", dependencies=core_account_only)
    async def social_friend_requests(
        direction: Literal["incoming", "outgoing"] = Query(),
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=2048),
    ):
        return await call(
            "GET",
            "/v1/social/friend-requests",
            params={
                "direction": direction,
                "limit": limit,
                **({"cursor": cursor} if cursor else {}),
            },
        )

    @router.post(
        "/social/friend-requests/{user_id}", dependencies=core_account_only
    )
    async def create_social_friend_request(
        user_id: str = Path(min_length=32, max_length=80),
    ):
        return await call("POST", f"/v1/social/friend-requests/{user_id}")

    @router.post(
        "/social/friend-requests/{request_id}/{action}",
        dependencies=core_account_only,
    )
    async def act_on_social_friend_request(
        request_id: str = Path(min_length=1, max_length=80),
        action: Literal["accept", "reject", "cancel"] = Path(),
    ):
        return await call(
            "POST", f"/v1/social/friend-requests/{request_id}/{action}"
        )

    @router.get("/system-messages/unread-count", dependencies=core_account_only)
    async def system_message_unread_count():
        return await call("GET", "/v1/system-messages/unread-count")

    @router.get("/system-messages", dependencies=core_account_only)
    async def system_messages(
        state: Literal["all", "unread"] = Query(default="all"),
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = Query(default=None, max_length=2048),
        principal: RequestPrincipal = principal_dependency,
    ):
        response = await call(
            "GET",
            "/v1/system-messages",
            params={
                "state": state,
                "limit": limit,
                **({"cursor": cursor} if cursor else {}),
            },
        )
        if response.status_code < 400:
            try:
                payload = json.loads(bytes(response.body))
                selected = messager_repository()
                if selected is not None:
                    for item in payload.get("items", []):
                        if isinstance(item, dict):
                            selected.ingest_cloud_message(principal.actor_user_id, item)
            except (AttributeError, TypeError, ValueError):
                logger.warning(
                    "Cloud returned an invalid System Message page",
                    exc_info=True,
                )
        return response

    @router.post(
        "/system-messages/{message_id}/{action}", dependencies=core_account_only
    )
    async def update_system_message(
        message_id: str = Path(min_length=1, max_length=80),
        action: Literal["read", "archive"] = Path(),
    ):
        return await call("POST", f"/v1/system-messages/{message_id}/{action}")

    @router.post("/system-messages/read-all", dependencies=core_account_only)
    async def read_all_system_messages():
        return await call("POST", "/v1/system-messages/read-all")

    @router.post("/system-messages/offline", dependencies=core_account_only)
    async def send_offline_message(
        request: OfflineMessageRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = messager_repository()
        if selected is not None:
            try:
                selected.validate_cloud_outgoing(
                    owner_user_id=principal.actor_user_id,
                    peer_user_id=request.recipient_user_id,
                    client_message_id=request.client_message_id,
                    body=request.body or "",
                    attachment_id=request.attachment_id,
                )
            except MessagerIdempotencyConflictError as error:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "messager_idempotency_conflict",
                        "message": str(error),
                    },
                ) from error
        response = await call(
            "POST",
            "/v1/system-messages/offline",
            payload=request.model_dump(by_alias=True, exclude_none=True),
        )
        if response.status_code < 400:
            message_payload: dict[str, Any] = {}
            try:
                decoded = json.loads(bytes(response.body))
                if isinstance(decoded, dict):
                    message_payload = decoded
            except (TypeError, ValueError):
                logger.warning(
                    "Cloud returned an invalid offline message",
                    exc_info=True,
                )
            if selected is not None:
                selected.record_cloud_outgoing(
                    owner_user_id=principal.actor_user_id,
                    peer_user_id=request.recipient_user_id,
                    client_message_id=request.client_message_id,
                    body=request.body or "",
                    remote_message_id=(
                        str(message_payload["id"])
                        if message_payload.get("id")
                        else None
                    ),
                    attachment=(
                        message_payload.get("attachment")
                        if isinstance(message_payload.get("attachment"), dict)
                        else None
                    ),
                    created_at=(
                        str(message_payload["createdAt"])
                        if message_payload.get("createdAt")
                        else None
                    ),
                )
            runtime = runtime_provider()
            events = None if runtime is None else getattr(runtime, "events", None)
            if events is not None:
                events.append(
                    event_type="messager.cloud_offline.sent",
                    subject_id=request.client_message_id,
                    trace_id=request.client_message_id,
                    payload={
                        "actor_user_id": principal.actor_user_id,
                        "installation_id": principal.installation_id,
                        "recipient_user_id": request.recipient_user_id,
                        "client_message_id": request.client_message_id,
                        "transport": "cloud_offline",
                    },
                )
        return response

    @router.post(
        "/system-message-attachments",
        dependencies=core_account_only,
    )
    async def upload_system_message_attachment(
        file: Annotated[UploadFile, File()],
    ):
        content = await file.read(2 * 1024 * 1024 + 1)
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "system_message_attachment_too_large",
                    "message": "Attachment exceeds 2 MiB",
                },
            )
        return await call(
            "POST",
            "/v1/system-message-attachments",
            files={
                "file": (
                    file.filename or "attachment",
                    content,
                    file.content_type or "application/octet-stream",
                )
            },
        )

    @router.get(
        "/system-message-attachments/{attachment_id}/content",
        dependencies=core_account_only,
    )
    async def system_message_attachment_content(
        attachment_id: str = Path(
            pattern=r"^[0-9a-fA-F-]{36}$",
        ),
    ):
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            return cloud
        try:
            response = await cloud.request(
                "GET",
                f"/v1/system-message-attachments/{attachment_id}/content",
                stream=True,
            )
        except httpx.HTTPError as error:
            return _transport_error(error)
        if response.status_code >= 400:
            try:
                await response.aread()
                return _forward_response(response)
            finally:
                await response.aclose()

        try:
            media_type = response.headers.get("content-type", "").split(";", 1)[0]
            if media_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "attachment_response_invalid",
                        "message": "Cloud returned an invalid attachment media type",
                    },
                )
            chunks: list[bytes] = []
            byte_size = 0
            async for chunk in response.aiter_bytes():
                byte_size += len(chunk)
                if byte_size > 2 * 1024 * 1024:
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "code": "attachment_response_invalid",
                            "message": "Cloud attachment exceeded the size limit",
                        },
                    )
                chunks.append(chunk)
        finally:
            await response.aclose()
        return _apply_browser_cookie(
            Response(
                content=b"".join(chunks),
                status_code=response.status_code,
                media_type=media_type,
                headers={
                    "Cache-Control": "private, no-store",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "default-src 'none'; sandbox",
                },
            )
        )

    @router.post("/admin/reauth", dependencies=core_account_only)
    async def admin_reauth(request: AdminReauthRequest):
        return await call(
            "POST", "/v1/admin/reauth", payload=request.model_dump(by_alias=True)
        )

    @router.post("/auth/password/reset-request")
    async def request_password_reset(request: EmailRequest):
        return await call(
            "POST", "/v1/auth/password/reset-request", payload=request.model_dump()
        )

    @router.post("/auth/password/reset")
    async def reset_password(request: PasswordResetRequest):
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            return cloud
        response = await call(
            "POST",
            "/v1/auth/password/reset",
            payload=request.model_dump(by_alias=True),
        )
        if response.status_code < 400:
            await cloud.clear_session()
        return response

    @router.get("/levels", dependencies=core_account_only)
    async def levels():
        return await call("GET", "/v1/levels")

    @router.get("/capacity-policy", dependencies=core_account_only)
    async def capacity_policy():
        """Return the Local compatibility table for Cloud capacity rollout."""

        return capacity_policy_payload()

    @router.get("/account/devices", dependencies=core_account_only)
    async def account_devices():
        """List every Cloud device owned by the signed-in Core account."""

        return await call("GET", "/v1/remote/devices")

    @router.patch(
        "/account/devices/{device_id}", dependencies=core_account_only
    )
    async def rename_account_device(
        request: CoreDeviceRenameRequest,
        device_id: str = Path(min_length=32, max_length=80),
    ):
        response = await call(
            "PATCH",
            f"/v1/remote/devices/{device_id}",
            payload=request.model_dump(by_alias=True),
        )
        if response.status_code < 400:
            try:
                device = json.loads(bytes(response.body))
                runtime = runtime_provider()
                remote = None if runtime is None else getattr(runtime, "remote", None)
                if remote is not None and remote.repository.get(device_id) is not None:
                    remote.repository.update_cloud_state(device)
            except (TypeError, ValueError):
                logger.warning(
                    "Cloud renamed the device but returned an invalid projection",
                    exc_info=True,
                )
        return response

    @router.post(
        "/account/devices/{device_id}/revoke", dependencies=core_account_only
    )
    async def revoke_account_device(
        request: CoreDeviceRevokeRequest,
        device_id: str = Path(min_length=32, max_length=80),
    ):
        installations_response = await call("GET", "/v1/installations")
        if installations_response.status_code >= 400:
            return installations_response
        try:
            installations_payload = json.loads(bytes(installations_response.body))
            installation = next(
                item
                for item in installations_payload.get("items", [])
                if item.get("cloudDeviceId") == device_id
                and item.get("role") in {"core", "owner"}
            )
            installation_id = str(installation["installationId"])
        except (AttributeError, KeyError, StopIteration, TypeError, ValueError):
            return platform_error_response(
                status_code=404,
                code="core_device_not_found",
                message="That device is not owned by the current Core account.",
                retryable=False,
            )

        grant = await owner_grant(
            installation_id,
            purpose="installation.revoke",
            password=request.owner_password,
        )
        if isinstance(grant, Response):
            return grant
        response = await call(
            "POST",
            f"/v1/remote/devices/{device_id}/revoke",
            headers={"X-Owner-Reauth-Grant": grant},
        )
        if response.status_code < 400:
            runtime = runtime_provider()
            remote = None if runtime is None else getattr(runtime, "remote", None)
            cloud = _REQUEST_CLOUD.get()
            if remote is not None and remote.repository.get(device_id) is not None:
                try:
                    await remote.stop(device_id)
                    if remote.identity_repository is not None:
                        remote.identity_repository.deactivate_installation("revoked")
                    if cloud is not None:
                        await remote.reconcile(cloud=cloud)
                except (RemoteAccessError, httpx.HTTPError):
                    logger.warning(
                        "Cloud revoked the current device but Local cleanup failed",
                        exc_info=True,
                    )
        return response

    @router.get("/points", dependencies=core_account_only)
    async def points():
        return await call("GET", "/v1/points")

    @router.get("/points/ledger", dependencies=core_account_only)
    async def point_ledger(limit: int = Query(default=50, ge=1, le=100)):
        return await call("GET", "/v1/points/ledger", params={"limit": limit})

    @router.post("/points/daily-claim", dependencies=core_account_only)
    async def daily_claim():
        return await call("POST", "/v1/points/daily-claim")

    @router.post("/promotion-codes/redeem", dependencies=core_account_only)
    async def redeem_promotion_code(
        request: PromotionCodeRedeemRequest,
        idempotency_key: str = Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=160,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ):
        return await call(
            "POST",
            "/v1/promotion-codes/redeem",
            payload=request.model_dump(),
            headers={"Idempotency-Key": idempotency_key},
        )

    @router.get("/currency/assets", dependencies=core_account_only)
    async def currency_assets():
        return await call("GET", "/v1/currency/assets")

    @router.get("/currency/balances", dependencies=core_account_only)
    async def currency_balances():
        return await call("GET", "/v1/currency/balances")

    @router.get("/currency/provider-balances", dependencies=core_account_only)
    async def provider_currency_balances():
        return await call("GET", "/v1/currency/provider-balances")

    @router.get("/currency/ledger", dependencies=core_account_only)
    async def currency_ledger(limit: int = Query(default=50, ge=1, le=100)):
        return await call("GET", "/v1/currency/ledger", params={"limit": limit})

    @router.get("/account/entitlements", dependencies=core_account_only)
    async def entitlements():
        return await call("GET", "/v1/account/entitlements")

    @router.get("/installation", dependencies=core_account_only)
    async def installation_detail(
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        return await call("GET", f"/v1/installations/{installation.id}")

    @router.get("/installation/members", dependencies=core_account_only)
    async def installation_members(
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        return await call(
            "GET", f"/v1/installations/{installation.id}/members"
        )

    @router.get("/installation/invitations", dependencies=core_account_only)
    async def installation_invitations(
        status: Literal["pending", "accepted", "rejected", "cancelled", "expired"]
        | None = Query(default=None),
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        return await call(
            "GET",
            f"/v1/installations/{installation.id}/invitations",
            params={"status": status} if status is not None else None,
        )

    @router.post("/installation/invitations", dependencies=core_account_only)
    async def invite_installation_member(
        request: MemberInvitationRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        response = await call(
            "POST",
            f"/v1/installations/{installation.id}/invitations",
            payload=request.model_dump(),
        )
        return _invitation_response_with_qr(response)

    @router.post(
        "/installation/invitations/{invitation_id}/resend",
        dependencies=core_account_only,
    )
    async def resend_installation_invitation(
        invitation_id: str = Path(min_length=1, max_length=80),
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        response = await call(
            "POST",
            f"/v1/installations/{installation.id}/invitations/{invitation_id}/resend",
        )
        return _invitation_response_with_qr(response)

    @router.post(
        "/installation/invitations/{invitation_id}/cancel",
        dependencies=core_account_only,
    )
    async def cancel_installation_invitation(
        invitation_id: str = Path(min_length=1, max_length=80),
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        return await call(
            "POST",
            f"/v1/installations/{installation.id}/invitations/{invitation_id}/cancel",
        )

    @router.patch(
        "/installation/members/{user_id}", dependencies=core_account_only
    )
    async def change_installation_member(
        request: MemberChangeRequest,
        user_id: str = Path(min_length=1, max_length=80),
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        if request.role is None and request.status is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "member_change_required",
                    "message": "A role or status change is required",
                },
            )
        headers = None
        if request.role is not None:
            if request.owner_password is None:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "owner_reauth_required",
                        "message": "Owner password is required for role changes",
                    },
                )
            grant = await owner_grant(
                installation.id,
                purpose="organization.member.role_change",
                password=request.owner_password,
            )
            if isinstance(grant, Response):
                return grant
            headers = {"X-Owner-Reauth-Grant": grant}
        response = await call(
            "PATCH",
            f"/v1/installations/{installation.id}/members/{user_id}",
            payload={
                **({"role": request.role} if request.role is not None else {}),
                **({"status": request.status} if request.status is not None else {}),
            },
            headers=headers,
        )
        if response.status_code < 400:
            await refresh_local_access_projection()
        return response

    @router.get("/installation/policy", dependencies=core_account_only)
    async def installation_policy(
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        return await call("GET", f"/v1/installations/{installation.id}/policy")

    @router.patch("/installation/policy", dependencies=core_account_only)
    async def change_installation_policy(
        request: OrganizationPolicyChangeRequest,
        principal: RequestPrincipal = principal_dependency,
        if_match: str = Header(
            alias="If-Match", pattern=r'^"policy-[1-9][0-9]*"$'
        ),
    ):
        installation = bound_installation(principal)
        grant = await owner_grant(
            installation.id,
            purpose="organization.policy.change",
            password=request.owner_password,
        )
        if isinstance(grant, Response):
            return grant
        payload = request.model_dump(by_alias=True, exclude={"owner_password"})
        response = await call(
            "PATCH",
            f"/v1/installations/{installation.id}/policy",
            payload=payload,
            headers={
                "If-Match": if_match,
                "X-Owner-Reauth-Grant": grant,
            },
        )
        if response.status_code < 400:
            await refresh_local_access_projection()
        return response

    @router.get(
        "/installation/members/{user_id}/quota", dependencies=core_account_only
    )
    async def installation_member_quota(
        user_id: str = Path(min_length=1, max_length=80),
        principal: RequestPrincipal = principal_dependency,
    ):
        installation = bound_installation(principal)
        return await call(
            "GET",
            f"/v1/installations/{installation.id}/members/{user_id}/quota",
        )

    @router.patch(
        "/installation/members/{user_id}/quota", dependencies=core_account_only
    )
    async def change_installation_member_quota(
        request: MemberQuotaChangeRequest,
        user_id: str = Path(min_length=1, max_length=80),
        principal: RequestPrincipal = principal_dependency,
        if_match: str = Header(
            alias="If-Match", pattern=r'^"policy-[1-9][0-9]*"$'
        ),
    ):
        installation = bound_installation(principal)
        grant = await owner_grant(
            installation.id,
            purpose="organization.member.quota_change",
            password=request.owner_password,
        )
        if isinstance(grant, Response):
            return grant
        payload = request.model_dump(by_alias=True, exclude={"owner_password"})
        response = await call(
            "PATCH",
            f"/v1/installations/{installation.id}/members/{user_id}/quota",
            payload=payload,
            headers={
                "If-Match": if_match,
                "X-Owner-Reauth-Grant": grant,
            },
        )
        if response.status_code < 400:
            await refresh_local_access_projection()
        return response

    @router.get("/ai/models")
    async def ai_models(principal: RequestPrincipal = principal_dependency):
        return await call("GET", "/v1/ai/models", principal=principal)

    @router.post("/ai/responses")
    async def ai_response(
        payload: dict[str, Any],
        principal: RequestPrincipal = principal_dependency,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=160
        ),
    ):
        payload = trusted_ai_payload(payload)
        repository = begin_owned_request(
            principal,
            idempotency_key=idempotency_key,
            operation="responses",
            model=payload.get("model"),
        )
        audit_model_request(
            principal,
            request_key=idempotency_key,
            model=payload.get("model"),
            operation="responses",
        )
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            if repository is not None:
                repository.set_status(idempotency_key, "failed")
            return cloud
        wants_stream = payload.get("stream", True) is not False
        try:
            response = await cloud.request(
                "POST",
                "/v1/ai/responses",
                json=payload,
                headers=cloud_ai_headers(
                    principal, {"Idempotency-Key": idempotency_key}
                ),
                stream=wants_stream,
            )
        except httpx.HTTPError as error:
            if repository is not None:
                repository.set_status(idempotency_key, "failed")
            return _transport_error(error)
        if not wants_stream or response.status_code >= 400:
            try:
                await response.aread()
                if repository is not None:
                    if response.status_code >= 400:
                        repository.set_status(idempotency_key, "failed")
                    else:
                        try:
                            response_payload = response.json()
                        except ValueError:
                            response_payload = None
                        bind_response_identity(
                            repository,
                            idempotency_key,
                            response_payload,
                            status="completed",
                        )
                        repository.set_status(idempotency_key, "completed")
                return _forward_response(response)
            finally:
                await response.aclose()

        tracker = SSEOwnershipTracker(repository, idempotency_key)

        async def body():
            try:
                async for chunk in response.aiter_bytes():
                    tracker.feed(chunk)
                    yield chunk
            finally:
                await response.aclose()

        return _apply_browser_cookie(StreamingResponse(
            body(),
            status_code=response.status_code,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        ))

    async def ai_image(
        endpoint: str,
        payload: dict[str, Any],
        idempotency_key: str,
        principal: RequestPrincipal,
    ) -> Response:
        """Forward synchronous image calls without retaining image Data URLs."""

        payload = trusted_ai_payload(payload)
        operation = f"images.{endpoint}"
        repository = begin_owned_request(
            principal,
            idempotency_key=idempotency_key,
            operation=operation,
            model=payload.get("model"),
        )
        audit_model_request(
            principal,
            request_key=idempotency_key,
            model=payload.get("model"),
            operation=operation,
        )
        response = await call(
            "POST",
            f"/v1/ai/images/{endpoint}",
            payload=payload,
            headers={"Idempotency-Key": idempotency_key},
            principal=principal,
        )
        if repository is not None:
            if response.status_code >= 400:
                repository.set_status(idempotency_key, "failed")
            else:
                try:
                    response_payload = json.loads(bytes(response.body))
                except (TypeError, ValueError):
                    response_payload = None
                bind_response_identity(
                    repository,
                    idempotency_key,
                    response_payload,
                    status="completed",
                )
                repository.set_status(idempotency_key, "completed")
        return response

    @router.post("/ai/images/generations")
    async def ai_image_generation(
        payload: dict[str, Any],
        principal: RequestPrincipal = principal_dependency,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=160
        ),
    ):
        return await ai_image("generations", payload, idempotency_key, principal)

    @router.post("/ai/images/edits")
    async def ai_image_edit(
        payload: dict[str, Any],
        principal: RequestPrincipal = principal_dependency,
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=160
        ),
    ):
        return await ai_image("edits", payload, idempotency_key, principal)

    @router.get("/ai/requests/{request_id}")
    async def ai_request(
        request_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        repository, record = authorize_cloud_request(
            principal,
            request_id,
            allow_core_override=False,
        )
        response = await call(
            "GET", f"/v1/ai/requests/{request_id}", principal=principal
        )
        if repository is not None and record is not None and response.status_code < 400:
            try:
                result = json.loads(bytes(response.body))
            except (TypeError, ValueError):
                result = None
            if isinstance(result, dict):
                status = normalized_request_status(result.get("status"))
                if status is not None:
                    repository.set_status(record.idempotency_key, status)
        return response

    @router.post("/ai/requests/{request_id}/cancel")
    async def cancel_ai_request(
        request_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        repository, record = authorize_cloud_request(
            principal,
            request_id,
            allow_core_override=True,
        )
        response = await call(
            "POST", f"/v1/ai/requests/{request_id}/cancel", principal=principal
        )
        if repository is not None and record is not None and response.status_code < 400:
            try:
                result = json.loads(bytes(response.body))
            except (TypeError, ValueError):
                result = None
            status = (
                normalized_request_status(result.get("status"))
                if isinstance(result, dict)
                else None
            )
            repository.set_status(
                record.idempotency_key,
                status or "cancel_requested",
            )
        return response

    return router
