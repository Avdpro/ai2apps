"""Native MLX training primitives for RVC v2 voice adaptation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from .flow import ReverseResidualCouplingFlow
from .generator import NSFGenerator
from .mlx_layers import conv1d_nct
from .text_encoder import TextEncoder


def _state_arrays(state: Mapping[str, Any]) -> dict[str, mx.array]:
    return {
        name: value if isinstance(value, mx.array) else mx.array(value)
        for name, value in state.items()
    }


def _conv2d_nchw(
    values: mx.array,
    weight: mx.array,
    bias: mx.array | None = None,
    *,
    stride: tuple[int, int] = (1, 1),
    padding: tuple[int, int] = (0, 0),
    groups: int = 1,
) -> mx.array:
    result = mx.conv2d(
        mx.transpose(values, (0, 2, 3, 1)),
        mx.transpose(weight, (0, 2, 3, 1)),
        stride=stride,
        padding=padding,
        groups=groups,
    )
    if bias is not None:
        result += bias[None, None, None, :]
    return mx.transpose(result, (0, 3, 1, 2))


def _leaky_relu(values: mx.array) -> mx.array:
    return mx.where(values >= 0, values, values * 0.1)


class PosteriorEncoder:
    """RVC posterior encoder used only while fitting a voice."""

    def __init__(self, state: Mapping[str, Any], *, prefix: str = "enc_q") -> None:
        self.state = _state_arrays(state)
        self.prefix = prefix

    def _get(self, suffix: str) -> mx.array:
        return self.state[f"{self.prefix}.{suffix}"]

    def _wn(self, hidden: mx.array, mask: mx.array, conditioning: mx.array) -> mx.array:
        prefix = "enc"
        channels = hidden.shape[1]
        conditioned = conv1d_nct(
            conditioning,
            self._get(f"{prefix}.cond_layer.weight"),
            self._get(f"{prefix}.cond_layer.bias"),
        )
        layers = conditioned.shape[1] // (2 * channels)
        output = mx.zeros_like(hidden)
        for layer in range(layers):
            dilation = 1 << layer
            combined = conv1d_nct(
                hidden,
                self._get(f"{prefix}.in_layers.{layer}.weight"),
                self._get(f"{prefix}.in_layers.{layer}.bias"),
                padding=(5 * dilation - dilation) // 2,
                dilation=dilation,
            )
            offset = layer * 2 * channels
            combined += conditioned[:, offset : offset + 2 * channels]
            activated = mx.tanh(combined[:, :channels]) * mx.sigmoid(
                combined[:, channels:]
            )
            residual_skip = conv1d_nct(
                activated,
                self._get(f"{prefix}.res_skip_layers.{layer}.weight"),
                self._get(f"{prefix}.res_skip_layers.{layer}.bias"),
            )
            if layer < layers - 1:
                hidden = (hidden + residual_skip[:, :channels]) * mask
                output += residual_skip[:, channels:]
            else:
                output += residual_skip
        return output * mask

    def __call__(
        self,
        spectrogram: mx.array,
        conditioning: mx.array,
        noise: mx.array,
    ) -> tuple[mx.array, mx.array, mx.array, mx.array]:
        mask = mx.ones(
            (spectrogram.shape[0], 1, spectrogram.shape[-1]), spectrogram.dtype
        )
        hidden = (
            conv1d_nct(spectrogram, self._get("pre.weight"), self._get("pre.bias"))
            * mask
        )
        hidden = self._wn(hidden, mask, conditioning)
        statistics = (
            conv1d_nct(hidden, self._get("proj.weight"), self._get("proj.bias")) * mask
        )
        midpoint = statistics.shape[1] // 2
        mean, log_scale = statistics[:, :midpoint], statistics[:, midpoint:]
        latent = (mean + noise * mx.exp(log_scale)) * mask
        return latent, mean, log_scale, mask


class RVCTrainingGenerator(nn.Module):
    """Trainable RVC generator whose parameters retain legacy checkpoint names."""

    def __init__(self, state: Mapping[str, Any]) -> None:
        super().__init__()
        arrays = _state_arrays(state)
        self.encoder_weights = {
            name: value for name, value in arrays.items() if name.startswith("enc_p.")
        }
        self.flow_weights = {
            name: value for name, value in arrays.items() if name.startswith("flow.")
        }
        self.posterior_weights = {
            name: value for name, value in arrays.items() if name.startswith("enc_q.")
        }
        self.decoder_weights = {
            name: value for name, value in arrays.items() if name.startswith("dec.")
        }
        self.speaker_weights = {
            name: value for name, value in arrays.items() if name.startswith("emb_g.")
        }

    @property
    def weights(self) -> dict[str, mx.array]:
        return {
            **self.encoder_weights,
            **self.flow_weights,
            **self.posterior_weights,
            **self.decoder_weights,
            **self.speaker_weights,
        }

    def freeze_content_path(self) -> None:
        """Keep linguistic encoding and invertible flow stable during adaptation."""

        self.freeze(keys=["encoder_weights", "flow_weights"])

    def __call__(
        self,
        phone: mx.array,
        pitch: mx.array,
        continuous_f0: mx.array,
        spectrogram: mx.array,
        posterior_noise: mx.array,
        *,
        speaker_id: int = 0,
    ) -> tuple[mx.array, dict[str, mx.array]]:
        state = self.weights
        conditioning = mx.broadcast_to(
            state["emb_g.weight"][speaker_id][None, :, None],
            (phone.shape[0], state["emb_g.weight"].shape[1], 1),
        )
        lengths = mx.full((phone.shape[0],), phone.shape[1], dtype=mx.int32)
        prior_mean, prior_log_scale, prior_mask = TextEncoder(state)(
            phone, pitch, lengths
        )
        latent, posterior_mean, posterior_log_scale, posterior_mask = PosteriorEncoder(
            state
        )(spectrogram, conditioning, posterior_noise)
        frames = min(
            latent.shape[-1],
            prior_mean.shape[-1],
            continuous_f0.shape[-1],
        )
        latent = latent[:, :, :frames]
        posterior_mean = posterior_mean[:, :, :frames]
        posterior_log_scale = posterior_log_scale[:, :, :frames]
        posterior_mask = posterior_mask[:, :, :frames]
        prior_mean = prior_mean[:, :, :frames]
        prior_log_scale = prior_log_scale[:, :, :frames]
        prior_mask = prior_mask[:, :, :frames]
        prior_latent = ReverseResidualCouplingFlow(state).forward(
            latent, posterior_mask, conditioning
        )
        waveform = NSFGenerator(
            state,
            sample_rate=48_000,
            upsample_rates=(12, 10, 2, 2),
            upsample_kernel_sizes=(24, 20, 4, 4),
        )(latent * posterior_mask, continuous_f0[:, :frames], conditioning)
        return waveform, {
            "latent": latent,
            "prior_latent": prior_latent,
            "prior_mean": prior_mean,
            "prior_log_scale": prior_log_scale,
            "posterior_mean": posterior_mean,
            "posterior_log_scale": posterior_log_scale,
            "mask": posterior_mask * prior_mask,
        }


class RVCMultiPeriodDiscriminator(nn.Module):
    """RVC v2 scale plus eight-period discriminator in MLX."""

    periods = (2, 3, 5, 7, 11, 17, 23, 37)

    def __init__(self, state: Mapping[str, Any]) -> None:
        super().__init__()
        self.weights = _state_arrays(state)

    def _get(self, branch: int, suffix: str) -> mx.array:
        return self.weights[f"discriminators.{branch}.{suffix}"]

    def _scale(self, waveform: mx.array) -> tuple[mx.array, list[mx.array]]:
        values = waveform
        features = []
        channels = (16, 64, 256, 1024, 1024, 1024)
        groups = (1, 4, 16, 64, 256, 1)
        strides = (1, 4, 4, 4, 4, 1)
        kernels = (15, 41, 41, 41, 41, 5)
        for layer, (out_channels, group, stride, kernel) in enumerate(
            zip(channels, groups, strides, kernels)
        ):
            del out_channels
            values = _leaky_relu(
                conv1d_nct(
                    values,
                    self._get(0, f"convs.{layer}.weight"),
                    self._get(0, f"convs.{layer}.bias"),
                    stride=stride,
                    padding=(kernel - 1) // 2,
                    groups=group,
                )
            )
            features.append(values)
        values = conv1d_nct(
            values,
            self._get(0, "conv_post.weight"),
            self._get(0, "conv_post.bias"),
            padding=1,
        )
        features.append(values)
        return values.reshape((values.shape[0], -1)), features

    def _period(
        self, waveform: mx.array, branch: int, period: int
    ) -> tuple[mx.array, list[mx.array]]:
        length = waveform.shape[-1]
        remainder = length % period
        if remainder:
            padding = period - remainder
            reflected = waveform[:, :, -2 : -2 - padding : -1]
            waveform = mx.concatenate((waveform, reflected), axis=-1)
            length += padding
        values = waveform.reshape(
            (waveform.shape[0], waveform.shape[1], length // period, period)
        )
        features = []
        for layer in range(5):
            stride = (3, 1) if layer < 4 else (1, 1)
            values = _leaky_relu(
                _conv2d_nchw(
                    values,
                    self._get(branch, f"convs.{layer}.weight"),
                    self._get(branch, f"convs.{layer}.bias"),
                    stride=stride,
                    padding=(2, 0),
                )
            )
            features.append(values)
        values = _conv2d_nchw(
            values,
            self._get(branch, "conv_post.weight"),
            self._get(branch, "conv_post.bias"),
            padding=(1, 0),
        )
        features.append(values)
        return values.reshape((values.shape[0], -1)), features

    def __call__(
        self, waveform: mx.array
    ) -> tuple[list[mx.array], list[list[mx.array]]]:
        outputs = []
        features = []
        score, fmap = self._scale(waveform)
        outputs.append(score)
        features.append(fmap)
        for branch, period in enumerate(self.periods, 1):
            score, fmap = self._period(waveform, branch, period)
            outputs.append(score)
            features.append(fmap)
        return outputs, features


def kl_loss(statistics: Mapping[str, mx.array]) -> mx.array:
    z_p = statistics["prior_latent"].astype(mx.float32)
    logs_q = statistics["posterior_log_scale"].astype(mx.float32)
    m_p = statistics["prior_mean"].astype(mx.float32)
    logs_p = statistics["prior_log_scale"].astype(mx.float32)
    mask = statistics["mask"].astype(mx.float32)
    value = logs_p - logs_q - 0.5
    value += 0.5 * mx.square(z_p - m_p) * mx.exp(-2.0 * logs_p)
    return mx.sum(value * mask) / mx.maximum(mx.sum(mask), 1.0)


def multi_resolution_spectral_loss(
    target: mx.array,
    generated: mx.array,
    *,
    resolutions: Sequence[tuple[int, int]] = ((2048, 480), (1024, 240), (512, 120)),
) -> mx.array:
    """Phase-tolerant, differentiable waveform reconstruction loss."""

    target = target.reshape((target.shape[0], -1)).astype(mx.float32)
    generated = generated.reshape((generated.shape[0], -1)).astype(mx.float32)
    length = min(target.shape[-1], generated.shape[-1])
    target, generated = target[:, :length], generated[:, :length]
    total = mx.array(0.0, dtype=mx.float32)
    for fft_size, hop in resolutions:
        if length < fft_size:
            continue
        window = mx.array(np.hanning(fft_size).astype(np.float32))
        starts = range(0, length - fft_size + 1, hop)
        target_frames = mx.stack(
            [target[:, start : start + fft_size] * window for start in starts], axis=1
        )
        generated_frames = mx.stack(
            [generated[:, start : start + fft_size] * window for start in starts],
            axis=1,
        )
        target_magnitude = mx.abs(mx.fft.rfft(target_frames, axis=-1))
        generated_magnitude = mx.abs(mx.fft.rfft(generated_frames, axis=-1))
        linear = mx.mean(mx.abs(target_magnitude - generated_magnitude))
        log = mx.mean(
            mx.abs(mx.log(target_magnitude + 1e-5) - mx.log(generated_magnitude + 1e-5))
        )
        total += linear + log
    return total / len(resolutions)


def _hz_to_mel(frequencies: np.ndarray) -> np.ndarray:
    """Librosa-compatible Slaney Hz-to-mel conversion."""

    frequencies = np.asarray(frequencies, dtype=np.float64)
    mel = frequencies / (200.0 / 3.0)
    logarithmic = frequencies >= 1_000.0
    mel[logarithmic] = 15.0 + np.log(frequencies[logarithmic] / 1_000.0) / (
        np.log(6.4) / 27.0
    )
    return mel


def _mel_to_hz(mels: np.ndarray) -> np.ndarray:
    """Librosa-compatible Slaney mel-to-Hz conversion."""

    mels = np.asarray(mels, dtype=np.float64)
    frequencies = (200.0 / 3.0) * mels
    logarithmic = mels >= 15.0
    frequencies[logarithmic] = 1_000.0 * np.exp(
        (np.log(6.4) / 27.0) * (mels[logarithmic] - 15.0)
    )
    return frequencies


def mel_filterbank(
    *,
    sample_rate: int = 48_000,
    n_fft: int = 2_048,
    n_mels: int = 128,
    fmin: float = 0.0,
    fmax: float | None = None,
) -> mx.array:
    """Return the Slaney-normalized mel bank used by the pinned RVC trainer."""

    upper = sample_rate / 2.0 if fmax is None else float(fmax)
    fft_frequencies = np.linspace(0.0, sample_rate / 2.0, 1 + n_fft // 2)
    mel_frequencies = _mel_to_hz(
        np.linspace(
            _hz_to_mel(np.array([fmin]))[0],
            _hz_to_mel(np.array([upper]))[0],
            n_mels + 2,
        )
    )
    ramps = mel_frequencies[:, None] - fft_frequencies[None, :]
    differences = np.diff(mel_frequencies)
    weights = np.zeros((n_mels, 1 + n_fft // 2), dtype=np.float64)
    for index in range(n_mels):
        lower = -ramps[index] / differences[index]
        upper_slope = ramps[index + 2] / differences[index + 1]
        weights[index] = np.maximum(0.0, np.minimum(lower, upper_slope))
    weights *= (2.0 / (mel_frequencies[2 : n_mels + 2] - mel_frequencies[:n_mels]))[
        :, None
    ]
    return mx.array(weights.astype(np.float32))


def _waveform_spectrogram(
    waveform: mx.array, *, n_fft: int = 2_048, hop: int = 480
) -> mx.array:
    values = waveform.reshape((waveform.shape[0], -1)).astype(mx.float32)
    padding = (n_fft - hop) // 2
    padded = mx.concatenate(
        (values[:, 1 : padding + 1][:, ::-1], values, values[:, -padding - 1 : -1][:, ::-1]),
        axis=-1,
    )
    window = mx.array(np.hanning(n_fft + 1)[:-1].astype(np.float32))
    frames = mx.stack(
        [
            padded[:, start : start + n_fft] * window
            for start in range(0, padded.shape[-1] - n_fft + 1, hop)
        ],
        axis=1,
    )
    magnitude = mx.sqrt(mx.square(mx.abs(mx.fft.rfft(frames, axis=-1))) + 2e-7)
    return mx.transpose(magnitude, (0, 2, 1))


def log_mel_l1_loss(
    target_spectrogram: mx.array,
    generated_waveform: mx.array,
    *,
    sample_rate: int = 48_000,
    n_fft: int = 2_048,
    hop: int = 480,
    n_mels: int = 128,
) -> mx.array:
    """RVC's log-mel L1 reconstruction objective, evaluated in float32."""

    target = target_spectrogram.astype(mx.float32)
    if target.ndim == 2:
        target = target[None]
    generated = _waveform_spectrogram(generated_waveform, n_fft=n_fft, hop=hop)
    basis = mel_filterbank(
        sample_rate=sample_rate, n_fft=n_fft, n_mels=n_mels
    )
    target_mel = mx.log(mx.maximum(mx.matmul(basis, target), 2e-6))
    generated_mel = mx.log(mx.maximum(mx.matmul(basis, generated), 2e-6))
    frames = min(target_mel.shape[-1], generated_mel.shape[-1])
    return mx.mean(mx.abs(target_mel[:, :, :frames] - generated_mel[:, :, :frames]))


