"""Remote Access v1 control plane used by the local runtime and Mobile Gateway."""

from __future__ import annotations

import asyncio
import logging
import platform
import re
from contextlib import suppress
from dataclasses import replace
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.core import utc_now
from ai2apps.identity import (
    IdentityBindingError,
    IdentityRepository,
    MemberRole,
    OrganizationType,
    RequestPrincipal,
)
from ai2apps.secrets import SecretBackend

from .frpc import RemoteFrpcSupervisor
from .models import RemoteDeviceRecord, RemoteMobileSession
from .repository import RemoteDeviceRepository
from .security import (
    ACCESS_CHECK_WINDOW,
    MOBILE_SESSION_LIFETIME,
    RemoteSessionStore,
    verify_installation_member_token,
    verify_remote_token,
)

PAIRING_HOST = "coder.ai2apps.com"
LEGACY_PAIRING_HOST = "ai2apps.com"
PAIRING_PATH = "/mobile/pair"
ACCESS_PROJECTION_REFRESH_SECONDS = 120.0
CONNECTOR_SECRET_PATTERN = re.compile(r"[A-Za-z0-9_-]{20,256}")
CONNECTOR_ROTATION_WINDOW = timedelta(days=7)
CONNECTOR_ROTATION_REQUIRED = (
    "Remote connector credential expires within seven days; rotate it before starting"
)

