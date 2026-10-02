# ruff: noqa: E402
import importlib.util
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1] / "packages/ai2apps-model-sol-refiner-mlx"
sys.path.insert(0, str(ROOT / "src"))
from upscale_engine import join_window

spec = importlib.util.spec_from_file_location(
    "sol_worker_adapter_test", ROOT / "src/worker_adapter.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MODEL_ID, SoLRefinerAdapter = module.MODEL_ID, module.SoLRefinerAdapter


@pytest.mark.parametrize("length", [1, 8, 9, 33, 40, 41, 42, 64, 65, 66, 129, 1500])
@pytest.mark.parametrize(
    "window,overlap", [(41, 17), (33, 9), (25, 9), (17, 9), (9, 1)]
)
def test_window_join_preserves_every_frame(length, window, overlap):
    frames = np.broadcast_to(
        (np.arange(length) % 251).astype(np.uint8)[:, None, None, None],
        (length, 2, 3, 3),
    ).copy()
    output = []
    tail = None
    start = 0
    while True:
        chunk = frames[start : start + window]
        valid = len(chunk)
        final = valid < window
        emitted, tail = join_window(tail, chunk, valid, final, window, overlap)
        output.extend(emitted)
        if final:
            break
        if start + window == length:
            output.extend(tail)
            break
        start += window - overlap
    np.testing.assert_array_equal(np.stack(output), frames)


@pytest.mark.parametrize(
    "parameters",
    [
        {"scale": True},
        {"scale": 4},
        {"seed": True},
        {"seed": -1},
        {"seed": 2**32},
        {"prompt": "x" * 2049},
    ],
)
def test_reject_invalid_parameters(parameters):
    with pytest.raises(ValueError):
        SoLRefinerAdapter.parameters({"model": MODEL_ID, "parameters": parameters})


def test_canonical_multipart_numbers():
    prompt, seed = SoLRefinerAdapter.parameters(
        {"model": MODEL_ID, "parameters": '{"scale":"2","seed":"7","prompt":"hello"}'}
    )
    assert (prompt, seed) == ("hello", 7)


def test_distinct_capability_contract():
    from ai2apps.model_providers import validate_package_models

    caps = {
        "schema": "ai2apps.video-upscaling-capabilities/v1",
        "operations": ["video_upscaling"],
        "scale_factors": [2],
        "maximum_output_pixels": 1024**2,
        "maximum_frames": 1500,
        "maximum_seconds": 60,
        "output_formats": ["mp4"],
        "preserves_frame_count": True,
        "preserves_audio": True,
        "segmented": True,
        "prompt_required": False,
    }
    models = validate_package_models(
        "example.upscaler",
        [
            {
                "id": "example.upscaler/default",
                "model_type": "video_upscaling",
                "video_upscaling_capabilities": caps,
            }
        ],
        runtime_mode="managed_process",
        protocol="ai2apps-model-worker/v1",
    )
    assert models[0]["capabilities"] == ["video_upscaling"]
    assert models[0]["endpoints"]["video_upscaling"] == "/v1/videos/upscalings"
    assert models[0]["video_capabilities"] is None
    with pytest.raises(ValueError):
        from ai2apps.model_worker.video_upscaling_capabilities import (
            validate_video_upscaling_capabilities,
        )

        validate_video_upscaling_capabilities({**caps, "maximum_frames": True})


def test_audio_remux_preserves_video_and_audio(tmp_path):
    import av
    from upscale_engine import remux_audio

    source = tmp_path / "source.mp4"
    silent = tmp_path / "silent.mp4"
    result = tmp_path / "out.mp4"
    for path, audio in [(source, True), (silent, False)]:
        with av.open(str(path), "w") as out:
            v = out.add_stream("libx264", rate=25)
            v.width = 32
            v.height = 32
            v.pix_fmt = "yuv420p"
            if audio:
                a = out.add_stream("aac", rate=24000)
                a.layout = "mono"
            for i in range(10):
                for p in v.encode(
                    av.VideoFrame.from_ndarray(
                        np.full((32, 32, 3), i * 10, np.uint8), format="rgb24"
                    )
                ):
                    out.mux(p)
                if audio:
                    values = (
                        np.sin(
                            2 * np.pi * 440 * (np.arange(960) + i * 960) / 24000
                        ).astype(np.float32)[None]
                        * 0.1
                    )
                    f = av.AudioFrame.from_ndarray(values, format="fltp", layout="mono")
                    f.sample_rate = 24000
                    f.pts = i * 960
                    f.time_base = Fraction(1, 24000)
                    for p in a.encode(f):
                        out.mux(p)
            for p in v.encode():
                out.mux(p)
            if audio:
                for p in a.encode():
                    out.mux(p)
    remux_audio(silent, source, result, Fraction(0), Fraction(10, 25), lambda: None)
    with av.open(str(result)) as c:
        assert len(c.streams.audio) == 1
        assert len(list(c.decode(video=0))) == 10
    with av.open(str(result)) as c:
        assert sum(f.samples for f in c.decode(audio=0)) >= 9600


def test_cancel_waits_for_worker_cleanup(tmp_path):
    import asyncio
    import threading
    import time
    from types import SimpleNamespace

    from ai2apps.model_worker import (
        ModelWorkerError,
        ModelWorkerPart,
        ModelWorkerRequest,
    )

    finished = threading.Event()
    started = threading.Event()
    (tmp_path / "model_index.json").write_text("{}")
    (tmp_path / "input.mp4").write_bytes(b"fake")
    context = SimpleNamespace(
        data_root=tmp_path / "data",
        checkpoint_for=lambda _: SimpleNamespace(path=tmp_path),
    )

    def engine(source, output, root, prompt, seed, data, check, progress):
        output.write_bytes(b"partial")
        started.set()
        try:
            while True:
                check()
                time.sleep(0.005)
        finally:
            finished.set()

    adapter = SoLRefinerAdapter(context, engine=engine)
    part = ModelWorkerPart(
        "video", tmp_path / "input.mp4", "video/mp4", "input.mp4", 4, "x"
    )
    request = ModelWorkerRequest(
        "video_upscaling", {"model": MODEL_ID}, "test-cancel", {"video": part}, tmp_path
    )

    async def run():
        task = asyncio.create_task(adapter.invoke(request))
        await asyncio.to_thread(started.wait, 2)
        assert started.is_set()
        adapter.cancel("test-cancel")
        with pytest.raises(ModelWorkerError) as caught:
            await task
        assert caught.value.status_code == 499
        assert finished.is_set()
        assert not list(tmp_path.glob("upscaled-*.mp4"))
        await adapter.stop()

    asyncio.run(run())


def test_absolute_latent_noise_keys_match_overlaps():
    from upscale_engine import noise_seed

    first = [noise_seed(7, i) for i in range(6)]
    second = [noise_seed(7, 3 + i) for i in range(6)]
    assert first[3:] == second[:3]
    assert len(set(noise_seed(7, i) for i in range(200))) == 200
    assert noise_seed(7, 0) != noise_seed(8, 0)


@pytest.mark.parametrize("action", ["cancel", "stop"])
def test_cancel_queued_request_never_starts_engine(tmp_path, action):
    import asyncio
    from types import SimpleNamespace

    from ai2apps.model_worker import (
        ModelWorkerError,
        ModelWorkerPart,
        ModelWorkerRequest,
    )

    (tmp_path / "model_index.json").write_text("{}")
    context = SimpleNamespace(
        data_root=tmp_path / "data",
        checkpoint_for=lambda _: SimpleNamespace(path=tmp_path),
    )
    calls = []
    adapter = SoLRefinerAdapter(context, engine=lambda *args: calls.append(args))
    part = ModelWorkerPart(
        "video", tmp_path / "input.mp4", "video/mp4", "input.mp4", 4, "x"
    )
    request = ModelWorkerRequest(
        "video_upscaling", {"model": MODEL_ID}, "queued", {"video": part}, tmp_path
    )

    async def run():
        await adapter._lock.acquire()
        task = asyncio.create_task(adapter.invoke(request))
        await asyncio.sleep(0)
        stopping = None
        if action == "cancel":
            adapter.cancel("queued")
        else:
            stopping = asyncio.create_task(adapter.stop())
            await asyncio.sleep(0)
        adapter._lock.release()
        with pytest.raises(ModelWorkerError) as caught:
            await task
        assert caught.value.status_code == 499
        if stopping is not None:
            await stopping
        assert calls == []
        assert not adapter._cancelled_before_start
        await adapter.stop()

    asyncio.run(run())


def test_blank_prompt_uses_standard_default():
    from prompt_context import DEFAULT_PROMPT

    assert (
        SoLRefinerAdapter.parameters(
            {"model": MODEL_ID, "parameters": {"prompt": "  "}}
        )[0]
        == DEFAULT_PROMPT
    )


def test_fixed_context_rejects_custom_prompt_without_text(tmp_path):
    import json

    from prompt_context import DEFAULT_PROMPT, fixed_context

    (tmp_path / "context-metadata.json").write_text(
        json.dumps({"prompt": DEFAULT_PROMPT})
    )
    with pytest.raises(ValueError, match="Custom prompts need"):
        fixed_context(tmp_path, "make it sharper")


def test_fixed_context_checks_digest_and_allows_installed_text(tmp_path):
    import hashlib
    import json

    from prompt_context import DEFAULT_PROMPT, fixed_context

    context = tmp_path / "default-prompt-context.safetensors"
    context.write_bytes(b"test-context")
    (tmp_path / "context-metadata.json").write_text(
        json.dumps(
            {
                "prompt": DEFAULT_PROMPT,
                "sha256": hashlib.sha256(context.read_bytes()).hexdigest(),
            }
        )
    )
    assert fixed_context(tmp_path, DEFAULT_PROMPT) == context
    context.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="damaged"):
        fixed_context(tmp_path, DEFAULT_PROMPT)
    for name in ("text_encoder", "connectors"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "config.json").write_text("{}")
    assert fixed_context(tmp_path, "custom") is None


