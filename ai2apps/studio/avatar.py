"""Mount-authorized avatar jobs backed by durable video tasks and shared output."""

from __future__ import annotations

import asyncio
import io
import threading
import wave
from contextlib import suppress

from ai2apps.audio_codecs import (
    AudioCodecError,
    decode_audio_to_wav,
    infer_audio_format,
)
from ai2apps.avatar import avatar_models, describe_model, plan_portrait
from ai2apps.studio.repository import StudioRepository
from ai2apps.video.tasks import VideoGenerationError

AVATAR_CAPABILITY = "video.avatar_generation"
VIDEO_STUDIO_ID = "ai2apps.video-studio"
TERMINAL = {"succeeded", "failed", "cancelled", "expired"}
_SYNC_LOCK = threading.RLock()


def _error(code, message, status=422):
    from ai2apps.studio.capability_broker import StudioCapabilityError

    return StudioCapabilityError(code, message, status_code=status)


def _scope(broker, studio_id, mount_id, principal):
    mounted = broker.mounted_mini_app(studio_id, mount_id, principal=principal)
    if studio_id != VIDEO_STUDIO_ID or AVATAR_CAPABILITY not in mounted.capabilities:
        raise _error("capability_not_declared", "Avatar generation is not allowed", 403)
    instance = (mounted.mount.get("context") or {}).get("studioInstanceId")
    if not isinstance(instance, str) or not instance:
        raise _error(
            "studio_output_scope_missing",
            "Video Studio output scope is unavailable",
            409,
        )
    return mounted, dict(
        actor_id=principal.actor_user_id,
        installation_id=principal.installation_id,
        app_instance_id=instance,
        studio_id=studio_id,
    )


def models_for_mount(broker, studio_id, mount_id, principal):
    _scope(broker, studio_id, mount_id, principal)
    return {
        "items": [
            describe_model(m, ready=broker._model_stack_ready(broker.runtime, m))
            for m in avatar_models(broker.runtime)
        ]
    }


def reconcile_outputs(runtime, repository, scope):
    """Project queue state into Host output on read, including after UI/process restart.

    This synchronous critical section serializes shared-panel and Mini-App reads;
    existing artifacts are checked before publishing, including crash recovery.
    """
    if getattr(runtime, "video_tasks", None) is None:
        return
    with _SYNC_LOCK:
        for run in repository.list_runs(**scope, limit=100):
            if (
                run["status"] in TERMINAL
                or run["input"].get("avatarOperation") != "portrait_animation"
            ):
                continue
            try:
                task = runtime.video_tasks.get(
                    run["input"]["videoTaskId"], actor_id=scope["actor_id"]
                )
            except VideoGenerationError as error:
                repository.update_run(
                    run["id"],
                    **scope,
                    status="failed",
                    progress=0,
                    detail=str(error),
                    error={"code": error.code, "message": str(error)},
                )
                continue
            status = task["status"]
            detail = task.get("progress") or {}
            if status == "succeeded" and not run["artifacts"]:
                video = task["result"]["video"]
                repository.create_artifact(
                    run["id"],
                    **scope,
                    kind="video",
                    name="avatar.mp4",
                    media_type="video/mp4",
                    preview_url=video["download_url"],
                    download_url=video["download_url"],
                    source_id=video["artifact_id"],
                    metadata={
                        "workspaceSessionId": runtime.video_tasks.artifact_session(),
                        "workspaceArtifactId": video["artifact_id"],
                        "videoTaskId": task["id"],
                    },
                )
            repository.update_run(
                run["id"],
                **scope,
                status=status,
                progress=100
                if status == "succeeded"
                else int(detail.get("percent") or 0),
                detail=str(
                    (task.get("error") or {}).get("message")
                    or detail.get("phase")
                    or status
                ),
                error=task.get("error"),
            )


def jobs_for_mount(broker, studio_id, mount_id, principal):
    mounted, scope = _scope(broker, studio_id, mount_id, principal)
    repository = StudioRepository(broker.runtime.database)
    reconcile_outputs(broker.runtime, repository, scope)
    return {
        "items": [
            _job(run)
            for run in repository.list_runs(**scope, limit=100)
            if run["miniAppId"] == mounted.declaration["id"]
            and run["input"].get("avatarOperation") == "portrait_animation"
        ]
    }


def _job(run):
    return {
        "id": run["id"],
        "status": run["status"],
        "progress": run["progress"],
        "modelId": run["input"].get("modelId"),
        "error": run["error"],
        "preset": run["input"].get("preset"),
        "resolution": run["input"].get("resolution"),
        "detail": (run.get("steps") or [{}])[0].get("detail", ""),
        "hasOutput": bool(run["artifacts"]),
    }


