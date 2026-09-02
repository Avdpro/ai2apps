"""Local composition root for protocol-neutral Peer control-plane services."""

from __future__ import annotations

import asyncio
import os
import socket
import time
from collections.abc import Awaitable, Callable

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.identity import IdentityRepository, RequestPrincipal
from ai2apps.remote import RemoteAccessManager
from ai2apps.secrets import SecretBackend
from ai2apps.storage import PlatformDatabase

from .broker import PeerBrokerClient, PeerBrokerError
from .grants import VerifiedPeerGrant, verify_peer_grant
from .identity import PeerDeviceKeyManager
from .repository import PeerSessionRepository
from .session import PeerSession
from .transports.base import PeerTransportResponse, PeerTransportStream
from .transports.direct_quic import (
    DirectAuthorization,
    DirectQuicServer,
    DirectQuicTransport,
)
from .transports.fallback import DirectThenRelayTransport
from .transports.relay_https import RelayHttpsTransport

DirectRouteHandler = Callable[[str, bytes], Awaitable[PeerTransportResponse | PeerTransportStream]]


class PeerTransportCore:
    """Resolve Device authority lazily so account provisioning can happen after startup."""

    def __init__(
        self, *, database: PlatformDatabase, cloud: AI2AppsCloudClient,
        remote: RemoteAccessManager, secret_backend: SecretBackend,
    ) -> None:
        self.cloud = cloud
        self.remote = remote
        self.identities = IdentityRepository(database)
        self.keys = PeerDeviceKeyManager(secret_backend)
        self.sessions = PeerSessionRepository(database)
        self._brokers: dict[str, PeerBrokerClient] = {}
        self._direct_handlers: dict[str, DirectRouteHandler] = {}
        self._direct_server = DirectQuicServer(
            authorize=self._authorize_direct, handler=self._handle_direct,
        )
        self._candidate_generations: dict[str, int] = {}

    def broker_for(self, principal: RequestPrincipal) -> PeerBrokerClient:
        installation = self.identities.get_installation()
        if installation is None or installation.status != "active":
            raise PeerBrokerError(
                "PEER_INSTALLATION_INACTIVE", "The Local installation is not active.", status_code=403
            )
        if principal.installation_id != installation.id:
            raise PeerBrokerError(
                "PEER_PRINCIPAL_INVALID", "The Local actor does not belong to this Installation.", status_code=403
            )
        device = self.remote.require_device(installation.cloud_device_id)
        if device.status != "active":
            raise PeerBrokerError("PEER_DEVICE_INACTIVE", "The Local Cloud Device is not active.", status_code=403)
        broker = self._brokers.get(device.device_id)
        if broker is None:
            broker = PeerBrokerClient(
                cloud=self.cloud, keys=self.keys, device_id=device.device_id,
                device_headers=lambda actor: self.remote.cloud_ai_headers(
                    device_id=device.device_id, principal=actor
                ),
                session_repository=self.sessions,
            )
            self._brokers[device.device_id] = broker
        return broker

    @staticmethod
    def relay_transport_for(session: PeerSession) -> RelayHttpsTransport:
        if "relay_https" not in session.transport_policy.allowed_transports:
            raise PeerBrokerError("PEER_TRANSPORT_NOT_ALLOWED", "Relay HTTPS is not allowed for this Session.", status_code=409)
        origin = session.peer_endpoint.relay_origin
        if origin is None:
            raise PeerBrokerError("PEER_RELAY_ORIGIN_UNAVAILABLE", "Cloud did not authorize a Peer Relay origin.", status_code=409)
        return RelayHttpsTransport(origin)

    def register_direct_handler(self, path: str, handler: DirectRouteHandler) -> None:
        allowed = {
            "/v1/messager/peer/v2/handshakes",
            "/v1/messager/peer/v2/messages",
            "/v1/model-share/peer/v1/inference",
        }
        if path not in allowed or path in self._direct_handlers:
            raise ValueError("Direct Peer route is invalid or already registered")
        self._direct_handlers[path] = handler

    async def shutdown(self) -> None:
        await self._direct_server.close()

    async def _authorize_direct(self, grant: str, session_id: str) -> DirectAuthorization:
        record = self.sessions.get(session_id)
        if record is None:
            raise PeerBrokerError("PEER_SESSION_NOT_FOUND", "Peer Session was not found.", status_code=404)
        principal = self.identities.principal_for(record.owner_user_id)
        broker = self.broker_for(principal)
        # A new Direct stream must revalidate both the Cloud Session and the
        # signing key set. Fetch them concurrently so the required online
        # authorization still fits inside the frozen QUIC + Noise deadline.
        session, jwks = await asyncio.gather(
            broker.get_session(principal, session_id), broker.jwks(),
        )
        if session.status != "active" or "direct_quic" not in session.transport_policy.allowed_transports:
            raise PeerBrokerError("PEER_TRANSPORT_NOT_ALLOWED", "Direct QUIC is not allowed.", status_code=403)
        verified = verify_peer_grant(
            grant, jwks, session=session,
            holder_user_id=session.peer_endpoint.user_id,
            holder_device_id=session.peer_endpoint.device_id,
        )
        keys = self.keys.get_or_create(session.self_endpoint.device_id, session.protocol)
        return DirectAuthorization(session, verified.claims, keys, grant)

    async def _handle_direct(self, authorization: DirectAuthorization, path: str, payload: bytes):
        handler = self._direct_handlers.get(path)
        if handler is None:
            raise PeerBrokerError("PEER_DIRECT_ROUTE_UNAVAILABLE", "Direct Peer route is unavailable.", status_code=404)
        return await handler(authorization.grant, payload)

    @staticmethod
    def _candidate_address() -> str:
        configured = os.environ.get("AI2APPS_PEER_DIRECT_CANDIDATE_ADDRESS", "").strip()
        if configured:
            return configured
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("192.0.2.1", 9))
            address = str(sock.getsockname()[0])
        finally:
            sock.close()
        if address.startswith("127.") or address == "0.0.0.0":
            raise PeerBrokerError("DIRECT_NO_CANDIDATE", "No publishable LAN Candidate is available.", status_code=503)
        return address

    async def publish_direct_candidate(
        self, principal: RequestPrincipal, session: PeerSession, broker: PeerBrokerClient | None = None,
    ) -> None:
        if session.status != "active" or "direct_quic" not in session.transport_policy.allowed_transports:
            return
        port = await self._direct_server.start(
            port=int(os.environ.get("AI2APPS_PEER_DIRECT_PORT", "0")),
        )
        generation = max(int(time.time()), self._candidate_generations.get(session.session_id, 0) + 1)
        self._candidate_generations[session.session_id] = generation
        await (broker or self.broker_for(principal)).add_candidate(
            principal, session.session_id, candidate_type="lan", transport="udp",
            address=self._candidate_address(), port=port, priority=100, generation=generation,
        )

    async def transport_for(
        self, *, principal: RequestPrincipal, session: PeerSession, grant: VerifiedPeerGrant,
    ):
        broker = self.broker_for(principal)
        relay = None
        if "relay_https" in session.transport_policy.allowed_transports:
            relay = self.relay_transport_for(session)
        if "direct_quic" not in session.transport_policy.allowed_transports:
            if relay is None:
                raise PeerBrokerError("PEER_TRANSPORT_NOT_ALLOWED", "No Peer transport is allowed.", status_code=409)
            return relay
        try:
            await self.publish_direct_candidate(principal, session, broker)
        except (OSError, PeerBrokerError):
            if relay is None:
                raise
        try:
            candidates = await broker.list_candidates(principal, session.session_id)
        except PeerBrokerError:
            if relay is not None:
                return relay
            raise
        candidates = sorted(
            (item for item in candidates if item.get("transport") == "udp"),
            key=lambda item: int(item.get("priority", 0)), reverse=True,
        )
        if not candidates:
            if relay is not None:
                return relay
            raise PeerBrokerError("DIRECT_NO_CANDIDATE", "Peer has no Direct QUIC Candidate.", status_code=503, retryable=True)
        candidate = candidates[0]
        direct = DirectQuicTransport(
            address=str(candidate["address"]), port=int(candidate["port"]),
            session=session,
            keys=self.keys.get_or_create(session.self_endpoint.device_id, session.protocol),
            grant=grant.compact, claims=grant.claims,
        )
        return direct if relay is None else DirectThenRelayTransport(direct, relay)
