"""Dedicated Core-controlled LAN listener for narrow or full Local access."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from contextlib import contextmanager, suppress

import uvicorn

from .models import LocalNetworkAccess


def discover_lan_host(request_host: str, bind_host: str) -> str:
    """Prefer the request host, otherwise derive a non-loopback LAN address."""
    try:
        if not ipaddress.ip_address(request_host).is_loopback:
            return request_host
    except ValueError:
        if request_host not in {"localhost", ""}:
            return request_host
    family = socket.AF_INET6 if bind_host == "::" else socket.AF_INET
    probe = socket.socket(family, socket.SOCK_DGRAM)
    try:
        probe.connect(("2001:4860:4860::8888", 80) if family == socket.AF_INET6 else ("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return request_host
    finally:
        probe.close()


class LanAccessApp:
    def __init__(self, app, settings_provider) -> None:
        self.app = app
        self.settings_provider = settings_provider

    async def __call__(self, scope, receive, send) -> None:
        settings = self.settings_provider()
        path = scope.get("path", "")
        allowed = settings.mode == "full" or (
            settings.mode == "share_only" and path.startswith("/v1/share/")
        )
        if allowed:
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = b'{"detail":{"code":"lan_access_disabled"}}'
        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class _NestedServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        yield


class LanAccessController:
    def __init__(self, app, settings_provider) -> None:
        self.asgi = LanAccessApp(app, settings_provider)
        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None
        self._socket: socket.socket | None = None
        self._address: tuple[str, int] | None = None
        self._lock = asyncio.Lock()

    async def apply(self, settings: LocalNetworkAccess) -> None:
        async with self._lock:
            if settings.mode == "disabled":
                await self._stop_locked()
                return
            address = (settings.bind_host, settings.port)
            if self._task is not None and not self._task.done() and self._address == address:
                return
            await self._stop_locked()
            family = socket.AF_INET6 if settings.bind_host == "::" else socket.AF_INET
            listener = socket.socket(family, socket.SOCK_STREAM)
            try:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(address)
                listener.listen(128)
                listener.setblocking(False)
            except Exception:
                listener.close()
                raise
            config = uvicorn.Config(
                self.asgi,
                host=settings.bind_host,
                port=settings.port,
                lifespan="off",
                access_log=False,
                log_level="warning",
                proxy_headers=False,
            )
            self._server = _NestedServer(config)
            self._socket = listener
            self._address = address
            self._task = asyncio.create_task(
                self._server.serve(sockets=[listener]), name="ai2apps-lan-access"
            )
            await asyncio.sleep(0)
            if self._task.done():
                error = self._task.exception()
                await self._stop_locked()
                raise RuntimeError(f"LAN listener failed to start: {error}")

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            with suppress(asyncio.CancelledError):
                await self._task
        if self._socket is not None:
            with suppress(OSError):
                self._socket.close()
        self._server = None
        self._task = None
        self._socket = None
        self._address = None
