from __future__ import annotations

import json
from types import SimpleNamespace

import mlx.core as mx
import pytest

from omlx.patches.qwen3_6_flesh.io_patch import (
    _bind_vlm_scope_blocks,
    _load_qwen36_scope_safetensors,
    apply_qwen36_vlm_flesh_patch,
    qwen36_scope_safetensors_on_load,
)
from omlx.patches.qwen3_6_flesh.scope_policy import (
    clear_qwen36_scope_policy,
    configure_qwen36_scope_policy,
    load_qwen36_scope_policy,
)


@pytest.fixture(autouse=True)
def _clear_policy():
    clear_qwen36_scope_policy()
    yield
    clear_qwen36_scope_policy()


def _configure_policy(tmp_path, *, backend="tiered", tail_slots=2):
    ranking = [17, 3, 250, 9, 11, 12, 13, 14] + [
        expert for expert in range(256) if expert not in {17, 3, 250, 9, 11, 12, 13, 14}
    ]
    layers = {str(layer): ranking for layer in range(40)}
    profile = tmp_path / "scope.json"
    profile.write_text(
        json.dumps(
            {
                "phases": {
                    "prefill": {"coding": layers},
                    "decode": {"coding": layers},
                }
            }
        )
    )
    store = tmp_path / "experts"
    store.mkdir()
    configure_qwen36_scope_policy(
        profile,
        "coding",
        store,
        8,
        backend=backend,
        arena_tail_slots=tail_slots,
    )
    return load_qwen36_scope_policy()


def test_scope_reader_loads_only_protected_plus_tail_experts(tmp_path):
    policy = _configure_policy(tmp_path)
    path = tmp_path / "model.safetensors"
    expert_rows = mx.arange(256, dtype=mx.uint32).reshape(256, 1)
    mx.save_safetensors(
        str(path),
        {
            "language_model.model.layers.0.mlp.switch_mlp.gate_proj.weight": expert_rows,
            "language_model.model.layers.0.self_attn.weight": mx.ones(
                (2, 2), dtype=mx.bfloat16
            ),
        },
    )

    loaded = _load_qwen36_scope_safetensors(path, policy)
    mx.eval(*loaded.values())

    compact = loaded["language_model.model.layers.0.mlp.switch_mlp.gate_proj.weight"]
    # Top-8 ranking followed by the first two non-protected tail experts.
    assert compact.shape == (10, 1)
    assert compact[:, 0].tolist() == [17, 3, 250, 9, 11, 12, 13, 14, 0, 1]
    assert loaded["language_model.model.layers.0.self_attn.weight"].shape == (2, 2)
    assert loaded["language_model.model.layers.0.self_attn.weight"].dtype == mx.bfloat16


def test_scope_reader_context_is_qwen_only_and_restores_loader(tmp_path):
    _configure_policy(tmp_path)
    import mlx_vlm.utils as vlm_utils

    original = vlm_utils._load_safetensors
    qwen_dir = tmp_path / "qwen"
    qwen_dir.mkdir()
    (qwen_dir / "config.json").write_text(json.dumps({"model_type": "qwen3_5_moe"}))
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    (other_dir / "config.json").write_text(json.dumps({"model_type": "llama"}))

    with qwen36_scope_safetensors_on_load(qwen_dir):
        assert vlm_utils._load_safetensors is not original
    assert vlm_utils._load_safetensors is original

    with qwen36_scope_safetensors_on_load(other_dir):
        assert vlm_utils._load_safetensors is original


def test_vlm_qwen_constructs_compact_primary_and_tail_banks(tmp_path):
    _configure_policy(tmp_path)
    apply_qwen36_vlm_flesh_patch()

    from mlx_vlm.models.qwen3_5_moe.language import Qwen3_5MoeSparseMoeBlock

    block = Qwen3_5MoeSparseMoeBlock(
        SimpleNamespace(
            hidden_size=16,
            moe_intermediate_size=8,
            shared_expert_intermediate_size=8,
            num_experts=256,
            num_experts_per_tok=8,
            hidden_act="silu",
        )
    )

    assert block.switch_mlp.gate_proj.weight.shape[0] == 8
    assert block.tail_switch_mlp.gate_proj.weight.shape[0] == 2


def test_vlm_scope_binding_does_not_depend_on_sanitize(tmp_path, monkeypatch):
    policy = _configure_policy(tmp_path, backend="flesh", tail_slots=1)
    blocks = [SimpleNamespace() for _ in range(3)]
    model = SimpleNamespace(
        language_model=SimpleNamespace(
            model=SimpleNamespace(
                layers=[SimpleNamespace(mlp=block) for block in blocks]
            )
        )
    )

    registered = {}

    class Loader:
        def register_prefill_blocks(self, model_key, value):
            registered[model_key] = value

    monkeypatch.setattr(
        "omlx.patches.qwen3_6_flesh.scope_cache.get_qwen36_fallback_loader",
        lambda _path: Loader(),
    )

    bound = _bind_vlm_scope_blocks(model, policy)

    assert bound == tuple(blocks)
    assert registered[id(model)] == tuple(blocks)
    for layer, block in enumerate(blocks):
        assert block.scope_layer == layer
        assert block.scope_expert_ids == policy.experts(layer, phase="decode")
        assert block.scope_prefill_model_key == id(model)
