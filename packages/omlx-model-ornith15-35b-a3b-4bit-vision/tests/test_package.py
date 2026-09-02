from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml


ROOT = Path(__file__).parents[1]
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from omlx_model_ornith15_35b_a3b_4bit_vision import (  # noqa: E402
    Ornith15CachedMoeAdapter,
)


def test_manifest_pins_dual_source_distribution_and_runtime_156():
    service = yaml.safe_load((ROOT / "service.yaml").read_text())
    model = service["models"][0]
    weights = model["weights"]
    preparation = weights["preparation"]
    distribution = json.loads(
        (ROOT / "META/checkpoint-distribution.json").read_text()
    )

    assert service["version"] == "0.1.0"
    assert model["model_type"] == "vlm"
    assert "image_recognition" in model["capabilities"]
    assert weights["revision"] == "31428ce8829c277f9255c59662b8efab58898ecf"
    assert weights["distribution_id"] == distribution["distributionId"]
    assert preparation["execution_modes"] == ["full", "cached"]
    assert preparation["default_execution_mode"] == "full"
    assert preparation["arena_tail_slots"] == 32
    assert [tier["experts"] for tier in preparation["memory_tiers"]] == [160, 192]
    assert service["requires"]["services"][0]["version"] == ">=1.5.6,<2.0.0"
    assert {
        (source["type"], source["revision"])
        for source in distribution["sourceRepositories"]
    } == {
        ("huggingface", "31428ce8829c277f9255c59662b8efab58898ecf"),
        ("modelscope", "2ceda9edec98ac813104d04f1fe05ca1b8fdae58"),
    }
    assert "ornith15_vision_bf16.safetensors" in distribution["includePatterns"]


def test_recipe_and_scope_pack_are_self_contained():
    recipe = Ornith15CachedMoeAdapter().installation_recipes()[0]
    profile = Path(recipe["engine"]["scope_asset"])
    pack = json.loads(Path(recipe["engine"]["scope_pack"]).read_text())

    assert recipe["id"] == "ornith-1.5-35b-a3b-mlx-4bit-vision"
    assert recipe["execution_modes"] == ("full", "cached")
    assert recipe["default_execution_mode"] == "full"
    assert profile.is_file()
    assert hashlib.sha256(profile.read_bytes()).hexdigest() == pack["profile"]["sha256"]
    assert pack["compatibility"]["memory_tiers"] == [160, 192]


def _load_worker():
    path = ROOT / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("ornith15_worker_adapter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worker_uses_memory_aware_full_default(monkeypatch):
    module = _load_worker()
    monkeypatch.setattr(module, "_physical_memory_bytes", lambda: 64 * 1024**3)
    assert module._execution_mode(
        {"moe_execution_mode": "cached", "cache_moe_memory_tier": "auto"}
    ) == "full"
    assert module._execution_mode(
        {"moe_execution_mode": "cached", "cache_moe_memory_tier": "compact"}
    ) == "cached"
    monkeypatch.setattr(module, "_physical_memory_bytes", lambda: 24 * 1024**3)
    assert module._execution_mode(
        {"moe_execution_mode": "cached", "cache_moe_memory_tier": "auto"}
    ) == "cached"


@pytest.mark.asyncio
async def test_worker_uses_vlm_engine_for_full_mode(monkeypatch, tmp_path):
    module = _load_worker()
    checkpoint = module.ModelWorkerCheckpoint(
        model_id="ornith",
        upstream_id="Avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision",
        provider="huggingface",
        repo_id="Avdpro/Ornith-1.5-35B-A3B-MLX-4bit-Vision",
        revision="31428ce8829c277f9255c59662b8efab58898ecf",
        path=tmp_path / "models--Avdpro--Ornith" / "snapshots" / "revision",
        preparation={},
    )
    checkpoint.path.mkdir(parents=True)

    vlm = ModuleType("omlx.engine.vlm")
    vlm.VLMBatchedEngine = lambda path, trust_remote_code=False: (path, trust_remote_code)
    policy = ModuleType("omlx.patches.qwen3_6_flesh.scope_policy")
    disabled = []
    policy.disable_qwen36_scope_policy = lambda: disabled.append(True)
    policy.configure_qwen36_scope_policy = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "omlx.engine.vlm", vlm)
    monkeypatch.setitem(sys.modules, "omlx.patches.qwen3_6_flesh.scope_policy", policy)
    monkeypatch.setattr(module, "_physical_memory_bytes", lambda: 64 * 1024**3)

    adapter = module.Ornith15VisionChatAdapter(object())
    engine = await adapter.create_engine(checkpoint, {})
    assert engine == (str(checkpoint.path), False)
    assert disabled == [True]
