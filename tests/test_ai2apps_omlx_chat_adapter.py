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
    tool_calls: list | None = None


class _Engine:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.stream_closed = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def chat(self, messages, **kwargs):
        return _Output()

    async def stream_chat(self, messages, **kwargs):
        try:
            yield _Output(text="he", new_text="he", finish_reason="length")
            yield _Output(text="hello", new_text="llo", finish_reason="stop")
        finally:
            self.stream_closed = True


class _Adapter(OmlxChatAdapter):
    def __init__(self, context):
        super().__init__(context)
        self.created: list[_Engine] = []

    async def create_engine(self, checkpoint, runtime_options=None):
        engine = _Engine()
        self.created.append(engine)
        return engine


def _context(tmp_path):
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
    return ModelWorkerContext(
        service_id="example.worker",
        package_root=tmp_path,
        data_root=tmp_path,
        models=(),
        checkpoints=checkpoints,
    )


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
        for event in content.split(b"\n\n"):
            if event.startswith(b"data: {"):
                json.loads(event.removeprefix(b"data: "))


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
