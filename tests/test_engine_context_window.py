# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

import pytest

from omlx.engine.base import cap_generation_tokens_to_context
from omlx.engine.batched import BatchedEngine
from omlx.engine.vlm import VLMBatchedEngine
from omlx.exceptions import InvalidRequestError


def test_generation_limit_preserves_smaller_requested_output():
    assert cap_generation_tokens_to_context(512, 1000, 32768) == 512


def test_generation_limit_caps_output_to_remaining_context():
    assert cap_generation_tokens_to_context(4096, 32000, 32768) == 768


def test_generation_limit_rejects_prompt_at_or_beyond_context():
    with pytest.raises(InvalidRequestError, match="Prompt exceeds"):
        cap_generation_tokens_to_context(256, 32768, 32768)


def test_generation_limit_is_backward_compatible_without_contract():
    assert cap_generation_tokens_to_context(4096, 999999, None) == 4096


class _Tokenizer:
    def encode(self, _prompt):
        return list(range(1000))


class _Core:
    def __init__(self):
        self.max_tokens = None

    async def generate(self, *, sampling_params, **_kwargs):
        self.max_tokens = sampling_params.max_tokens
        return SimpleNamespace(
            output_text="ok",
            prompt_tokens=1000,
            completion_tokens=1,
            finish_reason="stop",
            tool_calls=None,
            cached_tokens=0,
            first_token_at=None,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("engine_type", (BatchedEngine, VLMBatchedEngine))
async def test_generic_text_and_vlm_engines_enforce_package_context(engine_type):
    engine = object.__new__(engine_type)
    engine._loaded = True
    engine._tokenizer = _Tokenizer()
    engine._engine = _Core()

    await engine.generate("prompt", max_tokens=4096, max_context_window=2048)

    assert engine._engine.max_tokens == 1048
