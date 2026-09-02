import asyncio
import base64
import hashlib
import json
from datetime import timedelta

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.cloud_client import AI2AppsCloudClient, CloudSessionStore
from ai2apps.core import utc_now
from ai2apps.identity import IdentityRepository, MemberRole, OrganizationType
from ai2apps.qr import svg_qr_data_url
from ai2apps.remote import (
    RemoteAccessError,
    RemoteAccessManager,
    RemoteDeviceRepository,
    RemoteTokenError,
    verify_federation_relay_token,
    verify_installation_member_token,
    verify_remote_token,
)
from ai2apps.remote import frpc as frpc_module
from ai2apps.remote.frpc import (
    PINNED_FRP_BINARY_SHA256,
    PINNED_FRP_CA_SHA256,
    RemoteFrpcConfig,
    RemoteFrpcSupervisor,
)
from ai2apps.secrets import MemorySecretBackend
from ai2apps.storage import PlatformDatabase


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _jwt(private_key, claims, kid="remote-mobile-v1"):
    header = _b64(json.dumps({"alg": "EdDSA", "kid": kid}).encode())
    payload = _b64(json.dumps(claims).encode())
    signing = f"{header}.{payload}".encode("ascii")
    return f"{header}.{payload}.{_b64(private_key.sign(signing))}"


def _jwks(private_key, kid="remote-mobile-v1"):
    public = private_key.public_key().public_bytes_raw()
    return {"keys": [{"kty": "OKP", "crv": "Ed25519", "x": _b64(public), "kid": kid, "use": "sig", "alg": "EdDSA"}]}


def test_remote_mobile_token_verification_is_device_and_epoch_bound():
    key = Ed25519PrivateKey.generate()
    now = int(utc_now().timestamp())
    claims = {
        "iss": "ai2apps-cloud", "aud": "ai2apps-remote-mobile-v1",
        "sub": "user-1", "device_id": "device-1", "access_epoch": 3,
        "iat": now, "exp": now + 300, "jti": "token-1",
    }
    token = _jwt(key, claims)
    assert verify_remote_token(token, _jwks(key), device_id="device-1", access_epoch=3)["sub"] == "user-1"
    with pytest.raises(RemoteTokenError):
        verify_remote_token(token, _jwks(key), device_id="device-2", access_epoch=3)


def test_installation_member_assertion_is_bound_to_installation_and_epoch():
    key = Ed25519PrivateKey.generate()
    now = int(utc_now().timestamp())
    claims = {
        "iss": "ai2apps-cloud",
        "aud": "ai2apps-installation-member-v1",
        "sub": "9df2aa2a-b029-4d10-a9e1-805db637e595",
        "jti": "member-token-1",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "installation_id": "b657d60d-2a38-4a66-bf21-20d7bb1bb13f",
        "cloud_device_id": "35f29378-4912-4a76-a99d-197361226ca7",
        "organization_id": "c10c7a58-b338-4194-a6a2-693bf1d54c9e",
        "organization_type": "household",
        "role": "member",
        "membership_epoch": 4,
        "access_epoch": 7,
    }
    token = _jwt(key, claims, kid="installation-member-v1")
    jwks = _jwks(key, kid="installation-member-v1")

    verified = verify_installation_member_token(
        token,
        jwks,
        installation_id=claims["installation_id"],
        device_id=claims["cloud_device_id"],
        organization_id=claims["organization_id"],
        access_epoch=7,
    )

    assert verified["sub"] == claims["sub"]
    with pytest.raises(RemoteTokenError):
        verify_installation_member_token(
            token,
            jwks,
            installation_id=claims["installation_id"],
            device_id=claims["cloud_device_id"],
            organization_id=claims["organization_id"],
            access_epoch=8,
        )


def test_federation_relay_assertion_is_bound_to_request_export_and_two_node_path():
    key = Ed25519PrivateKey.generate()
    now = int(utc_now().timestamp())
    upstream = "b657d60d-2a38-4a66-bf21-20d7bb1bb13f"
    downstream = "35f29378-4912-4a76-a99d-197361226ca7"
    claims = {
        "iss": "ai2apps-cloud", "aud": "ai2apps-federation-relay-v1",
        "sub": "9df2aa2a-b029-4d10-a9e1-805db637e595", "jti": "relay-1",
        "iat": now, "nbf": now - 5, "exp": now + 90,
        "request_id": "405963f6-d6b5-46b2-b09f-d52e512adf42",
        "node_link_id": "71c8e42b-f8a6-49f1-b618-76b9e20c0510",
        "upstream_installation_id": upstream,
        "downstream_installation_id": downstream,
        "export_id": "weather.lookup", "grant_epoch": 2, "link_epoch": 3,
        "ancestor_node_ids": [downstream, upstream],
    }
    token = _jwt(key, claims, kid="federation-v1")
    verified = verify_federation_relay_token(
        token, _jwks(key, kid="federation-v1"), installation_id=upstream,
        export_id="weather.lookup", request_id=claims["request_id"],
        ancestor_node_ids=(downstream, upstream),
    )
    assert verified["node_link_id"] == claims["node_link_id"]
    with pytest.raises(RemoteTokenError):
        verify_federation_relay_token(
            token, _jwks(key, kid="federation-v1"), installation_id=upstream,
            export_id="weather.other", request_id=claims["request_id"],
            ancestor_node_ids=(downstream, upstream),
        )


