"""Offline FlashHead Lite/Pro inference from pinned local weights, without Torch."""

import json
import math
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from mlx.utils import tree_map
from PIL import Image, ImageOps

from .audio_encoder import (
    wav2vec2_encode,
    wav2vec2_parameters_from_tensors,
    wav2vec2_tensor_names,
    wav2vec2_window_hidden_states,
)
from .ltx_vae import LtxVAE
from .media import write_mp4_chunks_with_audio
from .model import WanModelAudioProject, convert_weights


def sampling_timesteps(steps=4, shift=5.0):
    if not isinstance(steps, int) or steps < 1 or shift <= 0:
        raise ValueError("Positive sampling steps and shift required")
    t = (
        np.array(
            [1000, 500]
            if steps == 2
            else [1000, 750, 500, 250]
            if steps == 4
            else np.linspace(1000, 1, steps),
            dtype=np.float32,
        )
        / 1000
    )
    return np.concatenate(
        [shift * t / (1 + (shift - 1) * t), np.zeros(1, dtype=np.float32)]
    )


def color_match(video, reference, strength):
    if not 0 <= strength <= 1:
        raise ValueError("Invalid color correction strength")
    if strength == 0:
        return video

    def lab(rgb):
        linear = mx.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
        matrix = mx.array(
            [
                [0.4124564, 0.3575761, 0.1804375],
                [0.2126729, 0.7151522, 0.0721750],
                [0.0193339, 0.1191920, 0.9503041],
            ],
            dtype=rgb.dtype,
        )
        xyz = mx.clip(
            (linear @ matrix.T) / mx.array([0.95047, 1, 1.08883], dtype=rgb.dtype),
            1e-8,
            1,
        )
        f = mx.where(xyz > 0.008856, xyz ** (1 / 3), (903.3 * xyz + 16) / 116)
        return mx.stack(
            [
                116 * f[..., 1] - 16,
                500 * (f[..., 0] - f[..., 1]),
                200 * (f[..., 1] - f[..., 2]),
            ],
            axis=-1,
        )

    rgb = (video.transpose(0, 2, 3, 4, 1) + 1) / 2
    ref = (reference.transpose(0, 2, 3, 4, 1) + 1) / 2
    src, ref = lab(rgb), lab(ref)
    mean = mx.mean(src, axis=(2, 3), keepdims=True)
    std = mx.sqrt(mx.var(src, axis=(2, 3), keepdims=True))
    out = (src - mean) * (
        mx.sqrt(mx.var(ref, axis=(2, 3), keepdims=True)) / mx.where(std < 1e-8, 1, std)
    ) + mx.mean(ref, axis=(2, 3), keepdims=True)
    lightness, a, b = out[..., 0], out[..., 1], out[..., 2]
    fy = (lightness + 16) / 116
    fx = a / 500 + fy
    fz = fy - b / 200
    x = mx.where(fx**3 > 0.008856, fx**3, (116 * fx - 16) / 903.3)
    y = mx.where(lightness > 903.3 * 0.008856, fy**3, lightness / 903.3)
    z = mx.where(fz**3 > 0.008856, fz**3, (116 * fz - 16) / 903.3)
    xyz = mx.stack([x, y, z], axis=-1) * mx.array(
        [0.95047, 1, 1.08883], dtype=video.dtype
    )
    mat = mx.array(
        [
            [3.2404542, -1.5371385, -0.4985314],
            [-0.969266, 1.8760108, 0.041556],
            [0.0556434, -0.2040259, 1.0572252],
        ],
        dtype=video.dtype,
    )
    lin = xyz @ mat.T
    corrected = mx.clip(
        mx.where(
            lin > 0.0031308,
            1.055 * mx.maximum(lin, 0) ** (1 / 2.4) - 0.055,
            12.92 * lin,
        ),
        0,
        1,
    )
    return ((rgb * (1 - strength) + corrected * strength) * 2 - 1).transpose(
        0, 4, 1, 2, 3
    )


