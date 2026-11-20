"""MuseTalk MLX pipeline — single-step latent inpainting.

Core face-level path (parity-gated): crop 256² -> VAE.encode(masked)⊕encode(ref)=8ch
-> UNet(t=0, audio cross-attn) -> VAE.decode -> recon BGR face.

Automatic detection and mouth parsing live in prepare.py; template.py owns
local blending. This module owns the neural generation.

Mirrors musetalk/models/vae.py (VAE wrapper) + scripts/inference.py inference loop.
"""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import numpy as np

from .config import RESIZED_IMG, UNET_TIMESTEP
from .models.unet import UNet2DConditionModel
from .models.vae import AutoencoderKL
from .utils.weights import (
    load_unet_weights,
    load_vae_weights,
    load_whisper_encoder_weights,
)
from .whisper.audio2feature import apply_pe, get_whisper_chunk
from .whisper.whisper_encoder import WhisperEncoder

_NORM_MEAN = 0.5
_NORM_STD = 0.5


def get_mask_tensor(size=RESIZED_IMG):
    m = np.zeros((size, size), dtype=np.float32)
    m[: size // 2, :] = 1.0  # keep upper half; lower (mouth) gets masked
    return m


def preprocess_img(img_bgr, half_mask=False, size=RESIZED_IMG):
    """BGR uint8 HxWx3 (already 256²) -> normalized NCHW float32 (1,3,256,256)."""
    rgb = np.ascontiguousarray(img_bgr[..., ::-1]).astype(np.float32) / 255.0  # HWC
    x = np.transpose(rgb, (2, 0, 1))  # CHW
    if half_mask:
        x = x * (get_mask_tensor(size) > 0.5)
    x = (x - _NORM_MEAN) / _NORM_STD
    return x[None]  # (1,3,256,256)


class MuseTalkPipeline:
    def __init__(self, vae, unet, whisper_encoder=None, scaling_factor=None):
        self.vae = vae
        self.unet = unet
        self.whisper_encoder = whisper_encoder
        self.scaling_factor = (
            scaling_factor if scaling_factor is not None else vae.scaling_factor
        )

    def astype(self, dtype):
        """Cast all three nets to dtype (e.g. mx.float16 for realtime/inference)."""
        for m in (self.vae, self.unet, self.whisper_encoder):
            if m is not None:
                m.update(_tree_cast(m.parameters(), dtype))
                mx.eval(m.parameters())
        self._dtype = dtype
        return self

    @classmethod
    def from_pretrained(cls, weights_root: str | Path):
        root = Path(weights_root)
        vae = AutoencoderKL()
        load_vae_weights(vae, root / "sd-vae-ft-mse")
        vae.eval()
        unet = UNet2DConditionModel()
        load_unet_weights(unet, root / "MuseTalk" / "musetalkV15" / "unet.pth")
        unet.eval()
        enc = WhisperEncoder()
        load_whisper_encoder_weights(enc, root / "whisper-tiny")
        enc.eval()
        return cls(vae, unet, enc)

    @classmethod
    def from_pretrained_mlx(cls, dist_dir: str | Path):
        """Load a published MLX variant (bf16 / q8 / q4) — torch-free, self-contained."""
        import json

        import mlx.nn as nn

        from .utils.weights import load_native

        dist_dir = Path(dist_dir)
        meta = json.loads((dist_dir / "config.json").read_text())
        vae = AutoencoderKL()
        load_native(vae, dist_dir / "vae.safetensors")
        vae.eval()
        unet = UNet2DConditionModel()
        q = meta.get("quantization")
        if q:  # quantized UNet: apply nn.quantize before load
            nn.quantize(unet, group_size=q["group_size"], bits=q["bits"])
        load_native(unet, dist_dir / "unet.safetensors")
        unet.eval()
        enc = WhisperEncoder()
        load_native(enc, dist_dir / "whisper_encoder.safetensors")
        enc.eval()
        pipe = cls(vae, unet, enc, scaling_factor=meta.get("scaling_factor"))
        pipe._dtype = mx.float16 if meta.get("dtype") == "float16" else mx.bfloat16
        return pipe

    # ---- VAE wrapper (mirrors musetalk/models/vae.py) ----
    def get_latents_for_unet(self, crop_bgr, deterministic=True):
        """256² BGR face -> 8-ch latent (masked⊕ref). deterministic uses the posterior mean."""
        masked = mx.array(preprocess_img(crop_bgr, half_mask=True))
        ref = mx.array(preprocess_img(crop_bgr, half_mask=False))
        mp, rp = self.vae.encode(masked), self.vae.encode(ref)
        ml = self.scaling_factor * (mp.mean if deterministic else mp.sample())
        rl = self.scaling_factor * (rp.mean if deterministic else rp.sample())
        return mx.concatenate([ml, rl], axis=1)  # (1,8,32,32) NCHW

    def decode_latents(self, latents):
        """4-ch latent -> BGR uint8 (B,256,256,3), matching VAE.decode_latents."""
        img = self.vae.decode(latents / self.scaling_factor)  # NCHW [-1..1]-ish
        img = mx.clip(img / 2 + 0.5, 0, 1)
        img = np.array(
            img.transpose(0, 2, 3, 1).astype(mx.float32)
        )  # NHWC RGB (fp32 for numpy)
        img = (img * 255).round().astype(np.uint8)
        return img[..., ::-1]  # RGB -> BGR

    # ---- generation ----
    def generate_faces(self, latent_batch, audio_chunks):
        """latent_batch: (B,8,32,32) mx; audio_chunks: (B,50,384) mx -> recon BGR uint8 (B,256,256,3)."""
        audio = apply_pe(audio_chunks)
        pred = self.unet(latent_batch, mx.array([UNET_TIMESTEP]), audio)
        mx.eval(pred)
        return self.decode_latents(pred)

    def encode_audio(self, mel, librosa_length, fps=25):
        """mel (1,80,3000) -> per-frame cross-attn chunks (num_frames,50,384)."""
        stacked = self.whisper_encoder(mel)
        return get_whisper_chunk(stacked, librosa_length, fps=fps)

    def encode_audio_from_wav(self, wav_path, fps=25):
        """Torch-free audio frontend: wav -> MLX log-mel -> whisper enc -> cross-attn chunks.

        Mirrors AudioProcessor.get_audio_feature + get_whisper_chunk with no torch/transformers.
        """
        import librosa

        from .whisper.log_mel import N_SAMPLES, log_mel_spectrogram

        wav, _ = librosa.load(str(wav_path), sr=16000)
        segs = [wav[i : i + N_SAMPLES] for i in range(0, max(len(wav), 1), N_SAMPLES)]
        feats = [self.whisper_encoder(log_mel_spectrogram(mx.array(s))) for s in segs]
        stacked = mx.concatenate(feats, axis=1)  # (1, total_seq, 5, 384)
        return get_whisper_chunk(stacked, len(wav), fps=fps)

    def encode_audio_frame_range(self, wav_path, start_frame, end_frame, *, fps=24,
                                 cancel_check=lambda: None):
        """Encode only global 30-second chunks needed by this video interval.

        Chunk origins match whole-track Whisper inference exactly, including
        neighboring features across a 30-second boundary.
        """
        import librosa
        from .whisper.log_mel import N_SAMPLES, log_mel_spectrogram
        from .whisper.audio2feature import get_whisper_frame_range

        cancel_check()
        wav, _ = librosa.load(str(wav_path), sr=16000)
        complete = len(wav) * fps // 16000
        covered = (len(wav) * fps + 15999) // 16000
        if (type(start_frame) is not int or type(end_frame) is not int
                or fps <= 0 or complete < 1
                or not 0 <= start_frame < end_frame <= covered):
            raise ValueError("Invalid audio frame interval")
        # The frontend pads every global chunk to 30 seconds (1500 features).
        left = (50 + fps - 1) // fps * 2
        first = max(0, min(start_frame, complete - 1) * 50 // fps - left)
        last = min(len(wav) * 50 // 16000 - 1,
                   min(end_frame - 1, complete - 1) * 50 // fps - left + 9)
        first_chunk, last_chunk = first // 1500, max(first, last) // 1500
        feats = []
        for index in range(first_chunk, last_chunk + 1):
            cancel_check()
            samples = wav[index * N_SAMPLES:(index + 1) * N_SAMPLES]
            feature = self.whisper_encoder(log_mel_spectrogram(mx.array(samples)))
            mx.eval(feature)
            feats.append(feature)
        cancel_check()
        return get_whisper_frame_range(mx.concatenate(feats, axis=1), len(wav),
                                       start_frame, end_frame,
                                       feature_offset=first_chunk * 1500, fps=fps)

    def run_batched(self, latent_stack, chunk_stack, batch_size=8):
        """Process N frames in batches (datagen-style). latent_stack:(N,8,32,32),
        chunk_stack:(N,50,384) -> recon BGR uint8 (N,256,256,3)."""
        n = latent_stack.shape[0]
        dtype = getattr(self, "_dtype", mx.float32)
        out = []
        for i in range(0, n, batch_size):
            lb = latent_stack[i : i + batch_size].astype(dtype)
            cb = chunk_stack[i : i + batch_size].astype(dtype)
            out.append(self.generate_faces(lb, cb))
        return np.concatenate(out, axis=0)


def _tree_cast(tree, dtype):
    if isinstance(tree, dict):
        return {k: _tree_cast(v, dtype) for k, v in tree.items()}
    if isinstance(tree, list):
        return [_tree_cast(v, dtype) for v in tree]
    return tree.astype(dtype)
