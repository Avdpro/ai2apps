# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from ai2apps.model_worker import (
    ModelWorkerCheckpoint,
    ModelWorkerContext,
    ModelWorkerRequest,
    ModelWorkerStream,
    OmlxChatAdapter,
)


@dataclass
class _Output:
    text: str = "hello"
    new_text: str = ""
    finish_reason: str = "stop"
    prompt_tokens: int = 2
    completion_tokens: int = 1
    cached_tokens: int = 0
    prompt_tps: float = 120.5
    generation_tps: float = 42.5
    generated_at: float | None = None
    generated_until: float | None = None
    tool_calls: list | None = None


class _Engine:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.stream_closed = False
        self.chat_kwargs = None
        self.stream_kwargs = None

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def chat(self, messages, **kwargs):
        self.chat_kwargs = kwargs
        return _Output()

    async def stream_chat(self, messages, **kwargs):
        self.stream_kwargs = kwargs
        try:
            yield _Output(
                text="he", new_text="he", finish_reason="length",
                completion_tokens=1, generated_at=10.0, generated_until=10.0,
            )
            yield _Output(
                text="hello", new_text="llo", finish_reason="stop",
                completion_tokens=3, generated_at=10.1, generated_until=10.1,
            )
        finally:
            self.stream_closed = True

    def get_stats(self):
        return {
            "engine_boost": {
                "available": True,
                "mode": "blast",
                "cache_hit_rate": 0.75,
            }
        }

    def get_live_metrics(self, session_id=None):
        return {
            "ssd_recent_10_tokens": {
                "tokens": 10,
                "pressure_percent": 12.5,
                "expert_loads": 3,
            },
            "ssd_turn_average": {
                "tokens": 3,
                "pressure_percent": 8.0,
                "expert_loads": 4,
            },
        }


class _Adapter(OmlxChatAdapter):
    def __init__(self, context):
        super().__init__(context)
        self.created: list[_Engine] = []

    async def create_engine(self, checkpoint, runtime_options=None):
        engine = _Engine()
        self.created.append(engine)
        return engine


def _context(tmp_path, *, reasoning=None, context_window=None):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    checkpoints = tuple(
        ModelWorkerCheckpoint(
            model_id=f"example.worker/{name}",
            upstream_id=f"upstream-{name}",
            provider="huggingface",
            repo_id=f"example/{name}",
            revision=revision * 40,
            path=path,
            preparation={"recipe": "native"},
        )
        for name, revision, path in (("first", "a", first), ("second", "b", second))
    )
    first_model = {
        "id": "example.worker/first",
        "upstream_id": "upstream-first",
        "metadata": {"reasoning": reasoning} if reasoning is not None else {},
    }
    if context_window is not None:
        first_model["context_window"] = context_window
    models = (first_model,)
    return ModelWorkerContext(
        service_id="example.worker",
        package_root=tmp_path,
        data_root=tmp_path,
        models=models,
        checkpoints=checkpoints,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "payload", "kwargs_attr"),
    (
        (
            "chat_completions",
            {"model": "upstream-first", "messages": [{"role": "user", "content": "hi"}]},
            "chat_kwargs",
        ),
        (
            "chat_completions",
            {
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            "stream_kwargs",
        ),
        ("responses", {"model": "upstream-first", "input": "hi"}, "chat_kwargs"),
        (
            "responses",
            {"model": "upstream-first", "input": "hi", "stream": True},
            "stream_kwargs",
        ),
    ),
)
async def test_omlx_adapter_passes_package_context_window_to_every_generation_path(
    tmp_path, operation, payload, kwargs_attr
):
    adapter = _Adapter(_context(tmp_path, context_window=131072))
    result = await adapter.invoke(
        ModelWorkerRequest(operation=operation, payload=payload, request_id="context")
    )
    if isinstance(result, ModelWorkerStream):
        _ = b"".join([chunk async for chunk in result.chunks])
    assert getattr(adapter.created[0], kwargs_attr)["max_context_window"] == 131072


@pytest.mark.asyncio
async def test_omlx_adapter_defaults_legacy_chat_package_context_to_32768(tmp_path):
    adapter = _Adapter(_context(tmp_path))
    await adapter.invoke(
        ModelWorkerRequest(
            operation="chat_completions",
            payload={
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
            },
            request_id="legacy-context",
        )
    )
    assert adapter.created[0].chat_kwargs["max_context_window"] == 32768


