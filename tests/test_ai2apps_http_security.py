"""Exact-origin checks for browser writes authenticated by Local cookies."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from ai2apps.http_security import (
    LocalBrowserSecurityHeadersMiddleware,
    enforce_same_origin_cookie_request,
    has_browser_auth_cookie,
    has_local_session_cookie,
)


def _request(
    method: str,
    *,
    origin: str | None = None,
    fetch_site: str | None = None,
    cookie: str | None = None,
) -> Request:
    headers = [(b"host", b"127.0.0.1:8000")]
    if origin is not None:
        headers.append((b"origin", origin.encode("ascii")))
    if fetch_site is not None:
        headers.append((b"sec-fetch-site", fetch_site.encode("ascii")))
    if cookie is not None:
        headers.append((b"cookie", cookie.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/v1/platform/secrets",
            "raw_path": b"/v1/platform/secrets",
            "query_string": b"",
            "headers": headers,
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 50000),
        }
    )


def test_exact_origin_cookie_write_is_allowed():
    enforce_same_origin_cookie_request(
        _request("POST", origin="http://127.0.0.1:8000")
    )


@pytest.mark.parametrize(
    "origin",
    (
        "http://127.0.0.1:9000",
        "https://127.0.0.1:8000",
        "http://evil.example",
        "null",
        "http://127.0.0.1:8000/path",
    ),
)
def test_cross_origin_cookie_write_is_rejected(origin):
    with pytest.raises(HTTPException) as error:
        enforce_same_origin_cookie_request(_request("POST", origin=origin))

    assert error.value.status_code == 403
    assert error.value.detail["code"] == "csrf_origin_mismatch"


def test_safe_read_does_not_require_origin():
    enforce_same_origin_cookie_request(
        _request("GET", origin="http://127.0.0.1:9000")
    )


def test_non_browser_write_without_origin_remains_supported():
    enforce_same_origin_cookie_request(_request("POST"))


def test_cross_site_fetch_without_origin_is_rejected():
    with pytest.raises(HTTPException) as error:
        enforce_same_origin_cookie_request(
            _request("POST", fetch_site="cross-site")
        )

    assert error.value.detail["code"] == "csrf_origin_mismatch"


def test_scoped_and_migration_cookie_names_are_detected():
    assert has_local_session_cookie(
        _request("POST", cookie="ai2apps_local_session_deadbeef=token")
    )
    assert has_local_session_cookie(
        _request("POST", cookie="ai2apps_local_session=token")
    )
    assert not has_local_session_cookie(
        _request("POST", cookie="unrelated=value")
    )
    assert has_browser_auth_cookie(
        _request("POST", cookie="ai2apps_cloud_browser_deadbeef=token")
    )


def test_html_security_headers_are_added_without_overriding_route_csp():
    app = FastAPI()
    app.add_middleware(LocalBrowserSecurityHeadersMiddleware)

    @app.get("/default")
    def default_html():
        return HTMLResponse("<h1>AI2Apps</h1>")

    @app.get("/sandbox")
    def sandbox_html():
        return HTMLResponse(
            "<h1>Sandbox</h1>",
            headers={"Content-Security-Policy": "default-src 'none'"},
        )

    @app.get("/")
    def shell_html():
        return HTMLResponse("<h1>Shell</h1>")

    @app.get("/apps/ai2apps.general-chat")
    def chat_shell_html():
        return HTMLResponse("<h1>Chat Shell</h1>")

    @app.get("/admin/chat")
    def chat_html():
        return HTMLResponse("<h1>Chat</h1>")

    client = TestClient(app)
    response = client.get("/default")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "script-src 'self' 'unsafe-inline' 'unsafe-eval'" in response.headers[
        "content-security-policy"
    ]
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "microphone=()" in response.headers["permissions-policy"]
    assert "microphone=(self)" in client.get("/").headers["permissions-policy"]
    assert "microphone=(self)" in client.get(
        "/apps/ai2apps.general-chat"
    ).headers["permissions-policy"]
    assert "microphone=(self)" in client.get(
        "/admin/chat"
    ).headers["permissions-policy"]
    assert client.get("/sandbox").headers["content-security-policy"] == "default-src 'none'"
