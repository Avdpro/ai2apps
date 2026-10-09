from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
import pytest
from PIL import Image

from ai2apps.config import PlatformConfig
from ai2apps.events import EventNotificationBus, EventStore
from ai2apps.storage import PlatformDatabase
from ai2apps.video import VideoGenerationError, VideoTaskManager
from ai2apps.video_policy import (
    H3_PADDED_RESOLUTIONS,
    H3_RATIOS,
    H3_RESOLUTIONS,
    effective_video_capabilities,
    is_temporarily_disabled_video_model,
)
from ai2apps.workspace import WorkspaceRepository


def _manager(tmp_path: Path, *, gateway=None):
    config = PlatformConfig.from_base_path(tmp_path)
    assert config.paths is not None
    database = PlatformDatabase(config.paths.database_path)
    database.initialize()
    events = EventStore(database, EventNotificationBus())
    workspace = WorkspaceRepository(database, events, config.paths)
    model = SimpleNamespace(
        id="example/video",
        upstream_id="example-upstream",
        model_type="video_generation",
        checkpoint_ready=True,
        weights={"revision": "a" * 40},
        video_capabilities={
            "content_combinations": [
                {
                    "required": [
                        {"type": "text", "role": "prompt", "min": 1, "max": 1}
                    ],
                    "optional": [],
                }
            ],
            "geometry": {
                "resolutions": ["512x512"],
                "ratios": ["1:1"],
                "framespersecond": [25],
            },
            "presets": [{"id": "fast"}],
            "defaults": {
                "resolution": "512x512",
                "ratio": "1:1",
                "framespersecond": 25,
                "preset": "fast",
                "seed": 7,
                "output_format": "mp4",
                "audio_output_mode": "generated",
            }
        },
        service_key="example.service",
        endpoints={"video_generation": "/v1/videos/generations"},
        endpoint="http://127.0.0.1:1",
        internal_headers={},
    )

    class Manager(VideoTaskManager):
        def _model(self, model_id):
            if model_id != model.id:
                raise VideoGenerationError("model_not_found", "missing", status_code=404)
            return model

        async def _invoke(self, task_id, _model, _request, _manifest):
            if gateway is not None:
                return await super()._invoke(task_id, _model, _request, _manifest)
            output = self.root / task_id / "result.mp4"
            output.write_bytes(b"fake-video")
            return output

    return Manager(
        runtime=SimpleNamespace(model_invocations=gateway),
        database=database,
        workspace=workspace,
        root=config.paths.base_path / "video-tasks",
    )


def test_h3_bf16_is_temporarily_disabled():
    model = SimpleNamespace(
        id="ai2apps.model.minimax-h3/fl2va-bf16",
        metadata={"family": "minimax-h3", "precision": "bf16"},
    )
    assert is_temporarily_disabled_video_model(model) is True
    model.id = "ai2apps.model.minimax-h3/fl2va-8bit"
    model.metadata["precision"] = "q8"
    assert is_temporarily_disabled_video_model(model) is False


def test_h3_effective_capabilities_expose_safe_native_resolutions():
    model = SimpleNamespace(
        id="ai2apps.model.minimax-h3/fl2va-8bit",
        metadata={
            "family": "minimax-h3",
            "precision": "q8",
            "recommended_steps": 8,
        },
        video_capabilities={
            "geometry": {"resolutions": ["512x512"], "ratios": ["1:1"]},
            "defaults": {"resolution": "512x512"},
        },
    )

    capabilities = effective_video_capabilities(model)

    assert capabilities["geometry"]["resolutions"] == list(H3_RESOLUTIONS)
    assert capabilities["geometry"]["ratios"] == list(H3_RATIOS)
    assert capabilities["defaults"]["resolution"] == "512x512"
    assert capabilities["defaults"]["steps"] == 8
    assert {"1024x576", "576x1024", "1280x720", "720x1280"}.issubset(H3_RESOLUTIONS)
    assert H3_PADDED_RESOLUTIONS == {
        "1280x720": (1280, 736), "720x1280": (736, 1280),
    }


