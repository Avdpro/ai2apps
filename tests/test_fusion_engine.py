from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from dynamoe.fusion import (
    AdaptiveGate,
    DraftChunk,
    FailurePolicy,
    FusionConfig,
    FusionRequest,
    GateDecision,
    GateSignals,
    PatchApplyError,
    ReviewAction,
    ReviewDecision,
    StreamMode,
    StructuredPatch,
    apply_structured_patches,
    text_sha256,
)
from dynamoe.fusion.engine import FusionExecutionError, FusionOrchestrator
from dynamoe.fusion.types import PatchOperation


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

    async def stream_draft(self):
        for start in range(0, len(self.draft), self.chunk_size):
            yield DraftChunk(text=self.draft[start : start + self.chunk_size])
        yield DraftChunk(
            finished=True,
            token_count=max(1, len(self.draft.split())),
            signals=self.signals,
        )

    async def revise(self, draft, decision):
        if self.revision_error is not None:
            raise self.revision_error
        return self.revision

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
    def __init__(self, decision=None, error=None):
        self.decision = decision
        self.error = error
        self.calls = []

    async def review(self, request, draft, draft_sha256, signals):
        self.calls.append((request, draft, draft_sha256, signals))
        if self.error:
            raise self.error
        return self.decision


class FakeResolver:
    def __init__(self, decision=None, error=None):
        self.decision = decision
        self.error = error
        self.calls = []

    async def resolve(self, request, draft, review):
        self.calls.append((request, draft, review))
        if self.error:
            raise self.error
        return self.decision


def request(*, mode=StreamMode.FINAL, high_risk=False):
    return FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="session-1",
        stream_mode=mode,
        high_risk=high_risk,
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
            [
                StructuredPatch(
                    base_sha256=text_sha256(draft), before="same", after="x"
                )
            ],
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
    patch = StructuredPatch(
        base_sha256=text_sha256(draft), before="bad", after="good"
    )
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
        config(
            gate_policy="always", resolver_enabled=True, max_changed_ratio=0.40
        ),
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


def test_enabled_resolver_requires_backend():
    with pytest.raises(ValueError, match="resolver backend"):
        FusionOrchestrator(
            config(gate_policy="off", resolver_enabled=True), FakeGenerator(None)
        )


def test_enabled_review_requires_reviewer():
    with pytest.raises(ValueError, match="reviewer backend"):
        FusionOrchestrator(config(), FakeGenerator(None))


def test_review_decision_validation():
    with pytest.raises(ValueError, match="patch"):
        ReviewDecision(ReviewAction.PATCH)
    with pytest.raises(ValueError, match="instructions"):
        ReviewDecision(ReviewAction.REVISE)
    with pytest.raises(ValueError, match="confidence"):
        ReviewDecision(ReviewAction.PASS, confidence=2.0)
