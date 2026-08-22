import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.router import create_ai2apps_router
from ai2apps.cloud_client import (
    AI2AppsCloudClient,
    CloudSessionStore,
    resolve_cloud_base_url,
)
from ai2apps.cloud_requests import CloudAIRequestRepository
from ai2apps.config import PlatformConfig
from ai2apps.identity import (
    IdentityRepository,
    MemberRole,
    OrganizationType,
    RequestPrincipal,
)
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.secrets import MemorySecretBackend


def _local_client(handler):
    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    runtime = SimpleNamespace(cloud=cloud)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
    return TestClient(app), backend, cloud


def _enable_device_auth(runtime):
    runtime.cloud_ai_authorization_headers = lambda principal: {
        "Authorization": "Device 35f29378-4912-4a76-a99d-197361226ca7.device-secret",
        "X-AI2Apps-Actor-User-Id": principal.actor_user_id,
        "X-AI2Apps-Membership-Epoch": str(principal.membership_epoch),
    }
    return runtime


def _bound_core_client(tmp_path, handler):
    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    identities = IdentityRepository(runtime.database)
    principal = RequestPrincipal(
        actor_user_id="9df2aa2a-b029-4d10-a9e1-805db637e595",
        installation_id="b657d60d-2a38-4a66-bf21-20d7bb1bb13f",
        organization_id="c10c7a58-b338-4194-a6a2-693bf1d54c9e",
        billing_account_id="71c8e42b-f8a6-49f1-b618-76b9e20c0510",
        role=MemberRole.CORE,
        membership_epoch=3,
    )
    identities.bind_installation(
        installation_id=principal.installation_id,
        cloud_device_id="35f29378-4912-4a76-a99d-197361226ca7",
        organization_id=principal.organization_id,
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id=principal.actor_user_id,
        billing_account_id=principal.billing_account_id,
        access_epoch=7,
        core_membership_epoch=principal.membership_epoch,
    )
    runtime.cloud = cloud
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: principal,
        )
    )
    return TestClient(app), runtime, backend, cloud, principal


def test_cloud_origin_validation_rejects_credentials_and_paths():
    assert resolve_cloud_base_url("https://coder.ai2apps.com/") == (
        "https://coder.ai2apps.com"
    )
    with pytest.raises(ValueError):
        resolve_cloud_base_url("https://user:secret@example.com")
    with pytest.raises(ValueError):
        resolve_cloud_base_url("https://example.com/api")
    with pytest.raises(ValueError):
        resolve_cloud_base_url("http://example.com")
    assert resolve_cloud_base_url("http://127.0.0.1:8787") == (
        "http://127.0.0.1:8787"
    )


def test_local_capacity_policy_endpoint_exposes_rollout_contract(tmp_path):
    def handler(request: httpx.Request):
        raise AssertionError(f"Local capacity policy must not call Cloud: {request.url}")

    client, _, _, _, _ = _bound_core_client(tmp_path, handler)

    response = client.get("/v1/platform/cloud/capacity-policy")

    assert response.status_code == 200
    assert response.json()["baseLevels"]["member"] == {
        "maxCoreDevices": 1,
        "maxMembersPerDevice": 2,
    }
    assert response.json()["subscriptionPlans"]["team"] == {
        "maxCoreDevices": 20,
        "maxMembersPerDevice": 50,
    }
    assert response.json()["rules"]["retroactiveRevocation"] is False


def test_cloud_session_store_namespaces_isolate_browser_profiles():
    backend = MemorySecretBackend()
    first = CloudSessionStore(
        backend,
        "https://coder.ai2apps.test",
        namespace="browser:first-profile-00000000000000000000000000000000",
    )
    second = CloudSessionStore(
        backend,
        "https://coder.ai2apps.test",
        namespace="browser:second-profile-0000000000000000000000000000000",
    )

    first.save("first-session")
    second.save("second-session")

    assert first.key != second.key
    assert first.load() == "first-session"
    assert second.load() == "second-session"
    first.clear()
    assert first.load() is None
    assert second.load() == "second-session"


