"""User-only control handoff endpoints for the managed browser."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.browser import BrowserError
from ai2apps.browser.shell_bidi_gateway import (
    ShellBiDiGatewayError,
    issue_shell_bidi_ticket,
    serve_shell_bidi_gateway,
)
from ai2apps.identity import RequestPrincipal


def create_browser_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter()

    def manager_or_error():
        runtime = runtime_provider()
        if runtime is None or runtime.browser is None:
            return platform_error_response(
                status_code=503,
                code="browser_unavailable",
                message="The managed browser runtime is unavailable.",
                retryable=True,
            )
        return runtime.browser

    def error_response(exc: BrowserError):
        return platform_error_response(
            status_code=409,
            code=exc.code,
            message=str(exc),
            retryable=False,
        )

    @router.get("/browser/status")
    async def browser_status():
        manager = manager_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        return await manager.get_status()

    @router.post("/browser/user-control/begin")
    async def begin_user_control():
        manager = manager_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.begin_user_control()
        except BrowserError as exc:
            return error_response(exc)

    @router.post("/browser/user-control/complete")
    async def complete_user_control():
        manager = manager_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return await manager.complete_user_control()
        except BrowserError as exc:
            return error_response(exc)

    @router.post("/browser/close")
    async def close_browser():
        manager = manager_or_error()
        if isinstance(manager, JSONResponse):
            return manager
        return await manager.close()

    @router.websocket("/browser/webdriver-bidi")
    async def shell_webdriver_bidi(websocket: WebSocket):
        """Expose the visible AceFox Shell through native WebDriver BiDi."""

        runtime = runtime_provider()
        if runtime is None:
            await websocket.close(code=1013, reason="Platform runtime unavailable")
            return
        await serve_shell_bidi_gateway(websocket, runtime)

    @router.post("/browser/webdriver-bidi/ticket")
    async def shell_webdriver_bidi_ticket(request: Request):
        """Issue a one-use ticket to an authenticated first-party Mini-Entry."""

        principal = getattr(request.state, "ai2apps_principal", None)
        if not isinstance(principal, RequestPrincipal):
            raise HTTPException(status_code=401, detail="Local Session required")
        try:
            ticket = issue_shell_bidi_ticket(principal)
        except ShellBiDiGatewayError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"ticket": ticket, "expires_in_seconds": 30}

    return router
