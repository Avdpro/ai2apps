import base64
import io
import json
import zipfile

import av
import pytest
from PIL import Image

from ai2apps.studio.visual_sequence import render_visual_sequence


def png(color, size=(720, 1280)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode()


def render(output, mode, frames):
    return render_visual_sequence(
        json.dumps({"format": mode, "frames": frames, "seconds": .5}).encode(), output
    )


def test_screenshot_and_timed_silent_clip(tmp_path):
    output = tmp_path / "output"
    red, blue = png("red"), png("blue")
    assert render(output, "png", [red])["media_type"] == "image/png"
    with Image.open(output) as image:
        assert image.size == (720, 1280)
        assert image.getpixel((0, 0)) == (255, 0, 0)
    assert render(output, "mp4", [red, blue])["media_type"] == "video/mp4"
    with av.open(output) as movie:
        assert not movie.streams.audio
        frames = list(movie.decode(video=0))
        assert len(frames) == 12 and frames[6].time == .5
        assert frames[0].to_image().getpixel((0, 0))[0] > 240
        assert frames[6].to_image().getpixel((0, 0))[2] > 240


def test_invalid_or_mixed_frames_are_rejected(tmp_path):
    for mode, frames in [
        ("png", [png("red"), png("blue")]),
        ("png", ["%%%"]),
        ("png", [png("red", (721, 1280))]),
        ("mp4", [png("red"), png("blue", (1280, 720))]),
        ("zip", [png("red"), png("blue", (1280, 720))]),
    ]:
        with pytest.raises(ValueError):
            render(tmp_path / "output", mode, frames)


def test_ordered_png_archive(tmp_path):
    output = tmp_path / "output"
    assert render(output, "zip", [png("red"), png("blue")]) == {
        "kind": "file", "media_type": "application/zip", "format": "zip",
    }
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["page-01.png", "page-02.png"]
        for index, color in enumerate(((255, 0, 0), (0, 0, 255)), 1):
            with Image.open(archive.open(f"page-{index:02d}.png")) as image:
                assert image.size == (720, 1280)
                assert image.getpixel((0, 0)) == color


@pytest.mark.parametrize("studio", ["ai2apps.imagine-studio", "ai2apps.doc-studio"])
def test_export_endpoint_checks_current_mount_and_declared_output(studio):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ai2apps.api import studio_mini_apps as api
    from ai2apps.studio.visual_sequence import CAPABILITY

    principal = SimpleNamespace(actor_user_id="actor", installation_id="installation")
    declaration = {
        "id": "arbitrary.provider.sequence", "version": "1.0.0",
        "provider": {"appId": "arbitrary.provider", "digest": "current"},
        "requirements": {"capabilities": [CAPABILITY]}, "outputs": [],
    }
    mount = {
        "entry_source": "mini_entry", "app_key": "arbitrary.provider", "effective_digest": "current",
        "context": {"studioId": studio, "miniAppId": declaration["id"], "studioInstanceId": "owner"},
    }

    def require_access(instance, actor):
        assert (instance, actor) == ("owner", principal)

    runtime = SimpleNamespace(
        database=object(), studio_jobs=object(),
        extension_manager=SimpleNamespace(
            mount_entry=lambda mount_id, **kw: mount,
            list_studio_mini_apps=lambda studio_id, **kw: [declaration],
            require_instance_access=require_access,
            instance_entry=lambda instance, **kw: {"app_key": studio},
        ),
    )
    app = FastAPI()
    app.include_router(api.create_studio_mini_app_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    path = f"/studios/{studio}/mini-app-mounts/mount/capabilities/{CAPABILITY}/invoke"
    spec = {"format": "png", "frames": [png("red")], "seconds": 1}

    def post(value):
        return client.post(path, files={"file": ("sequence.json", json.dumps(value))})

    assert post(spec).status_code == 403
    declaration["outputs"] = [{"kind": "image", "final": True}]
    assert post({"format": "png", "frames": ["invalid"], "seconds": 1}).status_code == 422
    declaration["requirements"]["capabilities"].clear()
    assert post(spec).status_code == 403
    declaration["requirements"]["capabilities"].append(CAPABILITY)
    mount["effective_digest"] = "stale"
    assert post(spec).status_code == 409
