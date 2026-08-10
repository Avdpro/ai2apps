"""Backend-neutral prompts for the first Fusion protocol version."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from .types import ReviewDecision


REVIEW_SYSTEM_PROMPT = """You are the reviewer inside a composite inference model.
Assess factual, logical, computational, code, and explicit-requirement errors.
Do not request changes for style alone. Return one JSON object and no prose.

Actions:
- PASS: the answer is deliverable.
- PATCH: return deterministic minimal patches for local defects.
- REVISE: return at most three exact instructions when a patch cannot be
  authored safely.
- ESCALATE: the core solution is wrong, uncertain, or requires a large rewrite.

Never rewrite a long answer. PATCH operations are replace, insert_before,
insert_after, or delete. Each patch must repeat the supplied draft SHA-256 in
base_sha256, use target=document or code_block_N, and use an exact unique before
anchor. ESCALATE should include a short fallback blueprint when possible.

Schema:
{"action":"PASS|PATCH|REVISE|ESCALATE","summary":"...",
"risk":"low|medium|high","confidence":0.0,"patches":[],
"instructions":[],"blueprint":{}}
"""


def _json_messages(messages: Sequence[Mapping[str, object]]) -> str:
    return json.dumps(list(messages), ensure_ascii=False, separators=(",", ":"))


def build_review_messages(
    messages: Sequence[Mapping[str, object]], draft: str, draft_sha256: str
) -> list[dict[str, str]]:
    payload = {
        "conversation": json.loads(_json_messages(messages)),
        "draft_sha256": draft_sha256,
        "draft": draft,
    }
    return [
        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def build_revision_messages(
    messages: Sequence[Mapping[str, object]],
    draft: str,
    draft_sha256: str,
    decision: ReviewDecision,
) -> list[dict[str, str]]:
    instructions = json.dumps(list(decision.instructions), ensure_ascii=False)
    prompt = f"""Return only a JSON object with a patches array. Apply the review
instructions as deterministic minimal anchor patches against the draft. Do not
rewrite the complete answer. Every patch must use base_sha256={draft_sha256}.

Instructions: {instructions}
Draft:
{draft}
"""
    return [
        {"role": "system", "content": prompt},
        *[dict(message) for message in messages],
    ]


def build_realization_messages(
    messages: Sequence[Mapping[str, object]], blueprint: Mapping[str, object]
) -> list[dict[str, object]]:
    instruction = """Produce the final answer from the authoritative blueprint.
Do not add facts, numbers, claims, or code behavior outside it. Preserve every
exact fragment verbatim. Return only the complete user-facing answer."""
    return [
        {"role": "system", "content": instruction},
        *[dict(message) for message in messages],
        {
            "role": "user",
            "content": json.dumps(dict(blueprint), ensure_ascii=False),
        },
    ]
