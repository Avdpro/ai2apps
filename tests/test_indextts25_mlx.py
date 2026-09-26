# SPDX-License-Identifier: Apache-2.0
"""IndexTTS 2.5 structured controls and Torch-free MLX runtime tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from ai2apps.model_worker import ModelWorkerError


ROOT = Path(__file__).resolve().parents[1]


def _adapter_module():
    path = ROOT / "packages/omlx-model-indextts25/src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("indextts25_worker_adapter", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_indextts25_adapter_maps_speed_emotion_and_language():
    module = _adapter_module()
    adapter = module.IndexTTS25Adapter.__new__(module.IndexTTS25Adapter)
    options = adapter.synthesis_options(
        "ai2apps.model.indextts25/fp16",
        {"input": "今天很好。", "language": "auto"},
        speed=1.25,
        emotion="happy",
        emotion_strength=0.5,
        instructions=None,
    )

    assert options["speed"] == 1.0
    assert options["duration_factor"] == pytest.approx(0.8)
    assert options["language"] == "ZH"
    assert options["emotion_strength"] == pytest.approx(0.5)
    assert len(options["emotion_vector"]) == 8
    assert sum(options["emotion_vector"]) <= 0.8
    assert options["emotion_vector"][0] > 0


def test_indextts25_adapter_neutral_uses_reference_emotion_path():
    module = _adapter_module()
    adapter = module.IndexTTS25Adapter.__new__(module.IndexTTS25Adapter)
    options = adapter.synthesis_options(
        "ai2apps.model.indextts25/fp16",
        {"input": "Hello.", "language": "en-US"},
        speed=1.0,
        emotion="neutral",
        emotion_strength=1.0,
        instructions=None,
    )
    assert options["language"] == "EN"
    assert options["emotion_vector"] is None


def test_indextts25_adapter_rejects_unpublished_language():
    module = _adapter_module()
    adapter = module.IndexTTS25Adapter.__new__(module.IndexTTS25Adapter)
    with pytest.raises(ModelWorkerError, match="does not support language"):
        adapter.synthesis_options(
            "ai2apps.model.indextts25/fp16",
            {"input": "Hola.", "language": "es"},
            speed=1.0,
            emotion=None,
            emotion_strength=1.0,
            instructions=None,
        )


def test_indextts25_runtime_source_is_torch_free_and_forwards_native_controls():
    vendor = ROOT / "omlx/vendor/indextts25"
    runtime_sources = [
        path.read_text(encoding="utf-8")
        for path in vendor.rglob("*.py")
        if path.name != "NOTICE.md"
    ]
    joined = "\n".join(runtime_sources)
    assert "import torch" not in joined
    assert "import torchaudio" not in joined

    engine = (ROOT / "omlx/engine/indextts25.py").read_text(encoding="utf-8")
    assert '"duration_factor": 1.0 / speed' not in engine
    assert "duration_factor=duration_factor" in engine
    assert "emo_vector=effective_vector" in engine
    assert "enable_emo_ref=True" in engine
    assert "audio_to_wav_bytes(waveform, int(sample_rate))" in engine

    inference = (vendor / "inference.py").read_text(encoding="utf-8")
    assert "Reference audio exceeds the" in inference
    assert "np.sinc(t / math.pi)" in (vendor / "ops.py").read_text(encoding="utf-8")


def test_indextts25_conversion_recipe_is_pinned_and_excludes_qwen_emotion_weights():
    recipe = (
        ROOT / "scripts/convert_indextts25_mlx_checkpoint.py"
    ).read_text(encoding="utf-8")
    assert "d0aa86e75bb6f3437f3831e95056fa72842d89ef" in recipe
    assert "eafb98c1b2ba46f6a608f29d8831208b89047681" in recipe
    assert "633ff708ed5b74903e86ff1298cf4a98e921c513" in recipe
    assert '(output / "qwen_tokenizer.json").unlink(missing_ok=True)' in recipe
    assert 'models=("gpt", "codec", "s2mel", "bigvgan", "campplus", "w2v_bert")' in recipe