def generator_reconstruction_loss(
    model: RVCTrainingGenerator,
    phone: mx.array,
    pitch: mx.array,
    continuous_f0: mx.array,
    spectrogram: mx.array,
    posterior_noise: mx.array,
    target_waveform: mx.array,
    *,
    kl_weight: float = 1.0,
) -> tuple[mx.array, dict[str, mx.array]]:
    generated, statistics = model(
        phone, pitch, continuous_f0, spectrogram, posterior_noise
    )
    mel = log_mel_l1_loss(spectrogram, generated)
    kl = kl_loss(statistics)
    return mel + kl * kl_weight, {"mel": mel, "kl": kl}


def discriminator_loss(
    real_outputs: Sequence[mx.array], generated_outputs: Sequence[mx.array]
) -> mx.array:
    return sum(
        (
            mx.mean(mx.square(1.0 - real.astype(mx.float32)))
            + mx.mean(mx.square(fake.astype(mx.float32)))
        )
        for real, fake in zip(real_outputs, generated_outputs)
    )


def adversarial_generator_loss(generated_outputs: Sequence[mx.array]) -> mx.array:
    return sum(
        mx.mean(mx.square(1.0 - value.astype(mx.float32)))
        for value in generated_outputs
    )


def feature_matching_loss(
    real_features: Sequence[Sequence[mx.array]],
    generated_features: Sequence[Sequence[mx.array]],
) -> mx.array:
    return 2.0 * sum(
        mx.mean(
            mx.abs(mx.stop_gradient(real).astype(mx.float32) - fake.astype(mx.float32))
        )
        for real_branch, fake_branch in zip(real_features, generated_features)
        for real, fake in zip(real_branch, fake_branch)
    )


