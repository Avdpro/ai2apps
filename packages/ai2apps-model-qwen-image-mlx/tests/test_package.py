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


def test_release_advertises_only_pinned_qwen_21():
    manifest = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    package = json.loads((PACKAGE / "ai2apps.json").read_text())
    lock = json.loads((PACKAGE / "META/source-lock.json").read_text())
    spec = json.loads((PACKAGE / "META/checkpoint-distribution-21.json").read_text())

    assert manifest["version"] == package["package"]["version"] == "0.1.3"
    assert manifest["requires"]["services"][0]["version"] == ">=1.8.17,<2.0.0"
    assert package["dependencies"][0]["version"] == ">=1.8.17 <2.0.0"
    (model,) = manifest["models"]
    (advertised,) = package["modelInstall"]["models"]
    assert model["id"] == advertised["id"] == spec["modelId"] == MODULE.QWEN_IMAGE_21_ID
    assert model["upstream_id"] == spec["repoId"] == MODULE.QWEN_IMAGE_21
    assert model["weights"]["revision"] == lock["models"]["2.1"]["revision"] == spec["revision"]
    assert model["weights"]["distribution_id"] == spec["distributionId"]
    modelscope = next(item for item in spec["sourceRepositories"] if item["type"] == "modelscope")
    assert model["metadata"]["modelscope"]["revision"] == modelscope["revision"]
    assert model["metadata"]["modelscope"]["allow_patterns"] == spec["includePatterns"]
    capabilities = validate_image_capabilities(model["image_capabilities"])
    assert capabilities["operations"] == ["image_generation", "image_edit"]
    assert capabilities["geometry"]["multiple_of"] == 32


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


def test_qwen_21_shares_pipeline_and_preserves_alpha(tmp_path):
    root = checkpoint(tmp_path / "qwen21")
    (root / "tokenizer").rename(root / "processor")
    checkpoint_info = SimpleNamespace(path=root, revision=MODULE.QWEN_IMAGE_21_REVISION)
    ctx = SimpleNamespace(checkpoint_for={MODULE.QWEN_IMAGE_21_ID: checkpoint_info}.get)
    loads = []
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(image=Image.new("RGBA", (256, 256), (255, 0, 0, 0)))

    def factory(**kwargs):
        loads.append(kwargs)
        return SimpleNamespace(generate_image=generate)

    adapter = MODULE.QwenImageAdapter(ctx, pipeline_factory=factory)

    async def run():
        payload = {"model": MODULE.QWEN_IMAGE_21, "prompt": "test", "size": "256x256"}
        generation = await adapter.invoke(request(tmp_path, "image_generation", payload))
        await adapter.invoke(request(
            tmp_path, "image_edit",
            dict(payload, model=MODULE.QWEN_IMAGE_21_ID, imageDataUrls=[data_url()]),
        ))
        return generation

    result = asyncio.run(run())
    assert len(loads) == 1
    assert calls[0]["num_inference_steps"] == 40
    assert calls[0]["guidance"] == 1.0
    assert Path(calls[1]["image_paths"][0]).name == "reference-0.png"
    with Image.open(io.BytesIO(base64.b64decode(result["data"][0]["b64_json"]))) as output:
        assert output.mode == "RGBA" and output.getpixel((0, 0))[3] == 0

    checkpoint_info.revision = "a" * 40
    with pytest.raises(ModelWorkerError, match="checkpoint revision"):
        adapter._checkpoint(MODULE.QWEN_IMAGE_21_ID)
    with pytest.raises(ValueError, match="divisible by 32"):
        adapter._parameters({"prompt": "test", "size": "272x256"}, edit=False, unified=True)


def test_qwen_21_distribution_requires_installing_user_consent():
    spec = json.loads((PACKAGE / "META/checkpoint-distribution-21.json").read_text())
    assert spec["modelId"] == MODULE.QWEN_IMAGE_21_ID
    assert spec["revision"] == MODULE.QWEN_IMAGE_21_REVISION
    terms = spec["license"]
    assert terms["termsHash"] == "sha256:" + hashlib.sha256(terms["termsText"].encode()).hexdigest()
    assert terms["usagePolicy"] == "non_commercial"
    assert terms["downloadConsent"]["required"] is True
    assert terms["downloadConsent"]["acceptanceOptions"] == [
        "accepted_license_terms", "obtained_separate_license",
    ]
