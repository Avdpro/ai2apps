"""Mount-authorized, durable Studio Runs for bounded and long video upscaling."""

from __future__ import annotations

import asyncio
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from ai2apps.model_invocation import ModelInvocationContext
from ai2apps.model_providers import list_package_models
from ai2apps.studio.repository import StudioRepository
from ai2apps.video.upscaling import inspect_source, split_source, stitch_segments

CAPABILITY = "video.upscaling"
STUDIO_ID = "ai2apps.video-studio"
MINI_APP_ID = "ai2apps.video.upscaling"
TERMINAL = {"succeeded", "failed", "cancelled", "expired"}
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


def _error(code, message, status=422):
    from ai2apps.studio.capability_broker import StudioCapabilityError

    return StudioCapabilityError(code, message, status_code=status)


def _models(runtime):
    return tuple(model for model in list_package_models(runtime)
                 if model.model_type == "video_upscaling"
                 and "video_upscaling" in model.capabilities
                 and not model.metadata.get("internal"))


def models_for_builtin(runtime):
    return {"items": [{
        "id": model.id,
        "label": model.display_name,
        "ready": _model_ready(runtime, model),
        "customPrompt": model.metadata.get("prompt_mode") == "custom",
        "maximumFrames": (model.video_upscaling_capabilities or {}).get("maximum_frames", 1500),
        "maximumSeconds": (model.video_upscaling_capabilities or {}).get("maximum_seconds", 60),
        "resolutionPolicy": (model.video_upscaling_capabilities or {}).get("resolution_policy", "fixed"),
    } for model in _models(runtime)]}


def _model_ready(runtime, model):
    from ai2apps.studio.capability_broker import StudioCapabilityBroker

    return StudioCapabilityBroker._model_stack_ready(runtime, model)


def _job(run):
    return {"id": run["id"], "status": run["status"], "progress": run["progress"],
            "detail": (run.get("steps") or [{}])[0].get("detail", ""),
            "modelId": run["input"].get("modelId"), "sourceName": run["input"].get("sourceName"),
            "segments": run["input"].get("segments"), "error": run["error"],
            "hasOutput": bool(run["artifacts"])}


@dataclass
class _Active:
    task: asyncio.Task
    stopped: threading.Event


