"""Authenticated lifecycle handoff for native AppShell browser windows."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

ShellBrowserAction = Literal["open", "delete"]


def shell_browser_profile_key(actor_user_id: str, profile_key: str) -> str:
    """Return the stable, user-scoped container key consumed by AppShell."""

    if profile_key == "default":
        # Keep the existing menu Profile and its cookies/session intact.
        material = f"ai2apps-managed-browser-v1\0{actor_user_id}"
    else:
        material = f"ai2apps-managed-browser-profile-v2\0{actor_user_id}\0{profile_key}"
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass(slots=True)
class _ShellBrowserRequest:
    id: str
    action: ShellBrowserAction
    profile_key: str
    profile_name: str
    is_default: bool
    initial_url: str | None
    created_at: float
    state: str = "pending"
    result: dict[str, Any] | None = None
    error: str | None = None


class ShellBrowserWindowBroker:
    """Pass window lifecycle requests to the already-running native Shell."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._requests: dict[str, _ShellBrowserRequest] = {}

    def enqueue(
        self,
        *,
        action: ShellBrowserAction,
        profile_key: str,
        profile_name: str,
        is_default: bool,
        initial_url: str | None = None,
    ) -> str:
        normalized_name = " ".join(profile_name.split())
        if not 1 <= len(normalized_name) <= 120:
            raise ValueError("Browser Profile name must contain 1 to 120 characters")
        request_id = secrets.token_hex(16)
        with self._condition:
            self._prune()
            self._requests[request_id] = _ShellBrowserRequest(
                id=request_id,
                action=action,
                profile_key=profile_key,
                profile_name=normalized_name,
                is_default=is_default,
                initial_url=initial_url,
                created_at=time.monotonic(),
            )
            self._condition.notify_all()
        return request_id

    def claim_next(self) -> dict[str, Any] | None:
        with self._condition:
            self._prune()
            request = next(
                (item for item in self._requests.values() if item.state == "pending"),
                None,
            )
            if request is None:
                return None
            request.state = "claimed"
            return {
                "request_id": request.id,
                "action": request.action,
                "profile_key": request.profile_key,
                "profile_name": request.profile_name,
                "is_default": request.is_default,
                "initial_url": request.initial_url,
            }

    def finish(
        self,
        request_id: str,
        *,
        status: str,
        pid: int,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self._condition:
            request = self._requests.get(request_id)
            if request is None or request.state not in {"pending", "claimed"}:
                raise ValueError("Shell browser request is not active")
            if status == "failed":
                request.state = "failed"
                request.error = (error or "AppShell could not complete the request")[:500]
            else:
                allowed = {"open": {"launched", "focused"}, "delete": {"deleted"}}
                if status not in allowed[request.action] or pid <= 1:
                    raise ValueError("Shell browser result is invalid")
                request.state = "complete"
                request.result = {"status": status, "pid": pid}
            self._condition.notify_all()
            return self._status(request)

    def wait(self, request_id: str, timeout: float = 10.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                request = self._requests.get(request_id)
                if request is None:
                    raise RuntimeError("Shell browser request expired")
                if request.state == "complete" and request.result is not None:
                    return dict(request.result)
                if request.state == "failed":
                    raise RuntimeError(request.error or "AppShell request failed")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    request.state = "failed"
                    request.error = "AppShell did not acknowledge the browser request"
                    raise TimeoutError(request.error)
                self._condition.wait(remaining)

    def _prune(self) -> None:
        cutoff = time.monotonic() - 15 * 60
        for request_id in [
            key for key, request in self._requests.items() if request.created_at < cutoff
        ]:
            del self._requests[request_id]

    @staticmethod
    def _status(request: _ShellBrowserRequest) -> dict[str, Any]:
        return {
            "request_id": request.id,
            "state": request.state,
            "result": request.result,
            "error": request.error,
        }


shell_browser_window_broker = ShellBrowserWindowBroker()
