import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from ai2apps.api.video_studio import create_video_studio_router
from ai2apps.config import DEFAULT_COMPOSER_IMPORT_LIMIT_BYTES, PlatformConfig
from ai2apps.identity import RequestPrincipal
from ai2apps.storage import PlatformDatabase
from ai2apps.video.composer import (
    ComposerClip,
    ComposerProject,
    ComposerSourceStore,
    _clip_visual_state,
    _fit_image_to_visual_box,
    _mix_audio,
    render_composition,
)

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"


def media_file(path: Path, *, color: int = 80) -> None:
    with av.open(str(path), "w", format="mp4") as container:
        video = container.add_stream("libx264", rate=12)
        video.width = video.height = 32
        video.pix_fmt = "yuv420p"
        audio = container.add_stream("aac", rate=48_000)
        audio.layout = "stereo"
        for _index in range(12):
            pixels = np.full((32, 32, 3), color, dtype=np.uint8)
            for packet in video.encode(av.VideoFrame.from_ndarray(pixels, format="rgb24")):
                container.mux(packet)
        for packet in video.encode():
            container.mux(packet)
        for _index in range(47):
            samples = np.zeros((2, 1024), dtype=np.float32)
            frame = av.AudioFrame.from_ndarray(samples, format="fltp", layout="stereo")
            frame.sample_rate = 48_000
            for packet in audio.encode(frame):
                container.mux(packet)
        for packet in audio.encode():
            container.mux(packet)


def project(source_id: str) -> ComposerProject:
    return ComposerProject.model_validate(
        {
            "schema": "ai2apps.video-composition/v1",
            "title": "Composer smoke",
            "settings": {"width": 64, "height": 64, "fps": 12, "background": "#000000"},
            "tracks": [
                {"id": "v1", "kind": "video", "name": "Video 1", "order": 0},
                {"id": "v2", "kind": "video", "name": "Video 2", "order": 1},
            ],
            "clips": [
                {
                    "id": "c1", "sourceId": source_id, "trackId": "v1", "name": "Base",
                    "start": 0, "sourceStart": 0, "duration": 0.75, "fadeOut": 1 / 12,
                    "width": 64, "height": 64,
                },
                {
                    "id": "c2", "sourceId": source_id, "trackId": "v2", "name": "Overlay",
                    "start": 0.25, "sourceStart": 0, "duration": 0.5, "speed": 1.25,
                    "volume": 0.5, "fadeIn": 0.1, "x": 32, "y": 32,
                    "width": 24, "height": 24, "opacity": 0.8,
                },
            ],
        }
    )


def test_composer_rejects_same_track_overlap_and_preserves_group_color():
    base = {
        "title": "Timeline rules",
        "tracks": [{"id": "v1", "kind": "video", "name": "Video 1", "order": 0}],
        "clips": [
            {
                "id": "a", "sourceId": "source", "trackId": "v1", "name": "A",
                "start": 0, "duration": 1, "groupId": "group_ab", "color": "#db2777",
            },
            {
                "id": "b", "sourceId": "source", "trackId": "v1", "name": "B",
                "start": 1, "duration": 1, "groupId": "group_ab", "color": "#059669",
            },
        ],
    }
    valid = ComposerProject.model_validate(base)
    payload = valid.model_dump(by_alias=True)
    assert payload["clips"][0]["groupId"] == "group_ab"
    assert payload["clips"][0]["color"] == "#db2777"

    overlapping = json.loads(json.dumps(base))
    overlapping["clips"][1]["start"] = 0.5
    try:
        ComposerProject.model_validate(overlapping)
    except Exception as error:
        assert "cannot overlap" in str(error)
    else:
        raise AssertionError("clips on one track must never overlap")


def test_composer_quantizes_timeline_times_to_project_frames():
    composition = ComposerProject.model_validate(
        {
            "title": "Frame grid",
            "settings": {"fps": 30},
            "tracks": [{"id": "v1", "kind": "video", "name": "Video 1", "order": 0}],
            "clips": [{
                "id": "clip", "sourceId": "source", "trackId": "v1", "name": "Clip",
                "start": 1.2620952380952382, "duration": 1.0478095238095237,
            }],
        }
    )
    clip = composition.clips[0]
    assert round(clip.start * composition.settings.fps) == 38
    assert round(clip.duration * composition.settings.fps) == 31
    assert clip.start == 1.266666667
    assert clip.duration == 1.033333333


