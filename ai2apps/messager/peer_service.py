"""Cloud-authorized Local-first Messager peer orchestration."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.core import utc_now_text
from ai2apps.events import EventStore
from ai2apps.identity import IdentityBindingError, IdentityRepository, RequestPrincipal
from ai2apps.remote import RemoteAccessManager
from ai2apps.secrets import SecretBackend
from ai2apps.storage import PlatformDatabase

from .assertion import MessagerAssertionError, verify_peer_assertion
from .identity import (
    MessagerDeviceKeyManager,
    MessagerIdentityError,
    b64url_decode,
    b64url_encode,
)
from .noise_transport import InitiatorExchange, MessagerNoiseError, ResponderExchange
from .repository import MessagerIdempotencyConflictError, MessagerRepository


class MessagerPeerError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, status_code: int = 400, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


@dataclass(slots=True)
class _InboundSession:
    exchange: ResponderExchange
    owner_user_id: str
    peer_user_id: str
    expires_at: float


class MessagerJwksCache:
    def __init__(self, cloud: AI2AppsCloudClient, *, ttl_seconds: float = 300.0) -> None:
        self.cloud = cloud
        self.ttl_seconds = ttl_seconds
        self._value: dict[str, Any] | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get(self, *, refresh: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not refresh and self._value is not None and now < self._expires_at:
            return self._value
        async with self._lock:
            now = time.monotonic()
            if not refresh and self._value is not None and now < self._expires_at:
                return self._value
            response = await self.cloud.request("GET", "/v1/messager/jwks.json")
            try:
                payload = response.json()
            except ValueError as error:
                raise MessagerPeerError(
                    "MESSAGER_JWKS_INVALID", "Cloud returned an invalid JWKS.", status_code=502
                ) from error
            finally:
                await response.aclose()
            if response.status_code != 200 or not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
                raise MessagerPeerError(
                    "MESSAGER_JWKS_UNAVAILABLE",
                    "Cloud Messager signing keys are unavailable.",
                    status_code=503,
                    retryable=True,
                )
            self._value = payload
            self._expires_at = now + self.ttl_seconds
            return payload


class MessagerPeerService:
    """Bind Cloud identity, Noise IK, replay defense, and local persistence."""

    def __init__(
        self,
        *,
        database: PlatformDatabase,
        events: EventStore,
        cloud: AI2AppsCloudClient,
        remote: RemoteAccessManager,
        secret_backend: SecretBackend,
    ) -> None:
        self.database = database
        self.events = events
        self.cloud = cloud
        self.remote = remote
        self.identities = IdentityRepository(database)
        self.keys = MessagerDeviceKeyManager(secret_backend)
        self.repository = MessagerRepository(database, events)
        self.jwks = MessagerJwksCache(cloud)
        self._sessions: dict[str, _InboundSession] = {}
        self._sessions_lock = asyncio.Lock()

    def _installation_device(self):
        installation = self.identities.get_installation()
        if installation is None or installation.status != "active":
            raise MessagerPeerError(
                "MESSAGER_INSTALLATION_INACTIVE",
                "The Local installation is not active.",
                status_code=403,
            )
        device = self.remote.require_device(installation.cloud_device_id)
        if device.status != "active":
            raise MessagerPeerError(
                "MESSAGER_DEVICE_INACTIVE", "The Local Cloud Device is not active.", status_code=403
            )
        return installation, device

    def _device_headers(self, principal: RequestPrincipal) -> dict[str, str]:
        installation, _ = self._installation_device()
        return self.remote.cloud_ai_headers(
            device_id=installation.cloud_device_id, principal=principal
        )

    async def ensure_registered(self, principal: RequestPrincipal) -> dict[str, Any]:
        installation, device = self._installation_device()
        headers = self._device_headers(principal)
        local = self.keys.get_or_create(device.device_id)
        response = await self.cloud.request(
            "GET", "/v1/messager/device-key", headers=headers
        )
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {}
        finally:
            await response.aclose()
        if response.status_code == 200 and isinstance(payload, dict):
            matches = (
                payload.get("status") == "active"
                and payload.get("deviceId") == installation.cloud_device_id
                and payload.get("deviceAccessEpoch") == installation.access_epoch
                and payload.get("identitySigningFingerprintSha256")
                == local.identity_fingerprint
                and payload.get("staticDhFingerprintSha256") == local.static_dh_fingerprint
            )
            if matches:
                return payload
        try:
            return await self.keys.register(
                cloud=self.cloud,
                device_id=device.device_id,
                headers=headers,
            )
        except MessagerIdentityError as error:
            raise MessagerPeerError(
                error.code, str(error), status_code=error.status_code
            ) from error

    async def rotate_device_key(self, principal: RequestPrincipal) -> dict[str, Any]:
        """Replace the Local key bundle and register it for the current Device."""

        installation, device = self._installation_device()
        headers = self._device_headers(principal)
        previous = self.keys.get_or_create(device.device_id)
        try:
            registered = await self.keys.register(
                cloud=self.cloud,
                device_id=device.device_id,
                headers=headers,
                rotate=True,
            )
        except MessagerIdentityError as error:
            raise MessagerPeerError(
                error.code, str(error), status_code=error.status_code
            ) from error
        self.events.append(
            event_type="messager.device_key.rotated",
            subject_id=device.device_id,
            payload={
                "actor_user_id": principal.actor_user_id,
                "device_access_epoch": installation.access_epoch,
                "previous_identity_fingerprint_sha256": previous.identity_fingerprint,
                "identity_fingerprint_sha256": registered[
                    "identitySigningFingerprintSha256"
                ],
                "previous_static_dh_fingerprint_sha256": previous.static_dh_fingerprint,
                "static_dh_fingerprint_sha256": registered[
                    "staticDhFingerprintSha256"
                ],
            },
        )
        return registered

    async def _verify(
        self, assertion: str, *, handshake_id: str, self_endpoint=None, peer_endpoint=None
    ):
        jwks = await self.jwks.get()
        try:
            return verify_peer_assertion(
                assertion,
                jwks,
                handshake_id=handshake_id,
                self_endpoint=self_endpoint,
                peer_endpoint=peer_endpoint,
            )
        except MessagerAssertionError:
            jwks = await self.jwks.get(refresh=True)
            try:
                return verify_peer_assertion(
                    assertion,
                    jwks,
                    handshake_id=handshake_id,
                    self_endpoint=self_endpoint,
                    peer_endpoint=peer_endpoint,
                )
            except MessagerAssertionError as error:
                raise MessagerPeerError(
                    "MESSAGER_ASSERTION_INVALID", str(error), status_code=401
                ) from error

    async def accept_handshake(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        required = {"assertion", "handshakeId", "initiator", "noiseMessage"}
        if set(payload) != required or not isinstance(payload.get("initiator"), dict):
            raise MessagerPeerError("MESSAGER_HANDSHAKE_INVALID", "Handshake fields are invalid.")
        assertion = str(payload["assertion"])
        handshake_id = str(payload["handshakeId"])
        initiator = payload["initiator"]
        if not 100 <= len(assertion) <= 8192 or len(str(payload["noiseMessage"])) > 4096:
            raise MessagerPeerError("MESSAGER_HANDSHAKE_INVALID", "Handshake size is invalid.")
        verified = await self._verify(
            assertion, handshake_id=handshake_id, self_endpoint=initiator
        )
        claims = verified.claims
        installation, device = self._installation_device()
        local_keys = self.keys.get_or_create(device.device_id)
        try:
            self.identities.principal_for(claims["recipient_user_id"])
        except IdentityBindingError as error:
            raise MessagerPeerError(
                "MESSAGER_RECIPIENT_NOT_LOCAL", "Assertion recipient is not local.", status_code=403
            ) from error
        if (
            claims["recipient_device_id"] != device.device_id
            or claims["recipient_installation_id"] != installation.id
            or claims["recipient_access_epoch"] != installation.access_epoch
            or claims["recipient_identity_signing_key_sha256"] != local_keys.identity_fingerprint
            or claims["recipient_static_dh_key_sha256"] != local_keys.static_dh_fingerprint
        ):
            raise MessagerPeerError(
                "MESSAGER_RECIPIENT_BINDING_INVALID", "Assertion does not bind this Local Device.", status_code=403
            )
        if not self.repository.accept_peer_handshake(
            assertion_jti=claims["jti"],
            handshake_id=handshake_id,
            initiator_user_id=claims["initiator_user_id"],
            initiator_device_id=claims["initiator_device_id"],
            expires_at=claims["exp"],
        ):
            raise MessagerPeerError(
                "MESSAGER_HANDSHAKE_REPLAYED", "Handshake was already consumed.", status_code=409
            )
        try:
            exchange, response = ResponderExchange.accept(
                keys=local_keys,
                asserted_initiator_static_public=initiator["staticDhPublicKey"],
                handshake_id=handshake_id,
                assertion_jti=claims["jti"],
                request=b64url_decode(str(payload["noiseMessage"])),
            )
        except (KeyError, ValueError, MessagerNoiseError) as error:
            raise MessagerPeerError(
                "MESSAGER_NOISE_HANDSHAKE_INVALID", str(error), status_code=401
            ) from error
        session_id = b64url_encode(uuid.uuid4().bytes + uuid.uuid4().bytes)
        async with self._sessions_lock:
            now = time.monotonic()
            self._sessions = {
                key: value for key, value in self._sessions.items() if value.expires_at > now
            }
            self._sessions[session_id] = _InboundSession(
                exchange=exchange,
                owner_user_id=claims["recipient_user_id"],
                peer_user_id=claims["initiator_user_id"],
                expires_at=now + 120,
            )
        self.events.append(
            event_type="messager.peer.handshake.accepted",
            subject_id=handshake_id,
            trace_id=claims["jti"],
            payload={
                "initiator_user_id": claims["initiator_user_id"],
                "initiator_device_id": claims["initiator_device_id"],
                "recipient_device_id": claims["recipient_device_id"],
            },
        )
        return {"sessionId": session_id, "noiseMessage": b64url_encode(response)}

    async def accept_message(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if set(payload) != {"sessionId", "ciphertext"}:
            raise MessagerPeerError("MESSAGER_FRAME_INVALID", "Encrypted frame fields are invalid.")
        session_id = str(payload["sessionId"])
        if len(session_id) != 43 or len(str(payload["ciphertext"])) > 30_000:
            raise MessagerPeerError("MESSAGER_FRAME_INVALID", "Encrypted frame size is invalid.")
        async with self._sessions_lock:
            session = self._sessions.pop(session_id, None)
        if session is None or session.expires_at <= time.monotonic():
            raise MessagerPeerError(
                "MESSAGER_SESSION_INVALID", "Peer session is invalid or expired.", status_code=401
            )
        try:
            message = session.exchange.decrypt_text(
                b64url_decode(str(payload["ciphertext"]))
            )
        except (ValueError, MessagerNoiseError) as error:
            raise MessagerPeerError(
                "MESSAGER_FRAME_AUTH_INVALID", str(error), status_code=401
            ) from error
        if (
            message["senderUserId"] != session.peer_user_id
            or message["recipientUserId"] != session.owner_user_id
        ):
            raise MessagerPeerError(
                "MESSAGER_MESSAGE_BINDING_INVALID", "Message users do not match the peer session.", status_code=403
            )
        try:
            _, created = self.repository.record_local_incoming(
                owner_user_id=session.owner_user_id,
                peer_user_id=session.peer_user_id,
                remote_message_id=message["clientMessageId"],
                body=message["body"],
            )
        except MessagerIdempotencyConflictError as error:
            raise MessagerPeerError(
                "MESSAGER_IDEMPOTENCY_CONFLICT", str(error), status_code=409
            ) from error
        received_at = utc_now_text()
        ack = session.exchange.encrypt_ack(
            client_message_id=message["clientMessageId"],
            received_at=received_at,
            status="received" if created else "duplicate",
        )
        return {"ciphertext": b64url_encode(ack)}

    async def send_local(
        self,
        *,
        principal: RequestPrincipal,
        recipient_user_id: str,
        client_message_id: str,
        body: str,
    ) -> dict[str, Any]:
        await self.ensure_registered(principal)
        handshake_id = str(uuid.uuid4())
        headers = self._device_headers(principal)
        response = await self.cloud.request(
            "POST",
            "/v1/messager/peer-assertions",
            json={"recipientUserId": recipient_user_id, "handshakeId": handshake_id},
            headers=headers,
        )
        try:
            assertion_payload = response.json() if response.content else {}
        except ValueError:
            assertion_payload = {}
        finally:
            await response.aclose()
        if response.status_code >= 400 or not isinstance(assertion_payload, dict):
            error = assertion_payload.get("error", {}) if isinstance(assertion_payload, dict) else {}
            code = str(error.get("code") or "MESSAGER_ASSERTION_UNAVAILABLE")
            unavailable = code == "MESSAGER_PEER_KEY_UNAVAILABLE"
            raise MessagerPeerError(
                code,
                str(error.get("message") or "Peer assertion is unavailable."),
                status_code=503 if unavailable else response.status_code,
                retryable=unavailable,
            )
        verified = await self._verify(
            assertion_payload["assertion"],
            handshake_id=handshake_id,
            self_endpoint=assertion_payload["self"],
            peer_endpoint=assertion_payload["peer"],
        )
        peer = assertion_payload["peer"]
        if peer.get("online") is not True:
            raise MessagerPeerError(
                "MESSAGER_LOCAL_UNAVAILABLE", "The peer Local Device is offline.", status_code=503, retryable=True
            )
        _, device = self._installation_device()
        exchange, first = InitiatorExchange.begin(
            keys=self.keys.load(device.device_id),
            peer_static_public=peer["staticDhPublicKey"],
            handshake_id=handshake_id,
            assertion_jti=verified.claims["jti"],
        )
        origin = verified.claims["recipient_public_origin"].rstrip("/")
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(
            base_url=origin, timeout=timeout, follow_redirects=False
        ) as client:
            try:
                handshake_response = await client.post(
                    "/v1/messager/peer/v1/handshakes",
                    json={
                        "assertion": assertion_payload["assertion"],
                        "handshakeId": handshake_id,
                        "initiator": assertion_payload["self"],
                        "noiseMessage": b64url_encode(first),
                    },
                )
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                raise MessagerPeerError(
                    "MESSAGER_LOCAL_UNAVAILABLE", "The peer Local Device is unreachable.", status_code=503, retryable=True
                ) from error
            if handshake_response.status_code != 201:
                raise MessagerPeerError(
                    "MESSAGER_LOCAL_HANDSHAKE_REJECTED", "The peer rejected the encrypted handshake.", status_code=502
                )
            handshake_result = handshake_response.json()
            exchange.finish(b64url_decode(handshake_result["noiseMessage"]))
            ciphertext = exchange.encrypt_text(
                client_message_id=client_message_id,
                sender_user_id=principal.actor_user_id,
                recipient_user_id=recipient_user_id,
                body=body,
            )
            try:
                message_response = await client.post(
                    "/v1/messager/peer/v1/messages",
                    json={
                        "sessionId": handshake_result["sessionId"],
                        "ciphertext": b64url_encode(ciphertext),
                    },
                )
            except (httpx.TimeoutException, httpx.TransportError) as error:
                self.repository.record_local_outgoing(
                    owner_user_id=principal.actor_user_id,
                    peer_user_id=recipient_user_id,
                    client_message_id=client_message_id,
                    body=body,
                    status="result_unknown",
                )
                raise MessagerPeerError(
                    "MESSAGER_RESULT_UNKNOWN",
                    "The encrypted message may have arrived; Cloud fallback is disabled.",
                    status_code=503,
                ) from error
            if message_response.status_code != 200:
                self.repository.record_local_outgoing(
                    owner_user_id=principal.actor_user_id,
                    peer_user_id=recipient_user_id,
                    client_message_id=client_message_id,
                    body=body,
                    status="result_unknown",
                )
                raise MessagerPeerError(
                    "MESSAGER_RESULT_UNKNOWN",
                    "The encrypted message may have arrived; Cloud fallback is disabled.",
                    status_code=503,
                )
            try:
                ack = exchange.decrypt_ack(
                    b64url_decode(message_response.json()["ciphertext"])
                )
            except (KeyError, ValueError, MessagerNoiseError) as error:
                self.repository.record_local_outgoing(
                    owner_user_id=principal.actor_user_id,
                    peer_user_id=recipient_user_id,
                    client_message_id=client_message_id,
                    body=body,
                    status="result_unknown",
                )
                raise MessagerPeerError(
                    "MESSAGER_RESULT_UNKNOWN",
                    "The encrypted message may have arrived; Cloud fallback is disabled.",
                    status_code=503,
                ) from error
        if ack["clientMessageId"] != client_message_id or ack["status"] not in {"received", "duplicate"}:
            self.repository.record_local_outgoing(
                owner_user_id=principal.actor_user_id,
                peer_user_id=recipient_user_id,
                client_message_id=client_message_id,
                body=body,
                status="result_unknown",
            )
            raise MessagerPeerError(
                "MESSAGER_RESULT_UNKNOWN",
                "The peer acknowledgement is invalid; Cloud fallback is disabled.",
                status_code=503,
            )
        row = self.repository.record_local_outgoing(
            owner_user_id=principal.actor_user_id,
            peer_user_id=recipient_user_id,
            client_message_id=client_message_id,
            body=body,
        )
        return {"status": "sent", "transport": "local_e2ee", "message": row}
