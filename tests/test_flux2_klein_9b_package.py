import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from ai2apps.packages.discovery import legacy_model_install


ROOT = Path(__file__).resolve().parents[1] / "packages/ai2apps-model-flux2-klein-9b-mlx"


def test_independent_model_identity():
    manifest = json.loads((ROOT / "ai2apps.json").read_text())
    service = yaml.safe_load((ROOT / "service.yaml").read_text())
    assert manifest["package"]["id"] == "ai2apps/model-flux2-klein-9b-mlx"
    assert service["id"] == manifest["modelInstall"]["serviceKey"]
    assert len(service["models"]) == 1
    assert service["models"][0]["id"] == manifest["modelInstall"]["models"][0]["id"]
    assert service["models"][0]["upstream_id"] == "black-forest-labs/FLUX.2-klein-9B"
    assert legacy_model_install(manifest["package"]["id"], "0.1.0")
    assert legacy_model_install(manifest["package"]["id"], "0.1.1") is None


def test_adapter_rejects_4b():
    spec = importlib.util.spec_from_file_location("flux9b_test", ROOT / "src/worker_adapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Flux2KleinAdapter._model({"model": "black-forest-labs/FLUX.2-klein-9B"})[:2] == (
        "9b", "ai2apps.model.flux2-klein-9b-mlx/9b"
    )
    with pytest.raises(module.ModelWorkerError):
        module.Flux2KleinAdapter._model({"model": "black-forest-labs/FLUX.2-klein-4B"})


def test_weight_license_and_sources():
    import hashlib
    spec = json.loads((ROOT / "META/checkpoint-distribution-9b.json").read_text())
    license = spec["license"]
    assert license["redistributionPolicy"] == "conditional"
    assert license["redistributionConditions"]["commercialUse"] == "separate_license_required"
    assert license["downloadConsent"]["required"] is True
    assert license["redistributionConditions"]["licenseDelivery"] == "required"
    assert license["id"] == "LicenseRef-FLUX-Non-Commercial"
    assert license["termsHash"] == "sha256:" + hashlib.sha256(license["termsText"].encode()).hexdigest()
    assert {s["type"] for s in spec["sourceRepositories"]} == {"huggingface", "modelscope"}
    assert all(len(s["revision"]) == 40 for s in spec["sourceRepositories"])
