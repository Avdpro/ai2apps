"""Transparent Direct-first transport selection with fail-safe Relay fallback."""

from __future__ import annotations

from .base import PeerRequestTransport, PeerStreamingTransport, PeerTransportError


class DirectThenRelayTransport:
    def __init__(self, direct: PeerRequestTransport | PeerStreamingTransport, relay) -> None:
        self.direct = direct
        self.relay = relay

    async def post(self, **kwargs):
        try:
            return await self.direct.post(**kwargs)
        except PeerTransportError as error:
            if not error.retryable or error.result_unknown:
                raise
            return await self.relay.post(**kwargs)

    async def post_stream(self, **kwargs):
        try:
            return await self.direct.post_stream(**kwargs)
        except PeerTransportError as error:
            if not error.retryable or error.result_unknown:
                raise
            return await self.relay.post_stream(**kwargs)
