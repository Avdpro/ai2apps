from __future__ import annotations

from pathlib import Path

_WEB_ROOT = Path(__file__).with_name("web")


def build_test_center_html() -> str:
    template = (_WEB_ROOT / "test_center.html").read_text(encoding="utf-8")
    style = (_WEB_ROOT / "test_center.css").read_text(encoding="utf-8")
    script = (_WEB_ROOT / "test_center.js").read_text(encoding="utf-8")
    return template.replace("/* __TEST_CENTER_STYLE__ */", style).replace(
        "/* __TEST_CENTER_SCRIPT__ */", script
    )
