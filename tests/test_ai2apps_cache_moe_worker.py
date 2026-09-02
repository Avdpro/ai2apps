# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import sys
from types import ModuleType

import pytest

from ai2apps.model_worker import ModelWorkerCheckpoint, ModelWorkerContext
from ai2apps.model_worker.cache_moe import (
    DeepseekV4ChatAdapter,
    Qwen36ChatAdapter,
    Qwen4ExpChatAdapter,
)


class _Engine:
    def __init__(self, model_name, **kwargs):
        self.model_name = model_name


def _checkpoint(tmp_path):
    revision = "a" * 40
    snapshot = tmp_path / "repo" / "snapshots" / revision
    profile = snapshot / ".ai2apps" / "scope.json"
    store = snapshot / ".ai2apps" / "experts"
    profile.parent.mkdir(parents=True)
    profile.write_text("{}")
    store.mkdir()
    (snapshot / "ai2apps-model.json").write_text(
        json.dumps(
            {
                "format": "ai2apps-cache-moe-model",
                "source": {"repo_id": "example/deepseek", "revision": revision},
                "scope": {"profile": str(profile), "default": "general"},
                "expert_store": str(store),
                "checkpoint_layout": {"format": "ai2apps-backbone-expert-store"},
            }
        )
    )
    checkpoint = ModelWorkerCheckpoint(
        model_id="example.worker/deepseek",
        upstream_id="example/deepseek",
        provider="huggingface",
        repo_id="example/deepseek",
        revision=revision,
        path=snapshot,
        preparation={"recipe": "ai2apps/cache-moe/v1"},
    )
    context = ModelWorkerContext(
        service_id="example.worker",
        package_root=tmp_path,
        data_root=tmp_path,
        models=(),
        checkpoints=(checkpoint,),
    )
    return checkpoint, context


@pytest.mark.asyncio
async def test_deepseek_worker_selects_full_and_cached_engines(monkeypatch, tmp_path):
    checkpoint, context = _checkpoint(tmp_path)
    configured = []

    batched = ModuleType("omlx.engine.batched")
    batched.BatchedEngine = _Engine
    flesh = ModuleType("omlx.engine.flesh")
    flesh.DeepseekV4FleshEngine = type("FleshEngine", (_Engine,), {})
    policy = ModuleType("omlx.patches.deepseek_v4.scope_policy")
    policy.configure_scope_policy = lambda *args: configured.append(args)
    policy.disable_scope_policy = lambda: configured.append(("disabled",))
    discovery = ModuleType("omlx.model_discovery")
    discovery.resolve_deepseek_cache_moe_experts = lambda *args: 40
    monkeypatch.setitem(sys.modules, "omlx.engine.batched", batched)
    monkeypatch.setitem(sys.modules, "omlx.engine.flesh", flesh)
    monkeypatch.setitem(sys.modules, "omlx.patches.deepseek_v4.scope_policy", policy)
    monkeypatch.setitem(sys.modules, "omlx.model_discovery", discovery)

    adapter = DeepseekV4ChatAdapter(context)
    full = await adapter.create_engine(
        checkpoint, {"moe_execution_mode": "full"}
    )
    cached = await adapter.create_engine(
        checkpoint,
        {"moe_execution_mode": "cached", "cache_moe_memory_tier": "compact"},
    )

    assert type(full) is _Engine
    assert type(cached).__name__ == "FleshEngine"
    assert configured[0][-1] == 256
    assert configured[1][-1] == 40


@pytest.mark.asyncio
async def test_qwen36_worker_selects_full_and_tiered_engines(monkeypatch, tmp_path):
    checkpoint, context = _checkpoint(tmp_path)
    configured = []

    batched = ModuleType("omlx.engine.batched")
    batched.BatchedEngine = _Engine
    tiered = ModuleType("omlx.engine.qwen36_tiered")
    tiered.Qwen36TieredEngine = type("TieredEngine", (_Engine,), {})
    policy = ModuleType("omlx.patches.qwen3_6_flesh.scope_policy")
    policy.configure_qwen36_scope_policy = (
        lambda *args, **kwargs: configured.append((args, kwargs))
    )
    policy.disable_qwen36_scope_policy = lambda: None
    discovery = ModuleType("omlx.model_discovery")
    discovery.resolve_qwen36_cache_moe_experts = lambda *args: 96
    monkeypatch.setitem(sys.modules, "omlx.engine.batched", batched)
    monkeypatch.setitem(sys.modules, "omlx.engine.qwen36_tiered", tiered)
    monkeypatch.setitem(
        sys.modules, "omlx.patches.qwen3_6_flesh.scope_policy", policy
    )
    monkeypatch.setitem(sys.modules, "omlx.model_discovery", discovery)

    adapter = Qwen36ChatAdapter(context)
    full = await adapter.create_engine(
        checkpoint, {"moe_execution_mode": "full"}
    )
    cached = await adapter.create_engine(
        checkpoint,
        {"moe_execution_mode": "cached", "cache_moe_memory_tier": "compact"},
    )

    assert type(full) is _Engine
    assert type(cached).__name__ == "TieredEngine"
    assert configured[0][0][-1] == 256
    assert configured[0][1] == {"backend": "flesh", "arena_tail_slots": 0}
    assert configured[1][0][-1] == 96
    assert configured[1][1] == {"backend": "tiered", "arena_tail_slots": 24}


@pytest.mark.asyncio
async def test_qwen4_worker_configures_exact_cached_vlm(monkeypatch, tmp_path):
    checkpoint, context = _checkpoint(tmp_path)
    vlm = ModuleType("omlx.engine.vlm")
    vlm.VLMBatchedEngine = type("VLMEngine", (_Engine,), {})
    monkeypatch.setitem(sys.modules, "omlx.engine.vlm", vlm)
    boost = ModuleType("omlx.patches.qwen38_next_cache.boost")
    boost.normalize_qwen4_boost = lambda value: value
    monkeypatch.setitem(sys.modules, "omlx.patches.qwen38_next_cache.boost", boost)

    adapter = Qwen4ExpChatAdapter(context)
    cached = await adapter.create_engine(
        checkpoint,
        {
            "moe_execution_mode": "cached",
            "cache_moe_memory_tier": "balanced",
            "cache_moe_boost_mode": "natural",
        },
    )

    assert type(cached).__name__ == "VLMEngine"
    assert cached.model_name == str(checkpoint.path)
    assert os.environ["OMLX_QWEN4_DYNAMIC_SLOTS"] == "160"
    assert os.environ["OMLX_QWEN4_HOT_SLOTS"] == "10"
    assert os.environ["OMLX_QWEN4_BOOST_MODE"] == "natural"
    assert os.environ["OMLX_QWEN4_PREFILL_CANONICAL_REUSE"] == "1"
    assert os.environ["OMLX_QWEN4_PREFILL_RETAIN_L1"] == "1"
