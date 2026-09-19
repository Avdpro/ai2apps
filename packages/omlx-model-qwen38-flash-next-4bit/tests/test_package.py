import json
import importlib.util
from pathlib import Path

import yaml

from ai2apps.model_worker.protocol import ModelWorkerError


PACKAGE = Path(__file__).parents[1]


def test_manifest_version_compatibility_and_runtime_dependency():
    manifest = json.loads((PACKAGE / "ai2apps.json").read_text())
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())

    assert manifest["package"]["id"] == "ai2apps/model-qwen38-flash-next-4bit"
    assert manifest["package"]["version"] == service["version"] == "0.1.4"
    assert manifest["compatibility"]["ai2apps"] == ">=0.1.0 <2.0.0"
    assert manifest["dependencies"] == [
        {
            "packageId": "ai2apps/runtime-omlx",
            "version": ">=1.7.5 <2.0.0",
            "optional": False,
        }
    ]
    assert service["requires"]["services"][0]["version"] == ">=1.7.5,<2.0.0"
    assert service["models"][0]["metadata"]["reasoning"] == {
        "schema": "ai2apps.reasoning/v1",
        "mode": "optional",
        "format": "think_tags",
        "default_enabled": True,
    }
    assert manifest["modelProfile"]["minimumMemoryBytes"] == 64 * 1024**3


def _worker_module(name: str):
    path = PACKAGE / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_auto_memory_tier_preserves_balanced_and_downgrades_to_lean(monkeypatch):
    module = _worker_module("qwen_next_auto_tier")
    monkeypatch.setattr(module, "get_total_memory_bytes", lambda: 128 * 1024**3)
    assert module._resolve_memory_tier("auto") == "balanced"
    monkeypatch.setattr(module, "get_total_memory_bytes", lambda: 52 * 1024**3)
    assert module._resolve_memory_tier("auto") == "lean"


def test_auto_memory_tier_keeps_performance_explicit_and_rejects_low_memory(monkeypatch):
    module = _worker_module("qwen_next_auto_tier_floor")
    monkeypatch.setattr(module, "get_total_memory_bytes", lambda: 128 * 1024**3)
    assert module._resolve_memory_tier("performance") == "performance"
    monkeypatch.setattr(module, "get_total_memory_bytes", lambda: 48 * 1024**3)
    try:
        module._resolve_memory_tier("auto")
    except ModelWorkerError as exc:
        assert exc.code == "insufficient_memory"
    else:
        raise AssertionError("48 GiB must not pass the Qwen Next Lean reserve floor")
