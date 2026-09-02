"""Protocol-transparent WebDriver BiDi gateway for the visible AceFox Shell."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import WebSocket, WebSocketDisconnect

from ai2apps.apps.access import APP_CHAT_USE, has_app_capability
from ai2apps.identity import RequestPrincipal

_TOKEN = re.compile(r"^[0-9a-f]{64}$")
_MAX_DESCRIPTOR_BYTES = 4096
_MAX_BIDI_MESSAGE_BYTES = 8 * 1024 * 1024
_TICKET = re.compile(r"^[A-Za-z0-9_-]{43}$")
_TICKET_TTL_SECONDS = 30.0
_ticket_lock = threading.Lock()
_tickets: dict[str, tuple[float, RequestPrincipal]] = {}


class ShellBiDiGatewayError(RuntimeError):
    """The visible Shell's private BiDi endpoint is unavailable or unsafe."""


def issue_shell_bidi_ticket(principal: RequestPrincipal) -> str:
    """Create a short-lived, one-use ticket without disclosing BiDi secrets."""

    if not has_app_capability(principal, APP_CHAT_USE):
        raise ShellBiDiGatewayError("Current account cannot use browser Chat")
    now = time.monotonic()
    token = secrets.token_urlsafe(32)
    with _ticket_lock:
        expired = [key for key, (deadline, _) in _tickets.items() if deadline <= now]
        for key in expired:
            _tickets.pop(key, None)
        _tickets[token] = (now + _TICKET_TTL_SECONDS, principal)
    return token


def consume_shell_bidi_ticket(token: str) -> RequestPrincipal | None:
    """Consume a valid ticket exactly once."""

    if not _TICKET.fullmatch(token):
        return None
    with _ticket_lock:
        item = _tickets.pop(token, None)
    if item is None or item[0] <= time.monotonic():
        return None
    return item[1]


@dataclass(frozen=True, slots=True)
class ShellBiDiEndpoint:
    host: str
    port: int
    token: str
    pid: int

    @property
    def web_socket_url(self) -> str:
        return f"ws://{self.host}:{self.port}/session"

    @property
    def authorization(self) -> str:
        return f"Bearer {self.token}"

    def attached_web_socket_url(self, session_id: str) -> str:
        if not re.fullmatch(r"[0-9a-f-]{16,64}", session_id, re.IGNORECASE):
            raise ShellBiDiGatewayError("AceFox Shell returned an invalid BiDi session")
        return f"ws://{self.host}:{self.port}/session/{session_id}"

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> ShellBiDiEndpoint:
        descriptor_path = Path(path).expanduser().resolve()
        try:
            raw = descriptor_path.read_bytes()
        except OSError as exc:
            raise ShellBiDiGatewayError(
                "AceFox Shell automation endpoint is unavailable"
            ) from exc
        if len(raw) > _MAX_DESCRIPTOR_BYTES:
            raise ShellBiDiGatewayError(
                "AceFox Shell automation descriptor is too large"
            )
        try:
            payload: Any = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ShellBiDiGatewayError(
                "AceFox Shell automation descriptor is invalid"
            ) from exc
        if not isinstance(payload, dict):
            raise ShellBiDiGatewayError("AceFox Shell automation descriptor is invalid")
        host = payload.get("host")
        port = payload.get("port")
        token = payload.get("token")
        pid = payload.get("pid")
        if (
            payload.get("schema_version") != 1
            or host != "127.0.0.1"
            or not isinstance(port, int)
            or isinstance(port, bool)
            or not 1024 <= port <= 65535
            or not isinstance(token, str)
            or not _TOKEN.fullmatch(token)
            or not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 1
        ):
            raise ShellBiDiGatewayError("AceFox Shell automation descriptor is unsafe")
        try:
            os.kill(pid, 0)
        except OSError as exc:
            raise ShellBiDiGatewayError("AceFox Shell browser is not running") from exc
        return cls(host=host, port=port, token=token, pid=pid)


def shell_bidi_descriptor_path() -> str:
    configured = os.environ.get("AI2APPS_SHELL_AUTOMATION_PATH", "")
    if not configured or not os.path.isabs(configured):
        raise ShellBiDiGatewayError("AI2APPS_SHELL_AUTOMATION_PATH is unavailable")
    return configured