@pytest.mark.asyncio
async def test_runtime_cloud_clients_keep_browser_logins_separate(tmp_path):
    def handler(request: httpx.Request):
        if request.url.path == "/v1/auth/login":
            email = json.loads(request.content)["email"]
            return httpx.Response(
                200,
                json={"email": email},
                headers={
                    "set-cookie": (
                        f"ai2apps_session=session-{email}; Path=/; HttpOnly; "
                        "Secure; SameSite=Strict"
                    )
                },
            )
        return httpx.Response(200, json={"cookie": request.headers.get("cookie")})

    backend = MemorySecretBackend()
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    first = runtime.cloud_for_browser("a" * 32)
    second = runtime.cloud_for_browser("b" * 32)

    first_login = await first.request(
        "POST", "/v1/auth/login", json={"email": "core@example.com"}
    )
    second_login = await second.request(
        "POST", "/v1/auth/login", json={"email": "member@example.com"}
    )
    await first_login.aclose()
    await second_login.aclose()
    first_me = await first.request("GET", "/v1/auth/me")
    second_me = await second.request("GET", "/v1/auth/me")

    assert first_me.json()["cookie"] == "ai2apps_session=session-core@example.com"
    assert second_me.json()["cookie"] == "ai2apps_session=session-member@example.com"
    await first_me.aclose()
    await second_me.aclose()
    await runtime.stop_background_tasks()


def test_bound_installation_local_session_resolves_to_core_device_principal():
    captured = {}
    core = RequestPrincipal(
        actor_user_id="9df2aa2a-b029-4d10-a9e1-805db637e595",
        installation_id="b657d60d-2a38-4a66-bf21-20d7bb1bb13f",
        organization_id="c10c7a58-b338-4194-a6a2-693bf1d54c9e",
        billing_account_id="71c8e42b-f8a6-49f1-b618-76b9e20c0510",
        role=MemberRole.CORE,
        membership_epoch=3,
    )

    def handler(request: httpx.Request):
        captured["authorization"] = request.headers.get("authorization")
        captured["actor"] = request.headers.get("x-ai2apps-actor-user-id")
        captured["membership_epoch"] = request.headers.get(
            "x-ai2apps-membership-epoch"
        )
        return httpx.Response(200, json={"items": []})

    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    runtime = _enable_device_auth(SimpleNamespace(cloud=cloud))
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: core,
        )
    )

    response = TestClient(app).get("/v1/platform/cloud/ai/models")

    assert response.status_code == 200
    assert captured["authorization"].startswith("Device ")
    assert captured["actor"] == core.actor_user_id
    assert captured["membership_epoch"] == "3"


def test_login_cookie_stays_in_native_client_and_is_restored_for_auth_me():
    captured = {}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/auth/login":
            captured["login"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"user": {"id": "user-1"}},
                headers={
                    "set-cookie": (
                        "ai2apps_session=session-secret; Path=/; HttpOnly; "
                        "Secure; SameSite=Strict"
                    )
                },
            )
        captured["cookie"] = request.headers.get("cookie")
        return httpx.Response(200, json={"user": {"id": "user-1"}})

    client, backend, cloud = _local_client(handler)
    login = client.post(
        "/v1/platform/cloud/auth/login",
        json={"email": "me@example.com", "password": "long-password"},
    )
    me = client.get("/v1/platform/cloud/auth/me")

    assert login.status_code == 200
    assert "ai2apps_session" not in login.headers.get("set-cookie", "")
    assert "ai2apps_cloud_browser=" in login.headers["set-cookie"]
    assert captured["login"] == {
        "email": "me@example.com",
        "password": "long-password",
    }
    assert captured["cookie"] == "ai2apps_session=session-secret"
    assert backend.values[cloud.session_store.key] == "session-secret"
    assert me.json()["user"]["id"] == "user-1"


def test_logout_clears_persisted_cloud_session():
    def handler(request: httpx.Request):
        return httpx.Response(204)

    client, backend, cloud = _local_client(handler)
    backend.store(cloud.session_store.key, "old-session")

    response = client.post("/v1/platform/cloud/auth/logout")

    assert response.status_code == 204
    assert cloud.session_store.key not in backend.values


