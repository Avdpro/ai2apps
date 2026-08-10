from __future__ import annotations

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
from ai2apps.fusion.serde import review_decision_from_json
from ai2apps.fusion.types import (
    FusionRequest,
    ReviewAction,
    StreamMode,
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


class FakeOutput:
    def __init__(
        self,
        *,
        text="",
        new_text="",
        completion_tokens=0,
        finish_reason="stop",
    ):
        self.text = text
        self.new_text = new_text
        self.completion_tokens = completion_tokens
        self.finish_reason = finish_reason


class FakeOMLXEngine:
    def __init__(self, chat_text='{"action":"PASS"}'):
        self.chat_text = chat_text
        self.stream_kwargs = None
        self.chat_kwargs = []

    async def stream_chat(self, messages, **kwargs):
        self.stream_kwargs = kwargs
        yield FakeOutput(new_text="hello ")
        yield FakeOutput(new_text="world", completion_tokens=2)

    async def chat(self, messages, **kwargs):
        self.chat_kwargs.append((messages, kwargs))
        return FakeOutput(text=self.chat_text, completion_tokens=4)


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
async def test_omlx_reviewer_uses_short_structured_protocol():
    engine = FakeOMLXEngine('{"action":"PASS","risk":"low"}')
    reviewer = OMLXReviewerBackend(engine, max_tokens=123)

    decision = await reviewer.review(fusion_request(), "draft", "hash", object())

    assert decision.action == ReviewAction.PASS
    assert engine.chat_kwargs[0][1]["max_tokens"] == 123
    assert engine.chat_kwargs[0][1]["temperature"] == 0.0


class FakeHTTPResponse:
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