def test_pairing_qr_is_a_local_svg_data_url():
    value = "https://coder.ai2apps.com/mobile/pair#challenge=opaque-one-use-value"
    rendered = svg_qr_data_url(value)
    assert rendered.startswith("data:image/svg+xml;base64,")
    svg = base64.b64decode(rendered.split(",", 1)[1])
    assert b"<svg" in svg
    assert value.encode() not in svg


def _projection_manager(tmp_path, handler, *, interval_seconds=120.0):
    installation_id = "b657d60d-2a38-4a66-bf21-20d7bb1bb13f"
    device_id = "35f29378-4912-4a76-a99d-197361226ca7"
    organization_id = "c10c7a58-b338-4194-a6a2-693bf1d54c9e"
    core_user_id = "b8696bee-d730-46b6-848c-e41f1f96a0b4"
    member_user_id = "9df2aa2a-b029-4d10-a9e1-805db637e595"
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    identities = IdentityRepository(database)
    identities.bind_installation(
        installation_id=installation_id,
        cloud_device_id=device_id,
        organization_id=organization_id,
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id=core_user_id,
        billing_account_id="71c8e42b-f8a6-49f1-b618-76b9e20c0510",
        access_epoch=7,
        core_membership_epoch=2,
    )
    identities.upsert_membership(
        cloud_user_id=member_user_id,
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=4,
    )
    backend = MemorySecretBackend()
    secret_key = f"ai2apps-remote-connector-{device_id}"
    backend.store(secret_key, "connector-secret")
    repository = RemoteDeviceRepository(database)
    repository.upsert(
        {
            "id": device_id,
            "displayName": "Test Mac",
            "platform": "macos-arm64",
            "clientVersion": "1",
            "status": "active",
            "suspensionReason": None,
            "accessEpoch": 7,
            "publicOrigin": "https://device-test.ai2apps.com",
            "credentialExpiresAt": "2026-11-12T08:00:00Z",
            "createdAt": "2026-08-14T08:00:00Z",
        },
        {
            "credentialVersion": 1,
            "credentialExpiresAt": "2026-11-12T08:00:00Z",
            "serverAddr": "frpc.ai2apps.com",
            "serverPort": 7000,
            "proxyName": f"device-{device_id}",
            "subdomain": "device-test",
        },
        secret_backend_key=secret_key,
    )
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    manager = RemoteAccessManager(
        cloud=cloud,
        repository=repository,
        secret_backend=backend,
        client_version="1",
        identity_repository=identities,
        access_projection_interval_seconds=interval_seconds,
    )
    return manager, identities, cloud, {
        "installation_id": installation_id,
        "device_id": device_id,
        "organization_id": organization_id,
        "core_user_id": core_user_id,
        "member_user_id": member_user_id,
    }


@pytest.mark.asyncio
async def test_access_projection_uses_etag_and_revokes_changed_member(tmp_path):
    requests = []

    def handler(request: httpx.Request):
        requests.append(request)
        if len(requests) == 2:
            assert request.headers["if-none-match"] == '"auth-7-12"'
            return httpx.Response(304)
        return httpx.Response(
            200,
            headers={"etag": '"auth-7-12"'},
            json={
                "installationId": ids["installation_id"],
                "cloudDeviceId": ids["device_id"],
                "deviceStatus": "active",
                "accessEpoch": 7,
                "localSessionEpoch": 1,
                "organizationId": ids["organization_id"],
                "authorizationVersion": 12,
                "memberships": [
                    {
                        "userId": ids["core_user_id"],
                        "status": "active",
                        "role": "core",
                        "membershipEpoch": 2,
                        "accountSessionEpoch": 1,
                    },
                    {
                        "userId": ids["member_user_id"],
                        "status": "active",
                        "role": "guest",
                        "membershipEpoch": 5,
                        "accountSessionEpoch": 1,
                    },
                ],
                "checkedAt": "2026-08-16T00:00:00.000Z",
            },
        )

    manager, identities, cloud, ids = _projection_manager(tmp_path, handler)
    core_token, _ = identities.create_local_session(ids["core_user_id"])
    member_token, _ = identities.create_local_session(ids["member_user_id"])

    assert await manager.refresh_access_projection() is True
    assert identities.authorize_local_session(core_token) is not None
    assert identities.authorize_local_session(member_token) is None
    assert identities.principal_for(ids["member_user_id"]).role is MemberRole.GUEST
    assert await manager.refresh_access_projection() is False
    assert requests[0].headers["authorization"].startswith(
        f"Device {ids['device_id']}."
    )
    await cloud.close()


