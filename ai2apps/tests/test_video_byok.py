"""Video API models use actor-scoped keys and vendor-specific request shapes."""

from types import SimpleNamespace

import httpx
import pytest

from ai2apps.secrets import MemorySecretBackend
from ai2apps.video.byok import (
    _minimax_media_content,
    _request_body,
    catalog,
    catalog_model,
    clear_credential,
    configured,
    credential,
    generate,
    provider_for_model,
    set_credential,
)
from ai2apps.video.tasks import VideoGenerationError, VideoTaskManager
from ai2apps.video_policy import effective_video_capabilities


@pytest.fixture
def runtime():
    return SimpleNamespace(model_manager=SimpleNamespace(secret_backend=MemorySecretBackend()))


def test_video_byok_keys_are_actor_scoped_and_never_in_catalog(runtime):
    set_credential(runtime, "minimax", "actor-one", "secret-one")
    assert configured(runtime, "minimax", "actor-one")
    assert not configured(runtime, "minimax", "actor-two")
    assert not configured(runtime, "volcengine", "actor-one")
    assert credential(runtime, "minimax", "actor-one") == "secret-one"
    model = catalog_model(runtime, "minimax", "actor-one")
    assert model.checkpoint_ready
    assert "secret-one" not in repr(model)
    with pytest.raises(VideoGenerationError, match="Configure"):
        credential(runtime, "minimax", "actor-two")
    clear_credential(runtime, "minimax", "actor-one")
    assert not configured(runtime, "minimax", "actor-one")


def test_seedance_variants_share_the_provider_key_but_keep_distinct_model_ids(runtime):
    set_credential(runtime, "volcengine", "actor-one", "secret-one")
    variants = [model for model in catalog(runtime, "actor-one") if model.provider_key == "volcengine"]
    assert [(model.upstream_id, model.checkpoint_ready) for model in variants] == [
        ("doubao-seedance-2-5-260628", True),
        ("doubao-seedance-2-5-flash-261115", True),
    ]
    assert all(provider_for_model(model.id) == "volcengine" for model in variants)
    assert all(not model.checkpoint_ready for model in catalog(runtime, "actor-two")
               if model.provider_key == "volcengine")
    manager = object.__new__(VideoTaskManager)
    manager.runtime = runtime
    assert manager._model(variants[1].id, "ai2apps-user:actor-one").upstream_id == variants[1].upstream_id
    with pytest.raises(VideoGenerationError, match="Configure"):
        manager._model(variants[1].id, "actor-two")


def test_minimax_official_variants_and_modes(runtime):
    variants = [model for model in catalog(runtime, "actor") if model.provider_key == "minimax"]
    assert [model.upstream_id for model in variants] == [
        "MiniMax-H3", "MiniMax-H3-Highspeed", "MiniMax-H3-Lite", "MiniMax-H3-Max"]
    assert all({"text_to_video", "image_to_video", "reference_to_video"} <= set(model.capabilities)
               for model in variants)
    assert "2048x1152" in variants[0].video_capabilities["geometry"]["resolutions"]
    assert all("2048x1152" not in model.video_capabilities["geometry"]["resolutions"]
               for model in variants[1:])
    assert variants[-1].video_capabilities["duration"]["minimum_seconds"] == 5
    for model in variants:
        payload = {"content": [{"type": "text", "role": "prompt", "text": "Bird"},
                               {"type": "image_url", "role": "first_frame", "image_url": {"url": "https://example.com/a.png"}}],
                   "resolution": model.video_capabilities["defaults"]["resolution"],
                   "ratio": "16:9", "duration": 5, "preset": "standard"}
        assert VideoTaskManager._effective_request(payload, model)["duration"] == 5
        payload["content"][1]["role"] = "reference_image"
        assert VideoTaskManager._effective_request(payload, model)["duration"] == 5


def test_minimax_private_media_is_encoded_and_tier_is_model_specific(runtime, tmp_path):
    root = tmp_path / "task"
    (root / "inputs").mkdir(parents=True)
    data = b"sample image bytes"
    (root / "inputs" / "frame.png").write_bytes(data)
    import hashlib
    import base64
    manifest = [{"part_name": "first_frame", "path": "inputs/frame.png", "media_type": "image/png",
                 "sha256": hashlib.sha256(data).hexdigest()}]
    media = _minimax_media_content({}, manifest, root)
    assert media == [{"type": "image_url", "role": "first_frame",
                      "image_url": {"url": "data:image/png;base64," + base64.b64encode(data).decode()}}]
    model = catalog_model(runtime, "minimax", "actor")
    body = _request_body("minimax", model, {"prompt": "Bird", "duration": 5,
                                           "ratio": "16:9", "resolution": "2048x1152"}, media)
    assert body["resolution"] == "2K"
    assert body["ratio"] == "adaptive"
    fast = catalog_model(runtime, "minimax", "actor", "byok/minimax/MiniMax-H3-Highspeed")
    with pytest.raises(ValueError, match="not supported"):
        _request_body("minimax", fast, {"prompt": "Bird", "duration": 5,
                                        "ratio": "16:9", "resolution": "2048x1152"})
    (root / "inputs" / "frame.png").write_bytes(b"changed")
    with pytest.raises(VideoGenerationError, match="changed"):
        _minimax_media_content({}, manifest, root)


