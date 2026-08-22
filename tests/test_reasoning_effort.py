# SPDX-License-Identifier: Apache-2.0
"""Reasoning-effort request compatibility tests."""

from omlx.api.openai_models import ChatCompletionRequest
from omlx.api.utils import merge_reasoning_effort_chat_template_kwargs


def test_chat_completion_accepts_reasoning_effort():
    request = ChatCompletionRequest(
        model="qwen38",
        messages=[{"role": "user", "content": "hello"}],
        reasoning_effort="high",
    )

    assert request.reasoning_effort == "high"


def test_reasoning_effort_is_forwarded_to_chat_template():
    assert merge_reasoning_effort_chat_template_kwargs(None, "high") == {
        "reasoning_effort": "high"
    }


def test_raw_chat_template_reasoning_effort_takes_precedence():
    assert merge_reasoning_effort_chat_template_kwargs(
        {"reasoning_effort": "low", "enable_thinking": True},
        "high",
    ) == {"reasoning_effort": "low", "enable_thinking": True}
