"""Task-bound video input links over the existing Remote Access connector."""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from starlette.responses import FileResponse, Response

MAX_LEASE_SECONDS = 35 * 60
_leases: dict[str, "_Lease"] = {}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class _Lease:
    task_id: str
    device_id: str
    path: Path
    media_type: str
    sha256: str
    size: int
    expires_at: float


def issue(runtime, task_id: str, task_root: Path, item: dict) -> str:
    from ai2apps.video.tasks import VideoGenerationError

    remote = getattr(runtime, "remote", None)
    connector = remote.frpc.status() if remote is not None else {}
    device_id = connector.get("deviceId")
    device = next((value for value in remote.repository.list()
                   if value.device_id == device_id and value.enabled and value.status == "active"), None) if remote else None
    origin = urlparse(device.public_origin) if device else None
    if (not connector.get("running") or not device or not origin
            or origin.scheme != "https" or origin.hostname != f"{device.subdomain}.ai2apps.com"
            or origin.port is not None or origin.path not in {"", "/"}):
        raise VideoGenerationError("remote_access_required", "Start this device's Remote Access to send a local reference video to Seedance", status_code=503)
    root = task_root.resolve()
    candidate = root / str(item.get("path") or "")
    path = candidate.resolve()
    if candidate.is_symlink() or root not in path.parents or not path.is_file():
        raise VideoGenerationError("input_unavailable", "Frozen reference video is unavailable")
    media_type = str(item.get("media_type") or "")
    if media_type not in {"video/mp4", "video/quicktime"}:
        raise VideoGenerationError("unsupported_media_type", "Seedance reference video must be MP4 or MOV")
    size = path.stat().st_size
    if size > 100 * 1024 * 1024:
        raise VideoGenerationError("input_changed", "Frozen reference video changed or exceeds the local limit")
    digest = _file_sha256(path)
    if digest != item.get("sha256"):
        raise VideoGenerationError("input_changed", "Frozen reference video changed or exceeds the local limit")
    now = time.monotonic()
    for key, lease in list(_leases.items()):
        if lease.expires_at <= now:
            _leases.pop(key, None)
    token = secrets.token_urlsafe(32)
    _leases[hashlib.sha256(token.encode()).hexdigest()] = _Lease(task_id, device_id, path, media_type, digest, size, now + MAX_LEASE_SECONDS)
    return device.public_origin.rstrip("/") + "/v1/public/video-input/" + token


def revoke_task(task_id: str) -> None:
    for key, lease in list(_leases.items()):
        if lease.task_id == task_id:
            _leases.pop(key, None)


async def serve(scope, receive, send, *, device_id: str) -> None:
    path = scope.get("path", "")
    token = path.removeprefix("/v1/public/video-input/")
    lease = _leases.get(hashlib.sha256(token.encode()).hexdigest()) if token else None
    valid = bool(lease and lease.device_id == device_id and lease.expires_at > time.monotonic())
    if valid:
        try:
            valid = (not lease.path.is_symlink() and lease.path.is_file()
                     and lease.path.stat().st_size == lease.size
                     and _file_sha256(lease.path) == lease.sha256)
        except OSError:
            valid = False
    if not valid:
        return await Response(status_code=404)(scope, receive, send)
    response = FileResponse(lease.path, media_type=lease.media_type,
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                     "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'"})
    await response(scope, receive, send)
