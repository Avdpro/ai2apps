"""Bounded, transactional orchestration for a Fusion model turn."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict, replace

from .gate import AdaptiveGate, GateEvaluation
from .patching import PatchApplyError, apply_structured_patches, text_sha256
from .protocols import GeneratorBackend, GeneratorTurn, ResolverBackend, ReviewerBackend
from .tooling import validate_tool_calls
from .types import (
    CheckpointAction,
    CheckpointDecision,
    DraftChunk,
    FailurePolicy,
    FusionConfig,
    FusionEvent,
    FusionRequest,
    FusionResult,
    FusionToolCall,
    GateDecision,
    GateSignals,
    ReviewAction,
    ReviewDecision,
    StreamMode,
    StructuredPatch,
    ToolReviewAction,
    ToolReviewDecision,
)
from .control import consume_skip_review


class _ReviewSkippedByUser(Exception):
    pass


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
        if (
            config.gate_policy != "off"
            or config.mid_generation_review_enabled
            or config.thinking_audit_enabled
        ) and reviewer is None:
            raise ValueError("enabled Fusion review requires a reviewer backend")
        if (
            config.mid_generation_review_enabled or config.thinking_audit_enabled
        ) and not callable(getattr(reviewer, "review_checkpoint", None)):
            raise ValueError(
                "Fusion checkpoint review requires checkpoint reviewer support"
            )
        if config.resolver_enabled and resolver is None:
            raise ValueError("resolver_enabled requires a resolver backend")
        self.config = config
        self.generator = generator
        self.reviewer = reviewer
        self.resolver = resolver
        self.validator = validator
        self.gate = AdaptiveGate(config)

    @staticmethod
    async def _await_role(
        backend: object,
        operation: Awaitable,
        timeout_seconds: float,
    ):
        """Use fixed timeout unless the backend tracks streaming progress."""

        if getattr(backend, "manages_inactivity_timeout", False):
            return await operation
        return await asyncio.wait_for(operation, timeout=timeout_seconds)

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
        request = replace(
            request,
            metadata={
                **request.metadata,
                "mid_generation_review_enabled": (
                    self.config.mid_generation_review_enabled
                ),
                "mid_generation_checkpoint_tokens": (
                    self.config.mid_generation_checkpoint_tokens
                ),
                "thinking_audit_enabled": self.config.thinking_audit_enabled,
                "thinking_audit_min_tokens": (self.config.thinking_audit_min_tokens),
                "thinking_audit_max_tokens": (self.config.thinking_audit_max_tokens),
                "reviewer_guidance_mode": self.config.reviewer_guidance_mode,
                "reasoning_handoff_max_tokens": (
                    self.config.reasoning_handoff_max_tokens
                ),
            },
        )
        turn = await self.generator.begin_turn(request)
        committed = False
        draft_parts: list[str] = []
        final_chunk: DraftChunk | None = None
        review: ReviewDecision | None = None
        gate_eval: GateEvaluation | None = None
        path = ""
        stage_metadata: dict[str, object] = {}
        final_tool_calls: tuple[FusionToolCall, ...] = ()
        checkpoint_chunk: DraftChunk | None = None
        checkpoint_decision: CheckpointDecision | None = None
        user_skipped_review = False

        try:
            if request.stream_mode == StreamMode.DRAFT:
                yield FusionEvent("draft_begin", draft_id=draft_id)

            async for chunk in turn.stream_draft():
                if chunk.text:
                    draft_parts.append(chunk.text)
                    if request.stream_mode == StreamMode.DRAFT:
                        yield FusionEvent(
                            "draft",
                            "draft",
                            chunk.text,
                            draft_id=draft_id,
                            metadata={
                                "tokens": chunk.token_count,
                                "thinking_tokens": (
                                    chunk.signals.extra.get("thinking_tokens", 0)
                                    if chunk.signals is not None
                                    else 0
                                ),
                            },
                        )
                    elif request.stream_mode == StreamMode.REASONING:
                        yield FusionEvent(
                            "draft",
                            "reasoning",
                            chunk.text,
                            draft_id=draft_id,
                            metadata={
                                "tokens": chunk.token_count,
                                "thinking_tokens": (
                                    chunk.signals.extra.get("thinking_tokens", 0)
                                    if chunk.signals is not None
                                    else 0
                                ),
                            },
                        )
                if chunk.finished:
                    final_chunk = chunk
                if chunk.checkpoint:
                    checkpoint_chunk = chunk

            if checkpoint_chunk is not None:
                checkpoint_draft = "".join(draft_parts)
                checkpoint_signals = self._final_signals(
                    checkpoint_draft, checkpoint_chunk
                )
                stage_metadata["checkpoint_tokens"] = checkpoint_signals.output_tokens
                checkpoint_reason = checkpoint_chunk.checkpoint_reason or "token_limit"
                stage_metadata["checkpoint_reason"] = checkpoint_reason
                thinking_tokens = checkpoint_signals.extra.get("thinking_tokens")
                if thinking_tokens is not None:
                    stage_metadata["thinking_audit_tokens"] = thinking_tokens
                yield FusionEvent(
                    "checkpoint_review_begin",
                    draft_id=draft_id,
                    metadata={
                        "checkpoint_tokens": checkpoint_signals.output_tokens,
                        "reason": checkpoint_reason,
                        "thinking_tokens": thinking_tokens,
                        "sha256": text_sha256(checkpoint_draft),
                    },
                )
                if consume_skip_review(request.session_id):
                    user_skipped_review = True
                    checkpoint_decision = CheckpointDecision(
                        CheckpointAction.CONTINUE,
                        summary="Review skipped by user",
                    )
                    yield FusionEvent(
                        "review_skipped",
                        draft_id=draft_id,
                        metadata={"stage": "checkpoint", "source": "user"},
                    )
                try:
                    if checkpoint_decision is not None:
                        raise _ReviewSkippedByUser()
                    checkpoint_decision = await self._await_role(
                        self.reviewer,
                        self.reviewer.review_checkpoint(
                            request,
                            checkpoint_draft,
                            text_sha256(checkpoint_draft),
                            checkpoint_signals,
                        ),
                        self.config.mid_generation_reviewer_timeout_seconds,
                    )
                    if (
                        checkpoint_decision.action == CheckpointAction.REASONING_HANDOFF
                        and self.config.reviewer_guidance_mode != "reasoning_handoff"
                    ):
                        raise ValueError(
                            "checkpoint reviewer selected disabled reasoning handoff"
                        )
                except _ReviewSkippedByUser:
                    pass
                except Exception as exc:
                    stage_metadata["checkpoint_review_error"] = type(exc).__name__
                    if request.high_risk:
                        raise FusionExecutionError(
                            "checkpoint_reviewer_failed"
                        ) from exc
                    checkpoint_decision = CheckpointDecision(
                        CheckpointAction.CONTINUE,
                        summary=(
                            "checkpoint reviewer unavailable; fail-open continuation"
                        ),
                    )

                stage_metadata["checkpoint_action"] = checkpoint_decision.action.value
                stage_metadata["checkpoint_confidence"] = checkpoint_decision.confidence
                if checkpoint_decision.action == CheckpointAction.REASONING_HANDOFF:
                    stage_metadata["reasoning_handoff_sha256"] = text_sha256(
                        checkpoint_decision.reasoning_seed
                    )
                    stage_metadata["reasoning_handoff_chars"] = len(
                        checkpoint_decision.reasoning_seed
                    )
                    stage_metadata["reasoning_handoff_constraint_count"] = len(
                        checkpoint_decision.constraints
                    )
                yield FusionEvent(
                    "checkpoint_review_result",
                    draft_id=draft_id,
                    metadata={
                        "action": checkpoint_decision.action.value,
                        "reason": checkpoint_reason,
                        "confidence": checkpoint_decision.confidence,
                        "summary": checkpoint_decision.summary,
                        "guidance": list(checkpoint_decision.guidance),
                    },
                )

                if checkpoint_decision.action == CheckpointAction.ABORT:
                    raise FusionExecutionError("checkpoint_reviewer_aborted")
                if checkpoint_decision.action in {
                    CheckpointAction.REDIRECT,
                    CheckpointAction.REASONING_HANDOFF,
                }:
                    stage_metadata["checkpoint_rejected_sha256"] = text_sha256(
                        checkpoint_draft
                    )
                    draft_parts = []
                    if request.stream_mode == StreamMode.DRAFT:
                        yield FusionEvent(
                            "draft_reset",
                            draft_id=draft_id,
                            metadata={
                                "reason": (
                                    f"checkpoint_{checkpoint_decision.action.value}"
                                )
                            },
                        )

                should_resume = (
                    checkpoint_decision.action
                    in {
                        CheckpointAction.REDIRECT,
                        CheckpointAction.REASONING_HANDOFF,
                    }
                    or not checkpoint_chunk.finished
                )
                if should_resume:
                    async for chunk in turn.resume_from_checkpoint(
                        checkpoint_draft, checkpoint_decision
                    ):
                        if chunk.text:
                            draft_parts.append(chunk.text)
                            if request.stream_mode == StreamMode.DRAFT:
                                yield FusionEvent(
                                    "draft",
                                    "draft",
                                    chunk.text,
                                    draft_id=draft_id,
                                    metadata={"tokens": chunk.token_count},
                                )
                            elif request.stream_mode == StreamMode.REASONING:
                                yield FusionEvent(
                                    "draft",
                                    "reasoning",
                                    chunk.text,
                                    draft_id=draft_id,
                                    metadata={"tokens": chunk.token_count},
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
                    metadata={
                        "sha256": text_sha256(draft),
                        "tokens": signals.output_tokens,
                        "thinking_tokens": signals.extra.get(
                            "thinking_tokens", 0
                        ),
                    },
                )

            gate_eval = self.gate.evaluate(request, signals)
            stage_metadata["gate_score"] = gate_eval.score
            stage_metadata["gate_reasons"] = gate_eval.reasons

            final = draft
            changed_patches: tuple[StructuredPatch, ...] = ()
            changed_ratio = 0.0

            candidate_tool_calls = final_chunk.tool_calls
            tool_errors = validate_tool_calls(
                candidate_tool_calls,
                request.tools,
                request.tool_choice,
                max_calls=self.config.max_tool_calls,
            )
            tool_review_required = bool(candidate_tool_calls or tool_errors)

            if tool_review_required:
                yield FusionEvent(
                    "tool_review_begin",
                    draft_id=draft_id,
                    metadata={
                        "call_count": len(candidate_tool_calls),
                        "validation_error_count": len(tool_errors),
                    },
                )
                (
                    final,
                    draft,
                    signals,
                    final_tool_calls,
                    path,
                ) = await self._review_tool_candidate(
                    request,
                    turn,
                    draft,
                    signals,
                    candidate_tool_calls,
                    tool_errors,
                    stage_metadata,
                )
                yield FusionEvent(
                    "tool_review_result",
                    draft_id=draft_id,
                    metadata={
                        "path": path,
                        "action": stage_metadata.get("tool_review_action"),
                        "final_action": stage_metadata.get("tool_final_review_action"),
                        "committed_call_count": len(final_tool_calls),
                    },
                )

            elif (
                user_skipped_review
                or consume_skip_review(request.session_id)
                or gate_eval.decision == GateDecision.SKIP
                or self.reviewer is None
            ):
                path = "skip_user" if user_skipped_review else "skip"
                if path == "skip" and gate_eval.decision != GateDecision.SKIP:
                    path = "skip_user"
                if path == "skip_user":
                    yield FusionEvent(
                        "review_skipped",
                        draft_id=draft_id,
                        metadata={"stage": "final", "source": "user"},
                    )
            else:
                yield FusionEvent(
                    "review_begin",
                    draft_id=draft_id,
                    metadata={"gate": gate_eval.decision.value},
                )
                review = None
                review_source = "local"
                review_skipped = False
                try:
                    stream_review = getattr(self.reviewer, "review_with_progress", None)
                    if callable(stream_review):
                        progress_queue: asyncio.Queue[dict] = asyncio.Queue()
                        review_task = asyncio.create_task(
                            self._await_role(
                                self.reviewer,
                                stream_review(
                                    request,
                                    draft,
                                    text_sha256(draft),
                                    signals,
                                    progress_queue.put_nowait,
                                ),
                                self.config.reviewer_timeout_seconds,
                            )
                        )
                        try:
                            while not review_task.done():
                                if consume_skip_review(request.session_id):
                                    review_skipped = True
                                    review_task.cancel()
                                    await asyncio.gather(
                                        review_task, return_exceptions=True
                                    )
                                    break
                                try:
                                    progress = await asyncio.wait_for(
                                        progress_queue.get(), timeout=0.1
                                    )
                                except TimeoutError:
                                    continue
                                yield FusionEvent(
                                    "review_progress",
                                    draft_id=draft_id,
                                    metadata=progress,
                                )
                            while not progress_queue.empty():
                                yield FusionEvent(
                                    "review_progress",
                                    draft_id=draft_id,
                                    metadata=progress_queue.get_nowait(),
                                )
                            if not review_skipped:
                                review = await review_task
                        finally:
                            if not review_task.done():
                                review_task.cancel()
                                await asyncio.gather(
                                    review_task, return_exceptions=True
                                )
                    else:
                        review = await self._await_role_or_skip(
                            self.reviewer,
                            self.reviewer.review(
                                request, draft, text_sha256(draft), signals
                            ),
                            self.config.reviewer_timeout_seconds,
                            request.session_id,
                        )
                except _ReviewSkippedByUser:
                    review_skipped = True
                except Exception as exc:
                    error_type = str(getattr(exc, "error_type", type(exc).__name__))
                    transcript = getattr(exc, "transcript", {})
                    stage_metadata["review_error"] = error_type
                    yield FusionEvent(
                        "review_error",
                        draft_id=draft_id,
                        metadata={
                            "error": error_type,
                            "message": str(exc),
                            "output": transcript.get("output", ""),
                            "tokens": transcript.get("tokens", 0),
                            "duration_seconds": transcript.get("duration_seconds", 0),
                        },
                    )
                    external_review = getattr(self.resolver, "review", None)
                    if self._resolver_handles("reviewer_failed") and callable(
                        external_review
                    ):
                        yield FusionEvent(
                            "review_fallback_begin",
                            draft_id=draft_id,
                            metadata={"source": "external"},
                        )
                        try:
                            review = await self._await_role_or_skip(
                                self.resolver,
                                external_review(
                                    request,
                                    draft,
                                    text_sha256(draft),
                                    signals,
                                ),
                                self.config.resolver_timeout_seconds,
                                request.session_id,
                            )
                        except _ReviewSkippedByUser:
                            review_skipped = True
                        except Exception as resolver_exc:
                            stage_metadata["resolver_review_error"] = type(
                                resolver_exc
                            ).__name__
                            yield FusionEvent(
                                "review_fallback_error",
                                draft_id=draft_id,
                                metadata={
                                    "source": "external",
                                    "error": type(resolver_exc).__name__,
                                    "message": str(resolver_exc),
                                },
                            )
                            final, path = await self._apply_failure_policy(
                                request,
                                turn,
                                draft,
                                None,
                                self.config.resolver_unavailable_policy,
                                "resolver_review_failed",
                            )
                        else:
                            review_source = "external"
                            stage_metadata["review_fallback"] = "external"
                    else:
                        final, path = await self._apply_failure_policy(
                            request,
                            turn,
                            draft,
                            None,
                            self.config.reviewer_failure_policy,
                            "reviewer_failed",
                        )

                if review_skipped:
                    final = draft
                    path = "skip_user"
                    yield FusionEvent(
                        "review_skipped",
                        draft_id=draft_id,
                        metadata={"stage": "final", "source": "user"},
                    )
                elif review is not None:
                    transcript = review.metadata.get("reviewer_transcript", {})
                    yield FusionEvent(
                        "review_result",
                        draft_id=draft_id,
                        metadata={
                            "source": review_source,
                            "action": review.action.value,
                            "risk": review.risk,
                            "confidence": review.confidence,
                            "summary": review.summary,
                            "output": transcript.get("output", ""),
                            "tokens": transcript.get("tokens", 0),
                            "duration_seconds": transcript.get("duration_seconds", 0),
                        },
                    )
                    (
                        final,
                        path,
                        changed_patches,
                        changed_ratio,
                    ) = await self._apply_review_decision(
                        request,
                        turn,
                        draft,
                        review,
                        stage_metadata,
                        source=review_source,
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
                tool_calls=final_tool_calls,
            )
            yield FusionEvent(
                "done",
                draft_id=draft_id,
                metadata={"result": result, "path": path},
            )
        finally:
            # A click racing with the final commit must never skip the next
            # turn that happens to reuse the same chat/session id.
            consume_skip_review(request.session_id)
            if not committed:
                await asyncio.shield(turn.abort())

    async def _review_tool_candidate(
        self,
        request: FusionRequest,
        turn: GeneratorTurn,
        draft: str,
        signals: GateSignals,
        calls: tuple[FusionToolCall, ...],
        errors: tuple[str, ...],
        stage_metadata: dict[str, object],
    ) -> tuple[str, str, GateSignals, tuple[FusionToolCall, ...], str]:
        """Audit a candidate and allow at most one full regeneration."""

        reviewer_method = getattr(self.reviewer, "review_tool_calls", None)
        replan_method = getattr(turn, "replan_tool_calls", None)
        yield_metadata = {
            "call_count": len(calls),
            "validation_errors": list(errors),
        }
        # Tool calls fail closed. Event metadata is collected on the final
        # result; provisional calls themselves are never exposed here.
        stage_metadata["tool_candidate"] = yield_metadata
        if not callable(reviewer_method):
            stage_metadata["tool_review_error"] = "reviewer_unavailable"
            return (
                self.config.tool_denial_message,
                draft,
                signals,
                (),
                "tool_denied",
            )
        try:
            decision = await self._await_role(
                self.reviewer,
                reviewer_method(request, draft, calls, errors, final=False),
                self.config.reviewer_timeout_seconds,
            )
        except Exception as exc:
            stage_metadata["tool_review_error"] = type(exc).__name__
            return (
                self.config.tool_denial_message,
                draft,
                signals,
                (),
                "tool_denied",
            )
        stage_metadata["tool_review_action"] = decision.action.value
        stage_metadata["tool_review_summary"] = decision.summary

        if decision.action == ToolReviewAction.PASS:
            if errors:
                stage_metadata["tool_review_error"] = "invalid_pass"
                return (
                    decision.user_message or self.config.tool_denial_message,
                    draft,
                    signals,
                    (),
                    "tool_denied",
                )
            return draft, draft, signals, calls, "tool_pass"
        if decision.action == ToolReviewAction.DENY:
            return (
                decision.user_message or self.config.tool_denial_message,
                draft,
                signals,
                (),
                "tool_denied",
            )
        if not callable(replan_method):
            stage_metadata["tool_review_error"] = "replan_unavailable"
            return (
                decision.user_message or self.config.tool_denial_message,
                draft,
                signals,
                (),
                "tool_denied",
            )

        replanned_parts: list[str] = []
        replanned_chunk: DraftChunk | None = None
        try:
            async for chunk in replan_method(draft, decision):
                if chunk.text:
                    replanned_parts.append(chunk.text)
                if chunk.finished:
                    replanned_chunk = chunk
        except Exception as exc:
            stage_metadata["tool_replan_error"] = type(exc).__name__
            return self.config.tool_denial_message, draft, signals, (), "tool_denied"
        replanned = "".join(replanned_parts)
        if replanned_chunk is None:
            replanned_chunk = DraftChunk(finished=True)
        replanned_signals = self._final_signals(replanned, replanned_chunk)
        replanned_calls = replanned_chunk.tool_calls
        replanned_errors = validate_tool_calls(
            replanned_calls,
            request.tools,
            request.tool_choice,
            max_calls=self.config.max_tool_calls,
        )
        stage_metadata["tool_replan_call_count"] = len(replanned_calls)
        stage_metadata["tool_replan_validation_errors"] = list(replanned_errors)
        try:
            final_decision: ToolReviewDecision = await self._await_role(
                self.reviewer,
                reviewer_method(
                    request,
                    replanned,
                    replanned_calls,
                    replanned_errors,
                    final=True,
                ),
                self.config.reviewer_timeout_seconds,
            )
        except Exception as exc:
            stage_metadata["tool_final_review_error"] = type(exc).__name__
            return (
                self.config.tool_denial_message,
                replanned,
                replanned_signals,
                (),
                "tool_denied",
            )
        stage_metadata["tool_final_review_action"] = final_decision.action.value
        if final_decision.action == ToolReviewAction.PASS and not replanned_errors:
            return (
                replanned,
                replanned,
                replanned_signals,
                replanned_calls,
                "tool_replan_pass",
            )
        return (
            final_decision.user_message or self.config.tool_denial_message,
            replanned,
            replanned_signals,
            (),
            "tool_denied",
        )

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

    async def _apply_review_decision(
        self,
        request: FusionRequest,
        turn: GeneratorTurn,
        draft: str,
        review: ReviewDecision,
        stage_metadata: dict,
        *,
        source: str,
    ) -> tuple[str, str, tuple[StructuredPatch, ...], float]:
        """Apply one completed local or external review exactly once."""

        external = source == "external"
        prefix = "resolver_review_" if external else ""
        is_uncertain = (
            review.confidence is not None
            and review.confidence < self.config.reviewer_escalate_below
        )
        if (
            is_uncertain
            and not external
            and self._resolver_handles("reviewer_uncertain")
        ):
            final, path = await self._resolve_or_fallback(
                request, turn, draft, review, "reviewer_uncertain"
            )
            return final, path, (), 0.0
        if review.action == ReviewAction.PASS:
            return draft, f"{prefix}pass", (), 0.0
        if review.action == ReviewAction.PATCH:
            try:
                applied = apply_structured_patches(
                    draft,
                    review.patches,
                    max_changed_ratio=self.config.max_changed_ratio,
                )
            except PatchApplyError as exc:
                stage_metadata["patch_error"] = str(exc)
                if external:
                    final, path = await self._apply_failure_policy(
                        request,
                        turn,
                        draft,
                        review,
                        self.config.resolver_unavailable_policy,
                        "resolver_review_patch_failed",
                    )
                else:
                    final, path = await self._resolve_or_fallback(
                        request, turn, draft, review, "patch_failed"
                    )
                return final, path, (), 0.0
            return (
                applied.text,
                f"{prefix}patch",
                review.patches,
                applied.changed_ratio,
            )
        if review.action == ReviewAction.REVISE:
            try:
                revision = await turn.revise(draft, review)
                final, patches, ratio = self._apply_revision(draft, revision)
            except Exception as exc:
                stage_metadata["revision_error"] = type(exc).__name__
                if external:
                    final, path = await self._apply_failure_policy(
                        request,
                        turn,
                        draft,
                        review,
                        self.config.resolver_unavailable_policy,
                        "resolver_review_revision_failed",
                    )
                else:
                    final, path = await self._resolve_or_fallback(
                        request, turn, draft, review, "patch_failed"
                    )
                return final, path, (), 0.0
            return final, f"{prefix}revise", patches, ratio
        if external:
            final, path = await self._apply_failure_policy(
                request,
                turn,
                draft,
                review,
                self.config.resolver_unavailable_policy,
                "resolver_review_escalate",
            )
            return final, path, (), 0.0
        final, path = await self._resolve_or_fallback(
            request, turn, draft, review, "reviewer_escalate"
        )
        return final, path, (), 0.0

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
                resolution = await self._await_role(
                    self.resolver,
                    self.resolver.resolve(request, draft, review),
                    self.config.resolver_timeout_seconds,
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

    async def _await_role_or_skip(
        self,
        backend: object,
        awaitable,
        timeout_seconds: float,
        session_id: str,
    ):
        task = asyncio.create_task(
            self._await_role(backend, awaitable, timeout_seconds)
        )
        try:
            while not task.done():
                if consume_skip_review(session_id):
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    raise _ReviewSkippedByUser()
                await asyncio.sleep(0.1)
            return await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

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