class _RequiredReasoningEngine(_Engine):
    def __init__(self) -> None:
        super().__init__()
        self.chat_kwargs = None
        self.stream_kwargs = None

    async def chat(self, messages, **kwargs):
        self.chat_kwargs = kwargs
        return _Output(text="private reasoning</think>visible answer")

    async def stream_chat(self, messages, **kwargs):
        self.stream_kwargs = kwargs
        for text in ("private ", "reasoning</thi", "nk>visible answer"):
            yield _Output(new_text=text)


class _RequiredReasoningAdapter(_Adapter):
    async def create_engine(self, checkpoint, runtime_options=None):
        engine = _RequiredReasoningEngine()
        self.created.append(engine)
        return engine


@pytest.mark.asyncio
async def test_omlx_adapter_json_lifecycle_and_model_switch(tmp_path):
    adapter = _Adapter(_context(tmp_path))
    request = ModelWorkerRequest(
        operation="chat_completions",
        payload={
            "model": "upstream-first",
            "messages": [{"role": "user", "content": "hi"}],
        },
        request_id="one",
    )

    response = await adapter.invoke(request)
    assert response["id"] == "chatcmpl-one"
    assert response["choices"][0]["message"]["content"] == "hello"
    assert response["usage"]["total_tokens"] == 3
    assert adapter.created[0].started is True

    await adapter.invoke(
        ModelWorkerRequest(
            operation="chat_completions",
            payload={
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
                "_ai2apps_model_settings": {"moe_execution_mode": "full"},
            },
            request_id="mode-switch",
        )
    )
    assert adapter.created[0].stopped is True
    assert len(adapter.created) == 2

    await adapter.invoke(
        ModelWorkerRequest(
            operation="responses",
            payload={"model": "upstream-second", "input": "hi"},
            request_id="two",
        )
    )
    assert adapter.created[1].stopped is True
    assert len(adapter.created) == 3

    await adapter.stop()
    assert adapter.created[2].stopped is True


