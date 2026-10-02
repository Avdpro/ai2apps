from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
import pytest

from ai2apps.video.upscaling import inspect_source, split_source, stitch_segments


def test_video_upscaling_builtin_and_acpf_contract():
    from ai2apps.api.video_studio import MINI_APP_BY_ID
    from ai2apps.provisioning.profiles import CapabilityProfileRegistry

    mini = MINI_APP_BY_ID["ai2apps.video.upscaling"]
    assert mini["entry"] == {"kind": "host-adapter", "adapter": "video-upscaling"}
    assert mini["requirements"]["capabilities"] == ["video.upscaling"]
    assert mini["placements"][0]["studio"] == "ai2apps.video-studio"
    profiles = CapabilityProfileRegistry().capability("ai2apps.video-studio", "video.upscaling")
    assert [item["stack"]["checkpoint"]["model_id"] for item in profiles["profiles"]] == [
        "ai2apps.model.sol-refiner-mlx/ltx23-one-step",
        "ai2apps.model.sol-refiner-mlx/ltx23-custom-prompt",
    ]
    root = Path(__file__).resolve().parents[1] / "ai2apps/web"
    template = (root / "templates/system_apps/video_studio.html").read_text()
    script = (root / "static/js/video_studio.js").read_text()
    assert "onUpscalingModelSelect($event.target)" in template
    assert "__install_upscaling_model__" in template
    assert "video.upscaling" in script and "AI2AppsCapabilities.ensure" in script
    assert "selectedUpscalingModel?.customPrompt" in template
    assert "startUpscaling()" in template


