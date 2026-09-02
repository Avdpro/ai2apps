from __future__ import annotations

import json
from pathlib import Path

from omlx.cache.glm5_expert_store import create_glm5_expert_major_store
from omlx.cache.moe_expert_store import ExpertMajorStore

_SOURCE_NAMES = tuple(
    f"{projection}.{component}"
    for projection in ("gate_proj", "up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
)
_RUNTIME_NAMES = tuple(
    f"{projection}.{component}"
    for projection in ("gate_up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
)


def _write_test_checkpoint(root: Path) -> None:
    tensors = {}
    payload = bytearray()
    weight_map = {}
    for expert in range(2):
        for index, name in enumerate(_SOURCE_NAMES):
            key = f"model.language_model.layers.3.mlp.experts.{expert}.{name}"
            size = 4088 if index == len(_SOURCE_NAMES) - 1 else 1
            start = len(payload)
            payload.extend(bytes([expert * 16 + index]) * size)
            tensors[key] = {
                "dtype": "U8",
                "shape": [size],
                "data_offsets": [start, len(payload)],
            }
            weight_map[key] = "model-00001-of-00001.safetensors"
    header = json.dumps(tensors, separators=(",", ":")).encode()
    shard = root / "model-00001-of-00001.safetensors"
    shard.write_bytes(len(header).to_bytes(8, "little") + header + payload)
    (root / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": weight_map})
    )


def test_repack_glm5_per_expert_checkpoint(tmp_path):
    _write_test_checkpoint(tmp_path)
    output = tmp_path / "layer-003.moe"

    result = create_glm5_expert_major_store(tmp_path, 3, output)

    assert result["experts"] == 2
    assert result["record_bytes"] == 4096
    with ExpertMajorStore(output) as store:
        assert store.layer == 3
        assert store.num_experts == 2
        assert [tensor.name for tensor in store.tensors] == list(_RUNTIME_NAMES)
        assert [tensor.shape for tensor in store.tensors[:3]] == [(2,), (2,), (2,)]
        first = store.read(0)
        second = store.read(1)
        # Runtime order is gate+up for each affine component, then down.
        assert first[:8] == bytes((0, 3, 1, 4, 2, 5, 6, 7))
        assert second[:8] == bytes((16, 19, 17, 20, 18, 21, 22, 23))
        assert first[-1] == 8
        assert second[-1] == 24
