import json

import pytest

from omlx.api.openai_models import ChatCompletionRequest
from omlx.engine.base import GenerationOutput
from omlx.server import stream_chat_completion


class FakeFusionTransportEngine:
    tokenizer = None

    async def stream_chat(self, messages, **kwargs):
        yield GenerationOutput(
            text="",
            finished=False,
            finish_reason=None,
            fusion_event={
                "phase": "draft",
                "channel": "reasoning",
                "text": "provisional",
                "draft_id": "draft_1",
                "metadata": {},
            },
        )
        yield GenerationOutput(
            text="",
            finished=False,
            finish_reason=None,
            fusion_event={
                "phase": "review_result",
                "channel": "control",
                "text": "",
                "draft_id": "draft_1",
                "metadata": {"action": "pass"},
            },
        )
        yield GenerationOutput(
            text="",
            finished=False,
            finish_reason=None,
            fusion_event={
                "phase": "final",
                "channel": "content",
                "text": "canonical",
                "draft_id": "draft_1",
                "metadata": {},
            },
        )
        yield GenerationOutput(
            text="canonical",
            prompt_tokens=2,
            completion_tokens=1,
            finished=True,
            finish_reason="stop",
            fusion_event={
                "phase": "done",
                "channel": "control",
                "text": "",
                "draft_id": "draft_1",
                "metadata": {"path": "pass"},
            },
        )


class FakeFusionToolTransportEngine:
    tokenizer = None

    async def stream_chat(self, messages, **kwargs):
        yield GenerationOutput(
            text="",
            finished=False,
            finish_reason=None,
            fusion_event={
                "phase": "final_begin",
                "channel": "control",
                "text": "",
                "draft_id": "draft_tool",
                "metadata": {},
            },
        )
        yield GenerationOutput(
            text="",
            completion_tokens=4,
            finished=True,
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_weather",
                    "name": "get_weather",
                    "arguments": '{"city":"Shanghai"}',
                }
            ],
            fusion_event={
                "phase": "done",
                "channel": "control",
                "text": "",
                "draft_id": "draft_tool",
                "metadata": {"path": "tool_pass"},
            },
        )


def _data_payloads(frames):
    payloads = []
    for frame in frames:
        if frame.startswith("data: {"):
            payloads.append(json.loads(frame.removeprefix("data: ").strip()))
    return payloads


@pytest.mark.asyncio
async def test_openai_stream_preserves_native_fusion_events_and_channels():
    request = ChatCompletionRequest(
        model="fusion", messages=[], stream=True, ai2apps_stream_mode="reasoning"
    )

    frames = [
        frame
        async for frame in stream_chat_completion(
            FakeFusionTransportEngine(), [], request, resolved_model="fusion"
        )
    ]
    payloads = _data_payloads(frames)
    deltas = [
        payload["choices"][0]["delta"]
        for payload in payloads
        if payload.get("choices")
    ]

    draft = next(delta for delta in deltas if delta.get("reasoning_content"))
    final = next(delta for delta in deltas if delta.get("content"))
    review = next(
        delta
        for delta in deltas
        if delta.get("ai2apps", {}).get("phase") == "review_result"
    )
    assert draft["reasoning_content"] == "provisional"
    assert draft["ai2apps"]["phase"] == "draft"
    assert final["content"] == "canonical"
    assert review["ai2apps"]["metadata"]["action"] == "pass"
    assert frames[-1] == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_openai_stream_emits_only_committed_fusion_tool_calls():
    request = ChatCompletionRequest(
        model="fusion",
        messages=[],
        stream=True,
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )

    frames = [
        frame
        async for frame in stream_chat_completion(
            FakeFusionToolTransportEngine(),
            [],
            request,
            resolved_model="fusion",
            tools=request.tools,
        )
    ]
    payloads = _data_payloads(frames)
    tool_deltas = [
        payload["choices"][0]["delta"]["tool_calls"][0]
        for payload in payloads
        if payload.get("choices")
        and payload["choices"][0]["delta"].get("tool_calls")
    ]

    assert len(tool_deltas) == 1
    assert tool_deltas[0]["id"] == "call_weather"
    assert tool_deltas[0]["function"]["name"] == "get_weather"