def test_composer_keyframes_validate_and_interpolate_all_transition_modes():
    def animated(transition: str) -> ComposerClip:
        return ComposerClip.model_validate(
            {
                "id": "clip", "sourceId": "source", "trackId": "v1", "name": "Animated",
                "start": 0, "duration": 1, "x": 0, "y": 0, "width": 100, "height": 50,
                "opacity": 0,
                "keyframes": [{
                    "id": "keyframe", "frame": 10, "transition": transition,
                    "x": 100, "y": 50, "width": 200, "height": 100, "opacity": 1,
                }],
            }
        )

    hold = _clip_visual_state(animated("hold"), 5)
    linear = _clip_visual_state(animated("linear"), 5)
    ease = _clip_visual_state(animated("ease"), 2)
    assert hold == {"x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0, "opacity": 0.0}
    assert linear == {"x": 50.0, "y": 25.0, "width": 150.0, "height": 75.0, "opacity": 0.5}
    assert round(ease["x"], 3) == 10.4 and round(ease["opacity"], 3) == 0.104
    assert _clip_visual_state(animated("hold"), 10)["x"] == 100

    inherited = animated("linear")
    inherited.keyframes[0].x = None
    inherited.keyframes[0].width = None
    inherited_state = _clip_visual_state(inherited, 10)
    assert inherited_state["x"] == 0 and inherited_state["width"] == 100
    assert inherited_state["y"] == 50 and inherited_state["opacity"] == 1

    invalid = {
        "title": "Invalid key frame",
        "settings": {"fps": 10},
        "tracks": [{"id": "v1", "kind": "video", "name": "Video 1", "order": 0}],
        "clips": [{
            "id": "clip", "sourceId": "source", "trackId": "v1", "name": "Clip",
            "start": 0, "duration": 1,
            "keyframes": [{"id": "outside", "frame": 10, "x": 0, "y": 0, "width": 100, "height": 100, "opacity": 1}],
        }],
    }
    try:
        ComposerProject.model_validate(invalid)
    except Exception as error:
        assert "inside the clip duration" in str(error)
    else:
        raise AssertionError("a key frame at the exclusive clip end must be rejected")


def test_composer_export_centers_contained_media_inside_visual_box():
    source = Image.new("RGBA", (40, 20), (240, 30, 20, 255))
    layer = _fit_image_to_visual_box(source, 40, 40)

    assert layer.size == (40, 40)
    assert layer.getpixel((20, 5))[3] == 0
    assert layer.getpixel((20, 10))[3] == 255
    assert layer.getpixel((20, 29))[3] == 255
    assert layer.getpixel((20, 30))[3] == 0


def test_video_clips_always_have_fixed_start_and_end_keyframes():
    composition = ComposerProject.model_validate(
        {
            "title": "Endpoint key frames",
            "settings": {"fps": 10, "width": 320, "height": 180},
            "tracks": [
                {"id": "v1", "kind": "video", "name": "Video 1", "order": 0},
                {"id": "a1", "kind": "audio", "name": "Audio 1", "order": 1},
            ],
            "clips": [
                {"id": "visual", "sourceId": "source", "trackId": "v1", "name": "Visual", "start": 0, "duration": 1},
                {"id": "audio", "sourceId": "audio", "trackId": "a1", "name": "Audio", "start": 0, "duration": 1},
            ],
        }
    )
    visual, audio = composition.clips
    assert [(keyframe.endpoint, keyframe.frame) for keyframe in visual.keyframes] == [("start", 0), ("end", 9)]
    assert visual.keyframes[0].transition == "hold"
    assert audio.keyframes == []

    deleted_endpoints = composition.model_dump(by_alias=True)
    deleted_endpoints["clips"][0]["keyframes"] = []
    restored = ComposerProject.model_validate(deleted_endpoints).clips[0]
    assert [(keyframe.endpoint, keyframe.frame) for keyframe in restored.keyframes] == [("start", 0), ("end", 9)]

    resized = visual.model_copy(deep=True)
    resized.duration = 2
    resized.keyframes[-1].frame = 3
    normalized = ComposerProject(
        title="Resized",
        settings={"fps": 10},
        tracks=[{"id": "v1", "kind": "video", "name": "Video 1", "order": 0}],
        clips=[resized],
    )
    assert [(keyframe.endpoint, keyframe.frame) for keyframe in normalized.clips[0].keyframes] == [("start", 0), ("end", 19)]


def test_hidden_video_track_keeps_audio_while_muted_audio_track_is_silent(monkeypatch, tmp_path):
    composition = ComposerProject.model_validate(
        {
            "title": "Track output semantics",
            "settings": {"fps": 10},
            "tracks": [
                {"id": "video", "kind": "video", "name": "Video", "order": 0, "muted": True},
                {"id": "audio", "kind": "audio", "name": "Audio", "order": 1, "muted": True},
            ],
            "clips": [
                {"id": "v", "sourceId": "video-source", "trackId": "video", "name": "V", "start": 0, "duration": 1},
                {"id": "a", "sourceId": "audio-source", "trackId": "audio", "name": "A", "start": 0, "duration": 1},
            ],
        }
    )
    monkeypatch.setattr(
        "ai2apps.video.composer._decoded_audio",
        lambda _path, _start, duration, rate: np.ones((2, round(duration * rate)), dtype=np.float32),
    )
    source = {"hasAudio": True}
    mixed = _mix_audio(
        composition,
        {"video-source": (source, tmp_path / "video"), "audio-source": (source, tmp_path / "audio")},
        rate=10,
    )
    assert np.allclose(mixed, 1), "hidden video keeps its audio; muted audio track contributes nothing"


def test_composer_source_store_is_scoped_and_render_is_playable(tmp_path):
    source_path = tmp_path / "source.mp4"
    media_file(source_path)
    store = ComposerSourceStore(tmp_path / "sources")
    source = store.register(
        source_path,
        actor_id="owner",
        installation_id="installation",
        app_instance_id="appi_composer",
    )

    assert source["hasVideo"] is True and source["hasAudio"] is True
    assert "path" not in source
    try:
        store.get(
            source["id"],
            actor_id="owner",
            installation_id="installation",
            app_instance_id="another_app",
        )
    except Exception as error:
        assert getattr(error, "code", "") == "source_not_found"
    else:
        raise AssertionError("a source ID must not cross AppInstance scope")
    record, resolved = store.get(
        source["id"],
        actor_id="owner",
        installation_id="installation",
        app_instance_id="appi_composer",
    )
    output = tmp_path / "composition.mp4"
    import asyncio

    asyncio.run(render_composition(project(source["id"]), {source["id"]: (record, resolved)}, output))
    with av.open(str(output)) as rendered:
        assert rendered.streams.video and rendered.streams.audio
        assert float(rendered.duration or 0) / av.time_base >= 0.7


def test_composer_stream_import_is_private_bounded_and_above_gallery_limit(tmp_path):
    source_path = tmp_path / "source.mp4"
    media_file(source_path)
    store = ComposerSourceStore(tmp_path / "sources")
    payload = source_path.read_bytes()

    source = store.import_stream(
        BytesIO(payload),
        actor_id="owner",
        installation_id="installation",
        app_instance_id="appi_composer",
        display_name="browser-source.mp4",
        media_type="video/mp4",
        max_bytes=len(payload),
    )
    assert source["name"] == "browser-source.mp4"
    assert "path" not in source
    assert DEFAULT_COMPOSER_IMPORT_LIMIT_BYTES > 64 * 1024 * 1024

    try:
        store.import_stream(
            BytesIO(payload),
            actor_id="owner",
            installation_id="installation",
            app_instance_id="appi_composer",
            display_name="too-large.mp4",
            media_type="video/mp4",
            max_bytes=max(1, len(payload) - 1),
        )
    except Exception as error:
        assert getattr(error, "code", "") == "source_too_large"
    else:
        raise AssertionError("Composer stream imports must enforce their own media limit")
    assert not list((tmp_path / "sources").rglob("*.part"))


def test_composer_accepts_still_images_with_adjustable_timeline_duration(tmp_path):
    source_path = tmp_path / "still.png"
    Image.new("RGB", (48, 24), (220, 40, 30)).save(source_path)
    store = ComposerSourceStore(tmp_path / "sources")
    source = store.register(
        source_path,
        actor_id="owner",
        installation_id="installation",
        app_instance_id="appi_composer",
        media_type="image/png",
    )
    assert source["kind"] == "image"
    assert source["hasImage"] is True and source["hasVideo"] is False
    assert source["duration"] == 1

    image_project = ComposerProject.model_validate(
        {
            "title": "Still image",
            "settings": {"width": 64, "height": 64, "fps": 12},
            "tracks": [{"id": "v1", "kind": "video", "name": "Video 1", "order": 0}],
            "clips": [{
                "id": "still", "sourceId": source["id"], "trackId": "v1",
                "name": "Still", "start": 0, "duration": 1.5,
                "width": 48, "height": 24, "opacity": 0,
                "keyframes": [{
                    "id": "visible", "frame": 6, "transition": "linear",
                    "x": 0, "y": 0, "width": 48, "height": 24, "opacity": 1,
                }],
            }],
        }
    )
    record, resolved = store.get(
        source["id"], actor_id="owner", installation_id="installation",
        app_instance_id="appi_composer",
    )
    output = tmp_path / "still.mp4"
    import asyncio

    asyncio.run(render_composition(image_project, {source["id"]: (record, resolved)}, output))
    with av.open(str(output)) as rendered:
        assert rendered.streams.video
        assert float(rendered.duration or 0) / av.time_base >= 1.4
        frames = [frame.to_ndarray(format="rgb24") for frame in rendered.decode(video=0)]
        assert frames[0].mean() < frames[6].mean()


def test_composer_masks_use_luminance_without_alpha_and_alpha_when_present(tmp_path):
    base_path = tmp_path / "base.png"
    luminance_path = tmp_path / "luminance.png"
    alpha_path = tmp_path / "alpha.png"
    Image.new("RGB", (64, 64), "white").save(base_path)
    luminance = Image.new("RGB", (64, 64), "black")
    luminance.paste("white", (32, 0, 64, 64))
    luminance.save(luminance_path)
    Image.new("RGBA", (64, 64), (0, 0, 0, 255)).save(alpha_path)

    store = ComposerSourceStore(tmp_path / "mask-sources")
    scope = {
        "actor_id": "owner",
        "installation_id": "installation",
        "app_instance_id": "appi_composer",
    }
    base = store.register(base_path, media_type="image/png", **scope)
    luminance_mask = store.register(luminance_path, media_type="image/png", **scope)
    alpha_mask = store.register(alpha_path, media_type="image/png", **scope)
    assert luminance_mask["hasAlpha"] is False
    assert alpha_mask["hasAlpha"] is True

    composition = ComposerProject.model_validate(
        {
            "title": "Mask semantics",
            "settings": {"width": 64, "height": 64, "fps": 10, "background": "#000000"},
            "tracks": [{"id": "v1", "kind": "video", "name": "Video 1", "order": 0}],
            "clips": [
                {
                    "id": "luma", "sourceId": base["id"], "maskSourceId": luminance_mask["id"],
                    "trackId": "v1", "name": "Luma", "start": 0, "duration": 0.2,
                    "width": 64, "height": 64,
                },
                {
                    "id": "alpha", "sourceId": base["id"], "maskSourceId": alpha_mask["id"],
                    "trackId": "v1", "name": "Alpha", "start": 0.2, "duration": 0.2,
                    "width": 64, "height": 64,
                },
            ],
        }
    )
    records = {source["id"]: store.get(source["id"], **scope) for source in (base, luminance_mask, alpha_mask)}
    output = tmp_path / "masked.mp4"
    import asyncio

    asyncio.run(render_composition(composition, records, output))
    with av.open(str(output)) as rendered:
        frames = [frame.to_ndarray(format="rgb24") for frame in rendered.decode(video=0)]
    assert frames[0][:, :28].mean() < 30 and frames[0][:, 36:].mean() > 200
    assert frames[2].mean() > 200, "opaque alpha wins even when the mask RGB channels are black"


def test_video_composer_api_registers_source_and_materializes_artifact(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    config = PlatformConfig.from_base_path(tmp_path / "data")
    principal = RequestPrincipal.legacy_local()
    app_instance_id = "appi_video_studio"
    source_path = tmp_path / "local-source.mp4"
    media_file(source_path, color=130)
    captured = {}

    class ExtensionManager:
        def require_instance_access(self, instance_id, _principal):
            assert instance_id == app_instance_id

        def instance_entry(self, instance_id, *, principal):
            self.require_instance_access(instance_id, principal)
            return {"app_key": "ai2apps.video-studio"}

    class VideoTasks:
        def artifact_session(self):
            return "sess_composer"

    class Workspace:
        def import_artifact(self, session_id, source, name, **kwargs):
            captured["bytes"] = source.read_bytes()
            captured["metadata"] = kwargs["metadata"]
            captured["workspace_kwargs"] = kwargs
            return SimpleNamespace(id="arti_composer", name=name, media_type=kwargs["media_type"])

    runtime = SimpleNamespace(
        database=database,
        config=config,
        events=None,
        extension_manager=ExtensionManager(),
        video_tasks=VideoTasks(),
        workspace=Workspace(),
    )
    app = FastAPI()
    app.include_router(create_video_studio_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    headers = {"X-AI2Apps-App-Instance": app_instance_id}

    source = client.post(
        "/video-studio/composer/sources",
        headers=headers,
        json={"sourcePath": str(source_path), "name": source_path.name, "mediaType": "video/mp4"},
    )
    assert source.status_code == 201
    source_payload = source.json()
    assert str(source_path) not in json.dumps(source_payload)
    uploaded = client.post(
        "/video-studio/composer/sources/import",
        headers=headers,
        files={"file": ("browser-source.mp4", source_path.read_bytes(), "video/mp4")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["name"] == "browser-source.mp4"
    assert str(source_path) not in uploaded.text
    content = client.get(
        f"/video-studio/composer/sources/{source_payload['id']}/content",
        params={"appInstanceId": app_instance_id},
    )
    assert content.status_code == 200 and content.content.startswith(b"\x00\x00\x00")

    project_path = tmp_path / "saved.ai2video"
    saved = client.post(
        "/video-studio/composer/projects/save",
        headers=headers,
        json={
            "targetPath": str(project_path),
            "project": project(source_payload["id"]).model_dump(by_alias=True),
            "sourceIds": [source_payload["id"]],
        },
    )
    assert saved.status_code == 200 and saved.json()["path"] == str(project_path)
    document = json.loads(project_path.read_text())
    assert document["schema"] == "ai2apps.video-composer-project/v1"
    assert document["sourceIds"] == [source_payload["id"]]
    assert str(source_path) not in project_path.read_text()
    opened = client.post(
        "/video-studio/composer/projects/open",
        headers=headers,
        json={"sourcePath": str(project_path)},
    )
    assert opened.status_code == 200
    assert opened.json()["project"]["title"] == "Composer smoke"
    assert opened.json()["sources"][0]["id"] == source_payload["id"]
    assert str(source_path) not in json.dumps(opened.json())

    mask_path = tmp_path / "mask.png"
    Image.new("RGB", (32, 32), "white").save(mask_path)
    mask_payload = client.post(
        "/video-studio/composer/sources",
        headers=headers,
        json={"sourcePath": str(mask_path), "name": mask_path.name, "mediaType": "image/png"},
    ).json()

    composition = project(source_payload["id"])
    composition.clips[0].mask_source_id = mask_payload["id"]
    run = client.post(
        "/video-studio/runs",
        headers=headers,
        json={
            "miniAppId": "ai2apps.video.composer",
            "title": "composer-smoke.mp4",
            "input": {"projectTitle": "Composer smoke", "trackCount": 2, "clipCount": 2},
        },
    ).json()
    started = client.post(
        f"/video-studio/runs/{run['id']}/compose",
        headers=headers,
        json={"project": composition.model_dump(by_alias=True), "outputName": "composer-smoke.mp4"},
    )
    assert started.status_code == 202
    completed = client.get(f"/video-studio/runs/{run['id']}", headers=headers).json()
    assert completed["status"] == "succeeded"
    assert completed["artifacts"][0]["mediaType"] == "video/mp4"
    assert captured["bytes"]
    assert captured["metadata"]["trackCount"] == 2
    assert "run_id" not in captured["workspace_kwargs"]
    assert str(source_path) not in json.dumps(completed)


def test_video_composer_surface_exposes_timeline_preview_and_chat_editing():
    template = (WEB_ROOT / "templates/system_apps/video_studio.html").read_text()
    script = (WEB_ROOT / "static/js/video_studio.js").read_text()
    gallery_script = (WEB_ROOT / "static/js/gallery.js").read_text()
    stylesheet = (WEB_ROOT / "static/css/video_composer.css").read_text()
    composer_backend = (Path(__file__).parents[1] / "ai2apps" / "video" / "composer.py").read_text()
    english = json.loads((WEB_ROOT / "i18n/en.json").read_text())
    chinese = json.loads((WEB_ROOT / "i18n/zh.json").read_text())

    assert "ai2apps.video.composer" in script
    assert "vs-composer-timeline" in template and "beginComposerDrag" in script
    assert "beginComposerTrim" in script and "snapComposerTime" in script
    assert "toggleComposerPreview" in script and "composerPreviewClips" in script
    assert "applyComposerChat" in template and "applyComposerChat" in script
    assert 'class="vs-composer-chat" hidden aria-hidden="true"' in template
    assert "/v1/chat/completions" in script and "allowed = new Set" in script
    assert "renderComposer" in template and "/compose" in script
    assert "beginComposerStageDrag" in script and "beginComposerStageResize" in script
    assert "composerStageStyle" in template and "390 * ratio" in script
    assert "max-height:390px" not in stylesheet
    assert "current.preventDefault()" in script and "pointercancel" in script
    assert "16 - width" in script and "canvasWidth - 16" in script
    assert "layer.style.left" in script and "layer.style.width" in script
    assert "setPointerCapture" in script and "releasePointerCapture" in script
    assert "Keep the active pointer target stable" in script
    assert "resetComposerClipSize" in template and "source.hasImage ? 1" in script
    assert "dropComposerOnTrack" in template and "application/x-ai2apps-gallery-kind" in script
    assert "setData('application/x-ai2apps-gallery-kind', asset.kind)" in gallery_script
    assert "beginComposerScrub" in template and "pointer-events:none" in stylesheet
    assert "settings.snapping" in script and "vs-composer-clip.snapped" in stylesheet
    assert "snapComposerPlayhead" in script and "clip.start + clip.duration" in script
    assert "syncComposerPlayheadToClip" in script and "Math.abs(this.composerPlayhead - start)" in script
    assert "Math.hypot(current.clientX - originX, current.clientY - originY) > 3" in script
    assert "composerPlayheadSnapped&&'snapped'" in template and ".vs-composer-playhead.snapped" in stylesheet
    assert "toggleComposerSnapping" in script and "event.key.toLowerCase() === 'n'" in script
    assert "snapping_shortcut" in template
    assert "quantizeComposerTime" in script and "composerFrameNumber" in script
    assert "`F${composerFrameNumber(composerSelectedClip.start)}`" in template
    assert "`${composerFrameNumber(composerSelectedClip.duration)}f`" in template
    assert ':step="composerFrameDuration"' in template and "composerFormatTime" in template
    assert "addComposerKeyframe" in template and "composerVisualStateAtFrame" in script
    assert "transition_hold" in template and "transition_linear" in template and "transition_ease" in template
    assert "vs-composer-keyframe-marker" in template and "splitComposerKeyframes" in script
    assert "composerSelectedKeyframeIsEndpoint" in template and "composerIsEndpointKeyframe" in script
    assert "lock-keyhole" in template and "keyframe.endpoint === 'end'" in script
    assert "composerIsProtectedKeyframe" in script and "this.composerSelectedKeyframe ? this.deleteComposerKeyframe()" in script
    assert "setComposerKeyframeFrame" in script and "keyframe_frame" in template
    assert ':disabled="composerSelectedKeyframeIsEndpoint"' in template
    assert "item.id !== keyframe.id && item.frame === frame" in script
    assert "composerStageEditMode" in template and "keyframe-edit" in stylesheet and "clip-edit" in stylesheet
    assert "translateComposerClipVisual" in script and "resizeComposerClipVisual" in script
    assert "setComposerKeyframeValue" in template and "composerPreviousKeyframeState" in template
    assert "importComposerMask" in template and "composerPreviewMaskStyle" in script
    assert "maskSourceId" in script and "mask-mode:${mode}" in script
    assert "video_studio.composer.mask_none" in template and "composerMaskSources" in template
    assert "ImageChops.multiply" in composer_backend and "ImageOps.grayscale" in composer_backend
    assert template.count('x-show="composerSource(composerSelectedClip.sourceId)?.hasAudio"') == 2
    assert english["video_studio.composer.fade_in"] == "Audio fade in"
    assert chinese["video_studio.composer.fade_out"] == "音频淡出"
    assert "fadeIn and fadeOut affect audio only" in script
    assert "envelope[:fade_in]" in composer_backend and "envelope[-fade_out:]" in composer_backend
    assert "elapsed < clip.fade_in" not in composer_backend
    assert "remaining < clip.fade_out" not in composer_backend
    assert ".vs-composer-panel-title strong" in stylesheet and "font-size:16px" in stylesheet
    assert ".vs-composer-properties label" in stylesheet and "font-size:11px" in stylesheet
    assert "white-space:nowrap" in stylesheet and "display:inline-flex" in stylesheet
    assert ".vs-composer-properties input:focus" in stylesheet and "outline:2px solid #bfdbfe" in stylesheet
    assert "target.trackId = nextTrackId" in script and "data-track-id" in template
    assert "candidate.kind === originTrack?.kind" in script
    assert "clip-drop-target" in stylesheet and "translateY" in script
    assert "composerMovePlan" in script and "composerTrimPlan" in script
    assert "composerDragUnit" in script and "selected.has(ordered[first - 1].id)" in script
    assert "preserveSelection" in script and "movingClips = null" in script
    assert "composerMovePlan(clip, nextStart, nextTrackId, moving)" in script
    assert "normalizeComposerTimeline" in script and "insertComposerClip" in script
    assert "composerCanGroupSelection" in script and "groupComposerSelection" in template
    assert "data-clip-id" in template and "isComposerClipSelected" in template
    assert "type=\"color\"" in template and "COMPOSER_CLIP_COLORS" in script
    assert "clip.groupId&&'grouped'" in template and ".vs-composer-clip.grouped" in stylesheet
    assert 'class="track-add"' not in template
    assert template.count("addComposerTrack('video')") == 1 and template.count("addComposerTrack('audio')") == 1
    assert "showComposerHoverTip" in script and "vs-composer-hover-tip" in template
    assert 'x-teleport="body"' in template
    assert "Number.isFinite(event.clientX)" in script
    assert "window.frameElement?.getBoundingClientRect?.().left" in script
    assert "transform:translate(-50%,-100%)" in stylesheet
    assert "video_studio.composer.mute_track" in script and "video_studio.composer.lock_track" in template
    assert "composerTrackOutputIcon" in script and "'eye-off' : 'eye'" in script
    assert "composerTrackOutputLabel" in template and "video_studio.composer.hide_track" in script
    assert "track.kind === 'audio' ? !track.muted" in script
    assert "confirm_remove_track" in script and "window.confirm" in script
    assert "selectedIndex + 1" in script and "tracks.splice" in script
    assert "touch-action:none" in stylesheet and "width:18px;height:18px" in stylesheet
    assert "handleComposerKeydown" in script and "addActiveComposerToGallery" in script
    assert "mozAI2AppsFullPath" in script and "resourceHandle" in script
    assert "`${STUDIO_API}/composer/sources/import`" in script
    assert "source = await this.uploadComposerSource(file)" in script
    assert 'get composerGridSeconds()' in script
    assert 'get composerTimelineTicks()' in script
    assert 'get composerClipMinimumWidth()' in script
    assert 'min="2" max="120" step="2"' in template
    assert 'background-size:${composerGridSeconds*composerScale}px 100%' in template
    assert 'second in composerTimelineTicks' in template
    assert "vs-composer-mask-import" in stylesheet
    assert "openComposerDocument" in template and "saveComposerDocumentAs" in template
    assert "/composer/projects/open" in script and "/composer/projects/save" in script
    assert "composerCompatibleSources" in template and "setComposerClipSource" in script
    assert "retimeComposerClip" in script and "sourceSpan / speed" in script
    assert ".vs-composer-clip" in stylesheet and ".vs-composer-stage" in stylesheet
