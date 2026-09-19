# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for prepared DeepSeek SSD memory-tier admission."""

from __future__ import annotations

import json
from pathlib import Path

from omlx.model_discovery import deepseek_cache_moe_memory_profile


def test_ssd_checkpoint_layout_uses_external_experts_for_full_estimate(
    tmp_path: Path, monkeypatch
):
    model = tmp_path / "model"
    experts = model / "experts"
    profile = model / "scope.json"
    experts.mkdir(parents=True)
    (model / "model.safetensors").write_bytes(b"backbone")
    profile.write_text(json.dumps({"scopes": {"general": {}}}))
    (experts / "manifest.json").write_text(
        json.dumps(
            {
                "layers": {
                    str(layer): {"record_bytes": 1024, "num_experts": 256}
                    for layer in range(43)
                }
            }
        )
    )
    prepared = {
        "checkpoint_layout": {"format": "ai2apps-ssd-checkpoint"},
        "expert_store": str(experts),
        "scope": {"profile": str(profile), "default": "general"},
    }
    monkeypatch.setattr(
        "omlx.utils.hardware.get_total_memory_bytes", lambda: 128 * 1024**3
    )

    memory = deepseek_cache_moe_memory_profile(model, prepared)

    assert memory is not None
    assert memory["physical_memory_gb"] == 128
    assert memory["recommended"] == "optimal"
    assert [tier["experts"] for tier in memory["tiers"]] == [20, 40, 60]
    assert all(
        tier["estimated_bytes"] < memory["full_estimated_bytes"]
        for tier in memory["tiers"]
    )
