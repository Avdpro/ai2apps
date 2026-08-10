"""Typed protocol objects shared by Fusion backends and transports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class _StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class StreamMode(_StringEnum):
    DRAFT = "draft"
    REASONING = "reasoning"
    FINAL = "final"


class GateDecision(_StringEnum):
    SKIP = "skip"
    REVIEW = "review"
    FORCE = "force"


class ReviewAction(_StringEnum):
    PASS = "pass"
    PATCH = "patch"
    REVISE = "revise"
    ESCALATE = "escalate"


class PatchOperation(_StringEnum):
    REPLACE = "replace"
    INSERT_BEFORE = "insert_before"
    INSERT_AFTER = "insert_after"
    DELETE = "delete"


class FailurePolicy(_StringEnum):
    RETURN_DRAFT = "return_draft"
    LOCAL_REBUILD = "local_rebuild"
    ERROR = "error"


@dataclass(frozen=True)
class GateSignals:
    """Signals collected without adding a per-token host synchronization."""

    output_tokens: int = 0
    output_chars: int = 0
    finish_reason: str = "stop"
    mean_nll: float | None = None
    tail_nll: float | None = None
    p95_nll: float | None = None
    low_confidence_ratio: float | None = None
    min_logit_margin: float | None = None
    uncertainty_spikes: int = 0
    structural_failure: bool = False
    scope_confidence: float | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuredPatch:
    base_sha256: str
    target: str = "document"
    operation: PatchOperation = PatchOperation.REPLACE
    before: str = ""
    after: str = ""
    expected_occurrences: int = 1

    def __post_init__(self) -> None:
        if not self.base_sha256:
            raise ValueError("patch base_sha256 is required")
        if self.expected_occurrences < 1:
            raise ValueError("patch expected_occurrences must be >= 1")
        if not self.before:
            raise ValueError(f"patch before is required for {self.operation.value}")
        if self.operation == PatchOperation.DELETE and self.after:
            raise ValueError("delete patch must not provide after text")


@dataclass(frozen=True)
class ReviewDecision:
    action: ReviewAction
    summary: str = ""
    risk: str = "medium"
    confidence: float | None = None
    patches: tuple[StructuredPatch, ...] = ()
    instructions: tuple[str, ...] = ()
    blueprint: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.risk not in {"low", "medium", "high"}:
            raise ValueError("review risk must be low, medium, or high")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("review confidence must be in [0, 1]")
        if self.action == ReviewAction.PATCH and not self.patches:
            raise ValueError("PATCH decision requires at least one patch")
        if self.action == ReviewAction.REVISE and not self.instructions:
            raise ValueError("REVISE decision requires instructions")


@dataclass(frozen=True)
class DraftChunk:
    text: str = ""
    token_count: int = 0
    finished: bool = False
    finish_reason: str = "stop"
    signals: GateSignals | None = None


@dataclass(frozen=True)
class FusionRequest:
    messages: Sequence[Mapping[str, Any]]
    session_id: str
    max_tokens: int = 256
    stream_mode: StreamMode = StreamMode.REASONING
    sampling: Mapping[str, Any] = field(default_factory=dict)
    prompt_risk: float | None = None
    high_risk: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("Fusion session_id is required")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if self.prompt_risk is not None and not 0.0 <= self.prompt_risk <= 1.0:
            raise ValueError("prompt_risk must be in [0, 1]")


@dataclass(frozen=True)
class FusionConfig:
    model_id: str
    gate_policy: str = "adaptive"
    review_threshold: float = 0.45
    force_threshold: float = 0.85
    long_output_tokens: int = 512
    mean_nll_threshold: float = 2.5
    low_confidence_ratio_threshold: float = 0.12
    min_margin_threshold: float = 0.20
    reviewer_timeout_seconds: float = 30.0
    resolver_timeout_seconds: float = 30.0
    resolver_enabled: bool = False
    resolver_triggers: tuple[str, ...] = (
        "reviewer_escalate",
        "reviewer_uncertain",
        "patch_failed",
    )
    reviewer_escalate_below: float = 0.35
    max_changed_ratio: float = 0.30
    reviewer_failure_policy: FailurePolicy = FailurePolicy.RETURN_DRAFT
    resolver_unavailable_policy: FailurePolicy = FailurePolicy.LOCAL_REBUILD
    high_risk_failure_policy: FailurePolicy = FailurePolicy.ERROR
    replay_chunk_chars: int = 512

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("Fusion model_id is required")
        if self.gate_policy not in {"off", "always", "adaptive"}:
            raise ValueError("gate_policy must be off, always, or adaptive")
        if not 0 <= self.review_threshold <= self.force_threshold <= 1:
            raise ValueError("gate thresholds must satisfy 0 <= review <= force <= 1")
        if not 0 < self.max_changed_ratio <= 1:
            raise ValueError("max_changed_ratio must be in (0, 1]")
        if self.reviewer_timeout_seconds <= 0 or self.resolver_timeout_seconds <= 0:
            raise ValueError("Fusion timeouts must be positive")
        if (
            self.long_output_tokens < 1
            or self.mean_nll_threshold <= 0
            or self.low_confidence_ratio_threshold <= 0
            or self.min_margin_threshold <= 0
        ):
            raise ValueError("Fusion gate thresholds must be positive")
        allowed_triggers = {
            "reviewer_escalate",
            "reviewer_uncertain",
            "patch_failed",
        }
        unknown_triggers = set(self.resolver_triggers) - allowed_triggers
        if unknown_triggers:
            raise ValueError(
                f"unknown resolver triggers: {sorted(unknown_triggers)}"
            )
        if not 0.0 <= self.reviewer_escalate_below <= 1.0:
            raise ValueError("reviewer_escalate_below must be in [0, 1]")
        if self.replay_chunk_chars < 1:
            raise ValueError("replay_chunk_chars must be >= 1")


@dataclass(frozen=True)
class FusionEvent:
    phase: str
    channel: str = "control"
    text: str = ""
    draft_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FusionResult:
    text: str
    draft: str
    draft_id: str
    gate_decision: GateDecision
    review_action: ReviewAction | None
    path: str
    signals: GateSignals
    metadata: Mapping[str, Any] = field(default_factory=dict)
