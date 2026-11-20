from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CUDA_PACKAGES = (
    "ai2apps-model-qwen25-0.5b-cuda",
    "ai2apps-model-qwen3-asr-0.6b-cuda",
    "ai2apps-model-qwen3-vl-2b-cuda",
    "ai2apps-model-qwen38-cuda",
    "ai2apps-model-qwen38-flash-next-cuda",
)


def _manifest(name: str) -> dict:
    return yaml.safe_load((ROOT / "packages" / name / "service.yaml").read_text())


def test_cuda_models_are_pinned_offline_workers() -> None:
    for name in CUDA_PACKAGES:
        manifest = _manifest(name)
        assert manifest["runtime"]["provider"] == "ai2apps.runtime.cuda-torch"
        assert manifest["permissions"]["network"]["outbound"] is False
        assert manifest["permissions"]["accelerator"]["cuda"] is True
        for model in manifest["models"]:
            revision = model["weights"]["revision"]
            assert len(revision) == 40
            assert all(character in "0123456789abcdef" for character in revision)


def test_spark_cuda_categories_cover_chat_vision_and_asr() -> None:
    model_types = {
        model["model_type"]
        for package in CUDA_PACKAGES
        for model in _manifest(package)["models"]
    }
    assert {"llm", "vlm", "audio_stt"} <= model_types


def test_cuda_runtime_declares_the_shared_base_capabilities() -> None:
    runtime = _manifest("ai2apps-runtime-cuda-torch")
    assert runtime["version"] == "0.5.0"
    assert {"llm", "vlm", "audio-stt"} <= set(runtime["capabilities"])


def test_qwen38_preserves_cross_platform_checkpoint_identity_and_requires_new_runtime():
    cuda = _manifest("ai2apps-model-qwen38-cuda")
    mac = _manifest("omlx-model-qwen38")
    assert cuda["id"] == mac["id"]
    assert cuda["models"][0]["id"] == mac["models"][0]["id"]
    assert cuda["models"][0]["weights"] == mac["models"][0]["weights"]
    assert cuda["models"][0]["context_window"] == 8192
    assert cuda["models"][0]["metadata"]["native_nvfp4"] is True
    required = set(cuda["requires"]["services"][0]["capabilities"])
    assert "nvfp4-sm121" in required
    assert cuda["requires"]["services"][0]["version"] == ">=0.3.0,<1.0.0"
    assert required <= set(_manifest("ai2apps-runtime-cuda-torch")["capabilities"])


def test_flash_cuda_preserves_identity_but_uses_native_disk_layout():
    cuda = _manifest("ai2apps-model-qwen38-flash-next-cuda")
    mac = _manifest("omlx-model-qwen38-flash-next-4bit")
    assert cuda["id"] == mac["id"]
    assert cuda["models"][0]["id"] == mac["models"][0]["id"]
    for key in ("repo_id", "revision", "distribution_id"):
        assert cuda["models"][0]["weights"][key] == mac["models"][0]["weights"][key]
    assert cuda["models"][0]["weights"]["preparation"] == {"recipe": "native"}
    assert cuda["models"][0]["metadata"]["development_status"] == "experimental-parity-pending"