def websocket_is_same_origin(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")
    if not origin or not host:
        return False
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.netloc.lower() == host.lower()
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


async def _bootstrap_command(
    upstream: Any, command_id: int, method: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Run one native lifecycle command while creating the shared Session."""

    await upstream.send(
        json.dumps(
            {"id": command_id, "method": method, "params": params},
            separators=(",", ":"),
        )
    )
    async with asyncio.timeout(10):
        while True:
            payload = await upstream.recv()
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            try:
                response = json.loads(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                continue
            if not isinstance(response, dict) or response.get("id") != command_id:
                continue
            if response.get("type") == "error" or response.get("error"):
                message = response.get("message") or response.get("error")
                raise ShellBiDiGatewayError(f"AceFox BiDi {method} failed: {message}")
            result = response.get("result", {})
            if not isinstance(result, dict):
                raise ShellBiDiGatewayError(
                    f"AceFox BiDi {method} returned an invalid result"
                )
            return result


@dataclass(frozen=True, slots=True)
class SharedShellBiDiSession:
    endpoint: ShellBiDiEndpoint
    session_id: str
    capabilities: dict[str, Any]

    @property
    def web_socket_url(self) -> str:
        return self.endpoint.attached_web_socket_url(self.session_id)

    @property
    def new_session_result(self) -> dict[str, Any]:
        # The attach URL points at AceFox's protected loopback listener.  The
        # client is already attached through the Gateway and must never learn
        # that raw endpoint, even though it cannot use it without the bearer.
        capabilities = dict(self.capabilities)
        capabilities.pop("webSocketUrl", None)
        return {"sessionId": self.session_id, "capabilities": capabilities}


class ShellBiDiSessionBroker:
    """Own one native Session and let many Gateway clients attach to it."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._session: SharedShellBiDiSession | None = None

    @staticmethod
    def _state_path() -> Path | None:
        try:
            return Path(shell_bidi_descriptor_path()).with_name(
                "shell-bidi-session.json"
            )
        except ShellBiDiGatewayError:
            return None

    @staticmethod
    def _endpoint_digest(endpoint: ShellBiDiEndpoint) -> str:
        material = f"{endpoint.pid}:{endpoint.port}:{endpoint.token}".encode("ascii")
        return hashlib.sha256(material).hexdigest()

    def _load_persisted(
        self, endpoint: ShellBiDiEndpoint
    ) -> SharedShellBiDiSession | None:
        state_path = self._state_path()
        if state_path is None:
            return None
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("endpoint_digest") != self._endpoint_digest(endpoint)
            or not isinstance(payload.get("session_id"), str)
            or not isinstance(payload.get("capabilities"), dict)
        ):
            return None
        session = SharedShellBiDiSession(
            endpoint=endpoint,
            session_id=payload["session_id"],
            capabilities=payload["capabilities"],
        )
        try:
            _ = session.web_socket_url
        except ShellBiDiGatewayError:
            return None
        return session

    def _persist(self, session: SharedShellBiDiSession) -> None:
        state_path = self._state_path()
        if state_path is None:
            return
        temporary = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
        payload = {
            "schema_version": 1,
            "endpoint_digest": self._endpoint_digest(session.endpoint),
            "session_id": session.session_id,
            "capabilities": session.capabilities,
        }
        try:
            temporary.write_text(
                json.dumps(payload, separators=(",", ":")), encoding="utf-8"
            )
            os.chmod(temporary, 0o600)
            os.replace(temporary, state_path)
        except OSError:
            with suppress(OSError):
                temporary.unlink()

    def _discard_persisted(self, session: SharedShellBiDiSession) -> None:
        state_path = self._state_path()
        if state_path is None:
            return
        persisted = self._load_persisted(session.endpoint)
        if persisted is not None and persisted.session_id == session.session_id:
            with suppress(OSError):
                state_path.unlink()

    async def ensure(
        self, endpoint: ShellBiDiEndpoint, connector: Any
    ) -> SharedShellBiDiSession:
        async with self._lock:
            if self._session is not None and self._session.endpoint == endpoint:
                return self._session
            persisted = self._load_persisted(endpoint)
            if persisted is not None:
                self._session = persisted
                return persisted
            try:
                async with connector(
                    endpoint.web_socket_url,
                    additional_headers={"Authorization": endpoint.authorization},
                    open_timeout=5,
                    close_timeout=2,
                    max_size=_MAX_BIDI_MESSAGE_BYTES,
                    proxy=None,
                ) as upstream:
                    status = await _bootstrap_command(upstream, 1, "session.status", {})
                    if status.get("ready") is not True:
                        raise ShellBiDiGatewayError(
                            "AceFox already has a BiDi Session not owned by this Gateway"
                        )
                    result = await _bootstrap_command(
                        upstream,
                        2,
                        "session.new",
                        {"capabilities": {"alwaysMatch": {"webSocketUrl": True}}},
                    )
            except ShellBiDiGatewayError:
                raise
            except Exception as exc:
                raise ShellBiDiGatewayError(
                    "AceFox Shell BiDi Session could not be created"
                ) from exc
            session_id = result.get("sessionId")
            capabilities = result.get("capabilities")
            if not isinstance(session_id, str) or not isinstance(capabilities, dict):
                raise ShellBiDiGatewayError("AceFox returned an invalid BiDi Session")
            capabilities = dict(capabilities)
            capabilities.pop("webSocketUrl", None)
            session = SharedShellBiDiSession(endpoint, session_id, capabilities)
            # Validate the attach URL before publishing the Session to clients.
            _ = session.web_socket_url
            self._session = session
            self._persist(session)
            return session

    async def invalidate(self, session: SharedShellBiDiSession) -> None:
        async with self._lock:
            if self._session == session:
                self._session = None
                self._discard_persisted(session)


_shell_session_broker = ShellBiDiSessionBroker()


def _success_response(command_id: Any, result: dict[str, Any]) -> str:
    return json.dumps(
        {"type": "success", "id": command_id, "result": result},
        separators=(",", ":"),
    )


async def serve_shell_bidi_gateway(websocket: WebSocket, _runtime: Any) -> None:
    """Attach a client to the Shell-owned Session and relay native BiDi."""

    ticket = websocket.query_params.get("ticket", "")
    principal = consume_shell_bidi_ticket(ticket)
    if principal is None or not has_app_capability(principal, APP_CHAT_USE):
        await websocket.close(code=4401, reason="Valid browser ticket required")
        return
    if not websocket_is_same_origin(websocket):
        await websocket.close(code=4403, reason="WebSocket origin denied")
        return
    try:
        endpoint = ShellBiDiEndpoint.load(shell_bidi_descriptor_path())
    except ShellBiDiGatewayError:
        await websocket.close(code=1013, reason="AceFox Shell BiDi unavailable")
        return

    try:
        from websockets.asyncio.client import connect
    except ImportError:
        await websocket.close(code=1013, reason="BiDi gateway dependency unavailable")
        return

    # Complete the authenticated downstream handshake before bootstrapping the
    # native Session.  Session creation can legitimately take longer than an
    # HTTP upgrade, and failures should arrive as WebSocket close reasons
    # instead of an opaque HTTP 403.
    await websocket.accept()
    try:
        shared_session = await _shell_session_broker.ensure(endpoint, connect)
        async with connect(
            shared_session.web_socket_url,
            additional_headers={"Authorization": endpoint.authorization},
            open_timeout=5,
            close_timeout=2,
            max_size=_MAX_BIDI_MESSAGE_BYTES,
            proxy=None,
        ) as upstream:
            downstream_send_lock = asyncio.Lock()

            async def send_downstream(payload: str | bytes) -> None:
                async with downstream_send_lock:
                    if isinstance(payload, str):
                        await websocket.send_text(payload)
                    else:
                        await websocket.send_bytes(payload)

            async def client_to_shell() -> None:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        raise WebSocketDisconnect(message.get("code", 1000))
                    text = message.get("text")
                    binary = message.get("bytes")
                    payload = text if text is not None else binary
                    if payload is None:
                        continue
                    size = (
                        len(payload.encode("utf-8"))
                        if isinstance(payload, str)
                        else len(payload)
                    )
                    if size > _MAX_BIDI_MESSAGE_BYTES:
                        await websocket.close(
                            code=1009, reason="BiDi message too large"
                        )
                        return
                    try:
                        decoded = json.loads(payload)
                    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                        decoded = None
                    if isinstance(decoded, dict):
                        method = decoded.get("method")
                        command_id = decoded.get("id")
                        # Firefox exposes one process-wide Session.  Present its
                        # lifecycle independently to every downstream client,
                        # while all non-lifecycle messages remain native BiDi.
                        if method == "session.status":
                            await send_downstream(
                                _success_response(
                                    command_id, {"ready": True, "message": ""}
                                )
                            )
                            continue
                        if method == "session.new":
                            await send_downstream(
                                _success_response(
                                    command_id, shared_session.new_session_result
                                )
                            )
                            continue
                        if method == "session.end":
                            await send_downstream(_success_response(command_id, {}))
                            return
                    await upstream.send(payload)

            async def shell_to_client() -> None:
                async for payload in upstream:
                    await send_downstream(payload)

            sender = asyncio.create_task(client_to_shell())
            receiver = asyncio.create_task(shell_to_client())
            relay_tasks = {sender, receiver}
            try:
                done, _ = await asyncio.wait(
                    relay_tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    task.result()
            finally:
                pending = {task for task in relay_tasks if not task.done()}
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
    except ShellBiDiGatewayError:
        with suppress(RuntimeError):
            await websocket.close(code=1013, reason="AceFox Shell BiDi unavailable")
    except Exception:
        # A downstream Sidebar or its attached upstream socket can disappear
        # independently.  The native process-wide Session remains valid and
        # must stay discoverable for the other Profile windows.
        with suppress(RuntimeError):
            await websocket.close(code=1011, reason="AceFox Shell BiDi disconnected")
