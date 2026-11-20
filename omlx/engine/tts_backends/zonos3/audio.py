# Copyright (c) 2026 Zyphra, Inc.

import mlx.core as mx


def polyphase_resample(
    x: mx.array, kernel: mx.array, orig: int, new: int, width: int
) -> mx.array:
    """Polyphase sinc resampling with a ``[new, 2*width + orig]`` kernel.

    Accumulate in float64 on the CPU stream to preserve the reference frontend's
    precision; float64 is unsupported on Metal. Return float32 PCM as an MLX
    array, with ``ceil(new * len(x) / orig)`` samples and zero padding at both ends.
    """
    if orig <= 0 or new <= 0 or width < 0:
        raise ValueError("resampling rates must be positive and width nonnegative")
    with mx.stream(mx.cpu):
        x = mx.array(x, dtype=mx.float64)
        kernel = mx.array(kernel, dtype=mx.float64)
        taps = 2 * width + orig
        if x.ndim != 1 or kernel.shape != (new, taps):
            raise ValueError(
                f"expected mono PCM and a resampling kernel of shape {(new, taps)}"
            )
        length = x.shape[0]
        total = -(-new * length // orig)
        if total == 0:
            return mx.zeros((0,), dtype=mx.float32)
        blocks = -(-total // new)
        pad_right = max(0, (blocks - 1) * orig + taps - (width + length))
        padded = mx.pad(x, [(width, pad_right)])
        windows = mx.as_strided(padded, shape=(blocks, taps), strides=(orig, 1))
        return (windows @ kernel.T).reshape(-1)[:total].astype(mx.float32)