@pytest.mark.asyncio
async def test_access_projection_refreshes_on_startup_and_periodically(tmp_path):
    request_count = 0

    def handler(_request: httpx.Request):
        nonlocal request_count
        request_count += 1
        if request_count > 1:
            return httpx.Response(304)
        return httpx.Response(
            200,
            headers={"etag": '"auth-7-1"'},
            json={
                "installationId": ids["installation_id"],
                "cloudDeviceId": ids["device_id"],
                "deviceStatus": "active",
                "accessEpoch": 7,
                "organizationId": ids["organization_id"],
                "authorizationVersion": 1,
                "memberships": [
                    {
                        "userId": ids["core_user_id"],
                        "status": "active",
                        "role": "core",
                        "membershipEpoch": 2,
                    },
                    {
                        "userId": ids["member_user_id"],
                        "status": "active",
                        "role": "member",
                        "membershipEpoch": 4,
                    },
                ],
                "checkedAt": "2026-08-16T00:00:00.000Z",
            },
        )

    manager, _identities, cloud, ids = _projection_manager(
        tmp_path, handler, interval_seconds=0.01
    )

    await manager.startup()
    await asyncio.sleep(0.035)
    await manager.shutdown()

    assert request_count >= 2
    await cloud.close()


@pytest.mark.asyncio
async def test_projection_transport_failure_keeps_last_known_local_access(tmp_path):
    def handler(_request: httpx.Request):
        raise httpx.ConnectError("offline")

    manager, identities, cloud, ids = _projection_manager(tmp_path, handler)
    member_token, _ = identities.create_local_session(ids["member_user_id"])

    with pytest.raises(httpx.ConnectError):
        await manager.refresh_access_projection()

    assert identities.authorize_local_session(member_token) is not None
    assert identities.get_installation().status == "active"
    await cloud.close()


@pytest.mark.asyncio
async def test_definitive_device_revoke_invalidates_all_local_sessions(tmp_path):
    def handler(_request: httpx.Request):
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": "DEVICE_REVOKED",
                    "message": "device authorization was revoked",
                }
            },
        )

    manager, identities, cloud, ids = _projection_manager(tmp_path, handler)
    core_token, _ = identities.create_local_session(ids["core_user_id"])
    member_token, _ = identities.create_local_session(ids["member_user_id"])

    with pytest.raises(RemoteAccessError, match="device authorization was revoked"):
        await manager.refresh_access_projection()

    assert identities.get_installation().status == "revoked"
    assert identities.authorize_local_session(core_token) is None
    assert identities.authorize_local_session(member_token) is None
    await cloud.close()


@pytest.mark.asyncio
async def test_stable_device_authorization_denial_invalidates_local_sessions(tmp_path):
    def handler(_request: httpx.Request):
        return httpx.Response(
            403,
            json={
                "error": {
                    "code": "REMOTE_DEVICE_AUTHORIZATION_DENIED",
                    "message": "device authorization was denied",
                }
            },
        )

    manager, identities, cloud, ids = _projection_manager(tmp_path, handler)
    token, _ = identities.create_local_session(ids["core_user_id"])

    with pytest.raises(RemoteAccessError, match="device authorization was denied"):
        await manager.refresh_access_projection()

    assert identities.get_installation().status == "suspended"
    assert identities.authorize_local_session(token) is None
    await cloud.close()


def test_pairing_url_uses_the_account_api_origin():
    value = "https://coder.ai2apps.com/mobile/pair#challenge=opaque-one-use-value"
    assert RemoteAccessManager._canonical_pairing_url(value) == value


def test_legacy_pairing_url_is_safely_migrated_to_the_account_api_origin():
    legacy = "https://ai2apps.com/mobile/pair#challenge=opaque-one-use-value"
    assert RemoteAccessManager._canonical_pairing_url(legacy) == (
        "https://coder.ai2apps.com/mobile/pair#challenge=opaque-one-use-value"
    )


@pytest.mark.asyncio
async def test_pairing_challenge_normalizes_legacy_cloud_response_before_qr_rendering():
    manager = RemoteAccessManager.__new__(RemoteAccessManager)
    manager.require_device = lambda device_id: type("Device", (), {"enabled": True})()
    manager.frpc = type(
        "Frpc",
        (),
        {"status": lambda self: {"running": True, "deviceId": "device-1"}},
    )()
    manager.repository = type(
        "Repository",
        (),
        {"update_cloud_state": lambda self, device: type("Device", (), {"proxy_connected": True})()},
    )()

    async def request(method, path, *, cloud=None):
        assert cloud is None
        if method == "GET":
            assert path == "/v1/remote/devices/device-1"
            return {"id": "device-1", "proxyConnected": True}
        assert method == "POST"
        assert path == "/v1/remote/devices/device-1/pairing-challenges"
        return {
            "pairingUrl": "https://ai2apps.com/mobile/pair#challenge=opaque-one-use-value",
            "expiresAt": "2026-08-15T03:05:00Z",
        }

    manager._request = request
    result = await manager.pairing_challenge("device-1")

    assert result["pairingUrl"] == (
        "https://coder.ai2apps.com/mobile/pair#challenge=opaque-one-use-value"
    )


