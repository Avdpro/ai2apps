from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from omlx.engine.glm5_dynamic import Glm5DynamicVLMEngine
from omlx.engine.qwen4_dynamic import Qwen4DynamicVLMEngine
from omlx.engine.qwen36_dynamic import Qwen36DynamicVLMEngine
from omlx.engine.qwen36_tiered import Qwen36TieredEngine


class _DynamicCache:
    def __init__(self):
        self._stores = {
            3: SimpleNamespace(record_bytes=100),
            4: SimpleNamespace(record_bytes=120),
        }

    @staticmethod
    def stats():
        return {"experts_loaded": 9, "bytes_loaded": 980}


@pytest.mark.parametrize(
    ("engine_class", "top_k_attr", "expected_routed_bytes"),
    [
        (Glm5DynamicVLMEngine, "num_experts_per_tok", 1760),
        (Qwen4DynamicVLMEngine, "top_k", 2200),
    ],
)
def test_dynamic_engines_sample_exact_cache_counters(
    engine_class, top_k_attr, expected_routed_bytes
) -> None:
    cache = _DynamicCache()
    first = SimpleNamespace(dynamic_cache=cache, dynamic_layer=3)
    second = SimpleNamespace(dynamic_cache=cache, dynamic_layer=4)
    setattr(first, top_k_attr, 8 if engine_class is Glm5DynamicVLMEngine else 10)
    setattr(second, top_k_attr, 8 if engine_class is Glm5DynamicVLMEngine else 10)
    layers = [SimpleNamespace(mlp=first), SimpleNamespace(mlp=second)]
    engine = engine_class.__new__(engine_class)
    engine._vlm_model = SimpleNamespace(
        language_model=SimpleNamespace(model=SimpleNamespace(layers=layers))
    )

    assert engine._ssd_storage_totals() == (9, 980, expected_routed_bytes)


@pytest.mark.parametrize(
    ("engine_class", "boost_method"),
    [
        (Glm5DynamicVLMEngine, "on_scheduler_step"),
        (Qwen4DynamicVLMEngine, "on_scheduler_step"),
        (Qwen36DynamicVLMEngine, "between_step"),
    ],
)
def test_dynamic_engine_decode_boundary_chains_boost_and_telemetry(
    engine_class, boost_method
) -> None:
    engine = engine_class.__new__(engine_class)
    engine._ssd_telemetry = SimpleNamespace(record_scheduler_output=Mock())
    engine._glm5_boost = SimpleNamespace(**{boost_method: Mock()})
    engine._qwen4_boost = engine._glm5_boost
    engine._qwen_boost = engine._glm5_boost
    output = object()

    engine._between_decode_step(output)

    if boost_method == "on_scheduler_step":
        getattr(engine._glm5_boost, boost_method).assert_called_once_with(output)
    else:
        getattr(engine._glm5_boost, boost_method).assert_called_once_with()
    engine._ssd_telemetry.record_scheduler_output.assert_called_once_with(output)


def test_qwen36_tiered_decode_boundary_keeps_adaptive_callback() -> None:
    engine = Qwen36TieredEngine.__new__(Qwen36TieredEngine)
    engine._qwen_adaptive = SimpleNamespace(between_step=Mock())
    engine._ssd_telemetry = SimpleNamespace(record_scheduler_output=Mock())
    output = object()

    engine._between_decode_step(output)

    engine._qwen_adaptive.between_step.assert_called_once_with(output)
    engine._ssd_telemetry.record_scheduler_output.assert_called_once_with(output)
