from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest

from ai2apps.fusion.adapters import (
    OMLXGeneratorBackend,
    OMLXReviewerBackend,
    OpenAICompatibleReviewBackend,
)
from ai2apps.fusion.profiles import (
    FusionProfile,
    ResolverConfig,
    RoleConfig,
    fusion_profile_from_mapping,
    profile_to_mapping,
)
from ai2apps.fusion.prompts import (
    REVIEW_SYSTEM_PROMPT,
    build_checkpoint_review_messages,
    build_review_messages,
    build_tool_review_messages,
)
from ai2apps.fusion.serde import (
    checkpoint_decision_from_json,
    review_decision_from_json,
    tool_review_decision_from_json,
)
from ai2apps.fusion.types import (
    CheckpointAction,
    FusionRequest,
    FusionToolCall,
    ReviewAction,
    StreamMode,
    ToolReviewAction,
)


def local(model):
    return RoleConfig(backend="local", model=model)


def remote(model="cloud"):
    return RoleConfig(
        backend="openai-compatible",
        model=model,
        base_url="https://provider.test/v1",
        credential_ref="provider-key",
    )


def test_profile_defaults_to_resolver_disabled_and_has_stable_fingerprint():
    profile = FusionProfile("fusion", local("small"), local("reviewer"))
    restored = fusion_profile_from_mapping(profile_to_mapping(profile))

    assert not profile.resolver.enabled
    assert profile.fingerprint == restored.fingerprint
    assert restored.engine_config().resolver_enabled is False


def test_mapping_uses_role_specific_reviewer_token_defaults():
    profile = fusion_profile_from_mapping(
        {
            "fusion": {
                "model_id": "fusion",
                "generator": {"backend": "local", "model": "small"},
                "reviewer": {"backend": "local", "model": "reviewer"},
            }
        }
    )

    assert profile.generator.max_tokens == 384
    assert profile.reviewer.max_tokens == 8192
    assert profile.engine_config().mid_generation_reviewer_max_tokens == 256


def test_mapping_preserves_explicit_reviewer_token_limits():
    profile = fusion_profile_from_mapping(
        {
            "fusion": {
                "model_id": "fusion",
                "generator": {"backend": "local", "model": "small"},
                "reviewer": {
                    "backend": "local",
                    "model": "reviewer",
                    "max_tokens": 444,
                },
                "gate": {"mid_generation_reviewer_max_tokens": 111},
            }
        }
    )

    assert profile.reviewer.max_tokens == 444
    assert profile.engine_config().mid_generation_reviewer_max_tokens == 111


def test_profile_round_trips_cache_moe_defaults():
    profile = FusionProfile(
        "fusion",
        local("small"),
        local("reviewer"),
        cache_moe={
            "generator": {"l1_mode": "off", "engine_boost": "turbo"},
            "reviewer": {"l1_mode": "auto", "engine_boost": "blast"},
        },
    )

    restored = fusion_profile_from_mapping(profile_to_mapping(profile))

    assert restored.cache_moe == {
        "generator": {
            "l1_mode": "off",
            "prefill_boost": "turbo",
            "decode_boost": "turbo",
        },
        "reviewer": {
            "l1_mode": "auto",
            "prefill_boost": "blast",
            "decode_boost": "blast",
        },
    }
    with pytest.raises(ValueError, match="engine_boost"):
        FusionProfile(
            "bad",
            local("small"),
            local("reviewer"),
            cache_moe={"reviewer": {"engine_boost": "unsafe"}},
        )


def test_profile_migrates_legacy_shared_cache_moe_defaults_to_both_roles():
    profile = fusion_profile_from_mapping(
        {
            "fusion": {
                "model_id": "legacy",
                "generator": {"backend": "local", "model": "small"},
                "reviewer": {"backend": "local", "model": "reviewer"},
                "cache_moe": {"l1_mode": "off", "engine_boost": "turbo"},
            }
        }
    )

    assert profile.cache_moe["generator"]["prefill_boost"] == "turbo"
    assert profile.cache_moe["generator"]["decode_boost"] == "turbo"
    assert profile.cache_moe["reviewer"]["l1_mode"] == "off"


def test_profile_accepts_auto_for_prefill_only():
    profile = FusionProfile(
        "auto-prefill",
        local("small"),
        local("reviewer"),
        cache_moe={"generator": {"prefill_boost": "auto", "decode_boost": "natural"}},
    )

    assert profile.cache_moe["generator"]["prefill_boost"] == "auto"
    with pytest.raises(ValueError, match="decode_boost"):
        FusionProfile(
            "bad-auto-decode",
            local("small"),
            local("reviewer"),
            cache_moe={"generator": {"decode_boost": "auto"}},
        )


def test_profile_requires_local_generator():
    with pytest.raises(ValueError, match="generator must"):
        FusionProfile("fusion", remote("generator"), local("reviewer"))


def test_three_stage_profile_requires_local_reviewer():
    with pytest.raises(ValueError, match="local reviewer"):
        FusionProfile(
            "fusion",
            local("small"),
            remote("reviewer"),
            ResolverConfig(enabled=True, role=remote("resolver")),
        )