def test_cross_origin_browser_login_is_not_forwarded_to_cloud():
    forwarded = []

    def handler(request: httpx.Request):
        forwarded.append(request)
        return httpx.Response(500)

    client, _, _ = _local_client(handler)

    response = client.post(
        "/v1/platform/cloud/auth/login",
        json={"email": "me@example.com", "password": "long-password"},
        headers={"Origin": "http://127.0.0.1:9000"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "csrf_origin_mismatch"
    assert forwarded == []


def test_logout_clears_local_session_even_when_cloud_rejects_it():
    def handler(request: httpx.Request):
        return httpx.Response(
            503,
            json={"error": {"code": "TEMPORARILY_UNAVAILABLE"}},
        )

    client, backend, cloud = _local_client(handler)
    backend.store(cloud.session_store.key, "unregistered-session")

    response = client.post("/v1/platform/cloud/auth/logout")

    assert response.status_code == 503
    assert cloud.session_store.key not in backend.values


def test_admin_reauthentication_is_forwarded_without_persisting_password():
    captured = {}

    def handler(request: httpx.Request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "verifiedAt": "2026-08-14T05:30:00Z",
                "expiresAt": "2026-08-14T05:45:00Z",
            },
        )

    client, backend, _ = _local_client(handler)
    response = client.post(
        "/v1/platform/cloud/admin/reauth",
        json={"password": "long-password"},
    )

    assert response.status_code == 200
    assert captured == {
        "path": "/v1/admin/reauth",
        "body": {"password": "long-password"},
    }
    assert not any("long-password" in value for value in backend.values.values())


def test_core_member_management_uses_bound_installation_id(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/members"):
            return httpx.Response(200, json={"items": []})
        return httpx.Response(
            200,
            json={
                "installationId": "b657d60d-2a38-4a66-bf21-20d7bb1bb13f",
                "organizationType": "household",
                "organizationName": "Family",
                "status": "active",
            },
        )

    client, _runtime, _backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )

    detail = client.get("/v1/platform/cloud/installation")
    members = client.get("/v1/platform/cloud/installation/members")

    assert detail.status_code == members.status_code == 200
    assert calls == [
        (
            "GET",
            "/v1/installations/b657d60d-2a38-4a66-bf21-20d7bb1bb13f",
        ),
        (
            "GET",
            "/v1/installations/b657d60d-2a38-4a66-bf21-20d7bb1bb13f/members",
        ),
    ]


def test_core_device_management_lists_and_revokes_owned_device(tmp_path):
    calls = []
    target_device = "6e33b10e-2322-44a3-9c4a-c32ead526224"
    target_installation = "49007af7-800e-47d9-84d6-801144ac7abc"

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body, dict(request.headers)))
        if request.url.path == "/v1/remote/devices" and request.method == "GET":
            return httpx.Response(200, json={"items": [{"id": target_device, "displayName": "Kitchen Mac", "status": "active"}]})
        if request.url.path == f"/v1/remote/devices/{target_device}" and request.method == "PATCH":
            assert body == {"displayName": "Living Room Mac"}
            return httpx.Response(200, json={"id": target_device, "displayName": "Living Room Mac", "status": "active"})
        if request.url.path == "/v1/installations":
            return httpx.Response(200, json={"items": [{"installationId": target_installation, "cloudDeviceId": target_device, "role": "core"}]})
        if request.url.path == "/v1/owner-reauth/grants":
            assert body == {
                "purpose": "installation.revoke",
                "resourceType": "installation",
                "resourceId": target_installation,
                "password": "correct-owner-password",
            }
            return httpx.Response(200, json={"grant": "one-use-owner-grant"})
        if request.url.path == f"/v1/remote/devices/{target_device}/revoke":
            assert request.headers["x-owner-reauth-grant"] == "one-use-owner-grant"
            return httpx.Response(200, json={"revoked": True})
        raise AssertionError(f"Unexpected Cloud request: {request.method} {request.url}")

    client, _runtime, backend, _cloud, _principal = _bound_core_client(tmp_path, handler)

    listed = client.get("/v1/platform/cloud/account/devices")
    renamed = client.patch(
        f"/v1/platform/cloud/account/devices/{target_device}",
        json={"displayName": "Living Room Mac"},
    )
    revoked = client.post(
        f"/v1/platform/cloud/account/devices/{target_device}/revoke",
        json={"ownerPassword": "correct-owner-password"},
    )

    assert listed.status_code == 200
    assert listed.json()["items"][0]["displayName"] == "Kitchen Mac"
    assert renamed.status_code == 200
    assert renamed.json()["displayName"] == "Living Room Mac"
    assert revoked.status_code == 200
    assert revoked.json() == {"revoked": True}
    assert not any("correct-owner-password" in value for value in backend.values.values())
    assert [item[:2] for item in calls] == [
        ("GET", "/v1/remote/devices"),
        ("PATCH", f"/v1/remote/devices/{target_device}"),
        ("GET", "/v1/installations"),
        ("POST", "/v1/owner-reauth/grants"),
        ("POST", f"/v1/remote/devices/{target_device}/revoke"),
    ]