@pytest.mark.parametrize("resolution,ratio", [
    ("1024x576", "16:9"), ("576x1024", "9:16"),
    ("1280x720", "16:9"), ("720x1280", "9:16"),
])
def test_h3_new_resolutions_pass_host_request_validation(tmp_path, resolution, ratio):
    manager = _manager(tmp_path)
    model = manager._model("example/video")
    model.id = "ai2apps.model.minimax-h3/fl2va-4bit"
    model.metadata = {"family": "minimax-h3"}
    effective = manager._effective_request({
        "resolution": resolution, "ratio": ratio,
        "content": [{"type": "text", "role": "prompt", "text": "landscape"}],
    }, model)
    assert effective["resolution"] == resolution
    assert (effective["width"], effective["height"]) == tuple(map(int, resolution.split("x")))


@pytest.mark.asyncio
@pytest.mark.parametrize("resolution,expected_padded", [
    ("1280x720", (1280, 736)), ("720x1280", (736, 1280)),
])
async def test_h3_720p_uses_aligned_worker_canvas_and_crops_result(
    tmp_path, monkeypatch, resolution, expected_padded,
):
    from ai2apps.video import geometry

    calls = {}

    class Gateway:
        async def invoke_background_to_file(self, _model_id, _operation, body, target, **options):
            calls["body"] = body
            options["on_admitted"]()
            target.write_bytes(b"padded")

    def crop(source, destination, *, width, height, check):
        check()
        calls["crop"] = (width, height)
        assert source.read_bytes() == b"padded"
        destination.write_bytes(b"cropped")
        return destination

    monkeypatch.setattr(geometry, "crop_video_canvas", crop)
    manager = object.__new__(VideoTaskManager)
    manager.root = tmp_path
    manager.runtime = SimpleNamespace(model_invocations=Gateway())
    manager._row = lambda _task_id: {"cancel_requested_at": None, "invocation_actor_id": "actor"}
    manager._update = lambda *_args, **_kwargs: None
    (tmp_path / "run").mkdir()
    model = SimpleNamespace(id="ai2apps.model.minimax-h3/openvdn-dmd8-4bit",
                            metadata={"family": "minimax-h3-openvdn"})
    width, height = (int(value) for value in resolution.split("x"))
    output = await manager._invoke("run", model, {
        "resolution": resolution, "width": width, "height": height,
    }, [])
    assert (calls["body"]["width"], calls["body"]["height"]) == expected_padded
    assert calls["crop"] == (width, height)
    assert output.read_bytes() == b"cropped"


def test_crop_video_canvas_preserves_frame_count_and_audio(tmp_path):
    from ai2apps.video.geometry import crop_video_canvas

    source, destination = tmp_path / "padded.mp4", tmp_path / "cropped.mp4"
    with av.open(str(source), "w", format="mp4") as container:
        video = container.add_stream("libx264", rate=24)
        video.width, video.height, video.pix_fmt = 128, 96, "yuv420p"
        audio = container.add_stream("aac", rate=24000)
        audio.layout = "mono"
        for index in range(3):
            pixels = np.zeros((96, 128, 3), dtype=np.uint8)
            pixels[16:80, :, 0] = 90 + index
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = index
            for packet in video.encode(frame):
                container.mux(packet)
            sound = av.AudioFrame.from_ndarray(np.zeros((1, 1000), dtype=np.float32),
                                               format="fltp", layout="mono")
            sound.sample_rate, sound.pts = 24000, index * 1000
            for packet in audio.encode(sound):
                container.mux(packet)
        for packet in video.encode():
            container.mux(packet)
        for packet in audio.encode():
            container.mux(packet)
    crop_video_canvas(source, destination, width=128, height=64, check=lambda: None)
    with av.open(str(destination)) as result:
        assert (result.streams.video[0].width, result.streams.video[0].height) == (128, 64)
        frames = list(result.decode(result.streams.video[0]))
        assert len(frames) == 3
        assert frames[0].to_ndarray(format="rgb24")[:, :, 0].mean() > 80
        assert len(result.streams.audio) == 1


def test_effective_capabilities_ignore_invalid_recommended_steps():
    model = SimpleNamespace(
        id="example/video",
        metadata={"recommended_steps": 0},
        video_capabilities={"defaults": {"steps": 24}},
    )

    assert effective_video_capabilities(model)["defaults"]["steps"] == 24


