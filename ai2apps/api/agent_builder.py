"""Actor-scoped APIs for browser Agent drafts, evidence, and local compilation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.agent_builder import (
    AgentDraftRecord,
    AgentType,
    CompileGenerationRecord,
    StepEvidenceRecord,
    StepOutcome,
    capability_ir,
    compile_source,
    create_ir_run,
)
from ai2apps.agents import BROWSER_BUILDER_AGENT_KEY
from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.api.ownership import authorize_session
from ai2apps.chat import ChatRepository
from ai2apps.core import RepositoryError
from ai2apps.identity import RequestPrincipal


class AgentDraftCreateRequest(BaseModel):
    agent_type: AgentType = AgentType.WEB
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    site_scope: list[str] = Field(default_factory=list, max_length=32)
    source: dict[str, Any] | None = None


class AgentDraftPatchRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    site_scope: list[str] | None = Field(default=None, max_length=32)
    source: dict[str, Any] | None = None
    agent_type: AgentType | None = None


class StepEvidenceCreateRequest(BaseModel):
    outcome: StepOutcome
    evidence: dict[str, Any] = Field(default_factory=dict)
    generation_id: str | None = None
    run_id: str | None = None
    page_fingerprint: str = Field(default="", max_length=200)
    user_feedback: str | None = Field(default=None, max_length=2000)


class BrowserAgentRunCreateRequest(BaseModel):
    preview: bool = False
    browser_context: dict[str, Any] = Field(default_factory=dict)
    capability_id: str | None = None


class BrowserAgentRunResponse(BaseModel):
    id: str
    session_id: str
    status: str
    draft_id: str
    generation_id: str | None


class AgentDraftResponse(BaseModel):
    id: str
    agent_type: str
    name: str
    description: str
    site_scope: list[str]
    source: dict[str, Any]
    status: str
    active_generation_id: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    site_key: str = ""

    @classmethod
    def from_record(cls, record: AgentDraftRecord):
        return cls(
            id=record.id,
            agent_type=record.agent_type.value,
            name=record.name,
            description=record.description,
            site_scope=list(record.site_scope),
            source=record.source,
            status=record.status.value,
            active_generation_id=record.active_generation_id,
            revision=record.revision,
            created_at=record.created_at,
            updated_at=record.updated_at,
            site_key=record.site_key,
        )


class AgentDraftListResponse(BaseModel):
    items: list[AgentDraftResponse]


class CompileGenerationResponse(BaseModel):
    id: str
    draft_id: str
    source_revision: int
    source_digest: str
    compiler_version: str
    policy_version: str
    ir: dict[str, Any]
    report: dict[str, Any]
    status: str
    created_at: datetime
    activated_at: datetime | None

    @classmethod
    def from_record(cls, record: CompileGenerationRecord):
        return cls(
            **{
                field: getattr(record, field)
                for field in (
                    "id",
                    "draft_id",
                    "source_revision",
                    "source_digest",
                    "compiler_version",
                    "policy_version",
                    "ir",
                    "report",
                    "created_at",
                    "activated_at",
                )
            },
            status=record.status.value,
        )


class StepPlanResponse(BaseModel):
    valid: bool
    step: dict[str, Any] | None
    report: dict[str, Any]


class StepEvidenceResponse(BaseModel):
    id: str
    draft_id: str
    generation_id: str | None
    run_id: str | None
    step_name: str
    page_fingerprint: str
    outcome: str
    evidence: dict[str, Any]
    user_feedback: str | None
    created_at: datetime

    @classmethod
    def from_record(cls, record: StepEvidenceRecord):
        return cls(
            **{
                field: getattr(record, field)
                for field in (
                    "id",
                    "draft_id",
                    "generation_id",
                    "run_id",
                    "step_name",
                    "page_fingerprint",
                    "evidence",
                    "user_feedback",
                    "created_at",
                )
            },
            outcome=record.outcome.value,
        )


def _default_source(request: AgentDraftCreateRequest) -> dict[str, Any]:
    return {
        "schema": "ai2apps.site-agent-source/v1",
        "agent_type": request.agent_type.value,
        "name": request.name,
        "description": request.description,
        "site_scope": request.site_scope,
        "capabilities": [],
    }


def create_agent_builder_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(tags=["agent-builder"])
    principal_dependency = Depends(principal_provider)

    def repository():
        runtime = runtime_provider()
        if runtime is None or runtime.agent_builder is None:
            return platform_error_response(
                status_code=503,
                code="agent_builder_not_ready",
                message="AI2Apps Agent Builder is not ready.",
                retryable=True,
            )
        return runtime.agent_builder

    def browser_run(runtime, run_id: str, principal: RequestPrincipal):
        run = runtime.agents.get_run(run_id)
        definition = runtime.agents.get_definition(run.agent_definition_id)
        if definition.agent_key != BROWSER_BUILDER_AGENT_KEY:
            raise HTTPException(status_code=404, detail="Browser AgentRun not found")
        authorize_session(runtime, principal, run.session_id)
        return run

    def run_projection(runtime, run):
        interactions = runtime.agents.list_interactions(run.id)
        return {
            "id": run.id,
            "session_id": run.session_id,
            "status": run.status.value,
            "input": run.input,
            "output": run.output,
            "error": run.error,
            "current_step": run.current_step,
            "revision": run.revision,
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "interactions": [
                {
                    "id": item.id,
                    "request_key": item.request_key,
                    "status": item.status.value,
                    "prompt": item.prompt,
                    "request": item.request,
                    "response": item.response,
                    "revision": item.revision,
                }
                for item in interactions
            ],
        }

    @router.post("/agent-drafts", response_model=AgentDraftResponse, status_code=201)
    def create_draft(
        request: AgentDraftCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        source = request.source or _default_source(request)
        source = dict(source)
        source.setdefault("name", request.name)
        source.setdefault("agent_type", request.agent_type.value)
        source.setdefault("site_scope", request.site_scope)
        try:
            return AgentDraftResponse.from_record(
                store.create_draft(
                    owner_user_id=principal.actor_user_id,
                    name=request.name,
                    description=request.description,
                    site_scope=request.site_scope,
                    source=source,
                    agent_type=request.agent_type,
                )
            )
        except (RepositoryError, ValueError) as error:
            if isinstance(error, RepositoryError):
                return repository_error_response(error)
            return platform_error_response(
                status_code=422,
                code="invalid_agent_draft",
                message=str(error),
            )

    @router.get("/agent-drafts", response_model=AgentDraftListResponse)
    def list_drafts(principal: RequestPrincipal = principal_dependency):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        return AgentDraftListResponse(
            items=[
                AgentDraftResponse.from_record(item)
                for item in store.list_drafts(principal.actor_user_id)
            ]
        )

    @router.get("/agent-drafts/{draft_id}", response_model=AgentDraftResponse)
    def get_draft(
        draft_id: str, principal: RequestPrincipal = principal_dependency
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            return AgentDraftResponse.from_record(
                store.get_draft(draft_id, principal.actor_user_id)
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.patch("/agent-drafts/{draft_id}", response_model=AgentDraftResponse)
    def patch_draft(
        draft_id: str,
        request: AgentDraftPatchRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            source = request.source
            if source is not None and request.agent_type is not None:
                source = {**source, "agent_type": request.agent_type.value}
            return AgentDraftResponse.from_record(
                store.update_draft(
                    draft_id,
                    principal.actor_user_id,
                    expected_revision=request.expected_revision,
                    name=request.name,
                    description=request.description,
                    site_scope=request.site_scope,
                    source=source,
                    agent_type=request.agent_type,
                )
            )
        except (RepositoryError, ValueError) as error:
            if isinstance(error, RepositoryError):
                return repository_error_response(error)
            return platform_error_response(
                status_code=422,
                code="invalid_agent_draft",
                message=str(error),
            )

    @router.post(
        "/agent-drafts/{draft_id}/steps/{step_name}/plan",
        response_model=StepPlanResponse,
    )
    def plan_step(
        draft_id: str,
        step_name: str,
        capability_id: str | None = Query(default=None),
        principal: RequestPrincipal = principal_dependency,
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            draft = store.get_draft(draft_id, principal.actor_user_id)
            result = compile_source(draft.source)
            selected_ir = capability_ir(result.ir, capability_id)
            step = next(
                (item for item in selected_ir.get("steps", []) if item["id"] == step_name),
                None,
            )
            if step is None:
                return platform_error_response(
                    status_code=404,
                    code="agent_step_not_found",
                    message="The Agent Source step was not found.",
                )
            related_errors = [
                item
                for item in result.report["errors"]
                if str(item.get("path", "")).endswith(
                    f"steps.{step.get('source_index')}."
                ) or str(item.get("path", "")).startswith(f"steps.{step.get('source_index')}.")
            ]
            return StepPlanResponse(
                valid=not related_errors,
                step=step,
                report={**result.report, "errors": related_errors},
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/agent-drafts/{draft_id}/compile",
        response_model=CompileGenerationResponse,
    )
    def compile_draft(
        draft_id: str, principal: RequestPrincipal = principal_dependency
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            draft = store.get_draft(draft_id, principal.actor_user_id)
            result = compile_source(draft.source)
            generation = store.create_generation(
                draft,
                source_digest=result.source_digest,
                compiler_version=result.ir["compiler_version"],
                policy_version=result.ir["policy_version"],
                ir=result.ir,
                report=result.report,
                valid=result.valid,
            )
            return CompileGenerationResponse.from_record(generation)
        except (RepositoryError, ValueError) as error:
            if isinstance(error, RepositoryError):
                return repository_error_response(error)
            return platform_error_response(
                status_code=422,
                code="agent_compile_failed",
                message=str(error),
            )

    @router.post(
        "/agent-drafts/{draft_id}/runs",
        response_model=BrowserAgentRunResponse,
        status_code=202,
    )
    def create_draft_run(
        draft_id: str,
        request: BrowserAgentRunCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        if runtime is None or runtime.agents is None or runtime.agent_runtime is None:
            return platform_error_response(
                status_code=503,
                code="agent_runtime_not_ready",
                message="AI2Apps Agent Runtime is not ready.",
                retryable=True,
            )
        try:
            draft = store.get_draft(draft_id, principal.actor_user_id)
            result = compile_source(draft.source)
            if not result.valid:
                return platform_error_response(
                    status_code=422,
                    code="agent_compile_failed",
                    message="Agent Source cannot run until compile errors are fixed.",
                    details={"report": result.report},
                )
            chats = ChatRepository(runtime.database, runtime.events, principal=principal)
            builtin = chats.ensure_builtin()
            session_id = builtin.collection.selected_session_id
            if session_id is None:
                thread, _ = chats.create_thread(
                    title="Browser Agents",
                    metadata={"surface": "browser_agent_sidebar"},
                )
                session_id = thread.session.id
            run = create_ir_run(
                runtime,
                session_id=session_id,
                ir=capability_ir(result.ir, request.capability_id),
                invocation_input={},
                draft_id=draft.id,
                generation_id=draft.active_generation_id,
                browser_context=request.browser_context,
                owner_user_id=principal.actor_user_id,
                installation_id=principal.installation_id,
                preview=request.preview,
            )
            return BrowserAgentRunResponse(
                id=run.id,
                session_id=run.session_id,
                status=run.status.value,
                draft_id=draft.id,
                generation_id=draft.active_generation_id,
            )
        except (RepositoryError, ValueError) as error:
            if isinstance(error, RepositoryError):
                return repository_error_response(error)
            return platform_error_response(
                status_code=422,
                code="invalid_agent_run",
                message=str(error),
            )

    @router.get("/agent-draft-runs")
    def list_draft_runs(
        limit: int = Query(default=10, ge=1, le=100),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        if runtime is None or runtime.agents is None:
            return platform_error_response(
                status_code=503,
                code="agent_runtime_not_ready",
                message="AI2Apps Agent Runtime is not ready.",
                retryable=True,
            )
        definition = runtime.agents.get_definition(BROWSER_BUILDER_AGENT_KEY)
        runs = runtime.agents.list_runs(
            agent_definition_id=definition.id, root_only=True, limit=limit
        )
        visible = []
        for run in runs:
            try:
                authorize_session(runtime, principal, run.session_id)
            except HTTPException:
                continue
            visible.append(run_projection(runtime, run))
        return {"items": visible}

    @router.get("/agent-draft-runs/{run_id}")
    def get_draft_run(
        run_id: str, principal: RequestPrincipal = principal_dependency
    ):
        runtime = runtime_provider()
        if runtime is None or runtime.agents is None:
            return platform_error_response(
                status_code=503,
                code="agent_runtime_not_ready",
                message="AI2Apps Agent Runtime is not ready.",
                retryable=True,
            )
        try:
            return run_projection(runtime, browser_run(runtime, run_id, principal))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/agent-draft-runs/{run_id}/interactions/{interaction_id}/respond")
    def respond_draft_run(
        run_id: str,
        interaction_id: str,
        request: dict[str, Any],
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        try:
            browser_run(runtime, run_id, principal)
            response = request.get("response")
            response_id = request.get("response_id")
            if not isinstance(response, dict) or not isinstance(response_id, str):
                raise ValueError("response and response_id are required")
            runtime.agents.respond_interaction(
                run_id, interaction_id, response=response, response_id=response_id
            )
            runtime.agent_runtime.wake()
            return run_projection(runtime, runtime.agents.get_run(run_id))
        except RepositoryError as error:
            return repository_error_response(error)
        except ValueError as error:
            return platform_error_response(
                status_code=422, code="invalid_interaction_response", message=str(error)
            )

    @router.post("/agent-draft-runs/{run_id}/{action}")
    def control_draft_run(
        run_id: str,
        action: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        try:
            browser_run(runtime, run_id, principal)
            if action == "pause":
                run = runtime.agent_runtime.pause(run_id)
            elif action == "cancel":
                run = runtime.agent_runtime.cancel(run_id)
            elif action == "resume":
                run = runtime.agent_runtime.resume(run_id)
            else:
                raise HTTPException(status_code=404, detail="Unknown run action")
            return run_projection(runtime, run)
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/agent-drafts/{draft_id}/generations/{generation_id}/activate",
        response_model=AgentDraftResponse,
    )
    def activate_generation(
        draft_id: str,
        generation_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            return AgentDraftResponse.from_record(
                store.activate_generation(
                    draft_id, generation_id, principal.actor_user_id
                )
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/agent-drafts/{draft_id}/generations",
        response_model=list[CompileGenerationResponse],
    )
    def list_generations(
        draft_id: str, principal: RequestPrincipal = principal_dependency
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            return [
                CompileGenerationResponse.from_record(item)
                for item in store.list_generations(draft_id, principal.actor_user_id)
            ]
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/agent-drafts/{draft_id}/archive", response_model=AgentDraftResponse)
    def archive_draft(
        draft_id: str,
        request: dict[str, Any],
        principal: RequestPrincipal = principal_dependency,
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            return AgentDraftResponse.from_record(
                store.archive_draft(
                    draft_id,
                    principal.actor_user_id,
                    expected_revision=int(request.get("expected_revision") or 0),
                )
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/agent-drafts/{draft_id}/steps/{step_name}/evidence",
        response_model=StepEvidenceResponse,
        status_code=201,
    )
    def add_evidence(
        draft_id: str,
        step_name: str,
        request: StepEvidenceCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            return StepEvidenceResponse.from_record(
                store.add_evidence(
                    draft_id=draft_id,
                    owner_user_id=principal.actor_user_id,
                    step_name=step_name,
                    outcome=request.outcome,
                    evidence=request.evidence,
                    generation_id=request.generation_id,
                    run_id=request.run_id,
                    page_fingerprint=request.page_fingerprint,
                    user_feedback=request.user_feedback,
                )
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/agent-drafts/{draft_id}/evidence",
        response_model=list[StepEvidenceResponse],
    )
    def list_evidence(
        draft_id: str, principal: RequestPrincipal = principal_dependency
    ):
        store = repository()
        if isinstance(store, JSONResponse):
            return store
        try:
            return [
                StepEvidenceResponse.from_record(item)
                for item in store.list_evidence(draft_id, principal.actor_user_id)
            ]
        except RepositoryError as error:
            return repository_error_response(error)

    return router