def test_profile_parses_optional_remote_resolver():
    profile = fusion_profile_from_mapping(
        {
            "fusion": {
                "model_id": "fusion-quality",
                "generator": {"backend": "local", "model": "small"},
                "reviewer": {"backend": "local", "model": "reviewer"},
                "resolver": {
                    "enabled": True,
                    "backend": "openai-compatible",
                    "model": "cloud",
                    "base_url": "https://provider.test/v1",
                    "credential_ref": "key",
                    "max_calls_per_turn": 1,
                },
                "gate": {"gate_policy": "always", "review_threshold": 0.2},
            }
        }
    )

    assert profile.resolver.enabled
    assert profile.resolver.role.backend == "openai-compatible"
    assert profile.engine_config().gate_policy == "always"
    assert profile.engine_config().review_threshold == 0.2


def test_profile_upgrades_legacy_resolver_to_handle_reviewer_failure():
    profile = fusion_profile_from_mapping(
        {
            "fusion": {
                "model_id": "fusion-quality",
                "generator": {"backend": "local", "model": "small"},
                "reviewer": {"backend": "local", "model": "reviewer"},
                "resolver": {
                    "enabled": True,
                    "backend": "openai-compatible",
                    "model": "cloud",
                    "base_url": "https://provider.test/v1",
                    "credential_ref": "key",
                    "triggers": [
                        "reviewer_escalate",
                        "reviewer_uncertain",
                        "patch_failed",
                    ],
                },
            }
        }
    )

    assert "reviewer_failed" in profile.resolver.triggers
    assert "reviewer_failed" in profile.engine_config().resolver_triggers


def test_profile_rejects_unknown_gate_setting():
    profile = FusionProfile(
        "fusion", local("small"), local("reviewer"), gate={"typo": 1}
    )
    with pytest.raises(ValueError, match="unknown Fusion gate"):
        profile.engine_config()


def test_review_json_parser_accepts_fence_and_rejects_invalid_protocol():
    decision = review_decision_from_json(
        '```json\n{"action":"PASS","risk":"low","confidence":0.9}\n```'
    )
    assert decision.action == ReviewAction.PASS
    thinking = review_decision_from_json(
        '<think>check carefully</think>{"action":"PASS","risk":"low"}'
    )
    assert thinking.action == ReviewAction.PASS
    with pytest.raises(ValueError, match="action"):
        review_decision_from_json('{"risk":"low"}')


def test_review_json_parser_handles_partial_thinking_and_nested_objects():
    decision = review_decision_from_json(
        "reasoning without an opening tag</think>"
        '{"action":"PASS","risk":"low","patches":[],"instructions":[],'
        '"blueprint":{}}'
    )

    assert decision.action == ReviewAction.PASS
    assert decision.blueprint == {}


def test_review_prompt_omits_redundant_summary_but_parser_remains_compatible():
    assert '"summary"' not in REVIEW_SYSTEM_PROMPT
    decision = review_decision_from_json(
        '{"action":"PASS","summary":"legacy","risk":"low"}'
    )
    assert decision.summary == "legacy"


def test_review_parser_binds_hashless_patch_to_current_draft():
    decision = review_decision_from_json(
        '{"action":"PATCH","risk":"low","patches":['
        '{"operation":"replace","before":"bad","after":"good"}]}',
        base_sha256="server-owned-hash",
    )

    assert decision.patches[0].base_sha256 == "server-owned-hash"


def test_other_review_parsers_ignore_trailing_nested_objects():
    checkpoint = checkpoint_decision_from_json(
        'prose {"action":"CONTINUE","metadata":{}}'
    )
    tool = tool_review_decision_from_json('prose {"action":"PASS","metadata":{}}')

    assert checkpoint.action == CheckpointAction.CONTINUE
    assert tool.action == ToolReviewAction.PASS


def test_checkpoint_json_parser_accepts_thinking_prefix():
    decision = checkpoint_decision_from_json(
        '<think>check direction</think>{"action":"CONTINUE","confidence":0.8}'
    )
    assert decision.action == CheckpointAction.CONTINUE


def test_checkpoint_json_parser_accepts_reasoning_handoff():
    decision = checkpoint_decision_from_json(
        '{"action":"REASONING_HANDOFF","reasoning_seed":"check x first",'
        '"constraints":["keep y fixed"]}'
    )
    assert decision.action == CheckpointAction.REASONING_HANDOFF
    assert decision.reasoning_seed == "check x first"
    assert decision.constraints == ("keep y fixed",)

    with pytest.raises(ValueError, match="reasoning_seed"):
        checkpoint_decision_from_json('{"action":"REASONING_HANDOFF"}')


def test_thinking_detector_triggers_on_short_closed_block():
    from ai2apps.fusion.adapters import _ThinkingAuditDetector

    detector = _ThinkingAuditDetector(FakeTokenizer(), min_tokens=128, max_tokens=256)
    assert detector.feed("<think>short</think>", completion_tokens=3, finished=False)
    assert detector.thinking_tokens == 1


class FakeOutput:
    def __init__(
        self,
        *,
        text="",
        new_text="",
        completion_tokens=0,
        finish_reason="stop",
        finished=False,
        tool_calls=None,
    ):
        self.text = text
        self.new_text = new_text
        self.completion_tokens = completion_tokens
        self.finish_reason = finish_reason
        self.finished = finished
        self.tool_calls = tool_calls


