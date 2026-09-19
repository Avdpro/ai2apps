"""End-to-end, Torch-free MLX Seed-VC v2 inference pipeline."""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import numpy as np
from scipy.signal import resample_poly

from .ar import SeedVCAR
from .astral import AstralQuantizer
from .audio import kaldi_fbank, mel_spectrogram
from .bigvgan import load_bigvgan
from .campplus import CAMPPlus
from .dit import SeedVCDiT
from .flow_matching import solve_euler
from .hubert import HubertLayer18
from .length_regulator import DiscreteLengthRegulator


class SeedVCV2:
    sample_rate = 22050

    def __init__(self, root: str | Path) -> None:
        root = Path(root)
        self.root = root
        self.hubert = HubertLayer18.from_directory(root / "hubert")
        self.astral_wide = AstralQuantizer(
            mx.load(str(root / "astral_wide.safetensors"))
        )
        self.style_encoder = CAMPPlus(mx.load(str(root / "campplus.safetensors")))
        self.cfm_regulator = DiscreteLengthRegulator(
            mx.load(str(root / "cfm_length_regulator.safetensors"))
        )
        self.astral_narrow: AstralQuantizer | None = None
        self.ar_regulator: DiscreteLengthRegulator | None = None
        self.ar: SeedVCAR | None = None
        self.dit = SeedVCDiT(mx.load(str(root / "cfm.safetensors")))
        self.vocoder = load_bigvgan(root / "bigvgan")

    @staticmethod
    def _resample(values: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        divisor = np.gcd(source_rate, target_rate)
        return resample_poly(
            values, target_rate // divisor, source_rate // divisor
        ).astype(np.float32)

    def _tokens(self, waveform_16k: np.ndarray, *, narrow: bool = False) -> mx.array:
        hidden = self.hubert(mx.array(waveform_16k[None]))
        if narrow:
            self._ensure_voice_path()
        extractor = self.astral_narrow if narrow else self.astral_wide
        assert extractor is not None
        tokens = extractor(hidden)[1]
        mx.eval(tokens)
        return tokens

    def _ensure_voice_path(self) -> None:
        if self.ar is not None:
            return
        self.astral_narrow = AstralQuantizer(
            mx.load(str(self.root / "astral_narrow.safetensors"))
        )
        self.ar_regulator = DiscreteLengthRegulator(
            mx.load(str(self.root / "ar_length_regulator.safetensors"))
        )
        self.ar = SeedVCAR(mx.load(str(self.root / "ar.safetensors")))

    def _style(self, waveform_16k: np.ndarray) -> mx.array:
        features = kaldi_fbank(waveform_16k)
        style = self.style_encoder(features, mx.array([features.shape[1] // 2]))
        mx.eval(style)
        return style

    @staticmethod
    def _reduce_duration(tokens: mx.array) -> mx.array:
        values = np.asarray(tokens).reshape(-1)
        keep = np.concatenate(([True], values[1:] != values[:-1]))
        return mx.array(values[keep][None].astype(np.int32))

    def convert(
        self,
        source: np.ndarray,
        target: np.ndarray,
        *,
        mode: str = "timbre",
        diffusion_steps: int = 30,
        guidance: tuple[float, float] = (0.5, 0.5),
        length_adjust: float = 1.0,
        seed: int = 0,
    ) -> np.ndarray:
        source = np.asarray(source, dtype=np.float32)
        target = np.asarray(target, dtype=np.float32)
        source_16k = self._resample(source, self.sample_rate, 16000)
        target_16k = self._resample(target, self.sample_rate, 16000)
        source_mel = mel_spectrogram(source)
        target_mel = mel_spectrogram(target)
        mx.eval(source_mel, target_mel)
        source_wide = self._tokens(source_16k)
        target_wide = self._tokens(target_16k)
        if mode == "timbre":
            output_tokens = source_wide
            output_length = source_mel.shape[-1]
        elif mode == "voice":
            self._ensure_voice_path()
            source_narrow = self._reduce_duration(self._tokens(source_16k, narrow=True))
            target_narrow = self._reduce_duration(self._tokens(target_16k, narrow=True))
            assert self.ar_regulator is not None and self.ar is not None
            condition = self.ar_regulator(
                mx.concatenate((target_narrow, source_narrow), axis=1)
            )
            output_tokens = self.ar.generate_greedy(condition, target_wide)
            output_length = max(
                1,
                int(
                    source_mel.shape[-1]
                    / source_wide.shape[-1]
                    * output_tokens.shape[-1]
                    * length_adjust
                ),
            )
        else:
            raise ValueError("mode must be 'timbre' or 'voice'")
        output_condition = self.cfm_regulator(output_tokens, output_length)
        prompt_condition = self.cfm_regulator(target_wide, target_mel.shape[-1])
        condition = mx.concatenate((prompt_condition, output_condition), axis=1)
        prompt = target_mel
        style = self._style(target_16k)
        mx.random.seed(seed)
        noise = mx.random.normal((1, 80, condition.shape[1]))
        generated = solve_euler(
            self.dit,
            noise,
            mx.array([condition.shape[1]]),
            prompt,
            condition,
            style,
            steps=diffusion_steps,
            cfg_rate=guidance,
            sway_sampling=True,
        )
        generated = generated[..., target_mel.shape[-1] :]
        waveform = self.vocoder(generated.astype(mx.float32))
        mx.eval(waveform)
        return np.asarray(waveform[0, 0])
