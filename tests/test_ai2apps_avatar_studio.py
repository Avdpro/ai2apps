import io
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

from ai2apps.avatar import providers
from ai2apps.provisioning.profiles import CapabilityProfileRegistry
from ai2apps.storage import PlatformDatabase
from ai2apps.studio import avatar
from ai2apps.studio.capability_broker import StudioCapabilityError
from ai2apps.studio.repository import StudioRepository, StudioRepositoryError

ROOT = Path(__file__).resolve().parents[1]
LITE = "ai2apps.model.flashhead-mlx/lite"
PRO = "ai2apps.model.flashhead-mlx/pro"


def test_optional_provider_stacks_and_generic_package():
    source = ROOT / "packages/ai2apps-avatar-studio-suite"
    manifest = yaml.safe_load((source / "app.yaml").read_text())
    assert manifest["navigation"]["launcher"] is False
    assert manifest["mini_apps"][0]["requirements"]["capabilities"] == [
        avatar.AVATAR_CAPABILITY
    ]
    profile = CapabilityProfileRegistry().capability(
        avatar.VIDEO_STUDIO_ID, avatar.AVATAR_CAPABILITY
    )
    assert [p["stack"]["checkpoint"]["model_id"] for p in profile["profiles"]] == [
        LITE,
        PRO,
        "ai2apps.model.echomimic-v3-mlx/default",
        "ai2apps.model.avtr1-mlx/default",
        "ai2apps.model.minimax-h3/avatar-lightx2v-4step-4bit",
        "ai2apps.model.minimax-h3/avatar-base-4bit",
        "ai2apps.model.minimax-h3/avatar-base-8bit",
        "ai2apps.model.minimax-h3/avatar-ref2va-4bit",
        "ai2apps.model.minimax-h3/avatar-ref2va-8bit",
        "ai2apps.model.minimax-h3/avatar-lightx2v-8step-4bit",
        "ai2apps.model.minimax-h3/avatar-openvdn-dmd8-4bit",
        "ai2apps.model.minimax-h3/avatar-openvdn-stageb50-4bit",
    ]
    js = (source / "web/avatar.js").read_text()
    assert "flashhead" not in js.lower() and "echomimic" not in js.lower()
    assert "<video" not in (source / "web/photo-speaking.html").read_text()
    assert "downloadUrl" not in js  # input previews do not own generated output


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db = PlatformDatabase(tmp_path / "db.sqlite")
    db.initialize()
    repository = StudioRepository(db)
    raw = yaml.safe_load(
        (ROOT / "packages/ai2apps-model-flashhead-mlx/service.yaml").read_text()
    )["models"]
    models = [
        SimpleNamespace(
            id=m["id"],
            display_name=m["display_name"],
            model_type=m["model_type"],
            capabilities=m["capabilities"],
            video_capabilities=m["video_capabilities"],
        )
        for m in raw
    ]
    monkeypatch.setattr(avatar, "avatar_models", lambda runtime: tuple(models))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\0\0" * 32000)
    monkeypatch.setattr(avatar, "decode_audio_to_wav", lambda *a, **k: buf.getvalue())
    task = {"id": "task1", "status": "queued", "progress": {}}

    async def cancel(*a, **k):
        task["status"] = "cancelled"

    tasks = SimpleNamespace(
        create=AsyncMock(return_value=task.copy()),
        get=lambda *a, **k: task.copy(),
        cancel=AsyncMock(side_effect=cancel),
        artifact_session=lambda: "session",
    )
    mounted = SimpleNamespace(
        capabilities={avatar.AVATAR_CAPABILITY},
        mount={"context": {"studioInstanceId": "instance"}},
        declaration={"id": "ai2apps.avatar.photo-speaking", "version": "0.1.0"},
    )
    broker = SimpleNamespace(
        runtime=SimpleNamespace(video_tasks=tasks, database=db, workspace=None),
        mounted_mini_app=lambda *a, **k: mounted,
        _model_stack_ready=lambda *a: True,
    )
    principal = SimpleNamespace(actor_user_id="actor", installation_id="installation")
    args = dict(
        principal=principal,
        request=SimpleNamespace(is_disconnected=AsyncMock(return_value=True)),
        content=b"audio",
        filename="speech.wav",
        media_type="audio/wav",
        image=b"image",
        image_name="portrait.png",
        image_type="image/png",
        preset="standard",
        model_id=LITE,
        resolution="512x512",
        progress=AsyncMock(),
    )
    return broker, mounted, tasks, task, repository, args, models