class FakeOMLXEngine:
    def __init__(self, chat_text='{"action":"PASS"}'):
        self.chat_text = chat_text
        self.stream_kwargs = None
        self.chat_kwargs = []

    async def stream_chat(self, messages, **kwargs):
        self.stream_kwargs = kwargs
        if kwargs.get("temperature") == 0.0:
            self.chat_kwargs.append((messages, kwargs))
            yield FakeOutput(
                new_text=self.chat_text,
                completion_tokens=4,
                finished=True,
            )
            return
        yield FakeOutput(new_text="hello ")
        yield FakeOutput(new_text="world", completion_tokens=2)

    async def chat(self, messages, **kwargs):
        self.chat_kwargs.append((messages, kwargs))
        return FakeOutput(text=self.chat_text, completion_tokens=4)


class FakeCheckpointOMLXEngine(FakeOMLXEngine):
    def __init__(self):
        super().__init__()
        self.stream_calls = []

    async def stream_chat(self, messages, **kwargs):
        self.stream_calls.append((messages, kwargs))
        if kwargs.get("is_partial"):
            yield FakeOutput(
                new_text="finish",
                completion_tokens=2,
                finish_reason="stop",
            )
        else:
            yield FakeOutput(
                new_text="first ",
                completion_tokens=4,
                finish_reason="length",
            )


class FakeTokenizer:
    think_start = "<think>"
    think_end = "</think>"

    def encode(self, text, add_special_tokens=False):
        return text.replace("\n", " ").split()


class FakeThinkingOMLXEngine(FakeOMLXEngine):
    tokenizer = FakeTokenizer()

    def __init__(self):
        super().__init__()
        self.stream_calls = []

    async def stream_chat(self, messages, **kwargs):
        self.stream_calls.append((messages, kwargs))
        if kwargs.get("is_partial"):
            yield FakeOutput(
                new_text=" continue</think>\nanswer",
                completion_tokens=3,
                finish_reason="stop",
                finished=True,
            )
            return
        yield FakeOutput(new_text="<thi", completion_tokens=1)
        yield FakeOutput(new_text="nk> first step.", completion_tokens=4)


def fusion_request():
    return FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="s1",
        max_tokens=64,
        stream_mode=StreamMode.FINAL,
    )


@pytest.mark.asyncio
async def test_omlx_generator_marks_provisional_draft_no_store():
    engine = FakeOMLXEngine()
    turn = await OMLXGeneratorBackend(engine).begin_turn(fusion_request())

    chunks = [chunk async for chunk in turn.stream_draft()]

    assert "".join(chunk.text for chunk in chunks) == "hello world"
    assert chunks[-1].finished
    assert engine.stream_kwargs["skip_cache_store"] is True
    assert engine.stream_kwargs["flesh_session_id"] == "s1"


@pytest.mark.asyncio
async def test_omlx_generator_session_kv_stores_pass_candidate():
    engine = FakeOMLXEngine()
    req = replace(
        fusion_request(),
        sampling={"flesh_kv_policy": "session"},
    )
    backend = OMLXGeneratorBackend(engine)
    turn = await backend.begin_turn(req)

    _ = [chunk async for chunk in turn.stream_draft()]
    await turn.commit_draft()

    assert engine.stream_kwargs["skip_cache_store"] is False
    assert engine.stream_kwargs["flesh_kv_policy"] == "session"
    assert backend.stats()["pass_commits"] == 1


@pytest.mark.asyncio
async def test_omlx_generator_reuses_raw_pass_transcript_next_turn():
    engine = FakeOMLXEngine()
    backend = OMLXGeneratorBackend(engine)
    first_request = replace(
        fusion_request(),
        messages=[{"role": "user", "content": "first"}],
        sampling={"flesh_kv_policy": "session"},
    )
    first = await backend.begin_turn(first_request)
    _ = [chunk async for chunk in first.stream_draft()]
    first._draft_parts = ["<think>private</think>hello world"]
    await first.commit_draft()

    second_request = replace(
        fusion_request(),
        messages=[
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "hello world"},
            {"role": "user", "content": "second"},
        ],
        sampling={"flesh_kv_policy": "session"},
    )
    second = await backend.begin_turn(second_request)

    assert second.request.messages == [
        {"role": "user", "content": "first"},
        {
            "role": "assistant",
            "content": "<think>private</think>hello world",
        },
        {"role": "user", "content": "second"},
    ]
    assert second._covered_conversation == second_request.messages


@pytest.mark.asyncio
async def test_omlx_generator_changed_final_compacts_reasoning_next_turn():
    engine = FakeOMLXEngine()
    backend = OMLXGeneratorBackend(engine)
    first = await backend.begin_turn(
        replace(fusion_request(), sampling={"flesh_kv_policy": "session"})
    )
    await first.commit_final("corrected")
    second_request = replace(
        fusion_request(),
        messages=[
            {"role": "user", "content": "first"},
            {
                "role": "assistant",
                "content": "<think>private trace</think>canonical answer",
                "reasoning_content": "private trace",
            },
            {"role": "user", "content": "second"},
        ],
        sampling={"flesh_kv_policy": "session"},
    )

    second = await backend.begin_turn(second_request)

    assert second.request.messages[1] == {
        "role": "assistant",
        "content": "canonical answer",
    }
    assert backend.stats()["compact_rebases"] == 1


