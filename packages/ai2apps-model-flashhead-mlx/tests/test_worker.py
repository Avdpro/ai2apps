import asyncio
import hashlib
import importlib.util
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
import yaml
from PIL import Image
from ai2apps.model_worker import ModelWorkerError, ModelWorkerPart, ModelWorkerRequest
from ai2apps.model_worker.video_capabilities import validate_video_capabilities

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "src"))
from flashhead_mlx.checkpoint import SCHEMA, required_files, validate_checkpoint

spec = importlib.util.spec_from_file_location(
    "flashhead_test_worker", PACKAGE / "src/worker_adapter.py"
)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def setup(tmp_path, factory, missing=False):
    roots = {}
    models = []
    for variant in ["lite", "pro"]:
        root = tmp_path / variant
        root.mkdir()
        entries = []
        for name in required_files(variant):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"fixture")
            entries.append(
                {
                    "path": name,
                    "size": 7,
                    "sha256": hashlib.sha256(b"fixture").hexdigest(),
                }
            )
        (root / "ai2apps-checkpoint.json").write_text(
            json.dumps({"schema": SCHEMA, "variant": variant, "files": entries})
        )
        model_id = worker.SERVICE_ID + "/" + variant
        roots[model_id] = root
        models.append({"id": model_id, "upstream_id": "test-" + variant})
    context = SimpleNamespace(
        models=models,
        checkpoint_for=lambda model: (
            None if missing else SimpleNamespace(path=roots[model], revision="fixed")
        ),
    )
    adapter = worker.FlashHeadAdapter(context, pipeline_factory=factory)
    picture = tmp_path / "image.png"
    Image.new("RGB", (32, 32)).save(picture)
    audio = tmp_path / "audio.wav"
    sf.write(audio, np.zeros(641), 16000)
    parts = {
        n: ModelWorkerPart(n, p, m, p.name, p.stat().st_size, "")
        for n, p, m in [
            ("reference_00_image", picture, "image/png"),
            ("audio", audio, "audio/wav"),
        ]
    }

    def request(variant="lite", request_id="job", **values):
        return ModelWorkerRequest(
            "video_generation",
            {
                "model": "test-" + variant,
                "reference_parts": [
                    {"kind": "image", "part_name": "reference_00_image"}
                ],
                **values,
            },
            request_id,
            parts,
            tmp_path,
        )

    return adapter, request, roots


class FakePipeline:
    variants = []

    def __init__(self, root, wav, variant):
        self.variants.append(variant)

    def generate(self, image, audio, output, *, cancel_check, progress, **kwargs):
        cancel_check()
        progress(1, 4)
        output.write_bytes(b"rendered")
        cancel_check()


def test_variants_and_reuse(tmp_path):
    FakePipeline.variants = []
    adapter, request, _ = setup(tmp_path, FakePipeline)

    async def run():
        await adapter.start()
        for variant in ["lite", "lite", "pro", "lite"]:
            result = await adapter.invoke(request(variant))
            assert result.metadata["frame_count"] == 2
            assert result.metadata["variant"] == variant
            assert result.path.parent == tmp_path
        await adapter.stop()

    asyncio.run(run())
    assert FakePipeline.variants == ["lite", "pro", "lite"]


@pytest.mark.parametrize(
    "values",
    [
        {"width": 256},
        {"fps": 30},
        {"preset": "fast"},
        {"seed": True},
        {"steps": 2},
        {"prompt": "ignored text"},
        {"reference_parts": [{"kind": "video", "part_name": "reference_00_image"}]},
    ],
)
def test_invalid_requests_never_load(tmp_path, values):
    def factory(*a, **kw):
        pytest.fail("loaded invalid request")

    adapter, request, _ = setup(tmp_path, factory)
    with pytest.raises(ModelWorkerError):
        asyncio.run(adapter.invoke(request(**values)))


def test_missing_checkpoint_health(tmp_path):
    adapter, request, _ = setup(tmp_path, FakePipeline, missing=True)
    asyncio.run(adapter.start())
    with pytest.raises(ModelWorkerError) as error:
        asyncio.run(adapter.invoke(request()))
    assert error.value.code == "model_unavailable"


def test_wrong_variant_and_missing_file(tmp_path):
    _, _, roots = setup(tmp_path, FakePipeline)
    root = roots[worker.SERVICE_ID + "/lite"]
    with pytest.raises(ValueError):
        validate_checkpoint(root, "pro")
    (root / "wav2vec2/config.json").unlink()
    with pytest.raises(OSError):
        validate_checkpoint(root, "lite")


def test_request_id_cannot_escape_output_root(tmp_path):
    adapter, request, _ = setup(tmp_path, FakePipeline)
    output = asyncio.run(adapter.invoke(request(request_id="../../escape")))
    assert output.path.parent == tmp_path and output.path.name.startswith("flashhead-")


def test_cancellation_waits_for_thread(tmp_path):
    started = threading.Event()
    stopped = threading.Event()

    class Slow(FakePipeline):
        def generate(self, image, audio, output, *, cancel_check, **kw):
            started.set()
            try:
                while True:
                    cancel_check()
                    threading.Event().wait(0.005)
            finally:
                stopped.set()

    adapter, request, _ = setup(tmp_path, Slow)

    async def run():
        task = asyncio.create_task(adapter.invoke(request()))
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set()
        assert adapter._tokens == {}
        await adapter.stop()

    asyncio.run(run())
    assert not list(tmp_path.glob("*.mp4"))


def test_explicit_cancel(tmp_path):
    class Cancel(FakePipeline):
        def generate(self, *args, cancel_check, **kwargs):
            adapter.cancel("job")
            cancel_check()

    adapter, request, _ = setup(tmp_path, Cancel)
    with pytest.raises(ModelWorkerError) as error:
        asyncio.run(adapter.invoke(request()))
    assert error.value.code == "generation_cancelled"


def test_candidate_capabilities_and_package_boundary():
    service = yaml.safe_load((PACKAGE / "META/service-candidate.yaml").read_text())
    for model in service["models"]:
        c = validate_video_capabilities(model["video_capabilities"])
        assert c["geometry"]["framespersecond"] == [25]
        assert c["content_combinations"][0]["optional"] == []
    assert service["runtime"]["provider"] == "ai2apps.runtime.omlx"
    assert service["permissions"]["network"]["outbound"] is False
    assert not list(PACKAGE.rglob("*.safetensors"))
    assert not any(
        p.suffix in {".so", ".dylib", ".metallib", ".pth"} for p in PACKAGE.rglob("*")
    )


def test_media_cancel_removes_partial_output(tmp_path):
    from flashhead_mlx.media import write_mp4_chunks_with_audio

    audio = tmp_path / "source.wav"
    sf.write(audio, np.zeros(1600, dtype=np.float32), 16000)
    output = tmp_path / "result.mp4"
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise worker.GenerationCancelledError()

    with pytest.raises(worker.GenerationCancelledError):
        write_mp4_chunks_with_audio(
            [np.zeros((3, 32, 32, 3), dtype=np.float32)],
            audio,
            output,
            cancel_check=cancel,
        )
    assert not output.exists() and not list(tmp_path.glob("*.tmp.mp4"))


def test_multipart_fields(tmp_path):
    adapter, request, _ = setup(tmp_path, FakePipeline)
    result = asyncio.run(adapter.invoke(request(
        reference_parts=json.dumps([{"kind": "image", "part_name": "reference_00_image"}]),
        width="512", height="512", framespersecond="25", seed="0", steps="4",
    )))
    assert result.path.is_file()
