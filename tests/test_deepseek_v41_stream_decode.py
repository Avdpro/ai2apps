from __future__ import annotations

import pytest

from omlx.api.stream_codec import (
    MODEL_STREAM_CODEC_API,
    validate_model_stream_codec,
)
from omlx.api.thinking import ThinkingParser
from omlx.patches.deepseek_v41.boost import (
    BOOST_TO_TOP,
    DeepseekV41BoostController,
    normalize_deepseek_v41_boost,
)
from omlx.patches.deepseek_v41.engine import (
    DeepseekV41Engine,
    _append_only_text_delta,
    _decode_generated_prefix,
    _effective_generation_limit,
    _generation_finish_reason,
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


def test_v41_stream_reports_stop_and_length_only_at_terminal_output():
    assert _generation_finish_reason(False, 0, 3) is None
    assert _generation_finish_reason(False, 1, 3) is None
    assert _generation_finish_reason(False, 2, 3) == "length"
    assert _generation_finish_reason(True, 0, 3) == "stop"


def test_v41_engine_defaults_to_32k_context(monkeypatch, tmp_path):
    monkeypatch.delenv("OMLX_DSV41_MAX_CONTEXT", raising=False)

    assert DeepseekV41Engine(tmp_path).max_context == 32768


def test_v41_generation_is_capped_to_remaining_context():
    assert _effective_generation_limit(4096, 404, 32768) == 4096
    assert _effective_generation_limit(40000, 404, 32768) == 32364


def test_v41_boost_product_modes_match_validated_decode_burst():
    assert BOOST_TO_TOP == {
        "auto": 6,
        "natural": 6,
        "turbo": 4,
        "blast": 2,
    }
    assert normalize_deepseek_v41_boost("blast") == "blast"
    with pytest.raises(ValueError, match="auto, natural, turbo, or blast"):
        normalize_deepseek_v41_boost("warp")


def test_v41_boost_request_is_applied_at_the_next_decode_boundary():
    applied = []

    class Model:
        boost_counts = type("Counts", (), {"tolist": lambda self: [[0, 0, 0, 0]]})()
        cache_counters = type("Counts", (), {"tolist": lambda self: [[0, 0, 0]]})()

        def set_boost_mode(self, mode, protected_top):
            applied.append((mode, protected_top))

    owner = type("Owner", (), {})()
    owner._model = Model()
    owner._active_session_id = "chat-a"
    controller = DeepseekV41BoostController(owner)
    controller.prepare("chat-a", "natural")

    result = controller.request("chat-a", "blast")

    assert result["queued"] is True
    assert result["applies"] == "next_token"
    assert controller.mode == "natural"
    assert controller.apply_pending("chat-a") == "blast"
    assert controller.mode == "blast"
    assert applied[-1] == ("blast", 2)


def test_v41_auto_remains_exact_until_a_measured_auto_policy_exists():
    applied = []
    model = type("Model", (), {
        "set_boost_mode": lambda self, mode, top: applied.append((mode, top)),
    })()
    owner = type("Owner", (), {"_model": model, "_active_session_id": None})()
    controller = DeepseekV41BoostController(owner)

    assert controller.prepare("chat-auto", "auto") == "natural"
    assert applied == [("natural", 6)]


def test_v41_engine_exports_session_owned_ssd_windows_without_mlx_readback(tmp_path):
    class Counter:
        def __init__(self, rows):
            self.rows = rows

        def tolist(self):
            return self.rows

    class Bank:
        def __init__(self, record_bytes, loaded_bytes):
            self.info = {"record_bytes": record_bytes}
            self.bytes = loaded_bytes

    class Config:
        n_activated_experts = 6

    class Model:
        c = Config()
        banks = {
            0: Bank(100, 500),
            1: Bank(200, 1000),
        }
        boost_counts = Counter([[0, 0, 0, 0]])
        cache_counters = Counter([[0, 0, 0]])

    engine = DeepseekV41Engine(tmp_path)
    engine._model = Model()
    engine._reset_ssd_window("chat-a")

    # The first output is sampled from Prefill logits, so it adds no Decode read.
    engine._record_ssd_window(0)
    first = engine.get_live_metrics("chat-a")
    assert first["ssd_recent_10_tokens"] == {
        "tokens": 0,
        "expert_loads": 0,
        "bytes_loaded": 0,
        "pressure": 0.0,
        "pressure_percent": 0.0,
        "severity": "healthy",
    }

    engine._model.banks[0].bytes += 600
    engine._model.banks[1].bytes += 400
    engine._record_ssd_window(5)
    engine._model.banks[0].bytes += 1800
    engine._model.banks[1].bytes += 1200
    engine._record_ssd_window(15)

    live = engine.get_live_metrics("chat-a")
    assert live["ssd_recent_10_tokens"]["tokens"] == 10
    assert live["ssd_recent_10_tokens"]["expert_loads"] == 24
    assert live["ssd_recent_10_tokens"]["bytes_loaded"] == 3000
    assert live["ssd_recent_10_tokens"]["pressure_percent"] == pytest.approx(
        100.0 / 6.0
    )
    assert live["ssd_turn_average"]["tokens"] == 15
    assert live["ssd_turn_average"]["expert_loads"] == 32
    assert live["ssd_turn_average"]["bytes_loaded"] == 4000
    assert live["ssd_turn_average"]["pressure_percent"] == pytest.approx(
        4000 / 27000 * 100.0
    )

    stats = engine.get_stats()["flesh"]
    assert stats["ssd_health_thresholds"]["routed_expert_bytes_per_token"] == 1800
    assert stats["ssd_recent_by_session"]["chat-a"] == live["ssd_recent_10_tokens"]
    assert stats["ssd_turn_by_session"]["chat-a"] == live["ssd_turn_average"]