logger = logging.getLogger(__name__)


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
        identity_repository: IdentityRepository | None = None,
        access_projection_interval_seconds: float = ACCESS_PROJECTION_REFRESH_SECONDS,
    ) -> None:
        self.cloud = cloud
        self.repository = repository
        self.secret_backend = secret_backend
        self.client_version = client_version
        self.sessions = RemoteSessionStore()
        self.frpc = frpc or RemoteFrpcSupervisor(None, secret_backend)
        self.identity_repository = identity_repository
        if access_projection_interval_seconds <= 0:
            raise ValueError("access projection interval must be positive")
        self.access_projection_interval_seconds = access_projection_interval_seconds
        self._access_projection_etag: str | None = None
        self._access_projection_stop: asyncio.Event | None = None
        self._access_projection_task: asyncio.Task[None] | None = None

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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        device: RemoteDeviceRecord | None = None,
        cloud: AI2AppsCloudClient | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = dict(headers or {})
        if device is not None:
            try:
                secret = self.secret_backend.load(device.secret_backend_key)
            except KeyError as error:
                raise RemoteAccessError(409, "REMOTE_CREDENTIAL_MISSING", "Remote device credential is missing") from error
            request_headers["Authorization"] = (
                f"Device {device.device_id}.{secret}"
            )
        response = await (cloud or self.cloud).request(
            method, path, json=json, headers=request_headers or None
        )
        try:
            return await self._payload(response)
        finally:
            await response.aclose()

    @staticmethod
    def _secret_key(device_id: str) -> str:
        return f"ai2apps-remote-connector-{device_id}"

    def cloud_ai_headers(
        self, *, device_id: str, principal: RequestPrincipal
    ) -> dict[str, str]:
        """Build trusted Device-auth headers without exposing the secret to UI code."""

        device = self.require_device(device_id)
        if device.status != "active":
            raise RemoteAccessError(
                403,
                "REMOTE_DEVICE_INACTIVE",
                "The Cloud device credential is not active",
            )
        try:
            secret = self.secret_backend.load(device.secret_backend_key)
        except KeyError as error:
            raise RemoteAccessError(
                409,
                "REMOTE_CREDENTIAL_MISSING",
                "Remote device credential is missing",
            ) from error
        return {
            "Authorization": f"Device {device.device_id}.{secret}",
            "X-AI2Apps-Actor-User-Id": principal.actor_user_id,
            "X-AI2Apps-Membership-Epoch": str(principal.membership_epoch),
        }

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

    @staticmethod
    def _validate_credential(device_id: str, credential: dict[str, Any]) -> str:
        secret = credential.get("secret")
        raw_version = credential.get("credentialVersion")
        try:
            canonical_device_id = str(UUID(device_id))
        except (ValueError, AttributeError):
            canonical_device_id = ""
        if (
            canonical_device_id != device_id
            or credential.get("deviceId") != device_id
            or type(raw_version) is not int
            or raw_version <= 0
            or not isinstance(secret, str)
            or CONNECTOR_SECRET_PATTERN.fullmatch(secret) is None
        ):
            raise RemoteAccessError(
                502,
                "REMOTE_CREDENTIAL_INVALID",
                "Cloud returned an invalid connector credential",
            )
        return secret

    async def _enforce_connector_credential_lifetime(
        self, device: RemoteDeviceRecord | None = None
    ) -> bool:
        candidate = device or next(
            (
                item
                for item in self.repository.list()
                if item.enabled and item.status == "active"
            ),
            None,
        )
        if (
            candidate is None
            or candidate.credential_expires_at > utc_now() + CONNECTOR_ROTATION_WINDOW
        ):
            return False
        await self.frpc.stop()
        self.frpc.last_error = CONNECTOR_ROTATION_REQUIRED
        return True

    async def _recover_registration(
        self,
        *,
        display_name: str,
        platform_name: str,
        cloud: AI2AppsCloudClient | None = None,
    ) -> RemoteDeviceRecord:
        listed = await self._request("GET", "/v1/remote/devices", cloud=cloud)
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
            "POST",
            f"/v1/remote/devices/{device['id']}/credentials/rotate",
            cloud=cloud,
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
        secret = self._validate_credential(str(device.get("id") or ""), connector)
        connector.pop("secret")
        key = self._secret_key(device["id"])
        self.secret_backend.store(key, secret)
        try:
            return self.repository.upsert(device, connector, secret_backend_key=key)
        except Exception:
            self.secret_backend.delete(key)
            raise

    async def register(
        self,
        *,
        display_name: str,
        cloud: AI2AppsCloudClient | None = None,
        organization_id: str | None = None,
        owner_reauth_grant: str | None = None,
        idempotency_key: str | None = None,
    ) -> RemoteDeviceRecord:
        binding_values = (
            organization_id,
            owner_reauth_grant,
            idempotency_key,
        )
        if any(binding_values) and not all(binding_values):
            raise ValueError("Cloud installation binding requires all credentials")
        platform_name = self._platform_name()
        request_body = {
            "displayName": display_name,
            "platform": platform_name,
            "clientVersion": self.client_version,
        }
        request_headers = None
        if organization_id is not None:
            request_body["organizationId"] = organization_id
            request_headers = {
                "X-Owner-Reauth-Grant": owner_reauth_grant or "",
                "Idempotency-Key": idempotency_key or "",
            }
        try:
            payload = await self._request(
                "POST",
                "/v1/remote/devices",
                json=request_body,
                cloud=cloud,
                headers=request_headers,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            record = await self._recover_registration(
                display_name=display_name,
                platform_name=platform_name,
                cloud=cloud,
            )
            await self.sync_installation_identity(
                device_id=record.device_id, cloud=cloud
            )
            return record
        device, connector = payload["device"], payload["connector"]
        record = self._persist_registration(device, connector)
        installation = payload.get("installation")
        installation_id = (
            str(installation.get("installationId"))
            if isinstance(installation, dict) and installation.get("installationId")
            else None
        )
        await self.sync_installation_identity(
            device_id=record.device_id,
            installation_id=installation_id,
            cloud=cloud,
        )
        return record

    async def sync_installation_identity(
        self,
        *,
        device_id: str,
        installation_id: str | None = None,
        cloud: AI2AppsCloudClient | None = None,
    ) -> None:
        """Refresh the Cloud-authoritative installation binding after Device setup."""

        if self.identity_repository is None:
            return
        if installation_id is None:
            listed = await self._request("GET", "/v1/installations", cloud=cloud)
            matches = [
                item
                for item in listed.get("items", [])
                if item.get("cloudDeviceId") == device_id
            ]
            if len(matches) != 1:
                raise RemoteAccessError(
                    409,
                    "INSTALLATION_BINDING_AMBIGUOUS",
                    "Cloud installation binding could not be resolved",
                )
            installation_id = str(matches[0].get("installationId") or "")
        detail = await self._request(
            "GET", f"/v1/installations/{installation_id}", cloud=cloud
        )
        if detail.get("cloudDeviceId") != device_id:
            raise RemoteAccessError(
                409,
                "INSTALLATION_DEVICE_MISMATCH",
                "Cloud installation is bound to another device",
            )
        try:
            role = MemberRole(str(detail["role"]))
            organization_type = OrganizationType(str(detail["organizationType"]))
            self.identity_repository.bind_installation(
                installation_id=str(detail["installationId"]),
                cloud_device_id=device_id,
                organization_id=str(detail["organizationId"]),
                organization_type=organization_type,
                core_user_id=str(detail["coreUserId"]),
                billing_account_id=str(detail["billingAccountId"]),
                access_epoch=int(detail["accessEpoch"]),
                core_membership_epoch=int(detail["membershipEpoch"]),
                core_role=role,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RemoteAccessError(
                502,
                "INSTALLATION_PROJECTION_INVALID",
                "Cloud returned an invalid installation projection",
            ) from error

    async def reconcile(
        self, *, cloud: AI2AppsCloudClient | None = None
    ) -> tuple[RemoteDeviceRecord, ...]:
        payload = await self._request("GET", "/v1/remote/devices", cloud=cloud)
        local = {item.device_id: item for item in self.repository.list()}
        active_device_ids: list[str] = []
        for device in payload.get("items", []):
            if device.get("id") in local:
                self.repository.update_cloud_state(device)
                if device.get("status") == "active":
                    active_device_ids.append(str(device["id"]))
        if self.identity_repository is not None and active_device_ids:
            installation = self.identity_repository.get_installation()
            device_id = (
                installation.cloud_device_id
                if installation is not None
                and installation.cloud_device_id in active_device_ids
                else active_device_ids[0]
            )
            await self.sync_installation_identity(device_id=device_id, cloud=cloud)
        return self.repository.list()

    async def refresh_access_projection(self) -> bool:
        """Refresh the complete Cloud authorization projection for this installation."""

        if self.identity_repository is None:
            return False
        installation = self.identity_repository.get_installation()
        if installation is None:
            return False
        device = self.require_device(installation.cloud_device_id)
        try:
            secret = self.secret_backend.load(device.secret_backend_key)
        except KeyError as error:
            raise RemoteAccessError(
                409,
                "REMOTE_CREDENTIAL_MISSING",
                "Remote device credential is missing",
            ) from error
        headers = {
            "Authorization": f"Device {device.device_id}.{secret}",
        }
        if self._access_projection_etag:
            headers["If-None-Match"] = self._access_projection_etag
        response = await self.cloud.request(
            "GET",
            f"/v1/internal/installations/{installation.id}/access",
            headers=headers,
        )
        try:
            if response.status_code == 304:
                self.identity_repository.touch_access_projection(installation.id)
                return False
            payload = await self._payload(response)
            try:
                if (
                    payload["installationId"] != installation.id
                    or payload["cloudDeviceId"] != installation.cloud_device_id
                    or payload["organizationId"] != installation.organization_id
                ):
                    raise ValueError("projection authority changed")
                authorization_version = int(payload["authorizationVersion"])
                if authorization_version < 1:
                    raise ValueError("authorization version is invalid")
                raw_memberships = payload["memberships"]
                if not isinstance(raw_memberships, list):
                    raise ValueError("memberships must be a list")
                memberships = [
                    {
                        "user_id": item["userId"],
                        "role": item["role"],
                        "status": item["status"],
                        "membership_epoch": item["membershipEpoch"],
                    }
                    for item in raw_memberships
                    if isinstance(item, dict)
                ]
                if len(memberships) != len(raw_memberships):
                    raise ValueError("membership entry is invalid")
                self.identity_repository.apply_access_projection(
                    installation_id=installation.id,
                    cloud_device_id=installation.cloud_device_id,
                    organization_id=installation.organization_id,
                    device_status=str(payload["deviceStatus"]),
                    access_epoch=int(payload["accessEpoch"]),
                    memberships=memberships,
                )
            except (KeyError, TypeError, ValueError, IdentityBindingError) as error:
                raise RemoteAccessError(
                    502,
                    "INSTALLATION_ACCESS_PROJECTION_INVALID",
                    "Cloud returned an invalid installation access projection",
                ) from error
            etag = response.headers.get("etag")
            self._access_projection_etag = etag if etag else None
            return True
        except RemoteAccessError as error:
            self._deactivate_for_access_error(error)
            raise
        finally:
            await response.aclose()

    def _deactivate_for_access_error(self, error: RemoteAccessError) -> None:
        if self.identity_repository is None:
            return
        revoked = {
            "DEVICE_REVOKED",
            "REMOTE_DEVICE_REVOKED",
        }
        suspended = {
            "DEVICE_SUSPENDED",
            "DEVICE_EPOCH_MISMATCH",
            "DEVICE_CREDENTIAL_EXPIRED",
            "REMOTE_DEVICE_SUSPENDED",
        }
        if error.code in revoked:
            self.identity_repository.deactivate_installation("revoked")
        elif error.code in suspended:
            self.identity_repository.deactivate_installation("suspended")

    async def _run_access_projection_refresh(self) -> None:
        assert self._access_projection_stop is not None
        while not self._access_projection_stop.is_set():
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    self._access_projection_stop.wait(),
                    timeout=self.access_projection_interval_seconds,
                )
            if self._access_projection_stop.is_set():
                break
            try:
                await self._enforce_connector_credential_lifetime()
                await self.refresh_access_projection()
            except (RemoteAccessError, httpx.HTTPError):
                logger.warning(
                    "AI2Apps installation access projection refresh failed",
                    exc_info=True,
                )

    async def rotate(
        self, device_id: str, *, cloud: AI2AppsCloudClient | None = None
    ) -> RemoteDeviceRecord:
        device = self.require_device(device_id)
        restart_after_rotation = device.enabled
        await self.stop(device_id)
        try:
            payload = await self._request(
                "POST",
                f"/v1/remote/devices/{device_id}/credentials/rotate",
                cloud=cloud,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            payload = await self._request(
                "POST",
                f"/v1/remote/devices/{device_id}/credentials/rotate",
                cloud=cloud,
            )
        secret = self._validate_credential(device_id, payload)
        try:
            self.secret_backend.load(device.secret_backend_key)
        except KeyError as error:
            raise RemoteAccessError(
                409,
                "REMOTE_CREDENTIAL_MISSING",
                "Remote device credential is missing",
            ) from error
        self.secret_backend.store(device.secret_backend_key, secret)
        # Cloud has already invalidated the previous Secret. If the local
        # projection update fails, retain the new Secret so retrying rotation
        # remains authenticated; never restore a credential Cloud revoked.
        record = self.repository.update_credential(device_id, payload)
        assert record is not None
        if restart_after_rotation:
            await self.frpc.start(record)
            restarted = self.repository.set_enabled(device_id, True)
            assert restarted is not None
            return restarted
        return record

    async def pairing_challenge(
        self, device_id: str, *, cloud: AI2AppsCloudClient | None = None
    ) -> dict[str, Any]:
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
        cloud_device = await self._request(
            "GET", f"/v1/remote/devices/{device_id}", cloud=cloud
        )
        refreshed = self.repository.update_cloud_state(cloud_device)
        if refreshed is None or not refreshed.proxy_connected:
            raise RemoteAccessError(
                409,
                "REMOTE_CONNECTOR_NOT_ONLINE",
                "Wait for the Remote Access indicator to turn green before pairing",
            )
        payload = await self._request(
            "POST",
            f"/v1/remote/devices/{device_id}/pairing-challenges",
            cloud=cloud,
        )
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

    async def usage(
        self, *, cloud: AI2AppsCloudClient | None = None
    ) -> dict[str, Any]:
        return await self._request("GET", "/v1/remote/usage", cloud=cloud)

    async def revoke(
        self, device_id: str, *, cloud: AI2AppsCloudClient | None = None
    ) -> dict[str, Any]:
        self.require_device(device_id)
        await self.stop(device_id)
        payload = await self._request(
            "POST", f"/v1/remote/devices/{device_id}/revoke", cloud=cloud
        )
        self.repository.set_enabled(device_id, False)
        self.sessions.revoke_device(device_id)
        await self.reconcile(cloud=cloud)
        return payload

    async def start(
        self, device_id: str, *, cloud: AI2AppsCloudClient | None = None
    ) -> RemoteDeviceRecord:
        device = self.require_device(device_id)
        if device.status == "revoked":
            raise RemoteAccessError(
                409,
                "REMOTE_DEVICE_REVOKED",
                "Revoked device identities cannot be started; register this Mac again",
            )
        cloud_device = await self._request(
            "GET", f"/v1/remote/devices/{device_id}", cloud=cloud
        )
        refreshed = self.repository.update_cloud_state(cloud_device)
        if refreshed is not None:
            device = refreshed
        if device.credential_expires_at <= utc_now() + CONNECTOR_ROTATION_WINDOW:
            raise RemoteAccessError(
                409, "REMOTE_CREDENTIAL_ROTATION_REQUIRED",
                CONNECTOR_ROTATION_REQUIRED,
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
        if (
            enabled is not None
            and self.frpc.available
            and not await self._enforce_connector_credential_lifetime(enabled)
        ):
            await self.frpc.start(enabled)
        try:
            await self.refresh_access_projection()
        except (RemoteAccessError, httpx.HTTPError):
            logger.warning(
                "Initial AI2Apps installation access projection refresh failed",
                exc_info=True,
            )
        if self._access_projection_task is None:
            self._access_projection_stop = asyncio.Event()
            self._access_projection_task = asyncio.create_task(
                self._run_access_projection_refresh(),
                name="ai2apps-installation-access-projection",
            )

    async def shutdown(self) -> None:
        if self._access_projection_stop is not None:
            self._access_projection_stop.set()
        if self._access_projection_task is not None:
            await self._access_projection_task
        self._access_projection_task = None
        self._access_projection_stop = None
        await self.frpc.stop()
        self.sessions.clear()

    async def redact(
        self, device_id: str, *, cloud: AI2AppsCloudClient | None = None
    ) -> None:
        device = self.require_device(device_id)
        response = await (cloud or self.cloud).request(
            "DELETE", f"/v1/remote/devices/{device_id}"
        )
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

    async def exchange_handoff(
        self,
        *,
        device_id: str,
        handoff: str,
        client_scope: str = "desktop",
    ) -> tuple[str, RemoteMobileSession]:
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
        owner_user_id = str(claims["sub"])
        local_session_token = None
        if self.identity_repository is not None:
            try:
                local_session_token, _ = self.identity_repository.create_local_session(
                    owner_user_id,
                    lifetime=MOBILE_SESSION_LIFETIME,
                    client_scope=client_scope,
                )
            except IdentityBindingError as error:
                raise RemoteAccessError(
                    403,
                    "REMOTE_MEMBER_NOT_ACTIVE",
                    "The remote account is not an active member of this installation",
                ) from error
        return self.sessions.create(
            device_id=device_id,
            owner_user_id=owner_user_id,
            access_epoch=int(claims["access_epoch"]),
            local_session_token=local_session_token,
            client_scope=client_scope,
        )

    def principal_for_mobile_session(
        self, session: RemoteMobileSession
    ) -> RequestPrincipal:
        """Resolve a remote session through the current installation projection."""

        if self.identity_repository is None:
            raise RemoteAccessError(
                503,
                "INSTALLATION_IDENTITY_NOT_READY",
                "Installation identity storage is unavailable",
            )
        installation = self.identity_repository.get_installation()
        if (
            installation is None
            or installation.status != "active"
            or installation.cloud_device_id != session.device_id
            or installation.access_epoch != session.access_epoch
        ):
            raise RemoteAccessError(
                403,
                "REMOTE_MEMBER_NOT_ACTIVE",
                "The remote session is not valid for this installation",
            )
        try:
            return replace(
                self.identity_repository.principal_for(session.owner_user_id),
                client_scope=session.client_scope,
            )
        except IdentityBindingError as error:
            raise RemoteAccessError(
                403,
                "REMOTE_MEMBER_NOT_ACTIVE",
                "The remote account is not an active member of this installation",
            ) from error

    async def exchange_member_handoff(
        self, *, handoff: str
    ) -> tuple[str, RequestPrincipal]:
        """Exchange a one-use Cloud handoff for a durable local member session."""

        if self.identity_repository is None:
            raise RemoteAccessError(
                503,
                "INSTALLATION_IDENTITY_NOT_READY",
                "Installation identity storage is unavailable",
            )
        installation = self.identity_repository.get_installation()
        if installation is None or installation.status != "active":
            raise RemoteAccessError(
                409,
                "INSTALLATION_NOT_BOUND",
                "This device is not bound to an active installation",
            )
        device = self.require_device(installation.cloud_device_id)
        payload = await self._request(
            "POST",
            f"/v1/internal/installations/{installation.id}/member-handoffs/exchange",
            json={"handoff": handoff},
            device=device,
        )
        jwks = await self._request("GET", "/v1/installation-auth/jwks.json")
        try:
            claims = verify_installation_member_token(
                str(payload["accessToken"]),
                jwks,
                installation_id=installation.id,
                device_id=installation.cloud_device_id,
                organization_id=installation.organization_id,
                access_epoch=int(payload["accessEpoch"]),
            )
            if (
                payload.get("installationId") != installation.id
                or payload.get("cloudDeviceId") != installation.cloud_device_id
                or payload.get("organizationId") != installation.organization_id
                or int(claims["access_epoch"]) != int(payload["accessEpoch"])
                or str(claims["role"]) != str(payload["role"])
                or int(claims["membership_epoch"])
                != int(payload["membershipEpoch"])
            ):
                raise ValueError("Member assertion projection does not match exchange")
            role = MemberRole(str(claims["role"]))
            organization_type = OrganizationType(str(claims["organization_type"]))
        except (KeyError, TypeError, ValueError) as error:
            raise RemoteAccessError(
                502,
                "MEMBER_ASSERTION_INVALID",
                "Cloud returned an invalid member assertion",
            ) from error

        actor_user_id = str(claims["sub"])
        if organization_type is not installation.organization_type:
            raise RemoteAccessError(
                502,
                "MEMBER_ASSERTION_INVALID",
                "Cloud member assertion changed the organization type",
            )
        assertion_access_epoch = int(claims["access_epoch"])
        if assertion_access_epoch < installation.access_epoch:
            raise RemoteAccessError(
                502,
                "MEMBER_ASSERTION_INVALID",
                "Cloud member assertion regressed the installation epoch",
            )
        if actor_user_id == installation.core_user_id:
            core_role = role
            core_membership_epoch = int(claims["membership_epoch"])
        else:
            core = self.identity_repository.principal_for(installation.core_user_id)
            core_role = core.role
            core_membership_epoch = core.membership_epoch
        self.identity_repository.bind_installation(
            installation_id=installation.id,
            cloud_device_id=installation.cloud_device_id,
            organization_id=installation.organization_id,
            organization_type=installation.organization_type,
            core_user_id=installation.core_user_id,
            billing_account_id=installation.billing_account_id,
            access_epoch=assertion_access_epoch,
            core_membership_epoch=core_membership_epoch,
            core_role=core_role,
        )
        if actor_user_id != installation.core_user_id:
            self.identity_repository.upsert_membership(
                cloud_user_id=actor_user_id,
                role=role,
                status="active",
                membership_epoch=int(claims["membership_epoch"]),
            )
        token, _ = self.identity_repository.create_local_session(actor_user_id)
        return token, self.identity_repository.principal_for(actor_user_id)

    async def activate_current_cloud_member(
        self,
        *,
        cloud: AI2AppsCloudClient | None = None,
    ) -> tuple[str, RequestPrincipal]:
        """Create and consume a LAN handoff without exposing it to the renderer."""

        if self.identity_repository is None:
            raise RemoteAccessError(
                503,
                "INSTALLATION_IDENTITY_NOT_READY",
                "Installation identity storage is unavailable",
            )
        installation = self.identity_repository.get_installation()
        if installation is None or installation.status != "active":
            raise RemoteAccessError(
                409,
                "INSTALLATION_NOT_BOUND",
                "This device is not bound to an active installation",
            )
        browser_cloud = cloud or self.cloud
        response = await browser_cloud.request(
            "POST",
            f"/v1/installations/{installation.id}/member-handoffs",
            json={"target": "lan_desktop"},
        )
        try:
            payload = await self._payload(response)
        finally:
            await response.aclose()
        parsed = urlparse(str(payload.get("redirectUrl") or ""))
        handoffs = parse_qs(parsed.fragment, keep_blank_values=True).get(
            "handoff", []
        )
        if (
            parsed.scheme != "ai2apps"
            or parsed.netloc != "auth"
            or parsed.path != "/complete"
            or len(handoffs) != 1
            or not 24 <= len(handoffs[0]) <= 200
        ):
            raise RemoteAccessError(
                502,
                "MEMBER_HANDOFF_INVALID",
                "Cloud returned an invalid Local member handoff",
            )
        return await self.exchange_member_handoff(handoff=handoffs[0])

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
