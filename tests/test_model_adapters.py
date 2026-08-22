# SPDX-License-Identifier: Apache-2.0
"""Contract and integration coverage for installable model adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from omlx.model_adapters import (
    ModelAdapterRegistrationError,
    ModelAdapterRegistry,
    adapter_context,
)
from omlx.model_discovery import detect_model_type
from omlx.utils.model_loading import (
    maybe_apply_pre_load_patches,
    maybe_load_custom_quantization,
)


@dataclass
class _Adapter:
    adapter_id: str
    priority: int = 0
    model_type: str | None = None
    loaded: tuple[object, object] | None = None
    prepared: list | None = None

    def match(self, context):
        return context.config.get("adapter") == self.adapter_id

    def classify(self, context):
        return self.model_type

    def prepare(self, context):
        if self.prepared is not None:
            self.prepared.append(context)

    def load(self, context):
        return self.loaded


def _install_registry(monkeypatch, *adapters):
    from omlx.model_adapters import registry as registry_module

    registry = ModelAdapterRegistry(load_entry_points=False)
    for adapter in adapters:
        registry.register(adapter)
    monkeypatch.setattr(registry_module, "_default_registry", registry)
    return registry


def _write_config(tmp_path, config):
    (tmp_path / "config.json").write_text(json.dumps(config))


class TestModelAdapterRegistry:
    def test_rejects_invalid_and_duplicate_adapters(self):
        registry = ModelAdapterRegistry(load_entry_points=False)

        with pytest.raises(ModelAdapterRegistrationError, match="adapter_id"):
            registry.register(object())

        registry.register(_Adapter("first"))
        with pytest.raises(ModelAdapterRegistrationError, match="already registered"):
            registry.register(_Adapter("first"))

    def test_priority_then_id_is_deterministic(self):
        registry = ModelAdapterRegistry(load_entry_points=False)
        registry.register(_Adapter("low", priority=1))
        registry.register(_Adapter("z-high", priority=10))
        registry.register(_Adapter("a-high", priority=10))

        assert [adapter.adapter_id for adapter in registry.adapters()] == [
            "a-high",
            "z-high",
            "low",
        ]

    def test_first_matching_classification_wins(self):
        registry = ModelAdapterRegistry(load_entry_points=False)
        high = _Adapter("family", priority=10, model_type="vlm")
        low = _Adapter("family-low", priority=1, model_type="llm")
        registry.register(low)
        registry.register(high)
        context = adapter_context("/tmp/model", {"adapter": "family"})

        assert registry.classify(context) == "vlm"

    def test_broken_match_is_isolated(self, caplog):
        class Broken:
            adapter_id = "broken"
            priority = 20

            def match(self, context):
                raise RuntimeError("bad plugin")

        registry = ModelAdapterRegistry(load_entry_points=False)
        registry.register(Broken())
        registry.register(_Adapter("family", model_type="vlm"))

        with caplog.at_level("WARNING"):
            result = registry.classify(
                adapter_context("/tmp/model", {"adapter": "family"})
            )

        assert result == "vlm"
        assert "bad plugin" in caplog.text

    def test_matched_operation_failure_is_not_silently_ignored(self):
        class BrokenLoad:
            adapter_id = "family"

            def match(self, context):
                return True

            def load(self, context):
                raise RuntimeError("weights are invalid")

        registry = ModelAdapterRegistry(load_entry_points=False)
        registry.register(BrokenLoad())

        with pytest.raises(RuntimeError, match="weights are invalid"):
            registry.load(adapter_context("/tmp/model", {}))


class TestModelAdapterIntegration:
    def test_adapter_classification_precedes_legacy_discovery(
        self, tmp_path, monkeypatch
    ):
        _write_config(
            tmp_path,
            {
                "adapter": "future-model",
                "model_type": "unknown",
                "architectures": ["UnknownForCausalLM"],
            },
        )
        _install_registry(
            monkeypatch,
            _Adapter("future-model", model_type="vlm"),
        )

        assert detect_model_type(tmp_path) == "vlm"

    def test_none_classification_preserves_legacy_discovery(
        self, tmp_path, monkeypatch
    ):
        _write_config(
            tmp_path,
            {
                "adapter": "observe-only",
                "model_type": "qwen3_vl",
                "vision_config": {"hidden_size": 64},
            },
        )
        _install_registry(monkeypatch, _Adapter("observe-only"))

        assert detect_model_type(tmp_path) == "vlm"

    def test_prepare_hook_runs_before_legacy_dispatch(self, tmp_path, monkeypatch):
        prepared = []
        _write_config(
            tmp_path,
            {"adapter": "future-model", "model_type": "future_model"},
        )
        _install_registry(
            monkeypatch,
            _Adapter("future-model", prepared=prepared),
        )

        maybe_apply_pre_load_patches(str(tmp_path), for_vlm=True)

        assert len(prepared) == 1
        assert prepared[0].model_path == tmp_path
        assert prepared[0].for_vlm is True

    def test_custom_load_hook_precedes_builtin_quantization(
        self, tmp_path, monkeypatch
    ):
        expected = (object(), object())
        _write_config(
            tmp_path,
            {
                "adapter": "future-model",
                "model_type": "future_model",
                "quantization_config": {"quant_method": "future-quant"},
            },
        )
        _install_registry(
            monkeypatch,
            _Adapter("future-model", loaded=expected),
        )

        assert maybe_load_custom_quantization(
            str(tmp_path), is_vlm=False
        ) == expected