@pytest.mark.asyncio
async def test_omlx_adapter_chat_and_responses_sse(tmp_path):
    adapter = _Adapter(_context(tmp_path))
    for operation, payload, expected in (
        (
            "chat_completions",
            {
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            "chat.completion.chunk",
        ),
        (
            "responses",
            {"model": "upstream-first", "input": "hi", "stream": True},
            "response.output_text.delta",
        ),
    ):
        result = await adapter.invoke(
            ModelWorkerRequest(operation=operation, payload=payload, request_id="stream")
        )
        assert isinstance(result, ModelWorkerStream)
        content = b"".join([chunk async for chunk in result.chunks])
        assert expected.encode() in content
        assert content.endswith(b"data: [DONE]\n\n")
        if operation == "chat_completions":
            events = [json.loads(event.removeprefix(b"data: ")) for event in content.split(b"\n\n")
                      if event.startswith(b"data: {")]
            assert events[-1]["usage"]["prompt_tokens_per_second"] == 120.5
            assert events[-1]["usage"]["generation_tokens_per_second"] == 42.5
            assert events[-1]["usage"]["ai2apps_engine_boost"] == {
                "available": True,
                "mode": "blast",
                "cache_hit_rate": 0.75,
            }
            live_metrics = [
                event["ai2apps_metrics"] for event in events
                if "ai2apps_metrics" in event
            ]
            assert [item["completion_tokens"] for item in live_metrics] == [1, 3]
            assert [item["generation_sample_time"] for item in live_metrics] == [10.0, 10.1]
            assert all(item["prompt_tokens"] == 2 for item in live_metrics)
            assert all(item["prefill_tokens_per_second"] == 120.5 for item in live_metrics)
            assert all(item["prefill_timing_source"] == "engine_native" for item in live_metrics)
            assert all(item["ssd_recent_10_tokens"]["tokens"] == 10 for item in live_metrics)
            assert all(item["ssd_turn_average"]["tokens"] == 3 for item in live_metrics)
        for event in content.split(b"\n\n"):
            if event.startswith(b"data: {"):
                json.loads(event.removeprefix(b"data: "))


@pytest.mark.asyncio
async def test_worker_boost_controls_loaded_engine_without_loading_another(tmp_path):
    from ai2apps.model_worker.protocol import ModelWorkerError
    adapter = _Adapter(_context(tmp_path))
    with pytest.raises(ModelWorkerError):
        adapter.request_engine_boost('upstream-first', 'session', 'blast')
    engine, checkpoint = await adapter.engine_for('upstream-first')
    calls = []
    engine.request_engine_boost = lambda session, mode: calls.append((session, mode)) or {'accepted': True}
    assert adapter.request_engine_boost(checkpoint.model_id, 'session', 'blast')['accepted']
    assert calls == [('session', 'blast')]
    with pytest.raises(ModelWorkerError):
        adapter.request_engine_boost('wrong-model', 'session', 'blast')
    assert len(adapter.created) == 1
    await adapter.stop()


@pytest.mark.asyncio
async def test_required_reasoning_overrides_off_and_structures_non_stream_output(
    tmp_path,
):
    contract = {
        "schema": "ai2apps.reasoning/v1",
        "mode": "required",
        "format": "think_tags",
        "default_enabled": True,
    }
    adapter = _RequiredReasoningAdapter(_context(tmp_path, reasoning=contract))
    response = await adapter.invoke(
        ModelWorkerRequest(
            operation="chat_completions",
            payload={
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
                "chat_template_kwargs": {"enable_thinking": False},
            },
            request_id="reasoning-json",
        )
    )

    message = response["choices"][0]["message"]
    assert message["reasoning_content"] == "private reasoning"
    assert message["content"] == "visible answer"
    assert adapter.created[0].chat_kwargs["chat_template_kwargs"] == {
        "enable_thinking": True
    }


@pytest.mark.asyncio
async def test_required_reasoning_stream_starts_inside_thinking_without_open_tag(
    tmp_path,
):
    contract = {
        "schema": "ai2apps.reasoning/v1",
        "mode": "required",
        "format": "think_tags",
        "default_enabled": True,
    }
    adapter = _RequiredReasoningAdapter(_context(tmp_path, reasoning=contract))
    result = await adapter.invoke(
        ModelWorkerRequest(
            operation="chat_completions",
            payload={
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            request_id="reasoning-stream",
        )
    )
    events = [
        json.loads(event.removeprefix(b"data: "))
        for event in b"".join([chunk async for chunk in result.chunks]).split(b"\n\n")
        if event.startswith(b"data: {")
    ]
    deltas = [choice["delta"] for event in events for choice in event.get("choices", [])]

    assert "".join(delta.get("reasoning_content", "") for delta in deltas) == (
        "private reasoning"
    )
    assert "".join(delta.get("content", "") for delta in deltas) == "visible answer"
    assert adapter.created[0].stream_kwargs["chat_template_kwargs"] == {
        "enable_thinking": True
    }


@pytest.mark.asyncio
async def test_optional_reasoning_default_on_stream_starts_inside_thinking(tmp_path):
    contract = {
        "schema": "ai2apps.reasoning/v1",
        "mode": "optional",
        "format": "think_tags",
        "default_enabled": True,
    }
    adapter = _RequiredReasoningAdapter(_context(tmp_path, reasoning=contract))
    result = await adapter.invoke(
        ModelWorkerRequest(
            operation="chat_completions",
            payload={
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            request_id="optional-reasoning-stream",
        )
    )
    events = [
        json.loads(event.removeprefix(b"data: "))
        for event in b"".join([chunk async for chunk in result.chunks]).split(b"\n\n")
        if event.startswith(b"data: {")
    ]
    deltas = [choice["delta"] for event in events for choice in event.get("choices", [])]
    assert "".join(delta.get("reasoning_content", "") for delta in deltas) == (
        "private reasoning"
    )
    assert "".join(delta.get("content", "") for delta in deltas) == "visible answer"
    assert adapter.created[0].stream_kwargs["chat_template_kwargs"] == {
        "enable_thinking": True
    }


@pytest.mark.asyncio
async def test_responses_hides_reasoning_and_honors_optional_default(tmp_path):
    contract = {
        "schema": "ai2apps.reasoning/v1",
        "mode": "optional",
        "format": "think_tags",
        "default_enabled": True,
    }
    adapter = _RequiredReasoningAdapter(_context(tmp_path, reasoning=contract))
    response = await adapter.invoke(
        ModelWorkerRequest(
            operation="responses",
            payload={"model": "upstream-first", "input": "hi"},
            request_id="optional-reasoning-responses",
        )
    )
    assert response["output_text"] == "visible answer"
    assert adapter.created[0].chat_kwargs["chat_template_kwargs"] == {
        "enable_thinking": True
    }


@pytest.mark.asyncio
async def test_omlx_adapter_closes_engine_stream_when_client_cancels(tmp_path):
    adapter = _Adapter(_context(tmp_path))
    result = await adapter.invoke(
        ModelWorkerRequest(
            operation="chat_completions",
            payload={
                "model": "upstream-first",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
            request_id="cancel",
        )
    )
    stream = result.chunks
    await anext(stream)  # role chunk
    await anext(stream)  # first generated token
    await stream.aclose()

    assert adapter.created[0].stream_closed is True
