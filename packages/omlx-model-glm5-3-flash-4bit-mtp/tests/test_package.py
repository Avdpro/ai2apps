import importlib.util
import json
from pathlib import Path

import yaml


PACKAGE = Path(__file__).parents[1]


def test_manifest_id_version_and_runtime_dependency_match_service():
    manifest = json.loads((PACKAGE / "ai2apps.json").read_text())
    service = yaml.safe_load((PACKAGE / "service.yaml").read_text())
    assert manifest["package"]["id"] == "ai2apps/model-glm5-3-flash-4bit-mtp"
    assert manifest["package"]["version"] == service["version"] == "0.1.0"
    assert manifest["dependencies"] == [
        {
            "packageId": "ai2apps/runtime-omlx",
            "version": ">=1.5.5 <2.0.0",
            "optional": False,
        }
    ]
    assert service["requires"]["services"][0]["version"] == ">=1.5.5,<2.0.0"


def test_checkpoint_is_dual_source_and_immutable():
    distribution = json.loads(
        (PACKAGE / "META/checkpoint-distribution.json").read_text()
    )
    model = yaml.safe_load((PACKAGE / "service.yaml").read_text())["models"][0]
    sources = {item["type"]: item for item in distribution["sourceRepositories"]}
    assert set(sources) == {"huggingface", "modelscope"}
    assert all(len(item["revision"]) == 40 for item in sources.values())
    assert sources["modelscope"]["revision"] == (
        "760a9f63f4553ff1f725bddf63ca9f20577e4441"
    )
    assert model["weights"]["distribution_id"] == distribution["distributionId"]


def test_glm_cache_recipe_and_product_defaults():
    model = yaml.safe_load((PACKAGE / "service.yaml").read_text())["models"][0]
    preparation = model["weights"]["preparation"]
    assert preparation["family"] == "glm5_next"
    assert preparation["conversion"]["variant"] == (
        "glm5-next-affine-q4-gate-up-fused-v2"
    )
    assert preparation["dynamic_slots"] == 96
    assert preparation["hot_slots"] == 16
    assert preparation["vision_l1_reserve_slots"] == 16
    assert preparation["execution_modes"] == ["cached"]
    assert model["metadata"]["execution_modes"] == ["cached"]


def test_worker_adapter_defaults_to_exact_dynamic_multimodal_path():
    path = PACKAGE / "src/worker_adapter.py"
    spec = importlib.util.spec_from_file_location("glm5_package_worker_adapter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.Glm5DynamicChatAdapter._TIER_SLOTS == {
        "lean": 80,
        "balanced": 96,
    }
    source = path.read_text()
    assert 'os.environ["OMLX_GLM5_BOOST_MODE"] = "natural"' in source
    assert 'os.environ.setdefault("OMLX_GLM5_MTP_ENABLED", "0")' in source


def test_scope_asset_is_small_and_has_general_scope():
    path = (
        PACKAGE
        / "src/omlx_model_glm5_3_flash_4bit_mtp/assets/scope-profile.json"
    )
    profile = json.loads(path.read_text())
    assert path.stat().st_size < 2 * 1024 * 1024
    assert profile["format"] == "omlx-glm5-dynamic-scope-profile"
    assert "general" in profile["scopes"]