def test_effective_capabilities_default_to_twenty_steps():
    model = SimpleNamespace(
        id="ai2apps.model.minimax-h3/fl2va-8bit",
        metadata={"family": "minimax-h3"},
        video_capabilities={"defaults": {"resolution": "512x512"}},
    )

    assert effective_video_capabilities(model)["defaults"]["steps"] == 20


@pytest.mark.asyncio
async def test_reference_inputs_keep_order_and_allow_repeated_roles(tmp_path):
    manager = _manager(tmp_path)
    task_root = manager.root / "reference-fixture"
    task_root.mkdir(parents=True)
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "red").save(buffer, format="PNG")
    image = buffer.getvalue()
    payload = {
        "content": [
            {"type": "text", "role": "prompt", "text": "same subject"},
            {"type": "image_url", "role": "reference_image", "image_url": {"url": "multipart://one"}},
            {"type": "image_url", "role": "reference_image", "image_url": {"url": "multipart://two"}},
        ]
    }
    worker, manifest = await manager._freeze_inputs(
        payload,
        task_root,
        {
            "one": ("one.png", image, "image/png"),
            "two": ("two.png", image, "image/png"),
        },
    )
    assert worker["reference_parts"] == [
        {"kind": "image", "part_name": "reference_00_image"},
        {"kind": "image", "part_name": "reference_01_image"},
    ]
    assert [item["part_name"] for item in manifest] == [
        "reference_00_image", "reference_01_image"
    ]


def test_reference_inputs_reject_more_than_twelve_files(tmp_path):
    manager = _manager(tmp_path)
    model = manager._model("example/video")
    model.video_capabilities["content_combinations"] = [{
        "required": [{"type": "text", "role": "prompt", "min": 1, "max": 1}],
        "optional": [
            {"type": "image_url", "role": "reference_image", "min": 0, "max": 9},
            {"type": "video_url", "role": "reference_video", "min": 0, "max": 3},
            {"type": "audio_url", "role": "reference_audio", "min": 0, "max": 3},
        ],
    }]
    content = [{"type": "text", "role": "prompt", "text": "same subject"}]
    content.extend({
        "type": "image_url", "role": "reference_image", "image_url": {"url": f"multipart://image-{index}"}
    } for index in range(9))
    content.extend({
        "type": "video_url", "role": "reference_video", "video_url": {"url": f"multipart://video-{index}"}
    } for index in range(3))
    content.append({
        "type": "audio_url", "role": "reference_audio", "audio_url": {"url": "multipart://audio-0"}
    })

    with pytest.raises(VideoGenerationError) as captured:
        manager._effective_request({"model": model.id, "content": content}, model)

    assert captured.value.code == "unsupported_content_combination"
    assert "12 files total" in str(captured.value)


def test_video_task_manager_rejects_h3_bf16():
    model = SimpleNamespace(
        id="ai2apps.model.minimax-h3/fl2va-bf16",
        model_type="video_generation",
        checkpoint_ready=True,
        metadata={"family": "minimax-h3", "precision": "bf16"},
    )
    manager = object.__new__(VideoTaskManager)
    manager.runtime = SimpleNamespace(
        model_invocations=SimpleNamespace(model=lambda _model_id: model)
    )

    with pytest.raises(VideoGenerationError) as captured:
        manager._model(model.id)

    assert captured.value.code == "model_temporarily_disabled"
    assert captured.value.status_code == 409


