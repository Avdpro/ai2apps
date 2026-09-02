"""QUIC v1 socket transport for the frozen AI2Apps Peer Direct profile."""

from __future__ import annotations

import asyncio
import logging
import secrets
import ssl
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aioquic.asyncio import connect, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.packet import QuicProtocolVersion
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from ai2apps.peer.direct_v1 import (
    ALPN,
    HEADER_SIZE,
    MAX_RECORD_PAYLOAD,
    DirectInitiatorHandshake,
    DirectRecord,
    DirectRecordType,
    DirectResponderHandshake,
    PeerDirectError,
    canonical_json,
    decode_object,
    parse_record,
    plain_record,
)
from ai2apps.peer.identity import PeerDeviceKeys, b64url_decode, b64url_encode
from ai2apps.peer.session import PeerSession

from .base import (
    PeerTransportError,
    PeerTransportResponse,
    PeerTransportStream,
)

DirectHandler = Callable[
    ["DirectAuthorization", str, bytes],
    Awaitable[PeerTransportResponse | PeerTransportStream],
]
DirectAuthorizer = Callable[[str, str], Awaitable["DirectAuthorization"]]

logger = logging.getLogger(__name__)

# A held Compute Contract is valid for ten minutes. Model execution may be
# silent while a Worker loads weights or renders an artifact, so the QUIC
# transport must not treat the old ten-second interactive-message timeout as
# proof that the peer disappeared. Keep the bound finite and aligned with the
# Cloud contract window; application-level request and result limits still
# apply independently.
DIRECT_IDLE_TIMEOUT_SECONDS = 10 * 60


@dataclass(frozen=True, slots=True)
class DirectAuthorization:
    session: PeerSession
    claims: Mapping[str, Any]
    keys: PeerDeviceKeys
    grant: str


async def _read_record(reader: asyncio.StreamReader) -> DirectRecord:
    try:
        header = await reader.readexactly(HEADER_SIZE)
        size = int.from_bytes(header[8:12], "big")
        if size > MAX_RECORD_PAYLOAD:
            raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct Record is too large.")
        return parse_record(header + await reader.readexactly(size))
    except (asyncio.IncompleteReadError, ConnectionError) as error:
        raise PeerDirectError("DIRECT_QUIC_FAILED", "Direct QUIC Stream ended early.") from error


def _client_configuration() -> QuicConfiguration:
    return QuicConfiguration(
        is_client=True,
        alpn_protocols=[ALPN],
        supported_versions=[QuicProtocolVersion.VERSION_1],
        verify_mode=ssl.CERT_NONE,
        idle_timeout=DIRECT_IDLE_TIMEOUT_SECONDS,
        max_data=8 * MAX_RECORD_PAYLOAD,
        max_stream_data=2 * MAX_RECORD_PAYLOAD,
    )


def _server_configuration() -> QuicConfiguration:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AI2Apps Peer Ephemeral")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    configuration = QuicConfiguration(
        is_client=False,
        alpn_protocols=[ALPN],
        supported_versions=[QuicProtocolVersion.VERSION_1],
        idle_timeout=DIRECT_IDLE_TIMEOUT_SECONDS,
        max_data=8 * MAX_RECORD_PAYLOAD,
        max_stream_data=2 * MAX_RECORD_PAYLOAD,
    )
    configuration.certificate = certificate
    configuration.private_key = key
    return configuration