def test_core_device_revoke_rejects_device_not_owned_by_core_account(tmp_path):
    def handler(request: httpx.Request):
        assert request.url.path == "/v1/installations"
        return httpx.Response(200, json={"items": []})

    client, _runtime, _backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )
    response = client.post(
        "/v1/platform/cloud/account/devices/6e33b10e-2322-44a3-9c4a-c32ead526224/revoke",
        json={"ownerPassword": "correct-owner-password"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "core_device_not_found"


def test_core_can_invite_member_without_exposing_device_identity(tmp_path):
    captured = {}

    def handler(request: httpx.Request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "invitationId": "invite-1",
                "inviteCode": "one-use-invite-code",
                "inviteUrl": "https://coder.ai2apps.test/invitations/accept#invite=secret",
                "role": "member",
                "expiresAt": "2026-08-23T00:00:00Z",
                "delivery": {
                    "status": "sent",
                    "attempts": 1,
                    "lastAttemptAt": "2026-08-16T00:00:00Z",
                    "deliveredAt": "2026-08-16T00:00:00Z",
                    "failureCategory": None,
                },
            },
        )

    client, _runtime, _backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )
    response = client.post(
        "/v1/platform/cloud/installation/invitations",
        json={"email": "member@example.com", "role": "member"},
    )

    assert response.status_code == 201
    assert captured == {
        "path": (
            "/v1/installations/"
            "b657d60d-2a38-4a66-bf21-20d7bb1bb13f/invitations"
        ),
        "body": {"email": "member@example.com", "role": "member"},
    }
    payload = response.json()
    assert payload["inviteUrl"].endswith("#invite=secret")
    assert payload["inviteQrDataUrl"].startswith("data:image/svg+xml;base64,")
    assert payload["delivery"]["status"] == "sent"


def test_core_can_list_and_resend_pending_invitations(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path, request.url.query.decode()))
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "invitationId": "invite-1",
                            "email": "member@example.com",
                            "role": "member",
                            "status": "pending",
                            "delivery": {
                                "status": "failed",
                                "attempts": 1,
                                "failureCategory": "temporary",
                            },
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "invitationId": "invite-1",
                "inviteCode": "rotated-one-use-code",
                "inviteUrl": (
                    "https://coder.ai2apps.test/invitations/accept"
                    "#invite=rotated-secret"
                ),
                "role": "member",
                "expiresAt": "2026-08-23T00:00:00Z",
                "delivery": {
                    "status": "sent",
                    "attempts": 2,
                    "lastAttemptAt": "2026-08-16T00:05:00Z",
                    "deliveredAt": "2026-08-16T00:05:00Z",
                    "failureCategory": None,
                },
            },
        )

    client, _runtime, _backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )

    listed = client.get(
        "/v1/platform/cloud/installation/invitations?status=pending"
    )
    resent = client.post(
        "/v1/platform/cloud/installation/invitations/invite-1/resend"
    )

    assert listed.status_code == resent.status_code == 200
    assert listed.json()["items"][0]["delivery"]["status"] == "failed"
    assert "inviteUrl" not in listed.text
    assert resent.json()["delivery"]["attempts"] == 2
    assert resent.json()["inviteQrDataUrl"].startswith(
        "data:image/svg+xml;base64,"
    )
    assert calls == [
        (
            "GET",
            "/v1/installations/b657d60d-2a38-4a66-bf21-20d7bb1bb13f/invitations",
            "status=pending",
        ),
        (
            "POST",
            "/v1/installations/b657d60d-2a38-4a66-bf21-20d7bb1bb13f/invitations/invite-1/resend",
            "",
        ),
    ]