@pytest.mark.asyncio
async def test_durable_disconnect_and_output_idempotency(setup):
    broker, mounted, tasks, task, repository, args, models = setup
    result = await avatar.generate_avatar(
        broker, avatar.VIDEO_STUDIO_ID, "mount", **args
    )
    assert result["status"] == "queued"
    tasks.cancel.assert_not_called()
    args["request"].is_disconnected.assert_not_called()
    assert tasks.create.call_args.args[0]["model"] == LITE
    task.update(
        status="succeeded",
        result={
            "video": {
                "download_url": "/v1/platform/sessions/session/artifacts/video/download",
                "artifact_id": "video",
            }
        },
    )
    for _ in range(2):
        result = avatar.jobs_for_mount(
            broker, avatar.VIDEO_STUDIO_ID, "new-mount", args["principal"]
        )["items"][0]
        assert result["hasOutput"] and result["status"] == "succeeded"
    scope = avatar._scope(
        broker, avatar.VIDEO_STUDIO_ID, "new-mount", args["principal"]
    )[1]
    assert len(repository.get_run(result["id"], **scope)["artifacts"]) == 1


@pytest.mark.asyncio
async def test_explicit_cancel_and_owner_scope(setup):
    broker, mounted, tasks, task, repository, args, models = setup
    job = await avatar.generate_avatar(
        broker, avatar.VIDEO_STUDIO_ID, "mount", **args
    )
    other = SimpleNamespace(actor_user_id="other", installation_id="installation")
    with pytest.raises(StudioRepositoryError):
        await avatar.cancel_job(
            broker, avatar.VIDEO_STUDIO_ID, "mount", other, job["id"]
        )
    tasks.cancel.assert_not_called()
    result = await avatar.cancel_job(
        broker, avatar.VIDEO_STUDIO_ID, "mount", args["principal"], job["id"]
    )
    assert result["status"] == "cancelled"
    tasks.cancel.assert_awaited_once_with("task1", actor_id="actor")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "undeclared",
        "wrong_studio",
        "preset",
        "model",
        "scope",
        "oversize",
        "resolution",
        "not_ready",
    ],
)
async def test_rejects_before_queue(setup, case):
    broker, mounted, tasks, task, repository, args, models = setup
    studio = avatar.VIDEO_STUDIO_ID
    if case == "undeclared":
        mounted.capabilities = set()
    if case == "wrong_studio":
        studio = "ai2apps.readaloud"
    if case == "preset":
        args["preset"] = "exact"
    if case == "model":
        args["model_id"] = "untrusted/model"
    if case == "scope":
        mounted.mount = {}
    if case == "oversize":
        args["image"] = b"x" * (20 * 1024 * 1024 + 1)
    if case == "resolution":
        args["resolution"] = "1920x1080"
    if case == "not_ready":
        broker._model_stack_ready = lambda *a: False
    with pytest.raises(StudioCapabilityError):
        await avatar.generate_avatar(broker, studio, "mount", **args)
    tasks.create.assert_not_called()


def test_provider_negotiation_and_duration(setup, monkeypatch):
    *_, models = setup
    monkeypatch.setattr(providers, "list_package_models", lambda runtime: models)
    assert providers.avatar_models(None)[0].id == LITE
    assert (
        providers.plan_portrait(models[0], preset="", resolution="", duration=60)[
            "preset"
        ]
        == "standard"
    )
    with pytest.raises(ValueError):
        providers.plan_portrait(models[1], preset="", resolution="", duration=10.01)
    models[0].capabilities = []
    assert len(providers.avatar_models(None)) == 1


@pytest.mark.asyncio
async def test_queue_failure_no_output_and_revoked_mount(setup):
    broker, mounted, tasks, task, repository, args, models = setup
    await avatar.generate_avatar(broker, avatar.VIDEO_STUDIO_ID, "mount", **args)
    task.update(
        status="failed", error={"code": "generation_failed", "message": "failure"}
    )
    result = avatar.jobs_for_mount(
        broker, avatar.VIDEO_STUDIO_ID, "mount", args["principal"]
    )["items"][0]
    assert result["error"]["message"] == "failure" and not result["hasOutput"]
    mounted.capabilities = set()
    with pytest.raises(StudioCapabilityError):
        avatar.jobs_for_mount(
            broker, avatar.VIDEO_STUDIO_ID, "mount", args["principal"]
        )


