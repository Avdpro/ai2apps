# SPDX-License-Identifier: BUSL-1.1
# See LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md.
"""Credential-safe error rendering shared by model inference transports."""

import re

import httpx


def provider_retry_headers(response: httpx.Response) -> dict[str, str]:
    names = ("retry-after", "x-request-id", "request-id", "x-deepseek-request-id")
    return {name: response.headers[name] for name in names if name in response.headers}


def rate_limit_detail(response: httpx.Response, message: str) -> str | dict:
    if response.status_code != 429:
        return message
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
    except ValueError:
        error = None
    code = (error.get("code") or error.get("type")) if isinstance(error, dict) else None
    if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", code):
        code = "model_rate_limited"
    return {"code": code, "message": message}


def redacted_provider_error(response: httpx.Response, secret: str) -> str:
    """Return a bounded upstream error without ever reflecting credentials."""

    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
            else:
                message = payload.get("detail") or error
            if isinstance(message, str) and message:
                return message.replace(secret, "[redacted]")[:1000]
    except (ValueError, TypeError):
        pass
    return f"Cloud provider returned HTTP {response.status_code}"