def test_role_change_uses_one_time_owner_grant_and_refreshes_projection(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(
            {
                "method": request.method,
                "path": request.url.path,
                "body": json.loads(request.content),
                "grant": request.headers.get("x-owner-reauth-grant"),
            }
        )
        if request.url.path == "/v1/owner-reauth/grants":
            return httpx.Response(
                201,
                json={
                    "grant": "owner-grant-secret",
                    "expiresAt": "2026-08-16T00:15:00Z",
                },
            )
        return httpx.Response(
            200,
            json={
                "userId": "member-user",
                "role": "guest",
                "status": "active",
                "membershipEpoch": 5,
            },
        )

    client, runtime, backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )
    refreshed = []

    class Remote:
        async def refresh_access_projection(self):
            refreshed.append(True)

    runtime.remote = Remote()
    response = client.patch(
        "/v1/platform/cloud/installation/members/member-user",
        json={"role": "guest", "ownerPassword": "owner-password"},
    )

    assert response.status_code == 200
    assert calls[0]["path"] == "/v1/owner-reauth/grants"
    assert calls[0]["body"]["password"] == "owner-password"
    assert calls[0]["body"]["resourceType"] == "installation"
    assert calls[1]["grant"] == "owner-grant-secret"
    assert calls[1]["body"] == {"role": "guest"}
    assert refreshed == [True]
    assert not any("owner-password" in value for value in backend.values.values())


def test_status_change_needs_no_password(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "userId": "member-user",
                "role": "member",
                "status": "suspended",
                "membershipEpoch": 5,
            },
        )

    client, runtime, _backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )

    class Remote:
        async def refresh_access_projection(self):
            return None

    runtime.remote = Remote()
    changed = client.patch(
        "/v1/platform/cloud/installation/members/member-user",
        json={"status": "suspended"},
    )
    assert changed.status_code == 200
    assert calls == [
        "/v1/installations/"
        "b657d60d-2a38-4a66-bf21-20d7bb1bb13f/members/member-user"
    ]


def test_policy_read_and_update_forward_etag_and_one_time_grant(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/owner-reauth/grants":
            return httpx.Response(201, json={"grant": "policy-grant-secret"})
        policy = {
            "organizationId": "c10c7a58-b338-4194-a6a2-693bf1d54c9e",
            "policyVersion": 4,
            "allowedRoles": ["core", "member"],
            "allowedAppIds": None,
            "allowedModelIds": ["openai/gpt-5"],
            "defaultMonthlyPointLimit": "1000",
            "defaultConcurrencyLimit": 2,
            "offlineGraceSeconds": 120,
            "membershipEpochRequired": True,
            "deviceAccessEpochRequired": True,
        }
        return httpx.Response(200, json=policy, headers={"etag": '"policy-4"'})

    client, runtime, backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )
    refreshed = []

    class Remote:
        async def refresh_access_projection(self):
            refreshed.append(True)

    runtime.remote = Remote()
    read = client.get("/v1/platform/cloud/installation/policy")
    changed = client.patch(
        "/v1/platform/cloud/installation/policy",
        headers={"If-Match": '"policy-3"'},
        json={
            "allowedAppIds": None,
            "allowedModelIds": ["openai/gpt-5"],
            "defaultMonthlyPointLimit": "1000",
            "defaultConcurrencyLimit": 2,
            "offlineGraceSeconds": 120,
            "ownerPassword": "owner-password",
        },
    )

    assert read.headers["etag"] == changed.headers["etag"] == '"policy-4"'
    grant_request, patch_request = calls[-2:]
    assert json.loads(grant_request.content)["purpose"] == "organization.policy.change"
    assert patch_request.headers["if-match"] == '"policy-3"'
    assert patch_request.headers["x-owner-reauth-grant"] == "policy-grant-secret"
    assert "ownerPassword" not in json.loads(patch_request.content)
    assert refreshed == [True]
    assert not any("owner-password" in value for value in backend.values.values())