@pytest.mark.parametrize("model", [module.CUSTOM_MODEL_ID, module.CUSTOM_UPSTREAM_ID])
def test_custom_profile_uses_its_own_checkpoint(tmp_path, model):
    import asyncio
    from types import SimpleNamespace

    from ai2apps.model_worker import ModelWorkerPart, ModelWorkerRequest

    (tmp_path / "model_index.json").write_text("{}")
    selected = []

    def checkpoint(model_id):
        selected.append(model_id)
        return SimpleNamespace(path=tmp_path)

    def engine(source, output, root, prompt, *args):
        assert prompt == "a custom prompt"
        output.write_bytes(b"test-video")
        return {}

    adapter = SoLRefinerAdapter(
        SimpleNamespace(data_root=tmp_path / "data", checkpoint_for=checkpoint),
        engine=engine,
    )
    part = ModelWorkerPart("video", tmp_path / "in.mp4", "video/mp4", "in.mp4", 1, "x")
    request = ModelWorkerRequest(
        "video_upscaling",
        {"model": model, "parameters": {"prompt": "a custom prompt"}},
        "custom",
        {"video": part},
        tmp_path,
    )
    result = asyncio.run(adapter.invoke(request))
    assert selected == [module.CUSTOM_MODEL_ID]
    assert result.path.read_bytes() == b"test-video"


