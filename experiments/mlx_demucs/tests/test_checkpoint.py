from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from experiments.mlx_demucs.checkpoint import export_raw_npz, inspect_torch_checkpoint
from experiments.mlx_demucs.mlx_model import load_converted_safetensors


def test_checkpoint_inspection_is_json_safe(tmp_path):
    torch = pytest.importorskip("torch")
    checkpoint = tmp_path / "fixture.th"
    torch.save(
        {
            "klass": None,
            "kwargs": {
                "sources": ["background", "vocals"],
                "samplerate": 44100,
                "audio_channels": 2,
                "segment": Fraction(39, 5),
            },
            "state": {"layer.weight": torch.ones(2, 3)},
        },
        checkpoint,
    )

    result = inspect_torch_checkpoint(checkpoint)

    assert result["segment_seconds"] == 7.8
    assert result["tensor_count"] == 1
    assert result["parameter_count"] == 6
    assert result["tensor_bytes"] == 24


def test_raw_export_records_source_and_output_hashes(tmp_path):
    torch = pytest.importorskip("torch")
    checkpoint = tmp_path / "fixture.th"
    output = tmp_path / "weights.npz"
    torch.save(
        {
            "klass": None,
            "kwargs": {"samplerate": 44100, "audio_channels": 2},
            "state": {"layer.weight": torch.ones(2, 3)},
        },
        checkpoint,
    )

    manifest = export_raw_npz(checkpoint, output)

    assert len(manifest["source_checkpoint_sha256"]) == 64
    assert len(manifest["weights_sha256"]) == 64
    assert manifest["source_checkpoint_sha256"] != manifest["weights_sha256"]


def test_converted_safetensors_restores_layout_and_packed_attention(tmp_path):
    safetensors = pytest.importorskip("safetensors.numpy")
    path = tmp_path / "weights.safetensors"
    query = np.full((2, 2), 1, dtype=np.float32)
    key = np.full((2, 2), 2, dtype=np.float32)
    value = np.full((2, 2), 3, dtype=np.float32)
    safetensors.save_file(
        {
            "model_0.encoder.0.conv.conv.weight": np.arange(24, dtype=np.float32).reshape(2, 3, 2, 2),
            "model_0.crosstransformer.layers.0.attn.query_proj.weight": query,
            "model_0.crosstransformer.layers.0.attn.key_proj.weight": key,
            "model_0.crosstransformer.layers.0.attn.value_proj.weight": value,
        },
        path,
    )

    state = load_converted_safetensors(path)

    assert state["encoder.0.conv.weight"].shape == (2, 2, 3, 2)
    np.testing.assert_array_equal(
        state["crosstransformer.layers.0.self_attn.in_proj_weight"],
        np.concatenate([query, key, value]),
    )