@pytest.mark.asyncio
async def test_omlx_generator_does_not_receive_reviewer_cache_moe_policy():
    engine = FakeOMLXEngine()
    req = FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="s1",
        sampling={
            "flesh_l1_mode": "off",
            "fusion_reviewer_l1_mode": "auto",
            "fusion_reviewer_boost_mode": "blast",
            "fusion_reviewer_prefill_boost_mode": "blast",
            "fusion_reviewer_decode_boost_mode": "natural",
        },
    )
    turn = await OMLXGeneratorBackend(engine).begin_turn(req)

    _ = [chunk async for chunk in turn.stream_draft()]

    assert engine.stream_kwargs["flesh_l1_mode"] == "off"
    assert "fusion_reviewer_l1_mode" not in engine.stream_kwargs
    assert "fusion_reviewer_boost_mode" not in engine.stream_kwargs
    assert "fusion_reviewer_prefill_boost_mode" not in engine.stream_kwargs
    assert "fusion_reviewer_decode_boost_mode" not in engine.stream_kwargs


@pytest.mark.asyncio
async def test_omlx_generator_buffers_and_normalizes_native_tool_call():
    class ToolEngine(FakeOMLXEngine):
        async def stream_chat(self, messages, **kwargs):
            self.stream_kwargs = kwargs
            yield FakeOutput(new_text="provisional markup", completion_tokens=2)
            yield FakeOutput(
                completion_tokens=3,
                finished=True,
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "lookup",
                        "arguments": {"query": "weather"},
                    }
                ],
            )

    req = FusionRequest(
        messages=[{"role": "user", "content": "weather"}],
        session_id="tool-session",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )
    engine = ToolEngine()
    turn = await OMLXGeneratorBackend(engine).begin_turn(req)

    chunks = [chunk async for chunk in turn.stream_draft()]

    assert chunks[-1].tool_calls == (
        FusionToolCall("call_1", "lookup", '{"query":"weather"}'),
    )
    assert engine.stream_kwargs["tools"] == list(req.tools)


@pytest.mark.asyncio
async def test_omlx_generator_checkpoint_uses_partial_continuation():
    engine = FakeCheckpointOMLXEngine()
    req = FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="s1",
        max_tokens=10,
        stream_mode=StreamMode.FINAL,
        metadata={
            "mid_generation_review_enabled": True,
            "mid_generation_checkpoint_tokens": 4,
        },
    )
    turn = await OMLXGeneratorBackend(engine).begin_turn(req)

    initial = [chunk async for chunk in turn.stream_draft()]
    assert initial[-1].checkpoint
    assert not initial[-1].finished
    assert engine.stream_calls[0][1]["max_tokens"] == 4
    assert engine.stream_calls[0][1]["skip_cache_store"] is False

    from ai2apps.fusion.types import CheckpointDecision

    resumed = [
        chunk
        async for chunk in turn.resume_from_checkpoint(
            "first ", CheckpointDecision(CheckpointAction.CONTINUE)
        )
    ]
    assert "".join(chunk.text for chunk in resumed) == "finish"
    messages, kwargs = engine.stream_calls[1]
    assert messages[-1] == {"role": "assistant", "content": "first "}
    assert kwargs["is_partial"] is True
    assert kwargs["max_tokens"] == 6
    assert resumed[-1].token_count == 6


@pytest.mark.asyncio
async def test_omlx_generator_thinking_audit_handles_split_marker_and_dedupes():
    engine = FakeThinkingOMLXEngine()
    req = FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="s1",
        max_tokens=20,
        stream_mode=StreamMode.FINAL,
        metadata={
            "mid_generation_review_enabled": True,
            "mid_generation_checkpoint_tokens": 10,
            "thinking_audit_enabled": True,
            "thinking_audit_min_tokens": 2,
            "thinking_audit_max_tokens": 4,
        },
    )
    turn = await OMLXGeneratorBackend(engine).begin_turn(req)

    initial = [chunk async for chunk in turn.stream_draft()]

    assert "".join(chunk.text for chunk in initial) == "<think> first step."
    assert initial[-1].checkpoint
    assert initial[-1].checkpoint_reason == "thinking"
    assert initial[-1].signals.extra["thinking_tokens"] == 2
    assert engine.stream_calls[0][1]["max_tokens"] == 10

    from ai2apps.fusion.types import CheckpointDecision

    resumed = [
        chunk
        async for chunk in turn.resume_from_checkpoint(
            "<think> first step.",
            CheckpointDecision(CheckpointAction.CONTINUE),
        )
    ]
    assert "".join(chunk.text for chunk in resumed) == (" continue</think>\nanswer")
    assert len(engine.stream_calls) == 2


@pytest.mark.asyncio
async def test_omlx_generator_reasoning_handoff_is_hidden_rebuild():
    engine = FakeCheckpointOMLXEngine()
    req = FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="s1",
        max_tokens=10,
        stream_mode=StreamMode.FINAL,
        metadata={
            "mid_generation_review_enabled": True,
            "mid_generation_checkpoint_tokens": 4,
        },
    )
    turn = await OMLXGeneratorBackend(engine).begin_turn(req)
    initial = [chunk async for chunk in turn.stream_draft()]
    assert initial[-1].checkpoint

    from ai2apps.fusion.types import CheckpointDecision

    decision = CheckpointDecision(
        CheckpointAction.REASONING_HANDOFF,
        reasoning_seed="verify the invariant",
        constraints=("keep the input fixed",),
    )
    rebuilt = [chunk async for chunk in turn.resume_from_checkpoint("first ", decision)]

    messages, kwargs = engine.stream_calls[1]
    assert kwargs["max_tokens"] == 10
    assert "is_partial" not in kwargs
    assert "verify the invariant" in messages[0]["content"]
    assert "keep the input fixed" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "hello"}
    assert "".join(chunk.text for chunk in rebuilt) == "first "