def test_standard_custom_prompt_error_precedes_engine(tmp_path):
    import asyncio
    import json
    from types import SimpleNamespace

    from prompt_context import DEFAULT_PROMPT

    from ai2apps.model_worker import (
        ModelWorkerError,
        ModelWorkerPart,
        ModelWorkerRequest,
    )

    (tmp_path / "model_index.json").write_text("{}")
    (tmp_path / "context-metadata.json").write_text(
        json.dumps({"prompt": DEFAULT_PROMPT})
    )
    calls = []
    adapter = SoLRefinerAdapter(
        SimpleNamespace(
            data_root=tmp_path / "data",
            checkpoint_for=lambda _: SimpleNamespace(path=tmp_path),
        ),
        engine=lambda *args: calls.append(args),
    )
    part = ModelWorkerPart("video", tmp_path / "in.mp4", "video/mp4", "in.mp4", 1, "x")
    request = ModelWorkerRequest(
        "video_upscaling",
        {"model": MODEL_ID, "parameters": {"prompt": "custom"}},
        "unsupported",
        {"video": part},
        tmp_path,
    )
    with pytest.raises(ModelWorkerError) as caught:
        asyncio.run(adapter.invoke(request))
    assert caught.value.code == "prompt_configuration_required"
    assert calls == []


