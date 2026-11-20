"""Bounded image/PDF transport for the iLink Bot channel."""

from __future__ import annotations

import base64
import binascii
import hashlib
import http.client
import io
import logging
import secrets
import warnings
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from PIL import Image, ImageOps

from .weixin import ConnectorError, NoRedirect

CDN = "https://novac2c.cdn.weixin.qq.com/c2c"
IMAGE_LIMIT = 8 * 1024 * 1024
PDF_LIMIT = 25 * 1024 * 1024
MAX_FILES = 2
MAX_PIXELS = 16_000_000
UPLOAD_TIMEOUT = 60
IMAGE_TYPES = {"image/png", "image/jpeg"}
LOGGER = logging.getLogger(__name__)


def cdn_url(value, operation, **params):
    if value:
        if (
            not isinstance(value, str)
            or len(value) > 8192
            or not value.isascii()
            or any(ord(c) <= 32 for c in value)
        ):
            raise ConnectorError("ilink_media_invalid_url")
        try:
            url = urlsplit(value)
        except ValueError:
            raise ConnectorError("ilink_media_invalid_url") from None
        if (url.scheme, url.netloc, url.path, url.fragment) != (
            "https",
            "novac2c.cdn.weixin.qq.com",
            f"/c2c/{operation}",
            "",
        ):
            raise ConnectorError("ilink_media_invalid_url")
        return value
    if not all(isinstance(v, str) and 0 < len(v) <= 4096 for v in params.values()):
        raise ConnectorError("ilink_media_invalid_reference")
    return f"{CDN}/{operation}?{urlencode(params)}"


def media_key(value, *, hex_key=False):
    try:
        if not isinstance(value, str) or not 0 < len(value) <= 64:
            raise ValueError
        key = (
            bytes.fromhex(value) if hex_key else base64.b64decode(value, validate=True)
        )
        if not hex_key and len(key) == 32:
            key = bytes.fromhex(key.decode("ascii"))
        if len(key) != 16:
            raise ValueError
        return key
    except (ValueError, binascii.Error):
        raise ConnectorError("ilink_media_invalid_key") from None


def crypt(data, key, *, encrypt):
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    if encrypt:
        pad = padding.PKCS7(128).padder()
        ctx = cipher.encryptor()
        return ctx.update(pad.update(data) + pad.finalize()) + ctx.finalize()
    try:
        ctx = cipher.decryptor()
        unpad = padding.PKCS7(128).unpadder()
        return unpad.update(ctx.update(data) + ctx.finalize()) + unpad.finalize()
    except ValueError:
        raise ConnectorError("ilink_media_decryption_failed") from None


def filename(value, ext):
    name = Path(value.replace("\\", "/")).name if isinstance(value, str) else ""
    name = "".join(c for c in name if c.isprintable()).strip()
    return (Path(name).stem[:100].strip(". ") or "微信附件") + ext