@pytest.mark.parametrize("value", [
    "http://coder.ai2apps.com/mobile/pair#challenge=opaque",
    "https://coder.ai2apps.com:443/mobile/pair#challenge=opaque",
    "https://coder.ai2apps.com.evil.test/mobile/pair#challenge=opaque",
    "https://coder.ai2apps.com/mobile/pair?challenge=opaque",
    "https://coder.ai2apps.com/mobile/pair#challenge=opaque&next=evil",
    "https://coder.ai2apps.com/mobile/other#challenge=opaque",
])
def test_pairing_url_rejects_values_outside_the_remote_access_policy(value):
    with pytest.raises(RemoteAccessError, match="outside the Remote Access v1 policy"):
        RemoteAccessManager._canonical_pairing_url(value)


@pytest.mark.asyncio
async def test_revoked_remote_identity_cannot_be_started_again():
    manager = RemoteAccessManager.__new__(RemoteAccessManager)
    manager.require_device = lambda device_id: type("Device", (), {"status": "revoked"})()

    with pytest.raises(RemoteAccessError, match="register this Mac again") as raised:
        await manager.start("device-1")

    assert raised.value.status_code == 409
    assert raised.value.code == "REMOTE_DEVICE_REVOKED"


@pytest.mark.asyncio
async def test_phone_pairing_requires_a_running_connector():
    manager = RemoteAccessManager.__new__(RemoteAccessManager)
    manager.require_device = lambda device_id: type(
        "Device", (), {"enabled": False}
    )()
    manager.frpc = type(
        "Frpc", (), {"status": lambda self: {"running": False, "deviceId": None}}
    )()

    with pytest.raises(RemoteAccessError, match="wait for the connector") as raised:
        await manager.pairing_challenge("device-1")

    assert raised.value.status_code == 409
    assert raised.value.code == "REMOTE_CONNECTOR_NOT_RUNNING"


def test_remote_frpc_config_uses_the_shipped_pinned_ca(tmp_path, monkeypatch):
    binary = tmp_path / "frpc"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o700)
    monkeypatch.setenv("AI2APPS_FRP_BINARY", str(binary))
    monkeypatch.delenv("AI2APPS_FRP_CA_FILE", raising=False)

    config = RemoteFrpcConfig.from_environment(tmp_path / "runtime")

    assert config is not None
    assert config.ca_file.name == "frp-ca-2026.pem"
    assert hashlib.sha256(config.ca_file.read_bytes()).hexdigest() == PINNED_FRP_CA_SHA256


def test_bundled_frpc_binaries_match_pinned_digests_and_architectures():
    binary_root = frpc_module.Path(frpc_module.__file__).with_name("bin")
    expected_cpu_types = {
        "darwin-arm64": 0x0100000C,
        "darwin-x86_64": 0x01000007,
    }

    assert set(PINNED_FRP_BINARY_SHA256) == set(expected_cpu_types)
    for platform_key, expected_digest in PINNED_FRP_BINARY_SHA256.items():
        binary = binary_root / platform_key / "frpc"
        content = binary.read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected_digest
        assert content[:4] == b"\xcf\xfa\xed\xfe"
        assert int.from_bytes(content[4:8], "little") == expected_cpu_types[platform_key]
        assert binary.stat().st_mode & 0o100


def test_bundled_frpc_discovery_fails_closed_on_digest_mismatch(monkeypatch):
    platform_key = f"{frpc_module.platform.system().lower()}-{frpc_module.platform.machine().lower()}"
    expected_digest = PINNED_FRP_BINARY_SHA256.get(platform_key)
    if expected_digest is None:
        pytest.skip("current platform has no bundled frpc")

    monkeypatch.setitem(PINNED_FRP_BINARY_SHA256, platform_key, "0" * 64)
    assert frpc_module._bundled_binary() is None

    monkeypatch.setitem(PINNED_FRP_BINARY_SHA256, platform_key, expected_digest)
    assert frpc_module._bundled_binary() is not None


def test_remote_frpc_config_rejects_an_unpinned_ca(tmp_path, monkeypatch):
    binary = tmp_path / "frpc"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o700)
    ca_file = tmp_path / "wrong-ca.pem"
    ca_file.write_text("not the release CA", encoding="utf-8")
    monkeypatch.setenv("AI2APPS_FRP_BINARY", str(binary))
    monkeypatch.setenv("AI2APPS_FRP_CA_FILE", str(ca_file))

    with pytest.raises(ValueError, match="fingerprint"):
        RemoteFrpcConfig.from_environment(tmp_path / "runtime")


def test_remote_frpc_config_does_not_require_a_global_bootstrap_secret(
    tmp_path, monkeypatch
):
    runtime = tmp_path / "remote"
    binary = runtime / "bin" / "frpc"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o700)
    for name in ("AI2APPS_FRP_BINARY", "AI2APPS_FRP_CA_FILE"):
        monkeypatch.delenv(name, raising=False)

    config = RemoteFrpcConfig.from_environment(runtime)

    assert config is not None
    assert config.binary == binary.resolve()
    assert not hasattr(config, "bootstrap_token")


