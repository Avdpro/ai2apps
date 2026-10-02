"""FP32 operator intermediates with one rounding to the input dtype."""

import math

import mlx.core as mx


def silu(x):
    y = x.astype(mx.float32)
    return (y * mx.sigmoid(y)).astype(x.dtype)


def gelu_approx(x):
    y = x.astype(mx.float32)
    return (
        0.5 * y * (1 + mx.tanh(math.sqrt(2 / math.pi) * (y + 0.044715 * y * y * y)))
    ).astype(x.dtype)