class DirectQuicServer:
    def __init__(self, *, authorize: DirectAuthorizer, handler: DirectHandler) -> None:
        self.authorize = authorize
        self.handler = handler
        self._server = None
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def port(self) -> int | None:
        if self._server is None:
            return None
        transport = getattr(self._server, "_transport", None)
        address = None if transport is None else transport.get_extra_info("sockname")
        return None if not address else int(address[1])

    async def start(self, *, host: str = "0.0.0.0", port: int = 0) -> int:
        if self._server is None:
            def stream_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
                task = asyncio.create_task(self._handle_stream(reader, writer), name="ai2apps-peer-direct-stream")
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

            self._server = await serve(
                host, port, configuration=_server_configuration(), stream_handler=stream_handler,
            )
        assert self.port is not None
        return self.port

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)

    async def _handle_stream(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            hello = await _read_record(reader)
            if hello.record_type is not DirectRecordType.CLIENT_HELLO:
                raise PeerDirectError("DIRECT_FRAME_REJECTED", "Client Hello must be first.")
            value = decode_object(hello.payload, {"grant", "noiseMessage", "protocolVersion", "sessionId"})
            if value["protocolVersion"] != 1 or not isinstance(value["grant"], str):
                raise PeerDirectError("DIRECT_GRANT_REJECTED", "Direct Client Hello is invalid.")
            authorization = await self.authorize(value["grant"], value["sessionId"])
            connection_id = b64url_encode(secrets.token_bytes(32))
            state, response = DirectResponderHandshake.accept(
                keys=authorization.keys,
                session=authorization.session,
                claims=authorization.claims,
                message=b64url_decode(value["noiseMessage"]),
                connection_id=connection_id,
            )
            writer.write(plain_record(DirectRecordType.SERVER_HELLO, canonical_json({
                "connectionId": connection_id,
                "noiseMessage": b64url_encode(response),
                "protocolVersion": 1,
                "sessionId": authorization.session.session_id,
            })))
            await writer.drain()
            head_record = await _read_record(reader)
            request_head = decode_object(
                state.decrypt_record(
                    head_record.header + head_record.payload, DirectRecordType.REQUEST_HEAD,
                ),
                {"contentType", "method", "path"},
            )
            if (
                request_head["method"] != "POST"
                or request_head["contentType"] != "application/json"
                or request_head["path"] not in {
                    "/v1/messager/peer/v2/handshakes",
                    "/v1/messager/peer/v2/messages",
                    "/v1/model-share/peer/v1/inference",
                }
            ):
                raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct request route is not allowed.")
            content = bytearray()
            while True:
                record = await _read_record(reader)
                if record.record_type is DirectRecordType.REQUEST_END:
                    state.decrypt_record(record.header + record.payload, DirectRecordType.REQUEST_END)
                    break
                chunk = state.decrypt_record(record.header + record.payload, DirectRecordType.REQUEST_BODY)
                content.extend(chunk)
                if len(content) > authorization.session.transport_policy.max_bytes:
                    raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct request exceeds the Session limit.")
            result = await self.handler(authorization, request_head["path"], bytes(content))
            content_type = result.headers.get("content-type", "application/json").split(";", 1)[0]
            if content_type not in {"application/json", "text/event-stream"}:
                raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct response content type is invalid.")
            writer.write(state.encrypt_record(DirectRecordType.RESPONSE_HEAD, canonical_json({
                "contentType": content_type, "status": result.status_code,
            })))
            if isinstance(result, PeerTransportStream):
                async for chunk in result.body:
                    for offset in range(0, len(chunk), MAX_RECORD_PAYLOAD - 16):
                        writer.write(state.encrypt_record(
                            DirectRecordType.RESPONSE_BODY,
                            chunk[offset:offset + MAX_RECORD_PAYLOAD - 16],
                        ))
                        await writer.drain()
            else:
                for offset in range(0, len(result.body), MAX_RECORD_PAYLOAD - 16):
                    writer.write(state.encrypt_record(
                        DirectRecordType.RESPONSE_BODY,
                        result.body[offset:offset + MAX_RECORD_PAYLOAD - 16],
                    ))
            writer.write(state.encrypt_record(DirectRecordType.RESPONSE_END, b""))
            await writer.drain()
        except BaseException as error:
            # Keep Direct diagnostics useful without ever emitting Grants,
            # candidates, addresses, payloads, or exception strings.
            code = getattr(error, "code", "DIRECT_QUIC_FAILED")
            logger.warning("Direct Peer stream rejected: %s", code)
        finally:
            writer.close()


class DirectQuicTransport:
    def __init__(self, *, address: str, port: int, session: PeerSession,
                 keys: PeerDeviceKeys, grant: str, claims: Mapping[str, Any]) -> None:
        self.address = address
        self.port = port
        self.session = session
        self.keys = keys
        self.grant = grant
        self.claims = claims

    async def post_stream(self, *, path: str, grant: str, payload: bytes,
                          max_response_bytes: int) -> PeerTransportStream:
        if grant != self.grant:
            raise PeerTransportError("DIRECT_GRANT_REJECTED", "Direct Grant changed before dispatch.")
        manager = connect(
            self.address, self.port, configuration=_client_configuration(), wait_connected=True,
        )
        dispatched = False
        try:
            protocol = await asyncio.wait_for(manager.__aenter__(), timeout=1.5)
            reader, writer = await protocol.create_stream()
            handshake, first = DirectInitiatorHandshake.begin(
                keys=self.keys, session=self.session, claims=self.claims,
            )
            writer.write(plain_record(DirectRecordType.CLIENT_HELLO, canonical_json({
                "grant": grant,
                "noiseMessage": b64url_encode(first),
                "protocolVersion": 1,
                "sessionId": self.session.session_id,
            })))
            await writer.drain()
            server_hello = await asyncio.wait_for(_read_record(reader), timeout=1.0)
            if server_hello.record_type is not DirectRecordType.SERVER_HELLO:
                raise PeerDirectError("DIRECT_FRAME_REJECTED", "Server Hello is invalid.")
            hello = decode_object(server_hello.payload, {"connectionId", "noiseMessage", "protocolVersion", "sessionId"})
            if hello["protocolVersion"] != 1 or hello["sessionId"] != self.session.session_id:
                raise PeerDirectError("DIRECT_NOISE_REJECTED", "Server Hello binding is invalid.")
            state = handshake.finish(b64url_decode(hello["noiseMessage"]), hello["connectionId"])
            writer.write(state.encrypt_record(DirectRecordType.REQUEST_HEAD, canonical_json({
                "contentType": "application/json", "method": "POST", "path": path,
            })))
            for offset in range(0, len(payload), MAX_RECORD_PAYLOAD - 16):
                writer.write(state.encrypt_record(
                    DirectRecordType.REQUEST_BODY, payload[offset:offset + MAX_RECORD_PAYLOAD - 16],
                ))
            writer.write(state.encrypt_record(DirectRecordType.REQUEST_END, b""))
            await writer.drain()
            dispatched = True
            head_record = await _read_record(reader)
            head = decode_object(
                state.decrypt_record(head_record.header + head_record.payload, DirectRecordType.RESPONSE_HEAD),
                {"contentType", "status"},
            )
        except (TimeoutError, OSError, PeerDirectError) as error:
            await manager.__aexit__(type(error), error, error.__traceback__)
            code = error.code if isinstance(error, PeerDirectError) else "DIRECT_QUIC_FAILED"
            raise PeerTransportError(
                "DIRECT_RESULT_UNKNOWN" if dispatched else code,
                "Direct QUIC ended after dispatch." if dispatched else "Direct QUIC is unavailable.",
                retryable=not dispatched,
                result_unknown=dispatched,
            ) from error

        async def body():
            count = 0
            try:
                while True:
                    record = await _read_record(reader)
                    if record.record_type is DirectRecordType.RESPONSE_END:
                        state.decrypt_record(record.header + record.payload, DirectRecordType.RESPONSE_END)
                        break
                    chunk = state.decrypt_record(record.header + record.payload, DirectRecordType.RESPONSE_BODY)
                    count += len(chunk)
                    if count > max_response_bytes:
                        raise PeerTransportError(
                            "PEER_RESPONSE_LIMIT_EXCEEDED", "Peer response exceeded the Session byte limit."
                        )
                    yield chunk
            except (OSError, PeerDirectError) as error:
                raise PeerTransportError(
                    "DIRECT_RESULT_UNKNOWN", "Direct QUIC ended after request dispatch.", result_unknown=True,
                ) from error
            finally:
                writer.close()
                await manager.__aexit__(None, None, None)

        return PeerTransportStream(int(head["status"]), {"content-type": head["contentType"]}, body())

    async def post(self, *, path: str, grant: str, payload: bytes,
                   max_response_bytes: int) -> PeerTransportResponse:
        response = await self.post_stream(
            path=path, grant=grant, payload=payload, max_response_bytes=max_response_bytes,
        )
        content = bytearray()
        async for chunk in response.body:
            content.extend(chunk)
        return PeerTransportResponse(response.status_code, response.headers, bytes(content))