def test_high_resolution_window_plan_and_reservation():
    from upscale_engine import window_plan

    from ai2apps.worker_resources import video_upscaling_transient_bytes

    assert window_plan(512, 512) == (41, 17)
    assert window_plan(1024, 1024) == (17, 9)
    assert window_plan(1920, 1080) == (9, 1)
    assert window_plan(3840, 2160) == (9, 1)
    for width, height in ((512, 512), (1024, 1024), (1920, 1080), (3840, 2160)):
        window, overlap = window_plan(width, height)
        assert (window - overlap) % 8 == 0
        estimate = video_upscaling_transient_bytes(
            {
                "_video_input_width": width,
                "_video_input_height": height,
                "_video_input_frames": 65,
            }
        )
        pixels = ((width + 31) // 32 * 32) * ((height + 31) // 32 * 32)
        assert estimate >= 2 * 1024**3 + pixels * window * 1000


def test_resource_limited_published_candidate_contract():
    import yaml

    from ai2apps.model_providers import validate_package_models
    from ai2apps.model_worker.video_upscaling_capabilities import (
        validate_video_upscaling_capabilities,
    )

    service = yaml.safe_load((ROOT / "service.yaml").read_text())
    models = validate_package_models(
        service["id"],
        service["models"],
        runtime_mode="managed_process",
        protocol="ai2apps-model-worker/v1",
    )
    assert len(models) == 2
    for model in models:
        caps = model["video_upscaling_capabilities"]
        assert caps["maximum_output_pixels"] is None
        assert caps["resolution_policy"] == "resource_limited"
        with pytest.raises(ValueError):
            validate_video_upscaling_capabilities(
                {**caps, "resolution_policy": "fixed"}
            )
        with pytest.raises(ValueError):
            validate_video_upscaling_capabilities(
                {**caps, "maximum_output_pixels": True}
            )


def test_resource_geometry_is_probed_from_media(tmp_path):
    import av

    from ai2apps.worker_resources import video_upscaling_resource_payload

    path = tmp_path / "geometry.mp4"
    with av.open(str(path), "w") as out:
        stream = out.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 640, 360, "yuv420p"
        frame = av.VideoFrame.from_ndarray(
            np.zeros((360, 640, 3), dtype=np.uint8), format="rgb24"
        )
        for packet in stream.encode(frame):
            out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    for source in (path, path.read_bytes()):
        payload = video_upscaling_resource_payload(
            {"_video_input_width": 1, "parameters": "{}"}, source
        )
        assert payload["_video_input_width"] == 640
        assert payload["_video_input_height"] == 360
        assert payload["_video_input_frames"] == 1
        assert payload["parameters"] == "{}"


@pytest.mark.asyncio
async def test_background_upscale_probes_upload_before_scheduling(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import av
    import httpx

    from ai2apps.model_invocation import ModelInvocationService
    from ai2apps.worker_resources import GIB

    source = tmp_path / "input.mp4"
    with av.open(str(source), "w") as out:
        stream = out.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 640, 360, "yuv420p"
        frame = av.VideoFrame.from_ndarray(
            np.zeros((360, 640, 3), dtype=np.uint8), format="rgb24"
        )
        for packet in stream.encode(frame):
            out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    model = SimpleNamespace(
        id=MODEL_ID,
        upstream_id="ai2apps-sol-refiner-default",
        internal_headers={},
        endpoint="http://127.0.0.1:1234",
        endpoints={"video_upscaling": "/upscale"},
        service_key="upscaler",
        model_type="video_upscaling",
        metadata={},
    )
    lease = SimpleNamespace(release=AsyncMock())
    scheduler = SimpleNamespace(acquire=AsyncMock(return_value=lease))
    service = ModelInvocationService(SimpleNamespace(worker_scheduler=scheduler))
    monkeypatch.setattr(service, "_require_model", lambda _: model)
    monkeypatch.setattr(service, "request_progress", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "ai2apps.model_invocation.ensure_package_model_ready",
        AsyncMock(return_value=model),
    )
    seen = {}

    async def handle(request):
        from email.parser import BytesParser
        from email.policy import default

        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode()
            + await request.aread()
        )
        for part in message.iter_parts():
            seen[part.get_param("name", header="content-disposition")] = (
                part.get_payload(decode=True)
            )
        assert request.headers["x-request-id"] == "upscale-host-test"
        return httpx.Response(200, content=b"completed-video")

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        "ai2apps.model_invocation.httpx.AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    target = tmp_path / "output.mp4"
    await service.invoke_background_to_file(
        MODEL_ID,
        "video_upscaling",
        {
            "parameters": {"scale": 2},
            "_video_input_width": 1,
            "_video_input_frames": 99999,
        },
        target,
        files={"video": (source.name, source, "video/mp4")},
        request_id="upscale-host-test",
    )
    assert seen["_video_input_width"] == b"640"
    assert seen["_video_input_height"] == b"360"
    assert seen["_video_input_frames"] == b"1"
    assert scheduler.acquire.await_args.kwargs["estimated_transient_bytes"] >= 12 * GIB
    assert target.read_bytes() == b"completed-video"
    lease.release.assert_awaited_once_with(failed=False)


def test_whole_clip_admission_grows_with_length_and_matches_host(monkeypatch):
    import psutil
    from types import SimpleNamespace
    from upscale_engine import estimated_memory_bytes, check_memory
    from ai2apps.worker_resources import video_upscaling_transient_bytes

    assert estimated_memory_bytes(1024, 1024, 500) > estimated_memory_bytes(1024, 1024, 65)
    for frames in (1, 41, 124, 500, 1500):
        assert estimated_memory_bytes(1024, 1024, frames) == video_upscaling_transient_bytes({
            "_video_input_width": 1024, "_video_input_height": 1024, "_video_input_frames": frames,
        })
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(available=8 * 1024**3))
    with pytest.raises(MemoryError, match="Independent segment refinement is disabled"):
        check_memory(512, 288, 124)


