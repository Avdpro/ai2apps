"""Durable capability policy and GrantLease contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class GrantScope(StrEnum):
    RUN = "run"
    SESSION = "session"
    AGENT = "agent"
    APP = "app"


class CapabilityRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CapabilityPolicyRecord:
    id: str
    policy_key: str
    effect: PolicyEffect
    capability_pattern: str
    agent_pattern: str
    tool_pattern: str
    priority: int
    enabled: bool
    source: str
    conditions: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class GrantLeaseRecord:
    id: str
    scope: GrantScope
    scope_id: str
    agent_definition_id: str | None
    session_id: str
    app_instance_id: str
    capabilities: tuple[str, ...]
    tool_pattern: str
    tool_service_digest: str | None
    resource_selector: dict[str, Any]
    issued_by: str
    evidence: dict[str, Any]
    expires_at: datetime | None
    revoked_at: datetime | None
    revoke_reason: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def active(self) -> bool:
        return self.revoked_at is None and (
            self.expires_at is None or self.expires_at > datetime.now(self.expires_at.tzinfo)
        )


@dataclass(frozen=True, slots=True)
class CapabilityRequestRecord:
    id: str
    subject_kind: str
    app_instance_id: str
    session_id: str
    run_id: str | None
    capabilities: tuple[str, ...]
    tool_name: str
    effects: tuple[str, ...]
    resource_selector: dict[str, Any]
    reason: str
    risk_level: str
    status: CapabilityRequestStatus
    requested_by: str
    decision_scope: str | None
    decision_evidence: dict[str, Any]
    grant_lease_id: str | None
    deadline_at: datetime
    revision: int
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    effect: PolicyEffect
    source: str
    capabilities: tuple[str, ...]
    allowed_capabilities: tuple[str, ...]
    matched_policy_ids: tuple[str, ...] = ()
    matched_lease_ids: tuple[str, ...] = ()
    evidence: dict[str, Any] | None = None