class FlashHeadPipeline:
    def __init__(
        self, checkpoint_dir, wav2vec_dir, *, dtype=mx.bfloat16, variant="lite"
    ):
        if variant not in {"lite", "pro"}:
            raise ValueError("Expected lite or pro variant")
        self.variant = variant
        root = Path(checkpoint_dir)
        model_root = root / ("Model_Lite" if variant == "lite" else "Model_Pro")
        config = json.loads((model_root / "config.json").read_text())
        self.model = WanModelAudioProject(**config)
        raw = mx.load(str(model_root / "diffusion_pytorch_model.safetensors"))
        self.model.load_weights(list(convert_weights(raw).items()), strict=True)
        self.model.update(tree_map(lambda x: x.astype(dtype), self.model.parameters()))
        self.model.eval()
        mx.eval(self.model.parameters())
        del raw
        self.latent_channels = config["out_dim"]
        self.stride = tuple(config["vae_stride"])
        self.motion_frames = self.stride[0] + 1
        self.chunk_stride = 33 - self.motion_frames
        if variant == "lite":
            self.vae = LtxVAE.from_pretrained(root / "VAE_LTX", dtype=dtype)
        else:
            from .wan_vae import WanVAE

            self.vae = WanVAE(root / "VAE_Wan/Wan2.1_VAE.safetensors", dtype=dtype)
        wavroot = Path(wav2vec_dir)
        wconfig = json.loads((wavroot / "config.json").read_text())
        if (
            wconfig.get("hidden_size"),
            wconfig.get("num_hidden_layers"),
            wconfig.get("feat_extract_norm"),
        ) != (768, 12, "group"):
            raise ValueError(
                "Expected wav2vec2-base-960h with group-normalized feature extraction"
            )
        weights = mx.load(str(wavroot / "model.safetensors"))
        # New HF exports use parametrization names for the weight-normalized position convolution.
        prefix = "wav2vec2.encoder.pos_conv_embed.conv."
        for old, new in [
            ("parametrizations.weight.original0", "weight_g"),
            ("parametrizations.weight.original1", "weight_v"),
        ]:
            if prefix + old in weights:
                weights[prefix + new] = weights.pop(prefix + old)
        self.audio_parameters = wav2vec2_parameters_from_tensors(
            {name: weights[name] for name in wav2vec2_tensor_names()}
        )
        self.dtype = dtype
        self._key = mx.random.key(0)

    def _normal(self, shape):
        self._key, key = mx.random.split(self._key)
        return mx.random.normal(shape, key=key).astype(self.dtype)

    def prepare(self, image, *, size=512, seed=0):
        if size <= 0 or size % 32:
            raise ValueError("Image size must be a positive multiple of 32")
        self._key = mx.random.key(seed)
        image = ImageOps.exif_transpose(Image.open(image)).convert("RGB")
        scale = max(size / image.width, size / image.height)
        image = image.resize(
            (math.ceil(image.width * scale), math.ceil(image.height * scale)),
            Image.Resampling.BILINEAR,
        )
        left = int(round((image.width - size) / 2))
        top = int(round((image.height - size) / 2))
        rgb = (
            np.asarray(image.crop((left, top, left + size, top + size))).astype(
                np.float32
            )
            / 127.5
            - 1
        )
        self.reference = (
            mx.array(rgb).transpose(2, 0, 1)[None, :, None].astype(self.dtype)
        )
        reference_video = mx.repeat(self.reference, 33, axis=2)
        self.reference_latent = self.vae.encode(
            reference_video,
            noise=self._normal(
                (
                    1,
                    self.latent_channels,
                    32 // self.stride[0] + 1,
                    size // self.stride[1],
                    size // self.stride[2],
                )
            ),
        )
        self.motion = self.reference_latent[:, :, :1]
        mx.eval(self.reference_latent)

    def generate_chunk(
        self,
        audio,
        *,
        steps=4,
        shift=5,
        color_strength=1.0,
        cancel_check=lambda: None,
        progress=lambda step, total: None,
    ):
        schedule = sampling_timesteps(steps, shift)
        noise = self._normal(self.reference_latent.shape)
        for index in range(steps):
            cancel_check()
            noise = mx.concatenate(
                [self.motion, noise[:, :, self.motion.shape[2] :]], axis=2
            )
            flow = self.model(
                noise,
                mx.array([float(schedule[index] * 1000)], dtype=mx.float32),
                audio,
                self.reference_latent,
            )
            t = mx.array(float(schedule[index]), dtype=self.dtype)
            next_t = mx.array(float(schedule[index + 1]), dtype=self.dtype)
            noise = (1 - next_t) * (noise - flow * t) + next_t * self._normal(
                noise.shape
            )
            mx.eval(noise)
            progress(index + 1, steps)
        noise = mx.concatenate(
            [self.motion, noise[:, :, self.motion.shape[2] :]], axis=2
        )
        video = self.vae.decode(noise)
        video = color_match(video, self.reference, color_strength)
        mx.eval(video)
        cancel_check()
        self.motion = self.vae.encode(
            video[:, :, -self.motion_frames :],
            noise=self._normal((1, self.latent_channels, 2, *noise.shape[-2:])),
        )
        mx.eval(self.motion)
        return video

    def generate(
        self,
        image,
        audio_path,
        output_path,
        *,
        size=512,
        seed=0,
        steps=4,
        cancel_check=lambda: None,
        progress=lambda current, total: None,
    ):
        cancel_check()
        wav, rate = sf.read(audio_path, dtype="float32", always_2d=True)
        if rate != 16000:
            raise ValueError("Prepare mono 16 kHz WAV before invoking FlashHead")
        if not np.isfinite(wav).all():
            raise ValueError("Audio contains non-finite samples")
        wav = wav.mean(axis=1)
        total_frames = (len(wav) + 639) // 640
        if total_frames < 1:
            raise ValueError("Audio is too short")
        count = max(1, math.ceil((total_frames - 33) / self.chunk_stride) + 1)
        needed = 33 + (count - 1) * self.chunk_stride
        wav = np.pad(wav, (0, max(0, needed * 640 - len(wav))))
        wav = (wav - wav.mean()) / np.sqrt(wav.var() + 1e-7)
        hidden = wav2vec2_encode(
            mx.array(wav)[None], self.audio_parameters, output_length=needed
        )
        windows = wav2vec2_window_hidden_states(hidden).astype(self.dtype)
        mx.eval(windows)
        cancel_check()
        self.prepare(image, size=size, seed=seed)
        cancel_check()

        def chunks():
            emitted = 0
            for index in range(count):
                result = self.generate_chunk(
                    windows[
                        :, index * self.chunk_stride : index * self.chunk_stride + 33
                    ],
                    steps=steps,
                    cancel_check=cancel_check,
                    progress=lambda step, total, index=index: progress(
                        index * total + step, count * total
                    ),
                )
                result = result[:, :, 0 if index == 0 else self.motion_frames :]
                result = result[:, :, : total_frames - emitted]
                emitted += result.shape[2]
                yield np.array(result[0].transpose(1, 2, 3, 0).astype(mx.float32))

        return write_mp4_chunks_with_audio(
            chunks(), audio_path, output_path, fps=25, cancel_check=cancel_check
        )
