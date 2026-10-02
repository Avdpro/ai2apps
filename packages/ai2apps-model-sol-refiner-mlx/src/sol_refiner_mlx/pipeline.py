"""Sequential component loading for independent MP4-to-MP4 MLX refinement."""

import gc
import json
import time
from pathlib import Path

import mlx.core as mx

from .text import VideoConnector, encode_features
from .transformer import VideoTransformer
from .upsampler import LatentUpsampler, adain
from .vae import VideoVAE


def release():
    gc.collect()
    mx.clear_cache()


class Refiner:
    def __init__(
        self, root, release_weights=True, vae_conv="conv3d", vae_chunk_frames=8
    ):
        self.vae_conv = vae_conv
        self.vae_chunk_frames = vae_chunk_frames
        self.release_weights = release_weights
        self.root = Path(root).resolve()
        index = json.loads((self.root / "model_index.json").read_text())
        if index.get("variant") != "one-step":
            raise ValueError("Only LTX-2.3 One-Step is supported")
        from .weights import config

        tc = config(self.root, "transformer")
        required = {
            "_class_name": "LTX2VideoTransformer3DModel",
            "in_channels": 128,
            "out_channels": 128,
            "num_layers": 48,
            "num_attention_heads": 32,
            "attention_head_dim": 128,
            "rope_type": "split",
            "pos_embed_max_pos": 20,
            "base_height": 2048,
            "base_width": 2048,
            "vae_scale_factors": [8, 32, 32],
            "use_prompt_embeddings": False,
            "cross_attn_mod": True,
            "gated_attn": True,
        }
        for key, expected in required.items():
            if tc.get(key) != expected:
                raise ValueError(
                    f"Unsupported transformer configuration: {key}={tc.get(key)!r}"
                )
        vc = config(self.root, "vae")
        if vc.get("_class_name") != "AutoencoderKLLTX2Video" or vc.get(
            "timestep_conditioning"
        ):
            raise ValueError("Only the LTX-2.3 convolutional VAE is supported")
        self.timings = {}

    def phase(self, name, start):
        elapsed = time.monotonic() - start
        self.timings[name] = elapsed
        print(
            f"{name}: {elapsed:.2f}s; active {mx.get_active_memory() / 2**30:.2f} GiB",
            flush=True,
        )

    def refine_latents(
        self,
        pixels,
        prompt,
        fps,
        seed=0,
        context_path=None,
        noise_path=None,
        save_context=None,
        check_cancel=None,
    ):
        check_cancel = check_cancel or (lambda: None)
        check_cancel()
        total = time.monotonic()
        start = total
        if context_path:
            context = mx.load(str(context_path))["context"]
        else:
            features, mask = encode_features(
                self.root, prompt, release_weights=self.release_weights
            )
            self.phase("text_encoder", start)
            check_cancel()
            start = time.monotonic()
            connector = VideoConnector(self.root)
            context = connector(features, mask)
            mx.eval(context)
            del connector, features, mask
            release()
            if save_context:
                mx.save_safetensors(str(save_context), {"context": context})
        self.phase("text_connector", start)
        check_cancel()
        start = time.monotonic()
        encoder = VideoVAE(self.root, "encoder")
        raw = encoder.encode(pixels.astype(mx.bfloat16))
        mean, std = encoder.stats()
        mx.eval(raw, mean, std)
        del encoder, pixels
        release()
        self.phase("vae_encode", start)
        check_cancel()
        start = time.monotonic()
        up = LatentUpsampler(self.root)
        enlarged = adain(up(raw), raw)
        mx.eval(enlarged)
        latent = ((enlarged - mean) / std).astype(mx.bfloat16)
        mx.eval(latent)
        del up, raw, enlarged
        release()
        self.phase("latent_upsample", start)
        check_cancel()
        start = time.monotonic()
        sigma = float(mx.array(0.725, mx.float32).item())
        mx.random.seed(seed)
        noise = (
            mx.load(str(noise_path))["noise"]
            if noise_path
            else mx.random.normal(latent.shape, dtype=mx.bfloat16)
        )
        if noise.shape != latent.shape:
            raise ValueError("Noise tensor shape mismatch")
        noisy = (1 - sigma) * latent + sigma * noise
        model = VideoTransformer(self.root, release_weights=self.release_weights)

        def progress(i, n):
            check_cancel()
            if i % 8 == 0:
                print(f"DiT {i}/{n}", flush=True)

        velocity = model(noisy, context, sigma, fps, progress)
        clean = noisy.astype(mx.float32) - sigma * velocity.astype(mx.float32)
        mx.eval(clean)
        del model, context, noise, noisy, latent, velocity
        release()
        self.phase("one_step_denoise", start)
        check_cancel()
        start = time.monotonic()
        # Denormalize the FP32 scheduler output before the single BF16 cast.
        raw = (clean * std.astype(mx.float32) + mean.astype(mx.float32)).astype(
            mx.bfloat16
        )
        mx.eval(raw)
        del clean
        release()
        self.timings["refine_total"] = time.monotonic() - total
        return raw

    def decode_latents(self, raw, check_cancel=None):
        check_cancel = check_cancel or (lambda: None)
        check_cancel()
        decoder = VideoVAE(self.root, "decoder", self.vae_conv, self.vae_chunk_frames)
        decoded = decoder.decode(raw)
        mx.eval(decoded)
        del decoder
        release()
        check_cancel()
        return decoded

    def __call__(self, *args, **kwargs):
        start = time.monotonic()
        raw = self.refine_latents(*args, **kwargs)
        decoded = self.decode_latents(raw, kwargs.get("check_cancel"))
        self.timings["total"] = time.monotonic() - start
        return decoded