def test_member_quota_update_uses_shared_policy_etag_and_preserves_conflict(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/v1/owner-reauth/grants":
            return httpx.Response(201, json={"grant": "quota-grant-secret"})
        if request.method == "PATCH":
            return httpx.Response(
                412,
                json={"error": {"code": "POLICY_VERSION_MISMATCH", "message": "stale"}},
                headers={"etag": '"policy-8"'},
            )
        return httpx.Response(
            200,
            json={"userId": "member-user", "policyVersion": 7, "allowedModelIds": None, "monthlyPointLimit": None, "concurrencyLimit": None},
            headers={"etag": '"policy-7"'},
        )

    client, runtime, _backend, _cloud, _principal = _bound_core_client(
        tmp_path, handler
    )

    class Remote:
        async def refresh_access_projection(self):
            raise AssertionError("conflicting writes must not refresh projection")

    runtime.remote = Remote()
    read = client.get("/v1/platform/cloud/installation/members/member-user/quota")
    changed = client.patch(
        "/v1/platform/cloud/installation/members/member-user/quota",
        headers={"If-Match": '"policy-7"'},
        json={"allowedModelIds": None, "monthlyPointLimit": None, "concurrencyLimit": 1, "ownerPassword": "owner-password"},
    )

    assert read.headers["etag"] == '"policy-7"'
    assert changed.status_code == 412
    assert changed.headers["etag"] == '"policy-8"'
    assert changed.json()["error"]["code"] == "POLICY_VERSION_MISMATCH"
    grant_request, patch_request = calls[-2:]
    assert json.loads(grant_request.content)["purpose"] == "organization.member.quota_change"
    assert patch_request.headers["if-match"] == '"policy-7"'
    assert patch_request.headers["x-owner-reauth-grant"] == "quota-grant-secret"


def test_points_remain_decimal_strings_and_ai_sse_is_forwarded():
    captured = {}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/points":
            return httpx.Response(
                200,
                json={"promotional": "300", "paid": "500", "total": "800"},
            )
        captured["idempotency"] = request.headers["idempotency-key"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=(
                b"event: response.created\ndata: {\"requestId\":\"req-1\"}\n\n"
                b"event: output_text.delta\ndata: {\"delta\":\"hello\"}\n\n"
                b"event: response.completed\ndata: {\"charged\":\"1\"}\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    client, _, _ = _local_client(handler)
    points = client.get("/v1/platform/cloud/points")
    streamed = client.post(
        "/v1/platform/cloud/ai/responses",
        headers={"Idempotency-Key": "request-123"},
        json={
            "model": "openai/gpt-test",
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }
            ],
            "stream": True,
        },
    )

    assert points.json() == {"promotional": "300", "paid": "500", "total": "800"}
    assert captured["idempotency"] == "request-123"
    assert captured["body"]["model"] == "openai/gpt-test"
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert "response.completed" in streamed.text


def test_cloud_ai_rejects_client_supplied_actor_and_billing_identity():
    called = False

    def handler(request: httpx.Request):
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client, _, _ = _local_client(handler)
    response = client.post(
        "/v1/platform/cloud/ai/responses",
        headers={"Idempotency-Key": "request-reserved-1"},
        json={
            "model": "openai/gpt-test",
            "input": [],
            "billingAccountId": "member-controlled-payer",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "reserved_identity_field"
    assert called is False


def test_cloud_ai_uses_trusted_principal_for_local_dispatch_audit(tmp_path):
    captured = {}

    def handler(request: httpx.Request):
        captured["body"] = json.loads(request.content)
        captured["authorization"] = request.headers.get("authorization")
        captured["actor"] = request.headers.get("x-ai2apps-actor-user-id")
        captured["membership_epoch"] = request.headers.get(
            "x-ai2apps-membership-epoch"
        )
        return httpx.Response(200, json={"output": []})

    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.cloud = cloud
    _enable_device_auth(runtime)
    principal = RequestPrincipal(
        actor_user_id="member-alice",
        installation_id="nas-1",
        organization_id="family-1",
        billing_account_id="core-billing",
        role=MemberRole.MEMBER,
        membership_epoch=4,
    )
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: principal,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/v1/platform/cloud/ai/responses",
        headers={"Idempotency-Key": "request-member-1"},
        json={"model": "openai/gpt-test", "input": [], "stream": False},
    )

    assert response.status_code == 200
    assert "actor_user_id" not in captured["body"]
    assert captured["authorization"].startswith("Device ")
    assert captured["actor"] == "member-alice"
    assert captured["membership_epoch"] == "4"
    event = runtime.events.latest_for_subject(
        "request-member-1", event_type="cloud.model.invocation.requested"
    )
    assert event is not None
    assert event.payload["actor_user_id"] == "member-alice"
    assert event.payload["billing_account_id"] == "core-billing"


def test_member_can_invoke_models_but_cannot_manage_core_cloud_account():
    paths = []

    def handler(request: httpx.Request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"output": []})

    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    runtime = _enable_device_auth(SimpleNamespace(cloud=cloud))
    member = RequestPrincipal(
        actor_user_id="member-alice",
        installation_id="nas-1",
        organization_id="family-1",
        billing_account_id="core-billing",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: member,
        )
    )
    client = TestClient(app)

    account = client.get("/v1/platform/cloud/auth/me")
    points = client.get("/v1/platform/cloud/points")
    model = client.post(
        "/v1/platform/cloud/ai/responses",
        headers={"Idempotency-Key": "member-model-request-1"},
        json={"model": "openai/gpt-test", "input": [], "stream": False},
    )

    assert account.status_code == points.status_code == 403
    assert model.status_code == 200
    assert paths == ["/v1/ai/responses"]


