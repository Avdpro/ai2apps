import base64
import hashlib
import json
from datetime import timedelta

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.api.remote import _pairing_qr_data_url
from ai2apps.cloud_client import AI2AppsCloudClient, CloudSessionStore
from ai2apps.core import utc_now
from ai2apps.remote import (
    RemoteAccessError,
    RemoteAccessManager,
    RemoteDeviceRepository,
    RemoteTokenError,
    verify_remote_token,
)
from ai2apps.remote.frpc import PINNED_FRP_CA_SHA256, RemoteFrpcConfig
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


def test_pairing_qr_is_a_local_svg_data_url():
    value = "https://coder.ai2apps.com/mobile/pair#challenge=opaque-one-use-value"
    rendered = _pairing_qr_data_url(value)
    assert rendered.startswith("data:image/svg+xml;base64,")
    svg = base64.b64decode(rendered.split(",", 1)[1])
    assert b"<svg" in svg
    assert value.encode() not in svg


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

    async def request(method, path):
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
    monkeypatch.setenv("AI2APPS_FRP_BOOTSTRAP_TOKEN", "deployment-token")
    monkeypatch.delenv("AI2APPS_FRP_CA_FILE", raising=False)

    config = RemoteFrpcConfig.from_environment(tmp_path / "runtime")

    assert config is not None
    assert config.ca_file.name == "frp-ca-2026.pem"
    assert hashlib.sha256(config.ca_file.read_bytes()).hexdigest() == PINNED_FRP_CA_SHA256


def test_remote_frpc_config_rejects_an_unpinned_ca(tmp_path, monkeypatch):
    binary = tmp_path / "frpc"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o700)
    ca_file = tmp_path / "wrong-ca.pem"
    ca_file.write_text("not the release CA", encoding="utf-8")
    monkeypatch.setenv("AI2APPS_FRP_BINARY", str(binary))
    monkeypatch.setenv("AI2APPS_FRP_CA_FILE", str(ca_file))
    monkeypatch.setenv("AI2APPS_FRP_BOOTSTRAP_TOKEN", "deployment-token")

    with pytest.raises(ValueError, match="fingerprint"):
        RemoteFrpcConfig.from_environment(tmp_path / "runtime")


def test_remote_frpc_config_discovers_private_runtime_files(tmp_path, monkeypatch):
    runtime = tmp_path / "remote"
    binary = runtime / "bin" / "frpc"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o700)
    token = runtime / "bootstrap-token"
    token.write_text("deployment-token\n", encoding="utf-8")
    token.chmod(0o600)
    for name in (
        "AI2APPS_FRP_BINARY", "AI2APPS_FRP_CA_FILE",
        "AI2APPS_FRP_BOOTSTRAP_TOKEN", "AI2APPS_FRP_BOOTSTRAP_TOKEN_FILE",
    ):
        monkeypatch.delenv(name, raising=False)

    config = RemoteFrpcConfig.from_environment(runtime)

    assert config is not None
    assert config.binary == binary.resolve()
    assert config.bootstrap_token == "deployment-token"


@pytest.mark.asyncio
async def test_remote_registration_keeps_connector_secret_out_of_sqlite(tmp_path):
    captured = []

    def handler(request: httpx.Request):
        captured.append((request.method, request.url.path, request.headers.get("authorization")))
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
    device = await manager.register(display_name="Test Mac")
    assert device.public_origin.endswith(".ai2apps.com")
    assert backend.load(device.secret_backend_key).startswith("super-secret")
    assert b"super-secret-connector" not in database.path.read_bytes()
    await cloud.close()


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
    manager = RemoteAccessManager(cloud=cloud, repository=repository, secret_backend=backend, client_version="1")
    cookie, session = await manager.exchange_handoff(device_id=device_id, handoff="one-use-handoff")
    assert cookie not in database.path.read_text(errors="ignore")
    assert (await manager.authorize_session(cookie)).owner_user_id == "user-1"
    assert session.expires_at - session.created_at == timedelta(minutes=15)
    await cloud.close()
