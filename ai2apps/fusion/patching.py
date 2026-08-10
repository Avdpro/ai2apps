"""Deterministic, hash-protected patch application for Fusion drafts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable

from .types import PatchOperation, StructuredPatch


class PatchApplyError(ValueError):
    pass


@dataclass(frozen=True)
class PatchApplyResult:
    text: str
    changed_ratio: float
    applied: int


_FENCED_BLOCK = re.compile(r"```[^\n]*\n(?P<body>.*?)```", re.DOTALL)


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _target_span(text: str, target: str) -> tuple[int, int]:
    if target == "document":
        return 0, len(text)
    match = re.fullmatch(r"code_block_(\d+)", target)
    if match is None:
        raise PatchApplyError(f"unsupported patch target: {target}")
    index = int(match.group(1))
    blocks = list(_FENCED_BLOCK.finditer(text))
    if index >= len(blocks):
        raise PatchApplyError(f"patch target does not exist: {target}")
    block = blocks[index]
    return block.start("body"), block.end("body")


def _apply_one(text: str, patch: StructuredPatch) -> str:
    start, end = _target_span(text, patch.target)
    target = text[start:end]
    count = target.count(patch.before)
    if count != patch.expected_occurrences:
        raise PatchApplyError(
            f"patch anchor matched {count} times in {patch.target}; "
            f"expected {patch.expected_occurrences}"
        )

    if patch.operation == PatchOperation.REPLACE:
        replacement = patch.after
    elif patch.operation == PatchOperation.INSERT_BEFORE:
        replacement = patch.after + patch.before
    elif patch.operation == PatchOperation.INSERT_AFTER:
        replacement = patch.before + patch.after
    elif patch.operation == PatchOperation.DELETE:
        replacement = ""
    else:  # pragma: no cover - enum validation prevents this
        raise PatchApplyError(f"unsupported patch operation: {patch.operation}")

    updated = target.replace(
        patch.before, replacement, patch.expected_occurrences
    )
    return text[:start] + updated + text[end:]


def _changed_ratio(before: str, after: str) -> float:
    denominator = max(len(before), len(after), 1)
    matching = sum(
        block.size
        for block in SequenceMatcher(None, before, after).get_matching_blocks()
    )
    return 1.0 - min(matching / denominator, 1.0)


def apply_structured_patches(
    draft: str,
    patches: Iterable[StructuredPatch],
    *,
    max_changed_ratio: float = 0.30,
) -> PatchApplyResult:
    patch_list = tuple(patches)
    if not patch_list:
        raise PatchApplyError("at least one patch is required")
    expected_hash = text_sha256(draft)
    for patch in patch_list:
        if patch.base_sha256 != expected_hash:
            raise PatchApplyError("patch base_sha256 does not match the draft")

    result = draft
    for patch in patch_list:
        result = _apply_one(result, patch)
    ratio = _changed_ratio(draft, result)
    if ratio > max_changed_ratio:
        raise PatchApplyError(
            f"patch changed ratio {ratio:.3f} exceeds limit {max_changed_ratio:.3f}"
        )
    return PatchApplyResult(result, ratio, len(patch_list))
