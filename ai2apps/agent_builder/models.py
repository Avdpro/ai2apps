"""Durable contracts for natural-language browser Agent authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AgentDraftStatus(StrEnum):
    EDITING = "editing"
    COMPILED = "compiled"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentType(StrEnum):
    WEB = "web"
    WORKFLOW = "workflow"
    KNOWLEDGE = "knowledge"
    RESEARCH = "research"
    CODING = "coding"
    APP = "app"
    COMPOSITE = "composite"


class CompileGenerationStatus(StrEnum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    ACTIVE = "active"
    FAILED = "failed"


class StepOutcome(StrEnum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    RETRYABLE_ERROR = "retryable_error"
    NEEDS_USER = "needs_user"
    RESTRICTED = "restricted"
    FAILED = "failed"


class AgentScheduleKind(StrEnum):
    ONCE = "once"
    INTERVAL = "interval"


class AgentScheduleStatus(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    COMPLETED = "completed"


class AgentHealthStatus(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    SUSPECT = "suspect"
    DRIFTED = "drifted"
    REPAIRING = "repairing"
    LOCAL_PATCHED = "local_patched"
    NEEDS_USER = "needs_user"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AgentDraftRecord:
    id: str
    owner_user_id: str
    agent_type: AgentType
    name: str
    description: str
    site_scope: tuple[str, ...]
    source: dict[str, Any]
    status: AgentDraftStatus
    active_generation_id: str | None
    revision: int
    created_at: datetime
    updated_at: datetime
    site_key: str = ""


@dataclass(frozen=True, slots=True)
class AgentRecipeRecord:
    id: str
    owner_user_id: str
    site_key: str
    name: str
    description: str
    source: dict[str, Any]
    page: dict[str, Any]
    status: str
    committed_draft_id: str | None
    committed_capability_id: str | None
    revision: int
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CompileGenerationRecord:
    id: str
    draft_id: str
    source_revision: int
    source_digest: str
    compiler_version: str
    policy_version: str
    ir: dict[str, Any]
    report: dict[str, Any]
    status: CompileGenerationStatus
    created_at: datetime
    activated_at: datetime | None


@dataclass(frozen=True, slots=True)
class StepEvidenceRecord:
    id: str
    draft_id: str
    generation_id: str | None
    run_id: str | None
    step_name: str
    page_fingerprint: str
    outcome: StepOutcome
    evidence: dict[str, Any]
    user_feedback: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AgentWorkflowRecord:
    id: str
    owner_user_id: str
    name: str
    description: str
    definition: dict[str, Any]
    status: str
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AgentScheduleRecord:
    id: str
    owner_user_id: str
    draft_id: str | None
    workflow_id: str | None
    session_id: str
    name: str
    kind: AgentScheduleKind
    status: AgentScheduleStatus
    input: dict[str, Any]
    knowledge_bucket_id: str | None
    interval_seconds: int | None
    run_at: datetime | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime
    installation_id: str = "local"
    max_concurrent_runs: int = 1
    max_failures: int = 5


@dataclass(frozen=True, slots=True)
class AgentScheduleDispatchRecord:
    id: str
    schedule_id: str
    run_id: str | None
    status: str
    error: dict[str, Any] | None
    dispatched_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class SiteAgentPackageBindingRecord:
    id: str
    owner_user_id: str
    package_key: str
    package_version: str
    package_digest: str
    publisher_id: str
    site_key: str
    draft_id: str
    granted_permissions: tuple[str, ...]
    source_digest: str
    hint_digest: str | None
    status: str
    installed_at: datetime
    updated_at: datetime
    source: dict[str, Any] = field(default_factory=dict)
    update_policy: str = "manual"
    pinned_version: str | None = None
    activated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AgentCapabilityHealthRecord:
    id: str
    owner_user_id: str
    draft_id: str
    capability_name: str
    status: AgentHealthStatus
    consecutive_failures: int
    success_count: int
    failure_count: int
    last_error_class: str | None
    last_error: dict[str, Any] | None
    structure_fingerprint: str
    circuit_open_until: datetime | None
    metrics: dict[str, Any]
    last_run_id: str | None
    last_success_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AgentSiteStateRecord:
    id: str
    owner_user_id: str
    draft_id: str
    capability_name: str
    source_identity: str
    generation_id: str
    checkpoint: dict[str, Any]
    item_index: dict[str, Any]
    structure_fingerprint: str
    calibration_status: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AgentRepairCandidateRecord:
    id: str
    owner_user_id: str
    draft_id: str
    capability_name: str
    base_generation_id: str
    candidate_generation_id: str | None
    strategy: str
    source: dict[str, Any]
    report: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