@pytest.mark.parametrize("length", [1, 9, 41, 42, 65, 124])
def test_video_refines_once_then_decodes_chunks(tmp_path, monkeypatch, length):
    import av
    import mlx.core as mx
    import upscale_engine as engine
    from test_ai2apps_video_upscaling import _video

    source, output = tmp_path / "in.mp4", tmp_path / "out.mp4"
    _video(source, length)
    calls = []
    class FakeRefiner:
        def __init__(self, root):
            pass
        def refine_latents(self, pixels, *args, **kwargs):
            calls.append(("refine", pixels.shape[2]))
            return mx.zeros((1, 128, (pixels.shape[2] - 1) // 8 + 1, 4, 4))
        def decode_latents(self, raw, **kwargs):
            calls.append(("decode", raw.shape[2]))
            return mx.zeros((1, 3, (raw.shape[2] - 1) * 8 + 1, 128, 128))
    monkeypatch.setattr(engine, "check_memory", lambda *a: 123)
    result = engine.upscale(source, output, tmp_path, "", 0, tmp_path,
                            lambda: None, lambda value: None, infer_factory=FakeRefiner)
    assert [c for c in calls if c[0] == "refine"] == [("refine", 1 + (length - 1 + 7) // 8 * 8)]
    assert all(count <= 6 for kind, count in calls if kind == "decode")
    assert result["frames"] == length and result["temporal_policy"] == "whole_clip"
    with av.open(str(output)) as video:
        assert len(list(video.decode(video=0))) == length
    calls.clear()
    def reject(*args):
        raise MemoryError("test budget exceeded")
    monkeypatch.setattr(engine, "check_memory", reject)
    with pytest.raises(MemoryError, match="budget exceeded"):
        engine.upscale(source, tmp_path / "rejected.mp4", tmp_path, "", 0, tmp_path,
                       lambda: None, lambda value: None, infer_factory=FakeRefiner)
    assert calls == []


def test_precision_operators_round_after_fp32_intermediates():
    import mlx.core as mx
    import mlx.nn as nn
    from sol_refiner_mlx.precision import silu, gelu_approx
    from sol_refiner_mlx.transformer import rms

    values = np.random.default_rng(42).normal(size=(8, 128)).astype(np.float32)
    x = mx.array(values, dtype=mx.bfloat16)
    weight = mx.array(values[0], dtype=mx.bfloat16)
    y = x.astype(mx.float32)
    expected = (y * mx.rsqrt(mx.mean(y * y, axis=-1, keepdims=True) + 1e-6)
                * weight.astype(mx.float32)).astype(mx.bfloat16)
    np.testing.assert_array_equal(np.array(rms(x, weight).astype(mx.float32)),
                                  np.array(expected.astype(mx.float32)))
    for actual, reference in ((silu(x), nn.silu(y)), (gelu_approx(x), nn.gelu_approx(y))):
        np.testing.assert_allclose(np.array(actual.astype(mx.float32)),
                                   np.array(reference.astype(mx.bfloat16).astype(mx.float32)),
                                   atol=2e-5, rtol=1e-4)