@pytest.mark.asyncio
async def test_retry_uses_frozen_task_and_rejects_running(setup):
    broker, mounted, tasks, task, repository, args, models = setup
    job = await avatar.generate_avatar(broker, avatar.VIDEO_STUDIO_ID, "mount", **args)
    tasks.retry = AsyncMock(return_value={"id": "retry-task", "status": "queued"})
    with pytest.raises(StudioCapabilityError):
        await avatar.retry_job(
            broker, avatar.VIDEO_STUDIO_ID, "mount", args["principal"], job["id"]
        )
    task.update(status="failed", error={"message": "failed"})
    avatar.jobs_for_mount(broker, avatar.VIDEO_STUDIO_ID, "mount", args["principal"])
    new = await avatar.retry_job(
        broker, avatar.VIDEO_STUDIO_ID, "mount", args["principal"], job["id"]
    )
    assert new["id"] != job["id"] and new["modelId"] == job["modelId"]
    scope = avatar._scope(broker, avatar.VIDEO_STUDIO_ID, "mount", args["principal"])[1]
    assert repository.get_run(new["id"], **scope)["retryOf"] == job["id"]
    tasks.retry.assert_awaited_once_with("task1", actor_id="actor")


def test_source_contract():
    import json

    from ai2apps.extensions.archive import InteractiveArchive
    from ai2apps.extensions.models import UnitKind

    source = ROOT / "packages/ai2apps-avatar-studio-suite"
    manifest = yaml.safe_load((source / "app.yaml").read_text())
    files = {
        p.relative_to(source).as_posix()
        for p in source.rglob("*")
        if p.is_file() and p.name != "ai2apps.json"
    }
    InteractiveArchive._validate_manifest(UnitKind.APP, manifest, files)
    contract = json.loads((source / "ai2apps.json").read_text())
    assert contract["dependencies"] == []
    assert contract["entrypoints"][0]["path"] == manifest["entry"]["resource"]


def test_mount_context_cannot_override_authorized_studio(monkeypatch):
    from ai2apps.api import studio_mini_apps as api

    captured = {}

    def mount(*args, **kwargs):
        captured.update(kwargs)
        return {"id": "mount"}

    manager = SimpleNamespace(
        instance_entry=lambda *a, **k: {"app_key": avatar.VIDEO_STUDIO_ID},
        mount_studio_mini_app=mount,
    )
    monkeypatch.setattr(api, "authorize_app_instance", lambda *a: None)
    monkeypatch.setattr(api, "_content_url", lambda mount: "/frame")
    monkeypatch.setattr(
        api,
        "StudioMiniAppRegistry",
        lambda manager: SimpleNamespace(
            list=lambda *a, **k: {"items": [{"id": "avatar", "source": "package"}]}
        ),
    )
    router = api.create_studio_mini_app_router(
        lambda: SimpleNamespace(extension_manager=manager)
    )
    endpoint = next(
        route.endpoint for route in router.routes if route.name == "mount_mini_app"
    )
    endpoint(
        avatar.VIDEO_STUDIO_ID,
        api.StudioMiniAppMountRequest(
            mini_app_id="avatar", context={"studioInstanceId": "another-instance"}
        ),
        studio_instance_id="authorized-instance",
        principal=SimpleNamespace(authentication_type="local_session"),
    )
    assert captured["context"]["studioInstanceId"] == "authorized-instance"


def test_long_avatar_quota_requires_explicit_segment_protocol(setup):
    models = setup[-1]
    model = models[0]
    model.video_capabilities['duration']['maximum_seconds'] = 3600
    assert providers.maximum_audio_seconds(model) == 600
    model.video_capabilities['avatar_segments'] = {
        'schema':'ai2apps.avatar-segment/v1', 'planner':'h3-v1', 'window_frames':192}
    assert providers.maximum_audio_seconds(model) == 3276
    assert providers.describe_model(model,ready=True)['maximumSeconds'] == 3276
    providers.plan_portrait(model,preset='',resolution='',duration=3276)
    with pytest.raises(ValueError):
        providers.plan_portrait(model,preset='',resolution='',duration=3276.01)
