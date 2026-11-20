"""MiniMax H3's single-frame VAE for MLX."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn

from .packing import PIXEL_MEAN, PIXEL_STD
from .video_vae import CausalConv3d, Encoder3d, SpatialVAETiling, VideoVAEConfig, ViTDecoder3d


class ImageVAE(nn.Module, SpatialVAETiling):
    def __init__(self, config: VideoVAEConfig, *, load_encoder: bool):
        super().__init__()
        self.config = config
        self.post_quant_conv = nn.Conv2d(config.latent_channels, config.latent_channels, 1)
        image_decoder = replace(config, temporal_downsample_factors=(1, 1, 1, 1, 1, 1))
        self.decoder = ViTDecoder3d(image_decoder, rope_axes=2)
        if load_encoder:
            self.encoder = Encoder3d(config)
            self.quant_conv = CausalConv3d(2 * config.latent_channels, 2 * config.latent_channels, 1)

    def _spatial_tiles(
        self,
        data: mx.array,
        transform: Callable[[mx.array], mx.array],
        input_ratio: int,
        output_ratio: int,
    ) -> mx.array:
        h, w = data.shape[1:3]
        ys, heights, yo = self._split_tiles(h * input_ratio, 256, 64)
        xs, widths, xo = self._split_tiles(w * input_ratio, 256, 64)
        tiles = []
        for y, height in zip(ys, heights):
            row = []
            for x, width in zip(xs, widths):
                tile = data[
                    :, y // input_ratio:(y + height) // input_ratio,
                    x // input_ratio:(x + width) // input_ratio,
                ]
                result = transform(tile)
                mx.eval(result)
                row.append(result)
            tiles.append(row)
        return self._stitch_tiles(tiles, [o // output_ratio for o in yo], [o // output_ratio for o in xo], 1, 2)

    def decode(self, latent: mx.array, *, tiled: bool = True) -> mx.array:
        """Decode (B, C, 1, H, W) normalized latents to (B, H, W, 3) RGB in [0, 1]."""
        if latent.ndim != 5 or latent.shape[1:3] != (self.config.latent_channels, 1):
            raise ValueError("Expected a single-frame image latent.")
        z = latent[:, :, 0].transpose(0, 2, 3, 1)
        mean = mx.array(self.config.latents_mean, dtype=z.dtype)
        std = mx.array(self.config.latents_std, dtype=z.dtype)
        z = (z * std + mean).astype(self.post_quant_conv.weight.dtype)

        def decode_tile(tile: mx.array) -> mx.array:
            return self.decoder(self.post_quant_conv(tile)[:, None])[:, 0].astype(mx.float32)

        ratio = self.config.spatial_compression_ratio
        pixels = self._spatial_tiles(z, decode_tile, ratio, 1) if tiled else decode_tile(z)
        return mx.clip(pixels * mx.array(PIXEL_STD) + mx.array(PIXEL_MEAN), 0, 1)

    def encode(self, pixels: mx.array) -> mx.array:
        """Encode (B, H, W, 3) RGB in [0, 1] as an image reference latent."""
        if not hasattr(self, "encoder"):
            raise RuntimeError("Image VAE encoder weights were not loaded.")
        normalized = (pixels - mx.array(PIXEL_MEAN)) / mx.array(PIXEL_STD)

        def encode_tile(tile: mx.array) -> mx.array:
            dtype = self.encoder.conv_in.weight.dtype
            return self.quant_conv(self.encoder(tile[:, None].astype(dtype)))[:, 0]

        ratio = self.config.spatial_compression_ratio
        moments = self._spatial_tiles(normalized, encode_tile, 1, ratio).astype(mx.float32)
        mean, logvar = mx.split(moments, 2, axis=-1)
        noise = mx.random.normal(mean.shape, key=mx.random.key(42))
        z = mean + mx.exp(0.5 * mx.clip(logvar, -30, 20)) * noise
        z = (z - mx.array(self.config.latents_mean)) / mx.array(self.config.latents_std)
        return z.transpose(0, 3, 1, 2)[:, :, None]


def load_image_vae(
    vae_dir: str | Path, weights_path: str | Path | None = None, *, load_encoder: bool = False,
) -> ImageVAE:
    root = Path(vae_dir)
    raw = json.loads((root / "config.json").read_text())
    vit = raw["vit_decoder_kwargs"]
    config = VideoVAEConfig(
        latent_channels=raw["latent_channels"],
        latents_mean=tuple(raw["latents_mean"]),
        latents_std=tuple(raw["latents_std"]),
        decoder_num_layers=vit["num_layers"],
        decoder_num_attention_heads=vit["heads"],
        decoder_attention_head_dim=vit["dim_head"],
        decoder_rope_dim_ratio=vit["rope_dim_ratio"],
        decoder_rope_theta=vit["rope_theta"],
    )
    model = ImageVAE(config, load_encoder=load_encoder)
    weights = {}
    for key, tensor in mx.load(str(weights_path or root / "diffusion_pytorch_model.safetensors")).items():
        if key in ("decoder.mask_token", "latents_mean", "latents_std"):
            continue
        if not load_encoder and key.startswith(("encoder.", "quant_conv.")):
            continue
        if tensor.ndim == 5:
            tensor = mx.contiguous(tensor.transpose(0, 2, 3, 4, 1))
        elif key == "post_quant_conv.weight":
            tensor = mx.contiguous(tensor.transpose(0, 2, 3, 1))
        weights[key] = tensor
    model.load_weights(list(weights.items()), strict=True)
    mx.eval(model.parameters())
    return model