class UpscalingJobs:
    def __init__(self, runtime):
        self.runtime = runtime
        self.repository = StudioRepository(runtime.database)
        self.root = Path(runtime.config.paths.artifacts_path) / "video-upscaling-jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.active: dict[str, _Active] = {}

    def reconcile(self, scope):
        for run in self.repository.list_runs(**scope, limit=100):
            if run["input"].get("upscalingOperation") != CAPABILITY or run["status"] in TERMINAL:
                continue
            if run["id"] not in self.active:
                self.repository.update_run(run["id"], **scope, status="failed",
                                           progress=run["progress"], detail="Host restarted",
                                           error={"code": "worker_interrupted", "message": "Host restarted; retry the task"})

    def launch(self, run, scope, context):
        stopped = threading.Event()
        task = asyncio.create_task(self._run(run["id"], scope, context, stopped),
                                   name=f"video-upscaling-{run['id']}")
        self.active[run["id"]] = _Active(task, stopped)
        task.add_done_callback(lambda _task: self.active.pop(run["id"], None))

    async def _thread(self, operation, stopped, *args, **kwargs):
        work = asyncio.create_task(asyncio.to_thread(operation, *args, **kwargs))
        try:
            return await asyncio.shield(work)
        except asyncio.CancelledError:
            stopped.set()
            while not work.done():
                try:
                    await asyncio.shield(work)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            raise

    async def _run(self, run_id, scope, context, stopped):
        run = self.repository.get_run(run_id, **scope)
        root = self.root / run_id
        source = root / "source.mp4"
        model_id = run["input"]["modelId"]
        capabilities = run["input"].get("videoUpscalingCapabilities")
        parameters = {"scale": 2, "seed": run["input"]["seed"]}
        if run["input"].get("prompt"):
            parameters["prompt"] = run["input"]["prompt"]

        def check():
            if stopped.is_set():
                raise InterruptedError("Video upscaling was cancelled")

        def update(percent, detail):
            self.repository.update_run(run_id, **scope, status="running",
                                       progress=min(99, max(0, int(percent))), detail=detail)

        try:
            update(1, "检查视频帧率、尺寸和音轨")
            info = await self._thread(inspect_source, stopped, source, check=check,
                                      capabilities=capabilities)
            check()
            caps = capabilities or {}
            maximum_frames = caps.get("maximum_frames", 1500)
            maximum_seconds = caps.get("maximum_seconds", 60)
            if info.frames <= maximum_frames and info.frames / float(info.fps) <= maximum_seconds:
                parts = [source]
                segments = None
            else:
                if caps.get("segmented") is False or caps.get("temporal_policy") == "whole_clip":
                    raise ValueError(
                        f"当前模型使用全片精修，最多支持 {maximum_frames} 帧 / {maximum_seconds} 秒；"
                        "为保持画面连续性，不会自动拆段。请使用较短的视频。"
                    )
                update(5, "按时间轴分段并保留叠帧")
                info = await self._thread(split_source, stopped, source, root / "parts",
                                          check=check, capabilities=capabilities)
                parts = [segment.path for segment in info.segments]
                segments = info.segments
            outputs = []
            for number, part in enumerate(parts):
                check()
                output = root / f"upscaled-{number:05d}.mp4"
                request_id = f"{run_id}-{number:05d}"

                def worker_progress(value, index=number):
                    current, total = value.get("current"), value.get("total")
                    fraction = current / total if isinstance(current, int) and isinstance(total, int) and total > 0 else 0
                    update(8 + 78 * (index + max(0, min(1, fraction))) / len(parts),
                           f"放大第 {index + 1}/{len(parts)} 段")

                await self.runtime.model_invocations.invoke_background_to_file(
                    model_id, "video_upscaling", {"parameters": parameters}, output,
                    files={"video": (part.name, part, "video/mp4")},
                    request_id=request_id, cancel_requested=stopped.is_set,
                    progress=worker_progress, context=context,
                    on_admitted=lambda n=number: update(8 + 78 * n / len(parts), f"放大第 {n + 1}/{len(parts)} 段"),
                )
                outputs.append(output)
            check()
            if segments is None:
                final = outputs[0]
            else:
                update(87, "叠帧拼合，复用原音轨")
                final = root / "result.mp4"
                await self._thread(stitch_segments, stopped, source, outputs, info, final,
                                   check=check,
                                   progress=lambda done, total: update(87 + 11 * done / total, "叠帧拼合，复用原音轨"))
            check()
            session_id = self.runtime.video_tasks.artifact_session()
            artifact = await self._thread(
                self.runtime.workspace.import_artifact, stopped, session_id, final,
                "upscaled.mp4", media_type="video/mp4",
                metadata={"generator": "video.upscaling", "model": model_id, "runId": run_id},
            )
            url = f"/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download"
            self.repository.create_artifact(run_id, **scope, kind="video", name=artifact.name,
                                            media_type="video/mp4", preview_url=url, download_url=url,
                                            source_id=artifact.id,
                                            metadata={"workspaceSessionId": session_id,
                                                      "workspaceArtifactId": artifact.id, "modelId": model_id})
            self.repository.update_run(run_id, **scope, status="succeeded", progress=100,
                                       detail="视频放大完成")
            shutil.rmtree(root, ignore_errors=True)
        except (InterruptedError, asyncio.CancelledError):
            self.repository.update_run(run_id, **scope, status="cancelled", progress=0,
                                       detail="视频放大已停止",
                                       error={"code": "generation_cancelled", "message": "Video upscaling was cancelled"})
        except Exception as error:
            cancelled = stopped.is_set() or getattr(error, "code", None) == "generation_cancelled"
            self.repository.update_run(
                run_id, **scope, status="cancelled" if cancelled else "failed", progress=0,
                detail="视频放大已停止" if cancelled else str(error),
                error={"code": "generation_cancelled" if cancelled else getattr(error, "code", "upscaling_failed"),
                       "message": "Video upscaling was cancelled" if cancelled else str(error)},
            )


def _manager(runtime):
    manager = getattr(runtime, "_video_upscaling_jobs", None)
    if manager is None:
        manager = UpscalingJobs(runtime)
        runtime._video_upscaling_jobs = manager
    return manager


