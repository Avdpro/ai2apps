# SPDX-License-Identifier: Apache-2.0
"""Inkling mlx-vlm compatibility patch tests.

Covers the vendor install/discovery surface (unlimited-ocr test pattern),
the torch-free processor pieces, the NVFP4 config translation, and the
batched right-padded prefill parity that the vendored conv_mask wiring
(G2) exists for.
"""

from __future__ import annotations

import json

import pytest

try:
    import mlx.core as mx

    HAS_MLX = True
except ImportError:
    HAS_MLX = False

pytestmark = pytest.mark.skipif(not HAS_MLX, reason="MLX not available")


@pytest.fixture(scope="module")
def applied():
    from omlx.patches.mlx_vlm_inkling_compat import (
        apply_mlx_vlm_inkling_compat_patch,
        is_applied,
    )

    apply_mlx_vlm_inkling_compat_patch()
    assert is_applied()
    return True


def test_vendor_module_resolves(applied):
    import mlx_vlm.utils as vlm_utils

    assert vlm_utils.MODEL_REMAPPING.get("inkling_mm_model") == "inkling"

    import importlib

    module = importlib.import_module("mlx_vlm.models.inkling")
    assert hasattr(module, "Model")
    assert hasattr(module, "LanguageModel")

    # get_model_and_args resolves the checkpoint model_type.
    arch, model_type = _get_model_and_args(vlm_utils, "inkling_mm_model")
    assert model_type == "inkling"
    assert arch is module


def _get_model_and_args(vlm_utils, model_type):
    config = {"model_type": model_type}
    result = vlm_utils.get_model_and_args(config)
    # Signature drift guard: pinned mlx-vlm returns (arch_module, model_type)
    # or (arch, model_type, quant) depending on version.
    return result[0], result[1]


