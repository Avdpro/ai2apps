import asyncio
import importlib.util
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

from ai2apps.model_worker import ModelWorkerError, ModelWorkerPart, ModelWorkerRequest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def adapter_module(monkeypatch):
    source = ROOT / "packages/ai2apps-model-avtr1-mlx/src"
    monkeypatch.syspath_prepend(str(source))
    spec = importlib.util.spec_from_file_location(
        "avtr_adapter_test", source / "worker_adapter.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "validate_checkpoint", lambda path: path)
    return module


@pytest.fixture
def worker_request(tmp_path):
    image = tmp_path / "portrait.png"
    audio = tmp_path / "speech.wav"
    Image.new("RGB", (64, 64)).save(image)
    sf.write(audio, np.zeros(6400, np.float32), 16000)
    parts = {
        name: ModelWorkerPart(name, path, mime, path.name, path.stat().st_size, "")
        for name, path, mime in [
            ("reference_00_image", image, "image/png"),
            ("audio", audio, "audio/wav"),
        ]
    }
    return ModelWorkerRequest(
        request_id="test",
        operation="video_generation",
        payload={
            "model": "ai2apps.model.avtr1-mlx/default",
            "reference_parts": '[{"kind":"image","part_name":"reference_00_image"}]',
        },
        parts=parts,
        output_root=tmp_path,
    )


def context(tmp_path, installed=True):
    return SimpleNamespace(
        models=[{"id": "ai2apps.model.avtr1-mlx/default", "upstream_id": "AVTR-1-MLX"}],
        checkpoint_for=lambda _: (
            SimpleNamespace(path=tmp_path, revision="test") if installed else None
        ),
    )


@pytest.mark.asyncio
async def test_missing_weights_health_and_structured_error(
    adapter_module, worker_request, tmp_path
):
    adapter = adapter_module.AVTRAdapter(
        context(tmp_path, False), pipeline_factory=object
    )
    await adapter.start()
    with pytest.raises(ModelWorkerError) as error:
        await adapter.invoke(worker_request)
    assert error.value.code == "model_unavailable"
    await adapter.stop()


def test_multipart_and_audio_bounds(adapter_module, worker_request):
    image, audio, seed, frames, preset = adapter_module.AVTRAdapter._inputs(
        worker_request
    )
    assert image == worker_request.parts["reference_00_image"].path
    assert frames == 10 and preset == "standard"
    worker_request.payload["seed"] = "-1"
    with pytest.raises(ValueError):
        adapter_module.AVTRAdapter._inputs(worker_request)


@pytest.mark.asyncio
async def test_cancel_waits_for_native_thread(adapter_module, worker_request, tmp_path):
    started = threading.Event()
    exited = threading.Event()

    class Pipeline:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, *args, cancel_check, **kwargs):
            started.set()
            try:
                while True:
                    cancel_check()
                    threading.Event().wait(0.01)
            finally:
                exited.set()

    adapter = adapter_module.AVTRAdapter(context(tmp_path), pipeline_factory=Pipeline)
    await adapter.start()
    task = asyncio.create_task(adapter.invoke(worker_request))
    assert await asyncio.to_thread(started.wait, 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert exited.is_set()
    assert not adapter._tokens
    await adapter.stop()


@pytest.mark.asyncio
async def test_progress_and_output_contract(adapter_module, worker_request, tmp_path):
    class Pipeline:
        def __init__(self, *args, **kwargs):
            assert kwargs["output_mode"] == "source"

        def generate(self, image, audio, output, *, progress, seconds, **kwargs):
            assert seconds == 0.4
            output.write_bytes(b"fixture")
            progress(10, 10)

    adapter = adapter_module.AVTRAdapter(context(tmp_path), pipeline_factory=Pipeline)
    artifact = await adapter.invoke(worker_request)
    assert artifact.media_type == "video/mp4" and artifact.metadata["frame_count"] == 10
    assert artifact.metadata["width"] == 512
    await adapter.stop()
