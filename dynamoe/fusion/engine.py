"""Bounded, transactional orchestration for a Fusion model turn."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from dataclasses import asdict, replace
from typing import AsyncIterator, Awaitable, Callable, Mapping

from .gate import AdaptiveGate, GateEvaluation
from .patching import PatchApplyError, apply_structured_patches, text_sha256
from .protocols import GeneratorBackend, GeneratorTurn, ResolverBackend, ReviewerBackend
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


class FusionExecutionError(RuntimeError):
    pass


Validator = Callable[[str], bool | Awaitable[bool]]


class FusionOrchestrator:
    """Compose role backends while preserving a single canonical turn."""

    def __init__(
        self,
        config: FusionConfig,
        generator: GeneratorBackend,
        reviewer: ReviewerBackend | None = None,
        resolver: ResolverBackend | None = None,
        validator: Validator | None = None,
    ):
        if config.gate_policy != "off" and reviewer is None:
            raise ValueError("enabled Fusion review requires a reviewer backend")
        if config.resolver_enabled and resolver is None:
            raise ValueError("resolver_enabled requires a resolver backend")
        self.config = config
        self.generator = generator
        self.reviewer = reviewer
        self.resolver = resolver
        self.validator = validator
        self.gate = AdaptiveGate(config)

    async def generate(self, request: FusionRequest) -> FusionResult:
        """Run a turn and return only its canonical result."""

        final_request = replace(request, stream_mode=StreamMode.FINAL)
        final_text: list[str] = []
        result: FusionResult | None = None
        async for event in self.stream(final_request):
            if event.channel == "content":
                final_text.append(event.text)
            if event.phase == "done":
                value = event.metadata.get("result")
                if isinstance(value, FusionResult):
                    result = value
        if result is None:
            raise FusionExecutionError("Fusion turn completed without a result")
        if "".join(final_text) != result.text:
            raise FusionExecutionError("canonical stream and Fusion result diverged")
        return result

    async def stream(self, request: FusionRequest) -> AsyncIterator[FusionEvent]:
        """Stream provisional and canonical phases for one bounded turn."""

        draft_id = f"draft_{uuid.uuid4().hex}"
        turn = await self.generator.begin_turn(request)
        committed = False
        draft_parts: list[str] = []
        final_chunk: DraftChunk | None = None
        review: ReviewDecision | None = None
        gate_eval: GateEvaluation | None = None
        path = ""
        stage_metadata: dict[str, object] = {}

        try:
            if request.stream_mode == StreamMode.DRAFT:
                yield FusionEvent("draft_begin", draft_id=draft_id)

            async for chunk in turn.stream_draft():
                if chunk.text:
                    draft_parts.append(chunk.text)
                    if request.stream_mode == StreamMode.DRAFT:
                        yield FusionEvent(
                            "draft", "draft", chunk.text, draft_id=draft_id
                        )
                    elif request.stream_mode == StreamMode.REASONING:
                        yield FusionEvent(
                            "draft", "reasoning", chunk.text, draft_id=draft_id
                        )
                if chunk.finished:
                    final_chunk = chunk

            draft = "".join(draft_parts)
            if final_chunk is None:
                final_chunk = DraftChunk(
                    finished=True,
                    token_count=0,
                    signals=GateSignals(output_chars=len(draft)),
                )
            signals = self._final_signals(draft, final_chunk)

            if request.stream_mode == StreamMode.DRAFT:
                yield FusionEvent(
                    "draft_end",
                    draft_id=draft_id,
                    metadata={"sha256": text_sha256(draft)},
                )

            gate_eval = self.gate.evaluate(request, signals)
            stage_metadata["gate_score"] = gate_eval.score
            stage_metadata["gate_reasons"] = gate_eval.reasons

            final = draft
            changed_patches: tuple[StructuredPatch, ...] = ()
            changed_ratio = 0.0

            if gate_eval.decision == GateDecision.SKIP or self.reviewer is None:
                path = "skip"
            else:
                yield FusionEvent(
                    "review_begin",
                    draft_id=draft_id,
                    metadata={"gate": gate_eval.decision.value},
                )
                try:
                    review = await asyncio.wait_for(
                        self.reviewer.review(
                            request, draft, text_sha256(draft), signals
                        ),
                        timeout=self.config.reviewer_timeout_seconds,
                    )
                except Exception as exc:
                    stage_metadata["review_error"] = type(exc).__name__
                    final, path = await self._apply_failure_policy(
                        request,
                        turn,
                        draft,
                        None,
                        self.config.reviewer_failure_policy,
                        "reviewer_failed",
                    )
                else:
                    yield FusionEvent(
                        "review_result",
                        draft_id=draft_id,
                        metadata={
                            "action": review.action.value,
                            "risk": review.risk,
                            "confidence": review.confidence,
                            "summary": review.summary,
                        },
                    )
                    is_uncertain = (
                        review.confidence is not None
                        and review.confidence
                        < self.config.reviewer_escalate_below
                    )
                    if is_uncertain and self._resolver_handles(
                        "reviewer_uncertain"
                    ):
                        final, path = await self._resolve_or_fallback(
                            request,
                            turn,
                            draft,
                            review,
                            "reviewer_uncertain",
                        )
                    elif review.action == ReviewAction.PASS:
                        path = "pass"
                    elif review.action == ReviewAction.PATCH:
                        try:
                            applied = apply_structured_patches(
                                draft,
                                review.patches,
                                max_changed_ratio=self.config.max_changed_ratio,
                            )
                        except PatchApplyError as exc:
                            stage_metadata["patch_error"] = str(exc)
                            final, path = await self._resolve_or_fallback(
                                request, turn, draft, review, "patch_failed"
                            )
                        else:
                            final = applied.text
                            changed_patches = review.patches
                            changed_ratio = applied.changed_ratio
                            path = "patch"
                    elif review.action == ReviewAction.REVISE:
                        try:
                            revision = await turn.revise(draft, review)
                            (
                                final,
                                changed_patches,
                                changed_ratio,
                            ) = self._apply_revision(draft, revision)
                        except Exception as exc:
                            stage_metadata["revision_error"] = type(exc).__name__
                            final, path = await self._resolve_or_fallback(
                                request,
                                turn,
                                draft,
                                review,
                                "patch_failed",
                            )
                        else:
                            path = "revise"
                    else:
                        final, path = await self._resolve_or_fallback(
                            request,
                            turn,
                            draft,
                            review,
                            "reviewer_escalate",
                        )

            if not await self._validate(final):
                raise FusionExecutionError("canonical answer failed validation")

            if final == draft:
                await turn.commit_draft()
            else:
                await turn.commit_final(final)
            committed = True

            if request.stream_mode == StreamMode.DRAFT:
                if final == draft:
                    yield FusionEvent(
                        "draft_commit",
                        draft_id=draft_id,
                        metadata={"path": path},
                    )
                elif changed_patches and path in {"patch", "revise"}:
                    yield FusionEvent(
                        "patch",
                        draft_id=draft_id,
                        metadata={
                            "patches": [asdict(patch) for patch in changed_patches],
                            "changed_ratio": changed_ratio,
                            "canonical_sha256": text_sha256(final),
                        },
                    )
                    yield FusionEvent(
                        "draft_commit",
                        draft_id=draft_id,
                        metadata={"path": path, "patched": True},
                    )
                else:
                    yield FusionEvent(
                        "draft_supersede", draft_id=draft_id, metadata={"path": path}
                    )
                    async for event in self._canonical_events(final, draft_id):
                        yield event
            else:
                async for event in self._canonical_events(final, draft_id):
                    yield event

            result = FusionResult(
                text=final,
                draft=draft,
                draft_id=draft_id,
                gate_decision=gate_eval.decision,
                review_action=review.action if review else None,
                path=path,
                signals=signals,
                metadata=stage_metadata,
            )
            yield FusionEvent(
                "done",
                draft_id=draft_id,
                metadata={"result": result, "path": path},
            )
        finally:
            if not committed:
                await asyncio.shield(turn.abort())

    @staticmethod
    def _final_signals(draft: str, chunk: DraftChunk) -> GateSignals:
        signals = chunk.signals or GateSignals()
        token_count = signals.output_tokens or chunk.token_count
        finish_reason = chunk.finish_reason or signals.finish_reason
        return replace(
            signals,
            output_tokens=token_count,
            output_chars=signals.output_chars or len(draft),
            finish_reason=finish_reason,
        )

    def _apply_revision(
        self, draft: str, revision: tuple[StructuredPatch, ...]
    ) -> tuple[str, tuple[StructuredPatch, ...], float]:
        applied = apply_structured_patches(
            draft, revision, max_changed_ratio=self.config.max_changed_ratio
        )
        return applied.text, revision, applied.changed_ratio

    async def _resolve_or_fallback(
        self,
        request: FusionRequest,
        turn: GeneratorTurn,
        draft: str,
        review: ReviewDecision,
        reason: str,
    ) -> tuple[str, str]:
        if self._resolver_handles(reason):
            try:
                resolution = await asyncio.wait_for(
                    self.resolver.resolve(request, draft, review),
                    timeout=self.config.resolver_timeout_seconds,
                )
            except Exception:
                return await self._apply_failure_policy(
                    request,
                    turn,
                    draft,
                    review,
                    self.config.resolver_unavailable_policy,
                    "resolver_failed",
                )
            if resolution.action == ReviewAction.PATCH:
                try:
                    applied = apply_structured_patches(
                        draft,
                        resolution.patches,
                        max_changed_ratio=self.config.max_changed_ratio,
                    )
                except PatchApplyError:
                    return await self._apply_failure_policy(
                        request,
                        turn,
                        draft,
                        review,
                        self.config.resolver_unavailable_policy,
                        "resolver_patch_failed",
                    )
                else:
                    return applied.text, "resolved_patch"
            if resolution.blueprint:
                return await turn.realize(draft, resolution.blueprint), "resolved"
            if resolution.action == ReviewAction.PASS:
                return draft, "resolver_pass"
            raise FusionExecutionError("resolver returned no applicable resolution")

        return await self._apply_failure_policy(
            request,
            turn,
            draft,
            review,
            self.config.resolver_unavailable_policy,
            reason,
        )

    def _resolver_handles(self, reason: str) -> bool:
        return (
            self.config.resolver_enabled
            and self.resolver is not None
            and reason in self.config.resolver_triggers
        )

    async def _apply_failure_policy(
        self,
        request: FusionRequest,
        turn: GeneratorTurn,
        draft: str,
        review: ReviewDecision | None,
        policy: FailurePolicy,
        reason: str,
    ) -> tuple[str, str]:
        if request.high_risk:
            policy = self.config.high_risk_failure_policy
        if policy == FailurePolicy.RETURN_DRAFT:
            return draft, f"{reason}_draft"
        if policy == FailurePolicy.LOCAL_REBUILD:
            if review is not None and review.blueprint:
                return await turn.realize(draft, review.blueprint), "local_rebuild"
            if request.high_risk:
                raise FusionExecutionError(
                    f"{reason}: no local fallback blueprint for high-risk request"
                )
            return draft, f"{reason}_draft"
        raise FusionExecutionError(reason)

    async def _validate(self, text: str) -> bool:
        if self.validator is None:
            return True
        result = self.validator(text)
        if inspect.isawaitable(result):
            result = await result
        return bool(result)

    async def _canonical_events(
        self, text: str, draft_id: str
    ) -> AsyncIterator[FusionEvent]:
        yield FusionEvent("final_begin", draft_id=draft_id)
        size = self.config.replay_chunk_chars
        for start in range(0, len(text), size):
            yield FusionEvent(
                "final", "content", text[start : start + size], draft_id=draft_id
            )
        yield FusionEvent("final_end", draft_id=draft_id)