def test_remote_frpc_template_uses_only_the_rotatable_device_credential():
    template = frpc_module.Path(frpc_module.__file__).with_name(
        "frpc-device.toml"
    ).read_text(encoding="utf-8")

    assert 'user = "{{ .Envs.AI2APPS_REMOTE_DEVICE_ID }}"' in template
    assert "metadatas.connectorSecret" in template
    assert 'metadatas.authProtocol = "device-credential-v1"' in template
    assert "AI2APPS_FRP_BOOTSTRAP_TOKEN" not in template
    assert "auth.token =" not in template


def test_remote_frpc_diagnostic_redacts_connector_secret():
    value = RemoteFrpcSupervisor._safe_diagnostic(
        "login failed: connectorSecret=very-secret-value", "very-secret-value"
    )

    assert "very-secret-value" not in value
    assert "[REDACTED]" in value


def test_remote_frpc_diagnostic_removes_volatile_frpc_prefix():
    value = RemoteFrpcSupervisor._safe_diagnostic(
        "2026-08-19 02:33:06.598 [E] [client/control.go:154] "
        "[run-id] StartWorkConn contains error: invalid NewWorkConn",
        "connector-secret",
    )

    assert value == "StartWorkConn contains error: invalid NewWorkConn"


def test_remote_frpc_diagnostic_keeps_new_proxy_as_root_cause():
    assert RemoteFrpcSupervisor._diagnostic_priority(
        "start error: new proxy authorization denied"
    ) > RemoteFrpcSupervisor._diagnostic_priority(
        "pong message contains error: invalid ping"
    )


@pytest.mark.asyncio
async def test_remote_frpc_diagnostic_surfaces_retrying_login_failure():
    supervisor = RemoteFrpcSupervisor(None, MemorySecretBackend())
    stream = asyncio.StreamReader()
    stream.feed_data(
        b"[W] login to server failed: authorization denied for device\n"
    )
    stream.feed_eof()

    await supervisor._drain_output(stream, "connector-secret")

    assert "authorization denied" in supervisor.last_error


@pytest.mark.parametrize(
    "credential",
    [
        {"deviceId": "35f29378-4912-4a76-a99d-197361226ca8", "credentialVersion": 1,
         "secret": "valid-device-secret-value"},
        {"deviceId": "35f29378-4912-4a76-a99d-197361226ca7", "credentialVersion": 0,
         "secret": "valid-device-secret-value"},
        {"deviceId": "35f29378-4912-4a76-a99d-197361226ca7", "credentialVersion": True,
         "secret": "valid-device-secret-value"},
        {"deviceId": "35F29378-4912-4A76-A99D-197361226CA7", "credentialVersion": 1,
         "secret": "valid-device-secret-value"},
        {"deviceId": "35f29378-4912-4a76-a99d-197361226ca7", "credentialVersion": 1,
         "secret": 'value-that-injects\"\nauth.token=\"x'},
    ],
)
def test_remote_connector_credential_is_validated_before_frpc_use(
    credential
):
    with pytest.raises(RemoteAccessError, match="invalid connector credential"):
        RemoteAccessManager._validate_credential(
            "35f29378-4912-4a76-a99d-197361226ca7", credential
        )


@pytest.mark.asyncio
async def test_enabled_remote_connector_stops_before_credential_expiry():
    stopped = []
    device = type(
        "Device",
        (),
        {
            "enabled": True,
            "status": "active",
            "credential_expires_at": utc_now() + timedelta(days=1),
        },
    )()
    manager = RemoteAccessManager.__new__(RemoteAccessManager)
    manager.repository = type("Devices", (), {"list": lambda self: (device,)})()

    class Frpc:
        last_error = ""

        async def stop(self):
            stopped.append(True)

    manager.frpc = Frpc()

    assert await manager._enforce_connector_credential_lifetime() is True
    assert stopped == [True]
    assert "expires within seven days" in manager.frpc.last_error


