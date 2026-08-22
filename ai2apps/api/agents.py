"""Asynchronous AgentRun, status, interaction, and cancellation APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ai2apps.agents import (
    AgentDefinitionRecord,
    AgentDefinitionStatus,
    AgentRunRecord,
    AgentRunStatus,
    InteractionRecord,
    RunStepRecord,
    StatusLineRecord,
)
from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.api.ownership import (
    authorize_session,
    require_agent_run_access,
    require_session_access,
)
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.core import RepositoryError
from ai2apps.events.stream import stream_events
from ai2apps.identity import RequestPrincipal
from ai2apps.platform_runtime import PlatformRuntime


class AgentDefinitionResponse(BaseModel):
    id: str
    agent_key: str
    package_version: str
    display_name: str
    description: str
    source: str
    status: str
    executor_key: str
    concurrency_group: str | None
    concurrency_limit: int | None
    max_steps: int
    timeout_seconds: int
    resume_policy: str
    manifest: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime
    discoverable: bool
    invocation_schema: dict[str, Any]
    ui_hints: dict[str, Any]
    aliases: list[str]

    @classmethod
    def from_record(cls, record: AgentDefinitionRecord):
        manifest = record.manifest or {}
        aliases = [record.agent_key]
        manifest_aliases = manifest.get("aliases", [])
        if not isinstance(manifest_aliases, list):
            manifest_aliases = []
        aliases.extend(
            str(item).strip()
            for item in manifest_aliases
            if str(item).strip()
        )
        invocation_schema = manifest.get("invocation_schema")
        if not isinstance(invocation_schema, dict):
            invocation_schema = {"type": "object", "properties": {}}
        ui_hints = manifest.get("invocation_ui")
        if not isinstance(ui_hints, dict):
            ui_hints = {}
        return cls(
            **{
                field: getattr(record, field)
                for field in cls.model_fields
                if hasattr(record, field)
            },
            discoverable=bool(
                manifest.get(
                    "discoverable",
                    record.agent_key != "ai2apps.diagnostic-agent",
                )
            ),
            invocation_schema=invocation_schema,
            ui_hints=ui_hints,
            aliases=list(dict.fromkeys(aliases)),
        )


class AgentDefinitionListResponse(BaseModel):
    items: list[AgentDefinitionResponse]


class StatusLineResponse(BaseModel):
    id: str
    phase: str
    text: str
    presentation: str
    progress: float | None
    content: dict[str, Any]
    revision: int

    @classmethod
    def from_record(cls, record: StatusLineRecord):
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class RunStepResponse(BaseModel):
    id: str
    sequence: int
    action_key: str
    kind: str
    status: str
    tool_name: str | None
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: dict[str, Any] | None

    @classmethod
    def from_record(cls, record: RunStepRecord):
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class InteractionResponse(BaseModel):
    id: str
    request_key: str
    kind: str
    status: str
    prompt: str
    response_schema: dict[str, Any]
    ui_hints: dict[str, Any]
    request: dict[str, Any]
    response: dict[str, Any] | None
    deadline_at: datetime
    revision: int

    @classmethod
    def from_record(cls, record: InteractionRecord):
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class AgentRunResponse(BaseModel):
    id: str
    agent_definition_id: str
    agent_key: str
    agent_display_name: str
    agent_package_version: str
    session_id: str
    parent_run_id: str | None
    root_run_id: str
    depth: int
    delegation: dict[str, Any]
    child_run_ids: list[str]
    status: str
    priority: int
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: dict[str, Any] | None
    current_step: int
    budget: dict[str, int]
    usage: dict[str, int]
    revision: int
    deadline_at: datetime
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    status_line: StatusLineResponse
    steps: list[RunStepResponse]
    interactions: list[InteractionResponse]
    event_stream_url: str


class AgentRunBudgetRequest(BaseModel):
    max_steps: int | None = Field(default=None, ge=1, le=10_000)
    timeout_seconds: int | None = Field(default=None, ge=1, le=604_800)
    max_model_tokens: int | None = Field(default=None, ge=1)


class AgentRunCreateRequest(BaseModel):
    agent: str = "ai2apps.general-agent"
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    priority: int = Field(default=0, ge=-100, le=100)
    budget: AgentRunBudgetRequest | None = None


class AgentRunListResponse(BaseModel):
    items: list[AgentRunResponse]


class InteractionSubmitRequest(BaseModel):
    response: dict[str, Any]
    response_id: str = Field(min_length=1)


class InteractionDecisionRequest(BaseModel):
    response_id: str = Field(min_length=1)
    scope: str = Field(default="run", pattern="^(run|session|agent|app)$")


class ResumeRunRequest(BaseModel):
    uncertain_resolution: str | None = None


class RetryRunRequest(BaseModel):
    idempotency_key: str | None = None


def _runtime_or_error(runtime_provider: PlatformRuntimeProvider):
    runtime = runtime_provider()
    if (
        runtime is None
        or runtime.agents is None
        or runtime.agent_runtime is None
        or runtime.events is None
        or runtime.notifications is None
    ):
        return platform_error_response(
            status_code=503,
            code="agent_runtime_not_ready",
            message="AI2Apps Agent Runtime is not ready.",
            retryable=True,
        )
    return runtime


def _run_response(runtime: PlatformRuntime, run: AgentRunRecord) -> AgentRunResponse:
    definition = runtime.agents.get_definition(run.agent_definition_id)
    status = runtime.agents.get_status_line(run.id)
    steps = runtime.agents.list_steps(run.id)
    interactions = runtime.agents.list_interactions(run.id)
    requested_budget = run.input.get("run_budget")
    requested_budget = requested_budget if isinstance(requested_budget, dict) else {}
    max_steps = requested_budget.get("max_steps", definition.max_steps)
    if not isinstance(max_steps, int) or max_steps <= 0:
        max_steps = definition.max_steps
    max_steps = min(max_steps, definition.max_steps)
    timeout_seconds = requested_budget.get(
        "timeout_seconds", definition.timeout_seconds
    )
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        timeout_seconds = definition.timeout_seconds
    timeout_seconds = min(timeout_seconds, definition.timeout_seconds)
    configured_tokens = definition.manifest.get("max_total_model_tokens", 100_000)
    max_model_tokens = requested_budget.get("max_model_tokens", configured_tokens)
    if not isinstance(max_model_tokens, int) or max_model_tokens <= 0:
        max_model_tokens = 100_000
    if isinstance(configured_tokens, int) and configured_tokens > 0:
        max_model_tokens = min(max_model_tokens, configured_tokens)
    model_tokens = 0
    for step in steps:
        if step.kind != "model" or not isinstance(step.output, dict):
            continue
        usage = step.output.get("usage")
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        if isinstance(total, int) and total > 0:
            model_tokens += total
    return AgentRunResponse(
        id=run.id,
        agent_definition_id=run.agent_definition_id,
        agent_key=definition.agent_key,
        agent_display_name=definition.display_name,
        agent_package_version=(run.input.get("invocation") or {}).get(
            "package_version", definition.package_version
        ),
        session_id=run.session_id,
        parent_run_id=run.parent_run_id,
        root_run_id=run.root_run_id,
        depth=run.depth,
        delegation=run.delegation,
        child_run_ids=[child.id for child in runtime.agents.list_children(run.id)],
        status=run.status.value,
        priority=run.priority,
        input=run.input,
        output=run.output,
        error=run.error,
        current_step=run.current_step,
        budget={
            "max_steps": max_steps,
            "timeout_seconds": timeout_seconds,
            "max_model_tokens": max_model_tokens,
        },
        usage={"steps": run.current_step, "model_tokens": model_tokens},
        revision=run.revision,
        deadline_at=run.deadline_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status_line=StatusLineResponse.from_record(status),
        steps=[RunStepResponse.from_record(step) for step in steps],
        interactions=[
            InteractionResponse.from_record(interaction) for interaction in interactions
        ],
        event_stream_url=f"/v1/platform/agent-runs/{run.id}/events",
    )


def create_agent_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ]
    )
    principal_dependency = Depends(principal_provider)
    session_access = Depends(require_session_access(runtime_provider, principal_provider))
    run_access = Depends(require_agent_run_access(runtime_provider, principal_provider))

    @router.get("/agents", response_model=AgentDefinitionListResponse)
    def list_agents():
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        return AgentDefinitionListResponse(
            items=[
                AgentDefinitionResponse.from_record(item)
                for item in runtime.agents.list_definitions()
            ]
        )

    @router.get("/agents/{agent_key}/management")
    def agent_management(agent_key: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            definition = runtime.agents.get_definition(agent_key)
            packages = []
            patches = []
            effective = None
            if runtime.extension_repository is not None:
                from ai2apps.extensions import UnitKind

                packages = [
                    {
                        "id": item.id,
                        "version": item.version,
                        "digest": item.digest,
                        "publisher": item.publisher_key,
                        "status": item.status.value,
                        "verification": item.verification,
                        "installed_at": item.installed_at,
                        "activated_at": item.activated_at,
                    }
                    for item in runtime.extension_repository.installed(
                        UnitKind.AGENT, definition.agent_key
                    )
                ]
                patches = [
                    {
                        "id": item.id,
                        "version": item.version,
                        "digest": item.digest,
                        "base_digest": item.base_digest,
                        "intent": item.intent,
                        "rebase_policy": item.rebase_policy.value,
                        "status": item.status.value,
                        "conflict": item.conflict,
                        "stack_order": item.stack_order,
                        "audit": item.audit,
                    }
                    for item in runtime.extension_repository.patches(
                        UnitKind.AGENT, definition.agent_key
                    )
                ]
                effective_record = runtime.extension_repository.effective(
                    UnitKind.AGENT, definition.agent_key
                )
                if effective_record is not None:
                    effective = {
                        "id": effective_record.id,
                        "upstream_digest": effective_record.upstream_digest,
                        "patch_set_digest": effective_record.patch_set_digest,
                        "effective_digest": effective_record.effective_digest,
                        "effective_version": effective_record.effective_version,
                        "audit": effective_record.audit,
                        "status": effective_record.status,
                        "revision": effective_record.revision,
                    }
            recent = runtime.agents.list_runs(
                agent_definition_id=definition.id, limit=20
            )
            return {
                "definition": AgentDefinitionResponse.from_record(definition),
                "run_counts": runtime.agents.run_counts(definition.id),
                "recent_runs": [_run_response(runtime, run) for run in recent],
                "packages": packages,
                "patches": patches,
                "effective_definition": effective,
            }
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/agents/{agent_key}/enable", response_model=AgentDefinitionResponse)
    def enable_agent(agent_key: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return AgentDefinitionResponse.from_record(
                runtime.agents.set_definition_status(
                    agent_key, AgentDefinitionStatus.ENABLED
                )
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post("/agents/{agent_key}/disable", response_model=AgentDefinitionResponse)
    def disable_agent(agent_key: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return AgentDefinitionResponse.from_record(
                runtime.agents.set_definition_status(
                    agent_key, AgentDefinitionStatus.DISABLED
                )
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get("/agent-runs", response_model=AgentRunListResponse)
    def list_runs(
        agent: str | None = None,
        status: str | None = None,
        root_only: bool = False,
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            definition_id = (
                None if agent is None else runtime.agents.get_definition(agent).id
            )
            parsed_status = None if status is None else AgentRunStatus(status)
            runs = runtime.agents.list_runs(
                agent_definition_id=definition_id,
                status=parsed_status,
                root_only=root_only,
                limit=limit,
                offset=offset,
            )
            if principal.authentication_type != "legacy_api_key":
                owned_runs = []
                for run in runs:
                    try:
                        authorize_session(runtime, principal, run.session_id)
                    except HTTPException:
                        continue
                    owned_runs.append(run)
                runs = tuple(owned_runs)
            return AgentRunListResponse(
                items=[_run_response(runtime, run) for run in runs]
            )
        except RepositoryError as error:
            return repository_error_response(error)
        except ValueError as error:
            return platform_error_response(
                status_code=422,
                code="invalid_agent_run_filter",
                message=str(error),
            )

    @router.post(
        "/sessions/{session_id}/agent-runs",
        response_model=AgentRunResponse,
        status_code=202,
        dependencies=[session_access],
    )
    def create_run(
        session_id: str,
        request: AgentRunCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        x_trace_id: str | None = Header(default=None),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        if (
            idempotency_key
            and request.idempotency_key
            and idempotency_key != request.idempotency_key
        ):
            return platform_error_response(
                status_code=400,
                code="idempotency_key_mismatch",
                message="Header and body idempotency keys must match.",
            )
        try:
            run, _ = runtime.agents.create_run(
                session_id=session_id,
                agent_key=request.agent,
                input=request.input,
                idempotency_key=idempotency_key or request.idempotency_key,
                priority=request.priority,
                trace_id=x_trace_id,
                budget=(
                    None
                    if request.budget is None
                    else request.budget.model_dump(exclude_none=True)
                ),
            )
            runtime.agent_runtime.wake()
            return _run_response(runtime, run)
        except RepositoryError as error:
            return repository_error_response(error)
        except ValueError as error:
            return platform_error_response(
                status_code=422,
                code="invalid_agent_parameters",
                message=str(error),
            )

    @router.get(
        "/agent-runs/{run_id}",
        response_model=AgentRunResponse,
        dependencies=[run_access],
    )
    def get_run(run_id: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return _run_response(runtime, runtime.agents.get_run(run_id))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/agent-runs/{run_id}/children",
        response_model=list[AgentRunResponse],
        dependencies=[run_access],
    )
    def list_child_runs(run_id: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            runtime.agents.get_run(run_id)
            return [
                _run_response(runtime, child)
                for child in runtime.agents.list_children(run_id)
            ]
        except RepositoryError as error:
            return repository_error_response(error)

    @router.get(
        "/agent-runs/{run_id}/events",
        response_model=None,
        dependencies=[run_access],
    )
    async def run_events(
        run_id: str,
        after: int | None = Query(default=None, ge=0),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            runtime.agents.get_run(run_id)
        except RepositoryError as error:
            return repository_error_response(error)
        cursor = after
        if cursor is None and last_event_id is not None:
            try:
                cursor = int(last_event_id)
            except ValueError:
                return platform_error_response(
                    status_code=400,
                    code="invalid_event_cursor",
                    message="Last-Event-ID must be a non-negative integer.",
                )
            if cursor < 0:
                return platform_error_response(
                    status_code=400,
                    code="invalid_event_cursor",
                    message="Last-Event-ID must be a non-negative integer.",
                )
        return StreamingResponse(
            stream_events(
                runtime.events,
                runtime.notifications,
                after_sequence=cursor or 0,
                subject_id=run_id,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post(
        "/agent-runs/{run_id}/interactions/{interaction_id}/respond",
        response_model=AgentRunResponse,
        dependencies=[run_access],
    )
    def respond_interaction(
        run_id: str,
        interaction_id: str,
        request: InteractionSubmitRequest,
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            runtime.agents.respond_interaction(
                run_id,
                interaction_id,
                response=request.response,
                response_id=request.response_id,
            )
            runtime.agent_runtime.wake()
            return _run_response(runtime, runtime.agents.get_run(run_id))
        except RepositoryError as error:
            return repository_error_response(error)

    async def decide(
        run_id: str,
        interaction_id: str,
        request: InteractionDecisionRequest,
        decision: str,
    ):
        return respond_interaction(
            run_id,
            interaction_id,
            InteractionSubmitRequest(
                response={
                    "decision": decision,
                    **({"scope": request.scope} if decision == "approve" else {}),
                },
                response_id=request.response_id,
            ),
        )

    @router.post(
        "/agent-runs/{run_id}/approve/{interaction_id}",
        response_model=AgentRunResponse,
        dependencies=[run_access],
    )
    async def approve(
        run_id: str,
        interaction_id: str,
        request: InteractionDecisionRequest,
    ):
        return await decide(run_id, interaction_id, request, "approve")

    @router.post(
        "/agent-runs/{run_id}/deny/{interaction_id}",
        response_model=AgentRunResponse,
        dependencies=[run_access],
    )
    async def deny(
        run_id: str,
        interaction_id: str,
        request: InteractionDecisionRequest,
    ):
        return await decide(run_id, interaction_id, request, "deny")

    @router.post(
        "/agent-runs/{run_id}/cancel",
        response_model=AgentRunResponse,
        dependencies=[run_access],
    )
    def cancel_run(run_id: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return _run_response(runtime, runtime.agent_runtime.cancel(run_id))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/agent-runs/{run_id}/pause",
        response_model=AgentRunResponse,
        dependencies=[run_access],
    )
    async def pause_run(run_id: str):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            return _run_response(runtime, runtime.agent_runtime.pause(run_id))
        except RepositoryError as error:
            return repository_error_response(error)

    @router.post(
        "/agent-runs/{run_id}/resume",
        response_model=AgentRunResponse,
        dependencies=[run_access],
    )
    def resume_run(run_id: str, request: ResumeRunRequest):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            run = runtime.agent_runtime.resume(
                run_id,
                uncertain_resolution=request.uncertain_resolution,
            )
            return _run_response(runtime, run)
        except (RepositoryError, ValueError) as error:
            if isinstance(error, RepositoryError):
                return repository_error_response(error)
            return platform_error_response(
                status_code=422,
                code="invalid_resume_resolution",
                message=str(error),
            )

    @router.post(
        "/agent-runs/{run_id}/retry",
        response_model=AgentRunResponse,
        status_code=202,
        dependencies=[run_access],
    )
    def retry_run(
        run_id: str,
        request: RetryRunRequest,
        x_trace_id: str | None = Header(default=None),
    ):
        runtime = _runtime_or_error(runtime_provider)
        if isinstance(runtime, JSONResponse):
            return runtime
        try:
            run, _ = runtime.agents.retry_run(
                run_id,
                idempotency_key=request.idempotency_key,
                trace_id=x_trace_id,
            )
            runtime.agent_runtime.wake()
            return _run_response(runtime, run)
        except RepositoryError as error:
            return repository_error_response(error)

    return router