async def cancel_job(broker, studio_id, mount_id, principal, job_id):
    mounted, scope = _scope(broker, studio_id, mount_id, principal)
    repository = StudioRepository(broker.runtime.database)
    run = repository.get_run(job_id, **scope)
    if (
        run["miniAppId"] != mounted.declaration["id"]
        or run["input"].get("avatarOperation") != "portrait_animation"
    ):
        raise _error("job_not_found", "Avatar job was not found", 404)
    try:
        await broker.runtime.video_tasks.cancel(
            run["input"]["videoTaskId"], actor_id=scope["actor_id"]
        )
    except VideoGenerationError as error:
        raise _error(error.code, str(error), error.status_code) from error
    reconcile_outputs(broker.runtime, repository, scope)
    return _job(repository.get_run(job_id, **scope))


async def retry_job(broker, studio_id, mount_id, principal, job_id):
    mounted, scope = _scope(broker, studio_id, mount_id, principal)
    repository = StudioRepository(broker.runtime.database)
    run = repository.get_run(job_id, **scope)
    if (
        run["miniAppId"] != mounted.declaration["id"]
        or run["input"].get("avatarOperation") != "portrait_animation"
    ):
        raise _error("job_not_found", "Avatar job was not found", 404)
    if run["status"] not in {"failed", "cancelled", "expired"}:
        raise _error(
            "job_not_retryable", "Only failed or cancelled jobs can retry", 409
        )
    try:
        task = await broker.runtime.video_tasks.retry(
            run["input"]["videoTaskId"], actor_id=scope["actor_id"]
        )
    except VideoGenerationError as error:
        raise _error(error.code, str(error), error.status_code) from error
    try:
        new_run = repository.create_run(
            **scope,
            mini_app_id=mounted.declaration["id"],
            mini_app_version=mounted.declaration["version"],
            placement="inline",
            title=run["title"],
            input_data={**run["input"], "videoTaskId": task["id"]},
            retry_of=run["id"],
            step_label="Retry avatar generation",
        )
        return _job(new_run)
    except BaseException:
        with suppress(Exception):
            await broker.runtime.video_tasks.cancel(
                task["id"], actor_id=scope["actor_id"]
            )
        raise


async def generate_avatar(
    broker,
    studio_id,
    mount_id,
    *,
    principal,
    request,
    content,
    filename,
    media_type,
    image,
    image_name,
    image_type,
    preset,
    progress,
    model_id="",
    resolution="",
):
    mounted, scope = _scope(broker, studio_id, mount_id, principal)
    if not image or len(image) > 20 * 1024 * 1024:
        raise _error("image_invalid", "A reference image up to 20 MiB is required")
    models = avatar_models(broker.runtime)
    model = (
        next((m for m in models if m.id == model_id), None)
        if model_id
        else next(
            (m for m in models if broker._model_stack_ready(broker.runtime, m)), None
        )
    )
    if model is None or not broker._model_stack_ready(broker.runtime, model):
        raise _error("capability_not_ready", "请先配置所选数字人模型", 409)
    runtime = broker.runtime
    if getattr(runtime, "video_tasks", None) is None:
        raise _error("capability_broker_unavailable", "Video queue is unavailable", 503)
    try:
        wav = await asyncio.to_thread(
            decode_audio_to_wav,
            content,
            input_format=infer_audio_format(filename, media_type),
            sample_rate=16_000,
            max_duration_seconds=min(
                600, model.video_capabilities["duration"]["maximum_seconds"] or 600
            ),
        )
        with wave.open(io.BytesIO(wav), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
        plan = plan_portrait(
            model, preset=preset, resolution=resolution, duration=duration
        )
    except (AudioCodecError, ValueError, wave.Error) as error:
        raise _error("avatar_input_invalid", str(error)) from error
    # Refresh authorization after decoding, before committing a persistent job.
    mounted, scope = _scope(broker, studio_id, mount_id, principal)
    task = None
    try:
        task = await runtime.video_tasks.create(
            {
                **plan,
                "content": [
                    {
                        "type": "image_url",
                        "role": "reference_image",
                        "image_url": {"url": "multipart://portrait"},
                    },
                    {
                        "type": "audio_url",
                        "role": "driving_audio",
                        "audio_url": {"url": "multipart://speech"},
                    },
                ],
            },
            actor_id=principal.actor_user_id,
            invocation_actor_id=principal.actor_user_id,
            uploads={
                "portrait": (image_name, image, image_type),
                "speech": ("speech.wav", wav, "audio/wav"),
            },
        )
        run = StudioRepository(runtime.database).create_run(
            **scope,
            mini_app_id=mounted.declaration["id"],
            mini_app_version=mounted.declaration["version"],
            placement="inline",
            title="照片说话",
            step_label="生成数字人视频",
            input_data={
                "avatarOperation": "portrait_animation",
                "videoTaskId": task["id"],
                "modelId": model.id,
                "preset": plan["preset"],
                "resolution": plan["resolution"],
            },
        )
        return _job(run)
    except BaseException as error:
        if task is not None:
            with suppress(Exception):
                await runtime.video_tasks.cancel(
                    task["id"], actor_id=principal.actor_user_id
                )
        if isinstance(error, VideoGenerationError):
            raise _error(error.code, str(error), error.status_code) from error
        raise