@pytest.mark.asyncio
async def test_remote_registration_keeps_connector_secret_out_of_sqlite(tmp_path):
    captured = []

    def handler(request: httpx.Request):
        captured.append(
            (
                request.method,
                request.url.path,
                request.headers.get("x-owner-reauth-grant"),
                request.headers.get("idempotency-key"),
                json.loads(request.content),
            )
        )
        if request.url.path == "/v1/remote/devices":
            return httpx.Response(201, json={
                "device": {
                    "id": "35f29378-4912-4a76-a99d-197361226ca7",
                    "displayName": "Test Mac", "platform": "macos-arm64",
                    "clientVersion": "1.0.0", "status": "active",
                    "suspensionReason": None, "accessEpoch": 1,
                    "publicOrigin": "https://device-0123456789abcdef0123456789abcdef.ai2apps.com",
                    "credentialExpiresAt": "2026-11-12T08:00:00Z",
                    "online": False, "proxyConnected": False, "lastSeenAt": None,
                    "createdAt": "2026-08-14T08:00:00Z",
                },
                "connector": {
                    "serverAddr": "frpc.ai2apps.com", "serverPort": 7000,
                    "proxyType": "http", "proxyName": "device-35f29378-4912-4a76-a99d-197361226ca7",
                    "subdomain": "device-0123456789abcdef0123456789abcdef",
                    "deviceId": "35f29378-4912-4a76-a99d-197361226ca7",
                    "credentialVersion": 1, "credentialExpiresAt": "2026-11-12T08:00:00Z",
                    "secret": "super-secret-connector-value-that-never-enters-sqlite",
                },
            })
        raise AssertionError(request.url.path)

    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    manager = RemoteAccessManager(
        cloud=cloud, repository=RemoteDeviceRepository(database),
        secret_backend=backend, client_version="1.0.0",
    )
    organization_id = "c10c7a58-b338-4194-a6a2-693bf1d54c9e"
    device = await manager.register(
        display_name="Test Mac",
        organization_id=organization_id,
        owner_reauth_grant="one-use-owner-grant",
        idempotency_key="8664f478-19a2-42f0-a6f4-93497fbd0d15",
    )
    assert device.public_origin.endswith(".ai2apps.com")
    assert backend.load(device.secret_backend_key).startswith("super-secret")
    assert b"super-secret-connector" not in database.path.read_bytes()
    assert captured == [
        (
            "POST",
            "/v1/remote/devices",
            "one-use-owner-grant",
            "8664f478-19a2-42f0-a6f4-93497fbd0d15",
            {
                "displayName": "Test Mac",
                "platform": "macos-arm64",
                "clientVersion": "1.0.0",
                "organizationId": organization_id,
            },
        )
    ]
    await cloud.close()


@pytest.mark.asyncio
async def test_remote_registration_binds_cloud_installation_identity(tmp_path):
    device_id = "35f29378-4912-4a76-a99d-197361226ca7"
    installation_id = "b657d60d-2a38-4a66-bf21-20d7bb1bb13f"
    organization_id = "c10c7a58-b338-4194-a6a2-693bf1d54c9e"
    core_user_id = "9df2aa2a-b029-4d10-a9e1-805db637e595"
    billing_id = "71c8e42b-f8a6-49f1-b618-76b9e20c0510"

    def handler(request: httpx.Request):
        if request.url.path == "/v1/remote/devices":
            return httpx.Response(201, json={
                "device": {
                    "id": device_id, "displayName": "Family NAS",
                    "platform": "macos-arm64", "clientVersion": "1.0.0",
                    "status": "active", "suspensionReason": None,
                    "accessEpoch": 3,
                    "publicOrigin": "https://device-0123456789abcdef0123456789abcdef.ai2apps.com",
                    "credentialExpiresAt": "2026-11-12T08:00:00Z",
                    "online": False, "proxyConnected": False,
                    "lastSeenAt": None, "createdAt": "2026-08-14T08:00:00Z",
                },
                "installation": {
                    "installationId": installation_id,
                    "organizationId": organization_id,
                    "billingAccountId": billing_id,
                    "accessEpoch": 3,
                },
                "connector": {
                    "serverAddr": "frpc.ai2apps.com", "serverPort": 7000,
                    "proxyType": "http", "proxyName": f"device-{device_id}",
                    "subdomain": "device-0123456789abcdef0123456789abcdef",
                    "deviceId": device_id, "credentialVersion": 1,
                    "credentialExpiresAt": "2026-11-12T08:00:00Z",
                    "secret": "installation-device-secret",
                },
            })
        if request.url.path == f"/v1/installations/{installation_id}":
            return httpx.Response(200, json={
                "installationId": installation_id, "cloudDeviceId": device_id,
                "organizationId": organization_id,
                "organizationType": "household", "organizationName": "Family",
                "billingAccountId": billing_id, "coreUserId": core_user_id,
                "status": "active", "accessEpoch": 3, "role": "core",
                "membershipEpoch": 2,
            })
        raise AssertionError(request.url.path)

    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    identities = IdentityRepository(database)
    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    manager = RemoteAccessManager(
        cloud=cloud,
        repository=RemoteDeviceRepository(database),
        secret_backend=backend,
        client_version="1.0.0",
        identity_repository=identities,
    )

    await manager.register(display_name="Family NAS")

    installation = identities.get_installation()
    principal = identities.principal_for(core_user_id)
    assert installation is not None
    assert installation.id == installation_id
    assert installation.cloud_device_id == device_id
    assert principal.role is MemberRole.CORE
    assert principal.membership_epoch == 2
    headers = manager.cloud_ai_headers(device_id=device_id, principal=principal)
    assert headers["Authorization"] == f"Device {device_id}.installation-device-secret"
    assert headers["X-AI2Apps-Actor-User-Id"] == core_user_id
    assert headers["X-AI2Apps-Membership-Epoch"] == "2"
    await cloud.close()


