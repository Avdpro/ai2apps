"""Remote Access v1 control plane used by the local runtime and Mobile Gateway."""

from __future__ import annotations

import platform
import re
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.core import utc_now
from ai2apps.secrets import SecretBackend

from .frpc import RemoteFrpcSupervisor
from .models import RemoteDeviceRecord, RemoteMobileSession
from .repository import RemoteDeviceRepository
from .security import ACCESS_CHECK_WINDOW, RemoteSessionStore, verify_remote_token

PAIRING_HOST = "coder.ai2apps.com"
LEGACY_PAIRING_HOST = "ai2apps.com"
PAIRING_PATH = "/mobile/pair"


class RemoteAccessError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class RemoteAccessManager:
    def __init__(
        self,
        *,
        cloud: AI2AppsCloudClient,
        repository: RemoteDeviceRepository,
        secret_backend: SecretBackend,
        client_version: str,
        frpc: RemoteFrpcSupervisor | None = None,
    ) -> None:
        self.cloud = cloud
        self.repository = repository
        self.secret_backend = secret_backend
        self.client_version = client_version
        self.sessions = RemoteSessionStore()
        self.frpc = frpc or RemoteFrpcSupervisor(None, secret_backend)

    @staticmethod
    async def _payload(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError:
            value = {}
        if response.status_code >= 400:
            error = value.get("error", {}) if isinstance(value, dict) else {}
            raise RemoteAccessError(
                response.status_code,
                str(error.get("code") or "REMOTE_REQUEST_FAILED"),
                str(error.get("message") or f"Remote request failed ({response.status_code})"),
            )
        if not isinstance(value, dict):
            raise RemoteAccessError(502, "REMOTE_RESPONSE_INVALID", "Cloud returned an invalid remote response")
        return value

    async def _request(self, method: str, path: str, *, json: Any | None = None, device: RemoteDeviceRecord | None = None) -> dict[str, Any]:
        headers = None
        if device is not None:
            try:
                secret = self.secret_backend.load(device.secret_backend_key)
            except KeyError as error:
                raise RemoteAccessError(409, "REMOTE_CREDENTIAL_MISSING", "Remote device credential is missing") from error
            headers = {"Authorization": f"Device {device.device_id}.{secret}"}
        response = await self.cloud.request(method, path, json=json, headers=headers)
        try:
            return await self._payload(response)
        finally:
            await response.aclose()

    @staticmethod
    def _secret_key(device_id: str) -> str:
        return f"ai2apps-remote-connector-{device_id}"

    @staticmethod
    def _platform_name() -> str:
        return "macos-arm64" if platform.system() == "Darwin" else platform.system().lower()

    @staticmethod
    def _validate_connector(device: dict[str, Any], connector: dict[str, Any]) -> None:
        device_id = str(device.get("id") or "")
        subdomain = str(connector.get("subdomain") or "")
        origin = urlparse(str(device.get("publicOrigin") or ""))
        expected_host = f"{subdomain}.ai2apps.com"
        if (
            connector.get("deviceId") != device_id
            or connector.get("serverAddr") != "frpc.ai2apps.com"
            or int(connector.get("serverPort", 0)) != 7000
            or connector.get("proxyType") != "http"
            or connector.get("proxyName") != f"device-{device_id}"
            or re.fullmatch(r"device-[0-9a-f]{32}", subdomain) is None
            or origin.scheme != "https"
            or origin.hostname != expected_host
            or origin.port is not None
            or origin.path not in {"", "/"}
            or origin.query
            or origin.fragment
        ):
            raise RemoteAccessError(
                502, "REMOTE_CONNECTOR_INVALID",
                "Cloud returned connector settings outside the Remote Access v1 policy",
            )

    async def _recover_registration(
        self, *, display_name: str, platform_name: str
    ) -> RemoteDeviceRecord:
        listed = await self._request("GET", "/v1/remote/devices")
        local_ids = {item.device_id for item in self.repository.list()}
        candidates = [
            item for item in listed.get("items", [])
            if item.get("id") not in local_ids
            and item.get("displayName") == display_name
            and item.get("platform") == platform_name
            and item.get("clientVersion") == self.client_version
            and item.get("status") == "active"
        ]
        if len(candidates) != 1:
            raise RemoteAccessError(
                409, "REMOTE_REGISTRATION_RECOVERY_REQUIRED",
                "Remote device creation was ambiguous; review the account device list",
            )
        device = candidates[0]
        credential = await self._request(
            "POST", f"/v1/remote/devices/{device['id']}/credentials/rotate"
        )
        public_host = urlparse(device["publicOrigin"]).hostname or ""
        connector = {
            **credential,
            "deviceId": device["id"],
            "serverAddr": "frpc.ai2apps.com",
            "serverPort": 7000,
            "proxyType": "http",
            "proxyName": f"device-{device['id']}",
            "subdomain": public_host.removesuffix(".ai2apps.com"),
        }
        return self._persist_registration(device, connector)

    def _persist_registration(
        self, device: dict[str, Any], connector_value: dict[str, Any]
    ) -> RemoteDeviceRecord:
        connector = dict(connector_value)
        self._validate_connector(device, connector)
        secret = connector.pop("secret", None)
        if not isinstance(secret, str) or not secret:
            raise RemoteAccessError(502, "REMOTE_CREDENTIAL_INVALID", "Cloud omitted the connector credential")
        key = self._secret_key(device["id"])
        self.secret_backend.store(key, secret)
        try:
            return self.repository.upsert(device, connector, secret_backend_key=key)
        except Exception:
            self.secret_backend.delete(key)
            raise

    async def register(self, *, display_name: str) -> RemoteDeviceRecord:
        platform_name = self._platform_name()
        try:
            payload = await self._request("POST", "/v1/remote/devices", json={
                "displayName": display_name,
                "platform": platform_name,
                "clientVersion": self.client_version,
            })
        except (httpx.TimeoutException, httpx.TransportError):
            return await self._recover_registration(
                display_name=display_name, platform_name=platform_name
            )
        device, connector = payload["device"], payload["connector"]
        return self._persist_registration(device, connector)

    async def reconcile(self) -> tuple[RemoteDeviceRecord, ...]:
        payload = await self._request("GET", "/v1/remote/devices")
        local = {item.device_id: item for item in self.repository.list()}
        for device in payload.get("items", []):
            if device.get("id") in local:
                self.repository.update_cloud_state(device)
        return self.repository.list()

    async def rotate(self, device_id: str) -> RemoteDeviceRecord:
        device = self.require_device(device_id)
        restart_after_rotation = device.enabled
        await self.stop(device_id)
        try:
            payload = await self._request("POST", f"/v1/remote/devices/{device_id}/credentials/rotate")
        except (httpx.TimeoutException, httpx.TransportError):
            payload = await self._request("POST", f"/v1/remote/devices/{device_id}/credentials/rotate")
        self.secret_backend.store(device.secret_backend_key, payload["secret"])
        record = self.repository.update_credential(device_id, payload)
        assert record is not None
        if restart_after_rotation:
            await self.frpc.start(record)
            restarted = self.repository.set_enabled(device_id, True)
            assert restarted is not None
            return restarted
        return record

    async def pairing_challenge(self, device_id: str) -> dict[str, Any]:
        device = self.require_device(device_id)
        connector = self.frpc.status()
        if (
            not device.enabled
            or not connector.get("running")
            or connector.get("deviceId") != device_id
        ):
            raise RemoteAccessError(
                409,
                "REMOTE_CONNECTOR_NOT_RUNNING",
                "Start Remote Access and wait for the connector to be online before pairing",
            )
        cloud_device = await self._request("GET", f"/v1/remote/devices/{device_id}")
        refreshed = self.repository.update_cloud_state(cloud_device)
        if refreshed is None or not refreshed.proxy_connected:
            raise RemoteAccessError(
                409,
                "REMOTE_CONNECTOR_NOT_ONLINE",
                "Wait for the Remote Access indicator to turn green before pairing",
            )
        payload = await self._request("POST", f"/v1/remote/devices/{device_id}/pairing-challenges")
        pairing_url = str(payload.get("pairingUrl") or "")
        payload["pairingUrl"] = self._canonical_pairing_url(pairing_url)
        return payload

    @staticmethod
    def _canonical_pairing_url(pairing_url: str) -> str:
        parsed = urlparse(pairing_url)
        try:
            port = parsed.port
        except ValueError:
            port = -1
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {PAIRING_HOST, LEGACY_PAIRING_HOST}
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or parsed.path != PAIRING_PATH
            or parsed.params
            or parsed.query
            or re.fullmatch(r"challenge=[A-Za-z0-9._~-]+", parsed.fragment) is None
        ):
            raise RemoteAccessError(
                502, "REMOTE_PAIRING_URL_INVALID",
                "Cloud returned a pairing URL outside the Remote Access v1 policy",
            )
        return parsed._replace(netloc=PAIRING_HOST).geturl()

    async def usage(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/remote/usage")

    async def revoke(self, device_id: str) -> dict[str, Any]:
        self.require_device(device_id)
        await self.stop(device_id)
        payload = await self._request("POST", f"/v1/remote/devices/{device_id}/revoke")
        self.repository.set_enabled(device_id, False)
        self.sessions.revoke_device(device_id)
        await self.reconcile()
        return payload

    async def start(self, device_id: str) -> RemoteDeviceRecord:
        device = self.require_device(device_id)
        if device.status == "revoked":
            raise RemoteAccessError(
                409,
                "REMOTE_DEVICE_REVOKED",
                "Revoked device identities cannot be started; register this Mac again",
            )
        cloud_device = await self._request("GET", f"/v1/remote/devices/{device_id}")
        refreshed = self.repository.update_cloud_state(cloud_device)
        if refreshed is not None:
            device = refreshed
        if device.credential_expires_at <= utc_now() + timedelta(days=7):
            raise RemoteAccessError(
                409, "REMOTE_CREDENTIAL_ROTATION_REQUIRED",
                "Remote connector credential expires within seven days; rotate it before starting",
            )
        await self.frpc.start(device)
        record = self.repository.set_enabled(device_id, True)
        assert record is not None
        return record

    async def stop(self, device_id: str | None = None) -> RemoteDeviceRecord | None:
        await self.frpc.stop()
        if device_id is None:
            return None
        self.sessions.revoke_device(device_id)
        return self.repository.set_enabled(device_id, False)

    async def startup(self) -> None:
        enabled = next((item for item in self.repository.list() if item.enabled and item.status == "active"), None)
        if enabled is not None and self.frpc.available:
            await self.frpc.start(enabled)

    async def shutdown(self) -> None:
        await self.frpc.stop()
        self.sessions.clear()

    async def redact(self, device_id: str) -> None:
        device = self.require_device(device_id)
        response = await self.cloud.request("DELETE", f"/v1/remote/devices/{device_id}")
        try:
            if response.status_code >= 400:
                await self._payload(response)
        finally:
            await response.aclose()
        self.secret_backend.delete(device.secret_backend_key)
        self.repository.delete(device_id)

    def require_device(self, device_id: str) -> RemoteDeviceRecord:
        device = self.repository.get(device_id)
        if device is None:
            raise RemoteAccessError(404, "REMOTE_DEVICE_NOT_FOUND", "Remote device is not registered locally")
        return device

    async def exchange_handoff(self, *, device_id: str, handoff: str) -> tuple[str, RemoteMobileSession]:
        device = self.require_device(device_id)
        token_payload = await self._request(
            "POST", "/v1/internal/remote/mobile/exchange",
            json={"handoff": handoff}, device=device,
        )
        jwks = await self._request("GET", "/v1/remote/jwks.json")
        claims = verify_remote_token(
            token_payload["accessToken"], jwks, device_id=device_id,
            access_epoch=int(token_payload["accessEpoch"]),
        )
        return self.sessions.create(
            device_id=device_id, owner_user_id=claims["sub"],
            access_epoch=int(claims["access_epoch"]),
        )

    async def authorize_session(self, token: str | None) -> RemoteMobileSession | None:
        session = self.sessions.get(token)
        if session is None:
            return None
        if utc_now() - session.last_access_check_at < ACCESS_CHECK_WINDOW:
            return session
        device = self.repository.get(session.device_id)
        if device is None:
            self.sessions.revoke_device(session.device_id)
            return None
        try:
            access = await self._request(
                "GET", f"/v1/internal/remote/devices/{session.device_id}/access",
                device=device,
            )
        except (RemoteAccessError, httpx.HTTPError):
            self.sessions.revoke_device(session.device_id)
            return None
        if access.get("status") != "active" or int(access.get("accessEpoch", 0)) != session.access_epoch:
            self.sessions.revoke_device(session.device_id)
            return None
        return self.sessions.checked(session)
