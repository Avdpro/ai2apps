"""Input bounds and protocol retention for native MLX video."""

import base64
import pytest
from omlx.exceptions import InvalidRequestError
from omlx.utils.video import load_inline_video, extract_video_from_messages
from ai2apps.model_worker.omlx_chat import _responses_messages


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"url": "https://example.org/v.mp4"},
        {"url": "file:///tmp/a.mp4"},
        {"url": "data:video/mp4;base64,!"},
    ],
)
def test_rejects_external_and_malformed_video(value):
    with pytest.raises(InvalidRequestError):
        load_inline_video(value)


@pytest.mark.parametrize(
    "options",
    [
        {"fps": float("nan")},
        {"fps": True},
        {"max_frames": 129},
        {"max_frames": 3},
        {"max_frames": 33},
        {"max_edge": 4096},
    ],
)
def test_bounds_before_decoder(options):
    with pytest.raises(InvalidRequestError):
        load_inline_video({"url": "data:video/mp4;base64,eA==", **options})


def test_only_one_user_video():
    part = {"type": "video_url", "video_url": {}}
    for messages in (
        [{"role": "assistant", "content": [part]}],
        [{"role": "user", "content": [part, part]}],
    ):
        with pytest.raises(InvalidRequestError):
            extract_video_from_messages(messages)
    assert extract_video_from_messages([{"role": "user", "content": "hello"}]) is None


def test_responses_preserves_video_options():
    video = {"url": "data:video/mp4;base64,eA==", "max_frames": 32}
    result = _responses_messages(
        [{"role": "user", "content": [{"type": "video_url", "video_url": video}]}], None
    )
    assert result[0]["content"][0]["video_url"] == video


def test_real_decoder_bounds_and_timestamps(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    source = tmp_path / "input.avi"
    writer = cv2.VideoWriter(
        str(source), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 240)
    )
    for n in range(20):
        writer.write(np.full((240, 320, 3), n * 10, dtype=np.uint8))
    writer.release()
    uri = "data:video/avi;base64," + base64.b64encode(source.read_bytes()).decode()
    result = load_inline_video({"url": uri, "max_frames": 4, "max_edge": 128})
    assert result.frames.shape == (4, 3, 96, 128)
    assert result.timestamps == [0, 0.6, 1.3, 1.9]
    assert result.duration == 2
    assert (
        result.digest
        == load_inline_video({"url": uri, "max_frames": 4, "max_edge": 128}).digest
    )
    assert (
        result.digest
        != load_inline_video(
            {"url": uri, "fps": 4, "max_frames": 6, "max_edge": 128}
        ).digest
    )


def test_engine_keeps_native_video_and_temporal_groups(monkeypatch):
    import numpy as np
    import mlx.core as mx
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from omlx.engine.vlm import VLMBatchedEngine
    from omlx.utils.video import VideoInput

    engine = VLMBatchedEngine("fixture-video")
    engine._vlm_model = MagicMock()
    engine._vlm_model.config.model_type = "qwen3_5"
    engine._vlm_model.language_model = None
    engine._vlm_model.get_input_embeddings.return_value = SimpleNamespace(
        inputs_embeds=mx.zeros((1, 4, 8))
    )
    engine._processor = MagicMock()
    engine._processor.apply_chat_template.return_value = "rendered video prompt"
    video = VideoInput(
        np.zeros((4, 3, 64, 64), dtype=np.uint8),
        [0.0, 1.0, 2.0, 3.0],
        1.0,
        4.0,
        "video-digest",
    )
    prepare = MagicMock(
        return_value={
            "input_ids": mx.array([[1, 2, 3, 4]]),
            "pixel_values_videos": mx.zeros((8, 8)),
            "video_grid_thw": mx.array([[1, 4, 4], [1, 4, 4]]),
        }
    )
    monkeypatch.setattr("mlx_vlm.utils.prepare_inputs", prepare)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video_url", "video_url": {}},
                {"type": "text", "text": "describe"},
            ],
        }
    ]
    result = engine._prepare_vision_inputs(messages, [], video=video)
    assert result[1] is not None and result[3] == "video-digest"
    assert result[5] == []
    assert len(prepare.call_args.kwargs["videos"]) == 2
    assert all(v.shape == (2, 3, 64, 64) for v in prepare.call_args.kwargs["videos"])
    formatted = engine._processor.apply_chat_template.call_args.args[0][0]["content"]
    assert [p["text"] for p in formatted if p.get("type") == "text"][:2] == [
        "<0.500 seconds>",
        "<2.500 seconds>",
    ]
    call = engine._vlm_model.get_input_embeddings.call_args.kwargs
    assert "video_grid_thw" in call and "pixel_values_videos" in call
    assert "cached_image_features" not in call


def test_openai_schema_keeps_video():
    from omlx.api.openai_models import ContentPart
    from omlx.api.utils import _extract_multimodal_content_list

    options = {"url": "data:video/mp4;base64,eA==", "max_frames": 32}
    part = ContentPart(type="video_url", video_url=options)
    assert _extract_multimodal_content_list([part]) == [
        {"type": "video_url", "video_url": options}
    ]


def test_runtime_export_keeps_video_decoder(tmp_path):
    import importlib.util
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "packaging/build.py"
    spec = importlib.util.spec_from_file_location("video_runtime_builder", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    site = tmp_path / "framework-mlx-base/lib/python3.11/site-packages"
    for name in [
        "cv2",
        "opencv_python-5.0.dist-info",
        "torch",
        "torch-2.0.dist-info",
        "pandas",
    ]:
        folder = site / name
        folder.mkdir(parents=True)
        (folder / "payload").write_bytes(b"fixture")
    module._strip_unused_packages(tmp_path)
    assert (site / "cv2/payload").is_file()
    assert (site / "opencv_python-5.0.dist-info/payload").is_file()
    assert not (site / "torch").exists() and not (site / "pandas").exists()
