"""Native offline InfiniteTalk image driver with exact CFG and motion overlap."""

import math

import mlx.core as mx
import numpy as np
from PIL import Image, ImageOps

from .media import write_mp4_chunks_with_audio


def infinite_schedule(steps, shift=5.0):
    if steps < 1 or shift <= 0:
        raise ValueError("Positive steps and shift required")
    t = np.concatenate(
        [
            np.linspace(1000, 1, steps, dtype=np.float32) / 1000,
            np.zeros(1, dtype=np.float32),
        ]
    )
    return shift * t / (1 + (shift - 1) * t)


class InfiniteTalkPipeline:
    def __init__(self, model, vae, text_encoder, image_encoder):
        self.model = model
        self.vae = vae
        self.text_encoder = text_encoder
        self.image_encoder = image_encoder
        self.dtype = model.patch_embedding.weight.dtype

    def generate(
        self,
        image,
        audio_features,
        audio_path,
        output_path,
        *,
        prompt="",
        negative_prompt="subtitles, blurred, deformed",
        size=480,
        window_frames=81,
        motion_frames=25,
        steps=40,
        text_cfg=5.0,
        audio_cfg=4.0,
        seed=0,
        reference_masks=None,
        cancel_check=lambda: None,
        progress=lambda current, total: None,
    ):
        """audio_features: [speakers,frames,12,768], masks: [3,h/16*w/16] for two speakers.

        For two speakers audio_path must already contain the user's intended
        mix. Automatic person detection and audio mixing belong to preprocessing.
        """
        if (
            audio_features.ndim != 4
            or audio_features.shape[0] not in (1, 2)
            or audio_features.shape[1] < 1
        ):
            raise ValueError("Invalid Wav2Vec2 feature shape")
        if (
            size <= 0
            or size % 16
            or window_frames < 5
            or (window_frames - 1) % 4
            or motion_frames < 1
            or (motion_frames - 1) % 4
            or motion_frames >= window_frames
        ):
            raise ValueError(
                "Expected 4n+1 temporal dimensions, motion shorter than window, and spatial dimensions divisible by 16"
            )
        if audio_features.shape[0] == 2 and reference_masks is None:
            raise ValueError(
                "Two speakers require explicit target and background masks"
            )
        cancel_check()
        context = self.text_encoder(prompt).astype(self.dtype)
        negative = (
            self.text_encoder(negative_prompt).astype(self.dtype)
            if text_cfg != 1
            else None
        )
        picture = ImageOps.fit(
            ImageOps.exif_transpose(Image.open(image)).convert("RGB"),
            (size, size),
            method=Image.Resampling.BILINEAR,
        )
        rgb = mx.array(np.asarray(picture).astype(np.float32) / 127.5 - 1)
        reference = rgb.transpose(2, 0, 1)[None, :, None].astype(self.dtype)
        clip = self.image_encoder(rgb[None]).astype(self.dtype)
        latent_frames = (window_frames - 1) // 4 + 1
        padding = mx.zeros((1, 3, window_frames - 1, size, size), dtype=self.dtype)
        encoded = self.vae.encode(mx.concatenate([reference, padding], axis=2)).astype(
            self.dtype
        )
        mask = mx.concatenate(
            [
                mx.ones((1, 4, 1, size // 8, size // 8), dtype=self.dtype),
                mx.zeros(
                    (1, 4, latent_frames - 1, size // 8, size // 8), dtype=self.dtype
                ),
            ],
            axis=2,
        )
        condition = mx.concatenate([mask, encoded], axis=1)
        initial_motion = self.vae.encode(reference)
        total = audio_features.shape[1]
        stride = window_frames - motion_frames
        count = max(1, math.ceil((total - window_frames) / stride) + 1)
        schedule = infinite_schedule(steps)
        key = mx.random.key(seed)

        def chunks():
            nonlocal key
            emitted = 0
            motion = initial_motion
            features = audio_features
            for chunk in range(count):
                cancel_check()
                start = chunk * stride
                end = start + window_frames
                if chunk and end >= features.shape[1]:
                    missing = end - features.shape[1] + 3
                    features = mx.concatenate(
                        [features, mx.flip(features[:, -missing:], axis=1)], axis=1
                    )
                indices = mx.clip(
                    mx.arange(start, end)[:, None] + mx.arange(-2, 3)[None],
                    0,
                    features.shape[1] - 1,
                )
                audio = features[:, indices].astype(self.dtype)
                key, rng = mx.random.split(key)
                latent = mx.random.normal(encoded.shape, key=rng)
                null = mx.zeros_like(audio[-1:])
                for i in range(steps):
                    cancel_check()
                    latent = mx.concatenate(
                        [motion, latent[:, :, motion.shape[2] :]], axis=2
                    )
                    t = mx.array([float(schedule[i] * 1000)], dtype=mx.float32)
                    positive = self.model(
                        latent, t, context, clip, condition, audio, reference_masks
                    )
                    if text_cfg == 1:
                        dropped = self.model(latent, t, context, clip, condition, null)
                        flow = dropped + audio_cfg * (positive - dropped)
                    else:
                        dropped = self.model(
                            latent, t, negative, clip, condition, audio, reference_masks
                        )
                        uncond = self.model(latent, t, negative, clip, condition, null)
                        flow = (
                            uncond
                            + text_cfg * (positive - dropped)
                            + audio_cfg * (dropped - uncond)
                        )
                    latent = latent - flow * mx.array(
                        float(schedule[i] - schedule[i + 1]), dtype=latent.dtype
                    )
                    mx.eval(latent)
                    progress(chunk * steps + i + 1, count * steps)
                latent = mx.concatenate(
                    [motion, latent[:, :, motion.shape[2] :]], axis=2
                )
                video = self.vae.decode(latent)
                mx.eval(video)
                cancel_check()
                if chunk + 1 < count:
                    motion = self.vae.encode(video[:, :, -motion_frames:])
                    mx.eval(motion)
                result = video[:, :, 0 if chunk == 0 else motion_frames :]
                result = result[:, :, : total - emitted]
                emitted += result.shape[2]
                yield np.array(result[0].transpose(1, 2, 3, 0).astype(mx.float32))

        return write_mp4_chunks_with_audio(chunks(), audio_path, output_path, fps=25)
