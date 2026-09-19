import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("z_image_base_adapter", ROOT / "src/worker_adapter.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_defaults_and_cfg():
    params = module.ZImageAdapter._parameters({"prompt": "test"})
    assert params[3:5] == (30, 4.0)
    with pytest.raises(ValueError):
        module.ZImageAdapter._parameters({"prompt": "test", "guidance": 0})
    assert module.ZImageAdapter._parameters({"prompt": "test", "steps": 50, "guidance": 5})[3:5] == (50, 5)

def test_turbo_rejected():
    with pytest.raises(ModelWorkerError):
        module.ZImageAdapter._model({"model": "Tongyi-MAI/Z-Image-Turbo"})

def test_cfg_negative_forwarding(tmp_path):
    for name in ("transformer", "text_encoder", "vae", "tokenizer"):
        (tmp_path / name).mkdir()
    calls = []
    class Pipeline:
        def generate_image(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(image=Image.new("RGB", (1024,1024)))
    context = SimpleNamespace(data_root=tmp_path, checkpoint_for=lambda _: SimpleNamespace(path=tmp_path, revision="test"))
    adapter = module.ZImageAdapter(context, pipeline_factory=lambda **_: Pipeline())
    request = ModelWorkerRequest("image_generation", {"model": module.PACKAGE_MODEL_ID, "prompt": "boat", "negative_prompt": "text"}, "test", output_root=tmp_path)
    result = asyncio.run(adapter.invoke(request))
    assert calls[0]["guidance"] == 4
    assert calls[0]["num_inference_steps"] == 30
    assert calls[0]["negative_prompt"] == "text"
    assert result["image"]["format"] == "png"

def test_edit_not_advertised_or_accepted(tmp_path):
    adapter = module.ZImageAdapter(None)
    with pytest.raises(ModelWorkerError):
        asyncio.run(adapter.invoke(ModelWorkerRequest("image_edit", {}, "test", output_root=tmp_path)))

def test_native_base_pipeline():
    source = (ROOT / "src/worker_adapter.py").read_text()
    assert "ModelConfig.z_image()" in source
    assert "ModelConfig.z_image_turbo()" not in source
    assert "from optimized_pipeline" not in source
