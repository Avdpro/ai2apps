"""Device-authenticated client for the Cloud Peer Session Broker."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.identity import RequestPrincipal

from .grants import VerifiedPeerGrant, verify_peer_grant
from .identity import PeerDeviceKeyManager, PeerIdentityError, PeerProtocol
from .session import PeerSession


class PeerBrokerError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 500, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class PeerBrokerClient:
    """Keep grants memory-only while persisting only safe Session projections."""

    def __init__(
        self,
        *,
        cloud: AI2AppsCloudClient,
        keys: PeerDeviceKeyManager,
        device_id: str,
        device_headers,
        session_repository=None,
        jwks_ttl_seconds: float = 300.0,
    ) -> None:
        self.cloud = cloud
        self.keys = keys
        self.device_id = device_id
        self.device_headers = device_headers
        self.session_repository = session_repository
        self.jwks_ttl_seconds = jwks_ttl_seconds
        self._jwks: dict[str, Any] | None = None
        self._jwks_expires_at = 0.0
        self._jwks_lock = asyncio.Lock()
        self._grants: dict[str, VerifiedPeerGrant] = {}

    async def _payload(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = None
        if response.status_code >= 400:
            detail = payload.get("error", {}) if isinstance(payload, dict) else {}
            code = str(detail.get("code") or "PEER_CLOUD_REQUEST_FAILED")
            raise PeerBrokerError(
                code,
                str(detail.get("message") or "Cloud rejected the Peer request."),
                status_code=response.status_code,
                retryable=response.status_code >= 500 or response.status_code == 429,
            )
        if not isinstance(payload, dict):
            raise PeerBrokerError("PEER_CLOUD_RESPONSE_INVALID", "Cloud returned invalid JSON.", status_code=502)
        return payload

    async def _request(self, method: str, path: str, *, principal: RequestPrincipal, **kwargs) -> dict[str, Any]:
        headers = dict(self.device_headers(principal))
        headers.update(kwargs.pop("headers", {}) or {})
        response = await self.cloud.request(method, path, headers=headers, **kwargs)
        try:
            return await self._payload(response)
        finally:
            await response.aclose()

    async def jwks(self, *, refresh: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not refresh and self._jwks is not None and now < self._jwks_expires_at:
            return self._jwks
        async with self._jwks_lock:
            now = time.monotonic()
            if not refresh and self._jwks is not None and now < self._jwks_expires_at:
                return self._jwks
            response = await self.cloud.request("GET", "/v1/peer/jwks.json")
            try:
                payload = await self._payload(response)
            finally:
                await response.aclose()
            if not isinstance(payload.get("keys"), list):
                raise PeerBrokerError("PEER_JWKS_INVALID", "Cloud returned an invalid Peer JWKS.", status_code=502)
            self._jwks = payload
            self._jwks_expires_at = now + self.jwks_ttl_seconds
            return payload

    async def ensure_registered(self, principal: RequestPrincipal, protocol: PeerProtocol) -> dict[str, Any]:
        headers = self.device_headers(principal)
        local = self.keys.get_or_create(self.device_id, protocol)
        response = await self.cloud.request("GET", f"/v1/peer/device-keys/{protocol.value}", headers=headers)
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {}
        finally:
            await response.aclose()
        if response.status_code == 200 and isinstance(payload, dict) and all((
            payload.get("deviceId") == self.device_id,
            payload.get("protocol") == protocol.value,
            payload.get("status") == "active",
            payload.get("identitySigningPublicKey") == local.identity_public,
            payload.get("staticDhPublicKey") == local.static_dh_public,
        )):
            return payload
        try:
            return await self.keys.register(
                cloud=self.cloud,
                device_id=self.device_id,
                protocol=protocol,
                headers=headers,
            )
        except PeerIdentityError as error:
            raise PeerBrokerError(error.code, str(error), status_code=error.status_code) from error

    async def create_session(
        self,
        *,
        principal: RequestPrincipal,
        protocol: PeerProtocol,
        peer_user_id: str,
        purpose_id: str,
        idempotency_key: str,
        requested_transports: Sequence[str] = ("relay_https",),
        peer_device_id: str | None = None,
        client_nonce: str | None = None,
    ) -> PeerSession:
        await self.ensure_registered(principal, protocol)
        body: dict[str, Any] = {
            "protocol": protocol.value,
            "peerUserId": peer_user_id,
            "purposeType": protocol.purpose_type,
            "purposeId": purpose_id,
            "requestedTransports": list(requested_transports),
            # Cloud binds Idempotency-Key and clientNonce exactly. Keeping one
            # value also makes a retried create deterministic across processes.
            "clientNonce": client_nonce or idempotency_key,
        }
        if peer_device_id is not None:
            body["peerDeviceId"] = peer_device_id
        payload = await self._request(
            "POST", "/v1/peer/sessions", principal=principal, json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        return await self._consume_session(payload, principal)

    async def add_candidate(
        self, principal: RequestPrincipal, session_id: str, *, candidate_type: str,
        transport: str, address: str, port: int, priority: int, generation: int,
    ) -> dict[str, Any]:
        return await self._request(
            "POST", f"/v1/peer/sessions/{session_id}/candidates", principal=principal,
            json={"type": candidate_type, "transport": transport, "address": address,
                  "port": port, "priority": priority, "generation": generation},
        )

    async def list_candidates(
        self, principal: RequestPrincipal, session_id: str, *, after_generation: int = -1,
    ) -> list[dict[str, Any]]:
        payload = await self._request(
            "GET", f"/v1/peer/sessions/{session_id}/candidates", principal=principal,
            params={"afterGeneration": str(after_generation)},
        )
        values = payload.get("items")
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise PeerBrokerError("PEER_CLOUD_RESPONSE_INVALID", "Cloud Candidate list is invalid.", status_code=502)
        return values

    async def observe(
        self, principal: RequestPrincipal, session_id: str, *, path_type: str,
        latency_bucket: str, result_code: str, protocol_version: str,
    ) -> None:
        await self._request(
            "POST", f"/v1/peer/sessions/{session_id}/observations", principal=principal,
            json={"pathType": path_type, "latencyBucket": latency_bucket,
                  "resultCode": result_code, "protocolVersion": protocol_version},
        )

    async def list_sessions(self, principal: RequestPrincipal, *, status: str = "pending") -> list[PeerSession]:
        payload = await self._request("GET", "/v1/peer/sessions", principal=principal, params={"status": status})
        values = payload.get("items")
        if not isinstance(values, list):
            raise PeerBrokerError("PEER_CLOUD_RESPONSE_INVALID", "Cloud Session list is invalid.", status_code=502)
        return [await self._consume_session(item, principal) for item in values]

    async def get_session(self, principal: RequestPrincipal, session_id: str) -> PeerSession:
        payload = await self._request("GET", f"/v1/peer/sessions/{session_id}", principal=principal)
        return await self._consume_session(payload, principal)

    async def accept_session(self, principal: RequestPrincipal, session_id: str) -> PeerSession:
        payload = await self._request("POST", f"/v1/peer/sessions/{session_id}/accept", principal=principal)
        return await self._consume_session(payload, principal)

    async def close_session(self, principal: RequestPrincipal, session_id: str) -> dict[str, Any]:
        payload = await self._request("DELETE", f"/v1/peer/sessions/{session_id}", principal=principal)
        self._grants.pop(session_id, None)
        if self.session_repository is not None:
            self.session_repository.mark_closed(session_id)
        return payload

    async def refresh_grant(self, principal: RequestPrincipal, session_id: str) -> VerifiedPeerGrant:
        session = await self.get_session(principal, session_id)
        payload = await self._request("POST", f"/v1/peer/sessions/{session_id}/grants/refresh", principal=principal)
        compact = payload.get("grant")
        if not isinstance(compact, str):
            raise PeerBrokerError("PEER_CLOUD_RESPONSE_INVALID", "Cloud Grant response is invalid.", status_code=502)
        return await self._verify_and_hold(session, principal, compact)

    def grant_for(self, session_id: str) -> VerifiedPeerGrant | None:
        grant = self._grants.get(session_id)
        if grant is not None and int(grant.claims["exp"]) >= int(time.time()):
            return grant
        self._grants.pop(session_id, None)
        return None

    async def _consume_session(self, payload: Mapping[str, Any], principal: RequestPrincipal) -> PeerSession:
        try:
            session = PeerSession.parse(payload)
        except (TypeError, ValueError) as error:
            raise PeerBrokerError("PEER_CLOUD_RESPONSE_INVALID", "Cloud returned an invalid Peer Session.", status_code=502) from error
        if session.self_endpoint.user_id != principal.actor_user_id or session.self_endpoint.device_id != self.device_id:
            raise PeerBrokerError("PEER_SESSION_BINDING_INVALID", "Cloud Session holder does not match this Local actor.", status_code=502)
        if self.session_repository is not None:
            self.session_repository.upsert(session, principal.actor_user_id)
        if session.grant is not None:
            await self._verify_and_hold(session, principal, session.grant)
        return session

    async def _verify_and_hold(self, session: PeerSession, principal: RequestPrincipal, compact: str) -> VerifiedPeerGrant:
        jwks = await self.jwks()
        try:
            verified = verify_peer_grant(
                compact, jwks, session=session,
                holder_user_id=principal.actor_user_id, holder_device_id=self.device_id,
            )
        except ValueError:
            jwks = await self.jwks(refresh=True)
            try:
                verified = verify_peer_grant(
                    compact, jwks, session=session,
                    holder_user_id=principal.actor_user_id, holder_device_id=self.device_id,
                )
            except ValueError as error:
                raise PeerBrokerError("PEER_GRANT_INVALID", str(error), status_code=401) from error
        self._grants[session.session_id] = verified
        return verified
