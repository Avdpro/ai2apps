from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    module_root = ROOT / "benchmarks" / "ideogram4"
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))
    spec = importlib.util.spec_from_file_location(name, module_root / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_ideogram4_schedule_matches_sampling_direction() -> None:
    scheduler = load_module("ideogram4_scheduler", "scheduler.py")
    values = scheduler.schedule_for_resolution(12, 1024, 1024, known_mean=1.0)
    assert values.shape == (13,)
    assert values.dtype == np.float32
    assert np.all(np.diff(values) < 0)
    assert 0.99 < values[0] <= 1.0
    assert 0.0 <= values[-1] < 0.01


def test_ideogram4_image_strength_selects_effective_steps() -> None:
    scheduler = load_module("ideogram4_strength_scheduler", "scheduler.py")
    assert scheduler.steps_for_strength(12, 1.0) == 12
    assert scheduler.steps_for_strength(12, 0.5) == 6
    assert scheduler.steps_for_strength(12, 0.01) == 1
    with pytest.raises(ValueError):
        scheduler.steps_for_strength(12, 0.0)
    with pytest.raises(ValueError):
        scheduler.steps_for_strength(12, 1.01)


def test_ideogram4_small_mlx_transformer_forward() -> None:
    mx = pytest.importorskip("mlx.core")
    model_module = load_module("ideogram4_mlx_model", "mlx_model.py")
    config = model_module.Ideogram4Config(
        emb_dim=96,
        num_layers=2,
        num_heads=3,
        intermediate_size=192,
        adaln_dim=32,
        in_channels=16,
        llm_features_dim=64,
        mrope_section=(6, 5, 5),
    )
    model = model_module.Ideogram4Transformer(config)
    batch, text_tokens, image_tokens = 1, 3, 4
    sequence = text_tokens + image_tokens
    indicator = mx.array(
        [
            [model_module.LLM_TOKEN_INDICATOR] * text_tokens
            + [model_module.OUTPUT_IMAGE_INDICATOR] * image_tokens
        ]
    )
    positions = mx.zeros((batch, sequence, 3), dtype=mx.int32)
    positions[:, :, 0] = mx.arange(sequence)
    positions[:, text_tokens:, 1] = mx.array([0, 0, 1, 1])
    positions[:, text_tokens:, 2] = mx.array([0, 1, 0, 1])
    output = model(
        llm_features=mx.random.normal((batch, sequence, config.llm_features_dim)),
        value=mx.random.normal((batch, sequence, config.in_channels)),
        timestep=mx.array([0.5]),
        position_ids=positions,
        segment_ids=mx.zeros((batch, sequence), dtype=mx.int32),
        indicator=indicator,
    )
    mx.eval(output)
    assert output.shape == (batch, sequence, config.in_channels)
    assert output.dtype == mx.float32
    assert bool(mx.all(mx.isfinite(output)).item())


def test_ideogram4_fp8_decoder_matches_ml_dtypes() -> None:
    converter = load_module("ideogram4_converter", "convert_fp8_to_mlx.py")
    values = np.arange(256, dtype=np.uint8)
    decoded = converter.decode_float8_e4m3fn(memoryview(values))
    assert decoded.shape == (256,)
    assert decoded[0] == 0.0
    assert decoded[0x01] == 2.0**-9
    assert decoded[0x38] == 1.0
    assert decoded[0x7E] == 448.0
    assert decoded[0xB8] == -1.0
    assert np.isnan(decoded[0x7F])


def test_ideogram4_fp8_converter_writes_native_quantized_weights(
    tmp_path: Path,
) -> None:
    mx = pytest.importorskip("mlx.core")
    converter = load_module("ideogram4_converter_roundtrip", "convert_fp8_to_mlx.py")
    encoded = np.tile(np.arange(64, dtype=np.uint8), 2)
    scale = np.array(0.25, dtype="<f4")
    bias_float = np.array([0.5, -0.5], dtype=np.float32)
    bias = (bias_float.view(np.uint32) >> 16).astype("<u2")
    marker = np.zeros(27, dtype=np.uint8)
    chunks = [encoded.tobytes(), scale.tobytes(), bias.tobytes(), marker.tobytes()]
    offsets = []
    cursor = 0
    for chunk in chunks:
        offsets.append([cursor, cursor + len(chunk)])
        cursor += len(chunk)
    header = {
        "linear.weight": {
            "dtype": "F8_E4M3",
            "shape": [2, 64],
            "data_offsets": offsets[0],
        },
        "linear.weight_scale": {
            "dtype": "F32",
            "shape": [],
            "data_offsets": offsets[1],
        },
        "linear.bias": {"dtype": "BF16", "shape": [2], "data_offsets": offsets[2]},
        "linear.comfy_quant": {
            "dtype": "U8",
            "shape": [27],
            "data_offsets": offsets[3],
        },
    }
    header_bytes = json.dumps(header, separators=(",", ":")).encode()
    header_bytes += b" " * ((8 - len(header_bytes) % 8) % 8)
    source = tmp_path / "source.safetensors"
    source.write_bytes(
        struct.pack("<Q", len(header_bytes)) + header_bytes + b"".join(chunks)
    )
    output = tmp_path / "output.safetensors"
    report = converter.convert_component(source, output, bits=8, group_size=32)
    weights = mx.load(str(output))
    restored = mx.dequantize(
        weights["linear.weight"],
        weights["linear.scales"],
        weights["linear.biases"],
        group_size=32,
        bits=8,
    )
    expected = converter.decode_float8_e4m3fn(memoryview(encoded))
    expected = expected.reshape(2, 64) * 0.25
    mx.eval(restored)
    assert np.max(np.abs(np.array(restored.astype(mx.float32)) - expected)) < 0.02
    assert np.allclose(
        np.array(weights["linear.bias"].astype(mx.float32)), bias_float, atol=1e-3
    )
    assert report["quantized_layers"] == 1


def test_ideogram4_unpatch_uses_patch_patch_channel_order() -> None:
    mx = pytest.importorskip("mlx.core")
    vae = load_module("ideogram4_vae", "vae.py")
    packed = mx.arange(2 * 2 * 128).reshape(1, 4, 128).astype(mx.float32)
    shift, scale = vae.latent_norm()
    normalized = packed * scale[None, None, :] + shift[None, None, :]
    expected = normalized.reshape(1, 2, 2, 2, 2, 32)
    expected = expected.transpose(0, 5, 1, 3, 2, 4).reshape(1, 32, 4, 4)
    actual = vae.unpatch_latents(packed, 2, 2)
    mx.eval(actual)
    assert bool(mx.allclose(actual, expected).item())


def test_ideogram4_pack_and_unpatch_round_trip() -> None:
    mx = pytest.importorskip("mlx.core")
    vae = load_module("ideogram4_vae_roundtrip", "vae.py")
    expected = mx.random.normal((1, 32, 6, 8), dtype=mx.float32)
    packed = vae.pack_latents(expected)
    actual = vae.unpatch_latents(packed, 3, 4)
    mx.eval(actual)
    assert bool(mx.allclose(actual, expected, rtol=1e-5, atol=1e-5).item())


def test_ideogram4_fused_qk_rms_mrope_matches_reference() -> None:
    mx = pytest.importorskip("mlx.core")
    fused_module = load_module("ideogram4_fused_qk_rope", "fused_qk_rope.py")
    if not fused_module.available():
        pytest.skip("Metal is unavailable")
    batch, sequence, heads, hidden = 1, 3, 2, 256
    query = mx.random.normal((batch, sequence, heads, hidden))
    key = mx.random.normal((batch, sequence, heads, hidden))
    q_weight = mx.random.normal((hidden,)).astype(mx.bfloat16)
    k_weight = mx.random.normal((hidden,)).astype(mx.bfloat16)
    cosine = mx.random.normal((batch, sequence, hidden))
    sine = mx.random.normal((batch, sequence, hidden))

    def rotate_half(value):
        half = value.shape[-1] // 2
        return mx.concatenate((-value[..., half:], value[..., :half]), axis=-1)

    q_reference = mx.fast.rms_norm(query, q_weight, 1e-5).transpose(0, 2, 1, 3)
    k_reference = mx.fast.rms_norm(key, k_weight, 1e-5).transpose(0, 2, 1, 3)
    q_reference = (
        q_reference * cosine[:, None] + rotate_half(q_reference) * sine[:, None]
    )
    k_reference = (
        k_reference * cosine[:, None] + rotate_half(k_reference) * sine[:, None]
    )
    fused = fused_module.fused_qk_rms_mrope(
        query,
        key,
        q_weight,
        k_weight,
        cosine,
        sine,
        1e-5,
    )
    assert fused is not None
    mx.eval(*fused, q_reference, k_reference)
    assert bool(mx.allclose(fused[0], q_reference, rtol=1e-5, atol=1e-5).item())
    assert bool(mx.allclose(fused[1], k_reference, rtol=1e-5, atol=1e-5).item())


def test_ideogram4_mlp_uses_bf16_qmm_and_preserves_residual_dtype() -> None:
    mx = pytest.importorskip("mlx.core")
    nn = pytest.importorskip("mlx.nn")
    model_module = load_module("ideogram4_mlx_model_mlp", "mlx_model.py")
    mlp = model_module.MLP(64, 128)
    mlp.set_dtype(mx.bfloat16)
    nn.quantize(mlp, group_size=32, bits=4)
    mlp.activation_dtype = mx.bfloat16
    value = mx.random.normal((1, 7, 64), dtype=mx.float32)
    output = mlp(value)
    mx.eval(output)
    assert output.shape == value.shape
    assert output.dtype == mx.float32
    assert bool(mx.all(mx.isfinite(output)).item())


def test_ideogram4_bf16_sdpa_preserves_attention_output_dtype() -> None:
    mx = pytest.importorskip("mlx.core")
    model_module = load_module("ideogram4_mlx_model_sdpa", "mlx_model.py")
    attention = model_module.Attention(96, 3)
    attention.sdpa_dtype = mx.bfloat16
    value = mx.random.normal((1, 7, 96), dtype=mx.float32)
    cosine = mx.ones((1, 7, 32), dtype=mx.float32)
    sine = mx.zeros((1, 7, 32), dtype=mx.float32)
    output = attention(value, None, cosine, sine)
    mx.eval(output)
    assert output.shape == value.shape
    assert output.dtype == mx.float32
    assert bool(mx.all(mx.isfinite(output)).item())