def validate(data, kind, name=None):
    if kind == "pdf":
        if not data or len(data) > PDF_LIMIT or b"%PDF-" not in data[:1024]:
            raise ConnectorError("ilink_media_invalid_pdf")
        return filename(name, ".pdf"), "application/pdf"
    if not data or len(data) > IMAGE_LIMIT:
        raise ConnectorError("ilink_media_invalid_image")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=("PNG", "JPEG")) as img:
                if img.width * img.height > MAX_PIXELS or getattr(
                    img, "is_animated", False
                ):
                    raise ValueError
                ext, mime = (
                    (".png", "image/png")
                    if img.format == "PNG"
                    else (".jpg", "image/jpeg")
                )
                img.verify()
    except (
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ConnectorError("ilink_media_invalid_image") from None
    return filename(name, ext), mime


def smaller_jpeg(data):
    """Keep PNG when converting would lose transparency or save no bytes."""
    try:
        with Image.open(io.BytesIO(data), formats=("PNG",)) as image:
            if image.mode not in {"RGB", "L", "P"} or "transparency" in image.info:
                return data
            oriented = ImageOps.exif_transpose(image)
            if oriented.mode == "P":
                oriented = oriented.convert("RGB")
            output = io.BytesIO()
            oriented.save(
                output,
                "JPEG",
                quality=88,
                optimize=True,
                icc_profile=image.info.get("icc_profile"),
            )
            if output.tell() < len(data):
                return output.getvalue()
    except (OSError, SyntaxError, ValueError):
        pass
    return data


def inbound_ref(item):
    kind = item.get("type")
    if kind not in (2, 4):
        return None
    body = item.get("image_item" if kind == 2 else "file_item")
    if not isinstance(body, dict):
        raise ConnectorError("ilink_media_invalid_reference")
    name = body.get("file_name")
    if kind == 4 and (not isinstance(name, str) or not name.lower().endswith(".pdf")):
        raise ConnectorError("ilink_media_unsupported")
    media = body.get("media")
    if not isinstance(media, dict):
        raise ConnectorError("ilink_media_invalid_reference")
    url = cdn_url(
        media.get("full_url"),
        "download",
        encrypted_query_param=media.get("encrypt_query_param"),
    )
    hex_value = body.get("aeskey") if kind == 2 else None
    value = hex_value or media.get("aes_key")
    key = (
        media_key(value, hex_key=bool(hex_value)).hex()
        if value is not None or kind == 4
        else None
    )
    return {
        "kind": "image" if kind == 2 else "pdf",
        "url": url,
        "key": key,
        "name": filename(name, ".pdf") if kind == 4 else None,
    }


class MediaTransport:
    def __init__(self, ilink):
        self.ilink = ilink

    def download(self, ref):
        limit = (PDF_LIMIT if ref["kind"] == "pdf" else IMAGE_LIMIT) + 16
        url = cdn_url(ref["url"], "download")
        try:
            with build_opener(NoRedirect()).open(Request(url), timeout=12) as response:
                data = response.read(limit + 1)
        except (OSError, ValueError, http.client.HTTPException):
            raise ConnectorError("ilink_media_download_failed") from None
        if len(data) > limit:
            raise ConnectorError("ilink_media_too_large")
        if ref["key"]:
            data = crypt(data, media_key(ref["key"], hex_key=True), encrypt=False)
        name, mime = validate(data, ref["kind"], ref["name"])
        return data, name, mime

    def upload(self, config, data, name, mime, *, compact_image=False):
        image = mime in IMAGE_TYPES
        name, actual = validate(data, "image" if image else "pdf", name)
        if actual != mime:
            raise ConnectorError("ilink_media_type_mismatch")
        if compact_image and mime == "image/png":
            data = smaller_jpeg(data)
        key, filekey = secrets.token_bytes(16), secrets.token_hex(16)
        encrypted = crypt(data, key, encrypt=True)
        result = self.ilink.request(
            "getuploadurl",
            base=config["base"],
            token=config["token"],
            data={
                "filekey": filekey,
                "media_type": 1 if image else 3,
                "to_user_id": config["user"],
                "rawsize": len(data),
                "rawfilemd5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
                "filesize": len(encrypted),
                "no_need_thumb": True,
                "aeskey": key.hex(),
            },
        )
        full_url = result.get("upload_full_url")
        if isinstance(full_url, str):
            full_url = full_url.strip()
        upload_params = {
            "encrypted_query_param": result.get("upload_param"),
            "filekey": filekey,
        }
        try:
            url = cdn_url(full_url, "upload", **upload_params)
        except ConnectorError as error:
            if (
                str(error) != "ilink_media_invalid_url"
                or not upload_params["encrypted_query_param"]
            ):
                raise
            # The same ticket can include a parameter for the canonical CDN.
            # Never forward bytes to a full URL that fails the CDN allowlist.
            LOGGER.info("iLink upload ticket uses canonical CDN fallback")
            url = cdn_url(None, "upload", **upload_params)
        request = Request(
            url, data=encrypted, headers={"Content-Type": "application/octet-stream"}
        )
        for attempt in (1, 2):
            try:
                with build_opener(NoRedirect()).open(
                    request, timeout=UPLOAD_TIMEOUT
                ) as response:
                    query = (
                        response.headers.get("x-encrypted-param")
                        if response.status == 200
                        else None
                    )
                break
            except HTTPError as error:
                LOGGER.warning("iLink media CDN rejected upload (HTTP %d)", error.code)
                if attempt == 2 or not 500 <= error.code <= 599:
                    raise ConnectorError("ilink_media_upload_failed") from None
            except (OSError, http.client.HTTPException) as error:
                reason = error.reason if isinstance(error, URLError) else error
                LOGGER.warning(
                    "iLink media CDN upload attempt %d failed (%s)",
                    attempt,
                    type(reason).__name__,
                )
                if attempt == 2:
                    raise ConnectorError("ilink_media_upload_failed") from None
        if not query or len(query) > 4096:
            LOGGER.warning(
                "iLink media CDN upload returned no usable download reference"
            )
            raise ConnectorError("ilink_media_upload_failed")
        media = {
            "encrypt_query_param": query,
            "encrypt_type": 1,
            "aes_key": base64.b64encode(key.hex().encode()).decode(),
        }
        if image:
            return {
                "type": 2,
                "image_item": {"media": media, "mid_size": len(encrypted)},
            }
        return {
            "type": 4,
            "file_item": {"media": media, "file_name": name, "len": str(len(data))},
        }


def store_attachment(documents, session, data, name, mime):
    """Use the same Local attachment records as an uploaded Chat file."""
    import tempfile

    if mime == "application/pdf":
        item = documents.create(session, filename=name, media_type=mime, data=data)
        parsed = documents.parse(session, item.id)
        if parsed.status.value != "ready" or not any(
            block.text.strip() for block in documents.blocks(session, item.id, limit=20)
        ):
            raise ConnectorError("ilink_media_unreadable_pdf")
        return item.id

    root = documents.root / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="ilink-", dir=root))
    target = folder / name
    try:
        with target.open("xb") as stream:
            target.chmod(0o600)
            stream.write(data)
        return documents.create_reference(
            session, target, filename=name, media_type=mime, source="uploaded_file"
        ).id
    except BaseException:
        target.unlink(missing_ok=True)
        folder.rmdir()
        raise


def read_artifact(workspace, session, ref):
    asset = workspace.get_artifact(session, ref)
    if asset.media_type not in IMAGE_TYPES | {"application/pdf"}:
        raise ConnectorError("ilink_media_unsupported")
    limit = PDF_LIMIT if asset.media_type == "application/pdf" else IMAGE_LIMIT
    if not 0 < asset.size_bytes <= limit:
        raise ConnectorError("ilink_media_too_large")
    with workspace.artifact_path(asset).open("rb") as stream:
        data = stream.read(limit + 1)
    if (
        len(data) != asset.size_bytes
        or "sha256:" + hashlib.sha256(data).hexdigest() != asset.content_hash
    ):
        raise ConnectorError("ilink_media_changed")
    return data, asset.name, asset.media_type
