"""Authenticated WebDriver BiDi transport for Helper-managed AceFox Agents."""

from __future__ import annotations

import json
import queue
import threading
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from ai2apps.browser.models import BrowserError


@dataclass(frozen=True, slots=True)
class AceFoxAgentEndpoint:
    web_socket_url: str
    authorization: str
    profile_id: str
    pid: int

    @classmethod
    def from_helper_result(cls, result: dict[str, Any]) -> AceFoxAgentEndpoint:
        automation = result["automation"]
        return cls(
            web_socket_url=str(automation["web_socket_url"]),
            authorization=str(automation["authorization"]),
            profile_id=str(result["profile_id"]),
            pid=int(result["pid"]),
        )


class AceFoxBiDiConnection:
    """One authenticated, multiplexed BiDi connection with bounded events."""

    def __init__(
        self,
        endpoint: AceFoxAgentEndpoint,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.events: deque[dict[str, Any]] = deque(maxlen=200)
        self._socket = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._next_id = 1
        self._responses: dict[int, queue.Queue[dict[str, Any]]] = {}
        self.session_id: str | None = None

    def connect(self) -> None:
        if self.connected:
            return
        try:
            import websocket
        except ImportError as exc:
            raise BrowserError(
                "browser_dependency_missing",
                "Install AI2Apps with the browser extra",
            ) from exc
        try:
            self._socket = websocket.create_connection(
                self.endpoint.web_socket_url,
                timeout=self.timeout_seconds,
                suppress_origin=True,
                header=[f"Authorization: {self.endpoint.authorization}"],
            )
            self._socket.settimeout(0.5)
            self._stop.clear()
            self._reader = threading.Thread(
                target=self._read_loop,
                name="ai2apps-acefox-bidi",
                daemon=True,
            )
            self._reader.start()
            status = self.command("session.status", {})
            if status.get("ready") is not True:
                raise BrowserError("bidi_unavailable", "AceFox BiDi is not ready")
            session = self.command(
                "session.new",
                {"capabilities": {"alwaysMatch": {"webSocketUrl": True}}},
            )
            self.session_id = str(session["sessionId"])
        except Exception:
            self.close(end_session=False)
            raise

    @property
    def connected(self) -> bool:
        return (
            self._socket is not None
            and self._reader is not None
            and self._reader.is_alive()
            and not self._stop.is_set()
        )

    def command(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if self._socket is None or self._stop.is_set():
            raise BrowserError("bidi_disconnected", "AceFox BiDi is disconnected")
        with self._state_lock:
            command_id = self._next_id
            self._next_id += 1
            response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._responses[command_id] = response_queue
        try:
            payload = json.dumps(
                {"id": command_id, "method": method, "params": params},
                separators=(",", ":"),
            )
            with self._write_lock:
                self._socket.send(payload)
            try:
                response = response_queue.get(
                    timeout=timeout_seconds or self.timeout_seconds
                )
            except queue.Empty as exc:
                raise BrowserError(
                    "bidi_timeout", f"AceFox BiDi command timed out: {method}"
                ) from exc
            if "error" in response:
                raise BrowserError(
                    "bidi_command_failed",
                    f"{method}: {response.get('error')} — {response.get('message', '')}",
                )
            result = response.get("result")
            if not isinstance(result, dict):
                raise BrowserError(
                    "bidi_invalid_response", f"AceFox returned no result for {method}"
                )
            return result
        finally:
            with self._state_lock:
                self._responses.pop(command_id, None)

    def close(self, *, end_session: bool = True) -> None:
        if end_session and self.session_id is not None and self.connected:
            with suppress(BrowserError):
                self.command("session.end", {}, timeout_seconds=2.0)
        self.session_id = None
        self._stop.set()
        socket = self._socket
        self._socket = None
        if socket is not None:
            with suppress(Exception):
                socket.close()
        reader = self._reader
        self._reader = None
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=2)
        with self._state_lock:
            pending = tuple(self._responses.values())
            self._responses.clear()
        for response_queue in pending:
            with suppress(queue.Full):
                response_queue.put_nowait(
                    {"error": "disconnected", "message": "AceFox BiDi disconnected"}
                )

    def _read_loop(self) -> None:
        while not self._stop.is_set() and self._socket is not None:
            try:
                message = json.loads(self._socket.recv())
            except Exception as exc:
                if type(exc).__name__ == "WebSocketTimeoutException":
                    continue
                break
            if not isinstance(message, dict):
                continue
            command_id = message.get("id")
            if isinstance(command_id, int):
                with self._state_lock:
                    response_queue = self._responses.get(command_id)
                if response_queue is not None:
                    with suppress(queue.Full):
                        response_queue.put_nowait(message)
                continue
            if isinstance(message.get("method"), str):
                self.events.append(message)
        self._stop.set()

    def __enter__(self) -> AceFoxBiDiConnection:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
