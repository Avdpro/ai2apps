import importlib.util
from pathlib import Path

import pytest
import yaml

from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.contract_v1 import build_package, inspect_package
from ai2apps.packages.discovery import legacy_model_discovery, legacy_model_profile
from experiments.mlx_whisperx.stage_package_candidate import stage


def test_candidate_stages_self_contained_runtime_source(tmp_path: Path):
    destination = stage(tmp_path / "candidate")
    assert (destination / "src/worker_adapter.py").is_file()
    assert (destination / "src/mlx_whisperx/service.py").is_file()
    assert not (destination / ".models").exists()
    assert not (destination / ".artifacts").exists()


def test_candidate_contract_is_supported_and_not_chat_eligible():
    root = Path(__file__).resolve().parents[1] / "package_candidate"
    raw = yaml.safe_load((root / "service.yaml").read_text(encoding="utf-8"))
    public = [item for item in raw["models"] if not item["metadata"].get("internal")]

    assert {item["model_type"] for item in public} == {
        "audio_detailed_transcription"
    }
    assert all(item["metadata"]["chat_eligible"] is False for item in public)
    assert all(
        item["metadata"]["operation_class"] == "audio_detailed_transcription"
        for item in public
    )
    assert all(
        item["audio_capabilities"]["operations"]
        == ["audio_detailed_transcription"]
        for item in public
    )
    assert all(item["metadata"]["modelscope"]["revision"] for item in raw["models"])
    assert raw["models"][0]["weights"]["distribution_id"] == (
        "dist_ai2apps_detailed_transcription_qwen3_asr_0_6b_4bit_313d8501_v1"
    )
    assert all(item["weights"].get("distribution_id") for item in raw["models"])
    required = raw["requires"]["services"][0]["capabilities"]
    assert "audio-detailed-transcription-v1" in required
    assert raw["requires"]["services"][0]["version"] == ">=1.6.0,<2.0.0"
    manifest = ServicePackageArchive._manifest(raw)
    assert {item["model_type"] for item in manifest.models} == {
        "audio_detailed_transcription",
        "audio_processing",
    }


def test_candidate_builds_as_weightless_contract_v1_package(tmp_path: Path):
    source = stage(tmp_path / "source")
    artifact = tmp_path / "mlx-whisperx.ai2service"

    built = build_package(source, artifact)
    inspected = inspect_package(artifact)

    assert built.sha256 == inspected.sha256
    assert inspected.manifest["package"] == {
        "id": "ai2apps/model-detailed-transcription-mlx",
        "type": "service",
        "version": "0.1.2",
        "displayName": "MLX WhisperX Detailed Transcription",
        "description": (
            "Standalone subtitle and meeting transcription with Qwen3 ASR, "
            "forced alignment, VAD, and anonymous diarization. Not a Chat STT model."
        ),
    }
    discovery = legacy_model_discovery(
        inspected.manifest["package"]["id"], inspected.manifest["package"]["version"]
    )
    assert discovery is not None
    assert discovery["tasks"] == [
        "detailed-transcription",
        "speaker-diarization",
        "subtitle-generation",
    ]
    profile = legacy_model_profile(
        inspected.manifest["package"]["id"], inspected.manifest["package"]["version"]
    )
    assert profile is not None
    assert profile["sizeBytes"] == 3832992557
    assert not any("model.safetensors" in row.path for row in inspected.files)


def test_worker_adapter_accepts_multipart_boolean_strings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    root = stage(tmp_path / "candidate")
    monkeypatch.syspath_prepend(str(root / "src"))
    spec = importlib.util.spec_from_file_location(
        "detailed_transcription_worker_adapter", root / "src/worker_adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._enabled("true") is True
    assert module._enabled("false", default=True) is False
    with pytest.raises(Exception, match="Boolean feature value is invalid"):
        module._enabled("sometimes")
