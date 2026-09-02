"""Local-first APIs for the built-in Read Aloud Studio App."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.core import RepositoryError, utc_now_text
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.model_providers import list_package_models
from ai2apps.readaloud import (
    ReadAloudRenderError,
    ReadAloudRepository,
    ReadAloudTaskManager,
)

ProjectPurpose = Literal["private", "noncommercial", "commercial"]
SourceRights = Literal["user_owned", "licensed", "public_domain", "personal_use"]
VoiceSource = Literal["synthetic_designed", "self_voice", "authorized_person"]
ReviewStatus = Literal["suggested", "needs_review", "approved"]
VOICE_RIGHTS_POLICY_VERSION = "ai2apps.voice-rights/v1"


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    purpose: ProjectPurpose = "private"
    source_rights: SourceRights = "user_owned"
    source_text: str = Field(default="", max_length=200_000)


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    purpose: ProjectPurpose | None = None
    source_rights: SourceRights | None = None
    source_text: str | None = Field(default=None, max_length=200_000)
    status: Literal["draft", "ready", "archived"] | None = None


class VoiceProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source_type: VoiceSource
    model_id: str | None = Field(default=None, max_length=255)
    provider_voice_id: str | None = Field(default=None, max_length=255)
    reference_transcript: str = Field(default="", max_length=20_000)
    reference_asset_id: str | None = Field(default=None, max_length=255)
    rights_scope: dict[str, Any] = Field(default_factory=dict)


class CharacterCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2_000)
    voice_profile_id: str | None = None


class SegmentCreateRequest(BaseModel):
    speaker_id: str | None = None
    text: str = Field(min_length=1, max_length=10_000)
    emotion: str = Field(default="neutral", min_length=1, max_length=80)
    emotion_strength: float = Field(default=1.0, ge=0.0, le=2.0)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pause_after_ms: int = Field(default=300, ge=0, le=10_000)


class SegmentUpdateRequest(BaseModel):
    speaker_id: str | None = None
    text: str | None = Field(default=None, min_length=1, max_length=10_000)
    emotion: str | None = Field(default=None, min_length=1, max_length=80)
    emotion_strength: float | None = Field(default=None, ge=0.0, le=2.0)
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    pause_after_ms: int | None = Field(default=None, ge=0, le=10_000)
    review_status: ReviewStatus | None = None


class RenderCreateRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=255)
    segment_ids: list[str] | None = Field(default=None, max_length=10_000)


def _camel(value: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "owner_user_id": "ownerUserId",
        "source_rights": "sourceRights",
        "source_text": "sourceText",
        "created_at": "createdAt",
        "updated_at": "updatedAt",
        "character_count": "characterCount",
        "segment_count": "segmentCount",
        "source_type": "sourceType",
        "model_id": "modelId",
        "provider_voice_id": "providerVoiceId",
        "reference_transcript": "referenceTranscript",
        "reference_asset_id": "referenceAssetId",
        "rights_scope": "rightsScope",
        "project_id": "projectId",
        "voice_profile_id": "voiceProfileId",
        "sort_order": "sortOrder",
        "speaker_id": "speakerId",
        "emotion_strength": "emotionStrength",
        "pause_after_ms": "pauseAfterMs",
        "review_status": "reviewStatus",
        "project_revision": "projectRevision",
        "total_segments": "totalSegments",
        "completed_segments": "completedSegments",
        "cancel_requested_at": "cancelRequestedAt",
        "started_at": "startedAt",
        "completed_at": "completedAt",
        "segment_id": "segmentId",
        "output_path": "outputPath",
    }
    result = {mapping.get(key, key): item for key, item in value.items()}
    if isinstance(result.get("characters"), list):
        result["characters"] = [_camel(item) for item in result["characters"]]
    if isinstance(result.get("segments"), list):
        result["segments"] = [_camel(item) for item in result["segments"]]
    return result


def _voice_rights_scope(
    request: VoiceProfileCreateRequest,
    principal: RequestPrincipal,
) -> dict[str, Any]:
    scope = dict(request.rights_scope)
    if request.source_type != "synthetic_designed":
        required = (
            "consent_confirmed",
            "usage_rights_confirmed",
            "prohibited_impersonation_acknowledged",
        )
        missing = [field for field in required if scope.get(field) is not True]
        if missing:
            raise ValueError(
                "Real-person voice profiles require consent, usage-rights, "
                "and anti-impersonation acknowledgements."
            )
    scope.update(
        {
            "policy_version": VOICE_RIGHTS_POLICY_VERSION,
            "accepted_by_user_id": principal.actor_user_id,
            "accepted_at": utc_now_text(),
        }
    )
    return scope


def create_readaloud_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/readaloud", tags=["platform-readaloud"])
    principal_dependency = Depends(principal_provider)

    def repository() -> ReadAloudRepository | JSONResponse:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        events = None if runtime is None else getattr(runtime, "events", None)
        if database is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Read Aloud persistence is not ready.",
                retryable=True,
            )
        return ReadAloudRepository(database, events)

    def render_manager() -> ReadAloudTaskManager | JSONResponse:
        runtime = runtime_provider()
        manager = None if runtime is None else getattr(runtime, "readaloud_tasks", None)
        if manager is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Read Aloud render queue is not ready.",
                retryable=True,
            )
        return manager

    def guarded(call):
        try:
            return call()
        except RepositoryError as error:
            return repository_error_response(error)
        except ValueError as error:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message=str(error),
            )

    def reference_audio_asset(
        asset_id: str | None,
        principal: RequestPrincipal,
    ) -> str | None:
        if not asset_id:
            return None
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        config = None if runtime is None else getattr(runtime, "config", None)
        paths = None if config is None else getattr(config, "paths", None)
        if database is None or paths is None:
            raise ValueError("Gallery persistence is not ready.")
        asset = GalleryRepository(
            database,
            paths.artifacts_path / "gallery",
            getattr(runtime, "events", None),
        ).get_asset(principal.actor_user_id, asset_id)
        if not str(asset.get("media_type") or "").startswith("audio/"):
            raise ValueError("Voice training reference must be an audio asset.")
        return asset_id

    @router.get("/providers")
    def providers(principal: RequestPrincipal = principal_dependency):
        del principal
        runtime = runtime_provider()
        installed = []
        for model in list_package_models(runtime):
            if model.model_type not in {"audio_tts", "audio_stt"}:
                continue
            installed.append(
                {
                    "id": model.id,
                    "displayName": model.display_name,
                    "modelType": model.model_type,
                    "capabilities": list(model.capabilities),
                    "audioCapabilities": dict(model.audio_capabilities or {}),
                    "ready": model.checkpoint_ready,
                    "family": model.metadata.get("family"),
                }
            )
        return {
            "strategy": {
                "ideal": "ai2apps.model.fish-s2-pro/bf16",
                "fallbacks": [
                    "ai2apps.model.cosyvoice3-0.5b/4bit",
                    "ai2apps.model.cosyvoice3-0.5b/8bit",
                    "ai2apps.model.qwen3-tts-1.7b/custom-voice-8bit",
                ],
                "cloudApiEnabled": False,
            },
            "items": installed,
        }

    @router.get("/projects")
    def list_projects(principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return {"items": [_camel(item) for item in selected.list_projects(principal.actor_user_id)]}

    @router.post("/projects", status_code=201)
    def create_project(
        request: ProjectCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        title = request.title.strip()
        if not title:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message="Project title must contain visible characters.",
            )
        return guarded(
            lambda: _camel(
                selected.create_project(
                    principal.actor_user_id,
                    title=title,
                    purpose=request.purpose,
                    source_rights=request.source_rights,
                    source_text=request.source_text,
                )
            )
        )

    @router.get("/projects/{project_id}")
    def get_project(
        project_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: _camel(selected.get_project(principal.actor_user_id, project_id)))

    @router.patch("/projects/{project_id}")
    def update_project(
        project_id: str,
        request: ProjectUpdateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: _camel(
                selected.update_project(
                    principal.actor_user_id,
                    project_id,
                    request.model_dump(exclude_none=True),
                )
            )
        )

    @router.get("/voice-profiles")
    def list_voice_profiles(principal: RequestPrincipal = principal_dependency):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return {
            "items": [
                _camel(item)
                for item in selected.list_voice_profiles(principal.actor_user_id)
            ]
        }

    @router.post("/voice-profiles", status_code=201)
    def create_voice_profile(
        request: VoiceProfileCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: _camel(
                selected.create_voice_profile(
                    principal.actor_user_id,
                    name=request.name.strip(),
                    source_type=request.source_type,
                    model_id=request.model_id,
                    provider_voice_id=request.provider_voice_id,
                    reference_transcript=request.reference_transcript,
                    rights_scope=_voice_rights_scope(request, principal),
                    reference_asset_id=reference_audio_asset(
                        request.reference_asset_id,
                        principal,
                    ),
                )
            )
        )

    @router.post("/projects/{project_id}/characters", status_code=201)
    def create_character(
        project_id: str,
        request: CharacterCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        name = request.name.strip()
        if not name:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message="Character name must contain visible characters.",
            )
        return guarded(
            lambda: _camel(
                selected.create_character(
                    principal.actor_user_id,
                    project_id,
                    name=name,
                    description=request.description,
                    voice_profile_id=request.voice_profile_id,
                )
            )
        )

    @router.post("/projects/{project_id}/segments", status_code=201)
    def create_segment(
        project_id: str,
        request: SegmentCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        text = request.text.strip()
        if not text:
            return platform_error_response(
                status_code=422,
                code="readaloud_request_invalid",
                message="Segment text must contain visible characters.",
            )
        return guarded(
            lambda: _camel(
                selected.create_segment(
                    principal.actor_user_id,
                    project_id,
                    speaker_id=request.speaker_id,
                    text=text,
                    emotion=request.emotion.strip(),
                    emotion_strength=request.emotion_strength,
                    speed=request.speed,
                    pause_after_ms=request.pause_after_ms,
                )
            )
        )

    @router.patch("/projects/{project_id}/segments/{segment_id}")
    def update_segment(
        project_id: str,
        segment_id: str,
        request: SegmentUpdateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: _camel(
                selected.update_segment(
                    principal.actor_user_id,
                    project_id,
                    segment_id,
                    request.model_dump(exclude_unset=True),
                )
            )
        )

    @router.post("/projects/{project_id}/render", status_code=202)
    async def create_render_job(
        project_id: str,
        request: RenderCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            job = await manager.create(
                owner_user_id=principal.actor_user_id,
                project_id=project_id,
                model_id=request.model_id,
                segment_ids=request.segment_ids,
            )
            return _camel(job)
        except RepositoryError as error:
            return repository_error_response(error)
        except ReadAloudRenderError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code,
                message=str(error),
                retryable=error.status_code >= 500,
            )

    @router.get("/render-jobs/{job_id}")
    def get_render_job(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return _camel(manager.get(job_id, owner_user_id=principal.actor_user_id))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/render-jobs/{job_id}/cancel")
    async def cancel_render_job(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        manager = render_manager()
        if isinstance(manager, JSONResponse):
            return manager
        try:
            return _camel(
                await manager.cancel(job_id, owner_user_id=principal.actor_user_id)
            )
        except RepositoryError as error:
            return repository_error_response(error)

    return router
