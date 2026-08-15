from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from ai2apps.fusion import (
    AdaptiveGate,
    CheckpointAction,
    CheckpointDecision,
    DraftChunk,
    FusionConfig,
    FusionRequest,
    FusionToolCall,
    GateDecision,
    GateSignals,
    PatchApplyError,
    ReviewAction,
    ReviewDecision,
    StreamMode,
    StructuredPatch,
    ToolReviewAction,
    ToolReviewDecision,
    apply_structured_patches,
    text_sha256,
)
from ai2apps.fusion.engine import FusionExecutionError, FusionOrchestrator
from ai2apps.fusion.control import (
    begin_fusion_session,
    consume_skip_review,
    end_fusion_session,
    request_active_skip_review,
    request_skip_review,
)
from ai2apps.fusion.types import PatchOperation


@dataclass
class FakeTurn:
    draft: str
    signals: GateSignals | None = None
    revision: tuple[StructuredPatch, ...] = ()
    revision_error: Exception | None = None
    realization: str = ""
    chunk_size: int = 4
    committed_draft: bool = False
    committed_final: str | None = None
    aborted: bool = False
    checkpoint: bool = False
    checkpoint_reason: str = "token_limit"
    checkpoint_finished: bool = False
    resumed: str = ""
    resume_decisions: list[CheckpointDecision] | None = None
    tool_calls: tuple[FusionToolCall, ...] = ()
    replanned: str = ""
    replanned_tool_calls: tuple[FusionToolCall, ...] = ()
    tool_replan_decisions: list[ToolReviewDecision] | None = None

    async def stream_draft(self):
        for start in range(0, len(self.draft), self.chunk_size):
            yield DraftChunk(text=self.draft[start : start + self.chunk_size])
        if self.checkpoint:
            yield DraftChunk(
                finished=self.checkpoint_finished,
                token_count=max(1, len(self.draft.split())),
                finish_reason=("stop" if self.checkpoint_finished else "length"),
                signals=self.signals,
                checkpoint=True,
                checkpoint_reason=self.checkpoint_reason,
            )
        else:
            yield DraftChunk(
                finished=True,
                token_count=max(1, len(self.draft.split())),
                signals=self.signals,
                tool_calls=self.tool_calls,
            )

    async def resume_from_checkpoint(self, draft, decision):
        if self.resume_decisions is None:
            self.resume_decisions = []
        self.resume_decisions.append(decision)
        for start in range(0, len(self.resumed), self.chunk_size):
            yield DraftChunk(text=self.resumed[start : start + self.chunk_size])
        yield DraftChunk(
            finished=True,
            token_count=max(1, len((draft + self.resumed).split())),
        )

    async def revise(self, draft, decision):
        if self.revision_error is not None:
            raise self.revision_error
        return self.revision

    async def replan_tool_calls(self, draft, decision):
        if self.tool_replan_decisions is None:
            self.tool_replan_decisions = []
        self.tool_replan_decisions.append(decision)
        if self.replanned:
            yield DraftChunk(text=self.replanned)
        yield DraftChunk(
            finished=True,
            token_count=max(1, len(self.replanned.split())),
            tool_calls=self.replanned_tool_calls,
        )

    async def realize(self, draft, blueprint):
        return self.realization or str(blueprint.get("conclusion", draft))

    async def commit_draft(self):
        self.committed_draft = True

    async def commit_final(self, text):
        self.committed_final = text

    async def abort(self):
        self.aborted = True


class FakeGenerator:
    def __init__(self, turn):
        self.turn = turn
        self.requests = []

    async def begin_turn(self, request):
        self.requests.append(request)
        return self.turn


