from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from dynamoe import __version__
from dynamoe.branding import INDEPENDENCE_NOTICE, PRODUCT_NAME, UPSTREAM_NAME
from dynamoe.cli import _apply_environment_compatibility


def test_product_identity_and_attribution() -> None:
    assert __version__.startswith("0.1.")
    assert PRODUCT_NAME == "DynaMoe"
    assert UPSTREAM_NAME == "oMLX"
    assert "independent" in INDEPENDENCE_NOTICE.lower()
    assert "not affiliated" in INDEPENDENCE_NOTICE.lower()


def test_dynamoe_environment_maps_to_runtime(monkeypatch) -> None:
    monkeypatch.setenv("DYNAMOE_DEEPSEEK_V4_SCOPE_PROBE_DEPTH", "43")
    monkeypatch.delenv("OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH", raising=False)

    _apply_environment_compatibility()

    assert os.environ["OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH"] == "43"


def test_environment_does_not_override_explicit_runtime_value(monkeypatch) -> None:
    monkeypatch.setenv("DYNAMOE_PORT", "9000")
    monkeypatch.setenv("OMLX_PORT", "8000")

    _apply_environment_compatibility()

    assert os.environ["OMLX_PORT"] == "8000"


def test_dynamoe_svg_assets_are_valid() -> None:
    static = Path("omlx/admin/static")
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
    html = Path("omlx/admin/templates/chat.html").read_text()
    pool = Path("omlx/engine_pool.py").read_text()
    routes = Path("omlx/admin/routes.py").read_text()
    assert "ENGINE BOOST" in html
    assert 'value="natural">Natural · Full fidelity' in html
    assert 'value="turbo">Turbo · Tail2' in html
    assert 'value="blast">Blast · Head2' in html
    assert "/v1/dynamoe/engine/boost" in html
    assert "dynamoe_engine_boost" in html
    assert "SSD PRESSURE · 10 TOK" in html
    assert "currentSsdPressure" in html
    assert "currentSsdSwapColor" in html
    assert "state?.epoch || 0" in html
    assert ">RUSH</span>" in html
    assert '@pointerdown.prevent="beginRush($event)"' in html
    assert '@pointerup.prevent="releaseRush()"' in html
    assert "Hold for temporary Blast (Head2)" in html
    assert html.count('x-show="isCacheMoeMode"') >= 5
    assert '"cache_moe"' in pool
    assert '"cache_moe"' in routes
