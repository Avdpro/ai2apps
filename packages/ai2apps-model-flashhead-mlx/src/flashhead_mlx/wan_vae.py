"""FlashHead Pro adapter for the native Wan 2.1 VAE implementation."""

from pathlib import Path

import mlx.core as mx

from .wan_vae_ops import (
    vae_decoder_tensor_names,
    vae_encoder_tensor_names,
    wan_vae_decode,
    wan_vae_decoder_parameters_from_tensors,
    wan_vae_encode_mode,
    wan_vae_encoder_parameters_from_tensors,
)


class WanVAE:
    def __init__(self, path, *, dtype=mx.bfloat16):
        weights = mx.load(str(Path(path)))
        expected = set(vae_encoder_tensor_names()) | set(vae_decoder_tensor_names())
        if set(weights) != expected:
            raise ValueError(
                f"Wan VAE tensor set mismatch: missing={sorted(expected - set(weights))}, extra={sorted(set(weights) - expected)}"
            )
        weights = {k: v.astype(dtype) for k, v in weights.items()}
        self.encoder = wan_vae_encoder_parameters_from_tensors(
            {k: weights[k] for k in vae_encoder_tensor_names()}
        )
        self.decoder = wan_vae_decoder_parameters_from_tensors(
            {k: weights[k] for k in vae_decoder_tensor_names()}
        )
        mx.eval(list(weights.values()))

    def encode(self, video, *, noise=None):
        return wan_vae_encode_mode(video, self.encoder)

    def decode(self, latent):
        return wan_vae_decode(latent, self.decoder, evaluation_interval=1)