def test_prompt_formatting_image_first(applied):
    from mlx_vlm.prompt_utils import get_message_json

    message = get_message_json(
        "inkling_mm_model", "describe this", role="user", num_images=2
    )
    assert message["role"] == "user"
    content = message["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "image"}
    assert content[1] == {"type": "image"}
    assert content[2]["type"] == "text"
    assert content[2]["text"] == "describe this"

    # Assistant/no-image turns stay plain strings.
    assistant = get_message_json("inkling", "hello", role="assistant")
    assert assistant["content"] == "hello"


def test_other_models_untouched(applied):
    from mlx_vlm.prompt_utils import get_message_json

    message = get_message_json("qwen2_vl", "hi", role="user", num_images=1)
    assert message["role"] == "user"
    assert message["content"] != [{"type": "image"}, {"type": "text", "text": "hi"}]


def test_load_config_translates_nvfp4(applied, tmp_path):
    import mlx_vlm.utils as vlm_utils

    (tmp_path / "config.json").write_text(
        json.dumps({"model_type": "inkling_mm_model", "vocab_size": 128})
    )
    (tmp_path / "hf_quant_config.json").write_text(
        json.dumps({"quantization": {"quant_algo": "NVFP4"}})
    )
    config = vlm_utils.load_config(tmp_path)
    assert config["quantization"] == {"group_size": 16, "bits": 4, "mode": "nvfp4"}

    # Non-inkling checkpoints are not touched.
    other = tmp_path / "other"
    other.mkdir()
    (other / "config.json").write_text(json.dumps({"model_type": "llama"}))
    (other / "hf_quant_config.json").write_text(
        json.dumps({"quantization": {"quant_algo": "NVFP4"}})
    )
    config = vlm_utils.load_config(other)
    assert "quantization" not in config


def test_image_processor_patch_grid(applied):
    import importlib

    import numpy as np
    from PIL import Image

    processing_inkling = importlib.import_module(
        "mlx_vlm.models.inkling.processing_inkling"
    )

    proc = processing_inkling.InklingImageProcessor()
    image = Image.fromarray(
        np.full((100, 50, 3), 128, dtype=np.uint8)
    )  # H=100, W=50
    out = proc.preprocess([image])
    # rows = ceil(100/40) = 3, cols = 50//40 + 1 = 2 (reference grid).
    assert out["num_patches"].tolist() == [6]
    assert out["pixel_values"].shape == (6, 2, 40, 40, 3)
    # Padded region carries -1.0 pre-rescale: (-1 * 1/255 - mean) / std.
    # Patch 1 covers x = [40, 80); the image ends at x = 50, so patch-local
    # x >= 10 is padding.
    padded_pixel = out["pixel_values"][1, 0, 0, 20, 0]
    expected = (-1.0 / 255.0 - proc.image_mean[0]) / proc.image_std[0]
    assert abs(float(padded_pixel) - float(expected)) < 1e-5
    # Temporal duplication is exact.
    assert np.array_equal(
        out["pixel_values"][:, 0], out["pixel_values"][:, 1]
    )


def _tiny_text_config():
    from mlx_vlm.models.inkling.config import TextConfig

    return TextConfig(
        hidden_size=32,
        num_hidden_layers=2,
        vocab_size=128,
        num_attention_heads=4,
        num_key_value_heads=2,
        head_dim=8,
        swa_num_attention_heads=4,
        swa_num_key_value_heads=2,
        swa_head_dim=8,
        sliding_window_size=8,
        layer_types=["hybrid_sliding", "full"],
        d_rel=4,
        rel_extent=4,
        log_scaling_n_floor=4,
        sconv_kernel_size=4,
        mlp_layer_types=["dense", "sparse"],
        intermediate_size=16,
        dense_intermediate_size=32,
        n_routed_experts=4,
        num_experts_per_tok=2,
        n_shared_experts=1,
        tie_word_embeddings=True,
    )


def _tiny_language_model():
    from mlx_vlm.models.inkling.language import LanguageModel

    mx.random.seed(7)
    model = LanguageModel(_tiny_text_config())
    # Give routing and rel-bias non-degenerate weights.
    for layer in model.model.layers:
        attn = layer.self_attn
        attn.rel_proj = (
            mx.random.normal(attn.rel_proj.shape).astype(attn.rel_proj.dtype) * 0.05
        )
        if hasattr(layer.mlp, "gate_weight"):
            layer.mlp.gate_weight = (
                mx.random.normal(layer.mlp.gate_weight.shape) * 0.05
            )
    mx.eval(model.parameters())
    return model


def test_tiny_model_single_forward(applied):
    model = _tiny_language_model()
    cache = model.make_cache()
    tokens = mx.array([[1, 5, 9, 13, 17]])
    out = model(tokens, cache=cache)
    assert out.logits.shape == (1, 5, 128)
    step = model(mx.array([[21]]), cache=cache)
    assert step.logits.shape == (1, 1, 128)
    kv_state = cache[0][0].state
    assert kv_state[0].shape[2] == 6
    conv_slots = list(cache[0][1].state)
    assert len(conv_slots) == 4
    assert all(s is not None for s in conv_slots)


def test_dense_intermediate_size_required(applied):
    from mlx_vlm.models.inkling.language import LanguageModel

    config = _tiny_text_config()
    config.dense_intermediate_size = None
    with pytest.raises(ValueError, match="dense_intermediate_size"):
        LanguageModel(config)


def test_batched_right_padded_prefill_parity(applied):
    """G2: a short request prefILLED inside a right-padded batch must end
    with the same conv states and next-token logits as the same request
    run alone. Without the vendored conv_mask / lengths-aware state /
    key-masking wiring, the pad rows pollute the short-conv states and
    the attention keys."""
    from mlx_lm.models.cache import CacheList

    model = _tiny_language_model()

    tokens_a = [3, 17, 44, 91, 12, 7, 63]  # length 7
    tokens_b = [8, 22, 5, 99, 41, 33, 27, 54, 76, 11, 90, 2]  # length 12
    la, lb = len(tokens_a), len(tokens_b)

    # Single-request reference for A.
    cache_a = model.make_cache()
    logits_a = model(mx.array([tokens_a]), cache=cache_a).logits
    mx.eval(logits_a)

    # Batched: merge fresh per-request caches (the BatchGenerator path),
    # right-pad, chunked prefill, finalize.
    cache_1 = model.make_cache()
    cache_2 = model.make_cache()
    merged = [
        CacheList.merge([c1, c2]) for c1, c2 in zip(cache_1, cache_2)
    ]
    padded = [tokens_a + [0] * (lb - la), tokens_b]
    for c in merged:
        c.prepare(lengths=[la, lb], right_padding=[lb - la, 0])

    chunk = 5
    batch_tokens = mx.array(padded)
    logits_chunks = []
    for start in range(0, lb, chunk):
        out = model(batch_tokens[:, start : start + chunk], cache=merged)
        logits_chunks.append(out.logits)
    logits_batch = mx.concatenate(logits_chunks, axis=1)
    for c in merged:
        c.finalize()
    mx.eval(logits_batch)

    # Conv states of A inside the batch == single-run states.
    for layer_idx in range(2):
        batch_conv = merged[layer_idx][1]
        single_conv = cache_a[layer_idx][1]
        for slot in range(4):
            got = batch_conv[slot][0:1]
            want = single_conv[slot]
            assert mx.max(mx.abs(got - want)).item() < 1e-4, (
                f"layer {layer_idx} conv slot {slot} diverged in batch "
                "(pad pollution)"
            )

    # Last valid-token logits of A == single-run logits.
    diff = mx.max(
        mx.abs(logits_batch[0, la - 1] - logits_a[0, -1])
    ).item()
    assert diff < 1e-3, f"prefill logits diverged: {diff}"

    # One decode step: exercises left_padding key masking + per-seq tau.
    step_a = model(mx.array([[100]]), cache=cache_a).logits
    step_batch = model(mx.array([[100], [101]]), cache=merged).logits
    mx.eval(step_a, step_batch)
    diff = mx.max(mx.abs(step_batch[0, 0] - step_a[0, 0])).item()
    assert diff < 1e-3, f"decode logits diverged: {diff}"


def test_sanitize_maps_bf16_checkpoint_keys(applied):
    """The vendored sanitize must cover the bf16 original repo's key
    layout: attn projections, sconv transpose, router bias, and the
    interleaved w13 expert de-interleave."""
    import importlib

    inkling_mod = importlib.import_module("mlx_vlm.models.inkling.inkling")

    model = inkling_mod.Model.__new__(inkling_mod.Model)  # sanitize is pure

    hidden, inter, n_experts = 8, 4, 2
    w13 = mx.arange(n_experts * 2 * inter * hidden, dtype=mx.float32).reshape(
        n_experts, 2 * inter, hidden
    )
    w2 = mx.ones((n_experts, hidden, inter))
    sconv = mx.arange(hidden * 4, dtype=mx.float32).reshape(hidden, 4, 1)
    weights = {
        "model.llm.layers.1.attn.wq_du.weight": mx.zeros((hidden, hidden)),
        "model.llm.layers.1.attn.rel_logits_proj.proj": mx.zeros((4, 8)),
        "model.llm.layers.1.attn.k_sconv.weight": sconv,
        "model.llm.layers.1.attn_sconv.weight": sconv,
        "model.llm.layers.1.mlp.gate.weight": mx.zeros((n_experts + 1, hidden)),
        "model.llm.layers.1.mlp.gate.bias": mx.zeros((n_experts,)),
        "model.llm.layers.1.mlp.gate.global_scale": mx.ones((1,)),
        "model.llm.layers.1.mlp.experts.w13_weight": w13,
        "model.llm.layers.1.mlp.experts.w2_weight": w2,
        "model.llm.embed.weight": mx.zeros((16, hidden)),
        "model.llm.unembed.weight": mx.zeros((16, hidden)),
        "model.mtp.layers.0.input_proj.weight": mx.zeros((4, 4)),
    }
    out = inkling_mod.Model.sanitize(model, weights)

    prefix = "language_model.model.layers.1."
    assert prefix + "self_attn.q_proj.weight" in out
    assert prefix + "self_attn.rel_proj" in out
    assert out[prefix + "self_attn.k_sconv.conv.weight"].shape == (hidden, 1, 4)
    assert out[prefix + "attn_sconv.conv.weight"].shape == (hidden, 1, 4)
    assert prefix + "mlp.gate_weight" in out
    assert prefix + "mlp.e_score_correction_bias" in out
    assert prefix + "mlp.global_scale" in out
    assert "language_model.model.embed_tokens.weight" in out
    assert "language_model.lm_head.weight" in out
    # Raw mtp keys never leak; with the Lightning MTP hook installed
    # (process-wide once any MTP-aware sanitize ran) they map to
    # language_model.mtp.*, otherwise they are dropped.
    assert not any(k.startswith("model.mtp") for k in out)

    gate = out[prefix + "mlp.switch_mlp.gate_proj.weight"]
    up = out[prefix + "mlp.switch_mlp.up_proj.weight"]
    assert gate.shape == (n_experts, inter, hidden)
    # w13 rows interleave gate/up: gate = rows 0,2,4..., up = rows 1,3,5...
    ref = w13.reshape(n_experts, inter, 2, hidden)
    assert mx.array_equal(gate, ref[:, :, 0, :])
    assert mx.array_equal(up, ref[:, :, 1, :])
    assert mx.array_equal(out[prefix + "mlp.switch_mlp.down_proj.weight"], w2)
    # bf16 path synthesizes identity per-expert scales.
    assert mx.array_equal(
        out[prefix + "mlp.switch_mlp.gate_scale"], mx.ones((n_experts,))
    )


def test_sliding_window_slice_parity(applied, monkeypatch):
    """Slicing sliding-layer K/V to the window must match full-sequence
    SDPA (masked keys contribute exactly zero after softmax)."""
    import importlib

    language = importlib.import_module("mlx_vlm.models.inkling.language")
    model = _tiny_language_model()
    # window (sliding_window_size=8) well exceeded by prompt + decode.
    tokens = [(i * 37 + 11) % 128 for i in range(24)]

    def run():
        cache = model.make_cache()
        logits = [model(mx.array([tokens]), cache=cache).logits[:, -1]]
        for step in range(4):
            logits.append(model(mx.array([[step + 1]]), cache=cache).logits[:, -1])
        out = mx.concatenate(logits, axis=0)
        mx.eval(out)
        return out

    monkeypatch.setattr(language, "_SLIDING_WINDOW_SLICE", False)
    reference = run()
    monkeypatch.setattr(language, "_SLIDING_WINDOW_SLICE", True)
    sliced = run()

    diff = mx.max(mx.abs(reference - sliced)).item()
    assert diff < 2e-5, f"sliding-window slice diverged: {diff}"


def test_attention_bias_transient_registration():
    """The banded-mask transient must be priced into the SDPA estimate
    when registered, and cleared registrations must restore the base
    estimate (process-wide registry across model swaps)."""
    from omlx.memory_monitor import (
        MemoryMonitor,
        register_attention_bias_transient,
    )

    monitor = MemoryMonitor.__new__(MemoryMonitor)
    monitor._head_dim = 128
    monitor._num_attention_heads = 32
    monitor._num_kv_heads = 8
    monitor._score_dtype_size = 2

    try:
        register_attention_bias_transient(None)
        base = monitor._estimate_sdpa_activation_bytes(2048, 65536)
        register_attention_bias_transient(2)
        with_bias = monitor._estimate_sdpa_activation_bytes(2048, 65536)
        assert with_bias - base == 32 * 2048 * 65536 * 2
    finally:
        register_attention_bias_transient(None)
    assert monitor._estimate_sdpa_activation_bytes(2048, 65536) == base
