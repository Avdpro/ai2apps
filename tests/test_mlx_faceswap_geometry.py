import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.mlx_faceswap.assets import resolve_model
from experiments.mlx_faceswap.geometry import (
    ARCFACE_112,
    align_face,
    alignment_template,
    estimate_similarity,
)
from experiments.mlx_faceswap.verify_bundles import verify_bundle


def test_alignment_templates_match_arcface_conventions():
    np.testing.assert_allclose(alignment_template(112), ARCFACE_112)
    expected_128 = ARCFACE_112.copy()
    expected_128[:, 0] += 8
    np.testing.assert_allclose(alignment_template(128), expected_128)
    with pytest.raises(ValueError, match="divisible"):
        alignment_template(100)


def test_similarity_and_crop_preserve_template_points():
    landmarks = alignment_template(128) + np.array([11.0, 7.0], dtype=np.float32)
    matrix = estimate_similarity(landmarks, 128)
    mapped = landmarks @ matrix[:, :2].T + matrix[:, 2]
    np.testing.assert_allclose(mapped, alignment_template(128), atol=1e-4)

    image = np.zeros((160, 160, 3), dtype=np.uint8)
    crop, returned_matrix = align_face(image, landmarks, 128)
    assert crop.shape == (128, 128, 3)
    np.testing.assert_allclose(returned_matrix, matrix)


def test_model_resolution_prefers_bundle_and_supports_optional(tmp_path: Path):
    onnx_path = tmp_path / "model.onnx"
    onnx_path.write_bytes(b"development-only")
    assert resolve_model(tmp_path, "model.onnx") == onnx_path

    bundle_path = tmp_path / "model.omlx"
    bundle_path.mkdir()
    (bundle_path / "graph.json").write_text("{}", encoding="utf-8")
    (bundle_path / "weights.safetensors").write_bytes(b"bundle")
    assert resolve_model(tmp_path, "model.onnx") == bundle_path
    assert resolve_model(tmp_path, "missing.onnx", optional=True) is None
    with pytest.raises(FileNotFoundError, match="missing model"):
        resolve_model(tmp_path, "missing.onnx")


def test_bundle_manifest_verifier_detects_corruption(tmp_path: Path):
    bundle = tmp_path / "model.omlx"
    bundle.mkdir()
    contents = {"graph.json": b"{}\n", "weights.safetensors": b"weights"}
    for filename, value in contents.items():
        (bundle / filename).write_bytes(value)
    manifest = {
        "schema_version": 1,
        "format": "ai2apps.omlx.graph",
        "graph": {
            "filename": "graph.json",
            "size": len(contents["graph.json"]),
            "sha256": hashlib.sha256(contents["graph.json"]).hexdigest(),
        },
        "weights": {
            "filename": "weights.safetensors",
            "size": len(contents["weights.safetensors"]),
            "sha256": hashlib.sha256(contents["weights.safetensors"]).hexdigest(),
        },
    }
    (bundle / "bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_bundle(bundle)["valid"] is True
    (bundle / "graph.json").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="integrity mismatch"):
        verify_bundle(bundle)