def test_seedance_frame_sizes_follow_each_models_supported_tiers(runtime):
    standard = catalog_model(runtime, "volcengine", "actor")
    flash = catalog_model(runtime, "volcengine", "actor",
                          "byok/volcengine/doubao-seedance-2-5-flash-261115")
    from ai2apps.video.byok import SEEDANCE_GEOMETRY
    assert set(standard.video_capabilities["geometry"]["resolutions"]) == {
        value for ratios in SEEDANCE_GEOMETRY.values() for value in ratios.values()}
    assert set(flash.video_capabilities["geometry"]["resolutions"]) == {
        value for tier in ('480p', '720p') for value in SEEDANCE_GEOMETRY[tier].values()}
    with pytest.raises(ValueError, match="resolution"):
        _request_body('volcengine', flash, {'prompt':'x','duration':5,'resolution':'1920x1080','ratio':'16:9'})


def test_seedance_modes_and_private_media_mapping(runtime, tmp_path):
    import hashlib
    import base64

    root = tmp_path / "task"
    (root / "inputs").mkdir(parents=True)
    image = b"image bytes"
    audio = b"audio bytes"
    video = b"video bytes"
    for name, data in (("frame.png", image), ("voice.wav", audio), ("clip.mp4", video)):
        (root / "inputs" / name).write_bytes(data)
    model = catalog_model(runtime, "volcengine", "actor")
    assert {"image_to_video", "reference_to_video"} <= set(model.capabilities)
    frame = [{"part_name": "first_frame", "path": "inputs/frame.png", "media_type": "image/png",
              "sha256": hashlib.sha256(image).hexdigest()}]
    media = _minimax_media_content({}, frame, root, "volcengine")
    assert media[0]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(image).decode()
    body = _request_body("volcengine", model, {"prompt": "Bird", "duration": 5,
                                                "ratio": "16:9", "resolution": "1280x720"}, media)
    assert body["ratio"] == "adaptive"
    assert body["content"][1]["role"] == "first_frame"
    with pytest.raises(ValueError, match="first frame"):
        _request_body("volcengine", model, {"prompt": "Bird", "duration": 5,
                                             "ratio": "16:9", "resolution": "1280x720"},
                      [{**media[0], "role": "last_frame"}])
    refs = [{"part_name": "reference_00_audio", "path": "inputs/voice.wav", "media_type": "audio/wav",
             "sha256": hashlib.sha256(audio).hexdigest()},
            {"part_name": "reference_01_video", "path": "inputs/clip.mp4", "media_type": "video/mp4",
             "sha256": hashlib.sha256(video).hexdigest(), "source_url": "https://media.example/clip.mp4"}]
    media = _minimax_media_content({"reference_parts": [
        {"part_name": "reference_00_audio", "kind": "audio"},
        {"part_name": "reference_01_video", "kind": "video"}]}, refs, root, "volcengine")
    assert media[0]["audio_url"]["url"].startswith("data:audio/wav;base64,")
    assert media[1]["video_url"]["url"] == "https://media.example/clip.mp4"
    body = _request_body("volcengine", model, {"prompt": "Bird", "duration": 5,
                                                "ratio": "16:9", "resolution": "1280x720"}, media)
    assert body["omni_reference_task_type"] == "reference"
    edit = _request_body("volcengine", model, {"prompt": "Remove the sign", "duration": 5,
                                              "ratio": "16:9", "resolution": "1280x720",
                                              "omni_reference_task_type": "edit"}, media)
    assert edit["ratio"] == "adaptive" and edit["duration"] == -1
    assert edit["omni_reference_task_type"] == "edit"
    extend = _request_body("volcengine", model, {"prompt": "Continue", "duration": 8,
                                                "ratio": "16:9", "resolution": "1280x720",
                                                "omni_reference_task_type": "extend"}, media)
    assert extend["ratio"] == "adaptive" and extend["duration"] == 8
    with pytest.raises(ValueError, match="reference video"):
        _request_body("volcengine", model, {"prompt": "Bird", "duration": 5,
                                             "ratio": "16:9", "resolution": "1280x720",
                                             "omni_reference_task_type": "edit"}, media[:1])
    del refs[1]["source_url"]
    local = _minimax_media_content({"reference_parts": [{"part_name": "reference_01_video", "kind": "video"}]},
                                   refs[1:], root, "volcengine")
    assert local[0]["video_url"]["url"] == "local-video://reference_01_video"


