import asyncio
import base64
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import yaml
from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "z_image_worker_adapter", PACKAGE / "src/worker_adapter.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeContext:
    def __init__(self, checkpoint, data_root):
        self._checkpoint = checkpoint
        self.data_root = data_root

    def checkpoint_for(self, _model_id):
        return SimpleNamespace(path=self._checkpoint, revision="test-revision")


class FakeGenerated:
    def __init__(self):
        self.image = Image.new("RGB", (32, 32), "navy")


class FakePipeline:
    def __init__(self, calls):
        self.calls = calls

    def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return FakeGenerated()

    def ai2apps_optimization_stats(self):
        return {"metal_rms_adaln_fusions_enabled": True}


def checkpoint(root):
    for name in ("transformer", "text_encoder", "vae", "tokenizer"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def request(tmp_path, operation, payload):
    from ai2apps.model_worker import ModelWorkerRequest

    output = tmp_path / "output"
    output.mkdir(exist_ok=True)
    return ModelWorkerRequest(operation, payload, "request-1", output_root=output)


def data_url(color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def oversized_data_url():
    buffer = io.BytesIO()
    Image.new("RGB", (8193, 1), "red").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def test_generation_returns_ai2apps_and_openai_shapes(tmp_path):
    calls = []
    adapter = MODULE.ZImageAdapter(
        FakeContext(checkpoint(tmp_path / "weights"), tmp_path / "data"),
        pipeline_factory=lambda **_kwargs: FakePipeline(calls),
    )
    result = asyncio.run(
        adapter.invoke(
            request(
                tmp_path,
                "image_generation",
                {
                    "model": MODULE.UPSTREAM_ID,
                    "prompt": "paper boat",
                    "size": "1024x1024",
                },
            )
        )
    )
    assert result["image"]["dataUrl"].startswith("data:image/png;base64,")
    assert result["data"][0]["b64_json"]
    assert result["quantization"] == "q8"
    assert result["optimization"]["metal_rms_adaln_fusions_enabled"] is True
    assert calls == [
        {
            "seed": 0,
            "prompt": "paper boat",
            "num_inference_steps": 8,
            "height": 1024,
            "width": 1024,
            "guidance": 0.0,
        }
    ]


def test_image_edit_passes_verified_reference_and_strength(tmp_path):
    calls = []
    adapter = MODULE.ZImageAdapter(
        FakeContext(checkpoint(tmp_path / "weights"), tmp_path / "data"),
        pipeline_factory=lambda **_kwargs: FakePipeline(calls),
    )
    result = asyncio.run(
        adapter.invoke(
            request(
                tmp_path,
                "image_edit",
                {
                    "model": MODULE.UPSTREAM_ID,
                    "prompt": "turn the boat into folded copper",
                    "size": "512x512",
                    "imageDataUrls": [data_url()],
                    "strength": 0.6,
                },
            )
        )
    )
    assert result["operation"] == "image_edit"
    assert result["imageStrength"] == 0.6
    assert calls[0]["image_strength"] == 0.6
    assert calls[0]["image_path"].is_file()
    assert calls[0]["height"] == calls[0]["width"] == 512


def test_image_edit_rejects_invalid_reference_and_strength(tmp_path):
    adapter = MODULE.ZImageAdapter(
        FakeContext(checkpoint(tmp_path / "weights"), tmp_path / "data"),
        pipeline_factory=lambda **_kwargs: FakePipeline([]),
    )
    for payload in (
        {"imageDataUrls": ["data:image/png;base64,bm90LWltYWdl"], "strength": 0.5},
        {"imageDataUrls": [data_url()], "strength": 0.0},
        {"imageDataUrls": [data_url(), data_url("blue")], "strength": 0.5},
        {"imageDataUrls": [oversized_data_url()], "strength": 0.5},
    ):
        payload.update({"model": MODULE.UPSTREAM_ID, "prompt": "edit"})
        try:
            asyncio.run(adapter.invoke(request(tmp_path, "image_edit", payload)))
        except Exception as exc:
            assert getattr(exc, "code", None) == "invalid_request"
        else:
            raise AssertionError("invalid edit request was accepted")


def test_manifests_pin_runtime_152_and_model_revision():
    outer = json.loads((PACKAGE / "ai2apps.json").read_text())
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    assert outer["package"]["version"] == service["version"] == "0.1.1"
    assert outer["dependencies"] == [
        {
            "packageId": "ai2apps/runtime-omlx",
            "version": ">=1.5.2 <2.0.0",
            "optional": False,
        }
    ]
    model = service["models"][0]
    assert model["weights"]["revision"] == "f332072aa78be7aecdf3ee76d5c247082da564a6"
    assert model["image_capabilities"]["operations"] == [
        "image_generation",
        "image_edit",
    ]
    assert model["image_capabilities"]["execution"]["metal_rms_adaln_fusion"] is True


def test_parameters_enforce_turbo_guidance_and_geometry():
    try:
        MODULE.ZImageAdapter._parameters(
            {"prompt": "x", "size": "1000x1024", "guidance": 0}
        )
    except ValueError as exc:
        assert "divisible by 32" in str(exc)
    else:
        raise AssertionError("invalid geometry was accepted")
    try:
        MODULE.ZImageAdapter._parameters({"prompt": "x", "guidance": 1})
    except ValueError as exc:
        assert "guidance must be 0" in str(exc)
    else:
        raise AssertionError("invalid Turbo guidance was accepted")


def test_derived_checkpoint_requires_group64_receipt(tmp_path):
    root = tmp_path / "q8"
    for name in ("transformer", "text_encoder", "vae", "tokenizer"):
        (root / name).mkdir(parents=True, exist_ok=True)
    metadata = {"metadata": {"quantization_level": "8"}, "weight_map": {}}
    for name in ("transformer", "text_encoder", "vae"):
        (root / name / "model.safetensors.index.json").write_text(json.dumps(metadata))
    (root / "tokenizer" / "tokenizer.json").write_text("{}")
    receipt = {
        "format": MODULE._DERIVED_FORMAT,
        "quantization_bits": 8,
        "quantization_group_size": 64,
    }
    (root / ".ai2apps-derived.json").write_text(json.dumps(receipt))
    assert MODULE._derived_checkpoint_complete(root, 8)
    receipt["quantization_group_size"] = 128
    (root / ".ai2apps-derived.json").write_text(json.dumps(receipt))
    assert not MODULE._derived_checkpoint_complete(root, 8)


def test_cache_key_is_revision_and_quantization_scoped(tmp_path):
    first = MODULE._derived_cache_key(tmp_path, "rev-a", 8)
    assert first == MODULE._derived_cache_key(tmp_path, "rev-a", 8)
    assert first != MODULE._derived_cache_key(tmp_path, "rev-b", 8)
    assert first != MODULE._derived_cache_key(tmp_path, "rev-a", 4)


def test_optimized_pipeline_installs_guarded_metal_path(monkeypatch):
    installed = []

    class FakeZImage:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    variants = ModuleType("mflux.models.z_image.variants.z_image")
    variants.ZImage = FakeZImage
    for name in (
        "mflux",
        "mflux.models",
        "mflux.models.z_image",
        "mflux.models.z_image.variants",
    ):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "mflux.models.z_image.variants.z_image", variants)
    fusions = ModuleType("z_image_fused_rms")
    fusions.install = lambda: installed.append(True) or True
    monkeypatch.setitem(sys.modules, "z_image_fused_rms", fusions)

    spec = importlib.util.spec_from_file_location(
        "z_image_optimized_pipeline_test", PACKAGE / "src/optimized_pipeline.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    pipeline = module.OptimizedZImage(model_path="weights", quantize=8)
    assert installed == [True]
    stats = pipeline.ai2apps_optimization_stats()
    assert stats["metal_rms_adaln_fusions_enabled"] is True
    assert stats["step_synchronization"] == "every-step"
