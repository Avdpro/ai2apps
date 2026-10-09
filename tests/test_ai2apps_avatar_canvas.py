from types import SimpleNamespace

import av
import numpy as np
import pytest
from PIL import Image
from test_ai2apps_video_tasks import _manager

from ai2apps.avatar.composition import prepare_portrait
from ai2apps.avatar.video_composition import compose_video
from ai2apps.video.tasks import VideoGenerationError, VideoTaskManager


def video(path, size=(64, 64), frames=5):
    with av.open(str(path), "w") as out:
        stream = out.add_stream("libx264", rate=25)
        stream.width, stream.height = size
        stream.pix_fmt = "yuv420p"
        audio = out.add_stream("aac", rate=16000)
        audio.layout = "mono"
        for _ in range(frames):
            frame = av.VideoFrame.from_ndarray(
                np.full((size[1], size[0], 3), 180, np.uint8), format="rgb24"
            )
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
        af = av.AudioFrame.from_ndarray(
            np.zeros((1, frames * 640), np.float32), format="fltp", layout="mono"
        )
        af.sample_rate = 16000
        for packet in audio.encode(af):
            out.mux(packet)
        for packet in audio.encode():
            out.mux(packet)


def test_crop_coordinates_and_odd_canvas(tmp_path):
    src = np.full((181, 321, 3), 20, np.uint8)
    src[95:130, 250:280] = 180
    path = tmp_path / "input.png"
    Image.fromarray(src).save(path)
    canvas = prepare_portrait(
        path,
        tmp_path / "crop.png",
        (64, 64),
        detector=lambda _: [(250, 95, 30, 35)],
        crop_scale=2,
    )
    restored = canvas.compose(np.array(Image.open(tmp_path / "crop.png")))
    assert restored.shape == src.shape
    np.testing.assert_array_equal(restored[:50], src[:50])
    assert restored[110, 265, 0] > 150
    movie = tmp_path / "model.mp4"
    video(movie)
    result = compose_video(movie, tmp_path / "result.mp4", canvas)
    with av.open(str(result)) as container:
        stream = container.streams.video[0]
        assert (stream.width, stream.height) == (322, 182)
        assert stream.codec_context.pix_fmt == "yuv420p"
        assert stream.codec_context.profile != "High 4:4:4 Predictive"
        assert len(container.streams.audio) == 1
        assert len(list(container.decode(video=0))) == 5


def test_missing_face_and_cancel_cleanup(tmp_path):
    path = tmp_path / "input.png"
    Image.new("RGB", (200, 120)).save(path)
    with pytest.raises(ValueError, match="No face"):
        prepare_portrait(path, tmp_path / "crop.png", (64, 64), detector=lambda _: [])
    canvas = prepare_portrait(
        path, tmp_path / "crop.png", (64, 64), detector=lambda _: [(20, 20, 30, 30)]
    )
    movie = tmp_path / "model.mp4"
    video(movie)
    destination = tmp_path / "result.mp4"
    destination.write_bytes(b"existing")
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if calls > 2:
            raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        compose_video(movie, destination, canvas, check=check)
    assert destination.read_bytes() == b"existing"
    assert not destination.with_suffix(".partial.mp4").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_id",
    [
        "ai2apps.model.flashhead-mlx/lite",
        "ai2apps.model.flashhead-mlx/pro",
        "ai2apps.model.echomimic-v3-mlx/default",
        "ai2apps.model.avtr1-mlx/default",
    ],
)
async def test_shared_task_path_for_all_avatar_providers(
    tmp_path, monkeypatch, model_id
):
    from ai2apps.avatar import face_detection

    monkeypatch.setattr(face_detection, "detect_faces", lambda _: [(130, 40, 30, 35)])
    seen = []

    async def invoke(model, operation, payload, output, **kwargs):
        assert model == model_id
        assert "avatar_output_mode" not in payload
        with Image.open(kwargs["files"]["reference_00_image"][1]) as image:
            assert image.size == (64, 64)
            assert image.mode == "RGB"
        seen.append(payload)
        video(output)

    manager = _manager(
        tmp_path, gateway=SimpleNamespace(invoke_background_to_file=invoke)
    )
    task = "canvas-test"
    folder = manager.root / task
    folder.mkdir(parents=True)
    Image.new("RGB", (200, 120), (20, 30, 40)).save(folder / "portrait.png")
    (folder / "audio.wav").write_bytes(b"opaque gateway fixture")
    manifest = [
        {"part_name": name, "filename": filename, "path": filename, "media_type": mime}
        for name, filename, mime in [
            ("reference_00_image", "portrait.png", "image/png"),
            ("audio", "audio.wav", "audio/wav"),
        ]
    ]
    body = {
        "avatar_output_mode": "source",
        "width": 64,
        "height": 64,
        "reference_parts": [{"kind": "image", "part_name": "reference_00_image"}],
    }
    output = await VideoTaskManager._invoke(
        manager, task, SimpleNamespace(id=model_id), body, manifest
    )
    assert seen and output.name == "source-result.mp4"
    with av.open(str(output)) as container:
        assert (
            container.streams.video[0].width,
            container.streams.video[0].height,
        ) == (200, 120)
        assert len(container.streams.audio) == 1
    assert body["avatar_output_mode"] == "source"  # frozen retry input is unchanged


def test_avatar_mode_rejected_for_unrelated_model(tmp_path):
    manager = _manager(tmp_path)
    model = manager._model("example/video")
    with pytest.raises(VideoGenerationError, match="avatar_output_mode"):
        manager._effective_request(
            {
                "content": [{"type": "text", "role": "prompt", "text": "test"}],
                "avatar_output_mode": "source",
            },
            model,
        )
