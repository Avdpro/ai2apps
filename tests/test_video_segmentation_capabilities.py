from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from ai2apps.model_providers import validate_package_models
from ai2apps.model_worker.video_segmentation_capabilities import (
    VideoSegmentationCapabilitiesError,
    validate_video_segmentation_capabilities,
)
from ai2apps.packages.archive import ServicePackageArchive

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "ai2apps-model-sam21-mlx"


def test_video_segmentation_capabilities_are_strict_and_normalized():
    value = validate_video_segmentation_capabilities(
        {
            "schema": "ai2apps.video-segmentation-capabilities/v1",
            "operations": ["video_segmentation"],
            "prompt_types": ["point"],
            "output_formats": ["mp4"],
            "maximum_seconds": 18.75,
            "soft_masks": True,
        }
    )
    assert value["soft_masks"] is True
    assert value["multi_object"] is False
    with pytest.raises(VideoSegmentationCapabilitiesError):
        validate_video_segmentation_capabilities({"schema": "wrong"})


def test_sam21_package_contract_uses_pinned_external_weights_and_new_runtime():
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    parsed = ServicePackageArchive._manifest(service)
    assert parsed.service_key == "ai2apps.model.sam21-mlx"
    assert parsed.protocol == "ai2apps-model-worker/v1"
    model = parsed.models[0]
    assert model["model_type"] == "video_segmentation"
    assert model["endpoints"]["video_segmentation"] == "/v1/videos/segmentations"
    assert model["weights"]["revision"] == "1b7b98828e383e3d64025b615aff049b1face026"
    assert model["video_segmentation_capabilities"]["soft_masks"] is True
    assert not list(PACKAGE.rglob("*.safetensors"))
    outer = json.loads((PACKAGE / "ai2apps.json").read_text())
    assert outer["dependencies"][0]["version"].startswith(">=1.8.6")


def test_model_contract_accepts_video_segmentation_type():
    models = validate_package_models(
        "example.segmenter",
        [
            {
                "id": "example.segmenter/small",
                "display_name": "Small",
                "model_type": "video_segmentation",
                "upstream_id": "example/small",
                "video_segmentation_capabilities": {
                    "schema": "ai2apps.video-segmentation-capabilities/v1",
                    "operations": ["video_segmentation"],
                    "prompt_types": ["point"],
                    "output_formats": ["mp4"],
                    "maximum_seconds": 10,
                },
            }
        ],
        runtime_mode="managed_process",
        protocol="ai2apps-model-worker/v1",
    )
    assert models[0]["video_segmentation_capabilities"]["operations"] == [
        "video_segmentation"
    ]


def test_sam21_worker_validates_prompts_without_loading_model(monkeypatch):
    monkeypatch.syspath_prepend(str(PACKAGE / "src"))
    # Packages intentionally share the worker_adapter filename. Do not reuse
    # another package's cached module when the entire test suite runs together.
    spec = importlib.util.spec_from_file_location(
        "sam21_worker_adapter_test", PACKAGE / "src" / "worker_adapter.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    SAM21Adapter = module.SAM21Adapter

    frame, points, labels, threshold, feather = SAM21Adapter._parameters(
        {
            "parameters": json.dumps(
                {
                    "prompt_frame": 2,
                    "points": [
                        {"x": 120.5, "y": 80, "label": 1},
                        {"x": 160, "y": 90, "label": 0},
                    ],
                    "threshold": 0.4,
                    "feather": 2,
                }
            )
        }
    )
    assert frame == 2
    assert points.shape == (2, 2)
    assert labels.tolist() == [1, 0]
    assert (threshold, feather) == (0.4, 2.0)


def test_package_cv2_shim_resizes_and_labels(monkeypatch):
    monkeypatch.syspath_prepend(str(PACKAGE / "src"))
    sys.modules.pop("cv2", None)
    import cv2

    source = np.zeros((4, 5), np.float32)
    source[1:3, 1:4] = 1
    resized = cv2.resize(source, (10, 8), interpolation=cv2.INTER_LINEAR)
    assert resized.shape == (8, 10)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(source, connectivity=4)
    assert count == 2
    assert stats[1, cv2.CC_STAT_AREA] == 6
    assert labels.shape == source.shape
