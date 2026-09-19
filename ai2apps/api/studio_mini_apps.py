"""Platform-owned discovery and mount API for Studio Mini-Apps."""

from __future__ import annotations

import json
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
from fastapi.responses import Response
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
from ai2apps.studio import (
    StudioCapabilityBroker,
    StudioCapabilityError,
    StudioMiniAppRegistry,
)

BUILTIN_MINI_APPS = {
    VIDEO_STUDIO_ID: VIDEO_MINI_APPS,
    READALOUD_STUDIO_ID: READALOUD_MINI_APPS,
    IMAGINE_STUDIO_ID: IMAGINE_MINI_APPS,
}
MAX_CAPABILITY_UPLOAD_BYTES = 100 * 1024 * 1024


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

    def manager():
        runtime = runtime_provider()
        value = None if runtime is None else getattr(runtime, "extension_manager", None)
        if value is None:
            raise HTTPException(status_code=503, detail="Studio Mini-App Registry is not ready")
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
        if request.interaction_session_id is not None and not extension_manager.instance_can_use_session(
            studio_instance_id,
            request.interaction_session_id,
            principal=principal,
        ):
            raise HTTPException(
                status_code=404, detail="Studio interaction session was not found"
            )
        if len(json.dumps(request.context, ensure_ascii=False).encode("utf-8")) > 64 * 1024:
            raise HTTPException(status_code=413, detail="Mini-App mount context is too large")
        catalog = StudioMiniAppRegistry(extension_manager).list(
            studio_id,
            builtins=BUILTIN_MINI_APPS.get(studio_id, ()),
            principal=principal,
        )
        selected = next(
            (item for item in catalog["items"] if item.get("id") == request.mini_app_id),
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

    @router.post(
        "/{studio_id}/mini-app-mounts/{mount_id}/capabilities/{capability}/invoke"
    )
    async def invoke_mini_app_capability(
        studio_id: str,
        mount_id: str,
        capability: str,
        request: Request,
        file: Annotated[UploadFile, File()],
        reference: Annotated[UploadFile | None, File()] = None,
        profile: Annotated[str, Form()] = "compact",
        language: Annotated[str, Form()] = "",
        word_timestamps: Annotated[bool, Form()] = True,
        diarization: Annotated[bool, Form()] = True,
        source_language: Annotated[str, Form()] = "",
        target_language: Annotated[str, Form()] = "",
        subtitle_format: Annotated[str, Form()] = "srt",
        bilingual: Annotated[bool, Form()] = True,
        burn_in: Annotated[bool, Form()] = False,
        speaker_labels: Annotated[bool, Form()] = False,
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
        chunks: list[bytes] = []
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
                        "message": "Media input exceeds the 100 MB MVP limit",
                    },
                )
            chunks.append(chunk)
        if total == 0:
            raise HTTPException(
                status_code=400,
                detail={"code": "media_empty", "message": "Media input is empty"},
            )
        runtime, _extension_manager = manager()
        try:
            broker = StudioCapabilityBroker(runtime)
            invocation = {
                "principal": principal,
                "content": b"".join(chunks),
                "filename": file.filename or "audio",
                "media_type": file.content_type,
                "profile": profile,
            }
            if capability == "audio.source_separation":
                return await broker.source_separation(
                    studio_id, mount_id, **invocation
                )
            if capability == "media.video_subtitles":
                return await broker.video_subtitles(
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
                )
            if capability == "audio.speaker_voice_replacement":
                reference_content = None
                if reference is not None:
                    reference_content = await reference.read(
                        MAX_CAPABILITY_UPLOAD_BYTES + 1
                    )
                    if len(reference_content) > MAX_CAPABILITY_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail={
                                "code": "media_too_large",
                                "message": "Reference audio exceeds the 100 MB MVP limit",
                            },
                        )
                return await broker.audio_speaker_replacement(
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
            if capability == "media.video_speaker_voice_replacement":
                reference_content = None
                if reference is not None:
                    reference_content = await reference.read(
                        MAX_CAPABILITY_UPLOAD_BYTES + 1
                    )
                    if len(reference_content) > MAX_CAPABILITY_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail={
                                "code": "media_too_large",
                                "message": "Reference audio exceeds the 100 MB MVP limit",
                            },
                        )
                return await broker.video_speaker_replacement(
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
            return await broker.detailed_transcription(
                studio_id,
                mount_id,
                **invocation,
                language=language or None,
                word_timestamps=word_timestamps,
                diarization=diarization,
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

    return router
