from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from ai2apps.config import PlatformConfig
from ai2apps.events import EventNotificationBus, EventStore
from ai2apps.storage import PlatformDatabase
from ai2apps.video import VideoGenerationError, VideoTaskManager
from ai2apps.video_policy import (
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
        metadata={"family": "minimax-h3", "precision": "q8"},
        video_capabilities={
            "geometry": {"resolutions": ["512x512"], "ratios": ["1:1"]},
            "defaults": {"resolution": "512x512"},
        },
    )

    capabilities = effective_video_capabilities(model)

    assert capabilities["geometry"]["resolutions"] == list(H3_RESOLUTIONS)
    assert capabilities["geometry"]["ratios"] == list(H3_RATIOS)
    assert capabilities["defaults"]["resolution"] == "512x512"


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
