from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from ai2apps import __version__
from ai2apps.branding import (
    INDEPENDENCE_NOTICE,
    PRODUCT_NAME,
    PRODUCT_TAGLINE,
    UPSTREAM_NAME,
)
from ai2apps.cli import _apply_environment_compatibility


def test_product_identity_and_attribution() -> None:
    assert __version__.startswith("0.1.")
    assert PRODUCT_NAME == "AI2Apps"
    assert PRODUCT_TAGLINE == "The Edge Supermodel Ecosystem"
    assert UPSTREAM_NAME == "oMLX"
    assert "independent" in INDEPENDENCE_NOTICE.lower()
    assert "not affiliated" in INDEPENDENCE_NOTICE.lower()


def test_ai2apps_environment_maps_to_runtime(monkeypatch) -> None:
    runtime_name = "OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH"
    monkeypatch.setenv("AI2APPS_DEEPSEEK_V4_SCOPE_PROBE_DEPTH", "43")
    monkeypatch.delenv(runtime_name, raising=False)

    try:
        _apply_environment_compatibility()
        assert os.environ[runtime_name] == "43"
    finally:
        # The compatibility layer intentionally creates runtime variables
        # directly in os.environ.  monkeypatch cannot track keys created by
        # the function, so remove the derived value explicitly.
        os.environ.pop(runtime_name, None)


def test_environment_does_not_override_explicit_runtime_value(monkeypatch) -> None:
    monkeypatch.setenv("AI2APPS_PORT", "9000")
    monkeypatch.setenv("OMLX_PORT", "8000")

    _apply_environment_compatibility()

    assert os.environ["OMLX_PORT"] == "8000"


def test_ai2apps_environment_overrides_legacy_product_value(monkeypatch) -> None:
    monkeypatch.setenv("DYNAMOE_PORT", "7000")
    monkeypatch.setenv("AI2APPS_PORT", "9000")
    monkeypatch.delenv("OMLX_PORT", raising=False)

    try:
        _apply_environment_compatibility()
        assert os.environ["OMLX_PORT"] == "9000"
    finally:
        os.environ.pop("OMLX_PORT", None)


def test_ai2apps_svg_assets_are_valid() -> None:
    static = Path("ai2apps/web/static")
    for name in (
        "favicon.svg",
        "logo-light.svg",
        "logo-dark.svg",
        "navbar-logo-light.svg",
        "navbar-logo-dark.svg",
    ):
        root = ET.parse(static / name).getroot()
        assert root.tag.endswith("svg")


def test_chat_exposes_engine_boost_modes() -> None:
    html = Path("ai2apps/web/templates/chat.html").read_text()
    pool = Path("omlx/engine_pool.py").read_text()
    routes = Path("omlx/admin/routes.py").read_text()
    assert "ENGINE BOOST" in html
    assert 'value="natural">Natural · Full fidelity' in html
    assert 'value="auto">Auto · 2K Turbo / 10K Blast' in html
    assert 'value="turbo">Turbo · Head3 Prefill' in html
    assert 'value="blast">Blast · Head2' in html
    assert "/v1/ai2apps/engine/boost" in html
    assert "ai2apps_engine_boost" in html
    assert "KV CONTINUITY" in html
    assert "ai2apps_kv_policy" in html
    assert 'value="session">Continuous · Same session' in html
    assert "SSD PRESSURE · 10 TOK" in html
    assert "currentSsdPressure" in html
    assert "currentSsdSwapColor" in html
    assert "state?.epoch || 0" in html
    assert ">RUSH</span>" in html
    assert '@pointerdown.prevent="beginRush($event)"' in html
    assert '@pointerup.prevent="releaseRush()"' in html
    assert "Hold for temporary Blast (Head2)" in html
    assert html.count('x-show="isCacheMoeMode"') >= 2
    assert '"cache_moe"' in pool
    assert '"cache_moe"' in routes
