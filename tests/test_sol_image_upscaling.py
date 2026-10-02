import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "packages/ai2apps-model-sol-refiner-mlx"
sys.path.insert(0, str(ROOT / "src"))
from image_upscale_engine import load_image, upscale_image
from worker_adapter import MODEL_ID, SoLRefinerAdapter


def test_direct_png_pixels_and_alpha(tmp_path):
    import mlx.core as mx

    source, output = tmp_path / "in.png", tmp_path / "out.png"
    pixels = np.arange(35 * 33 * 4, dtype=np.uint8).reshape(35, 33, 4)
    Image.fromarray(pixels).save(source)
    observed = {}

    class Refiner:
        def __init__(self, root):
            pass

        def __call__(self, tensor, *args, **kwargs):
            observed["shape"] = tensor.shape
            return mx.repeat(mx.repeat(tensor, 2, axis=3), 2, axis=4)

    progress = []
    result = upscale_image(
        source,
        output,
        tmp_path,
        "",
        0,
        tmp_path,
        lambda: None,
        progress.append,
        infer_factory=Refiner,
    )
    assert observed["shape"] == (1, 3, 1, 64, 64)
    with Image.open(output) as image:
        assert image.format == "PNG" and image.size == (66, 70) and image.mode == "RGBA"
        expected = np.repeat(np.repeat(pixels[:, :, :3], 2, axis=0), 2, axis=1)
        np.testing.assert_array_equal(np.array(image)[:, :, :3], expected)
        alpha = (
            Image.fromarray(pixels)
            .getchannel("A")
            .resize(image.size, Image.Resampling.LANCZOS)
        )
        assert alpha.tobytes() == image.getchannel("A").tobytes()
    assert result["alpha_preserved"] and progress[-1]["current"] == 1


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_orientation_and_supported_formats(tmp_path, format):
    path = tmp_path / "input"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 60), (120, 40, 80)).save(path, format=format, exif=exif)
    rgb, alpha = load_image(path)
    assert rgb.shape == (40, 60, 3) and alpha is None


def test_animated_and_hdr_inputs_rejected(tmp_path):
    path = tmp_path / "animated.png"
    Image.new("RGB", (32, 32), "red").save(
        path, save_all=True, append_images=[Image.new("RGB", (32, 32), "blue")]
    )
    with pytest.raises(ValueError, match="single-frame"):
        load_image(path)
    path = tmp_path / "hdr.png"
    Image.new("I;16", (32, 32)).save(path)
    with pytest.raises(ValueError, match="8-bit"):
        load_image(path)


def test_image_resource_dimensions_ignore_payload(tmp_path):
    from ai2apps.worker_resources import (
        estimate_request_transient_bytes,
        image_upscaling_resource_payload,
    )

    path = tmp_path / "image.png"
    Image.new("RGB", (1920, 1080)).save(path)
    payload = image_upscaling_resource_payload({"_image_input_width": 1}, path)
    assert payload["_image_input_width"] == 1920
    assert estimate_request_transient_bytes("image_upscaling", payload) >= 8 * 1024**3


def test_core_contract_and_shared_weight_profiles():
    import yaml

    from ai2apps.model_providers import validate_package_models
    from ai2apps.model_worker.server import OPERATIONS
    from ai2apps.provisioning.profiles import CapabilityProfileRegistry

    d = yaml.safe_load((ROOT / "service.yaml").read_text())
    models = validate_package_models(
        d["id"],
        d["models"],
        runtime_mode="managed_process",
        protocol="ai2apps-model-worker/v1",
    )
    assert len(models) == 2
    for model in models:
        assert (
            "image_upscaling" in model["capabilities"]
            and "video_upscaling" in model["capabilities"]
        )
        assert model["image_upscaling_capabilities"]["output_formats"] == ["png"]
        assert model["endpoints"]["image_upscaling"] == "/v1/images/upscalings"
    assert OPERATIONS["image_upscaling"] == "/v1/images/upscalings"
    registry = CapabilityProfileRegistry()
    for app in ["ai2apps.imagine-studio", "ai2apps.video-studio"]:
        cap = registry.capability(app, "image.upscaling")
        assert cap["requirements"]["operations"] == ["image_upscaling"]
        assert cap["profiles"][0]["stack"]["checkpoint"]["model_id"] == MODEL_ID


@pytest.mark.asyncio
async def test_adapter_dispatches_image_without_video_encoding(tmp_path):
    from ai2apps.model_worker import ModelWorkerPart, ModelWorkerRequest

    (tmp_path / "model_index.json").write_text("{}")
    source = tmp_path / "input.png"
    Image.new("RGB", (32, 32), "red").save(source)
    calls = []

    def engine(source, output, *args):
        calls.append(source)
        Image.new("RGB", (64, 64), "red").save(output, format="PNG")
        return {"width": 64, "height": 64}

    context = SimpleNamespace(
        data_root=tmp_path / "data",
        checkpoint_for=lambda _: SimpleNamespace(path=tmp_path),
    )
    adapter = SoLRefinerAdapter(context, image_engine=engine)
    request = ModelWorkerRequest(
        "image_upscaling",
        {"model": MODEL_ID},
        "image-test",
        {
            "image": ModelWorkerPart(
                "image", source, "image/png", "input.png", source.stat().st_size, "x"
            )
        },
        tmp_path,
    )
    result = await adapter.invoke(request)
    assert result.media_type == "image/png" and result.filename == "upscaled.png"
    assert calls == [source] and result.path.suffix == ".png"
    await adapter.stop()


@pytest.mark.asyncio
async def test_background_upscale_probes_upload_before_scheduling(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import httpx

    from ai2apps.model_invocation import ModelInvocationService
    from ai2apps.worker_resources import GIB

    source = tmp_path / "input.png"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (640, 360)).save(source, exif=exif)
    model = SimpleNamespace(
        id=MODEL_ID,
        upstream_id="ai2apps-sol-refiner-default",
        internal_headers={},
        endpoint="http://127.0.0.1:1234",
        endpoints={"image_upscaling": "/upscale"},
        service_key="upscaler",
        model_type="image_upscaling",
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
        return httpx.Response(200, content=b"completed-image")

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        "ai2apps.model_invocation.httpx.AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs),
    )
    target = tmp_path / "output.png"
    await service.invoke_background_to_file(
        MODEL_ID,
        "image_upscaling",
        {
            "parameters": {"scale": 2},
            "_image_input_width": 1,
            "_image_input_height": 99999,
        },
        target,
        files={"image": (source.name, source, "image/png")},
        request_id="upscale-host-test",
    )
    assert seen["_image_input_width"] == b"360"
    assert seen["_image_input_height"] == b"640"
    assert scheduler.acquire.await_args.kwargs["estimated_transient_bytes"] >= 8 * GIB
    assert target.read_bytes() == b"completed-image"
    lease.release.assert_awaited_once_with(failed=False)