class FakeReviewer:
    def __init__(
        self,
        decision=None,
        error=None,
        checkpoint_decision=None,
        checkpoint_error=None,
        tool_decisions=None,
        tool_error=None,
    ):
        self.decision = decision
        self.error = error
        self.calls = []
        self.checkpoint_decision = checkpoint_decision
        self.checkpoint_error = checkpoint_error
        self.checkpoint_calls = []
        self.tool_decisions = list(tool_decisions or [])
        self.tool_error = tool_error
        self.tool_calls = []

    async def review_tool_calls(
        self, request, draft, tool_calls, validation_errors, *, final=False
    ):
        self.tool_calls.append((request, draft, tool_calls, validation_errors, final))
        if self.tool_error:
            raise self.tool_error
        return self.tool_decisions.pop(0)

    async def review_checkpoint(self, request, draft, draft_sha256, signals):
        self.checkpoint_calls.append((request, draft, draft_sha256, signals))
        if self.checkpoint_error:
            raise self.checkpoint_error
        return self.checkpoint_decision

    async def review(self, request, draft, draft_sha256, signals):
        self.calls.append((request, draft, draft_sha256, signals))
        if self.error:
            raise self.error
        return self.decision


class FakeResolver:
    def __init__(
        self,
        decision=None,
        error=None,
        *,
        review_decision=None,
        review_error=None,
    ):
        self.decision = decision
        self.error = error
        self.calls = []
        self.review_decision = review_decision
        self.review_error = review_error
        self.review_calls = []

    async def review(self, request, draft, draft_sha256, signals):
        self.review_calls.append((request, draft, draft_sha256, signals))
        if self.review_error:
            raise self.review_error
        return self.review_decision

    async def resolve(self, request, draft, review):
        self.calls.append((request, draft, review))
        if self.error:
            raise self.error
        return self.decision


def request(*, mode=StreamMode.FINAL, high_risk=False, max_tokens=256):
    return FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="session-1",
        stream_mode=mode,
        high_risk=high_risk,
        max_tokens=max_tokens,
    )


def tool_request(*, tool_choice="auto"):
    return FusionRequest(
        messages=[{"role": "user", "content": "weather in Shanghai"}],
        session_id="session-tools",
        stream_mode=StreamMode.FINAL,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        tool_choice=tool_choice,
    )


def config(**kwargs):
    return FusionConfig(model_id="fusion-test", **kwargs)


async def events(orchestrator, req):
    return [event async for event in orchestrator.stream(req)]


def result_from(events_):
    done = next(event for event in events_ if event.phase == "done")
    return done.metadata["result"]


def test_patch_replace_is_hash_and_anchor_protected():
    draft = "before middle after"
    patch = StructuredPatch(
        base_sha256=text_sha256(draft), before="middle", after="fixed"
    )

    result = apply_structured_patches(draft, [patch])

    assert result.text == "before fixed after"
    assert result.applied == 1


def test_patch_targets_fenced_code_block_only():
    draft = "outside x\n```python\nx = 1\n```\noutside x"
    patch = StructuredPatch(
        base_sha256=text_sha256(draft),
        target="code_block_0",
        before="x = 1",
        after="x = 2",
    )

    result = apply_structured_patches(draft, [patch])

    assert result.text == "outside x\n```python\nx = 2\n```\noutside x"


def test_patch_rejects_wrong_hash_ambiguous_anchor_and_large_change():
    draft = "same same"
    with pytest.raises(PatchApplyError, match="base_sha256"):
        apply_structured_patches(
            draft,
            [StructuredPatch(base_sha256="bad", before="same", after="x")],
        )
    with pytest.raises(PatchApplyError, match="matched 2 times"):
        apply_structured_patches(
            draft,
            [StructuredPatch(base_sha256=text_sha256(draft), before="same", after="x")],
        )
    with pytest.raises(PatchApplyError, match="changed ratio"):
        apply_structured_patches(
            "abcdefghij",
            [
                StructuredPatch(
                    base_sha256=text_sha256("abcdefghij"),
                    before="abcdefghij",
                    after="xxxxxxxxxx",
                )
            ],
            max_changed_ratio=0.3,
        )


