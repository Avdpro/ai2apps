import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture(scope="module")
def deepseek_v4_model():
    from omlx.patches.deepseek_v4 import apply_deepseek_v4_patch

    apply_deepseek_v4_patch()
    return importlib.import_module("mlx_lm.models.deepseek_v4")


@pytest.mark.parametrize(
    ("resident_experts", "expected"),
    ((20, 16), (40, 16), (60, 16)),
)
def test_prefill_miss_bank_follows_memory_tier(
    monkeypatch: pytest.MonkeyPatch,
    deepseek_v4_model,
    resident_experts: int,
    expected: int,
) -> None:
    monkeypatch.delenv(deepseek_v4_model._PREFILL_MISS_BANK_EXPERTS_ENV, raising=False)
    monkeypatch.setattr(
        deepseek_v4_model,
        "load_scope_policy_from_env",
        lambda: SimpleNamespace(resident_experts=resident_experts),
    )

    assert deepseek_v4_model._prefill_miss_bank_experts() == expected


def test_prefill_miss_bank_environment_override(
    monkeypatch: pytest.MonkeyPatch,
    deepseek_v4_model,
) -> None:
    monkeypatch.setenv(deepseek_v4_model._PREFILL_MISS_BANK_EXPERTS_ENV, "48")

    assert deepseek_v4_model._prefill_miss_bank_experts() == 48


@pytest.mark.parametrize("value", ("1", "true", "on", "yes"))
def test_prefill_double_buffer_accepts_true_values(
    monkeypatch: pytest.MonkeyPatch, deepseek_v4_model, value: str
) -> None:
    monkeypatch.setenv(deepseek_v4_model._PREFILL_DOUBLE_BUFFER_ENV, value)
    assert deepseek_v4_model._prefill_double_buffer_enabled() is True


@pytest.mark.parametrize("value", ("", "0", "false", "off", "no"))
def test_prefill_double_buffer_accepts_false_values(
    monkeypatch: pytest.MonkeyPatch, deepseek_v4_model, value: str
) -> None:
    monkeypatch.setenv(deepseek_v4_model._PREFILL_DOUBLE_BUFFER_ENV, value)
    assert deepseek_v4_model._prefill_double_buffer_enabled() is (value == "")


def test_prefill_double_buffer_defaults_on(
    monkeypatch: pytest.MonkeyPatch, deepseek_v4_model
) -> None:
    monkeypatch.delenv(deepseek_v4_model._PREFILL_DOUBLE_BUFFER_ENV, raising=False)
    assert deepseek_v4_model._prefill_double_buffer_enabled() is True


@pytest.mark.parametrize("value", ("0", "257", "invalid"))
def test_prefill_miss_bank_rejects_invalid_override(
    monkeypatch: pytest.MonkeyPatch,
    deepseek_v4_model,
    value: str,
) -> None:
    monkeypatch.setenv(deepseek_v4_model._PREFILL_MISS_BANK_EXPERTS_ENV, value)

    with pytest.raises(ValueError, match="OMLX_DEEPSEEK_V4_PREFILL_MISS_BANK_EXPERTS"):
        deepseek_v4_model._prefill_miss_bank_experts()