def test_upscaling_model_api_requires_owned_video_studio_instance(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ai2apps.api.video_studio import create_video_studio_router
    from ai2apps.studio import upscaling

    class ExtensionManager:
        def require_instance_access(self, instance_id, principal):
            assert instance_id == "appi_video_studio"

        def instance_entry(self, instance_id, *, principal):
            return {"app_key": "ai2apps.video-studio"}

    runtime = SimpleNamespace(extension_manager=ExtensionManager())
    principal = SimpleNamespace(actor_user_id="actor", installation_id="installation")
    model = SimpleNamespace(id="test/upscaler", model_type="video_upscaling",
                            capabilities=("video_upscaling",), metadata={}, display_name="Test",
                            video_upscaling_capabilities={"maximum_frames": 1500, "maximum_seconds": 60,
                                                          "maximum_output_pixels": None,
                                                          "resolution_policy": "resource_limited"})
    monkeypatch.setattr(upscaling, "_models", lambda runtime: (model,))
    monkeypatch.setattr(upscaling, "_model_ready", lambda *a: True)
    app = FastAPI()
    app.include_router(create_video_studio_router(lambda: runtime, lambda: principal))
    client = TestClient(app)
    assert client.get("/video-studio/upscaling/models").status_code == 422
    response = client.get("/video-studio/upscaling/models",
                          headers={"X-AI2Apps-App-Instance": "appi_video_studio"})
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == model.id
    assert response.json()["items"][0]["resolutionPolicy"] == "resource_limited"


def _video(path: Path, count: int, *, width: int = 64, height: int = 64,
           audio: bool = False, audio_delay_samples: int = 0, rate: int = 24):
    with av.open(str(path), "w", format="mp4") as output:
        video = output.add_stream("libx264", rate=rate)
        video.width, video.height, video.pix_fmt = width, height, "yuv420p"
        sound = output.add_stream("aac", rate=24000) if audio else None
        if sound:
            sound.layout = "mono"
        for index in range(count):
            pixels = np.full((height, width, 3), index % 256, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = index
            for packet in video.encode(frame):
                output.mux(packet)
            if sound:
                sample_count = 24000 // rate
                samples = np.zeros((1, sample_count), dtype=np.float32)
                frame = av.AudioFrame.from_ndarray(samples, format="fltp", layout="mono")
                frame.sample_rate, frame.pts = 24000, index * sample_count + audio_delay_samples
                for packet in sound.encode(frame):
                    output.mux(packet)
        for packet in video.encode():
            output.mux(packet)
        if sound:
            for packet in sound.encode():
                output.mux(packet)


def _fake_upscale(source: Path, target: Path):
    with av.open(str(source)) as input_video, av.open(str(target), "w", format="mp4") as output:
        source_stream = input_video.streams.video[0]
        video = output.add_stream("libx264", rate=source_stream.average_rate)
        video.width, video.height, video.pix_fmt = source_stream.width * 2, source_stream.height * 2, "yuv420p"
        for index, frame in enumerate(input_video.decode(source_stream)):
            pixels = frame.to_ndarray(format="rgb24")
            doubled = np.repeat(np.repeat(pixels, 2, axis=0), 2, axis=1)
            next_frame = av.VideoFrame.from_ndarray(doubled, format="rgb24")
            next_frame.pts = index
            for packet in video.encode(next_frame):
                output.mux(packet)
        for packet in video.encode():
            output.mux(packet)


def test_upscaling_outer_segments_preserve_exact_frames_and_audio(tmp_path):
    source = tmp_path / "source.mp4"
    _video(source, 270, audio=True, audio_delay_samples=12000)
    inspected = inspect_source(source, check=lambda: None)
    assert inspected.frames == 270
    assert inspected.has_audio
    info = split_source(source, tmp_path / "parts", check=lambda: None)
    assert [(segment.start, segment.frames) for segment in info.segments] == [(0, 240), (223, 47)]
    outputs = []
    for index, segment in enumerate(info.segments):
        output = tmp_path / f"upscaled-{index}.mp4"
        _fake_upscale(segment.path, output)
        outputs.append(output)
    destination = tmp_path / "result.mp4"
    stitch_segments(source, outputs, info, destination, check=lambda: None)
    with av.open(str(destination)) as result:
        assert len(list(result.decode(result.streams.video[0]))) == 270
        assert (result.streams.video[0].width, result.streams.video[0].height) == (128, 128)
        assert len(result.streams.audio) == 1
        output_audio_start = result.streams.audio[0].start_time * result.streams.audio[0].time_base
    with av.open(str(source)) as original:
        original_audio_start = original.streams.audio[0].start_time * original.streams.audio[0].time_base
        original_video_start = original.streams.video[0].start_time * original.streams.video[0].time_base
    assert abs(float(output_audio_start - (original_audio_start - original_video_start))) < 0.05


def test_upscaling_rejects_variable_frame_rate_and_oversized_input(tmp_path):
    source = tmp_path / "source.mp4"
    _video(source, 4)
    assert inspect_source(source, check=lambda: None).frames == 4
    oversized = tmp_path / "oversized.mp4"
    _video(oversized, 2, width=514)
    with pytest.raises(ValueError, match="512 pixels"):
        inspect_source(oversized, check=lambda: None)
    resource_limited = {"resolution_policy": "resource_limited", "maximum_output_pixels": None}
    assert inspect_source(oversized, check=lambda: None,
                          capabilities=resource_limited).width == 514
    assert split_source(oversized, tmp_path / "wide-parts", check=lambda: None,
                        capabilities=resource_limited).frames == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("frames,expected_calls,segmented", [(12, 1, True), (270, 2, True), (270, 0, False)])
async def test_upscaling_background_run_publishes_only_host_artifact(tmp_path, monkeypatch, frames, expected_calls, segmented):
    from ai2apps.storage import PlatformDatabase
    from ai2apps.studio import upscaling

    database = PlatformDatabase(tmp_path / "db.sqlite")
    database.initialize()
    source = tmp_path / "source.mp4"
    _video(source, frames, audio=frames > 12, rate=4 if frames > 12 else 24)
    model = SimpleNamespace(id="test/upscaler", model_type="video_upscaling",
                            capabilities=("video_upscaling",), metadata={"prompt_mode": "fixed_default"},
                            video_upscaling_capabilities={"resolution_policy": "resource_limited",
                                                          "maximum_output_pixels": None, "segmented": segmented})
    monkeypatch.setattr(upscaling, "_models", lambda runtime: (model,))
    calls = []

    async def invoke(model_id, operation, payload, target, *, files, **kwargs):
        calls.append((model_id, operation, payload))
        _fake_upscale(files["video"][1], target)

    def import_artifact(session_id, path, name, **kwargs):
        assert path.is_file() and name == "upscaled.mp4"
        with av.open(str(path)) as output:
            assert len(list(output.decode(output.streams.video[0]))) == frames
            assert len(output.streams.audio) == (1 if frames > 12 else 0)
        return SimpleNamespace(id="artifact", name=name)

    runtime = SimpleNamespace(database=database,
                              config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)),
                              model_invocations=SimpleNamespace(invoke_background_to_file=invoke),
                              video_tasks=SimpleNamespace(artifact_session=lambda: "session"),
                              workspace=SimpleNamespace(import_artifact=import_artifact))
    monkeypatch.setattr(upscaling, "_model_ready", lambda *a: True)
    principal = SimpleNamespace(actor_user_id="actor", installation_id="installation",
                                organization_id="org", billing_account_id="bill", membership_epoch=1,
                                authentication_type="local")
    scope = dict(actor_id="actor", installation_id="installation", app_instance_id="instance",
                 studio_id=upscaling.STUDIO_ID)
    job = await upscaling.start_builtin_job(runtime, scope, principal,
                                            content=source.read_bytes(), filename="source.mp4",
                                            media_type="video/mp4", model_id=model.id, seed=0, prompt="")
    manager = runtime._video_upscaling_jobs
    await manager.active[job["id"]].task
    run = manager.repository.get_run(job["id"], **scope)
    if not segmented:
        assert run["status"] == "failed" and calls == []
        assert "不会自动拆段" in str(run["error"])
        return
    assert run["status"] == "succeeded" and len(run["artifacts"]) == 1, run["error"]
    assert run["artifacts"][0]["previewUrl"].endswith("/artifact/download")
    assert calls == [(model.id, "video_upscaling", {"parameters": {"scale": 2, "seed": 0}})] * expected_calls
