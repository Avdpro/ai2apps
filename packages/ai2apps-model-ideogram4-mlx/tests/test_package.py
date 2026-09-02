from __future__ import annotations

import asyncio
import base64
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml
from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
SPEC = importlib.util.spec_from_file_location(
    "ideogram4_worker_adapter", SOURCE / "worker_adapter.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeContext:
    def __init__(self, checkpoint: Path, data_root: Path):
        self._checkpoint = checkpoint
        self.data_root = data_root
        self.package_root = PACKAGE

    def checkpoint_for(self, _model_id):
        return SimpleNamespace(
            path=self._checkpoint,
            revision=MODULE.WEIGHTS_REVISION,
        )


class FakePipeline:
    def __init__(self):
        self.calls = []

    def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        edit = kwargs["image"] is not None
        effective_steps = 7 if edit else kwargs["steps"]
        report = {
            "effective_steps": effective_steps,
            "staged_model_lifecycle": True,
            "compiled_denoisers": False,
            "denoise_seconds": 1.25,
            "decode_seconds": 0.2,
            "stage_seconds": {"encode_image": 0.1} if edit else {},
            "peak_memory_bytes": 1234,
        }
        return Image.new("RGB", (kwargs["width"], kwargs["height"]), "navy"), report


def derived_checkpoint(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in MODULE._DERIVED_COMPONENTS:
        (root / name).write_bytes(b"test")
    return root


def request(tmp_path: Path, operation: str, payload: dict):
    from ai2apps.model_worker import ModelWorkerRequest

    output = tmp_path / "output"
    output.mkdir(exist_ok=True)
    return ModelWorkerRequest(operation, payload, "request-1", output_root=output)


def data_url(color="red") -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def adapter(tmp_path: Path, pipeline: FakePipeline):
    return MODULE.Ideogram4Adapter(
        FakeContext(derived_checkpoint(tmp_path / "weights"), tmp_path / "data"),
        pipeline_factory=lambda **_kwargs: pipeline,
    )


def test_generation_uses_optimized_q4_pipeline(tmp_path):
    pipeline = FakePipeline()
    result = asyncio.run(
        adapter(tmp_path, pipeline).invoke(
            request(
                tmp_path,
                "image_generation",
                {
                    "model": MODULE.UPSTREAM_ID,
                    "prompt": "Swiss poster",
                    "size": "512x512",
                    "steps": 12,
                    "quantization": "q4",
                },
            )
        )
    )
    assert result["operation"] == "image_generation"
    assert result["image"]["dataUrl"].startswith("data:image/png;base64,")
    assert result["optimization"]["native_mlx"] is True
    assert result["optimization"]["staged_model_lifecycle"] is True
    assert result["optimization"]["bf16_mlp"] is True
    assert result["optimization"]["bf16_sdpa"] is True
    assert result["optimization"]["fused_qk_rms_mrope"] is True
    assert pipeline.calls[0][1]["image"] is None


def test_edit_passes_decoded_reference_and_strength(tmp_path):
    pipeline = FakePipeline()
    result = asyncio.run(
        adapter(tmp_path, pipeline).invoke(
            request(
                tmp_path,
                "image_edit",
                {
                    "model": MODULE.PACKAGE_MODEL_ID,
                    "prompt": "change the circle to blue",
                    "size": "512x512",
                    "imageDataUrls": [data_url()],
                    "strength": 0.55,
                },
            )
        )
    )
    call = pipeline.calls[0][1]
    assert isinstance(call["image"], Image.Image)
    assert call["strength"] == 0.55
    assert result["imageStrength"] == 0.55
    assert result["optimization"]["effective_steps"] == 7
    assert result["optimization"]["encode_image_seconds"] == 0.1


def test_edit_rejects_invalid_reference_inputs(tmp_path):
    for payload in (
        {"imageDataUrls": [], "strength": 0.5},
        {"imageDataUrls": [data_url(), data_url("blue")], "strength": 0.5},
        {"imageDataUrls": ["data:image/png;base64,bm90LWltYWdl"], "strength": 0.5},
        {"imageDataUrls": [data_url()], "strength": 0.0},
    ):
        payload.update({"model": MODULE.UPSTREAM_ID, "prompt": "edit"})
        try:
            asyncio.run(
                adapter(tmp_path, FakePipeline()).invoke(
                    request(tmp_path, "image_edit", payload)
                )
            )
        except Exception as exc:
            assert getattr(exc, "code", None) == "invalid_request"
        else:
            raise AssertionError("invalid edit request was accepted")


def test_parameters_enforce_geometry_q4_and_compile_type():
    for payload in (
        {"prompt": "x", "size": "500x512"},
        {"prompt": "x", "quantization": "q8"},
        {"prompt": "x", "compileDenoisers": "yes"},
    ):
        try:
            MODULE.Ideogram4Adapter._parameters(payload, edit=False)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid parameters were accepted")


def test_manifest_pins_sources_and_optimized_capabilities():
    outer = json.loads((PACKAGE / "ai2apps.json").read_text())
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    lock = json.loads((PACKAGE / "META/source-lock.json").read_text())
    assert outer["package"]["version"] == service["version"] == "0.1.1"
    model = service["models"][0]
    assert model["weights"]["revision"] == MODULE.WEIGHTS_REVISION
    assert model["weights"]["distribution_id"] == (
        "dist_ai2apps_ideogram4_fp8_bbee2ab2_v1"
    )
    assert model["metadata"]["modelscope"]["revision"] == (
        "7ce334bb86142cd10c04bbb72d4e871572dd976f"
    )
    assert model["image_capabilities"]["operations"] == [
        "image_generation",
        "image_edit",
    ]
    execution = model["image_capabilities"]["execution"]
    assert execution["quantizations"] == ["q4"]
    assert execution["staged_model_lifecycle"] is True
    assert execution["fused_qk_rms_mrope"] is True
    assert execution["image_to_image"]["method"] == "sdedit"
    assert lock["qwen_config"]["revision"] == MODULE.QWEN_CONFIG_REVISION


def test_bundled_qwen_tokenizer_config_is_complete():
    root = PACKAGE / "assets/qwen3-vl-8b-config"
    for name in (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "merges.txt",
        "vocab.json",
    ):
        assert (root / name).is_file()
