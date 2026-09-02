"""Load and run the Flux 2 VAE shared by Ideogram 4."""

from __future__ import annotations

import base64
import re
from pathlib import Path

import mlx.core as mx
import numpy as np
from PIL import Image, ImageOps

_LATENT_NORM_F32 = "IY+iPLLdzz2dApg+qzSLPnuaW75uoSO+CqpNPcN0Gr6tSR2+TiZOvqV6nTwRB3894q/PPQMGir1HbMA+M1Jvvs0KtD5dP9S858TevNLg3b2vOhe+xks5vHFaa74b6XA+bhnfvW3k9D1AzCU9r32gPnliML6o7z6+eJ+xvjpHEr1pq9M8U7HQPXRrkT66/ok+AYpdvhyxN755ijI9lK0Zvg2RHr6vQ0K+4BLePM/DZT2GF9s9xmOMvSprwz4vhni+4M+2Piny+rxiWPG8cUjmvRDNEr4rLF+8XuJfvmPdbT4zbvC9OnnvPYf80Ty3i6A+CWMyvtafQr4tt7K+Pd0kvRSgnTytu5w9CGCZPniOhj5IZmG+jjQCvj3hRz2nIhC+/i4jvnt0Wb7VxqE8lz5iPawLzT1JqoO9c3HBPg4TXL6vYa8+IysBvekE/rzPZNy939YWvlTEyrxRC2q+q8WAPo3q1b3i5P49xqWQPT8bnj4ofji+YjhBvr/PsL7DpFO8GjTTPMu1oz3hpZI+EFGFPgX8Zb4mwhe+dUcmPUXOD76D+iS+FeFOvlgp1TxtxEY9h6bVPUU6gb3ansQ+ZlhlvglAsj7KmRq984AKvc9P5r23rRC+HLzpvJu9Xr6rsX4+p3fpvQNo+j26OmY9lEyePkD+OL7Qq0a+cJ2wvko6kLzL1dE/mtzZPzJD3j/GNPM/rXHVP3Jl2D+oxcg/XMPPP3YO8j/XWco/MtrNP1sIzj9lDdE/csbHPxz63T/ZXeU/1vjRP/KB1T+yTM0/c53gP0/h0D8pWdI/WwHPP6j8zD9ROtE/6cXGPwsH2D9xktc/mRPlP9tJ1T+NANQ/KHPUP55D0T8a+tg/71rdP67g9D8MztU/9obcP8SZyD/ORs8/6HHxP8bYyD9CGsw/u9zNP1/2zz9mv8c/e07ePwtI4z/hk9E/S/TUP+UrzD9yMuA/b63QPyaV0j+I7M4/uHHMP1AN0j+tOsU/QdLXP8e/1j9AHuU/mkbVP5fJ0z9qiNQ/dNTSP9E/1z9ruN4/uMP2P01J1j8sRNY/+XrJP3ydzz+7JvA/4XrHP4uFyT96/c4/vsLQP285xz9fmd0/10DnP/670j+aZNQ/QNjNP7Pf4D+Lz9I/usvQP0WRzj+lac0/nSXRP4p8xD9H4tM/6O3VP1fO5j8in9Y/4hjUP+uV1z+FotM/t3PWP3TS3T/9Z/g/YefWP7dp2j8IW8k/wETPP+yM7z9R/sc/hpLIP/nTzj8IVdA/zwPHP0YP3j/KMOU/OM3SP7Gi1D9U+cw/a1PgPx7x0j+KoNA/hZHOP53QzT/A19E/3e/DP+Cs0z9qgdU/7m/mP2CE1j/jCdQ/C7nXPw=="


def latent_norm() -> tuple[mx.array, mx.array]:
    values = np.frombuffer(base64.b64decode(_LATENT_NORM_F32), dtype="<f4")
    if values.shape != (256,):
        raise RuntimeError("invalid Ideogram 4 latent normalization constants")
    return mx.array(values[:128]), mx.array(values[128:])


