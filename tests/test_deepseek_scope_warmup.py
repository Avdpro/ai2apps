from types import SimpleNamespace

import pytest

from omlx.engine.batched import BatchedEngine, _deepseek_scope_warmup_ids


class _Tokenizer:
    bos_token_id = 7

    def encode(self, text, add_special_tokens=False):
        assert text
        assert add_special_tokens is False
        return [11, 12, 13]


def test_scope_warmup_ids_have_exact_requested_length():
    assert _deepseek_scope_warmup_ids(_Tokenizer(), "coding", 0) == []
    assert _deepseek_scope_warmup_ids(_Tokenizer(), "coding", 2) == [11, 12]
    assert _deepseek_scope_warmup_ids(_Tokenizer(), "coding", 8) == [
        11,
        12,
        13,
        11,
        12,
        13,
        11,
        12,
    ]


@pytest.mark.asyncio
async def test_scope_warmup_runs_once_and_clears_decode_hot_state(monkeypatch):
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_EXPERT_STORE", "/tmp/store")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_PROFILE", "/tmp/profile.json")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_NAME", "coding")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_WARMUP_TOKENS", "5")

    calls = []

    class Core:
        async def add_request(self, **kwargs):
            calls.append(kwargs)
            return "warmup"

        async def stream_outputs(self, request_id):
            assert request_id == "warmup"
            yield SimpleNamespace()

    class Loader:
        cleared = 0

        def clear_hot(self):
            self.cleared += 1

    loader = Loader()
    from omlx.patches.deepseek_v4 import scope_cache

    monkeypatch.setattr(
        scope_cache, "get_scope_fallback_loader", lambda directory: loader
    )
    import mlx.core as mx

    clear_calls = []
    monkeypatch.setattr(mx, "clear_cache", lambda: clear_calls.append(True))

    engine = BatchedEngine("unused")
    engine._model = SimpleNamespace(
        args=SimpleNamespace(model_type="deepseek_v4")
    )
    engine._tokenizer = _Tokenizer()
    engine._engine = Core()
    await engine._warm_deepseek_scope_cache()

    assert len(calls) == 1
    assert calls[0]["prompt"] == [11, 12, 13, 11, 12]
    assert calls[0]["skip_cache_store"] is True
    assert calls[0]["sampling_params"].max_tokens == 1
    assert loader.cleared == 1
    assert clear_calls == [True]


@pytest.mark.asyncio
async def test_scope_warmup_can_be_disabled(monkeypatch):
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_EXPERT_STORE", "/tmp/store")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_PROFILE", "/tmp/profile.json")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_NAME", "coding")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_WARMUP_TOKENS", "off")

    engine = BatchedEngine("unused")
    engine._model = SimpleNamespace(
        args=SimpleNamespace(model_type="deepseek_v4")
    )
    engine._tokenizer = _Tokenizer()
    engine._engine = SimpleNamespace()
    await engine._warm_deepseek_scope_cache()


@pytest.mark.asyncio
async def test_scope_warmup_skips_non_deepseek_model(monkeypatch):
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_EXPERT_STORE", "/tmp/store")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_PROFILE", "/tmp/profile.json")
    monkeypatch.setenv("OMLX_DEEPSEEK_V4_SCOPE_NAME", "coding")

    engine = BatchedEngine("unused")
    engine._model = SimpleNamespace(args=SimpleNamespace(model_type="llama"))
    engine._tokenizer = _Tokenizer()
    engine._engine = SimpleNamespace()
    await engine._warm_deepseek_scope_cache()
