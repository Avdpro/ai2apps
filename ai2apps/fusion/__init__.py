"""Model-independent local-first Fusion orchestration."""

from .engine import FusionOrchestrator
from .gate import AdaptiveGate
from .patching import PatchApplyError, apply_structured_patches, text_sha256
from .serde import review_decision_from_json, review_decision_from_mapping
from .types import (
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
)

__all__ = [
    "AdaptiveGate",
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
    "apply_structured_patches",
    "text_sha256",
    "review_decision_from_json",
    "review_decision_from_mapping",
]