@pytest.mark.asyncio
async def test_omlx_reviewer_uses_short_structured_protocol():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(engine, max_tokens=123)

    decision = await reviewer.review(fusion_request(), "draft", "hash", object())

    assert decision.action == ReviewAction.PASS
    assert engine.chat_kwargs[0][1]["max_tokens"] == 123
    assert engine.chat_kwargs[0][1]["temperature"] == 0.0


def test_final_reviewer_strips_current_and_historical_private_reasoning():
    messages = [
        {"role": "user", "content": "question"},
        {
            "role": "assistant",
            "content": "<think>old private</think>old answer",
            "reasoning_content": "old private field",
        },
        {"role": "user", "content": "follow-up"},
    ]

    review_messages = build_review_messages(
        messages,
        "new private</think>new answer",
        "raw-draft-hash",
    )
    payload = review_messages[1]["content"]

    assert "old private" not in payload
    assert "new private" not in payload
    assert "old answer" in payload
    assert "new answer" in payload
    assert "raw-draft-hash" not in payload
    assert "draft_sha256" not in payload


def test_checkpoint_reviewer_keeps_reasoning_direction_context():
    checkpoint = build_checkpoint_review_messages(
        [{"role": "user", "content": "question"}],
        "private direction</think>partial answer",
        "hash",
    )
    assert "private direction" in checkpoint[1]["content"]
    assert '"draft_sha256"' not in checkpoint[1]["content"]


def test_tool_reviewer_strips_private_reasoning():
    messages = [
        {
            "role": "assistant",
            "content": "<think>history secret</think>visible history",
            "reasoning_content": "secret field",
        }
    ]
    tool_messages = build_tool_review_messages(
        messages,
        [],
        "candidate secret</think>visible candidate",
        [],
        [],
    )
    payload = tool_messages[1]["content"]
    assert "secret" not in payload
    assert "visible history" in payload
    assert "visible candidate" in payload


@pytest.mark.asyncio
async def test_omlx_reviewer_defaults_leave_room_for_public_decision():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(engine)

    await reviewer.review(fusion_request(), "draft", "hash", object())
    final_kwargs = engine.chat_kwargs[0][1]
    assert final_kwargs["max_tokens"] == 8192
    assert final_kwargs["thinking_budget"] is None

    engine.chat_text = '{"action":"CONTINUE","risk":"low"}'
    await reviewer.review_checkpoint(fusion_request(), "draft", "hash", object())
    checkpoint_kwargs = engine.chat_kwargs[1][1]
    assert checkpoint_kwargs["max_tokens"] == 256
    assert checkpoint_kwargs["thinking_budget"] == 128


@pytest.mark.asyncio
async def test_omlx_reviewer_does_not_force_decision_from_incomplete_analysis():
    class DecisionRetryEngine(FakeOMLXEngine):
        async def stream_chat(self, messages, **kwargs):
            self.chat_kwargs.append((messages, kwargs))
            yield FakeOutput(
                new_text="analysis that never produced JSON",
                completion_tokens=4096,
                finish_reason="length",
                finished=True,
            )

    engine = DecisionRetryEngine()
    reviewer = OMLXReviewerBackend(engine)

    with pytest.raises(OMLXReviewerBackend.OutputError):
        await reviewer.review(fusion_request(), "draft", "hash", object())

    assert len(engine.chat_kwargs) == 1


@pytest.mark.asyncio
async def test_omlx_reviewer_retries_json_after_completed_analysis_drift():
    class DecisionRetryEngine(FakeOMLXEngine):
        async def stream_chat(self, messages, **kwargs):
            self.chat_kwargs.append((messages, kwargs))
            text = (
                "completed audit</think>public prose"
                if len(self.chat_kwargs) == 1
                else '{"action":"PASS","risk":"low"}'
            )
            yield FakeOutput(new_text=text, completion_tokens=12, finished=True)

    engine = DecisionRetryEngine()
    reviewer = OMLXReviewerBackend(engine)

    decision = await reviewer.review(fusion_request(), "draft", "hash", object())

    assert decision.action == ReviewAction.PASS
    retry_messages, retry_kwargs = engine.chat_kwargs[1]
    assert retry_messages[-2]["content"] == "completed audit</think>public prose"
    assert "Do not analyze again" in retry_messages[-1]["content"]
    assert retry_kwargs["max_tokens"] == 384
    assert retry_kwargs["thinking_budget"] == 0
    assert retry_kwargs["chat_template_kwargs"]["enable_thinking"] is False
    assert decision.metadata["reviewer_transcript"]["decision_retry"] is True


