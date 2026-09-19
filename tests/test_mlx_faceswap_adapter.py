from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai2apps.model_worker import ModelWorkerError

PACKAGE_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "omlx-model-face-swap"
    / "src"
)
sys.path.insert(0, str(PACKAGE_SOURCE))

from mlx_faceswap.worker_adapter import (  # noqa: E402
    CHECKPOINT_SCHEMA,
    MINIMUM_MEMORY_BYTES,
    MLXFaceSwapAdapter,
    UnsupportedControlError,
)


def test_face_swap_video_defaults_select_realtime_profile():
    parameters = MLXFaceSwapAdapter._parameters({}, "video_generation")
    assert parameters == {
        "precision": "fp16",
        "track_id": None,
        "detection_interval": 1,
        "batch_size": 2,
        "velocity_smoothing": 0.5,
        "audio_output_mode": "auto",
    }


def test_face_swap_image_defaults_do_not_claim_video_controls():
    parameters = MLXFaceSwapAdapter._parameters({}, "image_edit")
    assert parameters["detection_interval"] == 1
    assert parameters["batch_size"] == 1
    assert parameters["audio_output_mode"] == "none"


@pytest.mark.parametrize(
    "operation,parameters,message",
    [
        ("video_generation", {"precision": "bf16"}, "precision"),
        ("video_generation", {"mask_mode": "box"}, "mask_mode"),
        ("video_generation", {"detection_interval": 0}, "detection_interval"),
        ("video_generation", {"batch_size": 9}, "batch_size"),
        ("video_generation", {"track_id": 0}, "track_id"),
        ("image_edit", {"track_id": 1}, "track_id"),
        ("image_edit", {"output_format": "jpeg"}, "output_format=png"),
    ],
)
def test_face_swap_adapter_rejects_invalid_or_ignored_controls(
    operation, parameters, message
):
    error = ValueError if message in {
        "detection_interval",
        "batch_size",
        "track_id",
    } else UnsupportedControlError
    with pytest.raises(error, match=message):
        MLXFaceSwapAdapter._parameters(parameters, operation)


def _checkpoint(tmp_path: Path, schema: str = CHECKPOINT_SCHEMA) -> Path:
    root = tmp_path / "checkpoint"
    (root / "models").mkdir(parents=True)
    (root / "ai2apps-checkpoint.json").write_text(
        json.dumps(
            {
                "schema": schema,
                "components": {
                    "detector": "models/face_detection_yunet_2023mar.omlx",
                    "recognizer": "models/ghostv2_cvlface.omlx",
                    "generator": "models/ghostv2_generator.native",
                },
            }
        ),
        encoding="utf-8",
    )
    for name in ("face_detection_yunet_2023mar.omlx", "ghostv2_cvlface.omlx"):
        model = root / "models" / name
        model.mkdir()
        for filename in ("bundle.json", "graph.json", "weights.safetensors"):
            (model / filename).touch()
    generator = root / "models" / "ghostv2_generator.native"
    generator.mkdir()
    for filename in ("config.json", "weights.safetensors"):
        (generator / filename).touch()
    return root


def test_face_swap_adapter_accepts_complete_checkpoint_layout(tmp_path):
    root = _checkpoint(tmp_path)
    context = SimpleNamespace(
        checkpoint_for=lambda model_id: SimpleNamespace(path=root)
    )
    adapter = MLXFaceSwapAdapter(context)
    assert adapter._ensure_checkpoint("test/model") == root


def test_face_swap_adapter_rejects_wrong_checkpoint_schema(tmp_path):
    root = _checkpoint(tmp_path, schema="wrong")
    context = SimpleNamespace(
        checkpoint_for=lambda model_id: SimpleNamespace(path=root)
    )
    adapter = MLXFaceSwapAdapter(context)
    with pytest.raises(ModelWorkerError, match="layout is unsupported"):
        adapter._ensure_checkpoint("test/model")


def test_face_swap_adapter_rejects_below_memory_floor(monkeypatch):
    monkeypatch.setattr(
        "mlx_faceswap.worker_adapter._physical_memory_bytes",
        lambda: MINIMUM_MEMORY_BYTES - 1,
    )
    with pytest.raises(ModelWorkerError, match="at least 16 GiB") as captured:
        MLXFaceSwapAdapter._require_supported_memory()
    assert captured.value.code == "insufficient_resources"
