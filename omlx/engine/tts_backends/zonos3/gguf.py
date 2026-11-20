# Copyright (c) 2026 Zyphra, Inc.

"""GGUF -> MLX: metadata, dense tensors and Q4_0 / Q8_0 blocks repacked as MLX affine quantization.

Every GGUF goes through ``gguf.GGUFReader`` (``mx.load`` rejects the F64 tensors of ssl-teacher.gguf). Block layouts
are those ``tools/convert_gguf.py`` writes (32 elements per block):

- Q4_0: ``[f16 d][16 bytes]``, byte j = ``u[j] | u[j + 16] << 4`` with ``u = q + 8``; value ``(u - 8) * d``.
- Q8_0: ``[f16 d][32 x int8 q]``; value ``q * d``.

MLX affine quantization stores ``value = scale * u + bias`` with ``u`` packed little-endian into uint32 words (element
i at bit ``bits * (i % per_word)`` of word ``i // per_word``), so Q4_0 maps to ``scale = d, bias = -8 d`` and Q8_0 to
``u = q + 128, scale = d, bias = -128 d``: exact, no requantization.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import numpy as np
from gguf import GGMLQuantizationType, GGUFReader, GGUFValueType, quants

GROUP_SIZE = 32
_MISSING = object()
_DENSE = {
    GGMLQuantizationType.F32: np.float32,
    GGMLQuantizationType.F16: np.float16,
    GGMLQuantizationType.F64: np.float64,
    GGMLQuantizationType.I32: np.int32,
}


@dataclass(frozen=True)
class Weight:
    """A dense (``scales is None``) or affine-quantized (group 32) weight."""

    w: mx.array
    scales: mx.array | None = None
    biases: mx.array | None = None
    bits: int | None = None

    @property
    def quantized(self) -> bool:
        return self.scales is not None


class GGUFFile:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.reader = GGUFReader(self.path)
        self._tensors = {t.name: t for t in self.reader.tensors}
        self.arch = self.meta("general.architecture")

    # ------------------------------------------------------------------------------------------------- metadata
    def has(self, key: str) -> bool:
        return key in self.reader.fields

    def meta(self, key: str, default=_MISSING):
        f = self.reader.fields.get(key)
        if f is None:
            if default is _MISSING:
                raise KeyError(f"{self.path}: missing GGUF key {key}")
            return default
        kind = f.types[0]
        if kind == GGUFValueType.STRING:
            return bytes(f.parts[f.data[0]]).decode("utf-8")
        if kind == GGUFValueType.ARRAY:
            if len(f.types) > 1 and f.types[1] == GGUFValueType.STRING:
                return [bytes(f.parts[i]).decode("utf-8") for i in f.data]
            if not f.data:
                return np.zeros(0)
            return np.concatenate([f.parts[i] for i in f.data])
        return f.parts[f.data[0]][0].item()

    # -------------------------------------------------------------------------------------------------- tensors
    def names(self) -> list[str]:
        return list(self._tensors)

    def __contains__(self, name: str) -> bool:
        return name in self._tensors

    def _tensor(self, name: str):
        t = self._tensors.get(name)
        if t is None:
            raise KeyError(f"{self.path}: missing tensor {name}")
        return t

    def shape(self, name: str) -> tuple[int, ...]:
        """Numpy (= reference) order: GGUF ne reversed."""
        return tuple(int(v) for v in reversed(self._tensor(name).shape.tolist()))

    def array(self, name: str) -> np.ndarray:
        """A dense tensor (F32/F16/F64/I32) in numpy order."""
        t = self._tensor(name)
        dtype = _DENSE.get(t.tensor_type)
        if dtype is None:
            raise ValueError(
                f"{name}: unsupported GGUF type {t.tensor_type.name} for a dense read"
            )
        return np.asarray(t.data, dtype=dtype).reshape(self.shape(name))

    def weight(self, name: str) -> Weight:
        t = self._tensor(name)
        kind = t.tensor_type
        if kind == GGMLQuantizationType.F16:
            return Weight(
                mx.array(np.asarray(t.data, dtype=np.float16).reshape(self.shape(name)))
            )
        if kind in (GGMLQuantizationType.F32, GGMLQuantizationType.F64):
            return Weight(
                mx.array(np.asarray(t.data, dtype=np.float32).reshape(self.shape(name)))
            )
        if kind in (GGMLQuantizationType.Q4_0, GGMLQuantizationType.Q8_0):
            return _repack(np.asarray(t.data, dtype=np.uint8), self.shape(name), kind)
        raise ValueError(f"{name}: unsupported GGUF type {kind.name}")

    def tensor_type(self, name: str) -> GGMLQuantizationType:
        return self._tensor(name).tensor_type

    def weight_q8_0(self, name: str) -> Weight:
        """A dense F16/F32 matrix quantized to Q8_0 blocks (ggml ``quantize_row_q8_0``: scale = absmax / 127,
        round to nearest) and repacked like a stored Q8_0 tensor."""
        shape = self.shape(name)
        blocks = quants.quantize(
            self.array(name).astype(np.float32), GGMLQuantizationType.Q8_0
        )
        return _repack(blocks, shape, GGMLQuantizationType.Q8_0)

    def f32(self, name: str) -> mx.array:
        """A dense tensor as float32 (embedding tables, norms, 1-D tensors)."""
        return mx.array(self.array(name).astype(np.float32))


def _repack(raw: np.ndarray, shape: tuple[int, ...], kind) -> Weight:
    *lead, rows, cols = shape
    if cols % GROUP_SIZE:
        raise ValueError(
            f"quantized row length {cols} is not a multiple of {GROUP_SIZE}"
        )
    q4 = kind == GGMLQuantizationType.Q4_0
    block_bytes = 18 if q4 else 34
    blocks = raw.reshape(*lead, rows, cols // GROUP_SIZE, block_bytes)
    d = (
        np.ascontiguousarray(blocks[..., :2])
        .view(np.float16)[..., 0]
        .astype(np.float32)
    )
    if q4:
        qs = blocks[..., 2:]
        u = np.concatenate([qs & 0x0F, qs >> 4], axis=-1).astype(
            np.uint32
        )  # element order 0..15, 16..31
        bits, offset = 4, 8.0
    else:
        u = (blocks[..., 2:].view(np.int8).astype(np.int32) + 128).astype(np.uint32)
        bits, offset = 8, 128.0
    per_word = 32 // bits
    u = u.reshape(*lead, rows, cols // per_word, per_word)
    shifts = np.arange(per_word, dtype=np.uint32) * bits
    packed = np.bitwise_or.reduce(u << shifts, axis=-1).astype(np.uint32)
    return Weight(mx.array(packed), mx.array(d), mx.array(-offset * d), bits)
