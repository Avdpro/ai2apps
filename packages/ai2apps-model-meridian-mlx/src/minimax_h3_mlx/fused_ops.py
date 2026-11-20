"""AI2Apps package adaptation: use Runtime-owned MLX primitives only.

Modified 2026-10-09: optional inline Metal compilation removed from this Model
Package. Native execution belongs to the signed Runtime, not model payloads.
"""
import mlx.core as mx


def metal_fusions_available():
    return False


def rms_adaln(x, weight, shift, scale, indices, eps):
    normalized = mx.fast.rms_norm(x, weight, eps)
    return normalized * (1.0 + scale[indices]) + shift[indices]


def residual_rms_adaln(x, branch, gate, weight, shift, scale, indices, eps):
    residual = x + gate[indices] * branch
    normalized = mx.fast.rms_norm(residual, weight, eps)
    return residual, normalized * (1.0 + scale[indices]) + shift[indices]
