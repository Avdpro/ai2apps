from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ai2apps.environment_check import (
    GIB,
    _model_recommendation,
    collect_environment_report,
)


def test_model_recommendations_scale_with_unified_memory_and_disk():
    compact = _model_recommendation(16 * GIB - 1, 100 * GIB)
    research = _model_recommendation(128 * GIB, 500 * GIB)

    assert compact["tier"] == "compact"
    assert compact["max_concurrent_requests"] == 1
    assert research["tier"] == "research"
    assert "DeepSeek" in research["model_family"]
    assert research["disk_ready"] is True


def test_environment_report_fails_closed_when_required_components_are_missing(
    tmp_path: Path,
):
    memory = SimpleNamespace(total=64 * GIB, available=48 * GIB, percent=25.0)
    swap = SimpleNamespace(total=8 * GIB, used=0, percent=0.0)

    with (
        patch("ai2apps.environment_check.psutil.virtual_memory", return_value=memory),
        patch("ai2apps.environment_check.psutil.swap_memory", return_value=swap),
        patch("ai2apps.environment_check.psutil.cpu_count", return_value=8),
        patch("ai2apps.environment_check.importlib.util.find_spec", return_value=None),
        patch("ai2apps.environment_check.sys.platform", "darwin"),
        patch("ai2apps.environment_check.platform.machine", return_value="arm64"),
        patch("ai2apps.environment_check._sysctl", return_value="Apple M-series"),
    ):
        report = collect_environment_report(
            model_dir=tmp_path / "models",
            hf_cache_dir=tmp_path / "hf",
            settings={
                "prefill_memory_guard": False,
                "memory_guard_tier": "aggressive",
                "hf_cache_enabled": False,
            },
        )

    assert report["status"] == "critical"
    assert report["host"]["apple_silicon"] is True
    assert any(item["id"] == "dependencies" and item["status"] == "fail" for item in report["checks"])
    assert {action["id"] for action in report["actions"]} == {
        "enable_memory_guard",
        "set_memory_guard_balanced",
    }
    assert report["huggingface"]["network"]["status"] == "skipped"


def test_environment_system_app_is_registered_and_renderable():
    from ai2apps.apps import SYSTEM_APP_MANIFESTS
    from omlx.admin.routes import _DASHBOARD_APP_TEMPLATES, _HOST_APP_ENTRIES

    manifest = next(item for item in SYSTEM_APP_MANIFESTS if item["id"] == "ai2apps.environment")
    assert manifest["entry"]["resource"] == "ai2apps:system/environment"
    assert _DASHBOARD_APP_TEMPLATES["ai2apps.environment"] == "system_apps/environment.html"
    assert _HOST_APP_ENTRIES["ai2apps:system/environment"].endswith("ai2apps.environment")


def test_deep_check_adds_network_and_isolated_metal_probes(tmp_path: Path):
    with (
        patch(
            "ai2apps.environment_check._network_check",
            return_value={"status": "pass", "message": "network ready"},
        ),
        patch(
            "ai2apps.environment_check._metal_check",
            return_value={"status": "pass", "message": "metal ready"},
        ),
    ):
        report = collect_environment_report(
            model_dir=tmp_path,
            hf_cache_dir=tmp_path,
            check_network=True,
        )

    checks = {item["id"]: item for item in report["checks"]}
    assert checks["huggingface_network"]["status"] == "pass"
    assert checks["metal_runtime"]["detail"] == "metal ready"
