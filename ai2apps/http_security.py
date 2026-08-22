"""Browser request invariants for cookie-authenticated Local control planes."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
# The bundled Alpine build evaluates template expressions with Function().
# Keep unsafe-eval limited to first-party Local HTML; sandbox/package routes
# provide their own stricter CSP and are preserved by the middleware below.
_HTML_SECURITY_HEADERS = (
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        b"style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
        b"font-src 'self' data:; connect-src 'self' ws: wss:; "
        b"media-src 'self' blob:; worker-src 'self' blob:; frame-src 'self'; "
        b"object-src 'none'; base-uri 'self'; form-action 'self'; "
        b"frame-ancestors 'self'",
    ),
    (b"referrer-policy", b"no-referrer"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"SAMEORIGIN"),
)
_DEFAULT_PERMISSIONS_POLICY = (
    b"camera=(), microphone=(), geolocation=(), payment=(), usb=()"
)
_MICROPHONE_PERMISSIONS_POLICY = (
    b"camera=(), microphone=(self), geolocation=(), payment=(), usb=()"
)


def _html_permissions_policy(path: str) -> bytes:
    """Allow first-party Chat to request audio while denying other sensors.

    This policy only makes a browser permission request possible. Ordinary web
    browsers still ask the user; the dedicated AI2Apps Shell controls its own
    microphone default in its isolated Firefox profile.
    """

    if (
        path == "/"
        or path.startswith("/apps/")
        or path.rstrip("/") == "/admin/chat"
    ):
        return _MICROPHONE_PERMISSIONS_POLICY
    return _DEFAULT_PERMISSIONS_POLICY


class LocalBrowserSecurityHeadersMiddleware:
    """Attach a restrictive baseline to Local HTML without weakening route CSPs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", ()))
                content_type = next(
                    (
                        value.lower()
                        for name, value in headers
                        if name.lower() == b"content-type"
                    ),
                    b"",
                )
                if content_type.startswith(b"text/html"):
                    existing = {name.lower() for name, _ in headers}
                    headers.extend(
                        (name, value)
                        for name, value in _HTML_SECURITY_HEADERS
                        if name not in existing
                    )
                    if b"permissions-policy" not in existing:
                        headers.append(
                            (
                                b"permissions-policy",
                                _html_permissions_policy(scope.get("path", "")),
                            )
                        )
                    message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def enforce_same_origin_cookie_request(request: Request) -> None:
    """Reject cross-origin writes made with an ambient Local Session cookie.

    Cookies are not port-scoped. Two loopback instances on different ports are
    therefore same-site in browsers even though they are different origins.
    Browser writes must prove the exact scheme/host/port that received them.
    Requests without an Origin remain valid for non-browser Local clients.
    """

    method = getattr(request, "method", None)
    if not isinstance(method, str):
        return
    if method.upper() in _SAFE_METHODS:
        return
    fetch_site_value = request.headers.get("sec-fetch-site", "")
    origin_value = request.headers.get("origin", "")
    fetch_site = (
        fetch_site_value.strip().lower()
        if isinstance(fetch_site_value, str)
        else ""
    )
    origin = origin_value.strip() if isinstance(origin_value, str) else ""
    if not origin:
        if fetch_site == "cross-site":
            _raise_origin_mismatch()
        return
    try:
        parsed = urlsplit(origin)
    except ValueError:
        _raise_origin_mismatch()
    expected_scheme = request.url.scheme.lower()
    expected_netloc = request.url.netloc.lower()
    if (
        parsed.scheme.lower() != expected_scheme
        or parsed.netloc.lower() != expected_netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        _raise_origin_mismatch()


def has_local_session_cookie(request: Request) -> bool:
    """Return whether an instance-scoped or migration Local cookie is present."""

    return any(
        name == "ai2apps_local_session"
        or name.startswith("ai2apps_local_session_")
        for name in request.cookies
    )


def has_browser_auth_cookie(request: Request) -> bool:
    """Return whether a Local or Cloud-browser ambient credential is present."""

    return has_local_session_cookie(request) or any(
        name == "ai2apps_cloud_browser"
        or name.startswith("ai2apps_cloud_browser_")
        for name in request.cookies
    )


def _raise_origin_mismatch() -> None:
    raise HTTPException(
        status_code=403,
        detail={
            "code": "csrf_origin_mismatch",
            "message": "Cookie-authenticated writes require the current Local origin",
        },
    )