def discriminator_training_loss(
    model: RVCMultiPeriodDiscriminator,
    real_waveform: mx.array,
    generated_waveform: mx.array,
) -> mx.array:
    real_outputs, _ = model(real_waveform)
    generated_outputs, _ = model(mx.stop_gradient(generated_waveform))
    return discriminator_loss(real_outputs, generated_outputs)


def generator_adversarial_training_loss(
    model: RVCTrainingGenerator,
    discriminator: RVCMultiPeriodDiscriminator,
    phone: mx.array,
    pitch: mx.array,
    continuous_f0: mx.array,
    spectrogram: mx.array,
    posterior_noise: mx.array,
    target_waveform: mx.array,
    *,
    kl_weight: float = 1.0,
    mel_weight: float = 45.0,
) -> tuple[mx.array, dict[str, mx.array]]:
    generated, statistics = model(
        phone, pitch, continuous_f0, spectrogram, posterior_noise
    )
    real_outputs, real_features = discriminator(target_waveform)
    generated_outputs, generated_features = discriminator(generated)
    mel = log_mel_l1_loss(spectrogram, generated)
    kl = kl_loss(statistics)
    adversarial = adversarial_generator_loss(generated_outputs)
    feature_matching = feature_matching_loss(real_features, generated_features)
    total = mel * mel_weight + kl * kl_weight + adversarial + feature_matching
    return total, {
        "mel": mel,
        "kl": kl,
        "adversarial": adversarial,
        "feature_matching": feature_matching,
    }
