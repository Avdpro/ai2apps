"""Audio feature pipeline (MLX) — mirrors musetalk/utils/audio_processor.py.

stacked encoder hidden states (B, seq, 5, 384)  -- get_whisper_chunk -->
per-frame windows (num_frames, 50, 384)  -- PositionalEncoding -->  UNet cross-attn states.

Mel extraction is now torch-free MLX (see whisper/log_mel.py) — the whole audio path
(mel + encoder + chunking + PE) runs without torch/transformers.
"""

from __future__ import annotations

import math

import mlx.core as mx


def positional_encoding(seq_len, d_model=384):
    """Sinusoidal PE matching musetalk/models/unet.py PositionalEncoding."""
    pos = mx.arange(0, seq_len, dtype=mx.float32)[:, None]
    div = mx.exp(
        mx.arange(0, d_model, 2, dtype=mx.float32) * (-math.log(10000.0) / d_model)
    )
    angles = pos * div
    # interleave: even idx = sin, odd idx = cos
    sin, cos = mx.sin(angles), mx.cos(angles)
    inter = mx.stack([sin, cos], axis=-1).reshape(seq_len, d_model)
    return inter[None]  # (1, seq, d)


def apply_pe(x):
    """Add sinusoidal PE to (B, seq, d) audio features (PE cast to x's dtype)."""
    return x + positional_encoding(x.shape[1], x.shape[2]).astype(x.dtype)


def get_whisper_chunk(
    stacked, librosa_length, fps=25, audio_fps=50, sr=16000, pad_left=2, pad_right=2
):
    """stacked: (1, seq, n_hidden, 384) -> (num_frames, (10*n_hidden), 384).

    Faithful port of AudioProcessor.get_whisper_chunk.
    """
    if fps <= 0 or audio_fps <= 0 or sr <= 0 or librosa_length < 0:
        raise ValueError("Audio length and frame rates must be valid")
    feat_len_per_frame = 2 * (pad_left + pad_right + 1)  # 10
    idx_mult = audio_fps / fps
    num_frames = math.floor((librosa_length / sr) * fps)
    actual_length = math.floor((librosa_length / sr) * audio_fps)
    if num_frames == 0:
        return mx.zeros(
            (0, feat_len_per_frame * stacked.shape[2], stacked.shape[3]),
            dtype=stacked.dtype,
        )
    wf = stacked[:, :actual_length, ...]
    pad = math.ceil(idx_mult)
    zeros_l = mx.zeros((wf.shape[0], pad * pad_left, *wf.shape[2:]), dtype=wf.dtype)
    zeros_r = mx.zeros(
        (wf.shape[0], pad * 3 * pad_right, *wf.shape[2:]), dtype=wf.dtype
    )
    wf = mx.concatenate([zeros_l, wf, zeros_r], axis=1)

    clips = []
    for fi in range(num_frames):
        ai = math.floor(fi * idx_mult)
        clip = wf[:, ai : ai + feat_len_per_frame]  # (1, 10, n_hidden, 384)
        clips.append(clip)
    prompts = mx.concatenate(clips, axis=0)  # (T, 10, n_hidden, 384)
    t, c, h, w = prompts.shape
    return prompts.reshape(t, c * h, w)  # (T, 50, 384)


def get_whisper_frame_range(stacked, librosa_length, start_frame, end_frame, *,
                            feature_offset=0, fps=24, audio_fps=50, sr=16000,
                            pad_left=2, pad_right=2):
    """Select absolute video frames from whole 30-second Whisper chunk(s).

    feature_offset is the global encoder-frame origin of stacked. Interior
    boundaries use actual adjacent audio features, not fresh zero padding.
    The last fractional video frame repeats the final complete feature, as in
    the existing full-clip renderer.
    """
    import numpy as np
    if (type(start_frame) is not int or type(end_frame) is not int
            or not 0 <= start_frame < end_frame or fps <= 0 or sr <= 0
            or feature_offset < 0):
        raise ValueError('Invalid absolute Whisper frame range')
    complete = librosa_length * fps // sr
    covered = (librosa_length * fps + sr - 1) // sr
    if complete < 1 or end_frame > covered:
        raise ValueError('Whisper frame range exceeds source audio')
    actual = librosa_length * audio_fps // sr
    frames = np.minimum(np.arange(start_frame, end_frame, dtype=np.int64), complete - 1)
    count = 2 * (pad_left + pad_right + 1)
    positions = frames[:, None] * audio_fps // fps - math.ceil(audio_fps / fps) * pad_left
    positions = positions + np.arange(count, dtype=np.int64)[None, :]
    valid = (positions >= 0) & (positions < actual)
    relative = positions - feature_offset
    if np.any(valid & ((relative < 0) | (relative >= stacked.shape[1]))):
        raise ValueError('Whisper chunk lacks required neighboring audio context')
    indices = np.clip(relative, 0, stacked.shape[1] - 1).reshape(-1)
    selected = mx.take(stacked[0], mx.array(indices), axis=0)
    selected = selected.reshape(end_frame - start_frame, count, *stacked.shape[2:])
    selected = mx.where(mx.array(valid)[..., None, None], selected, mx.zeros_like(selected))
    return selected.reshape(end_frame - start_frame, count * stacked.shape[2], stacked.shape[3])
