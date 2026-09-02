from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.responses import Response

from ai2apps.events import EventNotificationBus, EventStore
from ai2apps.readaloud import ReadAloudRepository, ReadAloudTaskManager
from ai2apps.readaloud.tasks import ReadAloudRenderError
from ai2apps.storage import PlatformDatabase


def _fixture(tmp_path: Path, *, gateway=None):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    events = EventStore(database, EventNotificationBus())
    repository = ReadAloudRepository(database, events)
    project = repository.create_project(
        "user-1",
        title="Chapter one",
        purpose="private",
        source_rights="user_owned",
        source_text="",
    )
    first = repository.create_segment(
        "user-1",
        project["id"],
        speaker_id=None,
        text="First line",
        emotion="neutral",
        emotion_strength=1,
        speed=1,
        pause_after_ms=200,
    )
    second = repository.create_segment(
        "user-1",
        project["id"],
        speaker_id=None,
        text="Second line",
        emotion="calm",
        emotion_strength=1,
        speed=0.9,
        pause_after_ms=300,
    )
    model = SimpleNamespace(
        id="example.tts/default",
        upstream_id="example-upstream",
        model_type="audio_tts",
        checkpoint_ready=True,
        service_key="example.tts",
        endpoint="http://127.0.0.1:8100",
        metadata={},
        endpoints={"audio_speech": "/v1/audio/speech"},
        internal_headers={},
    )

    class Manager(ReadAloudTaskManager):
        def _model(self, model_id):
            if model_id != model.id:
                raise ReadAloudRenderError("model_not_found", "missing", status_code=404)
            return model

        async def _invoke(self, job_id, segment_id, _model, request, _owner_user_id):
            if gateway is not None:
                return await super()._invoke(
                    job_id, segment_id, _model, request, _owner_user_id
                )
            target = self.root / job_id / f"{segment_id}.wav"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(request["input"].encode())
            return target

    manager = Manager(
        runtime=SimpleNamespace(model_invocations=gateway),
        database=database,
        root=tmp_path / "renders",
    )
    return database, project, (first, second), manager


@pytest.mark.asyncio
async def test_batch_render_uses_transparent_background_model_gateway(tmp_path):
    captured = []

    class Gateway:
        async def invoke_background_json(
            self, model_id, operation, payload, *, request_id=None
        ):
            captured.append(
                {
                    "model_id": model_id,
                    "operation": operation,
                    "payload": payload,
                    "request_id": request_id,
                }
            )
            return Response(content=payload["input"].encode())

    _database, project, segments, manager = _fixture(
        tmp_path, gateway=Gateway()
    )
    await manager.startup()
    created = await manager.create(
        owner_user_id="user-1",
        project_id=project["id"],
        model_id="example.tts/default",
    )
    for _ in range(100):
        job = manager.get(created["id"], owner_user_id="user-1")
        if job["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Read Aloud render did not finish")

    assert job["project_revision"] == 3
    assert job["completed_segments"] == 2
    assert [item["status"] for item in job["segments"]] == ["succeeded", "succeeded"]
    assert len(captured) == 2
    assert all(item["operation"] == "audio_speech" for item in captured)
    assert all(item["model_id"] == "example.tts/default" for item in captured)
    assert [
        (manager.root / item["output_path"]).read_text() for item in job["segments"]
    ] == [segment["text"] for segment in segments]
    await manager.shutdown()


@pytest.mark.asyncio
async def test_cancelled_render_cancels_queued_scheduler_attempt(tmp_path):
    queued = asyncio.Event()
    cancelled = {}

    class Gateway:
        async def invoke_background_json(self, *_args, **_options):
            queued.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled["value"] = True
                raise

    _database, project, _segments, manager = _fixture(
        tmp_path, gateway=Gateway()
    )
    await manager.startup()
    created = await manager.create(
        owner_user_id="user-1",
        project_id=project["id"],
        model_id="example.tts/default",
    )
    await asyncio.wait_for(queued.wait(), timeout=1)

    job = await manager.cancel(created["id"], owner_user_id="user-1")

    assert cancelled["value"] is True
    assert job["status"] == "cancelled"
    assert {item["status"] for item in job["segments"]} == {"cancelled"}
    await manager.shutdown()


@pytest.mark.asyncio
async def test_restart_resumes_incomplete_render_from_segment_boundary(tmp_path):
    database, project, _segments, creator = _fixture(tmp_path)
    created = await creator.create(
        owner_user_id="user-1",
        project_id=project["id"],
        model_id="example.tts/default",
    )
    with database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE readaloud_render_jobs SET status='running' WHERE id=?",
            (created["id"],),
        )
        connection.execute(
            "UPDATE readaloud_render_segments SET status='running' "
            "WHERE job_id=? AND ordinal=0",
            (created["id"],),
        )
    resumed = type(creator)(
        runtime=creator.runtime,
        database=database,
        root=creator.root,
    )
    await resumed.startup()
    for _ in range(100):
        job = resumed.get(created["id"], owner_user_id="user-1")
        if job["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Recovered Read Aloud render did not finish")
    assert job["completed_segments"] == 2
    await resumed.shutdown()