def test_video_queue_requires_the_owner_key(runtime):
    manager = object.__new__(VideoTaskManager)
    manager.runtime = runtime
    model_id = "byok/minimax/MiniMax-H3"
    with pytest.raises(VideoGenerationError, match="Configure"):
        manager._model(model_id, "actor-two")
    set_credential(runtime, "minimax", "actor-one", "secret-one")
    assert manager._model(model_id, "ai2apps-user:actor-one").id == model_id
    with pytest.raises(VideoGenerationError, match="Configure"):
        manager._model(model_id, "actor-two")


@pytest.mark.parametrize("provider", ["minimax", "volcengine"])
def test_video_queue_accepts_declared_video_inputs(runtime, provider):
    model = catalog_model(runtime, provider, "actor")
    resolution = model.video_capabilities["defaults"]["resolution"]
    payload = {"content": [{"type": "text", "role": "prompt", "text": "Bird"}],
               "resolution": resolution, "ratio": "16:9", "duration": 5, "preset": "standard"}
    effective = VideoTaskManager._effective_request(payload, model)
    assert effective["duration"] == 5
    assert effective["resolution"] == resolution
    assert VideoTaskManager._effective_request({**payload, "content": [
            *payload["content"], {"type": "image_url", "role": "first_frame", "image_url": {"url": "https://example.com/a.png"}},
        ]}, model)["duration"] == 5
    with pytest.raises(VideoGenerationError, match="combination"):
        VideoTaskManager._effective_request({**payload, "content": [
            *payload["content"], {"type": "image_url", "role": "first_frame", "image_url": {"url": "https://example.com/a.png"}},
            {"type": "image_url", "role": "reference_image", "image_url": {"url": "https://example.com/b.png"}},
        ]}, model)


@pytest.mark.parametrize("provider,upstream,resolution", [
    ("minimax", "MiniMax-H3", "768P"),
    ("volcengine", "doubao-seedance-2-5-260628", "720p"),
    ("volcengine", "doubao-seedance-2-5-flash-261115", "720p"),
])
def test_video_byok_requests_only_include_supported_vendor_fields(runtime, provider, upstream, resolution):
    model = catalog_model(runtime, provider, "actor", f"byok/{provider}/{upstream}")
    request = {"prompt": "A blue bird flies", "duration": 5, "ratio": "16:9",
               "seed": 42, "steps": 20, "fast": False, "metadata": {"label": "Bird"}}
    body = _request_body(provider, model, request)
    assert body == {"model": upstream, "content": [{"type": "text", "text": "A blue bird flies"}],
                    "duration": 5, "resolution": resolution, "ratio": "16:9", "generate_audio": True}
    assert effective_video_capabilities(model)["geometry"]["resolutions"] == list(
        model.video_capabilities["geometry"]["resolutions"]
    )
    with pytest.raises(ValueError, match="whole number"):
        _request_body(provider, model, {**request, "duration": 5.5})


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,create_path,query_path", [
    ("minimax", "/v2/video_generation", "/v2/query/video_generation/remote-1"),
    ("volcengine", "/api/v3/contents/generations/tasks", "/api/v3/contents/generations/tasks/remote-1"),
])
async def test_direct_video_api_submits_polls_and_downloads(
    runtime, monkeypatch, tmp_path, provider, create_path, query_path,
):
    set_credential(runtime, provider, "actor", "private-token")
    model = catalog_model(runtime, provider, "actor")
    observed = []

    def handle(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        if request.method == "POST":
            assert request.url.path == create_path
            assert request.headers["Authorization"] == "Bearer private-token"
            return httpx.Response(200, json={"task_id": "remote-1"} if provider == "minimax" else {"id": "remote-1"})
        if request.url.path == query_path:
            content = {"url": "https://media.example/result.mp4"} if provider == "minimax" else {"video_url": "https://media.example/result.mp4"}
            task = {"status": "succeeded", "content": content}
            return httpx.Response(200, json={"task": task} if provider == "minimax" else task)
        assert request.url.host == "media.example"
        return httpx.Response(200, content=b"video bytes")

    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handle), **kwargs,
    ))
    async def no_wait(_seconds):
        return None
    monkeypatch.setattr("ai2apps.video.byok.asyncio.sleep", no_wait)
    monkeypatch.setattr("ai2apps.video.tasks._public_address", lambda *_args: None)
    output = tmp_path / "result.mp4"
    progress = []
    await generate(runtime, model, {"prompt": "Bird", "duration": 5, "ratio": "16:9"}, output,
                   actor_id="actor", cancelled=lambda: False, progress=progress.append)
    assert output.read_bytes() == b"video bytes"
    assert [item["phase"] for item in progress] == ["provider_generate", "download"]
    assert [request.method for request in observed] == ["POST", "GET", "GET"]
