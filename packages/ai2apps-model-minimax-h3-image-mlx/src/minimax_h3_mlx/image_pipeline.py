"""Staged local H3-Image text-to-image inference on the shared MLX Runtime."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import mlx.core as mx
import numpy as np
from PIL import Image, ImageOps

from .image_dit import MiniMaxH3ImageDiT, load_image_dit
from .image_vae import load_image_vae
from .text_encoder import MiniMaxH3TextEncoder, VisionFeatures


@dataclass
class ImageReferenceCache:
    """One reference latent and one vision result for immutable checkpoints."""

    key: tuple[Path, tuple[int, int], bytes] | None = None
    latent: mx.array | None = None
    vision_key: tuple[Path, tuple[int, int], bytes] | None = None
    vision_features: VisionFeatures | None = None


@dataclass
class ImageDenoiserCache:
    """One loaded DiT with a checkpoint identity supplied by the Worker."""

    root: Path
    model: MiniMaxH3ImageDiT | None = None


def _resize_reference(image: Image.Image, maximum_short_edge: int) -> Image.Image:
    scale = min(max(min(image.size), 1024), maximum_short_edge) / min(image.size)
    size = tuple(max(32, round(side * scale / 32) * 32) for side in image.size)
    return image.resize(size, Image.Resampling.LANCZOS)


def generate_image(
    model_dir: str | Path,
    text_encoder_dir: str | Path,
    prompt: str,
    *,
    width: int = 512,
    height: int = 512,
    seed: int = 42,
    references: Sequence[Image.Image] = (),
    reference_cache: ImageReferenceCache | None = None,
    denoiser_cache: ImageDenoiserCache | None = None,
    progress: Callable[[str, float], None] | None = None,
    on_step: Callable[[int, mx.array], None] | None = None,
) -> Image.Image:
    """Generate or edit one image with the official six-step model."""
    if not prompt.strip():
        raise ValueError("The image prompt cannot be empty.")
    if min(width, height) < 32 or width % 32 or height % 32:
        raise ValueError("Width and height must be positive multiples of 32.")
    if len(references) > 16:
        raise ValueError("H3-Image accepts up to sixteen reference images.")

    def report(phase: str, start: float) -> None:
        if progress is not None:
            progress(phase, perf_counter() - start)

    start = perf_counter()
    root = Path(model_dir)
    images = [ImageOps.exif_transpose(image).convert("RGB") for image in references]
    vision_images = [_resize_reference(image, 1024) for image in images]
    vision_features = None
    on_vision = None
    if reference_cache is not None and len(vision_images) == 1:
        vision_image = vision_images[0]
        vision_key = (
            Path(text_encoder_dir).resolve(), vision_image.size,
            hashlib.sha256(vision_image.tobytes()).digest(),
        )
        if reference_cache.vision_key == vision_key:
            vision_features = reference_cache.vision_features

        def remember_vision(features: VisionFeatures) -> None:
            reference_cache.vision_key = vision_key
            reference_cache.vision_features = features
        on_vision = remember_vision

    encoder = MiniMaxH3TextEncoder(text_encoder_dir, load_vision=bool(images) and vision_features is None)
    context, tags = encoder.encode(
        prompt, vision_images, picture_label="Picture {}: ",
        vision_features=vision_features, on_vision=on_vision,
    )
    mx.eval(context)
    del encoder
    mx.clear_cache()
    report("text", start)

    vae = None
    reference_latents = []
    if images:
        start = perf_counter()
        for image in images:
            resized = _resize_reference(image, 2048)
            key = None
            if reference_cache is not None:
                key = (root.resolve(), resized.size, hashlib.sha256(resized.tobytes()).digest())
                if reference_cache.key == key and reference_cache.latent is not None:
                    reference_latents.append(reference_cache.latent)
                    continue
            if vae is None:
                vae = load_image_vae(root / "vae", load_encoder=True)
            rgb = np.asarray(resized, dtype=np.float32) / 255.0
            latent = vae.encode(mx.array(rgb)[None])
            mx.eval(latent)
            reference_latents.append(latent)
            if reference_cache is not None:
                reference_cache.key = key
                reference_cache.latent = latent
        # The final decode uses the same decoder. Release only the encoder
        # before loading the DiT, so editing doesn't load the decoder twice.
        if vae is not None:
            del vae["encoder"]
            del vae["quant_conv"]
        mx.clear_cache()
        report("reference_encode", start)

    start = perf_counter()
    if denoiser_cache is None:
        dit = load_image_dit(root)
    else:
        if denoiser_cache.root != root.resolve():
            raise ValueError("Denoiser cache belongs to a different checkpoint.")
        if denoiser_cache.model is None:
            denoiser_cache.model = load_image_dit(root)
        dit = denoiser_cache.model
    noise = mx.random.normal(
        (1, dit.config.latents_dim, 1, height // 16, width // 16),
        key=mx.random.key(seed),
    )
    latent = dit.denoise(
        context, noise, text_tags=tags, reference_latents=reference_latents,
        reference_seed=seed, on_step=on_step,
    )
    mx.eval(latent)
    del dit
    mx.clear_cache()
    report("denoise", start)

    start = perf_counter()
    if vae is None:
        vae = load_image_vae(root / "vae")
    pixels = vae.decode(latent)[0]
    rgb = np.asarray(mx.clip(mx.round(pixels * 255.0), 0, 255).astype(mx.uint8))
    del vae
    mx.clear_cache()
    report("decode", start)
    return Image.fromarray(rgb)
