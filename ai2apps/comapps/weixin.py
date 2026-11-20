"""Bounded HTTPS client for the iLink Bot protocol."""

from __future__ import annotations

import base64
import io
import json
import secrets
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import qrcode
from qrcode.exceptions import DataOverflowError

BASE = "https://ilinkai.weixin.qq.com"
BASE_INFO = {"channel_version": "0.1.0", "bot_agent": "AI2Apps/0.1.0"}


class ConnectorError(RuntimeError):
    """A stable error code safe for the Package UI."""


def trusted_base(value: str) -> str:
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        if (
            url.scheme == "https"
            and host.endswith(".weixin.qq.com")
            and url.netloc == host
            and url.path in ("", "/")
            and not url.query
            and not url.fragment
        ):
            return f"https://{host}"
    except (TypeError, ValueError):
        pass
    raise ConnectorError("ilink_untrusted_server")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ILink:
    def request(
        self, operation, *, base=BASE, token=None, data=None, query=None, timeout=12
    ):
        url = f"{trusted_base(base)}/ilink/bot/{operation}"
        if query:
            url += "?" + urlencode(query)
        headers = {"iLink-App-Id": "bot", "iLink-App-ClientVersion": str(0x02040A)}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if token:
            data = {**data, "base_info": BASE_INFO}
            headers.update(
                {
                    "AuthorizationType": "ilink_bot_token",
                    "Authorization": f"Bearer {token}",
                    "X-WECHAT-UIN": base64.b64encode(
                        str(secrets.randbits(32)).encode()
                    ).decode(),
                }
            )
        request = Request(
            url, None if data is None else json.dumps(data).encode(), headers
        )
        try:
            with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ConnectorError("ilink_response_too_large")
            result = json.loads(raw)
        except (URLError, OSError, ValueError) as error:
            raise ConnectorError("ilink_request_failed") from error
        if not isinstance(result, dict):
            raise ConnectorError("ilink_invalid_response")
        if result.get("ret", 0) != 0 or result.get("errcode", 0) != 0:
            code = (
                "ilink_reconnect_required"
                if -14 in (result.get("ret"), result.get("errcode"))
                else "ilink_request_rejected"
            )
            raise ConnectorError(code)
        return result


def qr_png(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 1400:
        raise ConnectorError("ilink_invalid_qr")
    try:
        image = qrcode.make(value)
    except DataOverflowError:
        raise ConnectorError("ilink_invalid_qr") from None
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