def to_diffusers_key(key: str) -> str | None:
    if key.startswith("bn."):
        return key
    if key.startswith("encoder.quant_conv."):
        return key.replace("encoder.quant_conv.", "quant_conv.", 1)
    if key.startswith("decoder.post_quant_conv."):
        return key.replace("decoder.post_quant_conv.", "post_quant_conv.", 1)
    if key.startswith(
        (
            "encoder.conv_in.",
            "encoder.conv_out.",
            "decoder.conv_in.",
            "decoder.conv_out.",
        )
    ):
        return key
    if key.startswith("encoder.norm_out."):
        return key.replace("encoder.norm_out.", "encoder.conv_norm_out.", 1)
    if key.startswith("decoder.norm_out."):
        return key.replace("decoder.norm_out.", "decoder.conv_norm_out.", 1)

    match = re.match(r"^(encoder|decoder)\.mid\.block_(\d+)\.(.+)$", key)
    if match:
        side, block, rest = match.groups()
        return f"{side}.mid_block.resnets.{int(block) - 1}.{rest.replace('nin_shortcut', 'conv_shortcut')}"
    match = re.match(r"^(encoder|decoder)\.mid\.attn_1\.(.+)$", key)
    if match:
        side, rest = match.groups()
        rest = (
            rest.replace("norm.", "group_norm.")
            .replace("q.", "to_q.")
            .replace("k.", "to_k.")
            .replace("v.", "to_v.")
            .replace("proj_out.", "to_out.0.")
        )
        return f"{side}.mid_block.attentions.0.{rest}"
    match = re.match(r"^encoder\.down\.(\d+)\.block\.(\d+)\.(.+)$", key)
    if match:
        level, block, rest = match.groups()
        return f"encoder.down_blocks.{level}.resnets.{block}.{rest.replace('nin_shortcut', 'conv_shortcut')}"
    match = re.match(r"^encoder\.down\.(\d+)\.downsample\.conv\.(.+)$", key)
    if match:
        level, rest = match.groups()
        return f"encoder.down_blocks.{level}.downsamplers.0.conv.{rest}"
    match = re.match(r"^decoder\.up\.(\d+)\.block\.(\d+)\.(.+)$", key)
    if match:
        level, block, rest = match.groups()
        diffusers_level = 3 - int(level)
        return f"decoder.up_blocks.{diffusers_level}.resnets.{block}.{rest.replace('nin_shortcut', 'conv_shortcut')}"
    match = re.match(r"^decoder\.up\.(\d+)\.upsample\.conv\.(.+)$", key)
    if match:
        level, rest = match.groups()
        return f"decoder.up_blocks.{3 - int(level)}.upsamplers.0.conv.{rest}"
    return None


def load_vae(checkpoint: str | Path):
    from mflux.models.common.weights.mapping.weight_mapper import WeightMapper
    from mflux.models.flux2.model.flux2_vae.vae import Flux2VAE
    from mflux.models.flux2.weights.flux2_weight_mapping import Flux2WeightMapping

    source_weights = mx.load(str(checkpoint))
    raw_weights = {}
    for key, tensor in source_weights.items():
        mapped_key = to_diffusers_key(key)
        if mapped_key is None:
            continue
        if (
            ".mid_block.attentions.0." in mapped_key
            and mapped_key.endswith(".weight")
            and tensor.ndim == 4
        ):
            tensor = tensor[:, :, 0, 0]
        raw_weights[mapped_key] = tensor
    weights = WeightMapper.apply_mapping(
        raw_weights,
        Flux2WeightMapping.get_vae_mapping(),
    )
    vae = Flux2VAE()
    vae.update(weights, strict=True)
    vae.eval()
    mx.eval(vae.parameters())
    return vae


def unpatch_latents(packed: mx.array, grid_h: int, grid_w: int) -> mx.array:
    shift, scale = latent_norm()
    packed = packed * scale[None, None, :] + shift[None, None, :]
    batch = packed.shape[0]
    latents = packed.reshape(batch, grid_h, grid_w, 2, 2, 32)
    latents = latents.transpose(0, 5, 1, 3, 2, 4)
    return latents.reshape(batch, 32, grid_h * 2, grid_w * 2)


def pack_latents(latents: mx.array) -> mx.array:
    if latents.ndim != 4 or latents.shape[1] != 32:
        raise ValueError("Ideogram 4 VAE latents must have shape [B, 32, H, W]")
    batch, channels, height, width = latents.shape
    if height % 2 or width % 2:
        raise ValueError("Ideogram 4 VAE latent dimensions must be even")
    grid_h, grid_w = height // 2, width // 2
    packed = latents.reshape(batch, channels, grid_h, 2, grid_w, 2)
    packed = packed.transpose(0, 2, 4, 3, 5, 1)
    packed = packed.reshape(batch, grid_h * grid_w, 4 * channels)
    shift, scale = latent_norm()
    return (packed - shift[None, None, :]) / scale[None, None, :]


def encode_image(
    vae,
    image: Image.Image,
    *,
    width: int,
    height: int,
) -> mx.array:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    values = np.asarray(image, dtype=np.float32) / 127.5 - 1.0
    values = np.transpose(values, (2, 0, 1))[None, ...]
    return pack_latents(vae.encode(mx.array(values)))


def decode_packed(vae, packed: mx.array, grid_h: int, grid_w: int) -> mx.array:
    return vae.decode(unpatch_latents(packed, grid_h, grid_w))
