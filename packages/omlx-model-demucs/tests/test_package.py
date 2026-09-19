from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mlx_demucs.audio import AudioBuffer  # noqa: E402
from mlx_demucs.backends import OracleMaskBackend  # noqa: E402
from mlx_demucs.pipeline import SeparationConfig, separate_audio  # noqa: E402


def test_manifest_identity_and_pinned_dual_sources():
    manifest = json.loads((ROOT / "ai2apps.json").read_text())
    assert manifest["package"]["id"] == "ai2apps/model-demucs-mlx"
    assert manifest["package"]["version"] == "0.1.0"
    spec = json.loads((ROOT / "META/checkpoint-distribution.json").read_text())
    assert {item["type"] for item in spec["sourceRepositories"]} == {
        "huggingface",
        "modelscope",
    }
    assert all(len(item["revision"]) == 40 for item in spec["sourceRepositories"])


def test_pipeline_writes_relative_manifest_paths(tmp_path):
    rate = 8_000
    frames = rate // 10
    values = np.zeros((2, frames), dtype=np.float32)
    audio = AudioBuffer(values, rate)
    backend = OracleMaskBackend(np.ones(frames), rate, 2)
    result = separate_audio(
        audio,
        tmp_path,
        backend=backend,
        config=SeparationConfig(profile="vocals_instrumental", float32_wav=False),
    )
    assert [stem.path for stem in result.stems] == ["vocals.wav", "instrumental.wav"]
    payload = json.loads((tmp_path / "separation.json").read_text())
    assert all("/" not in stem["path"] for stem in payload["stems"])


def test_worker_adapter_is_importable():
    spec = importlib.util.spec_from_file_location(
        "demucs_worker_adapter", ROOT / "src/worker_adapter.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert callable(module.create_adapter)
