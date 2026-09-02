from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from PIL import Image

from ai2apps.model_worker import ModelWorkerError, ModelWorkerRequest
from ai2apps.model_worker.image_capabilities import validate_image_capabilities

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "qwen_image_worker_adapter", PACKAGE / "src" / "worker_adapter.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeContext:
    def __init__(self, checkpoints, data_root):
        self._checkpoints = checkpoints
        self.data_root = data_root

    def checkpoint_for(self, model_id):
        return SimpleNamespace(path=self._checkpoints[model_id], revision="a" * 40)


class FakeGenerated:
    def __init__(self):
        self.image = Image.new("RGB", (32, 32), "navy")


class FakePipeline:
    def __init__(self, calls):
        self.calls = calls

    def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return FakeGenerated()


def checkpoint(root: Path):
    root.mkdir(parents=True)
    (root / "model_index.json").write_text("{}")
    for name in ("transformer", "text_encoder", "vae", "tokenizer"):
        (root / name).mkdir()
    return root


def context(tmp_path):
    return FakeContext(
        {
            "ai2apps.model.qwen-image-mlx/2512": checkpoint(tmp_path / "generation"),
            "ai2apps.model.qwen-image-mlx/edit-2511": checkpoint(tmp_path / "edit"),
        },
        tmp_path / "data",
    )


def request(tmp_path, operation, payload):
    output = tmp_path / f"output-{operation}"
    output.mkdir()
    return ModelWorkerRequest(operation, payload, "request-1", output_root=output)


def data_url(color="red"):
    raw = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(raw, "PNG")
    return "data:image/png;base64," + base64.b64encode(raw.getvalue()).decode()


def test_manifest_locks_real_2512_and_2511_checkpoints():
    manifest = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    assert manifest["version"] == "0.1.1"
    assert manifest["requires"]["services"][0]["version"] == ">=1.5.1,<2.0.0"
    assert [model["upstream_id"] for model in manifest["models"]] == [
        "Qwen/Qwen-Image-2512",
        "Qwen/Qwen-Image-Edit-2511",
    ]
    assert [model["weights"]["revision"] for model in manifest["models"]] == [
        "25468b98e3276ca6700de15c6628e51b7de54a26",
        "6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9",
    ]
    assert [
        model["metadata"]["modelscope"]["revision"] for model in manifest["models"]
    ] == [
        "ee3f7563eefa997af5a07dbe54a57e5babd3768b",
        "f8403bcb7b827dab45d845cb71415ec9276e61d6",
    ]
    for model in manifest["models"]:
        assert model["metadata"]["modelscope"]["preferred"] is True
        assert "transformer/*" in model["metadata"]["modelscope"]["allow_patterns"]
        assert "scheduler/*" in model["metadata"]["modelscope"]["allow_patterns"]
        validate_image_capabilities(model["image_capabilities"])
    optimized = (PACKAGE / "src" / "optimized_pipeline.py").read_text()
    assert "class OptimizedQwenImage(" in optimized
    assert "class OptimizedQwenImageEdit(" in optimized
    assert "if guidance != 1.0:" in optimized
    assert (
        manifest["models"][0]["image_capabilities"]["execution"][
            "single_pass_guidance_one"
        ]
        is True
    )


def test_distribution_build_specs_match_package_source_lock():
    manifest = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    lock = json.loads((PACKAGE / "META/source-lock.json").read_text())
    models = {model["metadata"]["variant"]: model for model in manifest["models"]}
    specs = {
        "2512": json.loads(
            (PACKAGE / "META/checkpoint-distribution-2512.json").read_text()
        ),
        "edit-2511": json.loads(
            (PACKAGE / "META/checkpoint-distribution-edit-2511.json").read_text()
        ),
    }

    for variant, spec in specs.items():
        model = models[variant]
        source_lock = lock["models"][variant]
        assert spec["schema"] == "ai2apps.checkpoint-build/v1"
        assert spec["modelId"] == model["id"]
        assert spec["repoId"] == model["weights"]["repo_id"]
        assert spec["revision"] == source_lock["revision"]
        modelscope = next(
            source
            for source in spec["sourceRepositories"]
            if source["type"] == "modelscope"
        )
        assert modelscope["revision"] == source_lock["modelscope_revision"]
        assert model["metadata"]["modelscope"]["revision"] == modelscope["revision"]
        assert spec["license"]["termsHash"] == (
            "sha256:" + hashlib.sha256((PACKAGE / "LICENSE").read_bytes()).hexdigest()
        )