@pytest.mark.asyncio
async def test_omlx_reviewer_stops_public_analysis_at_forced_think_boundary():
    class BoundaryDriftEngine(FakeOMLXEngine):
        def __init__(self):
            super().__init__()
            self.calls = 0
            self.primary_chunks = 0

        async def stream_chat(self, messages, **kwargs):
            self.calls += 1
            self.chat_kwargs.append((messages, kwargs))
            if self.calls == 1:
                for index, text in enumerate(
                    ("brief analysis</think>", "continued prose", "never reached"),
                    start=1,
                ):
                    self.primary_chunks += 1
                    yield FakeOutput(new_text=text, completion_tokens=index)
                return
            yield FakeOutput(
                new_text='{"action":"PATCH","risk":"medium",'
                '"patches":[{"before":"bad","after":"good"}]}',
                completion_tokens=20,
            )

    engine = BoundaryDriftEngine()
    reviewer = OMLXReviewerBackend(engine)

    decision = await reviewer.review(fusion_request(), "bad", "hash", object())

    assert decision.action == ReviewAction.PATCH
    assert engine.primary_chunks == 2
    transcript = decision.metadata["reviewer_transcript"]
    assert transcript["decision_retry"] is True
    assert transcript["initial_output"].endswith("continued prose")


@pytest.mark.asyncio
async def test_omlx_reviewer_constrains_post_think_channel_to_json():
    class FakeCompiler:
        def __init__(self):
            self.structural_tag = None

        def compile_structural_tag(self, tag):
            self.structural_tag = tag
            return "compiled-think-then-json"

    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    engine.model_type = "deepseek_v4"
    engine.grammar_compiler = FakeCompiler()
    reviewer = OMLXReviewerBackend(engine)

    decision = await reviewer.review(fusion_request(), "draft", "hash", object())

    assert decision.action == ReviewAction.PASS
    assert engine.chat_kwargs[0][1]["compiled_grammar"] == (
        "compiled-think-then-json"
    )
    public_format = engine.grammar_compiler.structural_tag["format"]["elements"][-1]
    assert public_format == {"type": "json_schema", "json_schema": {}}


@pytest.mark.asyncio
async def test_omlx_reviewer_reports_prefill_and_token_progress():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(engine)
    progress = []

    decision = await reviewer.review_with_progress(
        fusion_request(), "draft", "hash", object(), progress.append
    )

    assert decision.action == ReviewAction.PASS
    assert progress[0]["stage"] == "prefill"
    assert progress[0]["prompt_messages"][0]["role"] == "system"
    assert "Return one JSON object" in progress[0]["prompt_messages"][0]["content"]
    assert progress[0]["prompt_messages"][1]["role"] == "user"
    assert '"type":"review_target"' in progress[0]["prompt_messages"][1]["content"]
    assert '"draft":"draft"' in progress[0]["prompt_messages"][1]["content"]
    assert progress[-1]["stage"] == "generating"
    assert progress[-1]["delta"] == '{"action":"PASS","risk":"low"}'
    request_id = engine.chat_kwargs[0][1]["request_id"]
    assert request_id.startswith("fusion-review-")


@pytest.mark.asyncio
async def test_omlx_reviewer_timeout_resets_when_tokens_keep_arriving():
    class ProgressEngine:
        async def stream_chat(self, messages, **kwargs):
            chunks = ('{"action":', '"PASS",', '"risk":"low"}')
            for index, chunk in enumerate(chunks, start=1):
                await asyncio.sleep(0.06)
                yield FakeOutput(new_text=chunk, completion_tokens=index)

    reviewer = OMLXReviewerBackend(ProgressEngine(), inactivity_timeout_seconds=0.1)

    decision = await reviewer.review(fusion_request(), "draft", "hash", object())

    assert decision.action == ReviewAction.PASS


@pytest.mark.asyncio
async def test_omlx_reviewer_times_out_after_token_progress_stalls():
    class StalledEngine:
        async def stream_chat(self, messages, **kwargs):
            yield FakeOutput(new_text='{"action":', completion_tokens=1)
            await asyncio.sleep(0.2)
            yield FakeOutput(new_text='"PASS"}', completion_tokens=2)

    reviewer = OMLXReviewerBackend(StalledEngine(), inactivity_timeout_seconds=0.05)

    with pytest.raises(TimeoutError, match="no token progress"):
        await reviewer.review(fusion_request(), "draft", "hash", object())


@pytest.mark.asyncio
async def test_omlx_reviewer_uses_its_own_cache_moe_policy():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(
        engine,
        cache_moe_defaults={"l1_mode": "off", "engine_boost": "blast"},
    )

    await reviewer.review(fusion_request(), "draft", "hash", object())

    kwargs = engine.chat_kwargs[0][1]
    assert kwargs["flesh_l1_mode"] == "off"
    assert kwargs["flesh_prefill_boost_mode"] == "blast"
    assert kwargs["flesh_decode_boost_mode"] == "blast"
    assert kwargs["flesh_kv_policy"] == "session"
    assert kwargs["skip_cache_store"] is False
    assert kwargs["cache_exact_system_prefix"] is True


