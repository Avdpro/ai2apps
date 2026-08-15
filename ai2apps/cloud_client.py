"""Native AI2Apps Cloud client with a private, persistent session cookie."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import httpx

from ai2apps.secrets import SecretBackend

DEFAULT_AI2APPS_CLOUD_BASE_URL = "https://coder.ai2apps.com"
AI2APPS_SESSION_COOKIE = "ai2apps_session"


def resolve_cloud_base_url(value: str | None = None) -> str:
    """Return the configured Cloud origin, rejecting paths and unsafe schemes."""

    candidate = (
        value
        if value is not None
        else os.environ.get("AI2APPS_CLOUD_BASE_URL", DEFAULT_AI2APPS_CLOUD_BASE_URL)
    ).strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("AI2Apps Cloud base URL must be an HTTP(S) origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("AI2Apps Cloud base URL must not contain credentials or metadata")
    if parsed.path.rstrip("/"):
        raise ValueError("AI2Apps Cloud base URL must not contain a path")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Remote AI2Apps Cloud origins must use HTTPS")
    return f"{parsed.scheme}://{parsed.netloc}"


class CloudSessionStore:
    """Persist only the opaque Cloud session value in the platform SecretBackend."""

    def __init__(self, backend: SecretBackend, base_url: str) -> None:
        self.backend = backend
        origin = resolve_cloud_base_url(base_url)
        origin_id = hashlib.sha256(origin.encode("utf-8")).hexdigest()[:16]
        self.key = f"ai2apps-cloud-session-{origin_id}"

    def load(self) -> str | None:
        try:
            value = self.backend.load(self.key)
        except KeyError:
            return None
        return value or None

    def save(self, value: str) -> None:
        self.backend.store(self.key, value)

    def clear(self) -> None:
        self.backend.delete(self.key)


class AI2AppsCloudClient:
    """Call the versioned Cloud API without exposing its Cookie to UI code."""

    def __init__(
        self,
        *,
        session_store: CloudSessionStore,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.base_url = resolve_cloud_base_url(base_url)
        self.session_store = session_store
        self.transport = transport
        self.timeout = timeout or httpx.Timeout(
            connect=15.0, read=3600.0, write=120.0, pool=30.0
        )
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            cookies = httpx.Cookies()
            session = self.session_store.load()
            if session:
                parsed = urlparse(self.base_url)
                cookies.set(
                    AI2APPS_SESSION_COOKIE,
                    session,
                    domain=parsed.hostname,
                    path="/",
                )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                cookies=cookies,
                follow_redirects=False,
                timeout=self.timeout,
                transport=self.transport,
                headers={"Accept": "application/json"},
            )
        return self._client

    def _persist_response_session(self, response: httpx.Response) -> None:
        try:
            value = response.cookies.get(AI2APPS_SESSION_COOKIE)
        except httpx.CookieConflict:
            value = None
        if not value and self._client is not None:
            try:
                value = self._client.cookies.get(AI2APPS_SESSION_COOKIE)
            except httpx.CookieConflict:
                value = None
        if value:
            self.session_store.save(value)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        content: bytes | str | None = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        if not path.startswith("/v1/"):
            raise ValueError("Cloud API requests must use a /v1/ path")
        client = self._get_client()
        request = client.build_request(
            method,
            path,
            json=json,
            content=content,
            data=data,
            files=files,
            params=params,
            headers=headers,
        )
        response = await client.send(request, stream=stream)
        self._persist_response_session(response)
        return response

    async def clear_session(self) -> None:
        self.session_store.clear()
        if self._client is not None:
            self._client.cookies.delete(AI2APPS_SESSION_COOKIE)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
