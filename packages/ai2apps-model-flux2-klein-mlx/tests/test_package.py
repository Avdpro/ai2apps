import asyncio
import base64
import importlib.util
import io
import json
import sys
from types import ModuleType
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("flux2_worker_adapter", PACKAGE / "src/worker_adapter.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeContext:
    def __init__(self, checkpoint):
        self._checkpoint = checkpoint

    def checkpoint_for(self, _model_id):
        return SimpleNamespace(path=self._checkpoint)


class FakeGenerated:
    def __init__(self):
        self.image = Image.new("RGB", (32, 32), "navy")


class FakePipeline:
    def __init__(self, calls):
        self.calls = calls

    def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return FakeGenerated()


def checkpoint(tmp_path):
    tmp_path.mkdir(parents=True)
    (tmp_path / "model_index.json").write_text("{}")
    for name in ("transformer", "text_encoder", "vae"):
        (tmp_path / name).mkdir()
    return tmp_path


def request(tmp_path, operation, payload):
    from ai2apps.model_worker import ModelWorkerRequest

    output = tmp_path / "output"
    output.mkdir()
    return ModelWorkerRequest(operation, payload, "request-1", output_root=output)


def test_generation_returns_ai2apps_and_openai_image_shapes(tmp_path):
    calls = []
    adapter = MODULE.Flux2KleinAdapter(
        FakeContext(checkpoint(tmp_path / "weights")),
        pipeline_factory=lambda **_kwargs: FakePipeline(calls),
    )
    result = asyncio.run(
        adapter.invoke(
            request(
                tmp_path,
                "image_generation",
                {"model": "black-forest-labs/FLUX.2-klein-4B", "prompt": "paper boat", "size": "1024x1024"},
            )
        )
    )
    assert result["image"]["dataUrl"].startswith("data:image/png;base64,")
    assert result["data"][0]["b64_json"]
    assert result["quantization"] == "q8"
    assert calls[0]["num_inference_steps"] == 4


def test_edit_enables_kv_cache_and_materializes_references(tmp_path):
    calls = []
    raw = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(raw, "PNG")
    data_url = "data:image/png;base64," + base64.b64encode(raw.getvalue()).decode()
    adapter = MODULE.Flux2KleinAdapter(
        FakeContext(checkpoint(tmp_path / "weights")),
        pipeline_factory=lambda **_kwargs: FakePipeline(calls),
    )
    asyncio.run(
        adapter.invoke(
            request(
                tmp_path,
                "image_edit",
                {
                    "model": "black-forest-labs/FLUX.2-klein-9B",
                    "prompt": "make it blue",
                    "imageDataUrls": [data_url],
                    "quantization": 8,
                },
            )
        )
    )
    assert calls[0]["use_kv_cache"] is True
    assert calls[0]["image_paths"][0].is_file()


def test_derived_checkpoint_requires_receipt_and_quantized_components(tmp_path):
    root = tmp_path / "q8"
    for name in ("transformer", "text_encoder", "vae", "tokenizer"):
        (root / name).mkdir(parents=True, exist_ok=True)
    metadata = {"metadata": {"quantization_level": "8"}, "weight_map": {}}
    for name in ("transformer", "text_encoder", "vae"):
        (root / name / "model.safetensors.index.json").write_text(json.dumps(metadata))
    (root / "tokenizer" / "tokenizer.json").write_text("{}")
    (root / ".ai2apps-derived.json").write_text(
        json.dumps({"format": MODULE._DERIVED_FORMAT, "quantization_bits": 8})
    )
    assert MODULE._derived_checkpoint_complete(root, 8)
    assert not MODULE._derived_checkpoint_complete(root, 4)
    (root / "vae" / "model.safetensors.index.json").unlink()
    assert not MODULE._derived_checkpoint_complete(root, 8)


def test_derived_cache_key_is_revision_and_quantization_scoped(tmp_path):
    first = MODULE._derived_cache_key(tmp_path, "rev-a", "4b", 8)
    assert first == MODULE._derived_cache_key(tmp_path, "rev-a", "4b", 8)
    assert first != MODULE._derived_cache_key(tmp_path, "rev-b", "4b", 8)
    assert first != MODULE._derived_cache_key(tmp_path, "rev-a", "4b", 4)


def test_optimized_pipeline_reuses_compiled_predict_and_prompt_embeddings(monkeypatch):
    monkeypatch.syspath_prepend(str(PACKAGE / "src"))
    evaluations = []
    mlx = ModuleType("mlx")
    mlx_core = ModuleType("mlx.core")
    mlx_core.eval = lambda *values: evaluations.append(values)
    mlx.core = mlx_core

    class FakeFlux2Klein:
        predict_builds = 0
        cached_predict_builds = 0
        prompt_builds = 0

        def __init__(self, *args, model_config=None, **kwargs):
            self.model_config = model_config

        def _predict(self, _transformer):
            self.predict_builds += 1
            return object()

        def _cached_predict(self, _transformer):
            self.cached_predict_builds += 1
            return object()

        def _encode_prompt_pair(self, **_kwargs):
            self.prompt_builds += 1
            return (object(), object())

    variants = ModuleType("mflux.models.flux2.variants")
    variants.Flux2Klein = FakeFlux2Klein
    variants.Flux2KleinEdit = FakeFlux2Klein
    for name in ("mflux", "mflux.models", "mflux.models.flux2"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "mflux.models.flux2.variants", variants)
    monkeypatch.setitem(sys.modules, "mlx", mlx)
    monkeypatch.setitem(sys.modules, "mlx.core", mlx_core)

    spec = importlib.util.spec_from_file_location(
        "flux2_optimized_pipeline_test", PACKAGE / "src/optimized_pipeline.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    pipeline = module.OptimizedFlux2Klein()
    assert pipeline._predict(object()) is pipeline._predict(object())
    first = pipeline._encode_prompt_pair(prompt="boat", negative_prompt="", guidance=1.0)
    assert first is pipeline._encode_prompt_pair(prompt="boat", negative_prompt="", guidance=1.0)
    assert pipeline.predict_builds == 1
    assert pipeline.prompt_builds == 1
    assert pipeline.ai2apps_optimization_stats()["prompt_cache_hits"] == 1
    assert pipeline.ai2apps_optimization_stats()["metal_fusions_enabled"] is False
    assert len(evaluations) == 1

    shared_config = SimpleNamespace(supports_kv_cache=False)
    edit = module.OptimizedFlux2KleinEdit(model_config=shared_config)
    assert edit.model_config is not shared_config
    assert edit.model_config.supports_kv_cache is True
    assert shared_config.supports_kv_cache is False
    assert edit._cached_predict(object()) is edit._cached_predict(object())
    assert edit.cached_predict_builds == 1
