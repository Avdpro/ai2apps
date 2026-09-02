"""Local member handoff and host-only Cookie API contracts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.auth import create_auth_router
from ai2apps.identity import (
    LOCAL_SESSION_COOKIE,
    MemberRole,
    RequestPrincipal,
    local_session_cookie_name,
)
from omlx.admin import auth as admin_auth


def _member() -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id="9df2aa2a-b029-4d10-a9e1-805db637e595",
        installation_id="b657d60d-2a38-4a66-bf21-20d7bb1bb13f",
        organization_id="c10c7a58-b338-4194-a6a2-693bf1d54c9e",
        billing_account_id="71c8e42b-f8a6-49f1-b618-76b9e20c0510",
        role=MemberRole.MEMBER,
        membership_epoch=4,
    )


def _member_cookie_name() -> str:
    return local_session_cookie_name(_member().installation_id)


def _core() -> RequestPrincipal:
    principal = _member()
    return RequestPrincipal(
        actor_user_id=principal.actor_user_id,
        installation_id=principal.installation_id,
        organization_id=principal.organization_id,
        billing_account_id=principal.billing_account_id,
        role=MemberRole.CORE,
        membership_epoch=principal.membership_epoch,
    )


def test_handoff_exchange_sets_host_only_http_only_cookie():
    captured = {}
    principal = _member()

    async def exchange(handoff):
        captured["handoff"] = handoff
        return "opaque-local-session", principal

    runtime = SimpleNamespace(exchange_member_handoff=exchange)
    app = FastAPI()
    app.include_router(create_auth_router(lambda: runtime), prefix="/v1/platform")
    client = TestClient(app)

    response = client.post(
        "/v1/platform/auth/handoff/exchange",
        json={"handoff": "one-use-cloud-member-handoff"},
    )

    assert response.status_code == 201
    assert captured["handoff"] == "one-use-cloud-member-handoff"
    assert response.json()["actorUserId"] == principal.actor_user_id
    cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{_member_cookie_name()}=opaque-local-session" in cookie
    assert f'{LOCAL_SESSION_COOKIE}=""' in cookie
    assert "omlx_admin_session=\"\"" in cookie
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie
    assert "Max-Age=15552000" in cookie
    assert "SameSite=strict" in cookie
    assert "Domain=" not in cookie


def test_auth_me_uses_authoritative_principal_and_logout_revokes_cookie():
    principal = _member()
    revoked = []
    runtime = SimpleNamespace(
        revoke_local_session=lambda token: revoked.append(token),
        local_session_cookie_name=_member_cookie_name,
    )
    app = FastAPI()
    app.include_router(
        create_auth_router(lambda: runtime, principal_provider=lambda: principal),
        prefix="/v1/platform",
    )
    client = TestClient(app)
    client.cookies.set(_member_cookie_name(), "member-session")

    me = client.get("/v1/platform/auth/me")
    logout = client.post("/v1/platform/auth/logout")

    assert me.status_code == 200
    assert me.json() == {
        "actorUserId": principal.actor_user_id,
        "installationId": principal.installation_id,
        "organizationId": principal.organization_id,
        "role": "member",
        "membershipEpoch": 4,
        "isCore": False,
        "authenticationType": "cloud_session",
    }
    assert logout.status_code == 204
    assert revoked == ["member-session"]


def test_desktop_session_refresh_rotates_cookie_without_cloud():
    principal = _member()
    captured = []
    runtime = SimpleNamespace(
        local_session_cookie_name=_member_cookie_name,
        local_session_token_from_cookies=lambda cookies: cookies.get(
            _member_cookie_name()
        ),
        refresh_local_session=lambda token: (
            captured.append(token) or ("rotated-session", principal, True)
        ),
    )
    app = FastAPI()
    app.include_router(
        create_auth_router(lambda: runtime, principal_provider=lambda: principal),
        prefix="/v1/platform",
    )
    client = TestClient(app)
    client.cookies.set(_member_cookie_name(), "member-session")

    response = client.post("/v1/platform/auth/session/refresh")

    assert response.status_code == 200
    assert response.json()["rotated"] is True
    assert captured == ["member-session"]
    cookie = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{_member_cookie_name()}=rotated-session" in cookie
    assert "Max-Age=15552000" in cookie
    assert "HttpOnly" in cookie


def test_cross_origin_logout_cannot_revoke_ambient_local_session():
    revoked = []
    runtime = SimpleNamespace(
        revoke_local_session=lambda token: revoked.append(token),
        local_session_cookie_name=_member_cookie_name,
    )
    app = FastAPI()
    app.include_router(create_auth_router(lambda: runtime), prefix="/v1/platform")
    client = TestClient(app)
    client.cookies.set(_member_cookie_name(), "member-session")

    response = client.post(
        "/v1/platform/auth/logout",
        headers={"Origin": "http://127.0.0.1:9000"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "csrf_origin_mismatch"
    assert revoked == []


def test_signed_in_cloud_member_is_activated_without_exposing_handoff():
    principal = _member()
    browser_cloud = object()

    async def activate(*, cloud):
        assert cloud is browser_cloud
        return "activated-member-session", principal

    runtime = SimpleNamespace(
        activate_current_cloud_member=activate,
        cloud=browser_cloud,
    )
    app = FastAPI()
    app.include_router(
        create_auth_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        ),
        prefix="/v1/platform",
    )
    client = TestClient(app)

    response = client.post("/v1/platform/auth/cloud-member/activate")

    assert response.status_code == 201
    assert response.json()["actorUserId"] == principal.actor_user_id
    assert "handoff" not in response.text.lower()
    cookies = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{_member_cookie_name()}=activated-member-session" in cookies
    assert "omlx_admin_session=\"\"" in cookies


def test_first_signed_in_cloud_account_can_explicitly_bootstrap_core():
    principal = _core()
    browser_cloud = object()
    captured = {}

    async def bootstrap(*, display_name, owner_password, cloud):
        captured.update(
            display_name=display_name,
            owner_password=owner_password,
            cloud=cloud,
        )
        return "new-core-session", principal

    runtime = SimpleNamespace(
        cloud_browser_cookie_name=lambda: "cloud_browser_instance_a",
        cloud_for_browser=lambda session_id: (
            browser_cloud if session_id == "signed-in-cloud-session" else None
        ),
        bootstrap_core_account=bootstrap,
    )
    app = FastAPI()
    app.include_router(create_auth_router(lambda: runtime), prefix="/v1/platform")
    client = TestClient(app)
    client.cookies.set("cloud_browser_instance_a", "signed-in-cloud-session")

    response = client.post(
        "/v1/platform/auth/core/bootstrap",
        json={
            "displayName": "My Mac Studio",
            "ownerPassword": "correct horse battery staple",
        },
    )

    assert response.status_code == 201
    assert response.json()["isCore"] is True
    assert captured == {
        "display_name": "My Mac Studio",
        "owner_password": "correct horse battery staple",
        "cloud": browser_cloud,
    }
    cookies = "\n".join(response.headers.get_list("set-cookie"))
    assert f"{_member_cookie_name()}=new-core-session" in cookies
    assert "HttpOnly" in cookies
    assert "omlx_admin_session=\"\"" in cookies


def test_cross_origin_request_cannot_bootstrap_core_with_cloud_cookie():
    bootstrap = MagicMock()
    runtime = SimpleNamespace(
        cloud_browser_cookie_name=lambda: "cloud_browser_instance_a",
        cloud_for_browser=lambda session_id: object(),
        bootstrap_core_account=bootstrap,
    )
    app = FastAPI()
    app.include_router(create_auth_router(lambda: runtime), prefix="/v1/platform")
    client = TestClient(app)
    client.cookies.set("cloud_browser_instance_a", "signed-in-cloud-session")

    response = client.post(
        "/v1/platform/auth/core/bootstrap",
        json={
            "displayName": "My Mac Studio",
            "ownerPassword": "correct horse battery staple",
        },
        headers={"Origin": "http://127.0.0.1:9000"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "csrf_origin_mismatch"
    bootstrap.assert_not_called()


def test_legacy_admin_session_is_bound_to_local_instance_audience():
    original = (
        admin_auth._serializer,
        admin_auth.SECRET_KEY,
        admin_auth._get_global_settings,
        admin_auth._resolve_local_principal,
        admin_auth._resolve_local_cookie_name,
        admin_auth._resolve_session_audience,
    )
    try:
        admin_auth.init_auth(
            "shared-cloned-signing-key",
            session_audience_resolver=lambda: (
                "local_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
        )
        token_a = admin_auth.create_session_token()
        cookie_a = admin_auth.session_cookie_name()
        assert admin_auth.verify_session_token(token_a) is True

        admin_auth.init_auth(
            "shared-cloned-signing-key",
            session_audience_resolver=lambda: (
                "local_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            ),
        )
        assert admin_auth.session_cookie_name() != cookie_a
        assert admin_auth.verify_session_token(token_a) is False
    finally:
        (
            admin_auth._serializer,
            admin_auth.SECRET_KEY,
            admin_auth._get_global_settings,
            admin_auth._resolve_local_principal,
            admin_auth._resolve_local_cookie_name,
            admin_auth._resolve_session_audience,
        ) = original