def test_cloud_request_status_and_cancel_are_scoped_to_local_actor(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/ai/responses":
            return httpx.Response(
                200,
                json={"requestId": "cloud-request-alice", "output": []},
            )
        if request.url.path.endswith("/cancel"):
            return httpx.Response(
                200,
                json={"requestId": "cloud-request-alice", "status": "cancelled"},
            )
        return httpx.Response(
            200,
            json={"requestId": "cloud-request-alice", "status": "completed"},
        )

    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.cloud = cloud
    _enable_device_auth(runtime)
    principals = {
        "alice": RequestPrincipal(
            actor_user_id="member-alice",
            installation_id="nas-1",
            organization_id="family-1",
            billing_account_id="core-billing",
            role=MemberRole.MEMBER,
            membership_epoch=1,
        ),
        "bob": RequestPrincipal(
            actor_user_id="member-bob",
            installation_id="nas-1",
            organization_id="family-1",
            billing_account_id="core-billing",
            role=MemberRole.MEMBER,
            membership_epoch=1,
        ),
        "core": RequestPrincipal(
            actor_user_id="core-user",
            installation_id="nas-1",
            organization_id="family-1",
            billing_account_id="core-billing",
            role=MemberRole.CORE,
            membership_epoch=1,
        ),
    }
    current = {"principal": "alice"}
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: principals[current["principal"]],
        )
    )
    client = TestClient(app)

    created = client.post(
        "/v1/platform/cloud/ai/responses",
        headers={"Idempotency-Key": "alice-request-key-1"},
        json={"model": "openai/gpt-test", "input": [], "stream": False},
    )
    current["principal"] = "bob"
    bob_status = client.get(
        "/v1/platform/cloud/ai/requests/cloud-request-alice"
    )
    bob_cancel = client.post(
        "/v1/platform/cloud/ai/requests/cloud-request-alice/cancel"
    )
    current["principal"] = "alice"
    alice_status = client.get(
        "/v1/platform/cloud/ai/requests/cloud-request-alice"
    )
    alice_cancel = client.post(
        "/v1/platform/cloud/ai/requests/cloud-request-alice/cancel"
    )
    current["principal"] = "core"
    core_status = client.get(
        "/v1/platform/cloud/ai/requests/cloud-request-alice"
    )
    core_cancel = client.post(
        "/v1/platform/cloud/ai/requests/cloud-request-alice/cancel"
    )

    assert created.status_code == 200
    assert bob_status.status_code == bob_cancel.status_code == 404
    assert alice_status.status_code == alice_cancel.status_code == 200
    assert core_status.status_code == 404
    assert core_cancel.status_code == 200
    assert calls == [
        ("POST", "/v1/ai/responses"),
        ("GET", "/v1/ai/requests/cloud-request-alice"),
        ("POST", "/v1/ai/requests/cloud-request-alice/cancel"),
        ("POST", "/v1/ai/requests/cloud-request-alice/cancel"),
    ]
    record = CloudAIRequestRepository(runtime.database).get_by_cloud_request_id(
        "cloud-request-alice"
    )
    assert record is not None
    assert record.actor_user_id == "member-alice"
    assert record.billing_account_id == "core-billing"


