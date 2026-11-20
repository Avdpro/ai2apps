"""Local reference-video links are scoped to one active task and Device Host."""

import hashlib
from types import SimpleNamespace

import httpx
import pytest
from starlette.applications import Starlette

from ai2apps.video.temporary_input import issue, revoke_task
from ai2apps.web.public_boundary import PublicDeviceBoundary


@pytest.mark.asyncio
async def test_reference_video_link_is_private_to_active_device_and_revocable(tmp_path):
    origin = "https://device-" + "a" * 32 + ".ai2apps.com"
    device = SimpleNamespace(device_id="device-1", enabled=True, status="active",
                             subdomain="device-" + "a" * 32, public_origin=origin)
    remote = SimpleNamespace(repository=SimpleNamespace(list=lambda: [device]),
                             frpc=SimpleNamespace(status=lambda: {"running": True, "deviceId": "device-1"}))
    runtime = SimpleNamespace(remote=remote)
    root = tmp_path / "task"
    root.mkdir()
    path = root / "input.mp4"
    data = b"private reference video"
    path.write_bytes(data)
    url = issue(runtime, "task-1", root, {"path": "input.mp4", "media_type": "video/mp4",
                                          "sha256": hashlib.sha256(data).hexdigest()})
    app = Starlette()
    app.add_middleware(PublicDeviceBoundary, manager_provider=lambda: remote)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as client:
        result = await client.get(url)
        assert result.status_code == 200 and result.content == data
        assert result.headers["cache-control"] == "no-store"
        partial = await client.get(url, headers={"Range": "bytes=0-6"})
        assert partial.status_code == 206 and partial.content == data[:7]
        assert (await client.get(origin + "/v1/public/video-input/" + "x" * 43)).status_code == 404
        path.write_bytes(b"changed")
        assert (await client.get(url)).status_code == 404
        revoke_task("task-1")
        assert (await client.get(url)).status_code == 404