def test_generation_returns_openai_and_ai2apps_shapes(tmp_path):
    calls = []
    adapter = MODULE.QwenImageAdapter(
        context(tmp_path), pipeline_factory=lambda **_kwargs: FakePipeline(calls)
    )
    result = asyncio.run(
        adapter.invoke(
            request(
                tmp_path,
                "image_generation",
                {"model": "Qwen/Qwen-Image-2512", "prompt": "海报上写着 AI2Apps"},
            )
        )
    )
    assert result["image"]["dataUrl"].startswith("data:image/png;base64,")
    assert result["data"][0]["b64_json"]
    assert result["quantization"] == "q8"
    assert calls[0]["width"] == calls[0]["height"] == 1328
    assert calls[0]["num_inference_steps"] == 20


def test_edit_uses_true_2511_model_and_ordered_images(tmp_path):
    calls = []
    factories = []

    def factory(**kwargs):
        factories.append(kwargs)
        return FakePipeline(calls)

    adapter = MODULE.QwenImageAdapter(context(tmp_path), pipeline_factory=factory)
    result = asyncio.run(
        adapter.invoke(
            request(
                tmp_path,
                "image_edit",
                {
                    "model": "Qwen/Qwen-Image-Edit-2511",
                    "prompt": "把第一张图中的主体换成第二张图中的主体",
                    "negative_prompt": "模糊",
                    "imageDataUrls": [data_url("red"), data_url("blue")],
                },
            )
        )
    )
    assert factories[0]["upstream"] == "Qwen/Qwen-Image-Edit-2511"
    assert factories[0]["kind"] == "edit"
    assert [Path(path).name for path in calls[0]["image_paths"]] == [
        "reference-0.png",
        "reference-1.png",
    ]
    assert calls[0]["negative_prompt"] == "模糊"
    assert result["model"] == "Qwen/Qwen-Image-Edit-2511"


def test_generation_checkpoint_cannot_be_used_for_edit(tmp_path):
    adapter = MODULE.QwenImageAdapter(
        context(tmp_path), pipeline_factory=lambda **_kwargs: FakePipeline([])
    )
    with pytest.raises(ModelWorkerError) as captured:
        asyncio.run(
            adapter.invoke(
                request(
                    tmp_path,
                    "image_edit",
                    {
                        "model": "Qwen/Qwen-Image-2512",
                        "prompt": "edit",
                        "imageDataUrls": [data_url()],
                    },
                )
            )
        )
    assert captured.value.code == "operation_not_supported"


def test_derived_checkpoint_is_revision_kind_and_quantization_scoped(tmp_path):
    first = MODULE._derived_cache_key(tmp_path, "rev-a", "generation", 8)
    assert first == MODULE._derived_cache_key(tmp_path, "rev-a", "generation", 8)
    assert first != MODULE._derived_cache_key(tmp_path, "rev-b", "generation", 8)
    assert first != MODULE._derived_cache_key(tmp_path, "rev-a", "edit", 8)
    assert first != MODULE._derived_cache_key(tmp_path, "rev-a", "generation", 4)

    root = tmp_path / "derived"
    for name in ("transformer", "text_encoder", "vae", "tokenizer"):
        (root / name).mkdir(parents=True)
    metadata = {"metadata": {"quantization_level": "8"}, "weight_map": {}}
    for name in ("transformer", "text_encoder", "vae"):
        (root / name / "model.safetensors.index.json").write_text(json.dumps(metadata))
    (root / "tokenizer" / "tokenizer.json").write_text("{}")
    (root / ".ai2apps-derived.json").write_text(
        json.dumps({"format": MODULE._DERIVED_FORMAT, "quantization_bits": 8})
    )
    assert MODULE._derived_checkpoint_complete(root, 8)
    assert not MODULE._derived_checkpoint_complete(root, 4)
