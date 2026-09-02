import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _provider_module():
    path = Path(__file__).parents[1] / "packages/qwen35-provider/src/provider.py"
    spec = importlib.util.spec_from_file_location("ai2apps_qwen35_provider_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Engine:
    async def stream_chat(self, _messages, **_kwargs):
        yield SimpleNamespace(
            new_text="OK",
            finish_reason="stop",
            prompt_tokens=3,
            completion_tokens=1,
            cached_tokens=0,
        )


@pytest.mark.asyncio
async def test_qwen35_stream_emits_requested_final_usage():
    provider = _provider_module()
    chunks = [
        chunk
        async for chunk in provider._chat_stream(
            "mlx-community/Qwen3.5-0.8B-4bit",
            _Engine(),
            [{"role": "user", "content": "Say OK"}],
            {"stream_options": {"include_usage": True}},
            "chatcmpl-test",
        )
    ]

    payloads = [
        json.loads(chunk.removeprefix(b"data: ").strip())
        for chunk in chunks
        if chunk != b"data: [DONE]\n\n"
    ]
    assert payloads[-1]["choices"] == []
    assert payloads[-1]["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 1,
        "total_tokens": 4,
        "prompt_tokens_details": {"cached_tokens": 0},
    }


@pytest.mark.asyncio
async def test_qwen35_stream_omits_usage_unless_requested():
    provider = _provider_module()
    chunks = [
        chunk
        async for chunk in provider._chat_stream(
            "mlx-community/Qwen3.5-0.8B-4bit",
            _Engine(),
            [{"role": "user", "content": "Say OK"}],
            {},
            "chatcmpl-test",
        )
    ]
    assert all(b'"usage"' not in chunk for chunk in chunks)
