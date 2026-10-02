"""Direct still-image refinement: decoded pixels to a lossless PNG artifact."""

from __future__ import annotations

import gc
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps, PngImagePlugin

INPUT_FORMATS = {"PNG", "JPEG", "WEBP"}


def load_image(path):
    """Apply orientation/color conversion once and keep alpha outside the model."""
    with Image.open(path) as source:
        if source.format not in INPUT_FORMATS or getattr(source, "n_frames", 1) != 1:
            raise ValueError("Use a single-frame PNG, JPEG or WebP image")
        if source.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "CMYK"}:
            raise ValueError(
                "This version supports 8-bit images; convert HDR/16-bit input first"
            )
        image = ImageOps.exif_transpose(source)
        image.load()
        alpha = (
            image.convert("RGBA").getchannel("A")
            if ("A" in image.getbands() or "transparency" in image.info)
            else None
        )
        profile = source.info.get("icc_profile")
        color = image.convert("RGB") if image.mode != "CMYK" else image
        if profile:
            try:
                color = ImageCms.profileToProfile(
                    color,
                    ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                    ImageCms.createProfile("sRGB"),
                    outputMode="RGB",
                )
            except (OSError, ValueError, ImageCms.PyCMSError) as exc:
                raise ValueError("Invalid or unsupported image color profile") from exc
        return np.array(color.convert("RGB")), alpha


def upscale_image(
    source,
    output,
    model_root,
    prompt,
    seed,
    data_root,
    check,
    progress,
    infer_factory=None,
):
    import mlx.core as mx
    from prompt_context import fixed_context
    from sol_refiner_mlx.pipeline import Refiner

    check()
    rgb, alpha = load_image(source)
    height, width = rgb.shape[:2]
    progress({"phase": "image_upscaling", "current": 0, "total": 1})
    ph, pw = (-height) % 32, (-width) % 32
    padded = np.pad(rgb, ((0, ph), (0, pw), (0, 0)), mode="edge")
    pixels = mx.array(
        (padded.astype(np.float32) / 127.5 - 1).transpose(2, 0, 1)[None, :, None]
    )
    mx.set_cache_limit(512 * 1024**2)
    runner = (infer_factory or Refiner)(Path(model_root))
    decoded = runner(
        pixels,
        prompt,
        25.0,
        seed,
        context_path=fixed_context(model_root, prompt),
        check_cancel=check,
    )
    check()
    if decoded.shape[2] != 1 or not bool(mx.all(mx.isfinite(decoded)).item()):
        raise ValueError("Image refinement produced invalid pixels")
    rgb = np.rint(
        np.array(
            mx.clip(
                (
                    decoded[0, :, 0, : height * 2, : width * 2]
                    .transpose(1, 2, 0)
                    .astype(mx.float32)
                    + 1
                )
                / 2,
                0,
                1,
            )
        )
        * 255
    ).astype(np.uint8)
    image = Image.fromarray(rgb)
    if alpha is not None:
        image.putalpha(alpha.resize(image.size, Image.Resampling.LANCZOS))
    check()
    metadata = PngImagePlugin.PngInfo()
    metadata.add(b"sRGB", b"\x00")
    image.save(output, format="PNG", pnginfo=metadata)
    del decoded, pixels, runner
    gc.collect()
    mx.clear_cache()
    check()
    progress({"phase": "image_upscaling", "current": 1, "total": 1})
    return {
        "kind": "image_upscaling",
        "width": width * 2,
        "height": height * 2,
        "scale": 2,
        "output_format": "png",
        "color_space": "sRGB",
        "alpha_preserved": alpha is not None,
    }