@pytest.mark.asyncio
async def test_omlx_reviewer_appends_jsonl_after_pass_for_session_kv():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(engine)
    first = fusion_request()

    await reviewer.review(first, "answer one", "hash-1", object())
    second = replace(
        first,
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "answer one"},
            {"role": "user", "content": "follow-up"},
        ],
    )
    await reviewer.review(second, "answer two", "hash-2", object())

    first_messages, first_kwargs = engine.chat_kwargs[0]
    second_messages, second_kwargs = engine.chat_kwargs[1]
    assert [message["role"] for message in second_messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert second_messages[:2] == first_messages
    assert second_messages[2]["content"] == '{"action":"PASS","risk":"low"}'
    delta = second_messages[3]["content"]
    assert "follow-up" in delta
    assert "answer two" in delta
    assert '"content":"hello"' not in delta
    assert '"content":"answer one"' not in delta
    assert first_kwargs["flesh_session_id"] == second_kwargs["flesh_session_id"]
    assert second_kwargs["flesh_kv_policy"] == "session"


@pytest.mark.asyncio
async def test_omlx_reviewer_rolls_back_speculative_non_pass_to_last_checkpoint():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(engine)
    first = fusion_request()

    await reviewer.review(first, "answer one", "hash-1", object())
    engine.chat_text = (
        '{"action":"REVISE","risk":"medium","instructions":["fix it"]}'
    )
    second = replace(
        first,
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "answer one"},
            {"role": "user", "content": "question two"},
        ],
    )
    await reviewer.review(second, "bad answer two", "hash-2", object())
    engine.chat_text = '{"action":"PASS","risk":"low"}'
    third = replace(
        first,
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "answer one"},
            {"role": "user", "content": "question two"},
            {"role": "assistant", "content": "fixed answer two"},
            {"role": "user", "content": "question three"},
        ],
    )
    await reviewer.review(third, "answer three", "hash-3", object())

    second_messages, second_kwargs = engine.chat_kwargs[1]
    third_messages, third_kwargs = engine.chat_kwargs[2]
    assert second_messages[:3] == third_messages[:3]
    assert "bad answer two" in second_messages[3]["content"]
    assert "bad answer two" not in third_messages[3]["content"]
    assert "fixed answer two" in third_messages[3]["content"]
    assert "question three" in third_messages[3]["content"]
    assert second_kwargs["cache_exact_message_prefix_count"] == 3
    assert third_kwargs["cache_exact_message_prefix_count"] == 3
    assert second_kwargs["flesh_session_id"] == third_kwargs["flesh_session_id"]


@pytest.mark.asyncio
async def test_omlx_reviewer_splits_prefill_and_decode_boost():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(
        engine,
        cache_moe_defaults={
            "l1_mode": "auto",
            "prefill_boost": "blast",
            "decode_boost": "natural",
        },
    )

    await reviewer.review(fusion_request(), "draft", "hash", object())

    kwargs = engine.chat_kwargs[0][1]
    assert kwargs["flesh_prefill_boost_mode"] == "blast"
    assert kwargs["flesh_decode_boost_mode"] == "natural"


@pytest.mark.asyncio
async def test_omlx_tool_reviewer_never_receives_executable_tools():
    engine = FakeOMLXEngine('{"action":"PASS"}')
    reviewer = OMLXReviewerBackend(engine, checkpoint_max_tokens=91)
    req = FusionRequest(
        messages=[{"role": "user", "content": "weather"}],
        session_id="s1",
        tools=[
            {
                "type": "function",
                "function": {"name": "lookup", "parameters": {"type": "object"}},
            }
        ],
    )

    decision = await reviewer.review_tool_calls(
        req,
        "",
        (FusionToolCall("call_1", "lookup", "{}"),),
        (),
    )

    assert decision.action == ToolReviewAction.PASS
    messages, kwargs = engine.chat_kwargs[0]
    assert kwargs["max_tokens"] == 91
    assert "tools" not in kwargs
    assert "candidate_tool_calls" in messages[1]["content"]


@pytest.mark.asyncio
async def test_omlx_checkpoint_reviewer_uses_direction_protocol():
    engine = FakeOMLXEngine('{"action":"REDIRECT","guidance":["fix the premise"]}')
    reviewer = OMLXReviewerBackend(engine, checkpoint_max_tokens=77)

    decision = await reviewer.review_checkpoint(
        fusion_request(), "draft", "hash", object()
    )

    assert decision.action == CheckpointAction.REDIRECT
    assert decision.guidance == ("fix the premise",)
    assert engine.chat_kwargs[0][1]["max_tokens"] == 77


@pytest.mark.asyncio
async def test_omlx_checkpoint_reviewer_enables_handoff_explicitly():
    engine = FakeOMLXEngine(
        '{"action":"REASONING_HANDOFF","reasoning_seed":"check premise"}'
    )
    reviewer = OMLXReviewerBackend(engine)
    req = FusionRequest(
        messages=[{"role": "user", "content": "hello"}],
        session_id="s1",
        metadata={
            "reviewer_guidance_mode": "reasoning_handoff",
            "reasoning_handoff_max_tokens": 99,
        },
    )

    decision = await reviewer.review_checkpoint(req, "draft", "hash", object())

    assert decision.action == CheckpointAction.REASONING_HANDOFF
    system = engine.chat_kwargs[0][0][0]["content"]
    assert "enabled for this request" in system
    assert "99 tokens" in system


class FakeHTTPResponse:
    status_code = 200
    is_error = False

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": '{"action":"PASS"}'}}]}


class FakeHTTPClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeHTTPResponse()


