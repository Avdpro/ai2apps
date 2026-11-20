"""Fetch only opted-in public raster images, without browser or mail credentials."""

import base64
import http.client
from io import BytesIO
import time
from urllib.parse import urljoin, urlsplit

from PIL import Image
from ai2apps.documents.public_pdf import _destination, _pinned_connection

_MAX_BYTES = 1024 * 1024
_FORMATS = {"PNG", "JPEG", "GIF", "WEBP"}


def image_url(value):
    try:
        url, _, port, _ = _destination(value)
        if port == 443 and urlsplit(url).scheme == "https":
            return url
    except (ValueError, UnicodeError):
        pass
    return None


def _download(url, deadline):
    for _ in range(4):
        if time.monotonic() >= deadline or not image_url(url):
            raise ValueError("Image URL or deadline rejected")
        url, host, port, path = _destination(url)
        connection = _pinned_connection(host, port, deadline)
        try:
            connection.request("GET", path, headers={
                "Accept": "image/png, image/jpeg, image/gif, image/webp",
                "Accept-Encoding": "identity",
                "User-Agent": "AI2Apps-Mail/1.0",
            })
            with connection.getresponse() as response:
                if response.status in (301, 302, 303, 307, 308):
                    target = response.getheader("Location")
                    if not target:
                        break
                    url = urljoin(url, target)
                    continue
                media = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
                if response.status != 200 or media not in {"image/png", "image/jpeg", "image/gif", "image/webp"}:
                    break
                size = response.getheader("Content-Length", "")
                if size.isdecimal() and int(size) > _MAX_BYTES:
                    break
                data = bytearray()
                while time.monotonic() < deadline:
                    chunk = response.read1(min(65536, _MAX_BYTES + 1 - len(data)))
                    if not chunk:
                        if not size.isdecimal() or len(data) == int(size):
                            return bytes(data)
                        break
                    data.extend(chunk)
                    if len(data) > _MAX_BYTES:
                        break
        finally:
            connection.close()
        break
    raise ValueError("Image download unavailable")


def _png(data):
    with Image.open(BytesIO(data), formats=list(_FORMATS)) as image:
        if image.width * image.height > 4_000_000:
            raise ValueError("Image dimensions too large")
        # Decode and re-encode the first frame without forwarding metadata.
        clean = image.convert("RGBA")
        clean.info.clear()
        clean.thumbnail((1200, 1200))
        out = BytesIO()
        clean.save(out, format="PNG")
        if out.tell() > _MAX_BYTES:
            raise ValueError("Image output too large")
        return out.getvalue()


class RemoteImages:
    def __init__(self):
        self.deadline = time.monotonic() + 12
        self.cache = {}
        self.remaining = 3 * _MAX_BYTES

    def __call__(self, url):
        if url not in self.cache:
            if len(self.cache) >= 12 or time.monotonic() >= self.deadline:
                return None
            result = None
            try:
                png = _png(_download(url, min(self.deadline, time.monotonic() + 5)))
                if len(png) <= self.remaining:
                    result = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
            except (OSError, ValueError, http.client.HTTPException, Image.DecompressionBombError):
                pass
            self.cache[url] = result
        result = self.cache[url]
        if result and len(result) <= self.remaining:
            self.remaining -= len(result)
            return result
        return None
