"""Platform-owned discovery and mount API for Studio Mini-Apps."""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import time
import uuid
import zipfile
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.imagine_studio import MINI_APPS as IMAGINE_MINI_APPS
from ai2apps.api.imagine_studio import STUDIO_ID as IMAGINE_STUDIO_ID
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.api.readaloud import READALOUD_MINI_APPS, READALOUD_STUDIO_ID
from ai2apps.api.video_studio import MINI_APPS as VIDEO_MINI_APPS
from ai2apps.api.video_studio import STUDIO_ID as VIDEO_STUDIO_ID
from ai2apps.core import ResourceNotFoundError
from ai2apps.extensions import ExtensionError
from ai2apps.identity import RequestPrincipal
from ai2apps.readaloud.transcript import transcript_output
from ai2apps.studio import (
    StudioCapabilityBroker,
    StudioCapabilityError,
    StudioMiniAppRegistry,
    StudioRepository,
)

BUILTIN_MINI_APPS = {
    VIDEO_STUDIO_ID: VIDEO_MINI_APPS,
    READALOUD_STUDIO_ID: READALOUD_MINI_APPS,
    IMAGINE_STUDIO_ID: IMAGINE_MINI_APPS,
}
MAX_CAPABILITY_UPLOAD_BYTES = 1024 * 1024 * 1024
MAX_REFERENCE_UPLOAD_BYTES = 100 * 1024 * 1024
PROGRESS_PHASE_RANGES = {
    "media.video_subtitles": ((0, 15), (15, 45), (45, 70), (70, 90), (90, 100)),
    "media.video_audio_translation": (
        (0, 15),
        (15, 35),
        (35, 50),
        (50, 75),
        (75, 88),
        (88, 100),
    ),
}
PROGRESS_CAPABILITIES = frozenset(PROGRESS_PHASE_RANGES)


def _phase_percent(capability: str, phase_index: int, status: str, percent: int) -> int:
    if status == "completed":
        return 100
    if status == "queued":
        return 0
    ranges = PROGRESS_PHASE_RANGES.get(capability, ())
    if not 0 <= phase_index < len(ranges):
        return max(0, min(100, percent))
    start, end = ranges[phase_index]
    return max(0, min(100, round((percent - start) * 100 / max(1, end - start))))


@dataclass(slots=True)
class _InvocationProgressRecord:
    scope: tuple[str, str, str, str, str]
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    revision: int = 0
    event: dict[str, Any] = field(
        default_factory=lambda: {
            "phaseIndex": 0,
            "status": "queued",
            "percent": 0,
            "phasePercent": 0,
            "detail": "等待 Host 接收素材",
        }
    )
    history: deque[tuple[int, dict[str, Any]]] = field(
        default_factory=lambda: deque(maxlen=128)
    )
    terminal: bool = False
    updated_at: float = field(default_factory=time.monotonic)


class _InvocationProgressStore:
    def __init__(self) -> None:
        self._records: dict[str, _InvocationProgressRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, scope: tuple[str, str, str, str, str]) -> str:
        async with self._lock:
            cutoff = time.monotonic() - 900
            self._records = {
                key: value
                for key, value in self._records.items()
                if value.updated_at >= cutoff
            }
            if len(self._records) >= 256:
                oldest = sorted(
                    self._records,
                    key=lambda key: self._records[key].updated_at,
                )[: len(self._records) - 255]
                for key in oldest:
                    self._records.pop(key, None)
            invocation_id = uuid.uuid4().hex
            record = _InvocationProgressRecord(scope=scope)
            record.history.append((0, dict(record.event)))
            self._records[invocation_id] = record
            return invocation_id

    def get(
        self, invocation_id: str, scope_prefix: tuple[str, str, str, str]
    ) -> _InvocationProgressRecord | None:
        record = self._records.get(invocation_id)
        if record is None or record.scope[:4] != scope_prefix:
            return None
        return record

    async def publish(
        self,
        invocation_id: str | None,
        scope: tuple[str, str, str, str, str],
        *,
        phase_index: int,
        status: str,
        percent: int,
        detail: str,
    ) -> None:
        if invocation_id is None:
            return
        record = self._records.get(invocation_id)
        if record is None or record.scope != scope or record.terminal:
            return
        async with record.condition:
            record.revision += 1
            record.event = {
                "phaseIndex": max(0, phase_index),
                "status": status,
                "percent": max(0, min(100, percent)),
                "phasePercent": _phase_percent(scope[4], phase_index, status, percent),
                "detail": detail[:500],
            }
            record.history.append((record.revision, dict(record.event)))
            record.terminal = status == "failed" or (
                status == "completed" and record.event["percent"] >= 100
            )
            record.updated_at = time.monotonic()
            record.condition.notify_all()
        # Give the StreamingResponse producer a scheduling point so adjacent
        # stage updates cannot collapse into one visible UI transition.
        await asyncio.sleep(0)

    async def fail(
        self,
        invocation_id: str | None,
        scope: tuple[str, str, str, str, str],
        detail: str,
    ) -> None:
        if invocation_id is None:
            return
        record = self._records.get(invocation_id)
        if record is None or record.scope != scope or record.terminal:
            return
        await self.publish(
            invocation_id,
            scope,
            phase_index=int(record.event.get("phaseIndex") or 0),
            status="failed",
            percent=int(record.event.get("percent") or 0),
            detail=detail,
        )


class StudioInvocationStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability: str = Field(min_length=3, max_length=200)


def _publish_video_studio_output(
    runtime: Any,
    principal: RequestPrincipal,
    mounted,
    content: bytes,
    source_filename: str,
    *,
    suffix: str = "subtitled",
    step_label: str = "Burn subtitles",
    detail: str = "Subtitled video ready",
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    context = (
        mounted.mount.get("context")
        if isinstance(mounted.mount.get("context"), dict)
        else {}
    )
    studio_instance_id = context.get("studioInstanceId")
    if not isinstance(studio_instance_id, str) or not studio_instance_id:
        raise StudioCapabilityError(
            "studio_output_scope_missing",
            "The Video Studio output scope is unavailable",
            status_code=409,
        )
    database = getattr(runtime, "database", None)
    workspace = getattr(runtime, "workspace", None)
    video_tasks = getattr(runtime, "video_tasks", None)
    paths = getattr(getattr(runtime, "config", None), "paths", None)
    if database is None or workspace is None or video_tasks is None or paths is None:
        raise StudioCapabilityError(
            "studio_output_unavailable",
            "Video Studio Artifact storage is unavailable",
            status_code=503,
        )
    stem = Path(source_filename or "video").stem[:120]
    safe_stem = (
        "".join(
            character if character.isalnum() or character in " -_." else "-"
            for character in stem
        ).strip(" .")
        or "video"
    )
    filename = f"{safe_stem}-{suffix}.mp4"
    repository = StudioRepository(database)
    scope = {
        "actor_id": principal.actor_user_id,
        "installation_id": principal.installation_id,
        "app_instance_id": studio_instance_id,
        "studio_id": VIDEO_STUDIO_ID,
    }
    run = repository.create_run(
        mini_app_id=mounted.declaration["id"],
        mini_app_version=str(mounted.declaration.get("version") or "1.0.0"),
        placement="inline",
        title=filename,
        input_data={
            "sourceName": Path(source_filename or "video").name,
            **(metadata or {}),
        },
        step_label=step_label,
        **scope,
    )
    repository.update_run(
        run["id"],
        status="running",
        progress=90,
        detail="Saving video Artifact",
        **scope,
    )
    session_id = video_tasks.artifact_session()
    with tempfile.TemporaryDirectory(dir=paths.artifacts_path) as directory:
        source = Path(directory) / filename
        source.write_bytes(content)
        artifact = workspace.import_artifact(
            session_id,
            source,
            filename,
            media_type="video/mp4",
            metadata={
                "generator": mounted.declaration["id"],
                "studioId": VIDEO_STUDIO_ID,
                **(metadata or {}),
            },
        )
    output_url = f"/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download"
    repository.create_artifact(
        run["id"],
        kind="video",
        name=artifact.name,
        media_type="video/mp4",
        preview_url=output_url,
        download_url=output_url,
        source_id=artifact.id,
        metadata={
            "workspaceSessionId": session_id,
            "workspaceArtifactId": artifact.id,
            "generator": mounted.declaration["id"],
            **(metadata or {}),
        },
        **scope,
    )
    repository.update_run(
        run["id"],
        status="succeeded",
        progress=100,
        detail=detail,
        **scope,
    )
    repository.prune_output_history(workspace, **scope)
    return {"downloadUrl": output_url, "runId": run["id"], "filename": filename}


class StudioTextExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str = Field(
        min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_-]+\.(json|md|srt)$"
    )
    content: str = Field(max_length=4 * 1024 * 1024)


class StudioMiniAppMountRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mini_app_id: str = Field(alias="miniAppId", min_length=3, max_length=200)
    placement: Literal["inline", "sidebar"] = "inline"
    interaction_session_id: str | None = Field(
        default=None, alias="interactionSessionId", max_length=100
    )
    context: dict[str, Any] = Field(default_factory=dict)


def _content_url(mount: dict[str, Any]) -> str:
    instance_id = quote(str(mount["app_instance_id"]), safe="")
    mount_id = quote(str(mount["id"]), safe="")
    context = mount.get("context") if isinstance(mount.get("context"), dict) else {}
    studio_id = quote(str(context.get("studioId") or ""), safe="")
    renderer = mount["renderer"]
    if renderer in {"schema", "safe-html"}:
        return (
            f"/admin/app-view/{instance_id}/{renderer}?mount_id={mount_id}"
            f"&studio_id={studio_id}"
        )
    if renderer == "sandbox":
        resource = quote(str(mount["resource"]), safe="/")
        return (
            f"/admin/api/shell/app-instances/{instance_id}/resources/"
            f"{resource}?mount_id={mount_id}&studio_id={studio_id}"
        )
    raise HTTPException(status_code=422, detail="Unsupported Studio Mini-App renderer")


def create_studio_mini_app_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/studios", tags=["platform-studio-mini-apps"])
    principal_dependency = Depends(principal_provider)
    invocation_progress = _InvocationProgressStore()

    def progress_scope(
        principal: RequestPrincipal,
        studio_id: str,
        mount_id: str,
        capability: str,
    ) -> tuple[str, str, str, str, str]:
        return (
            principal.actor_user_id,
            principal.installation_id,
            studio_id,
            mount_id,
            capability,
        )

    def manager():
        runtime = runtime_provider()
        value = None if runtime is None else getattr(runtime, "extension_manager", None)
        if value is None:
            raise HTTPException(
                status_code=503, detail="Studio Mini-App Registry is not ready"
            )
        return runtime, value

    def capability_error(error: StudioCapabilityError) -> HTTPException:
        return HTTPException(
            status_code=error.status_code,
            detail={
                "code": error.code,
                "message": str(error),
                "details": error.details,
            },
        )

    @router.get("/{studio_id}/mini-apps")
    def list_mini_apps(
        studio_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        _runtime, extension_manager = manager()
        return StudioMiniAppRegistry(extension_manager).list(
            studio_id,
            builtins=BUILTIN_MINI_APPS.get(studio_id, ()),
            principal=principal,
        )

    @router.get("/{studio_id}/mini-app-capabilities")
    def probe_installed_mini_app_capabilities(
        studio_id: str,
        studio_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime, extension_manager = manager()
        authorize_app_instance(runtime, principal, studio_instance_id)
        studio_entry = extension_manager.instance_entry(
            studio_instance_id, principal=principal
        )
        if studio_entry.get("app_key") != studio_id:
            raise HTTPException(status_code=404, detail="Studio instance was not found")
        catalog = StudioMiniAppRegistry(extension_manager).list(
            studio_id,
            builtins=BUILTIN_MINI_APPS.get(studio_id, ()),
            principal=principal,
        )
        broker = StudioCapabilityBroker(runtime)
        return {
            "schema": "ai2apps.studio-capability-catalog/v1",
            "studioId": studio_id,
            "items": [
                broker.probe_declaration(studio_id, item)
                for item in catalog["items"]
                if item.get("source") == "package"
            ],
        }

    @router.post("/{studio_id}/mini-app-mounts", status_code=201)
    def mount_mini_app(
        studio_id: str,
        request: StudioMiniAppMountRequest,
        studio_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime, extension_manager = manager()
        authorize_app_instance(runtime, principal, studio_instance_id)
        studio_entry = extension_manager.instance_entry(
            studio_instance_id, principal=principal
        )
        if studio_entry.get("app_key") != studio_id:
            raise HTTPException(status_code=404, detail="Studio instance was not found")
        if (
            request.interaction_session_id is not None
            and not extension_manager.instance_can_use_session(
                studio_instance_id,
                request.interaction_session_id,
                principal=principal,
            )
        ):
            raise HTTPException(
                status_code=404, detail="Studio interaction session was not found"
            )
        if (
            len(json.dumps(request.context, ensure_ascii=False).encode("utf-8"))
            > 64 * 1024
        ):
            raise HTTPException(
                status_code=413, detail="Mini-App mount context is too large"
            )
        catalog = StudioMiniAppRegistry(extension_manager).list(
            studio_id,
            builtins=BUILTIN_MINI_APPS.get(studio_id, ()),
            principal=principal,
        )
        selected = next(
            (
                item
                for item in catalog["items"]
                if item.get("id") == request.mini_app_id
            ),
            None,
        )
        if selected is None or selected.get("source") != "package":
            raise HTTPException(
                status_code=404, detail="Installed Studio Mini-App was not found"
            )
        try:
            mount = extension_manager.mount_studio_mini_app(
                studio_id,
                request.mini_app_id,
                placement=request.placement,
                interaction_session_id=request.interaction_session_id,
                context={"studioInstanceId": studio_instance_id, **request.context},
                principal=principal,
            )
        except ResourceNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ExtensionError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {**mount, "content_url": _content_url(mount)}

    @router.get("/{studio_id}/mini-app-mounts/{mount_id}/capabilities")
    def probe_mini_app_capabilities(
        studio_id: str,
        mount_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime, _extension_manager = manager()
        try:
            return StudioCapabilityBroker(runtime).probe(
                studio_id, mount_id, principal=principal
            )
        except StudioCapabilityError as error:
            raise capability_error(error) from error
        except ResourceNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ExtensionError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error

    @router.get("/{studio_id}/mini-app-mounts/{mount_id}/characters")
    def list_mini_app_characters(
        studio_id: str,
        mount_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime, _extension_manager = manager()
        try:
            return StudioCapabilityBroker(runtime).character_presets(
                studio_id, mount_id, principal=principal
            )
        except StudioCapabilityError as error:
            raise capability_error(error) from error
        except ResourceNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ExtensionError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error

    @router.get("/{studio_id}/mini-app-mounts/{mount_id}/voice-clone-models")
    def list_mini_app_voice_clone_models(
        studio_id: str,
        mount_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime, _extension_manager = manager()
        try:
            return StudioCapabilityBroker(runtime).voice_clone_models(
                studio_id, mount_id, principal=principal
            )
        except StudioCapabilityError as error:
            raise capability_error(error) from error
        except ResourceNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ExtensionError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error

    @router.post("/{studio_id}/mini-app-mounts/{mount_id}/invocations", status_code=201)
    async def create_mini_app_invocation_progress(
        studio_id: str,
        mount_id: str,
        body: StudioInvocationStartRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime, _extension_manager = manager()
        if body.capability not in PROGRESS_CAPABILITIES:
            raise HTTPException(status_code=422, detail="Progress is unavailable")
        try:
            mounted = StudioCapabilityBroker(runtime).mounted_mini_app(
                studio_id, mount_id, principal=principal
            )
        except StudioCapabilityError as error:
            raise capability_error(error) from error
        if body.capability not in mounted.capabilities:
            raise HTTPException(status_code=403, detail="Capability is not declared")
        invocation_id = await invocation_progress.create(
            progress_scope(principal, studio_id, mount_id, body.capability)
        )
        return {
            "id": invocation_id,
            "eventsUrl": (
                f"/v1/platform/studios/{quote(studio_id, safe='')}"
                f"/mini-app-mounts/{quote(mount_id, safe='')}"
                f"/invocations/{invocation_id}/events"
            ),
        }

    @router.get(
        "/{studio_id}/mini-app-mounts/{mount_id}/invocations/{invocation_id}/events"
    )
    async def stream_mini_app_invocation_progress(
        studio_id: str,
        mount_id: str,
        invocation_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        if len(invocation_id) != 32:
            raise HTTPException(status_code=404, detail="Invocation was not found")
        record = invocation_progress.get(
            invocation_id,
            (
                principal.actor_user_id,
                principal.installation_id,
                studio_id,
                mount_id,
            ),
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Invocation was not found")

        async def events():
            revision = -1
            while True:
                heartbeat = False
                async with record.condition:
                    available = next(
                        (item for item in record.history if item[0] > revision), None
                    )
                    if available is None and not record.terminal:
                        try:
                            await asyncio.wait_for(record.condition.wait(), timeout=15)
                        except TimeoutError:
                            heartbeat = True
                        available = next(
                            (item for item in record.history if item[0] > revision),
                            None,
                        )
                    if heartbeat:
                        payload = None
                        terminal = False
                    elif available is None:
                        return
                    else:
                        revision, event = available
                        payload = {
                            "invocationId": invocation_id,
                            "revision": revision,
                            **event,
                        }
                        terminal = record.terminal and revision == record.revision
                if heartbeat:
                    yield ": keepalive\n\n"
                    continue
                yield f"id: {revision}\nevent: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if terminal:
                    return

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @router.post("/{studio_id}/mini-app-mounts/{mount_id}/exports")
    async def export_mini_app_text(
        studio_id: str,
        mount_id: str,
        body: StudioTextExportRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime, _ = manager()
        try:
            mounted = StudioCapabilityBroker(runtime).mounted_mini_app(
                studio_id, mount_id, principal=principal
            )
        except StudioCapabilityError as error:
            raise capability_error(error) from error
        except (ResourceNotFoundError, ExtensionError) as error:
            raise HTTPException(
                status_code=404, detail="Mini-App mount unavailable"
            ) from error
        if studio_id != READALOUD_STUDIO_ID:
            raise HTTPException(
                status_code=422, detail="Text export is only available in Voice Studio"
            )
        content = body.content.encode("utf-8")
        if len(content) > 4 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Export exceeds 4 MiB")
        extension = body.filename.rsplit(".", 1)[1]
        if extension == "json":
            try:
                json.loads(body.content)
            except (ValueError, RecursionError) as error:
                raise HTTPException(
                    status_code=422, detail="Invalid JSON export"
                ) from error
        media_type = {
            "json": "application/json",
            "md": "text/markdown",
            "srt": "application/x-subrip",
        }[extension]
        url = await asyncio.to_thread(
            runtime.readaloud_tasks.save_studio_output,
            principal.actor_user_id,
            content,
            mini_app_id=mounted.declaration["id"],
            filename=body.filename,
            media_type=media_type,
        )
        return {"downloadUrl": url, "filename": body.filename}

    @router.post(
        "/{studio_id}/mini-app-mounts/{mount_id}/capabilities/{capability}/invoke"
    )
    async def invoke_mini_app_capability(
        studio_id: str,
        mount_id: str,
        capability: str,
        request: Request,
        file: Annotated[UploadFile, File()],
        invocation_id: Annotated[
            str | None, Header(alias="X-AI2Apps-Invocation-ID")
        ] = None,
        reference: Annotated[UploadFile | None, File()] = None,
        profile: Annotated[str, Form()] = "compact",
        language: Annotated[str, Form()] = "",
        output_format: Annotated[Literal["json", "markdown", "srt"], Form()] = "json",
        word_timestamps: Annotated[bool, Form()] = True,
        diarization: Annotated[bool, Form()] = True,
        source_language: Annotated[str, Form()] = "",
        target_language: Annotated[str, Form()] = "",
        subtitle_format: Annotated[str, Form()] = "srt",
        bilingual: Annotated[bool, Form()] = True,
        burn_in: Annotated[bool, Form()] = False,
        speaker_labels: Annotated[bool, Form()] = False,
        subtitle_font_size: Annotated[
            Literal["small", "medium", "large", "extra_large"], Form()
        ] = "large",
        subtitle_background: Annotated[Literal["outline", "box"], Form()] = "outline",
        voice_profile_id: Annotated[str, Form()] = "",
        voice_clone_model_id: Annotated[str, Form()] = "",
        asr_verification: Annotated[bool, Form()] = False,
        action: Annotated[str, Form()] = "analyze",
        target_speaker: Annotated[str, Form()] = "",
        conversion_profile: Annotated[str, Form()] = "timbre_quality",
        consent: Annotated[bool, Form()] = False,
        principal: RequestPrincipal = principal_dependency,
    ) -> Response:
        if capability not in {
            "audio.detailed_transcription",
            "audio.source_separation",
            "media.video_subtitles",
            "media.video_audio_translation",
            "audio.speaker_voice_replacement",
            "media.video_speaker_voice_replacement",
        }:
            raise HTTPException(
                status_code=501,
                detail={
                    "code": "capability_not_implemented",
                    "message": "This capability is not implemented by the MVP Broker",
                },
            )
        buffer = io.BytesIO()
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_CAPABILITY_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "media_too_large",
                        "message": "Media input exceeds the 1 GiB limit",
                    },
                )
            buffer.write(chunk)
        if total == 0:
            raise HTTPException(
                status_code=400,
                detail={"code": "media_empty", "message": "Media input is empty"},
            )
        content = buffer.getvalue()
        buffer.close()
        runtime, _extension_manager = manager()
        invocation_scope = progress_scope(principal, studio_id, mount_id, capability)
        if invocation_id is not None:
            record = invocation_progress.get(invocation_id, invocation_scope[:4])
            if record is None or record.scope != invocation_scope:
                raise HTTPException(status_code=404, detail="Invocation was not found")

        async def report_progress(
            phase_index: int, status: str, percent: int, detail: str
        ) -> None:
            await invocation_progress.publish(
                invocation_id,
                invocation_scope,
                phase_index=phase_index,
                status=status,
                percent=percent,
                detail=detail,
            )

        try:
            broker = StudioCapabilityBroker(runtime)
            invocation = {
                "principal": principal,
                "content": content,
                "filename": file.filename or "audio",
                "media_type": file.content_type,
                "profile": profile,
            }

            async def publish_output(result, *, filename, media_type, content=None):
                # The host persists results; opaque Package frames never own output URLs/history.
                if studio_id == READALOUD_STUDIO_ID and result.status_code == 200:
                    output_url = await asyncio.to_thread(
                        runtime.readaloud_tasks.save_studio_output,
                        principal.actor_user_id,
                        bytes(result.body) if content is None else content,
                        mini_app_id=broker.mounted_mini_app(
                            studio_id, mount_id, principal=principal
                        ).declaration["id"],
                        filename=filename,
                        media_type=media_type,
                    )
                    result.headers["X-AI2Apps-Download-URL"] = output_url
                return result

            if capability == "audio.source_separation":
                result = await broker.source_separation(
                    studio_id, mount_id, **invocation
                )
                if (
                    studio_id == READALOUD_STUDIO_ID
                    and "application/json" in request.headers.get("accept", "")
                    and result.status_code == 200
                ):
                    content = broker._artifact_bytes(
                        result, operation="Source separation"
                    )
                    output = await asyncio.to_thread(
                        runtime.readaloud_tasks.save_separation_output,
                        principal.actor_user_id,
                        content,
                        file.filename or "audio",
                    )
                    return JSONResponse(output)
                return result
            if capability == "media.video_subtitles":
                result = await broker.video_subtitles(
                    studio_id,
                    mount_id,
                    principal=principal,
                    request=request,
                    content=invocation["content"],
                    filename=invocation["filename"],
                    media_type=invocation["media_type"],
                    source_language=source_language or None,
                    target_language=target_language or None,
                    subtitle_format=subtitle_format,
                    bilingual=bilingual,
                    burn_in=burn_in,
                    speaker_labels=speaker_labels,
                    subtitle_font_size=subtitle_font_size,
                    subtitle_background=subtitle_background,
                    progress=report_progress,
                )
                if (
                    studio_id == VIDEO_STUDIO_ID
                    and burn_in
                    and result.status_code == 200
                ):
                    try:
                        with zipfile.ZipFile(io.BytesIO(bytes(result.body))) as archive:
                            rendered_video = archive.read("subtitled-video.mp4")
                    except (AttributeError, KeyError, zipfile.BadZipFile) as error:
                        raise StudioCapabilityError(
                            "subtitle_video_missing",
                            "Subtitle burn-in did not return a usable video",
                            status_code=502,
                        ) from error
                    output = await asyncio.to_thread(
                        _publish_video_studio_output,
                        runtime,
                        principal,
                        broker.mounted_mini_app(
                            studio_id, mount_id, principal=principal
                        ),
                        rendered_video,
                        invocation["filename"],
                        metadata={"burnIn": True},
                    )
                    result.headers["X-AI2Apps-Download-URL"] = output["downloadUrl"]
                    result.headers["X-AI2Apps-Studio-Run-ID"] = output["runId"]
                await report_progress(4, "completed", 100, "字幕工作流完成")
                return result
            if capability == "media.video_audio_translation":
                result = await broker.video_audio_translation(
                    studio_id,
                    mount_id,
                    principal=principal,
                    request=request,
                    content=invocation["content"],
                    filename=invocation["filename"],
                    media_type=invocation["media_type"],
                    source_language=source_language or None,
                    target_language=target_language,
                    voice_profile_id=voice_profile_id,
                    voice_clone_model_id=voice_clone_model_id or None,
                    asr_verification=asr_verification,
                    progress=report_progress,
                )
                if studio_id == VIDEO_STUDIO_ID and result.status_code == 200:
                    output = await asyncio.to_thread(
                        _publish_video_studio_output,
                        runtime,
                        principal,
                        broker.mounted_mini_app(
                            studio_id, mount_id, principal=principal
                        ),
                        bytes(result.body),
                        invocation["filename"],
                        suffix="translated-audio",
                        step_label="Translate video audio",
                        detail="Translated Character audio ready",
                        metadata={"targetLanguage": target_language},
                    )
                    result.headers["X-AI2Apps-Download-URL"] = output["downloadUrl"]
                    result.headers["X-AI2Apps-Studio-Run-ID"] = output["runId"]
                await report_progress(5, "completed", 100, "视频音轨翻译完成")
                return result
            if capability == "audio.speaker_voice_replacement":
                reference_content = None
                if reference is not None:
                    reference_content = await reference.read(
                        MAX_REFERENCE_UPLOAD_BYTES + 1
                    )
                    if len(reference_content) > MAX_REFERENCE_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail={
                                "code": "media_too_large",
                                "message": "Reference audio exceeds the 100 MiB limit",
                            },
                        )
                result = await broker.audio_speaker_replacement(
                    studio_id,
                    mount_id,
                    principal=principal,
                    content=invocation["content"],
                    filename=invocation["filename"],
                    media_type=invocation["media_type"],
                    action=action,
                    target_speaker=target_speaker or None,
                    reference=reference_content,
                    reference_filename=(
                        None if reference is None else reference.filename
                    ),
                    reference_media_type=(
                        None if reference is None else reference.content_type
                    ),
                    conversion_profile=conversion_profile,
                    consent=consent,
                )
                return (
                    await publish_output(
                        result, filename="speaker-replaced.wav", media_type="audio/wav"
                    )
                    if action == "replace"
                    else result
                )
            if capability == "media.video_speaker_voice_replacement":
                reference_content = None
                if reference is not None:
                    reference_content = await reference.read(
                        MAX_REFERENCE_UPLOAD_BYTES + 1
                    )
                    if len(reference_content) > MAX_REFERENCE_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail={
                                "code": "media_too_large",
                                "message": "Reference audio exceeds the 100 MiB limit",
                            },
                        )
                result = await broker.video_speaker_replacement(
                    studio_id,
                    mount_id,
                    principal=principal,
                    content=invocation["content"],
                    filename=invocation["filename"],
                    media_type=invocation["media_type"],
                    action=action,
                    target_speaker=target_speaker or None,
                    reference=reference_content,
                    reference_filename=(
                        None if reference is None else reference.filename
                    ),
                    reference_media_type=(
                        None if reference is None else reference.content_type
                    ),
                    conversion_profile=conversion_profile,
                    consent=consent,
                )
                return (
                    await publish_output(
                        result, filename="speaker-replaced.mp4", media_type="video/mp4"
                    )
                    if action == "replace"
                    else result
                )
            result = await broker.detailed_transcription(
                studio_id,
                mount_id,
                **invocation,
                language=language or None,
                word_timestamps=word_timestamps,
                diarization=diarization,
            )
            if result.status_code != 200:
                return result
            content, filename, media_type = transcript_output(
                bytes(result.body), output_format
            )
            return await publish_output(
                result, filename=filename, media_type=media_type, content=content
            )
        except StudioCapabilityError as error:
            await invocation_progress.fail(invocation_id, invocation_scope, str(error))
            raise capability_error(error) from error
        except ResourceNotFoundError as error:
            await invocation_progress.fail(invocation_id, invocation_scope, str(error))
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ExtensionError as error:
            await invocation_progress.fail(invocation_id, invocation_scope, str(error))
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error

    return router
