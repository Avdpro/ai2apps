import hashlib
import json
from pathlib import Path

import yaml

from omlx.patches.deepseek_v41.engine import DeepseekV41Engine

ROOT = Path(__file__).parents[1]


def test_dsv41_package_binds_ssd_distribution_and_runtime_175():
    manifest = json.loads((ROOT / "ai2apps.json").read_text())
    service = yaml.safe_load((ROOT / "service.yaml").read_text())
    distribution = json.loads((ROOT / "META/checkpoint-distribution.json").read_text())
    model = service["models"][0]
    assert manifest["package"]["version"] == service["version"] == "0.1.1"
    assert manifest["dependencies"][0]["version"] == ">=1.7.5 <2.0.0"
    assert service["requires"]["services"][0]["version"] == ">=1.7.5,<2.0.0"
    assert model["metadata"]["reasoning"] == {
        "schema": "ai2apps.reasoning/v1",
        "mode": "optional",
        "format": "think_tags",
        "default_enabled": True,
    }
    assert model["weights"]["distribution_id"] == distribution["distributionId"]
    assert model["weights"]["repo_id"] == "Avdpro/DeepSeek-V4.1-Flash-SSD"
    preparation = model["weights"]["preparation"]
    assert preparation["conversion"]["variant"] == "dsv41-original-fp4-six-segment-v1"
    assert preparation["storage_policies"] == ["keep_source"]
    assert preparation["execution_modes"] == ["cached"]


def test_dsv41_scope_pack_matches_profile():
    assets = ROOT / "src/omlx_model_deepseek_v41_flash/assets"
    profile = assets / "scope-profile.json"
    pack = json.loads((assets / "scope-pack.json").read_text())
    assert hashlib.sha256(profile.read_bytes()).hexdigest() == pack["profile"]["sha256"]
    assert json.loads(profile.read_text())["format"] == "ai2apps-deepseek-v41-runtime-profile"


def test_dsv41_engine_maps_package_toggle_to_native_mode():
    assert DeepseekV41Engine._reasoning_options({"enable_thinking": True}) == (
        "thinking",
        None,
    )
    assert DeepseekV41Engine._reasoning_options({"enable_thinking": False}) == (
        "chat",
        None,
    )
    assert DeepseekV41Engine._reasoning_options(
        {"enable_thinking": True, "reasoning_effort": "high"}
    ) == ("thinking", "high")
