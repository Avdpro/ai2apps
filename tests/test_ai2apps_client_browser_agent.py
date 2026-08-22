from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from ai2apps.api.client import create_client_router
from ai2apps.identity import MemberRole, RequestPrincipal


class FakeHelperControl:
    def __init__(self) -> None:
        self.actor_user_id: str | None = None
        self.initial_url: str | None = None

    def launch_browser_agent(
        self,
        *,
        actor_user_id: str,
        initial_url: str | None = None,
    ) -> dict[str, object]:
        self.actor_user_id = actor_user_id
        self.initial_url = initial_url
        return {
            "status": "launched",
            "profile_id": "a" * 64,
            "pid": 42,
        }

    def restart_local(self, *, actor_user_id: str) -> dict[str, object]:
        self.actor_user_id = actor_user_id
        return {"status": "restarting"}


class RejectingHelperControl(FakeHelperControl):
    def restart_local(self, *, actor_user_id: str) -> dict[str, object]:
        from ai2apps.helper_control import HelperControlError

        self.actor_user_id = actor_user_id
        raise HelperControlError("Helper request rejected")


def test_browser_agent_launch_uses_authenticated_actor() -> None:
    helper = FakeHelperControl()
    principal = RequestPrincipal(
        actor_user_id="user-123",
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.OWNER,
        membership_epoch=1,
    )
    app = FastAPI()
    app.include_router(
        create_client_router(
            runtime_provider=lambda: None,
            principal_provider=lambda: principal,
            helper_control_provider=lambda: helper,
        ),
        prefix="/v1/platform",
    )

    response = TestClient(app).post(
        "/v1/platform/client/browser-agent",
        json={"initial_url": "https://example.com/"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "launched",
        "profile_id": "a" * 64,
        "pid": 42,
    }
    assert helper.actor_user_id == "user-123"
    assert helper.initial_url == "https://example.com/"


def test_local_restart_uses_helper_and_requires_device_owner() -> None:
    helper = FakeHelperControl()
    owner = RequestPrincipal(
        actor_user_id="user-123",
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.OWNER,
        membership_epoch=1,
    )
    app = FastAPI()
    app.include_router(
        create_client_router(
            runtime_provider=lambda: None,
            principal_provider=lambda: owner,
            helper_control_provider=lambda: helper,
        ),
        prefix="/v1/platform",
    )

    response = TestClient(app).post("/v1/platform/client/restart-local")

    assert response.status_code == 202
    assert response.json() == {"status": "restarting"}
    assert helper.actor_user_id == "user-123"


def test_local_restart_rejects_non_owner_member() -> None:
    helper = FakeHelperControl()
    member = RequestPrincipal(
        actor_user_id="member-123",
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )
    app = FastAPI()
    app.include_router(
        create_client_router(
            runtime_provider=lambda: None,
            principal_provider=lambda: member,
            helper_control_provider=lambda: helper,
        ),
        prefix="/v1/platform",
    )

    response = TestClient(app).post("/v1/platform/client/restart-local")

    assert response.status_code == 403
    assert helper.actor_user_id is None


def test_local_restart_falls_back_to_supervised_exit_for_stale_token(
    monkeypatch,
) -> None:
    helper = RejectingHelperControl()
    owner = RequestPrincipal(
        actor_user_id="user-123",
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.OWNER,
        membership_epoch=1,
    )
    monkeypatch.setenv("AI2APPS_SUPERVISED", "helper")
    app = FastAPI()
    app.include_router(
        create_client_router(
            runtime_provider=lambda: None,
            principal_provider=lambda: owner,
            helper_control_provider=lambda: helper,
        ),
        prefix="/v1/platform",
    )

    with patch("ai2apps.api.client._schedule_supervised_self_restart") as restart:
        response = TestClient(app).post("/v1/platform/client/restart-local")

    assert response.status_code == 202
    assert response.json() == {"status": "restarting"}
    restart.assert_called_once_with()


def test_local_restart_does_not_self_exit_when_unsupervised(monkeypatch) -> None:
    helper = RejectingHelperControl()
    owner = RequestPrincipal(
        actor_user_id="user-123",
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.OWNER,
        membership_epoch=1,
    )
    monkeypatch.delenv("AI2APPS_SUPERVISED", raising=False)
    app = FastAPI()
    app.include_router(
        create_client_router(
            runtime_provider=lambda: None,
            principal_provider=lambda: owner,
            helper_control_provider=lambda: helper,
        ),
        prefix="/v1/platform",
    )

    with patch("ai2apps.api.client._schedule_supervised_self_restart") as restart:
        response = TestClient(app).post("/v1/platform/client/restart-local")

    assert response.status_code == 503
    restart.assert_not_called()
