"""Cloud-authorized Messager Peer v2 control and encrypted data plane."""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import time
import uuid
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ai2apps.core import utc_now_text
from ai2apps.events import EventStore
from ai2apps.identity import IdentityBindingError, RequestPrincipal
from ai2apps.peer.broker import PeerBrokerClient, PeerBrokerError
from ai2apps.peer.core import PeerTransportCore
from ai2apps.peer.grants import PeerGrantError, verify_peer_grant
from ai2apps.peer.identity import PeerProtocol, b64url_decode, b64url_encode
from ai2apps.peer.session import PeerSession
from ai2apps.peer.transports import PeerTransportError, PeerTransportResponse
from ai2apps.storage import PlatformDatabase

from .noise_v2 import MessagerV2NoiseError, V2InitiatorExchange, V2ResponderExchange
from .peer_service import MessagerPeerError
from .repository import MessagerIdempotencyConflictError, MessagerRepository


@dataclass(slots=True)
class _InboundConnection:
    exchange: V2ResponderExchange
    owner_user_id: str
    peer_user_id: str
    expires_at: float


class MessagerV2SessionCoordinator:
    """One-message Noise connections over short-lived Peer Session Grants."""

    def __init__(self, *, core: PeerTransportCore, database: PlatformDatabase,
                 events: EventStore | None = None) -> None:
        self.core = core
        self.repository = MessagerRepository(database, events)
        self._connections: dict[str, _InboundConnection] = {}
        self._connections_lock = asyncio.Lock()
        self._poll_stop: asyncio.Event | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self.core.register_direct_handler(
            "/v1/messager/peer/v2/handshakes", self._direct_handshake,
        )
        self.core.register_direct_handler(
            "/v1/messager/peer/v2/messages", self._direct_message,
        )

    async def _direct_handshake(self, grant: str, payload: bytes) -> PeerTransportResponse:
        value = json.loads(payload)
        result = await self.accept_handshake(grant, value)
        return PeerTransportResponse(
            200, {"content-type": "application/json"},
            json.dumps(result, separators=(",", ":")).encode(),
        )

    async def _direct_message(self, grant: str, payload: bytes) -> PeerTransportResponse:
        value = json.loads(payload)
        result = await self.accept_message(grant, value)
        return PeerTransportResponse(
            200, {"content-type": "application/json"},
            json.dumps(result, separators=(",", ":")).encode(),
        )

    def broker_for(self, principal: RequestPrincipal) -> PeerBrokerClient:
        return self.core.broker_for(principal)

    @staticmethod
    def conversation_id(first_user_id: str, second_user_id: str) -> str:
        pair = "\0".join(sorted((first_user_id, second_user_id))).encode("ascii")
        return f"conversation:{hashlib.sha256(pair).hexdigest()}"

    async def open_session(self, *, principal: RequestPrincipal, peer_user_id: str,
                           conversation_id: str | None = None,
                           idempotency_key: str | None = None) -> PeerSession:
        purpose = conversation_id or self.conversation_id(principal.actor_user_id, peer_user_id)
        return await self.broker_for(principal).create_session(
            principal=principal, protocol=PeerProtocol.MESSAGER_V2,
            peer_user_id=peer_user_id, purpose_id=purpose,
            idempotency_key=idempotency_key or f"messager-v2:{purpose}",
            requested_transports=("direct_quic", "relay_https"),
        )

    async def accept_pending(self, principal: RequestPrincipal) -> list[PeerSession]:
        broker = self.broker_for(principal)
        accepted: list[PeerSession] = []
        for session in await broker.list_sessions(principal, status="pending"):
            if session.protocol is PeerProtocol.MESSAGER_V2:
                active = await broker.accept_session(principal, session.session_id)
                if active.status == "active":
                    with suppress(OSError, PeerBrokerError):
                        await self.core.publish_direct_candidate(principal, active, broker)
                    accepted.append(active)
        return accepted

    async def startup(self, *, poll_interval_seconds: float = 5.0) -> None:
        if self._poll_task is None:
            self._poll_stop = asyncio.Event()
            self._poll_task = asyncio.create_task(
                self._poll_pending(poll_interval_seconds), name="ai2apps-messager-v2-pending"
            )

    async def shutdown(self) -> None:
        if self._poll_stop is not None:
            self._poll_stop.set()
        if self._poll_task is not None:
            await self._poll_task
        self._poll_task = None
        self._poll_stop = None
        async with self._connections_lock:
            self._connections.clear()

    async def _poll_pending(self, interval: float) -> None:
        assert self._poll_stop is not None
        while not self._poll_stop.is_set():
            installation = self.core.identities.get_installation()
            if installation is not None and installation.status == "active":
                with suppress(IdentityBindingError, PeerBrokerError, RuntimeError):
                    principal = self.core.identities.principal_for(installation.core_user_id)
                    broker = self.broker_for(principal)
                    # A recipient cannot appear in a new Cloud Session until
                    # its protocol key exists. Register proactively instead of
                    # waiting for an outbound message to bootstrap the key.
                    await broker.ensure_registered(principal, PeerProtocol.MESSAGER_V2)
                    await self.accept_pending(principal)
            with suppress(TimeoutError):
                await asyncio.wait_for(self._poll_stop.wait(), timeout=interval)

    async def _active_session(self, principal: RequestPrincipal, session: PeerSession) -> PeerSession:
        if session.status == "active":
            return session
        broker = self.broker_for(principal)
        for _ in range(10):
            await asyncio.sleep(0.5)
            session = await broker.get_session(principal, session.session_id)
            if session.status == "active":
                return session
            if session.status != "pending":
                break
        raise MessagerPeerError(
            "MESSAGER_LOCAL_UNAVAILABLE", "The peer Local Device did not accept the v2 Session.",
            status_code=503, retryable=True,
        )

    async def _verify_inbound(self, bearer_grant: str, session_id: str):
        record = self.core.sessions.get(session_id)
        if record is None:
            raise MessagerPeerError("PEER_SESSION_NOT_FOUND", "Peer Session was not found.", status_code=404)
        try:
            principal = self.core.identities.principal_for(record.owner_user_id)
            broker = self.broker_for(principal)
            session = await broker.get_session(principal, session_id)
        except (IdentityBindingError, PeerBrokerError) as error:
            raise MessagerPeerError("PEER_SESSION_INVALID", "Peer Session is unavailable.", status_code=403) from error
        if session.protocol is not PeerProtocol.MESSAGER_V2 or session.status != "active" or session.expires_at <= datetime.now(UTC):
            raise MessagerPeerError("PEER_SESSION_INVALID", "Peer Session is not active.", status_code=403)
        try:
            grant = verify_peer_grant(
                bearer_grant, await broker.jwks(), session=session,
                holder_user_id=session.peer_endpoint.user_id,
                holder_device_id=session.peer_endpoint.device_id,
            )
        except (PeerGrantError, PeerBrokerError) as error:
            raise MessagerPeerError("PEER_GRANT_INVALID", str(error), status_code=401) from error
        if not self.core.sessions.consume_grant_jti(
            jti=grant.claims["jti"], session_id=session_id,
            expires_at=datetime.fromtimestamp(grant.claims["exp"], UTC),
        ):
            raise MessagerPeerError("PEER_GRANT_REPLAYED", "Peer Grant was already consumed.", status_code=409)
        return session, grant.claims

    async def accept_handshake(self, bearer_grant: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if set(payload) != {"version", "sessionId", "handshakeId", "noiseMessage"} or payload.get("version") != 2:
            raise MessagerPeerError("MESSAGER_V2_HANDSHAKE_INVALID", "Handshake fields are invalid.")
        session_id, handshake_id, encoded = payload.get("sessionId"), payload.get("handshakeId"), payload.get("noiseMessage")
        if not all(isinstance(value, str) for value in (session_id, handshake_id, encoded)):
            raise MessagerPeerError("MESSAGER_V2_HANDSHAKE_INVALID", "Handshake fields are invalid.")
        session, claims = await self._verify_inbound(bearer_grant, session_id)
        connection_id = b64url_encode(secrets.token_bytes(32))
        try:
            keys = self.core.keys.get_or_create(session.self_endpoint.device_id, PeerProtocol.MESSAGER_V2)
            exchange, response = V2ResponderExchange.accept(
                keys=keys, session=session, handshake_id=handshake_id,
                handshake_grant_jti=claims["jti"], connection_id=connection_id,
                request=b64url_decode(encoded),
            )
        except (ValueError, MessagerV2NoiseError) as error:
            raise MessagerPeerError("MESSAGER_V2_HANDSHAKE_INVALID", str(error)) from error
        now = time.monotonic()
        async with self._connections_lock:
            self._connections = {key: value for key, value in self._connections.items() if value.expires_at > now}
            if len(self._connections) >= 256:
                raise MessagerPeerError("MESSAGER_V2_BUSY", "Too many encrypted connections.", status_code=429, retryable=True)
            self._connections[connection_id] = _InboundConnection(
                exchange, session.self_endpoint.user_id, session.peer_endpoint.user_id, now + 90
            )
        return {"version": 2, "sessionId": session_id, "handshakeId": handshake_id,
                "connectionId": connection_id, "noiseMessage": b64url_encode(response)}

    async def accept_message(self, bearer_grant: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        fields = {"version", "sessionId", "connectionId", "sequence", "ciphertext"}
        if set(payload) != fields or payload.get("version") != 2 or payload.get("sequence") != "0":
            raise MessagerPeerError("MESSAGER_V2_MESSAGE_INVALID", "Message fields are invalid.")
        session_id, connection_id, encoded = payload.get("sessionId"), payload.get("connectionId"), payload.get("ciphertext")
        if not all(isinstance(value, str) for value in (session_id, connection_id, encoded)):
            raise MessagerPeerError("MESSAGER_V2_MESSAGE_INVALID", "Message fields are invalid.")
        session, claims = await self._verify_inbound(bearer_grant, session_id)
        async with self._connections_lock:
            connection = self._connections.pop(connection_id, None)
        if connection is None or connection.expires_at <= time.monotonic():
            raise MessagerPeerError("MESSAGER_V2_CONNECTION_REPLAYED", "Encrypted connection is missing or consumed.", status_code=409)
        if connection.exchange.session_id != session.session_id:
            raise MessagerPeerError("MESSAGER_V2_MESSAGE_INVALID", "Message Session binding is invalid.", status_code=403)
        try:
            message = connection.exchange.decrypt_text(b64url_decode(encoded), message_grant_jti=claims["jti"])
        except (ValueError, MessagerV2NoiseError) as error:
            raise MessagerPeerError("MESSAGER_V2_MESSAGE_INVALID", str(error)) from error
        if message["senderUserId"] != connection.peer_user_id or message["recipientUserId"] != connection.owner_user_id:
            raise MessagerPeerError("MESSAGER_V2_MESSAGE_BINDING_INVALID", "Message users do not match the Session.", status_code=403)
        try:
            _row, created = self.repository.record_local_incoming(
                owner_user_id=connection.owner_user_id, peer_user_id=connection.peer_user_id,
                remote_message_id=message["clientMessageId"], body=message["body"],
            )
        except MessagerIdempotencyConflictError as error:
            raise MessagerPeerError("MESSAGER_IDEMPOTENCY_CONFLICT", str(error), status_code=409) from error
        ack = connection.exchange.encrypt_ack(
            message_grant_jti=claims["jti"], client_message_id=message["clientMessageId"],
            received_at=utc_now_text(), status="received" if created else "duplicate",
        )
        return {"version": 2, "sessionId": session_id, "connectionId": connection_id,
                "sequence": "0", "ciphertext": b64url_encode(ack)}

    async def send_local(self, *, principal: RequestPrincipal, recipient_user_id: str,
                         client_message_id: str, body: str) -> dict[str, Any]:
        session = await self._active_session(
            principal, await self.open_session(
                principal=principal,
                peer_user_id=recipient_user_id,
                idempotency_key=f"messager-v2-message:{client_message_id}",
            )
        )
        broker = self.broker_for(principal)
        keys = self.core.keys.get_or_create(session.self_endpoint.device_id, PeerProtocol.MESSAGER_V2)
        handshake_grant = await broker.refresh_grant(principal, session.session_id)
        handshake_id = str(uuid.uuid4())
        exchange, first = V2InitiatorExchange.begin(
            keys=keys, session=session, handshake_id=handshake_id,
            handshake_grant_jti=handshake_grant.claims["jti"],
        )
        dispatched = False
        try:
            transport = await self.core.transport_for(
                principal=principal, session=session, grant=handshake_grant,
            )
            response = await transport.post(
                path="/v1/messager/peer/v2/handshakes", grant=handshake_grant.compact,
                payload=json.dumps({"version": 2, "sessionId": session.session_id,
                    "handshakeId": handshake_id, "noiseMessage": b64url_encode(first)},
                    separators=(",", ":")).encode(), max_response_bytes=16_384,
            )
            handshake = json.loads(response.body)
            if set(handshake) != {"version", "sessionId", "handshakeId", "connectionId", "noiseMessage"}:
                raise MessagerV2NoiseError("Messager v2 handshake response fields are invalid")
            connection_id = exchange.finish(b64url_decode(handshake["noiseMessage"]))
            if handshake["sessionId"] != session.session_id or handshake["handshakeId"] != handshake_id or handshake["connectionId"] != connection_id:
                raise MessagerV2NoiseError("Messager v2 handshake response binding is invalid")
            message_grant = await broker.refresh_grant(principal, session.session_id)
            ciphertext = exchange.encrypt_text(
                message_grant_jti=message_grant.claims["jti"], client_message_id=client_message_id,
                sender_user_id=principal.actor_user_id, recipient_user_id=recipient_user_id, body=body,
            )
            dispatched = True
            transport = await self.core.transport_for(
                principal=principal, session=session, grant=message_grant,
            )
            response = await transport.post(
                path="/v1/messager/peer/v2/messages", grant=message_grant.compact,
                payload=json.dumps({"version": 2, "sessionId": session.session_id,
                    "connectionId": connection_id, "sequence": "0", "ciphertext": b64url_encode(ciphertext)},
                    separators=(",", ":")).encode(), max_response_bytes=16_384,
            )
            result = json.loads(response.body)
            if set(result) != {"version", "sessionId", "connectionId", "sequence", "ciphertext"}:
                raise MessagerV2NoiseError("Messager v2 message response fields are invalid")
            ack = exchange.decrypt_ack(
                b64url_decode(result["ciphertext"]), message_grant_jti=message_grant.claims["jti"],
                client_message_id=client_message_id,
            )
        except (KeyError, ValueError, json.JSONDecodeError, MessagerV2NoiseError, PeerTransportError) as error:
            if dispatched:
                self.repository.record_local_outgoing(
                    owner_user_id=principal.actor_user_id, peer_user_id=recipient_user_id,
                    client_message_id=client_message_id, body=body, status="result_unknown",
                )
                raise MessagerPeerError("MESSAGER_RESULT_UNKNOWN", "The encrypted v2 message may have arrived.", status_code=503) from error
            code = error.code if isinstance(error, PeerTransportError) else "MESSAGER_V2_HANDSHAKE_FAILED"
            raise MessagerPeerError(code, "Messager v2 handshake failed.", status_code=503, retryable=True) from error
        row = self.repository.record_local_outgoing(
            owner_user_id=principal.actor_user_id, peer_user_id=recipient_user_id,
            client_message_id=client_message_id, body=body, status="sent",
        )
        # A v2 data-plane connection carries one logical message. Close the
        # matching Cloud Session after its authenticated ack so acceptance and
        # retry tests cannot leave an active authorization behind.
        with suppress(PeerBrokerError):
            await broker.close_session(principal, session.session_id)
        return {"status": "sent", "transport": "peer_v2_e2ee", "ack": ack["status"], "message": row}