@pytest.mark.asyncio
async def test_video_task_is_durable_idempotent_and_materializes_artifact(tmp_path):
    manager = _manager(tmp_path)
    await manager.startup()
    payload = {
        "model": "example/video",
        "content": [{"type": "text", "role": "prompt", "text": "ocean waves"}],
    }
    created = await manager.create(payload, actor_id="actor-1", idempotency_key="same")
    duplicate = await manager.create(payload, actor_id="actor-1", idempotency_key="same")
    assert duplicate["id"] == created["id"]

    for _ in range(100):
        completed = manager.get(created["id"], actor_id="actor-1")
        if completed["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("video task did not finish")

    assert completed["result"]["video"]["uri"].startswith("artifact://art_")
    artifact_id = completed["result"]["video"]["artifact_id"]
    session_id = completed["result"]["video"]["download_url"].split("/")[4]
    artifact = manager.workspace.get_artifact(session_id, artifact_id)
    assert manager.workspace.artifact_path(artifact).read_bytes() == b"fake-video"
    await manager.shutdown()


@pytest.mark.asyncio
async def test_video_task_uses_transparent_background_model_gateway(tmp_path):
    admitted = asyncio.Event()
    allow = asyncio.Event()
    captured = {}

    class Gateway:
        def context_for_actor(self, actor_id, **options):
            captured["context_actor_id"] = actor_id
            captured["context_options"] = options
            return {"actor_id": actor_id}

        async def invoke_background_to_file(
            self, model_id, operation, _payload, target, **options
        ):
            captured.update(
                model_id=model_id,
                operation=operation,
                options=options,
            )
            admitted.set()
            await allow.wait()
            options["on_admitted"]()
            target.write_bytes(b"fake-video")

    manager = _manager(tmp_path, gateway=Gateway())
    await manager.startup()
    created = await manager.create(
        {
            "model": "example/video",
            "content": [
                {"type": "text", "role": "prompt", "text": "scheduled ocean"}
            ],
        },
        actor_id="actor-1",
        invocation_actor_id="cloud-user-1",
    )
    await asyncio.wait_for(admitted.wait(), timeout=1)
    assert manager.get(created["id"], actor_id="actor-1")["status"] == "queued"

    allow.set()
    for _ in range(100):
        completed = manager.get(created["id"], actor_id="actor-1")
        if completed["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("scheduled video task did not finish")

    assert captured["model_id"] == "example/video"
    assert captured["operation"] == "video_generation"
    assert captured["options"]["request_id"] == created["id"]
    assert captured["context_actor_id"] == "cloud-user-1"
    assert captured["context_options"] == {
        "session_id": f"video:{created['id']}",
        "consumer_app_id": "ai2apps.video-studio",
    }
    assert captured["options"]["context"] == {"actor_id": "cloud-user-1"}
    await manager.shutdown()


@pytest.mark.asyncio
async def test_video_task_normalizes_legacy_runtime_actor_identity(tmp_path):
    captured = {}

    class Gateway:
        def context_for_actor(self, actor_id, **_options):
            captured["context_actor_id"] = actor_id
            return {"actor_id": actor_id}

        async def invoke_background_to_file(
            self, _model_id, _operation, _payload, target, **options
        ):
            options["on_admitted"]()
            target.write_bytes(b"fake-video")

    manager = _manager(tmp_path, gateway=Gateway())
    await manager.startup()
    created = await manager.create(
        {
            "model": "example/video",
            "content": [
                {"type": "text", "role": "prompt", "text": "legacy route"}
            ],
        },
        actor_id="ai2apps-user:cloud-user-1",
    )
    for _ in range(100):
        completed = manager.get(
            created["id"], actor_id="ai2apps-user:cloud-user-1"
        )
        if completed["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("legacy Runtime video task did not finish")

    assert captured["context_actor_id"] == "cloud-user-1"
    assert manager.list(actor_id="ai2apps-user:cloud-user-1")["data"][0]["id"] == created["id"]
    with manager.database.transaction() as connection:
        row = connection.execute(
            "SELECT actor_id,invocation_actor_id FROM video_generation_tasks WHERE id=?",
            (created["id"],),
        ).fetchone()
    assert tuple(row) == ("cloud-user-1", "cloud-user-1")
    await manager.shutdown()


@pytest.mark.asyncio
async def test_queued_video_cancel_removes_scheduler_waiter(tmp_path):
    admitted = asyncio.Event()
    captured = {}

    class Gateway:
        async def invoke_background_to_file(self, *_args, **_options):
            admitted.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                captured["cancelled"] = True
                raise

        async def cancel_request(self, _model_id, _request_id):
            return None

    manager = _manager(tmp_path, gateway=Gateway())
    await manager.startup()
    created = await manager.create(
        {
            "model": "example/video",
            "content": [
                {"type": "text", "role": "prompt", "text": "cancel me"}
            ],
        },
        actor_id="actor-1",
    )
    await asyncio.wait_for(admitted.wait(), timeout=1)

    cancelled = await manager.cancel(created["id"], actor_id="actor-1")

    assert cancelled["status"] == "cancelled"
    assert captured["cancelled"] is True
    assert created["id"] not in manager._running
    await manager.shutdown()


@pytest.mark.asyncio
async def test_video_task_idempotency_conflict_and_queued_cancel(tmp_path):
    manager = _manager(tmp_path)
    first = {
        "model": "example/video",
        "content": [{"type": "text", "role": "prompt", "text": "first"}],
    }
    second = {
        "model": "example/video",
        "content": [{"type": "text", "role": "prompt", "text": "second"}],
    }
    created = await manager.create(first, actor_id="actor-1", idempotency_key="key")
    with pytest.raises(VideoGenerationError, match="different request") as error:
        await manager.create(second, actor_id="actor-1", idempotency_key="key")
    assert error.value.status_code == 409

    cancelled = await manager.cancel(created["id"], actor_id="actor-1")
    assert cancelled["status"] == "cancelled"
    assert manager.list(actor_id="actor-1")["data"][0]["id"] == created["id"]


@pytest.mark.asyncio
async def test_cancelled_video_task_can_retry_from_frozen_request(tmp_path):
    manager = _manager(tmp_path)
    original = await manager.create(
        {
            "model": "example/video",
            "content": [
                {"type": "text", "role": "prompt", "text": "retry this shot"}
            ],
            "metadata": {"mode": "t2v", "pipeline_id": "ai2apps.video.text-to-video"},
        },
        actor_id="actor-1",
    )
    await manager.cancel(original["id"], actor_id="actor-1")

    retried = await manager.retry(original["id"], actor_id="actor-1")

    assert retried["id"] != original["id"]
    assert retried["status"] == "queued"
    assert retried["metadata"] == original["metadata"] | {"retry_of": original["id"]}
    with pytest.raises(VideoGenerationError, match="Only failed, cancelled, or expired"):
        await manager.retry(retried["id"], actor_id="actor-1")


@pytest.mark.asyncio
async def test_video_retry_copies_frozen_private_inputs(tmp_path):
    manager = _manager(tmp_path)
    model = manager._model("example/video")
    model.video_capabilities["content_combinations"] = [{
        "required": [
            {"type": "text", "role": "prompt", "min": 1, "max": 1},
            {"type": "image_url", "role": "first_frame", "min": 1, "max": 1},
        ],
        "optional": [],
    }]
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="PNG")
    image = buffer.getvalue()
    original = await manager.create(
        {
            "model": model.id,
            "content": [
                {"type": "text", "role": "prompt", "text": "animate this frame"},
                {"type": "image_url", "role": "first_frame", "image_url": {"url": "multipart://first_frame"}},
            ],
        },
        actor_id="actor-1",
        uploads={"first_frame": ("frame.png", image, "image/png")},
    )
    await manager.cancel(original["id"], actor_id="actor-1")

    retried = await manager.retry(original["id"], actor_id="actor-1")

    with manager.database.transaction() as connection:
        row = connection.execute(
            "SELECT input_manifest_json FROM video_generation_tasks WHERE id=?",
            (retried["id"],),
        ).fetchone()
    descriptor = json.loads(row["input_manifest_json"])[0]
    copied = manager.root / retried["id"] / descriptor["path"]
    assert copied.read_bytes() == image


@pytest.mark.asyncio
async def test_video_task_join_preserves_requested_clip_order(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    await manager.startup()

    def payload(prompt):
        return {
            "model": "example/video",
            "content": [{"type": "text", "role": "prompt", "text": prompt}],
        }
    tasks = [await manager.create(payload(name), actor_id="actor-1") for name in ("one", "two")]
    for _ in range(100):
        if all(manager.get(task["id"], actor_id="actor-1")["status"] == "succeeded" for task in tasks):
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("video tasks did not finish")

    captured = {}

    class Process:
        returncode = 0

        async def communicate(self):
            captured["listing"] = Path(captured["args"][7]).read_text()
            Path(captured["args"][-1]).write_bytes(b"joined-video")
            return b"", b""

    async def create_process(*args, **_kwargs):
        captured["args"] = args
        return Process()

    monkeypatch.setattr("ai2apps.video.tasks.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr("ai2apps.video.tasks.asyncio.create_subprocess_exec", create_process)
    joined = await manager.join([task["id"] for task in tasks], actor_id="actor-1")

    assert joined["video"]["uri"].startswith("artifact://art_")
    assert captured["listing"].count("file '") == 2
    session_id = joined["video"]["download_url"].split("/")[4]
    artifact = manager.workspace.get_artifact(session_id, joined["video"]["artifact_id"])
    assert manager.workspace.artifact_path(artifact).read_bytes() == b"joined-video"
    await manager.shutdown()


@pytest.mark.asyncio
async def test_video_retention_removes_expired_files_and_preserves_gallery(tmp_path):
    from ai2apps.gallery import GalleryRepository
    manager = _manager(tmp_path)
    gallery = GalleryRepository(manager.database, manager.workspace.paths.artifacts_path / 'gallery')
    ids = []
    for index in range(21):
        task = await manager.create({'model': 'example/video', 'content': [
            {'type': 'text', 'role': 'prompt', 'text': str(index)}]}, actor_id='actor-1')
        ids.append(task['id'])
        output = manager.root / task['id'] / 'result.mp4'
        output.write_bytes(b'video-' + bytes([index]))
        artifact = manager._materialize_artifact(task['id'], manager._model('example/video'), output)
        manager._update(task['id'], status='succeeded', artifact_id=artifact.id,
                        artifact_session_id=artifact.session_id)
        if index == 0:
            source = manager.workspace.artifact_path(artifact)
            with source.open('rb') as stream:
                asset, _ = gallery.import_stream('actor-1', stream, name='saved.mp4', media_type='video/mp4')
    queued = await manager.create({'model': 'example/video', 'content': [
        {'type': 'text', 'role': 'prompt', 'text': 'pending'}]}, actor_id='actor-1')
    manager.prune_history('another-user')
    assert source.exists()
    manager.prune_history('actor-1')
    assert not source.exists()
    assert not (manager.root / ids[0]).exists()
    assert (manager.root / ids[-1]).is_dir()
    assert manager.get(queued['id'], actor_id='actor-1')['status'] == 'queued'
    assert gallery.asset_path('actor-1', asset['id'])[1].read_bytes() == b'video-\x00'
    assert len(manager.list(actor_id='actor-1', limit=100)['data']) == 21


@pytest.mark.asyncio
async def test_video_manual_delete_rejects_active_and_foreign_tasks(tmp_path):
    from ai2apps.gallery import GalleryRepository
    manager = _manager(tmp_path)
    task = await manager.create({'model':'example/video','content':[{'type':'text','role':'prompt','text':'delete test'}]},actor_id='actor-1')
    with pytest.raises(VideoGenerationError) as error:
        manager.delete(task['id'],actor_id='actor-1')
    assert error.value.status_code == 409
    output=manager.root/task['id']/'result.mp4'; output.write_bytes(b'video-delete-test')
    artifact=manager._materialize_artifact(task['id'],manager._model('example/video'),output)
    manager._update(task['id'],status='succeeded',artifact_id=artifact.id,artifact_session_id=artifact.session_id)
    gallery=GalleryRepository(manager.database,manager.workspace.paths.artifacts_path/'gallery')
    source=manager.workspace.artifact_path(artifact)
    with source.open('rb') as stream:
        asset,_=gallery.import_stream('actor-1',stream,name='saved.mp4',media_type='video/mp4')
    with pytest.raises(VideoGenerationError) as error:
        manager.delete(task['id'],actor_id='another-user')
    assert error.value.status_code == 404 and source.exists()
    manager.delete(task['id'],actor_id='actor-1')
    assert not source.exists() and not (manager.root/task['id']).exists()
    assert gallery.asset_path('actor-1',asset['id'])[1].read_bytes()==b'video-delete-test'


@pytest.mark.asyncio
async def test_segmented_avatar_shutdown_requeues_and_restart_resumes(tmp_path):
    from ai2apps.avatar.segments import SCHEMA
    manager = _manager(tmp_path)
    model = manager._model("example/video")
    model.capabilities = ("avatar_video",)
    model.metadata = {}
    model.video_capabilities["avatar_segments"] = {
        "schema": SCHEMA, "planner": "h3-v1", "window_frames": 192}
    manager.runtime.package_manager = SimpleNamespace(packages=SimpleNamespace(
        active=lambda _: SimpleNamespace(package_digest="fixed-package")))
    started = asyncio.Event()
    async def blocked(*args):
        started.set()
        await asyncio.Event().wait()
    manager._invoke = blocked
    await manager.startup()
    task = await manager.create({"model": model.id, "content": [
        {"type":"text", "role":"prompt", "text":"portrait"}]},actor_id="actor-1")
    await asyncio.wait_for(started.wait(), 2)
    await manager.shutdown()
    row = manager._row(task["id"])
    assert row["status"] == "queued"
    assert row["cancel_requested_at"] is None
    assert json.loads(row["request_json"])["_avatar_model"]["package"] == "fixed-package"
    started.clear()
    await manager.startup()
    await asyncio.wait_for(started.wait(), 2)
    await manager.shutdown()
    assert manager._row(task["id"])["status"] == "queued"


@pytest.mark.asyncio
async def test_explicit_cancel_during_shutdown_is_not_requeued(tmp_path):
    from ai2apps.avatar.segments import SCHEMA
    manager = _manager(tmp_path)
    model = manager._model("example/video")
    model.capabilities = ("avatar_video",)
    model.metadata = {}
    model.video_capabilities["avatar_segments"] = {
        "schema": SCHEMA, "planner": "h3-v1", "window_frames": 192}
    manager.runtime.package_manager = SimpleNamespace(packages=SimpleNamespace(
        active=lambda _: SimpleNamespace(package_digest="fixed-package")))
    started = asyncio.Event()
    async def blocked(*args):
        started.set()
        await asyncio.Event().wait()
    manager._invoke = blocked
    await manager.startup()
    task = await manager.create({"model": model.id, "content": [
        {"type":"text", "role":"prompt", "text":"portrait"}]},actor_id="actor-1")
    await asyncio.wait_for(started.wait(), 2)
    cancel = manager.cancel
    async def concurrent(task_id, **kwargs):
        result = await cancel(task_id, **kwargs)
        with manager.database.transaction(write=True) as connection:
            connection.execute("UPDATE video_generation_tasks SET cancel_requested_at=? WHERE id=?",
                               ("2026-10-06T00:00:00Z", task_id))
        return result
    manager.cancel = concurrent
    await manager.shutdown()
    assert manager._row(task["id"])["status"] == "cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize("frame_count", [1, 400])
async def test_source_video_is_frozen_and_retryable(tmp_path, frame_count):
    manager = _manager(tmp_path)
    model = manager._model("example/video")
    model.video_capabilities["content_combinations"] = [{"required": [
        {"type": "video_url", "role": "source_video", "min": 1, "max": 1}], "optional": []}]
    path=tmp_path/"source.mp4"
    with av.open(str(path),"w") as output:
        stream=output.add_stream("libx264",rate=25);stream.width=32;stream.height=32;stream.pix_fmt="yuv420p"
        for _ in range(frame_count):
            for packet in stream.encode(av.VideoFrame.from_ndarray(np.zeros((32,32,3),dtype=np.uint8),format="rgb24")):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    with pytest.raises(VideoGenerationError, match="between 2 and 15"):
        manager._validate_media(path.read_bytes(),"video/mp4","video_url","reference_video")
    original=await manager.create({"model":model.id,"content":[{"type":"video_url","role":"source_video","video_url":{"url":"multipart://movie"}}]},actor_id="actor-1",uploads={"movie":("source.mp4",path.read_bytes(),"video/mp4")})
    await manager.cancel(original["id"],actor_id="actor-1")
    retried=await manager.retry(original["id"],actor_id="actor-1")
    for task in (original,retried):
        manifest=json.loads(manager._row(task["id"])["input_manifest_json"])
        assert len(manifest)==1 and manifest[0]["part_name"]=="source_video"
        assert (manager.root/task["id"]/manifest[0]["path"]).read_bytes()==path.read_bytes()
