"""Strict JSON conversion for reviewer and resolver decisions."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from omlx.api.thinking import extract_thinking

from .types import (
    CheckpointAction,
    CheckpointDecision,
    PatchOperation,
    ReviewAction,
    ReviewDecision,
    StructuredPatch,
    ToolReviewAction,
    ToolReviewDecision,
)

_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)
_DecisionT = TypeVar("_DecisionT")


def _decision_from_json(
    text: str,
    converter: Callable[[Mapping[str, Any]], _DecisionT],
    *,
    protocol: str,
) -> _DecisionT:
    """Parse the last protocol-valid object, ignoring model reasoning."""

    _, regular = extract_thinking(text)
    text = regular
    fenced = _JSON_FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        decoder = json.JSONDecoder()
        candidates: list[Mapping[str, Any]] = []
        for start, character in enumerate(text):
            if character != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, Mapping):
                candidates.append(candidate)
        if not candidates:
            raise ValueError(
                f"{protocol} response is not valid JSON: {exc.msg}"
            ) from exc

        validation_error: ValueError | None = None
        # Nested objects (for example blueprint={}) appear after their parent
        # in the scan. Select the last *protocol-valid* object, not merely the
        # last syntactically valid JSON object.
        for candidate in reversed(candidates):
            try:
                return converter(candidate)
            except ValueError as candidate_error:
                validation_error = candidate_error
        assert validation_error is not None
        raise validation_error from exc

    if not isinstance(value, Mapping):
        raise ValueError(f"{protocol} response must be a JSON object")
    return converter(value)


def _as_tuple_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if value in (None, []):
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return tuple(value)


def review_decision_from_mapping(
    value: Mapping[str, Any], *, base_sha256: str | None = None
) -> ReviewDecision:
    try:
        action = ReviewAction(str(value["action"]).lower())
    except (KeyError, ValueError) as exc:
        raise ValueError("review action is missing or invalid") from exc

    raw_patches = value.get("patches") or []
    if not isinstance(raw_patches, list):
        raise ValueError("review patches must be a list")
    patches: list[StructuredPatch] = []
    for raw in raw_patches:
        if not isinstance(raw, Mapping):
            raise ValueError("each review patch must be an object")
        try:
            operation = PatchOperation(str(raw.get("operation", "replace")).lower())
            patches.append(
                StructuredPatch(
                    base_sha256=str(raw.get("base_sha256") or base_sha256 or ""),
                    target=str(raw.get("target", "document")),
                    operation=operation,
                    before=str(raw.get("before", "")),
                    after=str(raw.get("after", "")),
                    expected_occurrences=int(raw.get("expected_occurrences", 1)),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid review patch: {exc}") from exc

    blueprint = value.get("blueprint") or {}
    metadata = value.get("metadata") or {}
    if not isinstance(blueprint, Mapping):
        raise ValueError("review blueprint must be an object")
    if not isinstance(metadata, Mapping):
        raise ValueError("review metadata must be an object")
    confidence = value.get("confidence")
    return ReviewDecision(
        action=action,
        summary=str(value.get("summary", "")),
        risk=str(value.get("risk", "medium")).lower(),
        confidence=float(confidence) if confidence is not None else None,
        patches=tuple(patches),
        instructions=_as_tuple_strings(value.get("instructions"), "instructions"),
        blueprint=dict(blueprint),
        metadata=dict(metadata),
    )


def review_decision_from_json(
    text: str, *, base_sha256: str | None = None
) -> ReviewDecision:
    return _decision_from_json(
        text,
        lambda value: review_decision_from_mapping(
            value, base_sha256=base_sha256
        ),
        protocol="review",
    )


def checkpoint_decision_from_mapping(
    value: Mapping[str, Any],
) -> CheckpointDecision:
    try:
        action = CheckpointAction(str(value["action"]).lower())
    except (KeyError, ValueError) as exc:
        raise ValueError("checkpoint action is missing or invalid") from exc
    confidence = value.get("confidence")
    metadata = value.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise ValueError("checkpoint metadata must be an object")
    return CheckpointDecision(
        action=action,
        summary=str(value.get("summary", "")),
        confidence=float(confidence) if confidence is not None else None,
        guidance=_as_tuple_strings(value.get("guidance"), "guidance"),
        reasoning_seed=str(value.get("reasoning_seed", "")),
        constraints=_as_tuple_strings(value.get("constraints"), "constraints"),
        metadata=dict(metadata),
    )


def checkpoint_decision_from_json(text: str) -> CheckpointDecision:
    return _decision_from_json(
        text, checkpoint_decision_from_mapping, protocol="checkpoint"
    )


def tool_review_decision_from_mapping(
    value: Mapping[str, Any],
) -> ToolReviewDecision:
    try:
        action = ToolReviewAction(str(value["action"]).lower())
    except (KeyError, ValueError) as exc:
        raise ValueError("tool review action is missing or invalid") from exc
    confidence = value.get("confidence")
    return ToolReviewDecision(
        action=action,
        summary=str(value.get("summary", "")),
        confidence=float(confidence) if confidence is not None else None,
        guidance=_as_tuple_strings(value.get("guidance"), "guidance"),
        user_message=str(value.get("user_message", "")),
    )


def tool_review_decision_from_json(text: str) -> ToolReviewDecision:
    return _decision_from_json(
        text, tool_review_decision_from_mapping, protocol="tool review"
    )
