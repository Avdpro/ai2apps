"""Local native-network facade for the AI2Apps Cloud v1 API."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider


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


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class EmailCodeRequest(EmailRequest):
    code: str = Field(pattern=r"^[0-9]{8}$")


class PasswordResetRequest(EmailCodeRequest):
    model_config = ConfigDict(populate_by_name=True)

    new_password: str = Field(alias="newPassword", min_length=12, max_length=128)


def _cloud_or_error(runtime_provider: PlatformRuntimeProvider):
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


def _forward_response(response: httpx.Response) -> Response:
    headers = {}
    content_type = response.headers.get("content-type")
    retry_after = response.headers.get("retry-after")
    if content_type:
        headers["content-type"] = content_type
    if retry_after:
        headers["retry-after"] = retry_after
    return Response(content=response.content, status_code=response.status_code, headers=headers)


def _transport_error(error: httpx.HTTPError) -> JSONResponse:
    if isinstance(error, httpx.TimeoutException):
        return platform_error_response(
            status_code=504,
            code="cloud_timeout",
            message="AI2Apps Cloud did not respond in time.",
            retryable=True,
        )
    return platform_error_response(
        status_code=502,
        code="cloud_unavailable",
        message="AI2Apps Cloud is unavailable.",
        retryable=True,
    )


def create_cloud_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter(prefix="/cloud", tags=["platform-cloud"])

    async def call(
        method: str,
        path: str,
        *,
        payload: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            return cloud
        try:
            response = await cloud.request(
                method, path, json=payload, params=params, headers=headers
            )
        except httpx.HTTPError as error:
            return _transport_error(error)
        try:
            return _forward_response(response)
        finally:
            await response.aclose()

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

    @router.post("/auth/logout")
    async def logout():
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            return cloud
        response = await call("POST", "/v1/auth/logout")
        if response.status_code < 400:
            await cloud.clear_session()
        return response

    @router.get("/auth/me")
    async def auth_me():
        return await call("GET", "/v1/auth/me")

    @router.post("/admin/reauth")
    async def admin_reauth(request: AdminReauthRequest):
        return await call(
            "POST", "/v1/admin/reauth", payload=request.model_dump()
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

    @router.get("/levels")
    async def levels():
        return await call("GET", "/v1/levels")

    @router.get("/points")
    async def points():
        return await call("GET", "/v1/points")

    @router.get("/points/ledger")
    async def point_ledger(limit: int = Query(default=50, ge=1, le=100)):
        return await call("GET", "/v1/points/ledger", params={"limit": limit})

    @router.post("/points/daily-claim")
    async def daily_claim():
        return await call("POST", "/v1/points/daily-claim")

    @router.get("/account/entitlements")
    async def entitlements():
        return await call("GET", "/v1/account/entitlements")

    @router.get("/ai/models")
    async def ai_models():
        return await call("GET", "/v1/ai/models")

    @router.post("/ai/responses")
    async def ai_response(
        payload: dict[str, Any],
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=160
        ),
    ):
        cloud = _cloud_or_error(runtime_provider)
        if isinstance(cloud, JSONResponse):
            return cloud
        wants_stream = payload.get("stream", True) is not False
        try:
            response = await cloud.request(
                "POST",
                "/v1/ai/responses",
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
                stream=wants_stream,
            )
        except httpx.HTTPError as error:
            return _transport_error(error)
        if not wants_stream or response.status_code >= 400:
            try:
                await response.aread()
                return _forward_response(response)
            finally:
                await response.aclose()

        async def body():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()

        return StreamingResponse(
            body(),
            status_code=response.status_code,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def ai_image(
        endpoint: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> Response:
        """Forward synchronous image calls without retaining image Data URLs."""

        return await call(
            "POST",
            f"/v1/ai/images/{endpoint}",
            payload=payload,
            headers={"Idempotency-Key": idempotency_key},
        )

    @router.post("/ai/images/generations")
    async def ai_image_generation(
        payload: dict[str, Any],
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=160
        ),
    ):
        return await ai_image("generations", payload, idempotency_key)

    @router.post("/ai/images/edits")
    async def ai_image_edit(
        payload: dict[str, Any],
        idempotency_key: str = Header(
            alias="Idempotency-Key", min_length=8, max_length=160
        ),
    ):
        return await ai_image("edits", payload, idempotency_key)

    @router.get("/ai/requests/{request_id}")
    async def ai_request(request_id: str):
        return await call("GET", f"/v1/ai/requests/{request_id}")

    @router.post("/ai/requests/{request_id}/cancel")
    async def cancel_ai_request(request_id: str):
        return await call("POST", f"/v1/ai/requests/{request_id}/cancel")

    return router