def test_patch_insert_and_delete_operations():
    draft = "alpha beta gamma"
    digest = text_sha256(draft)
    result = apply_structured_patches(
        draft,
        [
            StructuredPatch(
                base_sha256=digest,
                operation=PatchOperation.INSERT_AFTER,
                before="alpha",
                after="!",
            ),
            StructuredPatch(
                base_sha256=digest,
                operation=PatchOperation.DELETE,
                before=" gamma",
            ),
        ],
        max_changed_ratio=0.5,
    )
    assert result.text == "alpha! beta"


def test_gate_forces_structural_failure_and_length_cap():
    gate = AdaptiveGate(config())
    req = request()

    structural = gate.evaluate(req, GateSignals(structural_failure=True))
    length = gate.evaluate(req, GateSignals(finish_reason="length"))

    assert structural.decision == GateDecision.FORCE
    assert length.decision == GateDecision.FORCE


def test_gate_off_and_always_are_deterministic():
    signals = GateSignals(output_tokens=10000, structural_failure=True)
    assert (
        AdaptiveGate(config(gate_policy="off")).evaluate(request(), signals).decision
        == GateDecision.SKIP
    )
    assert (
        AdaptiveGate(config(gate_policy="always"))
        .evaluate(request(), GateSignals())
        .decision
        == GateDecision.FORCE
    )


