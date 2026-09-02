"""In-process handoff between authenticated Apps and the desktop Shell."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def managed_browser_profile_key(actor_user_id: str) -> str:
    return hashlib.sha256(
        f"ai2apps-managed-browser-v1\0{actor_user_id}".encode()
    ).hexdigest()


@dataclass(slots=True)
class _Request:
    id: str
    url: str
    actor_user_id: str
    profile_key: str
    created_at: float
    complete: Callable[[dict[str, Any]], str]
    state: str = "pending"
    item_id: str | None = None
    error: str | None = None


class ManagedBrowserBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[str, _Request] = {}

    def enqueue(
        self,
        *,
        url: str,
        actor_user_id: str,
        complete: Callable[[dict[str, Any]], str],
    ) -> str:
        request_id = secrets.token_hex(16)
        profile_key = managed_browser_profile_key(actor_user_id)
        with self._lock:
            self._prune()
            self._requests[request_id] = _Request(
                id=request_id,
                url=url,
                actor_user_id=actor_user_id,
                profile_key=profile_key,
                created_at=time.monotonic(),
                complete=complete,
            )
        return request_id

    def claim_next(self) -> dict[str, str] | None:
        with self._lock:
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
                "url": request.url,
                "profile_key": request.profile_key,
            }

    def finish(self, request_id: str, article: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            request = self._requests.get(request_id)
            if request is None or request.state not in {"pending", "claimed"}:
                raise ValueError("managed browser request is not active")
            request.state = "finishing"
        try:
            item_id = request.complete(article)
        except Exception as error:
            with self._lock:
                request.state = "failed"
                request.error = str(error)
            raise
        with self._lock:
            request.state = "complete"
            request.item_id = item_id
            return self._status(request)

    def status(self, request_id: str, actor_user_id: str) -> dict[str, Any]:
        with self._lock:
            self._prune()
            request = self._requests.get(request_id)
            if request is None or request.actor_user_id != actor_user_id:
                raise KeyError(request_id)
            return self._status(request)

    def fail(self, request_id: str, message: str) -> None:
        with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                return
            request.state = "failed"
            request.error = message[:500]

    def _prune(self) -> None:
        cutoff = time.monotonic() - 15 * 60
        expired = [
            request_id
            for request_id, request in self._requests.items()
            if request.created_at < cutoff
        ]
        for request_id in expired:
            del self._requests[request_id]

    @staticmethod
    def _status(request: _Request) -> dict[str, Any]:
        return {
            "request_id": request.id,
            "state": request.state,
            "item_id": request.item_id,
            "error": request.error,
        }


managed_browser_broker = ManagedBrowserBroker()
