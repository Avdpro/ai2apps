"""Adversarial authorization checks for installation-wide control planes."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.router import create_ai2apps_router
from ai2apps.identity import MemberRole, RequestPrincipal

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _member() -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id="security-test-member",
        installation_id="security-test-installation",
        organization_id="security-test-organization",
        billing_account_id="security-test-billing",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    (
        "/v1/platform/packages/installed",
        "/v1/platform/capability-policies",
        "/v1/platform/remote/status",
        "/v1/platform/secrets",
        "/v1/platform/interactive-packages",
        "/v1/platform/safe-mode",
    ),
)
async def test_member_cannot_read_or_mutate_system_security_control_planes(path):
    runtime = SimpleNamespace()
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=_member,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(path)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "app_access_denied"


@pytest.mark.asyncio
async def test_platform_router_never_invents_core_authority_without_auth_state():
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(runtime_provider=lambda: SimpleNamespace())
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/platform/packages/installed")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "local_session_required"


def test_inference_api_keys_cannot_load_models_or_reveal_saved_sub_keys():
    """Keep these invariants testable without importing the Metal runtime."""

    source = (REPOSITORY_ROOT / "omlx/admin/routes.py").read_text(encoding="utf-8")
    load_route = source.split(
        '@router.post("/api/models/{model_id}/load")', 1
    )[1].split('@router.post("/api/reload")', 1)[0]
    assert "Depends(require_admin)" in load_route
    assert "_require_admin_or_bearer" not in source
    assert '"sub_keys": [_sub_key_view(sk)' in source

    server = (REPOSITORY_ROOT / "omlx/server.py").read_text(encoding="utf-8")
    platform_guard = server.split("async def verify_ai2apps_platform_access(", 1)[
        1
    ].split("def _reset_boundary_snapshots_for_server", 1)[0]
    assert "await verify_api_key" not in platform_guard
    assert "return principal" in platform_guard
    assert '"code": "local_session_required"' in platform_guard
    for route in (
        '@app.post("/v1/models/{model_id}/unload")',
        '@app.post("/v1/models/{model_id}/load")',
    ):
        model_admin = server.split(route, 1)[1].split("\n\n@app.", 1)[0]
        assert "Depends(verify_ai2apps_platform_access)" in model_admin
        assert "Depends(verify_api_key)" not in model_admin


def test_webui_does_not_receive_the_main_api_key_or_saved_sub_key_values():
    chat = (REPOSITORY_ROOT / "ai2apps/web/templates/chat.html").read_text(
        encoding="utf-8"
    )
    login = (REPOSITORY_ROOT / "ai2apps/web/templates/login.html").read_text(
        encoding="utf-8"
    )
    settings = (
        REPOSITORY_ROOT / "ai2apps/web/templates/dashboard/_settings.html"
    ).read_text(encoding="utf-8")

    assert "runtimeApiKey = '';" in chat
    assert "api_key | tojson" not in chat
    assert "Enter your API key" not in login
    assert "sk.key" not in settings
    assert "sk.fingerprint" in settings


def test_native_helper_never_puts_inference_key_in_browser_url():
    source = (
        REPOSITORY_ROOT
        / "apps/omlx-mac/Sources/Menubar/MenubarController.swift"
    ).read_text(encoding="utf-8")
    builder = source.split("static func webAdminURL", 1)[1].split(
        "static func shouldShowGenericFailureAlert", 1
    )[0]

    assert "apiKey" not in builder
    assert "/admin/auto-login" not in builder
    assert 'comps.path = "/admin"' in builder


def test_legacy_admin_cookie_and_inference_no_auth_cannot_bypass_core_login():
    source = (REPOSITORY_ROOT / "omlx/admin/auth.py").read_text(
        encoding="utf-8"
    )
    verifier = source.split("def verify_session(", 1)[1].split(
        "async def require_admin", 1
    )[0]
    guard = source.split("async def require_admin", 1)[1].split(
        "class _RedirectToLogin", 1
    )[0]

    assert "active_local_principal" in verifier
    assert "verify_session_token" not in verifier
    assert "skip_api_key_verification" not in guard

    routes = (REPOSITORY_ROOT / "omlx/admin/routes.py").read_text(
        encoding="utf-8"
    )
    login_routes = routes.split('@router.post("/api/login")', 1)[1].split(
        "# =============================================================================\n# Sub Key Management Routes",
        1,
    )[0]
    assert "api_key_web_login_retired" in login_routes
    assert "api_key_web_setup_retired" in login_routes
    assert "create_session_token" not in login_routes


def test_agent_process_and_package_sandboxes_do_not_allow_all_mach_services():
    process_policy = (
        REPOSITORY_ROOT / "ai2apps/processes/sandbox.py"
    ).read_text(encoding="utf-8")
    package_policy = (
        REPOSITORY_ROOT / "ai2apps/packages/supervisor.py"
    ).read_text(encoding="utf-8")

    assert '"(allow mach-lookup)"' not in process_policy
    assert '"(allow mach-lookup)"' not in package_policy
