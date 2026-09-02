from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
import pytest
import soundfile as sf
import yaml
from echomimic_mlx.media import write_mp4_chunks_with_audio

from ai2apps.model_worker import ModelWorkerError, ModelWorkerPart, ModelWorkerRequest

PACKAGE = Path(__file__).resolve().parents[1]


def test_package_binds_the_published_dual_source_distribution():
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    package = json.loads((PACKAGE / "ai2apps.json").read_text())
    source_lock = json.loads((PACKAGE / "META/source-lock.json").read_text())
    distribution = json.loads(
        (PACKAGE / "META/checkpoint-distribution.json").read_text()
    )

    model = service["models"][0]
    assert service["version"] == package["package"]["version"] == "0.1.1"
    assert model["weights"]["distribution_id"] == distribution["distributionId"]
    assert model["weights"]["repo_id"] == "Avdpro/EchoMimicV3-MLX"
    assert model["weights"]["revision"] == distribution["revision"]
    assert source_lock["checkpoint_publication"]["status"] == "published"
    assert {
        item["type"] for item in distribution["sourceRepositories"]
    } == {"huggingface", "modelscope"}


def _adapter_module():
    spec = importlib.util.spec_from_file_location(
        "echomimic_worker_adapter", PACKAGE / "src" / "worker_adapter.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checkpoint_manifest_matches_the_runtime_layout():
    spec = importlib.util.spec_from_file_location(
        "echomimic_checkpoint_manifest", PACKAGE / "scripts" / "build_checkpoint_manifest.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert "config.json" not in module.FILES
    assert set(module.FILES) >= {
        "echomimicv3-flash-pro/config.json",
        "echomimicv3-flash-pro/diffusion_pytorch_model.safetensors",
        "Wan2.1_VAE.safetensors",
        "models_t5_umt5-xxl-enc-bf16-local.safetensors",
        "models_clip_open-clip-xlm-roberta-large-vit-huge-14.safetensors",
        "umt5-xxl/tokenizer.json",
        "chinese-wav2vec2-base/model.safetensors",
    }


def _checkpoint(root: Path) -> Path:
    checkpoint = root / "checkpoint"
    files = (
        "echomimicv3-flash-pro/diffusion_pytorch_model.safetensors",
        "Wan2.1_VAE.safetensors",
        "models_t5_umt5-xxl-enc-bf16-local.safetensors",
        "models_clip_open-clip-xlm-roberta-large-vit-huge-14.safetensors",
        "chinese-wav2vec2-base/model.safetensors",
    )
    for name in files:
        path = checkpoint / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    (checkpoint / "umt5-xxl").mkdir()
    (checkpoint / "ai2apps-checkpoint.json").write_text(json.dumps({
        "schema": "ai2apps.echomimic-mlx-checkpoint/v1"
    }))
    return checkpoint


def test_pyav_writer_streams_h264_aac(tmp_path):
    audio = tmp_path / "audio.wav"
    output = tmp_path / "avatar.mp4"
    sf.write(audio, np.zeros(16_000, dtype=np.float32), 16_000, subtype="FLOAT")
    chunks = [
        np.zeros((2, 32, 32, 3), dtype=np.float32),
        np.full((2, 32, 32, 3), 0.25, dtype=np.float32),
    ]

    assert write_mp4_chunks_with_audio(chunks, audio, output, fps=25) == output

    with av.open(str(output)) as container:
        assert container.streams.video[0].codec_context.name == "h264"
        assert container.streams.audio[0].codec_context.name == "aac"
        assert sum(1 for _ in container.decode(video=0)) == 4


@pytest.mark.asyncio
async def test_adapter_starts_without_checkpoint_and_reports_request_503(tmp_path):
    module = _adapter_module()

    class Context:
        data_root = tmp_path

        def checkpoint_for(self, _model_id):
            return SimpleNamespace(path=None)

    adapter = module.EchoMimicAdapter(Context())
    await adapter.start()
    request = ModelWorkerRequest(
        operation="video_generation",
        payload={},
        request_id="missing-checkpoint",
        output_root=tmp_path,
    )
    with pytest.raises(ModelWorkerError) as error:
        await adapter.invoke(request)
    assert error.value.code == "model_unavailable"
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_adapter_routes_exact_request_to_controlled_artifact(tmp_path):
    module = _adapter_module()
    checkpoint = _checkpoint(tmp_path)
    image = tmp_path / "avatar.png"
    audio = tmp_path / "speech.wav"
    image.write_bytes(b"image")
    audio.write_bytes(b"wav")
    output_root = tmp_path / "output"
    output_root.mkdir()
    data_root = tmp_path / "data"
    data_root.mkdir()

    class Context:
        def checkpoint_for(self, _model_id):
            return SimpleNamespace(path=checkpoint)

    Context.data_root = data_root

    calls = []

    class Pipeline:
        def generate_to_file(self, request, output, **kwargs):
            calls.append((request, output, kwargs))
            kwargs["progress"]("denoise", 1, 8)
            Path(output).write_bytes(b"mp4")

        def clear_condition_cache(self):
            pass

    module.select_memory_profile = lambda: SimpleNamespace(
        cache_conditions=False, validate=lambda _request: None
    )
    adapter = module.EchoMimicAdapter(
        Context(), pipeline_factory=lambda *_args, **_kwargs: Pipeline()
    )
    await adapter.start()
    updates = []

    async def progress(value):
        updates.append(dict(value))

    request = ModelWorkerRequest(
        operation="video_generation",
        payload={
            "inputs": {
                "reference_image": {"part_name": "image"},
                "driving_audio": {"part_name": "audio"},
                "prompt": "A person is speaking.",
            },
            "parameters": {"preset": "exact", "width": 512, "height": 512},
        },
        request_id="avatar-1",
        parts={
            "image": ModelWorkerPart("image", image, "image/png", "avatar.png", 5, "sha256:x"),
            "audio": ModelWorkerPart("audio", audio, "audio/wav", "speech.wav", 3, "sha256:y"),
        },
        output_root=output_root,
        progress=progress,
    )

    artifact = await adapter.invoke(request)
    await asyncio.sleep(0)

    assert artifact.path.read_bytes() == b"mp4"
    assert artifact.metadata["audio_output_mode"] == "preserve_driving_audio"
    assert calls[0][2]["checkpoint_path"].is_relative_to(data_root)
    assert updates == [{"phase": "denoise", "current": 1, "total": 8}]
