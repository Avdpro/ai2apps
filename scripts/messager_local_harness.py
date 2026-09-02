"""Run one inference-free Local instance for Messager integration testing."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ai2apps.api import create_ai2apps_router
from ai2apps.api.messager_peer import create_messager_peer_ingress_router
from ai2apps.config import PlatformConfig
from ai2apps.http_security import LocalBrowserSecurityHeadersMiddleware
from ai2apps.identity import RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime
from omlx.admin.routes import static_dir, templates

PUBLIC_BOOTSTRAP_ROUTES = frozenset(
    {
        ("GET", "/v1/platform/health"),
        ("GET", "/v1/platform/client/bootstrap"),
        ("POST", "/v1/platform/client/shell-session"),
        ("GET", "/v1/platform/client/shell"),
        ("POST", "/v1/platform/cloud/auth/register"),
        ("POST", "/v1/platform/cloud/auth/email/verify"),
        ("POST", "/v1/platform/cloud/auth/email/resend"),
        ("POST", "/v1/platform/cloud/auth/login"),
        ("POST", "/v1/platform/cloud/auth/password/reset-request"),
        ("POST", "/v1/platform/cloud/auth/password/reset"),
        ("POST", "/v1/platform/auth/handoff/exchange"),
        ("POST", "/v1/platform/auth/cloud-member/activate"),
        ("POST", "/v1/platform/auth/core/bootstrap"),
    }
)


def create_harness(base_path: Path) -> FastAPI:
    runtime = PlatformRuntime(PlatformConfig.from_base_path(base_path))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        runtime.start()
        await runtime.start_background_tasks()
        try:
            yield
        finally:
            await runtime.stop_background_tasks()
            runtime.stop()

    app = FastAPI(title="AI2Apps Messager Local Harness", lifespan=lifespan)
    app.add_middleware(LocalBrowserSecurityHeadersMiddleware)

    async def verify_platform_access(request: Request):
        token = runtime.local_session_token_from_cookies(request.cookies)
        if token:
            principal = runtime.authorize_local_session(token)
            if principal is not None:
                request.state.ai2apps_principal = principal
                return principal
        # Account must be able to restore its private, SecretBackend-held Cloud
        # browser session before this disposable Installation has a Local
        # principal. Cloud remains the authorization boundary for these calls.
        if request.url.path.startswith("/v1/platform/cloud/"):
            return True
        if (request.method, request.url.path) in PUBLIC_BOOTSTRAP_ROUTES:
            return True
        raise HTTPException(
            status_code=401,
            detail={
                "code": "local_session_required",
                "message": "Sign in to this Local test Installation.",
            },
        )

    def harness_principal(request: Request) -> RequestPrincipal:
        principal = getattr(request.state, "ai2apps_principal", None)
        if isinstance(principal, RequestPrincipal):
            return principal
        # Only Cloud bootstrap/facade calls may arrive before a Local Session
        # exists. Once bound, real Local cookies always win above.
        if request.url.path.startswith("/v1/platform/cloud/"):
            return runtime.legacy_api_key_principal()
        raise HTTPException(
            status_code=401,
            detail={
                "code": "local_session_required",
                "message": "Sign in to this Local test Installation.",
            },
        )

    app.include_router(
        create_ai2apps_router(
            config_provider=lambda: runtime.config,
            runtime_provider=lambda: runtime,
            principal_provider=harness_principal,
        ),
        dependencies=[Depends(verify_platform_access)],
    )
    app.include_router(create_messager_peer_ingress_router(lambda: runtime))
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.mount("/admin/static", StaticFiles(directory=static_dir), name="admin-static")

    @app.get("/")
    async def account(request: Request):
        return templates.TemplateResponse(
            request,
            "system_apps/account.html",
            {"app_base_template": "base.html"},
        )

    @app.get("/setup")
    async def setup(request: Request):
        from ai2apps.identity import IdentityRepository

        installation_bound = IdentityRepository(runtime.database).get_installation() is not None
        return templates.TemplateResponse(
            request,
            "login.html",
            {"installation_bound": installation_bound},
        )

    @app.get("/admin/dashboard")
    async def dashboard_after_setup():
        return RedirectResponse(url="/", status_code=302)

    @app.get("/admin/api/account/ui-language")
    async def account_ui_language():
        return {"language": "en"}

    @app.get("/messager")
    async def messager(request: Request):
        return templates.TemplateResponse(
            request,
            "system_apps/messager.html",
            {"app_base_template": "base.html"},
        )

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    args.base_path.mkdir(parents=True, exist_ok=True)
    uvicorn.run(
        create_harness(args.base_path.resolve()),
        host="127.0.0.1",
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