def jobs_for_builtin(runtime, scope):
    manager = _manager(runtime)
    manager.reconcile(scope)
    return {"items": [_job(run) for run in manager.repository.list_runs(**scope, limit=100)
                      if run["miniAppId"] == MINI_APP_ID
                      and run["input"].get("upscalingOperation") == CAPABILITY]}


async def start_builtin_job(runtime, scope, principal, *, content, filename,
                            media_type, model_id, seed, prompt):
    if not content or len(content) > MAX_UPLOAD_BYTES or not (
        media_type.startswith("video/") or media_type == "application/octet-stream"
    ):
        raise _error("invalid_video", "Select a video up to 1 GiB")
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise _error("invalid_request", "Seed must be an integer from 0 to 4294967295")
    if not isinstance(prompt, str) or len(prompt) > 2048:
        raise _error("invalid_request", "Prompt exceeds 2048 characters")
    model = next((item for item in _models(runtime) if item.id == model_id), None)
    if model is None:
        raise _error("model_not_found", "Select a video upscaling model", 404)
    if not _model_ready(runtime, model):
        raise _error("model_unavailable", "Install the selected model first", 409)
    if prompt.strip() and model.metadata.get("prompt_mode") != "custom":
        raise _error("prompt_configuration_required", "Select the Custom Prompt model")
    manager = _manager(runtime)
    run = manager.repository.create_run(**scope, mini_app_id=MINI_APP_ID,
                                        mini_app_version="1.0.0",
                                        placement="inline", title="放大视频", step_label="视频 2× 放大",
                                        input_data={"upscalingOperation": CAPABILITY,
                                                    "modelId": model_id, "sourceName": Path(filename).name[:255],
                                                    "videoUpscalingCapabilities": dict(model.video_upscaling_capabilities or {}),
                                                    "seed": seed, "prompt": prompt.strip()})
    root = manager.root / run["id"]
    try:
        root.mkdir(mode=0o700)
        (root / "source.mp4").write_bytes(content)
        context = ModelInvocationContext.from_principal(
            principal, session_id=f"video-upscaling:{run['id']}",
            app_instance_id=scope["app_instance_id"], consumer_app_id=STUDIO_ID)
        manager.launch(run, scope, context)
        return _job(run)
    except BaseException as error:
        shutil.rmtree(root, ignore_errors=True)
        manager.repository.update_run(run["id"], **scope, status="failed", progress=0,
                                      detail=str(error), error={"code": "upscaling_setup_failed", "message": str(error)})
        raise


async def mutate_builtin_job(runtime, scope, principal, job_id, action):
    manager = _manager(runtime)
    run = manager.repository.get_run(job_id, **scope)
    if run["miniAppId"] != MINI_APP_ID or run["input"].get("upscalingOperation") != CAPABILITY:
        raise _error("job_not_found", "Upscaling job was not found", 404)
    if action == "cancel":
        active = manager.active.get(job_id)
        if active is not None:
            active.stopped.set()
        elif run["status"] not in TERMINAL:
            manager.reconcile(scope)
        return _job(manager.repository.get_run(job_id, **scope))
    if run["status"] not in {"failed", "cancelled", "expired"}:
        raise _error("job_not_retryable", "Only failed or cancelled jobs can retry", 409)
    source = manager.root / job_id / "source.mp4"
    if not source.is_file():
        raise _error("input_expired", "Original input is no longer available", 410)
    new_run = manager.repository.create_run(**scope, mini_app_id=MINI_APP_ID,
                                            mini_app_version="1.0.0",
                                            placement="inline", title=run["title"], retry_of=job_id,
                                            step_label="视频 2× 放大", input_data=dict(run["input"]))
    new_root = manager.root / new_run["id"]
    try:
        new_root.mkdir(mode=0o700)
        await asyncio.to_thread(shutil.copyfile, source, new_root / "source.mp4")
        context = ModelInvocationContext.from_principal(
            principal, session_id=f"video-upscaling:{new_run['id']}",
            app_instance_id=scope["app_instance_id"], consumer_app_id=STUDIO_ID)
        manager.launch(new_run, scope, context)
        return _job(new_run)
    except BaseException as error:
        shutil.rmtree(new_root, ignore_errors=True)
        manager.repository.update_run(new_run["id"], **scope, status="failed", progress=0,
                                      detail=str(error),
                                      error={"code": "upscaling_retry_setup_failed", "message": str(error)})
        raise
