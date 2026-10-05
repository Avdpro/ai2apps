"""Recovery preserves instance binding and never retries an executed command."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from ai2apps.browser import shell_bidi_gateway as gateway
from ai2apps.identity import RequestPrincipal


@pytest.mark.asyncio
async def test_gateway_rereads_repaired_descriptor(monkeypatch):
    endpoint = gateway.ShellBiDiEndpoint("127.0.0.1", 49152, "a" * 64, 42)
    reads = []

    def load(path):
        reads.append(path)
        if len(reads) < 3:
            raise gateway.ShellBiDiGatewayError("dead record")
        return endpoint

    monkeypatch.setattr(
        gateway,
        "shell_bidi_descriptor_path",
        lambda: "/one/instance/run/shell-automation.json",
    )
    monkeypatch.setattr(gateway.ShellBiDiEndpoint, "load", load)

    @asynccontextmanager
    async def attach(actual, connector):
        assert actual == endpoint

        class Upstream:
            async def __aiter__(self):
                if False:
                    yield ""

        yield SimpleNamespace(), Upstream()

    monkeypatch.setattr(gateway, "attach_shell_bidi_session", attach)

    # Stop after successful record recovery; relay needs no actual browser here.
    class Client:
        query_params = {
            "ticket": gateway.issue_shell_bidi_ticket(RequestPrincipal.legacy_local())
        }
        headers = {"origin": "http://127.0.0.1:1234", "host": "127.0.0.1:1234"}
        accepted = False

        async def accept(self):
            self.accepted = True

        async def close(self, **kwargs):
            pass

        async def receive(self):
            return {"type": "websocket.disconnect", "code": 1000}

    client = Client()
    await gateway.serve_shell_bidi_gateway(client, object())
    assert client.accepted
    assert reads == ["/one/instance/run/shell-automation.json"] * 3


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [(404, 2), (401, 1), (503, 1)])
async def test_only_expired_attach_session_is_recreated(monkeypatch, status, expected):
    endpoint = gateway.ShellBiDiEndpoint("127.0.0.1", 49152, "a" * 64, 42)
    calls = []
    invalidated = []

    class Broker:
        async def ensure(self, actual, connector):
            assert actual == endpoint
            return SimpleNamespace(
                web_socket_url=f"ws://127.0.0.1:49152/session/{len(calls)}"
            )

        async def invalidate(self, session):
            invalidated.append(session)

    monkeypatch.setattr(gateway, "_shell_session_broker", Broker())

    @asynccontextmanager
    async def connector(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise InvalidStatus(Response(status, "Failure", Headers()))
        yield object()

    if status == 404:
        async with gateway.attach_shell_bidi_session(endpoint, connector):
            pass
    else:
        with pytest.raises(InvalidStatus):
            async with gateway.attach_shell_bidi_session(endpoint, connector):
                pass
    assert len(calls) == expected
    assert len(invalidated) == (1 if status == 404 else 0)


@pytest.mark.asyncio
async def test_client_action_failure_is_never_replayed(monkeypatch):
    endpoint = gateway.ShellBiDiEndpoint("127.0.0.1", 49152, "a" * 64, 42)

    class Broker:
        async def ensure(self, *args):
            return SimpleNamespace(web_socket_url="ws://127.0.0.1:49152/session/id")

        async def invalidate(self, session):
            pytest.fail("must not invalidate after attach")

    monkeypatch.setattr(gateway, "_shell_session_broker", Broker())
    calls = []

    @asynccontextmanager
    async def connector(*args, **kwargs):
        calls.append(1)
        yield object()

    with pytest.raises(InvalidStatus):
        async with gateway.attach_shell_bidi_session(endpoint, connector):
            raise InvalidStatus(Response(404, "Action failed", Headers()))
    assert len(calls) == 1
