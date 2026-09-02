from __future__ import annotations

import json

import mlx.core as mx

from omlx.cache.moe_expert_store import ExpertMajorStore
from omlx.cache.qwen36_expert_store import (
    create_qwen36_direct_store,
    discover_qwen36_expert_rows,
)


def test_qwen36_direct_store_fuses_source_rows_without_intermediate(tmp_path):
    prefix = "language_model.model.layers.0.mlp.switch_mlp"
    widths = {
        "gate_proj.weight": 1024,
        "up_proj.weight": 1024,
        "down_proj.weight": 1024,
        "gate_proj.scales": 128,
        "up_proj.scales": 128,
        "down_proj.scales": 128,
        "gate_proj.biases": 213,
        "up_proj.biases": 213,
        "down_proj.biases": 214,
    }
    tensors = {}
    cursor = 1
    for name, width in widths.items():
        size = 2 * width
        tensors[f"{prefix}.{name}"] = (
            mx.arange(cursor, cursor + size, dtype=mx.uint32) % 251
        ).astype(mx.uint8).reshape(2, width)
        cursor += size
    shard = tmp_path / "model-00001-of-00001.safetensors"
    mx.save_safetensors(str(shard), tensors)
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "model_type": "qwen3_5_moe",
                "text_config": {"num_experts": 2, "num_hidden_layers": 1},
            }
        )
    )
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    key: shard.name for key in tensors
                }
            }
        )
    )

    discovered = discover_qwen36_expert_rows(tmp_path)
    output = tmp_path / "layer-000.moe"
    result = create_qwen36_direct_store(
        tmp_path, 0, output, discovered=discovered
    )

    assert result["record_bytes"] == 4096
    assert result["variant"].endswith("direct-v3")
    with ExpertMajorStore(output) as store:
        assert store.runtime_layout == "fused-switch-glu"
        assert store.num_experts == 2
        assert [item.name for item in store.tensors] == [
            "gate_up_proj.weight",
            "gate_up_proj.scales",
            "gate_up_proj.biases",
            "down_proj.weight",
            "down_proj.scales",
            "down_proj.biases",
        ]
        record = store.read(1)
        views = {layout.name: bytes(raw) for layout, raw in store.tensor_views(record)}

    def row(name):
        value = tensors[f"{prefix}.{name}"][1]
        mx.eval(value)
        return bytes(memoryview(value))

    assert views["gate_up_proj.weight"] == row("gate_proj.weight") + row("up_proj.weight")
    assert views["gate_up_proj.scales"] == row("gate_proj.scales") + row("up_proj.scales")
    assert views["gate_up_proj.biases"] == row("gate_proj.biases") + row("up_proj.biases")
    assert views["down_proj.weight"] == row("down_proj.weight")
    assert views["down_proj.scales"] == row("down_proj.scales")
    assert views["down_proj.biases"] == row("down_proj.biases")
