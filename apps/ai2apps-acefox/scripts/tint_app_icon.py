#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from PIL import Image


def parse_hex_color(value: str) -> tuple[int, int, int]:
    raw = value.removeprefix("#")
    if len(raw) != 6:
        raise ValueError("color must use #RRGGBB")
    try:
        return tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as exc:
        raise ValueError("color must use #RRGGBB") from exc


def tint_upper_sphere(
    image: Image.Image,
    target: tuple[int, int, int],
) -> Image.Image:
    result = image.convert("RGBA")
    pixels = result.load()
    width, height = result.size
    center_x = (width - 1) / 2
    center_y = (height - 1) / 2
    radius_squared = (min(width, height) * 0.305) ** 2

    for y in range(height):
        for x in range(width):
            if (x - center_x) ** 2 + (y - center_y) ** 2 > radius_squared:
                continue
            red, green, blue, alpha = pixels[x, y]
            luminance = round((red + green + blue) / 3)
            if alpha == 0 or max(red, green, blue) - min(red, green, blue) > 8:
                continue
            # The upper sphere is a subtly shaded neutral grey around 188.
            # The lower sphere and outer tile are both brighter than this
            # range; the black outline and logo are darker.
            if not 145 <= luminance <= 220:
                continue
            shading = luminance - 188
            pixels[x, y] = (
                max(0, min(255, target[0] + shading)),
                max(0, min(255, target[1] + shading)),
                max(0, min(255, target[2] + shading)),
                alpha,
            )
    return result


def count_tinted_upper_sphere_pixels(
    image: Image.Image,
    target: tuple[int, int, int],
) -> int:
    """Count pixels that retain the tint's equal-channel shading offset."""
    source = image.convert("RGBA")
    pixels = source.load()
    width, height = source.size
    center_x = (width - 1) / 2
    center_y = (height - 1) / 2
    radius_squared = (min(width, height) * 0.305) ** 2
    matched = 0
    for y in range(round(center_y)):
        for x in range(width):
            if (x - center_x) ** 2 + (y - center_y) ** 2 > radius_squared:
                continue
            red, green, blue, alpha = pixels[x, y]
            offsets = (red - target[0], green - target[1], blue - target[2])
            if (
                alpha != 0
                and max(offsets) - min(offsets) <= 2
                and -50 <= sum(offsets) / 3 <= 40
            ):
                matched += 1
    return matched


def verify_icns_tint(icns: Path, color: tuple[int, int, int]) -> None:
    with Image.open(icns) as source:
        sizes = source.info.get("sizes", [])
        if not sizes:
            raise RuntimeError(f"icon has no native representations: {icns}")
        largest_spec = max(sizes, key=lambda item: item[0] * item[2])
        # ICNS frames may retain a lazy seek into the container. Materialize a
        # copy before the source file is closed so verification is deterministic.
        largest = source.icns.getimage(largest_spec).copy()
    minimum_pixels = max(100, round(largest.width * largest.height * 0.01))
    matched = count_tinted_upper_sphere_pixels(largest, color)
    if matched < minimum_pixels:
        raise RuntimeError(
            f"icon tint verification failed for {icns}: "
            f"found {matched}, expected at least {minimum_pixels} tinted pixels"
        )


def tint_icns(icns: Path, color: tuple[int, int, int]) -> None:
    original_mode = icns.stat().st_mode
    temporary_path: Path | None = None
    try:
        with Image.open(icns) as source:
            representations: dict[int, Image.Image] = {}
            for logical_width, logical_height, scale in source.info.get("sizes", []):
                native = source.icns.getimage((logical_width, logical_height, scale))
                representation = tint_upper_sphere(native, color)
                representations[logical_width * scale] = representation
        if 1024 not in representations:
            raise RuntimeError(f"icon is missing its 1024-pixel representation: {icns}")
        with tempfile.NamedTemporaryFile(
            prefix=".ai2apps-icon-tint.",
            suffix=".icns",
            dir=icns.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        largest = representations.pop(1024)
        largest.save(
            temporary_path,
            format="ICNS",
            append_images=list(representations.values()),
        )
        os.replace(temporary_path, icns)
        temporary_path = None
        os.chmod(icns, original_mode)
        verify_icns_tint(icns, color)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--icns", type=Path, required=True)
    parser.add_argument("--color", required=True)
    arguments = parser.parse_args()
    if not arguments.icns.is_file():
        parser.error(f"icon not found: {arguments.icns}")
    try:
        color = parse_hex_color(arguments.color)
    except ValueError as exc:
        parser.error(str(exc))
    tint_icns(arguments.icns, color)


if __name__ == "__main__":
    main()
