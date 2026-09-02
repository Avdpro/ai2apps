"""Strict HTTPS/SSE Relay adapter for a Cloud-authorized Peer origin."""

from __future__ import annotations

from collections.abc import AsyncIterator
import re
from urllib.parse import urlparse

import httpx

from .base import PeerTransportError, PeerTransportResponse, PeerTransportStream

_MODEL_SHARE_PATH = "/v1/model-share/peer/v1/inference"
_MESSAGER_PATHS = frozenset({
    "/v1/messager/peer/v2/handshakes",
    "/v1/messager/peer/v2/messages",
})
_RELAY_HOST = re.compile(r"^device-[0-9a-f]{32}\.[a-z0-9.-]+$")


class RelayHttpsTransport:
    """Pilot-only adapter; the caller must obtain an authorized relay origin."""

    def __init__(self, origin: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        parsed = urlparse(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or _RELAY_HOST.fullmatch(parsed.hostname) is None
            or parsed.username
            or parsed.password
            or parsed.port is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Peer Relay origin must be a bare HTTPS origin")
        self.origin = origin.rstrip("/")
        self.transport = transport

    async def post_stream(
        self, *, path: str, grant: str, payload: bytes, max_response_bytes: int
    ) -> PeerTransportStream:
        if path != _MODEL_SHARE_PATH:
            raise PeerTransportError("PEER_RELAY_PATH_FORBIDDEN", "Relay path is not allowed.")
        if not 1 <= len(grant) <= 8192:
            raise PeerTransportError("PEER_GRANT_INVALID", "Peer Grant is invalid.")
        client = httpx.AsyncClient(
            base_url=self.origin,
            transport=self.transport,
            timeout=httpx.Timeout(connect=5, read=3600, write=30, pool=5),
            follow_redirects=False,
            headers={"Accept": "text/event-stream"},
        )
        request = client.build_request(
            "POST", path, content=payload,
            headers={"Authorization": f"Bearer {grant}", "Content-Type": "application/json"},
        )
        try:
            response = await client.send(request, stream=True)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            await client.aclose()
            raise PeerTransportError("PEER_RELAY_UNAVAILABLE", "Peer Relay is unavailable.", retryable=True) from error
        if response.status_code != 200:
            status = response.status_code
            await response.aclose()
            await client.aclose()
            raise PeerTransportError(
                "PEER_RELAY_REJECTED", "Peer Relay rejected the request.",
                retryable=status in {401, 403, 409, 429, 503},
                result_unknown=status >= 500,
            )

        async def bounded_body() -> AsyncIterator[bytes]:
            count = 0
            try:
                async for chunk in response.aiter_bytes():
                    count += len(chunk)
                    if count > max_response_bytes:
                        raise PeerTransportError("PEER_RESPONSE_LIMIT_EXCEEDED", "Peer response exceeded the Session byte limit.")
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return PeerTransportStream(response.status_code, dict(response.headers), bounded_body())

    async def post(
        self, *, path: str, grant: str, payload: bytes, max_response_bytes: int
    ) -> PeerTransportResponse:
        if path not in _MESSAGER_PATHS:
            raise PeerTransportError("PEER_RELAY_PATH_FORBIDDEN", "Relay path is not allowed.")
        if not 1 <= len(grant) <= 8192:
            raise PeerTransportError("PEER_GRANT_INVALID", "Peer Grant is invalid.")
        try:
            async with httpx.AsyncClient(
                base_url=self.origin, transport=self.transport,
                timeout=httpx.Timeout(connect=5, read=30, write=30, pool=5),
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    path, content=payload,
                    headers={"Authorization": f"Bearer {grant}", "Content-Type": "application/json",
                             "Accept": "application/json"},
                )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise PeerTransportError("PEER_RELAY_UNAVAILABLE", "Peer Relay is unavailable.", retryable=True) from error
        if response.status_code not in {200, 201}:
            raise PeerTransportError(
                "PEER_RELAY_REJECTED", "Peer Relay rejected the request.",
                retryable=response.status_code in {401, 403, 409, 429, 503},
                result_unknown=response.status_code >= 500,
            )
        if len(response.content) > max_response_bytes:
            raise PeerTransportError("PEER_RESPONSE_LIMIT_EXCEEDED", "Peer response exceeded the Session byte limit.")
        return PeerTransportResponse(response.status_code, dict(response.headers), response.content)
