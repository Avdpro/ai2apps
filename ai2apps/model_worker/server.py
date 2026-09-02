# SPDX-License-Identifier: Apache-2.0
"""Authenticated HTTP transport for the system Model Worker protocol v1."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
import secrets
import shutil
import stat
import sys
import tempfile
import uuid
import wave
from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.datastructures import UploadFile

from .protocol import (
    ModelWorkerArtifact,
    ModelWorkerCheckpoint,
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerPart,
    ModelWorkerRequest,
    ModelWorkerResponse,
    ModelWorkerStream,
)

PROTOCOL = "ai2apps-model-worker/v1"
OPERATIONS = {
    "chat_completions": "/v1/chat/completions",
    "responses": "/v1/responses",
    "image_generation": "/v1/images/generations",
    "image_edit": "/v1/images/edits",
    "audio_transcription": "/v1/audio/transcriptions",
    "audio_speech": "/v1/audio/speech",
    "audio_process": "/v1/audio/process",
    "video_generation": "/v1/videos/generations",
}
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_MULTIPART_FILE_BYTES = 100 * 1024 * 1024
MAX_MULTIPART_FIELD_BYTES = 64 * 1024
# Video reference models such as MiniMax H3 Ref2VA accept up to twelve
# ordered media inputs.  Keep the transport limit aligned with the public
# capability contract so valid requests are not rejected before the adapter.
MAX_MULTIPART_PARTS = 12
MAX_AUDIO_SECONDS = 60 * 60
MAX_AUDIO_SAMPLE_RATE = 192_000
MAX_AUDIO_CHANNELS = 2
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024 * 1024
AUDIO_OPERATIONS = {
    "audio_transcription",
    "audio_speech",
    "audio_process",
}


class ModelWorkerConfigurationError(RuntimeError):
    pass


def _request_root(context: ModelWorkerContext, request_id: str) -> Path:
    base = context.data_root / "requests"
    base.mkdir(parents=True, exist_ok=True)
    safe_id = hashlib.sha256(request_id.encode("utf-8", errors="replace")).hexdigest()[:16]
    return Path(tempfile.mkdtemp(prefix=f"{safe_id}-", dir=base))


def _validate_wav(path: Path) -> None:
    try:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_rate = source.getframerate()
            frames = source.getnframes()
    except (OSError, EOFError, wave.Error) as exc:
        raise ModelWorkerError(
            "Audio input must be a valid WAV/PCM container",
            code="unsupported_audio_format",
            status_code=415,
        ) from exc
    if channels < 1 or channels > MAX_AUDIO_CHANNELS:
        raise ModelWorkerError(
            "Audio input has an unsupported channel count",
            code="unsupported_audio_format",
            status_code=415,
        )
    if sample_rate < 1 or sample_rate > MAX_AUDIO_SAMPLE_RATE:
        raise ModelWorkerError(
            "Audio input has an unsupported sample rate",
            code="unsupported_audio_format",
            status_code=415,
        )
    if frames / sample_rate > MAX_AUDIO_SECONDS:
        raise ModelWorkerError(
            "Audio input exceeds the decoded duration limit",
            code="audio_too_large",
            status_code=413,
        )


async def _multipart_payload(
    request: Request,
    *,
    context: ModelWorkerContext,
    request_id: str,
    operation: str,
    root: Path,
) -> tuple[dict[str, Any], dict[str, ModelWorkerPart], Path]:
    payload: dict[str, Any] = {}
    parts: dict[str, ModelWorkerPart] = {}
    try:
        async with request.form(
            max_files=MAX_MULTIPART_PARTS,
            max_fields=MAX_MULTIPART_PARTS * 4,
            max_part_size=MAX_MULTIPART_FILE_BYTES,
        ) as form:
            if len(form) > MAX_MULTIPART_PARTS * 4:
                raise ModelWorkerError(
                    "Multipart request has too many fields",
                    code="invalid_multipart",
                    status_code=400,
                )
            for name, value in form.multi_items():
                if not isinstance(name, str) or not name or len(name) > 128:
                    raise ModelWorkerError(
                        "Multipart field name is invalid",
                        code="invalid_multipart",
                        status_code=400,
                    )
                if isinstance(value, UploadFile):
                    if name in parts or len(parts) >= MAX_MULTIPART_PARTS:
                        raise ModelWorkerError(
                            "Multipart file parts are invalid",
                            code="invalid_multipart",
                            status_code=400,
                        )
                    filename = Path(value.filename or "upload.bin").name[:255]
                    # Host-side audio normalization guarantees that audio crossing
                    # the Worker boundary is PCM WAV.  Keep the trusted extension
                    # because downstream audio engines use it to select a decoder.
                    # The WAV header is still validated below before invocation.
                    suffix = ".wav" if operation in AUDIO_OPERATIONS else ".part"
                    destination = root / f"{len(parts):02d}-{uuid.uuid4().hex}{suffix}"
                    digest = hashlib.sha256()
                    size = 0
                    with destination.open("xb") as target:
                        while True:
                            chunk = await value.read(1024 * 1024)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > MAX_MULTIPART_FILE_BYTES:
                                raise ModelWorkerError(
                                    "Uploaded file exceeds the request limit",
                                    code="audio_too_large",
                                    status_code=413,
                                )
                            digest.update(chunk)
                            target.write(chunk)
                    media_type = (value.content_type or "application/octet-stream").lower()
                    if operation in AUDIO_OPERATIONS:
                        if media_type not in {
                            "audio/wav",
                            "audio/x-wav",
                            "audio/vnd.wave",
                            "application/octet-stream",
                        }:
                            raise ModelWorkerError(
                                "The Package audio protocol currently accepts WAV only",
                                code="unsupported_audio_format",
                                status_code=415,
                            )
                        _validate_wav(destination)
                        media_type = "audio/wav"
                    part = ModelWorkerPart(
                        name=name,
                        path=destination,
                        media_type=media_type,
                        filename=filename,
                        size=size,
                        sha256=digest.hexdigest(),
                    )
                    parts[name] = part
                    payload[name] = {"part": name}
                else:
                    encoded = str(value).encode("utf-8")
                    if len(encoded) > MAX_MULTIPART_FIELD_BYTES:
                        raise ModelWorkerError(
                            "Multipart text field exceeds the request limit",
                            code="invalid_multipart",
                            status_code=413,
                        )
                    payload[name] = str(value)
        return payload, parts, root
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def _load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelWorkerConfigurationError("Model Worker config is unreadable") from exc
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise ModelWorkerConfigurationError("Unsupported Model Worker config")
    return value


def _context(config: Mapping[str, Any]) -> ModelWorkerContext:
    # These canonical absolute paths are written by the trusted Host before it
    # enters the sandbox. Re-resolving them here traverses parent directories
    # (notably /private on macOS) that the Worker intentionally cannot inspect.
    package_root = Path(str(config["package_root"]))
    data_root = Path(str(config["data_root"]))
    adapter_path = Path(str(config["adapter_path"]))
    if not all(path.is_absolute() for path in (package_root, data_root, adapter_path)):
        raise ModelWorkerConfigurationError("Model Worker paths must be absolute")
    try:
        adapter_path.relative_to(package_root)
    except ValueError as exc:
        raise ModelWorkerConfigurationError("Adapter escapes the Package root") from exc
    models = config.get("models", [])
    if not isinstance(models, list) or not all(isinstance(item, dict) for item in models):
        raise ModelWorkerConfigurationError("Model declarations are invalid")
    checkpoints_raw = config.get("checkpoints", [])
    if not isinstance(checkpoints_raw, list) or not all(
        isinstance(item, dict) for item in checkpoints_raw
    ):
        raise ModelWorkerConfigurationError("Checkpoint declarations are invalid")
    checkpoints: list[ModelWorkerCheckpoint] = []
    for item in checkpoints_raw:
        path_value = item.get("path")
        path = Path(path_value) if isinstance(path_value, str) else None
        if path is not None and not path.is_absolute():
            raise ModelWorkerConfigurationError("Checkpoint paths must be absolute")
        preparation = item.get("preparation", {})
        if not isinstance(preparation, dict):
            raise ModelWorkerConfigurationError("Checkpoint preparation is invalid")
        checkpoints.append(
            ModelWorkerCheckpoint(
                model_id=str(item["model_id"]),
                upstream_id=str(item["upstream_id"]),
                provider=str(item["provider"]),
                repo_id=str(item["repo_id"]),
                revision=str(item["revision"]),
                path=path,
                preparation=preparation,
            )
        )
    cache = os.environ.get("AI2APPS_HF_CACHE_ROOT")
    return ModelWorkerContext(
        service_id=str(config["service_id"]),
        package_root=package_root,
        data_root=data_root,
        models=tuple(models),
        checkpoints=tuple(checkpoints),
        huggingface_cache_root=Path(cache).resolve() if cache else None,
    )


async def _load_adapter(config: Mapping[str, Any], context: ModelWorkerContext) -> Any:
    adapter_path = Path(str(config["adapter_path"]))
    factory_name = str(config["adapter_factory"])
    module_name = f"_ai2apps_model_package_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, adapter_path)
    if spec is None or spec.loader is None:
        raise ModelWorkerConfigurationError("Could not load Model Package adapter")
    module = importlib.util.module_from_spec(spec)
    # Imports from Package-local modules are allowed only inside this Worker.
    # Package-local imports remain available for lazy model/engine loading.
    # This path mutation occurs only in the isolated Worker, never the Host.
    for local_path in (str(adapter_path.parent), str(context.package_root)):
        if local_path not in sys.path:
            sys.path.insert(0, local_path)
    spec.loader.exec_module(module)
    factory = getattr(module, factory_name, None)
    if not callable(factory):
        raise ModelWorkerConfigurationError(f"Adapter factory is missing: {factory_name}")
    adapter = factory(context)
    if inspect.isawaitable(adapter):
        adapter = await adapter
    if not callable(getattr(adapter, "invoke", None)):
        raise ModelWorkerConfigurationError("Adapter must implement invoke(request)")
    return adapter


async def _maybe_call(target: Any, name: str) -> None:
    operation = getattr(target, name, None)
    if callable(operation):
        result = operation()
        if inspect.isawaitable(result):
            await result


def create_app(config_path: str | Path, *, token: str | None = None) -> FastAPI:
    config = _load_config(Path(config_path))
    context = _context(config)
    expected_token = token if token is not None else os.environ.get("AI2APPS_MODEL_WORKER_TOKEN")
    if not expected_token:
        raise ModelWorkerConfigurationError("Model Worker authentication token is missing")
    state: dict[str, Any] = {
        "adapter": None,
        "invocation_lock": asyncio.Lock(),
        "requests": {},
        "accepting_requests": True,
    }

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        adapter = await _load_adapter(config, context)
        state["adapter"] = adapter
        await _maybe_call(adapter, "start")
        try:
            yield
        finally:
            await _maybe_call(adapter, "stop")
            state["adapter"] = None

    app = FastAPI(title="AI2Apps Model Worker", version="1", lifespan=lifespan)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        provided = request.headers.get("authorization", "")
        if not secrets.compare_digest(provided, f"Bearer {expected_token}"):
            return JSONResponse(
                {"error": {"code": "worker_unauthorized", "message": "Unauthorized"}},
                status_code=401,
            )
        return await call_next(request)

    @app.get("/health")
    async def health():
        return {
            "status": "ready" if state["adapter"] is not None else "starting",
            "protocol": PROTOCOL,
            "service": context.service_id,
        }

    @app.get("/v1/models")
    async def models():
        return {
            "object": "list",
            "data": [
                {
                    "id": model.get("upstream_id", model.get("id")),
                    "object": "model",
                    "owned_by": context.service_id,
                }
                for model in context.models
            ],
        }

    @app.get("/v1/status")
    async def worker_status():
        records = state["requests"].values()
        return {
            "status": "ready" if state["adapter"] is not None else "starting",
            "protocol": PROTOCOL,
            "service": context.service_id,
            "accepting_requests": state["accepting_requests"],
            "active_requests": sum(
                1 for record in records if record.get("status") == "running"
            ),
            "queued_requests": sum(
                1 for record in records if record.get("status") == "queued"
            ),
        }

    @app.post("/v1/control/drain")
    async def drain():
        state["accepting_requests"] = False
        return {"status": "draining"}

    @app.post("/v1/control/resume")
    async def resume():
        state["accepting_requests"] = True
        return {"status": "ready"}

    @app.get("/v1/requests/{request_id}")
    async def request_status(request_id: str):
        record = state["requests"].get(request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Worker request not found")
        return dict(record)

    @app.delete("/v1/requests/{request_id}")
    async def cancel_request(request_id: str):
        record = state["requests"].get(request_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Worker request not found")
        if record["status"] not in {"queued", "running"}:
            return dict(record)
        cancel = getattr(state["adapter"], "cancel", None)
        if not callable(cancel):
            raise HTTPException(status_code=409, detail="Worker request is not cancellable")
        result = cancel(request_id)
        if inspect.isawaitable(result):
            await result
        record["cancel_requested"] = True
        return dict(record)

    @app.exception_handler(ModelWorkerError)
    async def model_worker_error(_request: Request, exc: ModelWorkerError):
        return JSONResponse(
            {
                "error": {
                    "code": exc.code,
                    "type": "model_worker_error",
                    "message": str(exc),
                }
            },
            status_code=exc.status_code,
        )

    async def invoke(operation: str, request: Request):
        if not state["accepting_requests"]:
            raise HTTPException(status_code=503, detail="Model Worker is draining")
        request_id = request.headers.get("x-request-id") or f"worker-{uuid.uuid4().hex}"
        records: dict[str, dict[str, Any]] = state["requests"]
        if len(records) >= 128:
            completed = next(
                (key for key, value in records.items()
                 if value.get("status") not in {"queued", "running"}),
                None,
            )
            if completed is not None:
                records.pop(completed, None)
        record: dict[str, Any] = {
            "request_id": request_id,
            "operation": operation,
            "status": "queued",
            "progress": None,
            "cancel_requested": False,
        }
        async def report_progress(update: Mapping[str, Any]) -> None:
            if not isinstance(update, Mapping):
                raise ModelWorkerError("Progress update must be an object")
            phase = update.get("phase")
            current = update.get("current")
            total = update.get("total")
            if (
                not isinstance(phase, str) or not phase or len(phase) > 64
                or not isinstance(current, int) or isinstance(current, bool) or current < 0
                or not isinstance(total, int) or isinstance(total, bool) or total < 1
                or current > total
            ):
                raise ModelWorkerError("Progress update is invalid")
            safe = {"phase": phase, "current": current, "total": total}
            for name in ("segment", "segments"):
                value = update.get(name)
                if value is not None:
                    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                        raise ModelWorkerError("Progress segment is invalid")
                    safe[name] = value
            record["progress"] = safe

        request_root = _request_root(context, request_id)
        output_root = request_root / "output"
        output_root.mkdir()
        parts: dict[str, ModelWorkerPart] = {}
        content_type = request.headers.get("content-type", "").lower()
        if content_type.startswith("multipart/form-data"):
            payload, parts, request_root = await _multipart_payload(
                request,
                context=context,
                request_id=request_id,
                operation=operation,
                root=request_root,
            )
        else:
            content = await request.body()
            if len(content) > MAX_JSON_BYTES:
                raise HTTPException(status_code=413, detail="Request body is too large")
            try:
                payload = json.loads(content or b"{}")
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail="Request body must be JSON") from exc
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Request body must be an object")
        worker_request = ModelWorkerRequest(
            operation=operation,
            payload=payload,
            request_id=request_id,
            parts=parts,
            output_root=output_root,
            progress=report_progress,
        )
        records[request_id] = record
        lock: asyncio.Lock = state["invocation_lock"]
        await lock.acquire()
        record["status"] = "running"
        try:
            result = state["adapter"].invoke(worker_request)
            if inspect.isawaitable(result):
                result = await result
        except BaseException:
            record["status"] = "failed"
            lock.release()
            shutil.rmtree(request_root, ignore_errors=True)
            raise
        if isinstance(result, ModelWorkerStream):
            async def serialized_chunks():
                try:
                    async for chunk in result.chunks:
                        yield chunk
                finally:
                    record["status"] = "succeeded"
                    lock.release()
                    shutil.rmtree(request_root, ignore_errors=True)

            return StreamingResponse(
                serialized_chunks(),
                status_code=result.status_code,
                media_type=result.media_type,
                headers=dict(result.headers or {}),
            )
        if isinstance(result, ModelWorkerArtifact):
            artifact = result.path
            if artifact.parent != output_root or artifact.name in {"", ".", ".."}:
                lock.release()
                shutil.rmtree(request_root, ignore_errors=True)
                raise ModelWorkerError(
                    "Artifact must be a direct child of the request output root",
                    code="invalid_output_artifact",
                    status_code=500,
                )
            root_descriptor = None
            try:
                root_descriptor = os.open(
                    output_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                )
                descriptor = os.open(
                    artifact.name,
                    os.O_RDONLY | os.O_NOFOLLOW,
                    dir_fd=root_descriptor,
                )
            except OSError as exc:
                lock.release()
                shutil.rmtree(request_root, ignore_errors=True)
                raise ModelWorkerError(
                    "Artifact cannot be opened safely",
                    code="invalid_output_artifact",
                    status_code=500,
                ) from exc
            finally:
                if root_descriptor is not None:
                    os.close(root_descriptor)
            descriptor_stat = os.fstat(descriptor)
            if not stat.S_ISREG(descriptor_stat.st_mode) or descriptor_stat.st_size > MAX_ARTIFACT_BYTES:
                os.close(descriptor)
                lock.release()
                shutil.rmtree(request_root, ignore_errors=True)
                raise ModelWorkerError(
                    "Artifact is not a supported output file",
                    code="invalid_output_artifact",
                    status_code=500,
                )

            async def artifact_chunks():
                try:
                    while chunk := await asyncio.to_thread(os.read, descriptor, 1024 * 1024):
                        yield chunk
                finally:
                    record["status"] = "succeeded"
                    os.close(descriptor)
                    lock.release()
                    shutil.rmtree(request_root, ignore_errors=True)

            filename = (Path(result.filename).name or "result.bin").replace('"', "_")
            return StreamingResponse(
                artifact_chunks(),
                media_type=result.media_type,
                headers={
                    "content-length": str(descriptor_stat.st_size),
                    "content-disposition": f'attachment; filename="{filename}"',
                },
            )
        lock.release()
        shutil.rmtree(request_root, ignore_errors=True)
        record["status"] = "succeeded"
        if isinstance(result, ModelWorkerResponse):
            return Response(
                content=result.content,
                status_code=result.status_code,
                media_type=result.media_type,
                headers=dict(result.headers or {}),
            )
        if isinstance(result, Mapping):
            return JSONResponse(dict(result))
        raise HTTPException(status_code=500, detail="Adapter returned an unsupported result")

    for operation, path in OPERATIONS.items():
        async def endpoint(request: Request, _operation: str = operation):
            return await invoke(_operation, request)

        app.add_api_route(path, endpoint, methods=["POST"], name=operation)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="AI2Apps system Model Worker")
    parser.add_argument("--config", required=True)
    endpoint = parser.add_mutually_exclusive_group(required=True)
    endpoint.add_argument("--port", type=int)
    endpoint.add_argument("--uds")
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    args = parser.parse_args()
    try:
        from setproctitle import setproctitle

        setproctitle("ai2apps-model-worker")
    except ImportError:  # pragma: no cover - optional in source environments
        pass
    app = create_app(args.config)
    if args.uds:
        uvicorn.run(app, uds=args.uds, access_log=False)
    else:
        uvicorn.run(app, host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
