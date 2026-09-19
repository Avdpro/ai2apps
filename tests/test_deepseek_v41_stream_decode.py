from __future__ import annotations

import pytest

from omlx.api.stream_codec import (
    MODEL_STREAM_CODEC_API,
    validate_model_stream_codec,
)
from omlx.api.thinking import ThinkingParser
from omlx.patches.deepseek_v41.engine import (
    DeepseekV41Engine,
    _append_only_text_delta,
    _decode_generated_prefix,
)


class _Tokenizer:
    _decoded = {
        (): "",
        (1,): "<think>",
        (1, 2): "<think>draft",
        (1, 2, 3): "<think>draft</think>",
        (1, 2, 3, 4): "<think>draft</think>\ufffd",
        (1, 2, 3, 4, 5): "<think>draft</think>你好",
        (1, 2, 3, 4, 5, 9): "<think>draft</think>你好<｜end▁of▁sentence｜>",
    }

    def decode(self, token_ids, *, skip_special_tokens):
        assert skip_special_tokens is False
        return self._decoded[tuple(token_ids)]


def test_v41_stream_preserves_think_boundary_and_withholds_incomplete_utf8():
    tokenizer = _Tokenizer()
    previous = ""
    deltas = []
    snapshots = []

    for end in range(1, 7):
        ids = [1, 2, 3, 4, 5, 9][:end]
        current = _decode_generated_prefix(tokenizer, ids, 9)
        previous, delta = _append_only_text_delta(previous, current)
        snapshots.append(previous)
        deltas.append(delta)

    assert "\ufffd" not in "".join(snapshots)
    assert "".join(deltas) == "<think>draft</think>你好"

    parser = ThinkingParser(start_in_thinking=True)
    reasoning_parts = []
    content_parts = []
    for delta in deltas:
        reasoning, content = parser.feed(delta)
        reasoning_parts.append(reasoning)
        content_parts.append(content)
    reasoning, content = parser.finish()
    reasoning_parts.append(reasoning)
    content_parts.append(content)

    assert "".join(reasoning_parts) == "draft"
    assert "".join(content_parts) == "你好"


def test_v41_stream_never_replays_text_when_decoder_prefix_regresses():
    previous, delta = _append_only_text_delta("stable", "changed")

    assert previous == "stable"
    assert delta == ""


def test_runtime_accepts_package_owned_pure_python_stream_codec(tmp_path):
    class PackageCodec:
        api_version = MODEL_STREAM_CODEC_API

        def decode_prefix(self, tokenizer, token_ids, *, eos_token_id):
            return "package:" + ",".join(str(token) for token in token_ids)

        def append_delta(self, previous, current):
            return current, current.removeprefix(previous)

    codec = PackageCodec()
    engine = DeepseekV41Engine(tmp_path, stream_codec=codec)

    assert engine._stream_codec is codec
    assert engine._stream_codec.decode_prefix(None, [1, 2], eos_token_id=None) == "package:1,2"


def test_stream_codec_contract_rejects_unknown_api_version():
    class FutureCodec:
        api_version = "ai2apps.model-stream-codec/v2"

        def decode_prefix(self, tokenizer, token_ids, *, eos_token_id):
            return ""

        def append_delta(self, previous, current):
            return current, ""

    with pytest.raises(ValueError, match="ai2apps.model-stream-codec/v1"):
        validate_model_stream_codec(FutureCodec())