@pytest.mark.asyncio
async def test_skip_commits_draft_without_calling_reviewer():
    turn = FakeTurn("draft answer")
    reviewer = FakeReviewer(ReviewDecision(ReviewAction.PASS))
    orchestrator = FusionOrchestrator(
        config(gate_policy="off"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(request())

    assert result.text == "draft answer"
    assert result.path == "skip"
    assert turn.committed_draft
    assert reviewer.calls == []


@pytest.mark.asyncio
async def test_user_skip_request_accepts_finished_draft_without_reviewer():
    turn = FakeTurn("draft answer")
    reviewer = FakeReviewer(ReviewDecision(ReviewAction.PASS))
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )
    request_skip_review("session-1")

    output = await events(orchestrator, request())
    result = result_from(output)

    assert result.text == "draft answer"
    assert result.path == "skip_user"
    assert turn.committed_draft
    assert reviewer.calls == []
    assert any(event.phase == "review_skipped" for event in output)


def test_active_skip_registry_rejects_stale_sessions_and_cleans_up():
    session_id = "active-skip-test"
    assert request_active_skip_review(session_id) is False

    begin_fusion_session(session_id)
    assert request_active_skip_review(session_id) is True
    assert consume_skip_review(session_id) is True

    end_fusion_session(session_id)
    assert request_active_skip_review(session_id) is False


@pytest.mark.asyncio
async def test_pass_reasoning_stream_replays_canonical_content():
    turn = FakeTurn("draft answer")
    reviewer = FakeReviewer(ReviewDecision(ReviewAction.PASS))
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    output = await events(orchestrator, request(mode=StreamMode.REASONING))

    assert "".join(e.text for e in output if e.channel == "reasoning") == "draft answer"
    assert "".join(e.text for e in output if e.channel == "content") == "draft answer"
    assert result_from(output).path == "pass"
    assert turn.committed_draft


@pytest.mark.asyncio
async def test_mid_generation_checkpoint_continue_resumes_same_draft():
    turn = FakeTurn("first direction ", checkpoint=True, resumed="and finish")
    reviewer = FakeReviewer(
        decision=ReviewDecision(ReviewAction.PASS),
        checkpoint_decision=CheckpointDecision(CheckpointAction.CONTINUE),
    )
    orchestrator = FusionOrchestrator(
        config(
            gate_policy="off",
            mid_generation_review_enabled=True,
            mid_generation_checkpoint_tokens=4,
        ),
        FakeGenerator(turn),
        reviewer,
    )

    output = await events(
        orchestrator, request(mode=StreamMode.REASONING, max_tokens=12)
    )
    result = result_from(output)

    assert result.text == "first direction and finish"
    assert result.metadata["checkpoint_action"] == "continue"
    assert result.metadata["checkpoint_reason"] == "token_limit"
    assert len(reviewer.checkpoint_calls) == 1
    assert turn.resume_decisions[0].action == CheckpointAction.CONTINUE
    assert any(e.phase == "checkpoint_review_begin" for e in output)


@pytest.mark.asyncio
async def test_completed_thinking_checkpoint_is_audited_without_resuming():
    turn = FakeTurn(
        "<think>checked</think>answer",
        checkpoint=True,
        checkpoint_reason="thinking",
        checkpoint_finished=True,
        resumed="must not appear",
    )
    reviewer = FakeReviewer(
        checkpoint_decision=CheckpointDecision(CheckpointAction.CONTINUE),
    )
    orchestrator = FusionOrchestrator(
        config(
            gate_policy="off",
            thinking_audit_enabled=True,
            thinking_audit_min_tokens=2,
            thinking_audit_max_tokens=4,
        ),
        FakeGenerator(turn),
        reviewer,
    )

    output = await events(orchestrator, request(max_tokens=12))
    result = result_from(output)

    assert result.text == "<think>checked</think>answer"
    assert result.metadata["checkpoint_reason"] == "thinking"
    assert turn.resume_decisions is None
    begin = next(e for e in output if e.phase == "checkpoint_review_begin")
    assert begin.metadata["reason"] == "thinking"


@pytest.mark.asyncio
async def test_mid_generation_checkpoint_redirect_replaces_rejected_draft():
    turn = FakeTurn("wrong path", checkpoint=True, resumed="correct answer")
    reviewer = FakeReviewer(
        decision=ReviewDecision(ReviewAction.PASS),
        checkpoint_decision=CheckpointDecision(
            CheckpointAction.REDIRECT,
            summary="wrong direction",
            guidance=("Use the second approach",),
        ),
    )
    orchestrator = FusionOrchestrator(
        config(
            gate_policy="off",
            mid_generation_review_enabled=True,
            mid_generation_checkpoint_tokens=2,
        ),
        FakeGenerator(turn),
        reviewer,
    )

    output = await events(orchestrator, request(mode=StreamMode.DRAFT, max_tokens=12))
    result = result_from(output)

    assert result.text == "correct answer"
    assert result.draft == "correct answer"
    assert result.metadata["checkpoint_action"] == "redirect"
    assert "checkpoint_rejected_sha256" in result.metadata
    assert any(e.phase == "draft_reset" for e in output)


@pytest.mark.asyncio
async def test_reasoning_handoff_rebuilds_without_exposing_seed():
    seed = "Privately reconsider the invariant before choosing the algorithm."
    turn = FakeTurn("uncertain path", checkpoint=True, resumed="verified answer")
    reviewer = FakeReviewer(
        checkpoint_decision=CheckpointDecision(
            CheckpointAction.REASONING_HANDOFF,
            summary="continue from corrected reasoning",
            reasoning_seed=seed,
            constraints=("Preserve the boundary condition",),
        ),
    )
    orchestrator = FusionOrchestrator(
        config(
            gate_policy="off",
            mid_generation_review_enabled=True,
            mid_generation_checkpoint_tokens=2,
            reviewer_guidance_mode="reasoning_handoff",
        ),
        FakeGenerator(turn),
        reviewer,
    )

    output = await events(orchestrator, request(mode=StreamMode.DRAFT, max_tokens=12))
    result = result_from(output)

    assert result.text == "verified answer"
    assert result.metadata["checkpoint_action"] == "reasoning_handoff"
    assert result.metadata["reasoning_handoff_chars"] == len(seed)
    assert result.metadata["reasoning_handoff_constraint_count"] == 1
    assert seed not in repr(result.metadata)
    assert seed not in repr([event.metadata for event in output])
    reset = next(event for event in output if event.phase == "draft_reset")
    assert reset.metadata["reason"] == "checkpoint_reasoning_handoff"


@pytest.mark.asyncio
async def test_disabled_reasoning_handoff_fails_open_without_using_seed():
    turn = FakeTurn("partial ", checkpoint=True, resumed="answer")
    reviewer = FakeReviewer(
        checkpoint_decision=CheckpointDecision(
            CheckpointAction.REASONING_HANDOFF,
            reasoning_seed="must not be used",
        )
    )
    orchestrator = FusionOrchestrator(
        config(gate_policy="off", mid_generation_review_enabled=True),
        FakeGenerator(turn),
        reviewer,
    )

    result = await orchestrator.generate(request(max_tokens=2048))

    assert result.text == "partial answer"
    assert result.metadata["checkpoint_action"] == "continue"
    assert result.metadata["checkpoint_review_error"] == "ValueError"


@pytest.mark.asyncio
async def test_checkpoint_reviewer_failure_is_bounded_by_request_risk():
    ordinary_turn = FakeTurn("partial ", checkpoint=True, resumed="answer")
    ordinary = FusionOrchestrator(
        config(gate_policy="off", mid_generation_review_enabled=True),
        FakeGenerator(ordinary_turn),
        FakeReviewer(checkpoint_error=TimeoutError()),
    )
    result = await ordinary.generate(request(max_tokens=2048))
    assert result.text == "partial answer"
    assert result.metadata["checkpoint_action"] == "continue"
    assert result.metadata["checkpoint_review_error"] == "TimeoutError"

    risky_turn = FakeTurn("partial", checkpoint=True, resumed="answer")
    risky = FusionOrchestrator(
        config(gate_policy="off", mid_generation_review_enabled=True),
        FakeGenerator(risky_turn),
        FakeReviewer(checkpoint_error=TimeoutError()),
    )
    with pytest.raises(FusionExecutionError, match="checkpoint_reviewer_failed"):
        await risky.generate(request(high_risk=True, max_tokens=2048))
    assert risky_turn.aborted


@pytest.mark.asyncio
async def test_native_patch_updates_draft_without_full_replay():
    draft = "alpha beta gamma"
    patch = StructuredPatch(
        base_sha256=text_sha256(draft), before="beta", after="fixed"
    )
    turn = FakeTurn(draft)
    reviewer = FakeReviewer(ReviewDecision(ReviewAction.PATCH, patches=(patch,)))
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    output = await events(orchestrator, request(mode=StreamMode.DRAFT))
    result = result_from(output)

    assert result.text == "alpha fixed gamma"
    assert result.path == "patch"
    assert any(e.phase == "patch" for e in output)
    assert not any(e.channel == "content" for e in output)
    assert turn.committed_final == result.text


@pytest.mark.asyncio
async def test_revise_requires_and_applies_local_patch():
    draft = "bad answer"
    patch = StructuredPatch(base_sha256=text_sha256(draft), before="bad", after="good")
    turn = FakeTurn(draft, revision=(patch,))
    reviewer = FakeReviewer(
        ReviewDecision(ReviewAction.REVISE, instructions=("Replace bad",))
    )
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(request())

    assert result.text == "good answer"
    assert result.path == "revise"
    assert turn.committed_final == "good answer"


@pytest.mark.asyncio
async def test_malformed_local_revision_has_bounded_fallback():
    turn = FakeTurn("safe draft", revision_error=ValueError("bad JSON"))
    reviewer = FakeReviewer(
        ReviewDecision(ReviewAction.REVISE, instructions=("Fix it",))
    )
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(request())

    assert result.text == "safe draft"
    assert result.path == "patch_failed_draft"
    assert result.metadata["revision_error"] == "ValueError"


@pytest.mark.asyncio
async def test_escalate_without_resolver_uses_local_blueprint():
    turn = FakeTurn("wrong", realization="rebuilt locally")
    reviewer = FakeReviewer(
        ReviewDecision(
            ReviewAction.ESCALATE,
            blueprint={"conclusion": "correct"},
        )
    )
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(request())

    assert result.text == "rebuilt locally"
    assert result.path == "local_rebuild"


@pytest.mark.asyncio
async def test_optional_resolver_is_called_once_for_escalation():
    draft = "wrong conclusion"
    patch = StructuredPatch(
        base_sha256=text_sha256(draft), before="wrong", after="correct"
    )
    review = ReviewDecision(ReviewAction.ESCALATE, summary="core error")
    resolver = FakeResolver(ReviewDecision(ReviewAction.PATCH, patches=(patch,)))
    turn = FakeTurn(draft)
    orchestrator = FusionOrchestrator(
        config(gate_policy="always", resolver_enabled=True, max_changed_ratio=0.40),
        FakeGenerator(turn),
        FakeReviewer(review),
        resolver,
    )

    result = await orchestrator.generate(request())

    assert result.text == "correct conclusion"
    assert result.path == "resolved_patch"
    assert len(resolver.calls) == 1


@pytest.mark.asyncio
async def test_resolver_only_handles_configured_triggers():
    resolver = FakeResolver(ReviewDecision(ReviewAction.PASS))
    turn = FakeTurn("draft", realization="local")
    orchestrator = FusionOrchestrator(
        config(
            gate_policy="always",
            resolver_enabled=True,
            resolver_triggers=("patch_failed",),
        ),
        FakeGenerator(turn),
        FakeReviewer(
            ReviewDecision(
                ReviewAction.ESCALATE,
                blueprint={"conclusion": "local"},
            )
        ),
        resolver,
    )

    result = await orchestrator.generate(request())

    assert result.text == "local"
    assert result.path == "local_rebuild"
    assert resolver.calls == []


@pytest.mark.asyncio
async def test_low_reviewer_confidence_can_trigger_resolver():
    resolver = FakeResolver(ReviewDecision(ReviewAction.PASS))
    turn = FakeTurn("draft")
    orchestrator = FusionOrchestrator(
        config(gate_policy="always", resolver_enabled=True),
        FakeGenerator(turn),
        FakeReviewer(ReviewDecision(ReviewAction.PASS, confidence=0.1)),
        resolver,
    )

    result = await orchestrator.generate(request())

    assert result.path == "resolver_pass"
    assert len(resolver.calls) == 1


@pytest.mark.asyncio
async def test_resolver_disabled_never_calls_configured_backend():
    resolver = FakeResolver()
    turn = FakeTurn("draft", realization="local")
    orchestrator = FusionOrchestrator(
        config(gate_policy="always", resolver_enabled=False),
        FakeGenerator(turn),
        FakeReviewer(
            ReviewDecision(ReviewAction.ESCALATE, blueprint={"conclusion": "local"})
        ),
        resolver,
    )

    result = await orchestrator.generate(request())

    assert result.text == "local"
    assert resolver.calls == []


@pytest.mark.asyncio
async def test_reviewer_failure_returns_draft_for_ordinary_request():
    turn = FakeTurn("safe draft")
    reviewer = FakeReviewer(error=TimeoutError())
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(request())

    assert result.text == "safe draft"
    assert result.path == "reviewer_failed_draft"
    assert result.metadata["review_error"] == "TimeoutError"


@pytest.mark.asyncio
async def test_reviewer_parse_failure_uses_external_model_for_full_review():
    draft = "wrong conclusion"
    patch = StructuredPatch(
        base_sha256=text_sha256(draft), before="wrong", after="correct"
    )
    resolver = FakeResolver(
        review_decision=ReviewDecision(ReviewAction.PATCH, patches=(patch,))
    )
    turn = FakeTurn(draft)
    orchestrator = FusionOrchestrator(
        config(
            gate_policy="always",
            resolver_enabled=True,
            max_changed_ratio=0.5,
        ),
        FakeGenerator(turn),
        FakeReviewer(error=ValueError("review response is not valid JSON")),
        resolver,
    )

    result = await orchestrator.generate(request())

    assert result.text == "correct conclusion"
    assert result.path == "resolver_review_patch"
    assert result.metadata["review_fallback"] == "external"
    assert len(resolver.review_calls) == 1
    assert resolver.calls == []


@pytest.mark.asyncio
async def test_external_review_failure_uses_resolver_unavailable_policy():
    resolver = FakeResolver(review_error=TimeoutError("external stalled"))
    turn = FakeTurn("draft")
    orchestrator = FusionOrchestrator(
        config(gate_policy="always", resolver_enabled=True),
        FakeGenerator(turn),
        FakeReviewer(error=ValueError("invalid JSON")),
        resolver,
    )

    result = await orchestrator.generate(request())

    assert result.path == "resolver_review_failed_draft"
    assert result.metadata["resolver_review_error"] == "TimeoutError"


@pytest.mark.asyncio
async def test_reviewer_failure_emits_public_diagnostic_event():
    class DiagnosticError(ValueError):
        error_type = "ValueError"
        transcript = {
            "output": "not-json",
            "tokens": 12,
            "duration_seconds": 1.25,
        }

    turn = FakeTurn("safe draft")
    reviewer = FakeReviewer(error=DiagnosticError("invalid decision"))
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    events = [event async for event in orchestrator.stream(request())]
    error = next(event for event in events if event.phase == "review_error")

    assert error.metadata["error"] == "ValueError"
    assert error.metadata["output"] == "not-json"
    assert error.metadata["tokens"] == 12


@pytest.mark.asyncio
async def test_reviewer_progress_is_streamed_before_result():
    class ProgressReviewer(FakeReviewer):
        async def review_with_progress(
            self, request, draft, draft_sha256, signals, progress
        ):
            progress(
                {
                    "stage": "prefill",
                    "processed": 32,
                    "total": 64,
                    "speed": 100.0,
                }
            )
            await asyncio.sleep(0)
            progress(
                {
                    "stage": "generating",
                    "delta": '{"action":"PASS"}',
                    "tokens": 4,
                }
            )
            return self.decision

    turn = FakeTurn("safe draft")
    reviewer = ProgressReviewer(decision=ReviewDecision(ReviewAction.PASS, risk="low"))
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    events = [event async for event in orchestrator.stream(request())]
    phases = [event.phase for event in events]
    progress = [event for event in events if event.phase == "review_progress"]

    assert phases.index("review_begin") < phases.index("review_progress")
    assert phases.index("review_progress") < phases.index("review_result")
    assert progress[0].metadata["stage"] == "prefill"
    assert progress[1].metadata["delta"] == '{"action":"PASS"}'


@pytest.mark.asyncio
async def test_high_risk_failure_aborts_transaction():
    turn = FakeTurn("unverified")
    reviewer = FakeReviewer(error=RuntimeError("offline"))
    orchestrator = FusionOrchestrator(
        config(gate_policy="always"), FakeGenerator(turn), reviewer
    )

    with pytest.raises(FusionExecutionError, match="reviewer_failed"):
        await orchestrator.generate(request(high_risk=True))

    assert turn.aborted
    assert not turn.committed_draft


@pytest.mark.asyncio
async def test_validation_failure_aborts_without_committing():
    turn = FakeTurn("draft")
    orchestrator = FusionOrchestrator(
        config(gate_policy="off"), FakeGenerator(turn), validator=lambda _: False
    )

    with pytest.raises(FusionExecutionError, match="failed validation"):
        await orchestrator.generate(request())

    assert turn.aborted


@pytest.mark.asyncio
async def test_valid_tool_call_is_committed_only_after_audit_pass():
    call = FusionToolCall("call_1", "get_weather", '{"city":"Shanghai"}')
    turn = FakeTurn("", tool_calls=(call,))
    reviewer = FakeReviewer(tool_decisions=[ToolReviewDecision(ToolReviewAction.PASS)])
    orchestrator = FusionOrchestrator(
        config(gate_policy="off"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(tool_request())

    assert result.tool_calls == (call,)
    assert result.path == "tool_pass"
    assert len(reviewer.tool_calls) == 1
    assert reviewer.tool_calls[0][3] == ()


@pytest.mark.asyncio
async def test_invalid_tool_call_cannot_be_committed_by_reviewer_pass():
    call = FusionToolCall("call_1", "get_weather", '{"country":"CN"}')
    turn = FakeTurn("", tool_calls=(call,))
    reviewer = FakeReviewer(tool_decisions=[ToolReviewDecision(ToolReviewAction.PASS)])
    orchestrator = FusionOrchestrator(
        config(gate_policy="off"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(tool_request())

    assert result.tool_calls == ()
    assert result.path == "tool_denied"
    assert result.metadata["tool_review_error"] == "invalid_pass"
    assert reviewer.tool_calls[0][3]


@pytest.mark.asyncio
async def test_tool_replan_gets_one_regeneration_and_final_review():
    bad = FusionToolCall("call_1", "get_weather", "{}")
    fixed = FusionToolCall("call_2", "get_weather", '{"city":"Shanghai"}')
    turn = FakeTurn("", tool_calls=(bad,), replanned_tool_calls=(fixed,))
    reviewer = FakeReviewer(
        tool_decisions=[
            ToolReviewDecision(
                ToolReviewAction.REPLAN, guidance=("Provide the required city.",)
            ),
            ToolReviewDecision(ToolReviewAction.PASS),
        ]
    )
    orchestrator = FusionOrchestrator(
        config(gate_policy="off"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(tool_request())

    assert result.tool_calls == (fixed,)
    assert result.path == "tool_replan_pass"
    assert len(turn.tool_replan_decisions) == 1
    assert [call[-1] for call in reviewer.tool_calls] == [False, True]


@pytest.mark.asyncio
async def test_tool_reviewer_failure_is_fail_closed():
    call = FusionToolCall("call_1", "get_weather", '{"city":"Shanghai"}')
    turn = FakeTurn("", tool_calls=(call,))
    reviewer = FakeReviewer(tool_error=TimeoutError())
    orchestrator = FusionOrchestrator(
        config(gate_policy="off"), FakeGenerator(turn), reviewer
    )

    result = await orchestrator.generate(tool_request())

    assert result.tool_calls == ()
    assert result.path == "tool_denied"
    assert result.metadata["tool_review_error"] == "TimeoutError"


def test_enabled_resolver_requires_backend():
    with pytest.raises(ValueError, match="resolver backend"):
        FusionOrchestrator(
            config(gate_policy="off", resolver_enabled=True), FakeGenerator(None)
        )


def test_enabled_review_requires_reviewer():
    with pytest.raises(ValueError, match="reviewer backend"):
        FusionOrchestrator(config(), FakeGenerator(None))


def test_mid_generation_review_requires_checkpoint_capable_reviewer():
    class FinalOnlyReviewer:
        async def review(self, request, draft, draft_sha256, signals):
            return ReviewDecision(ReviewAction.PASS)

    with pytest.raises(ValueError, match="checkpoint reviewer support"):
        FusionOrchestrator(
            config(gate_policy="off", mid_generation_review_enabled=True),
            FakeGenerator(None),
            FinalOnlyReviewer(),
        )


def test_review_decision_validation():
    with pytest.raises(ValueError, match="patch"):
        ReviewDecision(ReviewAction.PATCH)
    with pytest.raises(ValueError, match="instructions"):
        ReviewDecision(ReviewAction.REVISE)
    with pytest.raises(ValueError, match="confidence"):
        ReviewDecision(ReviewAction.PASS, confidence=2.0)


def test_thinking_audit_window_validation():
    with pytest.raises(ValueError, match="1 <= min <= max"):
        config(
            thinking_audit_enabled=True,
            thinking_audit_min_tokens=8,
            thinking_audit_max_tokens=4,
        )
    with pytest.raises(ValueError, match="reviewer_guidance_mode"):
        config(reviewer_guidance_mode="raw_think")
