"""Selective, PyTorch-free Safetensors loading for MLX weights."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import mlx.core as mx
import numpy as np
import numpy.typing as npt


@dataclass(frozen=True, slots=True)
class SafeTensorLocation:
    """Validated location of one tensor payload in a Safetensors file."""

    name: str
    shape: tuple[int, ...]
    dtype: str
    start: int
    end: int

    @property
    def nbytes(self) -> int:
        return self.end - self.start


_NUMPY_DTYPES: dict[str, npt.DTypeLike] = {
    "BOOL": np.bool_,
    "I8": np.int8,
    "U8": np.uint8,
    "I16": np.dtype("<i2"),
    "U16": np.dtype("<u2"),
    "F16": np.dtype("<f2"),
    "I32": np.dtype("<i4"),
    "U32": np.dtype("<u4"),
    "F32": np.dtype("<f4"),
    "I64": np.dtype("<i8"),
    "U64": np.dtype("<u8"),
    "F64": np.dtype("<f8"),
}


class SelectiveSafeTensorReader:
    """Read named tensors without materializing the rest of a checkpoint."""

    def __init__(self, path: Path, *, maximum_header_bytes: int = 64 * 1024 * 1024) -> None:
        self.path = path.expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"Safetensors checkpoint does not exist: {self.path}")
        with self.path.open("rb") as stream:
            prefix = stream.read(8)
            if len(prefix) != 8:
                raise ValueError("truncated Safetensors size prefix")
            header_size = struct.unpack("<Q", prefix)[0]
            if header_size <= 0 or header_size > maximum_header_bytes:
                raise ValueError(f"unsafe Safetensors header size: {header_size}")
            header_bytes = stream.read(header_size)
        if len(header_bytes) != header_size:
            raise ValueError("truncated Safetensors header")
        self._payload_start = 8 + header_size
        header = json.loads(header_bytes)
        self._metadata = self._parse_metadata(header)
        self._locations = self._parse_header(header)

    @staticmethod
    def _parse_metadata(header: object) -> dict[str, str]:
        if not isinstance(header, dict):
            raise ValueError("Safetensors header must contain an object")
        metadata = header.get("__metadata__", {})
        if metadata is None:
            return {}
        if not isinstance(metadata, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in metadata.items()
        ):
            raise ValueError("Safetensors metadata must contain string pairs")
        return dict(metadata)

    def _parse_header(self, header: object) -> dict[str, SafeTensorLocation]:
        if not isinstance(header, dict):
            raise ValueError("Safetensors header must contain an object")
        file_size = self.path.stat().st_size
        result: dict[str, SafeTensorLocation] = {}
        ranges: list[tuple[int, int, str]] = []
        for name, value in header.items():
            if name == "__metadata__":
                continue
            if not isinstance(name, str) or not isinstance(value, dict):
                raise ValueError("invalid Safetensors tensor descriptor")
            shape = value.get("shape")
            dtype = value.get("dtype")
            offsets = value.get("data_offsets")
            if (
                not isinstance(shape, list)
                or not all(isinstance(extent, int) and extent >= 0 for extent in shape)
                or not isinstance(dtype, str)
                or not isinstance(offsets, list)
                or len(offsets) != 2
                or not all(isinstance(offset, int) for offset in offsets)
            ):
                raise ValueError(f"invalid Safetensors descriptor for {name}")
            relative_start, relative_end = offsets
            start = self._payload_start + relative_start
            end = self._payload_start + relative_end
            if relative_start < 0 or relative_end < relative_start or end > file_size:
                raise ValueError(f"invalid Safetensors payload range for {name}")
            location = SafeTensorLocation(name, tuple(shape), dtype, start, end)
            expected = int(np.prod(shape, dtype=np.int64)) * self._itemsize(dtype)
            if location.nbytes != expected:
                raise ValueError(f"Safetensors payload size disagrees with {name} schema")
            result[name] = location
            ranges.append((start, end, name))
        if not result:
            raise ValueError("Safetensors file contains no tensors")
        for previous, current in zip(sorted(ranges), sorted(ranges)[1:], strict=False):
            if current[0] < previous[1]:
                raise ValueError(
                    f"overlapping Safetensors payloads: {previous[2]} and {current[2]}"
                )
        return result

    @staticmethod
    def _itemsize(dtype: str) -> int:
        if dtype == "BF16":
            return 2
        try:
            return np.dtype(_NUMPY_DTYPES[dtype]).itemsize
        except KeyError as error:
            raise ValueError(f"unsupported Safetensors dtype for MLX loading: {dtype}") from error

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._locations)

    @property
    def metadata(self) -> dict[str, str]:
        """Return a copy of the validated string metadata."""

        return dict(self._metadata)

    def location(self, name: str) -> SafeTensorLocation:
        try:
            return self._locations[name]
        except KeyError as error:
            raise KeyError(f"checkpoint does not contain tensor {name}") from error

    def read(self, name: str) -> mx.array:
        """Read one tensor and preserve BF16 bits without a float32 round trip."""

        location = self.location(name)
        with self.path.open("rb") as stream:
            stream.seek(location.start)
            payload = stream.read(location.nbytes)
        return self._decode(location, payload)

    @staticmethod
    def _decode(location: SafeTensorLocation, payload: bytes) -> mx.array:
        if len(payload) != location.nbytes:
            raise ValueError(f"truncated tensor payload for {location.name}")
        if location.dtype == "BF16":
            words = np.frombuffer(payload, dtype="<u2").reshape(location.shape)
            result = mx.view(mx.array(cast(Any, words)), mx.bfloat16)
        else:
            values = np.frombuffer(payload, dtype=_NUMPY_DTYPES[location.dtype]).reshape(
                location.shape
            )
            result = mx.array(cast(Any, values))
        mx.eval(result)
        return result

    def read_many(self, names: list[str] | tuple[str, ...]) -> dict[str, mx.array]:
        missing = sorted(set(names) - self.names)
        if missing:
            raise KeyError(f"checkpoint is missing requested tensors: {missing}")
        result: dict[str, mx.array] = {}
        with self.path.open("rb") as stream:
            for name in names:
                location = self.location(name)
                stream.seek(location.start)
                result[name] = self._decode(location, stream.read(location.nbytes))
        return result

    def verify_sha256(self, expected: str, *, chunk_size: int = 8 * 1024 * 1024) -> None:
        """Verify the complete local file before trusting its tensor payloads."""

        if len(expected) != 64 or any(
            character not in "0123456789abcdef" for character in expected
        ):
            raise ValueError("expected SHA-256 must be a lowercase hexadecimal digest")
        digest = hashlib.sha256()
        with self.path.open("rb") as stream:
            while chunk := stream.read(chunk_size):
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            raise ValueError(f"checkpoint SHA-256 mismatch: {actual} != {expected}")
