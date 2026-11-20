"""Offline Ex-Omni Teacher image + speech-code video pipeline."""

import math

import mlx.core as mx
import numpy as np
from PIL import Image, ImageOps

from .media import write_mp4_chunks_with_audio
from .video import embed_speech_tokens, prepare_audio_condition


def teacher_schedule(steps, shift=5.0):
    if steps < 1 or shift <= 0:
        raise ValueError("Positive steps and shift required")
    sigma = np.linspace(1, 0, steps + 1, dtype=np.float32)
    return shift * sigma / (1 + (shift - 1) * sigma)


def combine_guidance(positive, drop_audio, negative, cfg, audio_cfg):
    if cfg == 1 and audio_cfg == 1:
        return positive
    if cfg == audio_cfg:
        return negative + cfg * (positive - negative)
    if cfg == 1:
        return drop_audio + audio_cfg * (positive - drop_audio)
    if audio_cfg == 1:
        return negative + cfg * (positive - negative)
    return (
        negative + cfg * (drop_audio - negative) + audio_cfg * (positive - drop_audio)
    )


class TeacherPipeline:
    def __init__(self, model, vae, codec, text_encoder):
        self.model = model
        self.vae = vae
        self.codec = codec
        self.text_encoder = text_encoder
        self.dtype = model.patch_embedding.weight.dtype

    def generate(
        self,
        image,
        codes,
        audio_path,
        output_path,
        *,
        prompt="",
        negative_prompt="subtitles, blurred, deformed",
        size=512,
        window_frames=125,
        steps=50,
        cfg=4.0,
        audio_cfg=4.0,
        seed=42,
        cancel_check=lambda: None,
        progress=lambda current, total: None,
    ):
        if window_frames < 5 or (window_frames - 1) % 4 or size <= 0 or size % 16:
            raise ValueError(
                "Expected 4n+1 frames and image dimensions divisible by 16"
            )
        if codes.ndim == 3:
            if codes.shape[0] != 1:
                raise ValueError("Expected one speech track")
            codes = codes[0]
        if codes.ndim != 2 or codes.shape[0] < 1:
            raise ValueError("Expected nonempty speech code frames")
        cancel_check()
        positive = self.text_encoder(prompt).astype(self.dtype)
        negative = (
            self.text_encoder(negative_prompt).astype(self.dtype) if cfg != 1 else None
        )
        features = mx.repeat(
            embed_speech_tokens(codes, self.codec.codebooks), 2, axis=0
        )
        features = self.model.speech_token_adapter(features.astype(self.dtype))
        original = features.shape[0]
        # Match teacher's one fixed reference frame and one-frame overlap.
        stride = window_frames - 1
        chunks = math.ceil(original / stride)
        features = mx.pad(features, [(0, chunks * stride - original), (0, 0)])
        picture = ImageOps.fit(
            ImageOps.exif_transpose(Image.open(image)).convert("RGB"),
            (size, size),
            method=Image.Resampling.BICUBIC,
        )
        rgb = mx.array(np.asarray(picture).astype(np.float32) / 127.5 - 1)
        reference = rgb.transpose(2, 0, 1)[None, :, None].astype(self.dtype)
        reference_latent = self.vae.encode(reference)
        latent_frames = (window_frames + 3) // 4
        repeated = mx.repeat(reference_latent, latent_frames, axis=2)
        mask = mx.concatenate(
            [mx.zeros_like(repeated[:, :1, :1]), mx.ones_like(repeated[:, :1, 1:])],
            axis=2,
        )
        condition = mx.concatenate([repeated, mask], axis=1)
        schedule = teacher_schedule(steps)
        key = mx.random.key(seed)
        motion = reference_latent

        def generate_chunks():
            nonlocal key, motion
            prefix = mx.zeros_like(features[:1])
            emitted = 0
            for chunk in range(chunks):
                cancel_check()
                audio = mx.concatenate(
                    [prefix, features[chunk * stride : (chunk + 1) * stride]]
                )
                prefix = audio[-1:]
                cond = prepare_audio_condition(
                    audio[None], self.model.audio_proj, self.model.audio_cond_projs
                )
                null = prepare_audio_condition(
                    mx.zeros_like(audio)[None],
                    self.model.audio_proj,
                    self.model.audio_cond_projs,
                )
                key, rng = mx.random.split(key)
                latent = mx.random.normal(repeated.shape, key=rng).astype(self.dtype)
                for i in range(steps):
                    cancel_check()
                    latent = mx.concatenate([motion, latent[:, :, 1:]], axis=2)
                    t = mx.array([float(schedule[i] * 1000)], dtype=self.dtype)
                    pred = self.model(
                        latent, t, positive, condition, prepared_audio_condition=cond
                    )
                    no_audio = neg = None
                    if cfg != 1 or audio_cfg != 1:
                        if cfg == audio_cfg:
                            neg = self.model(
                                latent,
                                t,
                                negative,
                                condition,
                                prepared_audio_condition=null,
                            )
                        else:
                            no_audio = self.model(
                                latent,
                                t,
                                positive,
                                condition,
                                prepared_audio_condition=null,
                            )
                            if cfg != 1:
                                neg = self.model(
                                    latent,
                                    t,
                                    negative,
                                    condition,
                                    prepared_audio_condition=null,
                                )
                    flow = combine_guidance(pred, no_audio, neg, cfg, audio_cfg)
                    latent = latent + flow * mx.array(
                        float(schedule[i + 1] - schedule[i]), dtype=self.dtype
                    )
                    mx.eval(latent)
                    progress(chunk * steps + i + 1, chunks * steps)
                latent = mx.concatenate([motion, latent[:, :, 1:]], axis=2)
                video = self.vae.decode(latent)
                mx.eval(video)
                cancel_check()
                motion = self.vae.encode(video[:, :, -1:])
                mx.eval(motion)
                result = video[:, :, 0 if chunk == 0 else 1 :]
                result = result[:, :, : original + 1 - emitted]
                emitted += result.shape[2]
                yield np.array(result[0].transpose(1, 2, 3, 0).astype(mx.float32))

        return write_mp4_chunks_with_audio(
            generate_chunks(), audio_path, output_path, fps=25
        )
