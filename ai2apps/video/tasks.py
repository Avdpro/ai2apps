"""Durable AI2Apps video-generation queue and Artifact materialization."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import ipaddress
import json
import mimetypes
import shutil
import socket
import uuid
import wave
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import av
import httpx
from PIL import Image

from ai2apps.core import (
    AppInstanceMode,
    AppInstanceStatus,
    SessionKind,
    SessionRetention,
    SessionVisibility,
    SingletonScope,
    utc_now_text,
)
from ai2apps.model_providers import (
    PackageModel,
)
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import AppRepository, SessionRepository
from ai2apps.video_policy import (
    H3_PADDED_RESOLUTIONS,
    effective_video_capabilities,
    is_h3_video_model,
    is_temporarily_disabled_video_model,
)
from ai2apps.workspace import WorkspaceRepository

MAX_INPUT_BYTES = 100 * 1024 * 1024
MAX_DATA_URL_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 64 * 1024 * 1024
MAX_TASKS_PER_LIST = 100
REDIRECT_LIMIT = 5


class VideoGenerationError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _percent(progress: dict[str, Any]) -> float:
    current, total = progress.get("current"), progress.get("total")
    if isinstance(current, int) and isinstance(total, int) and total > 0:
        return round(min(100.0, max(0.0, current * 100.0 / total)), 2)
    return 0.0


def _public_address(host: str, port: int) -> None:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise VideoGenerationError("input_download_failed", "Input host did not resolve") from exc
    if not addresses:
        raise VideoGenerationError("input_download_failed", "Input host did not resolve")
    for address in addresses:
        value = ipaddress.ip_address(address[4][0].split("%", 1)[0])
        if not value.is_global:
            raise VideoGenerationError(
                "unsafe_input_url", "Input URL resolves to a non-public address"
            )


class VideoTaskManager:
    """One-device durable queue; Model Packages remain single-invocation adapters."""

    def __init__(
        self,
        *,
        runtime: Any,
        database: PlatformDatabase,
        workspace: WorkspaceRepository,
        root: Path,
    ) -> None:
        self.runtime = runtime
        self.database = database
        self.workspace = workspace
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._dispatcher: asyncio.Task[None] | None = None
        self._running: dict[str, asyncio.Task[None]] = {}
        self._closing = False
        self._artifact_session_id: str | None = None

    async def startup(self) -> None:
        if self._dispatcher is not None:
            return
        self._closing = False
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                "SELECT id, request_json FROM video_generation_tasks "
                "WHERE status IN ('queued','running') ORDER BY created_at, id"
            ).fetchall()
            for row in rows:
                request = json.loads(row["request_json"])
                resumable = request.get("preset") == "exact" or bool(request.get("_avatar_model"))
                if row["id"] and resumable:
                    connection.execute(
                        "UPDATE video_generation_tasks SET status='queued', "
                        "progress_json=?, updated_at=? WHERE id=?",
                        (_json({"phase": "queued", "current": 0, "total": 1}), now, row["id"]),
                    )
                elif row["id"]:
                    connection.execute(
                        "UPDATE video_generation_tasks SET status='failed', error_json=?, "
                        "completed_at=?, updated_at=? WHERE id=?",
                        (
                            _json({"code": "worker_interrupted", "message": "Host restarted"}),
                            now,
                            now,
                            row["id"],
                        ),
                    )
        self._dispatcher = asyncio.create_task(self._dispatch(), name="ai2apps-video-tasks")
        for row in rows:
            request = json.loads(row["request_json"])
            if request.get("preset") == "exact" or request.get("_avatar_model"):
                self._queue.put_nowait(str(row["id"]))

    async def shutdown(self) -> None:
        self._closing = True
        running = tuple(self._running)
        for task_id in running:
            row = self._row(task_id)
            resume = (row is not None and not row["cancel_requested_at"]
                      and bool(json.loads(row["request_json"]).get("_avatar_model")))
            await self.cancel(task_id, actor_id=None, shutdown=True)
            job = self._running.get(task_id)
            if job is not None:
                with suppress(asyncio.CancelledError):
                    await job
            if resume:
                with self.database.transaction(write=True) as connection:
                    connection.execute(
                        "UPDATE video_generation_tasks SET status='queued', cancel_requested_at=NULL, "
                        "completed_at=NULL, error_json=NULL, updated_at=? WHERE id=? "
                        "AND status='cancelled' AND cancel_requested_at IS NULL",
                        (utc_now_text(), task_id))
        if self._dispatcher is not None:
            self._dispatcher.cancel()
            with suppress(asyncio.CancelledError):
                await self._dispatcher
        self._dispatcher = None
        if self._running:
            await asyncio.gather(*tuple(self._running.values()), return_exceptions=True)

    def _model(self, model_id: str) -> PackageModel:
        invocations = getattr(self.runtime, "model_invocations", None)
        model = None if invocations is None else invocations.model(model_id)
        if model is None:
            raise VideoGenerationError(
                "model_not_found", f"Video model provider not found: {model_id}", status_code=404
            )
        if model.model_type != "video_generation":
            raise VideoGenerationError(
                "invalid_model_type", "Selected model is not a video generator"
            )
        if is_temporarily_disabled_video_model(model):
            raise VideoGenerationError(
                "model_temporarily_disabled",
                "H3 16-bit inference is temporarily disabled while output quality is under validation; select the 8-bit or 4-bit model.",
                status_code=409,
            )
        if not model.checkpoint_ready:
            raise VideoGenerationError(
                "model_unavailable", "The model checkpoint is not installed", status_code=503
            )
        return model

    @staticmethod
    def _owner_actor_id(actor_id: str) -> str:
        """Normalize owners emitted by both current and older Runtime routes."""

        prefix = "ai2apps-user:"
        if actor_id.startswith(prefix):
            return actor_id[len(prefix) :]
        return actor_id

    @classmethod
    def _background_actor_id(
        cls, actor_id: str, invocation_actor_id: str | None
    ) -> str:
        if invocation_actor_id:
            return invocation_actor_id
        if actor_id.startswith("local-api:"):
            return "local"
        return cls._owner_actor_id(actor_id)

    @staticmethod
    def _effective_request(payload: dict[str, Any], model: PackageModel) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise VideoGenerationError("invalid_request", "Request must be an object")
        content = payload.get("content")
        if not isinstance(content, list) or not content:
            raise VideoGenerationError("invalid_content", "content must be a non-empty array")
        caps = effective_video_capabilities(model)
        defaults = dict(caps.get("defaults") or {})
        effective = dict(payload)
        for key in (
            "resolution",
            "ratio",
            "framespersecond",
            "preset",
            "seed",
            "output_format",
            "audio_output_mode",
        ):
            if effective.get(key) is None and defaults.get(key) is not None:
                effective[key] = defaults[key]
        avatar_mode = effective.get("avatar_output_mode")
        if avatar_mode is not None and (
            not isinstance(avatar_mode, str) or avatar_mode not in {"source", "crop"}
            or "avatar_video" not in getattr(model, "capabilities", ())
        ):
            raise VideoGenerationError("unsupported_parameter", "avatar_output_mode is unsupported")
        resolution = str(effective.get("resolution") or "")
        if "x" in resolution:
            try:
                width, height = (int(item) for item in resolution.lower().split("x", 1))
            except ValueError as exc:
                raise VideoGenerationError("unsupported_parameter", "resolution is invalid") from exc
            effective["width"], effective["height"] = width, height
        if effective.get("framespersecond") is not None:
            effective["fps"] = effective["framespersecond"]
        geometry = dict(caps.get("geometry") or {})
        if resolution and resolution not in geometry.get("resolutions", []):
            raise VideoGenerationError("unsupported_parameter", "resolution is not supported")
        ratio = effective.get("ratio")
        if ratio is not None and ratio not in geometry.get("ratios", []):
            raise VideoGenerationError("unsupported_parameter", "ratio is not supported")
        fps = effective.get("framespersecond")
        if fps is not None and fps not in geometry.get("framespersecond", []):
            raise VideoGenerationError("unsupported_parameter", "framespersecond is not supported")
        preset = effective.get("preset")
        preset_ids = {
            item.get("id") for item in caps.get("presets", []) if isinstance(item, dict)
        }
        if preset not in preset_ids:
            raise VideoGenerationError("unsupported_parameter", "preset is not supported")
        effective["fast"] = preset == "fast"
        effective["fast_max"] = preset == "fast_max"
        if effective.get("duration") == "auto":
            effective.pop("duration")
        duration = effective.get("duration")
        duration_caps = dict(caps.get("duration") or {})
        if duration is not None:
            if isinstance(duration, bool) or not isinstance(duration, (int, float)):
                raise VideoGenerationError("unsupported_parameter", "duration must be numeric or auto")
            minimum = duration_caps.get("minimum_seconds")
            maximum = duration_caps.get("maximum_seconds")
            if (minimum is not None and duration < minimum) or (
                maximum is not None and duration > maximum
            ):
                raise VideoGenerationError("unsupported_parameter", "duration is not supported")
        counts: dict[tuple[str, str], int] = {}
        for item in content:
            if not isinstance(item, dict):
                raise VideoGenerationError("invalid_content", "content items must be objects")
            key = (str(item.get("type")), str(item.get("role")))
            counts[key] = counts.get(key, 0) + 1
        reference_count = sum(
            count
            for (_content_type, role), count in counts.items()
            if role in {"reference_image", "reference_video", "reference_audio"}
        )
        if reference_count > 12:
            raise VideoGenerationError(
                "unsupported_content_combination",
                "reference_image, reference_video, and reference_audio are limited to 12 files total",
            )
        matched = False
        for combination in caps.get("content_combinations", []):
            if not isinstance(combination, dict):
                continue
            rules = [
                item
                for group in ("required", "optional")
                for item in combination.get(group, [])
                if isinstance(item, dict)
            ]
            allowed = {(str(rule["type"]), str(rule["role"])) for rule in rules}
            if set(counts) - allowed:
                continue
            if all(
                int(rule.get("min", 0))
                <= counts.get((str(rule["type"]), str(rule["role"])), 0)
                <= int(rule.get("max", 1))
                for rule in rules
            ):
                matched = True
                break
        if not matched:
            raise VideoGenerationError(
                "unsupported_content_combination",
                "content does not match a combination declared by the model",
            )
        if len(_json(effective).encode()) > 64 * 1024:
            raise VideoGenerationError("request_too_large", "Video request metadata is too large")
        callback = effective.get("callback_url")
        if callback is not None:
            raise VideoGenerationError(
                "unsupported_parameter", "callback_url is not enabled in this Host build"
            )
        return effective

    async def create(
        self,
        payload: dict[str, Any],
        *,
        actor_id: str,
        invocation_actor_id: str | None = None,
        idempotency_key: str | None = None,
        uploads: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        invocation_actor_id = self._background_actor_id(
            actor_id, invocation_actor_id
        )
        actor_id = self._owner_actor_id(actor_id)
        model_id = str(payload.get("model") or "").strip()
        if not model_id:
            raise VideoGenerationError("invalid_request", "model is required")
        model = self._model(model_id)
        effective = self._effective_request(payload, model)
        task_id = f"vgt_{uuid.uuid4().hex}"
        task_root = self.root / task_id
        task_root.mkdir(mode=0o700)
        try:
            worker, manifest = await self._freeze_inputs(
                effective, task_root, uploads or {}
            )
            from ai2apps.avatar.segmented_inference import supports_segments, model_identity
            if supports_segments(model):
                worker["_avatar_model"] = model_identity(self.runtime, model)
            else:
                worker.pop("_avatar_model", None)
            canonical = {
                "request": effective,
                "inputs": [{k: v for k, v in item.items() if k != "path"} for item in manifest],
                "model_revision": str((model.weights or {}).get("revision") or ""),
            }
            request_hash = "sha256:" + hashlib.sha256(_json(canonical).encode()).hexdigest()
            now = utc_now_text()
            with self.database.transaction(write=True) as connection:
                if idempotency_key:
                    existing = connection.execute(
                        "SELECT * FROM video_generation_tasks WHERE actor_id=? "
                        "AND idempotency_key=?",
                        (actor_id, idempotency_key),
                    ).fetchone()
                    if existing is not None:
                        if existing["request_hash"] != request_hash:
                            raise VideoGenerationError(
                                "idempotency_conflict",
                                "Idempotency-Key was already used for a different request",
                                status_code=409,
                            )
                        shutil.rmtree(task_root, ignore_errors=True)
                        return self._response(existing)
                connection.execute(
                    """INSERT INTO video_generation_tasks(
                        id,actor_id,invocation_actor_id,model_id,model_revision,status,request_json,request_hash,
                        idempotency_key,progress_json,input_manifest_json,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        task_id,
                        actor_id,
                        invocation_actor_id,
                        model.id,
                        str((model.weights or {}).get("revision") or ""),
                        "queued",
                        _json(worker),
                        request_hash,
                        idempotency_key,
                        _json({"phase": "queued", "current": 0, "total": 1}),
                        _json(manifest),
                        now,
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM video_generation_tasks WHERE id=?", (task_id,)
                ).fetchone()
            self._queue.put_nowait(task_id)
            return self._response(row)
        except BaseException:
            if not self._task_exists(task_id):
                shutil.rmtree(task_root, ignore_errors=True)
            raise

    def _task_exists(self, task_id: str) -> bool:
        with self.database.transaction() as connection:
            return connection.execute(
                "SELECT 1 FROM video_generation_tasks WHERE id=?", (task_id,)
            ).fetchone() is not None

    async def _freeze_inputs(
        self,
        payload: dict[str, Any],
        task_root: Path,
        uploads: dict[str, tuple[str, bytes, str]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        inputs_root = task_root / "inputs"
        inputs_root.mkdir()
        worker = {key: value for key, value in payload.items() if key != "content"}
        manifest: list[dict[str, Any]] = []
        prompt: str | None = None
        singleton_roles: set[str] = set()
        reference_parts: list[dict[str, str]] = []
        repeatable_roles = {"reference_image", "reference_video", "reference_audio"}
        part_names = {
            "reference_image": "image",
            "first_frame": "first_frame",
            "last_frame": "last_frame",
            "driving_audio": "audio",
            "source_video": "source_video",
        }
        for index, item in enumerate(payload["content"]):
            if not isinstance(item, dict):
                raise VideoGenerationError("invalid_content", "content items must be objects")
            item_type, role = item.get("type"), item.get("role")
            if not isinstance(role, str):
                raise VideoGenerationError("invalid_content", "content roles must be strings")
            if role not in repeatable_roles:
                if role in singleton_roles:
                    raise VideoGenerationError("invalid_content", "content roles must be unique")
                singleton_roles.add(role)
            if item_type == "text" and role == "prompt":
                prompt = str(item.get("text") or "").strip()
                if not prompt:
                    raise VideoGenerationError("invalid_content", "prompt must not be empty")
                continue
            if role in repeatable_roles:
                kind = role.removeprefix("reference_")
                part_name = f"reference_{len(reference_parts):02d}_{kind}"
                reference_parts.append({"kind": kind, "part_name": part_name})
            else:
                part_name = part_names.get(str(role))
            field = {
                "image_url": "image_url",
                "audio_url": "audio_url",
                "video_url": "video_url",
            }.get(str(item_type))
            if part_name is None or field is None:
                raise VideoGenerationError(
                    "unsupported_content", f"Unsupported content type/role: {item_type}/{role}"
                )
            locator = item.get(field)
            url = locator.get("url") if isinstance(locator, dict) else None
            if not isinstance(url, str) or not url:
                raise VideoGenerationError("invalid_content", f"{field}.url is required")
            filename, data, media_type = await self._resolve_input(url, uploads)
            if len(data) > MAX_INPUT_BYTES:
                raise VideoGenerationError("input_too_large", "Input exceeds 100 MiB", status_code=413)
            self._validate_media(data, media_type, item_type, role)
            suffix = Path(filename).suffix or mimetypes.guess_extension(media_type) or ".bin"
            destination = inputs_root / f"{index:02d}-{part_name}{suffix[:12]}"
            destination.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            manifest.append(
                {
                    "part_name": part_name,
                    "path": str(destination.relative_to(task_root)),
                    "filename": Path(filename).name[:255],
                    "media_type": media_type,
                    "size": len(data),
                    "sha256": digest,
                }
            )
        if prompt is not None:
            worker["prompt"] = prompt
        if reference_parts:
            worker["reference_parts"] = reference_parts
        return worker, manifest

    async def _resolve_input(
        self, url: str, uploads: dict[str, tuple[str, bytes, str]]
    ) -> tuple[str, bytes, str]:
        if url.startswith("multipart://"):
            name = url.removeprefix("multipart://")
            try:
                return uploads[name]
            except KeyError as exc:
                raise VideoGenerationError(
                    "missing_multipart_part", f"Multipart part is missing: {name}"
                ) from exc
        if url.startswith("artifact://"):
            artifact_id = url.removeprefix("artifact://")
            with self.database.transaction() as connection:
                row = connection.execute(
                    "SELECT * FROM artifacts WHERE id=? AND status='active'", (artifact_id,)
                ).fetchone()
            if row is None:
                raise VideoGenerationError("artifact_not_found", "Input Artifact was not found", status_code=404)
            path = self.workspace.paths.artifacts_path / row["storage_key"]
            return row["name"], path.read_bytes(), row["media_type"]
        if url.startswith("data:"):
            header, separator, encoded = url.partition(",")
            if not separator or not header.endswith(";base64"):
                raise VideoGenerationError("invalid_data_url", "Only base64 data URLs are supported")
            media_type = header[5:-7].lower()
            try:
                data = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise VideoGenerationError("invalid_data_url", "Data URL is invalid") from exc
            if len(data) > MAX_DATA_URL_BYTES:
                raise VideoGenerationError("input_too_large", "Data URL exceeds 8 MiB", status_code=413)
            return "inline" + (mimetypes.guess_extension(media_type) or ".bin"), data, media_type
        if url.startswith("https://"):
            return await self._download_https(url)
        raise VideoGenerationError(
            "unsafe_input_url", "Only artifact://, multipart://, data:, and HTTPS inputs are allowed"
        )

    async def _download_https(self, url: str) -> tuple[str, bytes, str]:
        current = url
        async with httpx.AsyncClient(timeout=30.0, trust_env=False, follow_redirects=False) as client:
            for _ in range(REDIRECT_LIMIT + 1):
                parsed = urlparse(current)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    raise VideoGenerationError("unsafe_input_url", "Input URL must be public HTTPS")
                _public_address(parsed.hostname, parsed.port or 443)
                async with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise VideoGenerationError("input_download_failed", "Redirect has no location")
                        current = urljoin(current, location)
                        continue
                    if response.status_code != 200:
                        raise VideoGenerationError(
                            "input_download_failed", f"Input download returned HTTP {response.status_code}"
                        )
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_INPUT_BYTES:
                            raise VideoGenerationError(
                                "input_too_large", "Downloaded input exceeds 100 MiB", status_code=413
                            )
                    media_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0].lower()
                    filename = Path(urlparse(current).path).name or "download.bin"
                    return filename, bytes(data), media_type
        raise VideoGenerationError("input_download_failed", "Input redirected too many times")

    @staticmethod
    def _validate_media(data: bytes, media_type: str, item_type: str, role: str) -> None:
        if item_type == "image_url":
            if media_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise VideoGenerationError("unsupported_media_type", "Image must be PNG, JPEG, or WebP")
            try:
                with Image.open(BytesIO(data)) as image:
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise VideoGenerationError("input_too_large", "Image pixel count is too large")
                    image.verify()
            except VideoGenerationError:
                raise
            except Exception as exc:
                raise VideoGenerationError("invalid_media", "Image input is invalid") from exc
        elif item_type == "audio_url" and role != "reference_audio" and media_type not in {
            "audio/wav", "audio/x-wav", "audio/vnd.wave", "application/octet-stream"
        }:
            raise VideoGenerationError("unsupported_media_type", "Driving audio must be WAV")
        elif item_type == "audio_url" and role != "reference_audio":
            try:
                with wave.open(BytesIO(data), "rb") as audio:
                    rate = audio.getframerate()
                    frames = audio.getnframes()
                    channels = audio.getnchannels()
                if not 1 <= channels <= 2 or not 8_000 <= rate <= 192_000:
                    raise VideoGenerationError("invalid_media", "WAV format is unsupported")
                if frames / rate > 60 * 60:
                    raise VideoGenerationError("input_too_large", "WAV duration exceeds one hour")
            except VideoGenerationError:
                raise
            except (EOFError, wave.Error) as exc:
                raise VideoGenerationError("invalid_media", "Driving audio is not valid WAV") from exc
        elif item_type in {"audio_url", "video_url"}:
            allowed = (
                {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/x-m4a", "audio/flac", "application/octet-stream"}
                if item_type == "audio_url"
                else {"video/mp4", "video/quicktime", "video/webm", "application/octet-stream"}
            )
            if media_type not in allowed:
                raise VideoGenerationError("unsupported_media_type", "Reference media format is not supported")
            try:
                with av.open(BytesIO(data)) as container:
                    streams = container.streams.audio if item_type == "audio_url" else container.streams.video
                    if not streams:
                        raise VideoGenerationError("invalid_media", "Reference media has no decodable stream")
                    stream = streams[0]
                    duration = (
                        float(stream.duration * stream.time_base)
                        if stream.duration is not None and stream.time_base is not None
                        else (
                            float(container.duration / av.time_base)
                            if container.duration is not None
                            else None
                        )
                    )
                    if role == "source_video" and duration is not None and duration <= 0:
                        raise VideoGenerationError("invalid_media", "Source video duration must be positive")
                    if role != "source_video" and duration is not None and not 2.0 <= duration <= 15.1:
                        raise VideoGenerationError(
                            "unsupported_parameter",
                            "Reference video and audio duration must be between 2 and 15 seconds",
                        )
            except VideoGenerationError:
                raise
            except Exception as exc:
                raise VideoGenerationError("invalid_media", "Reference media is invalid") from exc

    async def _dispatch(self) -> None:
        while True:
            task_id = await self._queue.get()
            if self._closing:
                return
            row = self._row(task_id)
            if row is None or row["status"] != "queued":
                continue
            task = asyncio.create_task(self._run(task_id), name=f"video-{task_id}")
            self._running[task_id] = task
            try:
                await task
            finally:
                self._running.pop(task_id, None)

    async def _run(self, task_id: str) -> None:
        row = self._row(task_id)
        if row is None:
            return
        try:
            model = self._model(row["model_id"])
            request = json.loads(row["request_json"])
            manifest = json.loads(row["input_manifest_json"])
            output = await self._invoke(task_id, model, request, manifest)
            artifact = await asyncio.to_thread(self._materialize_artifact, task_id, model, output)
            self._update(
                task_id,
                status="succeeded",
                progress={"phase": "completed", "current": 1, "total": 1},
                artifact_id=artifact.id,
                artifact_session_id=artifact.session_id,
                completed_at=utc_now_text(),
            )
        except asyncio.CancelledError:
            self._update(
                task_id,
                status="cancelled",
                error={"code": "cancelled", "message": "Video generation was cancelled"},
                completed_at=utc_now_text(),
            )
            raise
        except Exception as exc:
            code = getattr(exc, "code", "generation_failed")
            self._update(
                task_id,
                status="cancelled" if code == "generation_cancelled" else "failed",
                error={"code": code, "message": str(exc)},
                completed_at=utc_now_text(),
            )
        finally:
            self.prune_history(row["actor_id"])

    async def _invoke(
        self,
        task_id: str,
        model: PackageModel,
        request: dict[str, Any],
        manifest: list[dict[str, Any]],
    ) -> Path:
        task_root = self.root / task_id
        output = task_root / "result.mp4"
        body = dict(request)
        avatar_mode = body.pop("avatar_output_mode", "crop")
        requested_resolution = str(body.get("resolution") or "")
        padded_geometry = (H3_PADDED_RESOLUTIONS.get(requested_resolution)
                           if is_h3_video_model(model) else None)
        if padded_geometry is not None:
            body["width"], body["height"] = padded_geometry
        files = {
            item["part_name"]: (
                item["filename"],
                task_root / item["path"],
                item["media_type"],
            )
            for item in manifest
        }
        invocations = getattr(self.runtime, "model_invocations", None)
        if invocations is None:
            raise VideoGenerationError(
                "model_gateway_unavailable", "Model invocation service is unavailable"
            )

        def cancelled() -> bool:
            row = self._row(task_id)
            return row is not None and bool(row["cancel_requested_at"])

        row = self._row(task_id)
        context_factory = getattr(invocations, "context_for_actor", None)
        context = (
            None
            if row is None or context_factory is None
            else context_factory(
                row["invocation_actor_id"],
                session_id=f"video:{task_id}",
                consumer_app_id="ai2apps.video-studio",
            )
        )
        canvas = None
        if avatar_mode == "source":
            from ai2apps.avatar.composition import prepare_portrait

            references = [p for p in body.get("reference_parts", []) if p.get("kind") == "image"]
            if len(references) != 1 or "audio" not in files:
                raise VideoGenerationError("invalid_content", "Source canvas requires one portrait and driving audio")
            part_name = references[0]["part_name"]
            crop_path = task_root / "avatar-crop.png"
            canvas = await asyncio.to_thread(
                prepare_portrait, files[part_name][1], crop_path,
                (int(body["width"]), int(body["height"])),
            )
            files[part_name] = (crop_path.name, crop_path, "image/png")

        def worker_progress(value):
            if padded_geometry is not None and isinstance(value, dict):
                value = dict(value)
                current, total = value.get("current"), value.get("total")
                if isinstance(current, int) and isinstance(total, int) and total > 0:
                    value["current"] = min(95, round(95 * current / total))
                    value["total"] = 100
            if canvas is not None and isinstance(value, dict):
                value = dict(value)
                percent = value.get("percent")
                if isinstance(percent, (int, float)):
                    value["percent"] = max(0, min(100, percent)) * 0.9
            self._update(task_id, progress=value)

        from ai2apps.avatar.segmented_inference import supports_segments, invoke_segmented
        if supports_segments(model):
            # Retry may reuse only the same actor's terminal task. Packets are
            # still independently checked against the new frozen identity.
            retry_of = (body.get("metadata") or {}).get("retry_of")
            previous = self._row(retry_of, row["actor_id"]) if isinstance(retry_of, str) and row else None
            source_cache = self.root / retry_of / "avatar-segments" if previous is not None else None
            target_cache = task_root / "avatar-segments"
            if (previous is not None and previous["status"] in {"failed", "cancelled", "expired"}
                    and json.loads(previous["request_json"]).get("_avatar_model") == body.get("_avatar_model")
                    and source_cache.is_dir() and not source_cache.is_symlink()
                    and not target_cache.exists()):
                from ai2apps.avatar.segmented_inference import copy_verified_cache
                await asyncio.to_thread(copy_verified_cache, source_cache, target_cache)
            await invoke_segmented(
                self.runtime, model, body, files, output,
                root=task_root / "avatar-segments", task_id=task_id,
                frozen_model=body.get("_avatar_model"), cancelled=cancelled,
                progress=worker_progress,
                admitted=lambda: self._update(task_id, status="running", started_at=utc_now_text()),
                context=context)
        else:
            await invocations.invoke_background_to_file(
                model.id,
                "video_generation",
                body,
                output,
                files=files,
                request_id=task_id,
                cancel_requested=cancelled,
                progress=worker_progress,
                on_admitted=lambda: self._update(
                    task_id,
                    status="running",
                    progress={"phase": "starting", "current": 0, "total": 1},
                    started_at=utc_now_text(),
                ),
                **({"context": context} if context is not None else {}),
            )
        if canvas is not None:
            import threading

            from ai2apps.avatar.video_composition import compose_video

            stopped = threading.Event()
            def check():
                if stopped.is_set() or cancelled():
                    raise VideoGenerationError("generation_cancelled", "Avatar composition cancelled")
            def progress(current, total):
                self._update(task_id, progress={"phase": "composition", "current": current, "total": total,
                                               "percent": 90 + min(9, 9 * current / max(total, 1))})
            work = asyncio.create_task(asyncio.to_thread(
                compose_video, output, task_root / "source-result.mp4", canvas,
                check=check, progress=progress,
            ))
            try:
                output = await asyncio.shield(work)
            except asyncio.CancelledError:
                stopped.set()
                while not work.done():
                    try:
                        await asyncio.shield(work)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if not work.cancelled():
                    work.exception()
                raise
        if padded_geometry is not None:
            from ai2apps.video.geometry import crop_video_canvas

            requested_width, requested_height = (
                int(value) for value in requested_resolution.split("x", 1)
            )
            self._update(task_id, progress={"phase": "crop", "current": 95, "total": 100})

            def check_crop():
                if cancelled():
                    raise VideoGenerationError("generation_cancelled", "Video crop cancelled")

            work = asyncio.create_task(asyncio.to_thread(
                crop_video_canvas, output, task_root / "result-cropped.mp4",
                width=requested_width, height=requested_height, check=check_crop,
            ))
            try:
                output = await asyncio.shield(work)
            except asyncio.CancelledError:
                while not work.done():
                    try:
                        await asyncio.shield(work)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if not work.cancelled():
                    work.exception()
                raise
        return output

    def _materialize_artifact(self, task_id: str, model: PackageModel, output: Path):
        session_id = self._artifact_session()
        return self.workspace.import_artifact(
            session_id,
            output,
            f"{task_id}.mp4",
            media_type="video/mp4",
            metadata={"generator": model.service_key, "model": model.id, "task_id": task_id},
        )

    def _artifact_session(self) -> str:
        if self._artifact_session_id is not None:
            return self._artifact_session_id
        package_id = "ai2apps.video-generation.internal"
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT s.id FROM sessions s
                   JOIN app_instances i ON i.id=s.app_instance_id
                   JOIN app_definitions d ON d.id=i.app_definition_id
                   WHERE d.package_id=? AND s.is_home=1 AND s.status='active'
                   ORDER BY s.created_at LIMIT 1""",
                (package_id,),
            ).fetchone()
            definition = connection.execute(
                "SELECT id FROM app_definitions WHERE package_id=?", (package_id,)
            ).fetchone()
        apps = AppRepository(self.database)
        sessions = SessionRepository(self.database)
        if row is None:
            if definition is None:
                created = apps.create_definition(
                    package_id=package_id,
                    package_version="1.0.0",
                    display_name="Video Generation Artifacts",
                    instance_mode=AppInstanceMode.SINGLETON,
                    singleton_scope=SingletonScope.SYSTEM,
                    source="builtin",
                    manifest={"schema": "ai2apps.app/v1", "internal": True},
                )
                definition_id = created.id
            else:
                definition_id = definition["id"]
            with self.database.transaction() as connection:
                existing = connection.execute(
                    "SELECT id FROM app_instances WHERE singleton_key=?",
                    (f"{package_id}:system:local",),
                ).fetchone()
            if existing is None:
                instance = apps.create_instance(
                    app_definition_id=definition_id,
                    singleton_key=f"{package_id}:system:local",
                    status=AppInstanceStatus.ACTIVE,
                )
                instance_id = instance.id
            else:
                instance_id = existing["id"]
            session = sessions.create(
                app_instance_id=instance_id,
                title="Video Generation Artifacts",
                is_home=True,
                session_kind=SessionKind.APP,
                visibility=SessionVisibility.UNLISTED,
                retention=SessionRetention.DURABLE,
            )
            self._artifact_session_id = session.id
        else:
            self._artifact_session_id = row["id"]
        return self._artifact_session_id

    def artifact_session(self) -> str:
        """Return the durable media Artifact session for first-party Studio tools."""

        return self._artifact_session()

    def _row(self, task_id: str, actor_id: str | None = None):
        query = "SELECT * FROM video_generation_tasks WHERE id=?"
        parameters: tuple[Any, ...] = (task_id,)
        if actor_id is not None:
            query += " AND actor_id=?"
            parameters += (self._owner_actor_id(actor_id),)
        with self.database.transaction() as connection:
            return connection.execute(query, parameters).fetchone()

    def _update(
        self,
        task_id: str,
        *,
        status: str | None = None,
        progress: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        artifact_id: str | None = None,
        artifact_session_id: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"updated_at": utc_now_text()}
        if status is not None:
            values["status"] = status
        if progress is not None:
            values["progress_json"] = _json(progress)
        if error is not None:
            values["error_json"] = _json(error)
        for key, value in (
            ("artifact_id", artifact_id),
            ("artifact_session_id", artifact_session_id),
            ("started_at", started_at),
            ("completed_at", completed_at),
        ):
            if value is not None:
                values[key] = value
        assignments = ",".join(f"{key}=?" for key in values)
        with self.database.transaction(write=True) as connection:
            connection.execute(
                f"UPDATE video_generation_tasks SET {assignments} WHERE id=?",
                (*values.values(), task_id),
            )

    def get(self, task_id: str, *, actor_id: str) -> dict[str, Any]:
        row = self._row(task_id, actor_id)
        if row is None:
            raise VideoGenerationError("task_not_found", "Video task was not found", status_code=404)
        return self._response(row)

    def delete(self, task_id, *, actor_id):
        row = self._row(task_id, actor_id)
        if row is None:
            raise VideoGenerationError('task_not_found', 'Video task was not found', status_code=404)
        if row['status'] not in {'succeeded','failed','cancelled','expired'}:
            raise VideoGenerationError('task_active', 'Stop the task before deleting it', status_code=409)
        if row['artifact_id']:
            self.workspace.retire_artifact(row['artifact_session_id'], row['artifact_id'])
        task_root = (self.root / row['id']).resolve()
        task_root.relative_to(self.root)
        shutil.rmtree(task_root, ignore_errors=True)
        with self.database.transaction(write=True) as connection:
            connection.execute('DELETE FROM video_generation_tasks WHERE id=?', (task_id,))

    def prune_history(self, actor_id: str) -> None:
        # Running and queued jobs are never candidates for retention cleanup.
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM video_generation_tasks WHERE actor_id=?
                   AND status IN ('succeeded','failed','cancelled','expired')
                   ORDER BY created_at DESC,id DESC LIMIT -1 OFFSET 20""",
                (self._owner_actor_id(actor_id),),
            ).fetchall()
        for row in rows:
            if row["artifact_id"]:
                self.workspace.retire_artifact(row["artifact_session_id"], row["artifact_id"])
            task_root = (self.root / row["id"]).resolve()
            task_root.relative_to(self.root)
            shutil.rmtree(task_root, ignore_errors=True)
            with self.database.transaction(write=True) as connection:
                connection.execute("DELETE FROM video_generation_tasks WHERE id=?", (row["id"],))

    def list(self, *, actor_id: str, limit: int = 20, after: str | None = None) -> dict[str, Any]:
        self.prune_history(actor_id)
        limit = max(1, min(MAX_TASKS_PER_LIST, int(limit)))
        query = "SELECT * FROM video_generation_tasks WHERE actor_id=?"
        parameters: list[Any] = [self._owner_actor_id(actor_id)]
        if after:
            query += " AND created_at < (SELECT created_at FROM video_generation_tasks WHERE id=?)"
            parameters.append(after)
        query += " ORDER BY created_at DESC,id DESC LIMIT ?"
        parameters.append(limit + 1)
        with self.database.transaction() as connection:
            rows = connection.execute(query, parameters).fetchall()
        has_more = len(rows) > limit
        items = rows[:limit]
        return {
            "object": "list",
            "data": [self._response(row) for row in items],
            "has_more": has_more,
            "next_after": items[-1]["id"] if has_more and items else None,
        }

    async def retry(self, task_id: str, *, actor_id: str) -> dict[str, Any]:
        """Create a new task from a terminal task and its frozen private inputs."""

        row = self._row(task_id, actor_id)
        if row is None:
            raise VideoGenerationError("task_not_found", "Video task was not found", status_code=404)
        if row["status"] not in {"failed", "cancelled", "expired"}:
            raise VideoGenerationError(
                "task_not_retryable", "Only failed, cancelled, or expired tasks can retry", status_code=409
            )
        payload = json.loads(row["request_json"])
        prompt = str(payload.get("prompt") or "").strip()
        content: list[dict[str, Any]] = []
        if prompt:
            content.append({"type": "text", "role": "prompt", "text": prompt})
        reference_roles = {
            str(item.get("part_name")): f"reference_{item.get('kind')}"
            for item in payload.get("reference_parts", [])
            if isinstance(item, dict)
        }
        role_types = {
            "first_frame": "image_url", "last_frame": "image_url",
            "driving_audio": "audio_url", "reference_image": "image_url",
            "reference_video": "video_url", "reference_audio": "audio_url",
            "source_video": "video_url",
        }
        uploads: dict[str, tuple[str, bytes, str]] = {}
        task_root = (self.root / task_id).resolve()
        manifest = json.loads(row["input_manifest_json"])
        if not isinstance(manifest, list):
            raise VideoGenerationError(
                "retry_input_unavailable", "The frozen inputs for this task are invalid", status_code=409
            )
        for descriptor in manifest:
            part_name = str(descriptor.get("part_name") or "")
            role = reference_roles.get(part_name) or {
                "first_frame": "first_frame", "last_frame": "last_frame", "audio": "driving_audio",
                "source_video": "source_video",
            }.get(part_name)
            item_type = role_types.get(str(role))
            source = (task_root / str(descriptor.get("path") or "")).resolve()
            if not part_name or item_type is None or task_root not in source.parents or not source.is_file():
                raise VideoGenerationError(
                    "retry_input_unavailable", "A frozen input required by this task is unavailable", status_code=409
                )
            data = source.read_bytes()
            uploads[part_name] = (
                str(descriptor.get("filename") or part_name), data,
                str(descriptor.get("media_type") or "application/octet-stream"),
            )
            content.append({item_type: {"url": f"multipart://{part_name}"}, "type": item_type, "role": role})
        payload["content"] = content
        payload.pop("prompt", None)
        payload.pop("reference_parts", None)
        payload["metadata"] = dict(payload.get("metadata") or {}) | {"retry_of": task_id}
        return await self.create(
            payload,
            actor_id=actor_id,
            invocation_actor_id=row["invocation_actor_id"],
            uploads=uploads,
        )

    async def cancel(
        self, task_id: str, *, actor_id: str | None, shutdown: bool = False
    ) -> dict[str, Any]:
        row = self._row(task_id, actor_id)
        if row is None:
            raise VideoGenerationError("task_not_found", "Video task was not found", status_code=404)
        if row["status"] in {"succeeded", "failed", "expired"}:
            if not shutdown:
                raise VideoGenerationError(
                    "task_not_cancellable",
                    "Completed task cannot be cancelled",
                    status_code=409,
                )
            return self._response(row)
        if row["status"] == "cancelled":
            return self._response(row)
        # Shutdown interrupts computation without recording a user cancellation.
        # A concurrent explicit cancel remains authoritative during requeue.
        if not shutdown:
            now = utc_now_text()
            with self.database.transaction(write=True) as connection:
                if row["status"] == "queued":
                    connection.execute(
                        "UPDATE video_generation_tasks SET status='cancelled',cancel_requested_at=?,"
                        "completed_at=?,updated_at=? WHERE id=?",
                        (now, now, now, task_id),
                    )
                else:
                    connection.execute(
                        "UPDATE video_generation_tasks SET cancel_requested_at=?,updated_at=? WHERE id=?",
                        (now, now, task_id),
                    )
        running = self._running.get(task_id)
        if running is not None:
            if row["status"] == "queued":
                running.cancel()
                with suppress(asyncio.CancelledError):
                    await running
                return self.get(task_id, actor_id=row["actor_id"])
            invocations = getattr(self.runtime, "model_invocations", None)
            if invocations is not None:
                await invocations.cancel_request(row["model_id"], task_id)
            if shutdown:
                running.cancel()
        return self.get(task_id, actor_id=row["actor_id"])

    async def join(self, task_ids: list[str], *, actor_id: str) -> dict[str, Any]:
        """Concatenate compatible completed clips and publish a new Artifact."""

        if not isinstance(task_ids, list) or not 2 <= len(task_ids) <= 50:
            raise VideoGenerationError(
                "invalid_request", "task_ids must contain between 2 and 50 tasks"
            )
        if len(set(task_ids)) != len(task_ids) or any(
            not isinstance(item, str) or not item for item in task_ids
        ):
            raise VideoGenerationError("invalid_request", "task_ids must be unique task IDs")
        if shutil.which("ffmpeg") is None:
            raise VideoGenerationError(
                "media_tool_unavailable", "ffmpeg is required to join clips", status_code=503
            )
        sources: list[Path] = []
        for task_id in task_ids:
            row = self._row(task_id, actor_id)
            if row is None:
                raise VideoGenerationError(
                    "task_not_found", "A selected video task was not found", status_code=404
                )
            if row["status"] != "succeeded" or not row["artifact_id"]:
                raise VideoGenerationError(
                    "task_not_complete", "Every selected task must have completed successfully"
                )
            artifact = self.workspace.get_artifact(
                row["artifact_session_id"], row["artifact_id"]
            )
            sources.append(self.workspace.artifact_path(artifact))
        join_id = f"video-join-{uuid.uuid4().hex}"
        join_root = self.root / join_id
        join_root.mkdir(mode=0o700)
        listing = join_root / "clips.txt"
        destination = join_root / "joined.mp4"
        listing.write_text(
            "".join(f"file '{source.as_posix()}'\n" for source in sources),
            encoding="utf-8",
        )
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", str(destination),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            shutil.rmtree(join_root, ignore_errors=True)
            raise VideoGenerationError("join_failed", "Joining clips timed out") from exc
        if process.returncode or not destination.is_file():
            detail = stderr.decode("utf-8", "replace")[-500:]
            shutil.rmtree(join_root, ignore_errors=True)
            raise VideoGenerationError("join_failed", f"Could not join clips: {detail}")
        session_id = self._artifact_session()
        artifact = self.workspace.import_artifact(
            session_id,
            destination,
            f"{join_id}.mp4",
            media_type="video/mp4",
            metadata={"generator": "ai2apps.video-studio", "source_task_ids": task_ids},
        )
        shutil.rmtree(join_root, ignore_errors=True)
        return {
            "id": join_id,
            "object": "video.join",
            "video": {
                "artifact_id": artifact.id,
                "uri": f"artifact://{artifact.id}",
                "media_type": "video/mp4",
                "download_url": f"/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download",
            },
        }

    @staticmethod
    def _response(row) -> dict[str, Any]:
        progress = json.loads(row["progress_json"])
        progress["percent"] = _percent(progress)
        response = {
            "id": row["id"],
            "object": "video.generation.task",
            "status": row["status"],
            "model": row["model_id"],
            "model_revision": row["model_revision"],
            "request_hash": row["request_hash"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "cancel_requested_at": row["cancel_requested_at"],
            "progress": progress,
            "metadata": json.loads(row["request_json"]).get("metadata", {}),
        }
        if row["artifact_id"]:
            response["result"] = {
                "video": {
                    "artifact_id": row["artifact_id"],
                    "uri": f"artifact://{row['artifact_id']}",
                    "media_type": "video/mp4",
                    "download_url": (
                        f"/v1/platform/sessions/{row['artifact_session_id']}/artifacts/"
                        f"{row['artifact_id']}/download"
                    ),
                }
            }
        if row["error_json"]:
            response["error"] = json.loads(row["error_json"])
        return response
