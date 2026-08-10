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