@pytest.mark.asyncio
async def test_reconcile_backfills_installation_for_existing_active_device():
    device_id = "35f29378-4912-4a76-a99d-197361226ca7"
    device = type("Device", (), {"device_id": device_id})()
    manager = RemoteAccessManager.__new__(RemoteAccessManager)
    manager.identity_repository = type(
        "Identities", (), {"get_installation": lambda self: None}
    )()
    manager.repository = type(
        "Devices",
        (),
        {
            "list": lambda self: (device,),
            "update_cloud_state": lambda self, value: device,
        },
    )()
    synchronized = []

    async def request(method, path, *, cloud=None):
        assert cloud is None
        assert (method, path) == ("GET", "/v1/remote/devices")
        return {"items": [{"id": device_id, "status": "active"}]}

    async def sync(*, device_id, cloud=None):
        assert cloud is None
        synchronized.append(device_id)

    manager._request = request
    manager.sync_installation_identity = sync

    result = await manager.reconcile()

    assert result == (device,)
    assert synchronized == [device_id]


@pytest.mark.asyncio
async def test_ambiguous_remote_registration_is_reconciled_and_rotated(tmp_path, monkeypatch):
    device_id = "35f29378-4912-4a76-a99d-197361226ca7"
    requests = []

    def handler(request: httpx.Request):
        requests.append((request.method, request.url.path))
        if requests == [("POST", "/v1/remote/devices")]:
            raise httpx.ReadTimeout("create response was lost", request=request)
        if request.method == "GET" and request.url.path == "/v1/remote/devices":
            return httpx.Response(200, json={"items": [{
                "id": device_id, "displayName": "Recovered Mac",
                "platform": "macos-arm64", "clientVersion": "1.0.0",
                "status": "active", "suspensionReason": None, "accessEpoch": 1,
                "publicOrigin": "https://device-0123456789abcdef0123456789abcdef.ai2apps.com",
                "credentialExpiresAt": "2026-11-12T08:00:00Z",
                "online": False, "proxyConnected": False, "lastSeenAt": None,
                "createdAt": "2026-08-14T08:00:00Z",
            }]})
        if request.method == "POST" and request.url.path.endswith("/credentials/rotate"):
            return httpx.Response(200, json={
                "deviceId": device_id, "credentialVersion": 2,
                "credentialExpiresAt": "2026-11-12T08:00:00Z",
                "secret": "recovered-secret-that-is-long-enough-for-the-contract",
            })
        raise AssertionError(request.url.path)

    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    manager = RemoteAccessManager(
        cloud=cloud, repository=RemoteDeviceRepository(database),
        secret_backend=backend, client_version="1.0.0",
    )
    monkeypatch.setattr(manager, "_platform_name", lambda: "macos-arm64")

    device = await manager.register(display_name="Recovered Mac")

    assert device.device_id == device_id
    assert device.credential_version == 2
    assert backend.load(device.secret_backend_key).startswith("recovered-secret")
    await cloud.close()


