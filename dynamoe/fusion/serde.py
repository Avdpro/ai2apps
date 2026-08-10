"""Strict JSON conversion for reviewer and resolver decisions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from .types import PatchOperation, ReviewAction, ReviewDecision, StructuredPatch


_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _as_tuple_strings(value: Any, field_name: str) -> tuple[str, ...]:
    if value in (None, []):
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must be a list of strings")
    return tuple(value)


def review_decision_from_mapping(value: Mapping[str, Any]) -> ReviewDecision:
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
                    base_sha256=str(raw["base_sha256"]),
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


def review_decision_from_json(text: str) -> ReviewDecision:
    fenced = _JSON_FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        decoder = json.JSONDecoder()
        candidates = []
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
            raise ValueError(f"review response is not valid JSON: {exc.msg}") from exc
        # Thinking models may emit an example object before the actual answer;
        # the constrained decision is the final JSON object in the response.
        value = candidates[-1]
    if not isinstance(value, Mapping):
        raise ValueError("review response must be a JSON object")
    return review_decision_from_mapping(value)
