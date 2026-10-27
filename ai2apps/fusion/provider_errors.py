# SPDX-License-Identifier: BUSL-1.1
# See LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md.
"""Credential-safe error rendering shared by model inference transports."""

import httpx


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
