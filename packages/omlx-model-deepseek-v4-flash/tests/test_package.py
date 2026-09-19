from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from jinja2 import Environment

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_manifest_declares_required_reasoning_and_runtime_floor():
    manifest = yaml.safe_load((PACKAGE_ROOT / "service.yaml").read_text())
    model = manifest["models"][0]

    assert model["metadata"]["reasoning"] == {
        "schema": "ai2apps.reasoning/v1",
        "mode": "required",
        "format": "think_tags",
    }
    assert manifest["requires"]["services"][0]["version"] == ">=1.7.5,<2.0.0"


def test_package_template_opens_required_thinking():
    template = (
        PACKAGE_ROOT
        / "src/omlx_model_deepseek_v4_flash/assets/chat_template.jinja"
    ).read_text()

    assert "{{- '<think>\\n' -}}" in template
    assert "enable_thinking is defined and enable_thinking is false" in template
    rendered = Environment().from_string(template).render(
        messages=[{"role": "user", "content": "hi"}],
        add_generation_prompt=True,
        enable_thinking=True,
    )
    assert rendered == (
        "<｜begin▁of▁sentence｜><｜User｜>hi<｜Assistant｜><think>\n"
    )


def test_worker_adapter_owns_post_load_template_configuration():
    path = PACKAGE_ROOT / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("deepseek_v4_worker_adapter", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.create_adapter.__name__ == "create_adapter"
    assert hasattr(module.DeepSeekV4FlashWorkerAdapter, "configure_engine")


@pytest.mark.asyncio
async def test_worker_adapter_installs_packaged_template(monkeypatch):
    monkeypatch.syspath_prepend(str(PACKAGE_ROOT / "src"))
    path = PACKAGE_ROOT / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("deepseek_v4_worker_runtime", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    engine = SimpleNamespace(tokenizer=SimpleNamespace(chat_template="old"))
    adapter = module.DeepSeekV4FlashWorkerAdapter(None)

    await adapter.configure_engine(engine, None, {})

    assert "<｜Assistant｜>" in engine.tokenizer.chat_template
    assert "{{- '<think>\\n' -}}" in engine.tokenizer.chat_template