@pytest.mark.asyncio
async def test_handoff_exchange_creates_http_only_local_session_material(tmp_path):
    key = Ed25519PrivateKey.generate()
    now = int(utc_now().timestamp())
    device_id = "35f29378-4912-4a76-a99d-197361226ca7"
    token = _jwt(key, {
        "iss": "ai2apps-cloud", "aud": "ai2apps-remote-mobile-v1",
        "sub": "user-1", "device_id": device_id, "access_epoch": 1,
        "iat": now, "exp": now + 300, "jti": "token-1",
    })

    def handler(request: httpx.Request):
        if request.url.path == "/v1/internal/remote/mobile/exchange":
            assert request.headers["authorization"].startswith(f"Device {device_id}.")
            return httpx.Response(200, json={"accessToken": token, "tokenType": "Bearer", "expiresIn": 300, "deviceId": device_id, "accessEpoch": 1})
        if request.url.path == "/v1/remote/jwks.json":
            return httpx.Response(200, json=_jwks(key))
        raise AssertionError(request.url.path)

    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    identities = IdentityRepository(database)
    identities.bind_installation(
        installation_id="installation-1",
        cloud_device_id=device_id,
        organization_id="organization-1",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="user-1",
        billing_account_id="billing-1",
        access_epoch=1,
    )
    backend = MemorySecretBackend()
    repository = RemoteDeviceRepository(database)
    backend.store(f"ai2apps-remote-connector-{device_id}", "connector-secret")
    repository.upsert({
        "id": device_id, "displayName": "Test Mac", "platform": "macos-arm64",
        "clientVersion": "1", "status": "active", "suspensionReason": None,
        "accessEpoch": 1, "publicOrigin": "https://device-0123456789abcdef0123456789abcdef.ai2apps.com",
        "credentialExpiresAt": "2026-11-12T08:00:00Z", "createdAt": "2026-08-14T08:00:00Z",
    }, {
        "credentialVersion": 1, "credentialExpiresAt": "2026-11-12T08:00:00Z",
        "serverAddr": "frpc.ai2apps.com", "serverPort": 7000,
        "proxyName": f"device-{device_id}", "subdomain": "device-0123456789abcdef0123456789abcdef",
    }, secret_backend_key=f"ai2apps-remote-connector-{device_id}")
    cloud = AI2AppsCloudClient(base_url="https://coder.ai2apps.test", session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"), transport=httpx.MockTransport(handler))
    manager = RemoteAccessManager(
        cloud=cloud,
        repository=repository,
        secret_backend=backend,
        client_version="1",
        identity_repository=identities,
    )
    cookie, session = await manager.exchange_handoff(
        device_id=device_id,
        handoff="one-use-handoff",
        client_scope="mobile-browser-one",
    )
    assert cookie not in database.path.read_text(errors="ignore")
    assert (await manager.authorize_session(cookie)).owner_user_id == "user-1"
    assert session.expires_at - session.created_at == timedelta(minutes=15)
    assert session.local_session_token
    principal = manager.principal_for_mobile_session(session)
    assert principal.actor_user_id == "user-1"
    assert principal.client_scope == "mobile-browser-one"
    await cloud.close()


@pytest.mark.asyncio
async def test_member_handoff_creates_durable_local_member_session(tmp_path):
    key = Ed25519PrivateKey.generate()
    now = int(utc_now().timestamp())
    installation_id = "b657d60d-2a38-4a66-bf21-20d7bb1bb13f"
    device_id = "35f29378-4912-4a76-a99d-197361226ca7"
    organization_id = "c10c7a58-b338-4194-a6a2-693bf1d54c9e"
    core_user_id = "b8696bee-d730-46b6-848c-e41f1f96a0b4"
    actor_user_id = "9df2aa2a-b029-4d10-a9e1-805db637e595"
    token = _jwt(key, {
        "iss": "ai2apps-cloud",
        "aud": "ai2apps-installation-member-v1",
        "sub": actor_user_id,
        "jti": "member-token-2",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "installation_id": installation_id,
        "cloud_device_id": device_id,
        "organization_id": organization_id,
        "organization_type": "household",
        "role": "member",
        "membership_epoch": 4,
        "access_epoch": 7,
    }, kid="installation-member-v1")

    def handler(request: httpx.Request):
        if request.url.path == f"/v1/installations/{installation_id}/member-handoffs":
            assert request.headers.get("authorization", "").startswith("Device ") is False
            assert json.loads(request.content) == {"target": "lan_desktop"}
            return httpx.Response(201, json={
                "redirectUrl": "ai2apps://auth/complete#handoff=one-use-member-handoff-value",
                "expiresAt": "2026-08-16T03:00:00.000Z",
            })
        if request.url.path.endswith("/member-handoffs/exchange"):
            assert request.headers["authorization"].startswith(
                f"Device {device_id}."
            )
            return httpx.Response(200, json={
                "accessToken": token,
                "tokenType": "Bearer",
                "expiresIn": 300,
                "installationId": installation_id,
                "cloudDeviceId": device_id,
                "organizationId": organization_id,
                "role": "member",
                "membershipEpoch": 4,
                "accessEpoch": 7,
            })
        if request.url.path == "/v1/installation-auth/jwks.json":
            return httpx.Response(
                200, json=_jwks(key, kid="installation-member-v1")
            )
        raise AssertionError(request.url.path)

    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    identities = IdentityRepository(database)
    identities.bind_installation(
        installation_id=installation_id,
        cloud_device_id=device_id,
        organization_id=organization_id,
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id=core_user_id,
        billing_account_id="71c8e42b-f8a6-49f1-b618-76b9e20c0510",
        access_epoch=7,
    )
    backend = MemorySecretBackend()
    repository = RemoteDeviceRepository(database)
    secret_key = f"ai2apps-remote-connector-{device_id}"
    backend.store(secret_key, "connector-secret")
    repository.upsert({
        "id": device_id,
        "displayName": "Test Mac",
        "platform": "macos-arm64",
        "clientVersion": "1",
        "status": "active",
        "suspensionReason": None,
        "accessEpoch": 7,
        "publicOrigin": "https://device-0123456789abcdef0123456789abcdef.ai2apps.com",
        "credentialExpiresAt": "2026-11-12T08:00:00Z",
        "createdAt": "2026-08-14T08:00:00Z",
    }, {
        "credentialVersion": 1,
        "credentialExpiresAt": "2026-11-12T08:00:00Z",
        "serverAddr": "frpc.ai2apps.com",
        "serverPort": 7000,
        "proxyName": f"device-{device_id}",
        "subdomain": "device-0123456789abcdef0123456789abcdef",
    }, secret_backend_key=secret_key)
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    manager = RemoteAccessManager(
        cloud=cloud,
        repository=repository,
        secret_backend=backend,
        client_version="1",
        identity_repository=identities,
    )

    cookie, principal = await manager.exchange_member_handoff(
        handoff="one-use-member-handoff-value"
    )

    assert principal.actor_user_id == actor_user_id
    assert principal.role is MemberRole.MEMBER
    assert identities.authorize_local_session(cookie) == principal
    assert cookie not in database.path.read_text(errors="ignore")

    activated_cookie, activated_principal = (
        await manager.activate_current_cloud_member()
    )
    assert activated_principal == principal
    assert identities.authorize_local_session(activated_cookie) == principal
    await cloud.close()
