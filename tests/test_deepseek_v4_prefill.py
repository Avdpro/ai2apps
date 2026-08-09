from types import SimpleNamespace

from omlx.patches.deepseek_v4.prefill import (
    DeepSeekV4PrefillConfig,
    deepseek_v4_prefill_step_size,
    make_deepseek_v4_prefill_config,
    model_declares_deepseek_v4,
)


def _step(context_tokens: int, remaining_tokens: int | None = None) -> int:
    remaining = context_tokens - 1 if remaining_tokens is None else remaining_tokens
    processed = context_tokens - 1 - remaining
    return deepseek_v4_prefill_step_size(
        processed_tokens=processed,
        remaining_tokens=remaining,
        base_tokens=0,
        config=DeepSeekV4PrefillConfig(),
    )


def test_detects_nested_deepseek_v4_model_type():
    model = SimpleNamespace(model=SimpleNamespace(args={"model_type": "deepseek_v4"}))

    assert model_declares_deepseek_v4(model)
    assert make_deepseek_v4_prefill_config(model) is not None


def test_does_not_enable_for_other_deepseek_generations():
    model = SimpleNamespace(args=SimpleNamespace(model_type="deepseek_v32"))

    assert not model_declares_deepseek_v4(model)
    assert make_deepseek_v4_prefill_config(model) is None


def test_context_bands_hold_transient_budget_schedule():
    assert _step(128 * 1024) == 5120
    assert _step(128 * 1024 + 1) == 4096
    assert _step(256 * 1024 + 1) == 3072
    assert _step(512 * 1024 + 1) == 2048
    assert _step(1_000_000) == 2048


def test_10k_prefill_keeps_one_unaligned_tail_to_avoid_moe_reload():
    config = DeepSeekV4PrefillConfig()
    context = 10_000
    remaining = context - 1
    processed = 0
    chunks = []

    while remaining:
        chunk = deepseek_v4_prefill_step_size(
            processed_tokens=processed,
            remaining_tokens=remaining,
            base_tokens=0,
            config=config,
        )
        chunks.append(chunk)
        processed += chunk
        remaining -= chunk

    assert chunks == [5120, 4879]
    assert sum(chunks) == context - 1


def test_long_context_splits_unaligned_large_tail_from_tiny_tail():
    config = DeepSeekV4PrefillConfig()
    base = 128 * 1024

    large_tail = deepseek_v4_prefill_step_size(
        processed_tokens=0,
        remaining_tokens=4001,
        base_tokens=base,
        config=config,
    )
    tiny_tail = deepseek_v4_prefill_step_size(
        processed_tokens=large_tail,
        remaining_tokens=4001 - large_tail,
        base_tokens=base,
        config=config,
    )

    assert large_tail == 3968
    assert tiny_tail == 33


def test_aligned_final_chunk_is_not_split():
    config = DeepSeekV4PrefillConfig()

    assert (
        deepseek_v4_prefill_step_size(
            processed_tokens=5120,
            remaining_tokens=4096,
            base_tokens=0,
            config=config,
        )
        == 4096
    )


def test_cached_prefix_counts_toward_context_band():
    config = DeepSeekV4PrefillConfig()

    assert (
        deepseek_v4_prefill_step_size(
            processed_tokens=0,
            remaining_tokens=4095,
            base_tokens=512 * 1024,
            config=config,
        )
        == 2048
    )
