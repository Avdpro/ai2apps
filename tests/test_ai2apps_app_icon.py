from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

SCRIPT = (
    Path(__file__).parents[1]
    / "apps/ai2apps-acefox/scripts/tint_app_icon.py"
)
SPEC = importlib.util.spec_from_file_location("ai2apps_tint_app_icon", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_tint_upper_sphere_preserves_logo_lower_sphere_and_outer_tile():
    image = Image.new("RGBA", (100, 100), (250, 250, 250, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 20, 80, 80), fill=(188, 188, 188, 255))
    draw.rectangle((20, 50, 80, 80), fill=(235, 235, 235, 255))
    draw.line((35, 35, 65, 65), fill=(51, 51, 51, 255), width=5)

    result = MODULE.tint_upper_sphere(image, (199, 231, 250))

    assert result.getpixel((50, 30))[:3] == (199, 231, 250)
    assert result.getpixel((50, 70))[:3] == (235, 235, 235)
    assert result.getpixel((50, 50))[:3] == (51, 51, 51)
    assert result.getpixel((5, 5))[:3] == (250, 250, 250)
    assert MODULE.count_tinted_upper_sphere_pixels(result, (199, 231, 250)) > 100


def test_untinted_icon_does_not_satisfy_blue_tint_contract():
    image = Image.new("RGBA", (100, 100), (250, 250, 250, 255))
    ImageDraw.Draw(image).ellipse((20, 20, 80, 80), fill=(188, 188, 188, 255))

    assert MODULE.count_tinted_upper_sphere_pixels(image, (199, 231, 250)) == 0


@pytest.mark.parametrize("value", ["blue", "#12345", "#GGEEFF"])
def test_icon_tint_rejects_invalid_color(value):
    with pytest.raises(ValueError, match="#RRGGBB"):
        MODULE.parse_hex_color(value)