@pytest.mark.asyncio
async def test_remote_backend_uses_openai_compatible_endpoint_and_key():
    client = FakeHTTPClient()
    backend = OpenAICompatibleReviewBackend(
        base_url="https://provider.test/v1",
        model="reviewer",
        api_key="secret",
        client=client,
    )

    decision = await backend.review(fusion_request(), "draft", "hash", object())

    assert decision.action == ReviewAction.PASS
    url, kwargs = client.calls[0]
    assert url == "https://provider.test/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_remote_backend_retries_modern_gpt5_chat_fields_after_400():
    class BadRequest:
        status_code = 400
        is_error = True

        def json(self):
            return {"error": {"message": "max_tokens is not supported"}}

    class ModernClient(FakeHTTPClient):
        async def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return BadRequest() if len(self.calls) == 1 else FakeHTTPResponse()

    client = ModernClient()
    backend = OpenAICompatibleReviewBackend(
        base_url="https://provider.test/v1",
        model="gpt-5.6-terra",
        api_key="secret",
        max_tokens=321,
        client=client,
    )

    decision = await backend.review(fusion_request(), "draft", "hash", object())

    assert decision.action == ReviewAction.PASS
    assert len(client.calls) == 2
    modern = client.calls[1][1]["json"]
    assert modern["max_completion_tokens"] == 321
    assert "max_tokens" not in modern
    assert "temperature" not in modern


@pytest.mark.asyncio
async def test_external_review_returns_exact_prompt_and_raw_response():
    client = FakeHTTPClient()
    backend = OpenAICompatibleReviewBackend(
        base_url="https://provider.test/v1",
        model="reviewer",
        api_key="secret",
        client=client,
    )

    answer, action, usage, prompt, response, explanation = (
        await backend.review_and_repair(
        fusion_request(), "draft"
    )
    )

    assert answer == "draft"
    assert action == "pass"
    assert usage == {}
    assert prompt == client.calls[0][1]["json"]["messages"]
    assert prompt[0]["role"] == "system"
    assert prompt[1]["role"] == "user"
    assert response == '{"action":"PASS"}'
    assert explanation == ""


@pytest.mark.asyncio
async def test_external_replace_requires_and_returns_explanation():
    class ReplaceResponse(FakeHTTPResponse):
        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"action":"REPLACE",'
                                '"explanation":"The calculation is incorrect; 2+2 is 4.",'
                                '"answer":"4"}'
                            )
                        }
                    }
                ]
            }

    class ReplaceClient(FakeHTTPClient):
        async def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return ReplaceResponse()

    backend = OpenAICompatibleReviewBackend(
        base_url="https://provider.test/v1",
        model="reviewer",
        api_key="secret",
        client=ReplaceClient(),
    )

    answer, action, _, _, _, explanation = await backend.review_and_repair(
        fusion_request(), "5"
    )

    assert answer == "4"
    assert action == "replace"
    assert explanation == "The calculation is incorrect; 2+2 is 4."


@pytest.mark.asyncio
async def test_external_review_prompt_excludes_private_thinking():
    client = FakeHTTPClient()
    backend = OpenAICompatibleReviewBackend(
        base_url="https://provider.test/v1",
        model="reviewer",
        api_key="secret",
        client=client,
    )
    request = fusion_request()
    request = replace(
        request,
        messages=[
            {"role": "user", "content": "question"},
            {
                "role": "assistant",
                "content": "<think>private history</think>visible history",
                "thinking": "private field",
            },
        ],
    )

    answer, action, _, prompt, _, _ = await backend.review_and_repair(
        request,
        "<think>private draft</think>visible draft",
    )

    payload = json.loads(prompt[1]["content"])
    assert action == "pass"
    assert answer == "<think>private draft</think>visible draft"
    assert payload["conversation"][1] == {
        "role": "assistant",
        "content": "visible history",
    }
    assert payload["answer"] == "visible draft"
    assert "private" not in prompt[1]["content"]


def test_stream_mode_request_validation_is_exposed():
    from pydantic import ValidationError

    from omlx.api.openai_models import ChatCompletionRequest

    parsed = ChatCompletionRequest(
        model="fusion", messages=[], ai2apps_stream_mode="draft"
    )
    assert parsed.ai2apps_stream_mode == "draft"
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="fusion", messages=[], ai2apps_stream_mode="invalid"
        )


def test_chat_request_validates_fusion_review_overrides():
    from pydantic import ValidationError

    from omlx.api.openai_models import ChatCompletionRequest

    parsed = ChatCompletionRequest(
        model="fusion",
        messages=[],
        ai2apps_fusion_gate_policy="always",
        ai2apps_fusion_mid_generation_review=True,
        ai2apps_fusion_thinking_audit=False,
        ai2apps_fusion_reviewer_guidance="reasoning_handoff",
        ai2apps_fusion_checkpoint_tokens=768,
        ai2apps_fusion_generator_l1_mode="off",
        ai2apps_fusion_generator_engine_boost="turbo",
        ai2apps_fusion_reviewer_l1_mode="auto",
        ai2apps_fusion_reviewer_engine_boost="blast",
    )
    assert parsed.ai2apps_fusion_checkpoint_tokens == 768
    assert parsed.ai2apps_fusion_reviewer_engine_boost == "blast"
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="fusion", messages=[], ai2apps_fusion_gate_policy="sometimes"
        )