def test_cloud_idempotency_key_cannot_be_reused_by_another_member(tmp_path):
    upstream_calls = 0

    def handler(request: httpx.Request):
        nonlocal upstream_calls
        upstream_calls += 1
        return httpx.Response(
            200,
            json={"requestId": "cloud-request-shared-key", "output": []},
        )

    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.cloud = cloud
    _enable_device_auth(runtime)
    current = {"actor": "member-alice"}

    def principal():
        return RequestPrincipal(
            actor_user_id=current["actor"],
            installation_id="nas-1",
            organization_id="family-1",
            billing_account_id="core-billing",
            role=MemberRole.MEMBER,
            membership_epoch=1,
        )

    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=principal,
        )
    )
    client = TestClient(app)
    request = {
        "headers": {"Idempotency-Key": "shared-request-key-1"},
        "json": {"model": "openai/gpt-test", "input": [], "stream": False},
    }

    alice = client.post("/v1/platform/cloud/ai/responses", **request)
    current["actor"] = "member-bob"
    bob = client.post("/v1/platform/cloud/ai/responses", **request)

    assert alice.status_code == 200
    assert bob.status_code == 409
    assert bob.json()["detail"]["code"] == "cloud_request_idempotency_conflict"
    assert upstream_calls == 1


def test_stream_created_event_binds_cloud_request_to_member(tmp_path):
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            content=(
                b'event: response.created\ndata: {"requestId":"stream-request-1"}\n\n'
                b'event: output_text.delta\ndata: {"delta":"hello"}\n\n'
                b'event: response.completed\ndata: {"requestId":"stream-request-1"}\n\n'
            ),
            headers={"content-type": "text/event-stream"},
        )

    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.cloud = cloud
    _enable_device_auth(runtime)
    member = RequestPrincipal(
        actor_user_id="member-alice",
        installation_id="nas-1",
        organization_id="family-1",
        billing_account_id="core-billing",
        role=MemberRole.MEMBER,
        membership_epoch=2,
    )
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: member,
        )
    )
    client = TestClient(app)

    response = client.post(
        "/v1/platform/cloud/ai/responses",
        headers={"Idempotency-Key": "stream-request-key-1"},
        json={"model": "openai/gpt-test", "input": [], "stream": True},
    )

    record = CloudAIRequestRepository(runtime.database).get_by_cloud_request_id(
        "stream-request-1"
    )
    assert response.status_code == 200
    assert record is not None
    assert record.actor_user_id == "member-alice"
    assert record.status == "completed"


def test_image_generation_and_edit_are_forwarded_without_protocol_rewriting():
    captured = []

    def handler(request: httpx.Request):
        captured.append(
            {
                "path": request.url.path,
                "idempotency": request.headers["idempotency-key"],
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json={
                "requestId": f"req-{len(captured)}",
                "image": {
                    "dataUrl": "data:image/png;base64,aW1hZ2U=",
                    "size": "1024x1024",
                    "quality": "auto",
                    "format": "png",
                },
                "charged": "3",
                "balance": "797",
            },
        )

    client, _, _ = _local_client(handler)
    generated = client.post(
        "/v1/platform/cloud/ai/images/generations",
        headers={"Idempotency-Key": "image-generate-1"},
        json={
            "model": "openai/gpt-image-2",
            "prompt": "A paper boat",
            "size": "1024x1024",
            "quality": "auto",
            "outputFormat": "png",
            "n": 1,
        },
    )
    edited = client.post(
        "/v1/platform/cloud/ai/images/edits",
        headers={"Idempotency-Key": "image-edit-1"},
        json={
            "model": "openai/gpt-image-2",
            "prompt": "Make it blue",
            "imageDataUrls": ["data:image/png;base64,aW5wdXQ="],
        },
    )

    assert generated.status_code == edited.status_code == 200
    assert generated.json()["image"]["dataUrl"].startswith("data:image/png;base64,")
    assert [item["path"] for item in captured] == [
        "/v1/ai/images/generations",
        "/v1/ai/images/edits",
    ]
    assert captured[0]["idempotency"] == "image-generate-1"
    assert captured[1]["idempotency"] == "image-edit-1"
    assert captured[1]["body"]["imageDataUrls"] == [
        "data:image/png;base64,aW5wdXQ="
    ]


def test_cloud_transport_failure_has_stable_redacted_error():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("secret internal address", request=request)

    client, _, _ = _local_client(handler)
    response = client.get("/v1/platform/cloud/auth/me")

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "cloud_unavailable",
        "message": "AI2Apps Cloud is unavailable.",
        "retryable": True,
        "details": {},
    }
