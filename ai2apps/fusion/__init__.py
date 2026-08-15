"""Model-independent local-first Fusion orchestration."""

from .engine import FusionOrchestrator
from .gate import AdaptiveGate
from .patching import PatchApplyError, apply_structured_patches, text_sha256
from .serde import (
    checkpoint_decision_from_json,
    checkpoint_decision_from_mapping,
    review_decision_from_json,
    review_decision_from_mapping,
    tool_review_decision_from_json,
    tool_review_decision_from_mapping,
)
from .types import (
    CheckpointAction,
    CheckpointDecision,
    DraftChunk,
    FailurePolicy,
    FusionConfig,
    FusionEvent,
    FusionRequest,
    FusionResult,
    GateDecision,
    GateSignals,
    ReviewAction,
    ReviewDecision,
    StreamMode,
    StructuredPatch,
    FusionToolCall,
    ToolReviewAction,
    ToolReviewDecision,
)

__all__ = [
    "AdaptiveGate",
    "CheckpointAction",
    "CheckpointDecision",
    "DraftChunk",
    "FailurePolicy",
    "FusionConfig",
    "FusionEvent",
    "FusionOrchestrator",
    "FusionRequest",
    "FusionResult",
    "GateDecision",
    "GateSignals",
    "PatchApplyError",
    "ReviewAction",
    "ReviewDecision",
    "StreamMode",
    "StructuredPatch",
    "FusionToolCall",
    "ToolReviewAction",
    "ToolReviewDecision",
    "apply_structured_patches",
    "text_sha256",
    "checkpoint_decision_from_json",
    "checkpoint_decision_from_mapping",
    "review_decision_from_json",
    "review_decision_from_mapping",
    "tool_review_decision_from_json",
    "tool_review_decision_from_mapping",
]
