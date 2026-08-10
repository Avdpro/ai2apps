"""Adapters for existing oMLX engines and OpenAI-compatible reviewers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, AsyncIterator

from .prompts import (
    REVIEW_SYSTEM_PROMPT,
    build_realization_messages,
    build_review_messages,
    build_revision_messages,
)
from .serde import review_decision_from_json, review_decision_from_mapping
from .types import (
    DraftChunk,
    FusionRequest,
    GateSignals,
    ReviewAction,
    ReviewDecision,
    StructuredPatch,
)


class OMLXGeneratorTurn:
    """One provisional turn backed by an existing oMLX BaseEngine."""

    def __init__(self, engine: Any, request: FusionRequest):
        self.engine = engine
        self.request = request
        self._finished = False

    def _kwargs(self) -> dict[str, Any]:
        values = dict(self.request.sampling)
        values.setdefault("max_tokens", self.request.max_tokens)
        values.setdefault("flesh_session_id", self.request.session_id)
        # A provisional answer is not canonical until Fusion commits it. The
        # current BaseEngine cache API cannot promote a completed request, so
        # v1 avoids polluting the shared prefix store. The next canonical turn
        # safely rebuilds from the client-provided conversation history.
        values.setdefault("skip_cache_store", True)
        return values

    async def stream_draft(self) -> AsyncIterator[DraftChunk]:
        last = None
        async for output in self.engine.stream_chat(
            messages=[dict(message) for message in self.request.messages],
            **self._kwargs(),
        ):
            last = output
            if output.new_text:
                yield DraftChunk(text=output.new_text)
        self._finished = True
        completion_tokens = int(getattr(last, "completion_tokens", 0) or 0)
        finish_reason = str(getattr(last, "finish_reason", "stop") or "stop")
        yield DraftChunk(
            finished=True,
            finish_reason=finish_reason,
            token_count=completion_tokens,
            signals=GateSignals(
                output_tokens=completion_tokens,
                finish_reason=finish_reason,
            ),
        )

    async def revise(
        self, draft: str, decision: ReviewDecision
    ) -> tuple[StructuredPatch, ...]:
        output = await self.engine.chat(
            messages=build_revision_messages(
                self.request.messages, draft, _sha256(draft), decision
            ),
            max_tokens=min(self.request.max_tokens, 512),
            temperature=0.0,
            top_p=1.0,
            flesh_session_id=self.request.session_id,
        )
        text = str(getattr(output, "text", ""))
        try:
            payload = json.loads(_strip_json_fence(text))
        except json.JSONDecodeError as exc:
            raise ValueError("generator revision is not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("generator revision must be a JSON object")
        value = dict(payload)
        value.setdefault("action", "patch")
        parsed = review_decision_from_mapping(value)
        if parsed.action != ReviewAction.PATCH:
            raise ValueError("generator revision must contain PATCH operations")
        return parsed.patches

    async def realize(self, draft: str, blueprint: Mapping[str, object]) -> str:
        sampling = dict(self.request.sampling)
        sampling.pop("max_tokens", None)
        sampling.setdefault("flesh_session_id", self.request.session_id)
        sampling.setdefault("skip_cache_store", True)
        output = await self.engine.chat(
            messages=build_realization_messages(self.request.messages, blueprint),
            max_tokens=self.request.max_tokens,
            **sampling,
        )
        return str(getattr(output, "text", ""))

    async def commit_draft(self) -> None:
        return None

    async def commit_final(self, text: str) -> None:
        return None

    async def abort(self) -> None:
        return None


class OMLXGeneratorBackend:
    def __init__(self, engine: Any):
        self.engine = engine

    async def begin_turn(self, request: FusionRequest) -> OMLXGeneratorTurn:
        return OMLXGeneratorTurn(self.engine, request)


class OMLXReviewerBackend:
    """Use a loaded local oMLX engine as a constrained reviewer."""

    def __init__(self, engine: Any, *, max_tokens: int = 384):
        self.engine = engine
        self.max_tokens = max_tokens

    async def review(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> ReviewDecision:
        output = await self.engine.chat(
            messages=build_review_messages(
                request.messages, draft, draft_sha256
            ),
            max_tokens=self.max_tokens,
            temperature=0.0,
            top_p=1.0,
            flesh_session_id=f"fusion-review:{request.session_id}",
        )
        return review_decision_from_json(str(getattr(output, "text", "")))

    async def resolve(
        self,
        request: FusionRequest,
        draft: str,
        review: ReviewDecision,
    ) -> ReviewDecision:
        messages = build_review_messages(request.messages, draft, _sha256(draft))
        messages[0]["content"] += (
            "\nYou are the final resolver. Prefer PATCH; otherwise return "
            "ESCALATE with a short authoritative blueprint."
        )
        messages[1]["content"] += "\nLocal review:\n" + json.dumps(
            {
                "summary": review.summary,
                "risk": review.risk,
                "confidence": review.confidence,
                "blueprint": dict(review.blueprint),
            },
            ensure_ascii=False,
        )
        output = await self.engine.chat(
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=0.0,
            top_p=1.0,
            flesh_session_id=f"fusion-resolve:{request.session_id}",
        )
        return review_decision_from_json(str(getattr(output, "text", "")))


class OpenAICompatibleReviewBackend:
    """Remote reviewer/resolver adapter with no persistent credential storage."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        max_tokens: int = 384,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
    ):
        if not base_url or not model or not api_key:
            raise ValueError(
                "remote Fusion backend requires base_url, model, and api_key"
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._owns_client = client is None

    async def _complete(self, messages: list[dict[str, Any]]) -> ReviewDecision:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0,
                "max_tokens": self.max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("remote Fusion response has no assistant content") from exc
        return review_decision_from_json(str(content))

    async def review(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> ReviewDecision:
        return await self._complete(
            build_review_messages(request.messages, draft, draft_sha256)
        )

    async def resolve(
        self,
        request: FusionRequest,
        draft: str,
        review: ReviewDecision,
    ) -> ReviewDecision:
        payload = {
            "conversation": list(request.messages),
            "draft_sha256": _sha256(draft),
            "draft": draft,
            "local_review": {
                "summary": review.summary,
                "risk": review.risk,
                "confidence": review.confidence,
                "blueprint": dict(review.blueprint),
            },
        }
        system = (
            REVIEW_SYSTEM_PROMPT
            + "\nYou are the final resolver. Prefer a minimal PATCH. If the core "
            "solution must change, return ESCALATE with an authoritative short "
            "blueprint."
        )
        return await self._complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]
        )

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        first_newline = stripped.find("\n")
        if first_newline >= 0:
            return stripped[first_newline + 1 : -3].strip()
    return stripped


def _sha256(text: str) -> str:
    from .patching import text_sha256

    return text_sha256(text)
