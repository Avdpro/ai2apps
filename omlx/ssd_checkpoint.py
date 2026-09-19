"""Validated access to tensors externalized in SSD-ready checkpoints.

The signed checkpoint distribution remains the authority for payload hashes.
This module enforces the on-disk layout, metadata digests, file boundaries,
and model-family identity before a Runtime loader consumes the snapshot.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

SSD_CHECKPOINT_SCHEMA = "ai2apps.ssd-checkpoint/v1"
SSD_CHECKPOINT_LAYOUTS = {
    "deepseek_v4": frozenset({"deepseek-v4-expert-major-v1"}),
    "deepseek_v41": frozenset({"dsv41-original-fp4-six-segment-v1"}),
    "glm5_next": frozenset({"glm5-next-affine-q4-gate-up-fused-v2"}),
    "qwen3_6": frozenset(
        {
            "qwen3.6-affine-q4-gate-up-fused-v2",
            "qwen3.6-affine-q4-gate-up-fused-direct-v3",
        }
    ),
    "qwen4_exp": frozenset({"qwen4-exp-affine-q4-gate-up-fused-v1"}),
}
_BYTES = {
    "U8": 1,
    "I8": 1,
    "U16": 2,
    "I16": 2,
    "U32": 4,
    "I32": 4,
    "U64": 8,
    "I64": 8,
    "BF16": 2,
    "F16": 2,
    "F32": 4,
    "F64": 8,
    "F8_E8M0": 1,
    "F8_E4M3": 1,
}
_SHA256 = re.compile(r"[0-9a-f]{64}")
_OPTIONAL_REPOSITORY_METADATA = frozenset({".gitattributes"})


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _safe_path(root: Path, authorized_root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("unsafe SSD checkpoint path")
    candidate = (root / relative).resolve()
    candidate.relative_to(root)
    candidate.relative_to(authorized_root)
    return candidate


def inspect_ssd_checkpoint(
    checkpoint: str | Path,
    *,
    authorized_root: str | Path | None = None,
    expected_family: str | None = None,
    expected_layout: str | None = None,
) -> dict[str, Any]:
    """Validate a complete SSD snapshot without hashing its large payloads."""

    root = Path(checkpoint).resolve()
    boundary = Path(authorized_root).resolve() if authorized_root else root
    root.relative_to(boundary)
    manifest = _json_object(root / "ssd-checkpoint.json", "SSD checkpoint manifest")
    family = manifest.get("family")
    layout = manifest.get("layout")
    if (
        manifest.get("schema") != SSD_CHECKPOINT_SCHEMA
        or family not in SSD_CHECKPOINT_LAYOUTS
        or layout not in SSD_CHECKPOINT_LAYOUTS[family]
    ):
        raise ValueError("unsupported SSD checkpoint layout")
    if expected_family is not None and family != expected_family:
        raise ValueError("SSD checkpoint family differs from the model recipe")
    if expected_layout is not None and layout != expected_layout:
        raise ValueError("SSD checkpoint layout differs from the model recipe")
    if manifest.get("verification") != "all_tensor_payloads_equal":
        raise ValueError("unverified SSD checkpoint")

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("SSD checkpoint file manifest is empty")
    required = {
        "config.json",
        "external-tensors.json",
        "model.safetensors.index.json",
    }
    if not required.issubset(files):
        raise ValueError("SSD checkpoint metadata files are incomplete")
    for name, metadata in files.items():
        if not isinstance(name, str) or not isinstance(metadata, dict):
            raise ValueError("SSD checkpoint file entry is invalid")
        size = metadata.get("size")
        digest = metadata.get("sha256")
        if (
            not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
        ):
            raise ValueError("SSD checkpoint file metadata is invalid")
        # Hub upload metadata is not part of the Runtime payload. Published
        # checkpoint distributions intentionally omit it, even when an older
        # SSD marker recorded the file while preparing the Hub repository.
        if name in _OPTIONAL_REPOSITORY_METADATA:
            continue
        path = _safe_path(root, boundary, name)
        if not path.is_file() or path.stat().st_size != size:
            raise ValueError(f"SSD checkpoint file is missing or truncated: {name}")

    index_digest = manifest.get("index_sha256")
    if index_digest != files["model.safetensors.index.json"]["sha256"]:
        raise ValueError("SSD checkpoint index digest is inconsistent")
    for name in ("model.safetensors.index.json", "external-tensors.json"):
        path = _safe_path(root, boundary, name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != files[name]["sha256"]:
            raise ValueError(f"SSD checkpoint metadata digest mismatch: {name}")

    expert_relative = manifest.get("expert_store")
    if not isinstance(expert_relative, str):
        raise ValueError("SSD checkpoint expert store is missing")
    expert_store = _safe_path(root, boundary, expert_relative)
    expert_manifest = _json_object(
        expert_store / "manifest.json", "expert store manifest"
    )
    if family == "deepseek_v41":
        if (
            expert_manifest.get("status") != "complete"
            or not isinstance(expert_manifest.get("layers"), list)
        ):
            raise ValueError("DeepSeek V4.1 expert store is incomplete")
    elif (
        expert_manifest.get("format") != "omlx-moe-expert-major-set"
        or expert_manifest.get("version") != 1
        or expert_manifest.get("variant") != layout
        or not isinstance(expert_manifest.get("layers"), dict)
        or not expert_manifest["layers"]
    ):
        raise ValueError("SSD expert store layout differs from the checkpoint")
    return manifest


class ExternalTensorReader:
    """Read original packed tensors from an SSD-ready expert store."""

    def __init__(
        self,
        checkpoint: str | Path,
        *,
        authorized_root: str | Path | None = None,
        expected_family: str | None = None,
        expected_layout: str | None = None,
    ) -> None:
        self.root = Path(checkpoint).resolve()
        self.authorized_root = (
            Path(authorized_root).resolve() if authorized_root else self.root
        )
        self.manifest = inspect_ssd_checkpoint(
            self.root,
            authorized_root=self.authorized_root,
            expected_family=expected_family,
            expected_layout=expected_layout,
        )
        self.tensors = _json_object(
            self.path("external-tensors.json"), "external tensor map"
        )

    def path(self, name: str) -> Path:
        return _safe_path(self.root, self.authorized_root, name)

    def _geometry(self, name: str) -> tuple[dict[str, Any], Path, int, int, int, int]:
        try:
            tensor = self.tensors[name]
        except KeyError as exc:
            raise KeyError(f"external tensor is not declared: {name}") from exc
        if not isinstance(tensor, dict):
            raise ValueError("external tensor entry is invalid")
        file_name = tensor.get("file")
        if not isinstance(file_name, str) or file_name not in self.manifest["files"]:
            raise ValueError("external tensor file is not declared")
        path = self.path(file_name)
        expected_size = self.manifest["files"][file_name]["size"]
        if not path.is_file() or path.stat().st_size != expected_size:
            raise ValueError("external tensor file mismatch")
        count = int(tensor.get("count", 1))
        row_bytes = int(tensor.get("row_bytes", tensor.get("nbytes", 0)))
        stride = int(tensor.get("stride", row_bytes))
        offset = int(tensor.get("offset", -1))
        shape = tensor.get("shape")
        dtype = tensor.get("dtype")
        if (
            not isinstance(shape, list)
            or not shape
            or any(
                not isinstance(dimension, int) or dimension <= 0
                for dimension in shape
            )
            or dtype not in _BYTES
        ):
            raise ValueError("invalid external tensor shape or dtype")
        if (
            count <= 0
            or row_bytes <= 0
            or stride < row_bytes
            or offset < 0
            or offset + (count - 1) * stride + row_bytes > expected_size
            or math.prod(shape) * _BYTES[dtype] != row_bytes * count
        ):
            raise ValueError("external tensor range is invalid")
        return tensor, path, count, row_bytes, stride, offset

    def read(self, name: str, rows: Iterable[int] | None = None) -> bytes:
        _tensor, path, count, row_bytes, stride, offset = self._geometry(name)
        selected = tuple(range(count)) if rows is None else tuple(int(row) for row in rows)
        if not selected or any(row < 0 or row >= count for row in selected):
            raise ValueError("external tensor row selection is invalid")
        data = bytearray(row_bytes * len(selected))
        with path.open("rb") as handle:
            view = memoryview(data)
            for output_row, source_row in enumerate(selected):
                handle.seek(offset + source_row * stride)
                part = view[output_row * row_bytes : (output_row + 1) * row_bytes]
                read = 0
                while read < row_bytes:
                    size = handle.readinto(part[read:])
                    if not size:
                        raise EOFError("short external tensor read")
                    read += size
        return bytes(data)

    def mlx_array(self, name: str, rows: Iterable[int] | None = None):
        import mlx.core as mx
        import numpy as np

        tensor, _path, count, _row_bytes, _stride, _offset = self._geometry(name)
        selected = tuple(range(count)) if rows is None else tuple(int(row) for row in rows)
        shape = tuple(int(value) for value in tensor["shape"])
        if count > 1:
            shape = (len(selected), *shape[1:])
        elif len(selected) != 1:
            raise ValueError("single-row external tensor cannot be expanded")
        dtypes = {
            "U8": np.uint8,
            "I8": np.int8,
            "U16": np.uint16,
            "I16": np.int16,
            "U32": np.uint32,
            "I32": np.int32,
            "U64": np.uint64,
            "I64": np.int64,
            "BF16": np.uint16,
            "F16": np.float16,
            "F32": np.float32,
            "F64": np.float64,
            "F8_E8M0": np.uint8,
            "F8_E4M3": np.uint8,
        }
        value = mx.array(
            np.frombuffer(
                self.read(name, selected), dtype=dtypes[tensor["dtype"]]
            ).copy().reshape(shape)
        )
        if tensor["dtype"] == "BF16":
            value = value.view(mx.bfloat16)
        return value

    def iter_mlx_weights(self):
        """Yield original tensor names and arrays for a Full loader."""

        for name in self.tensors:
            yield name, self.mlx_array(name)


__all__ = [
    "ExternalTensorReader",
    "SSD_CHECKPOINT_LAYOUTS",
    "SSD_CHECKPOINT_SCHEMA",
    "inspect_ssd_checkpoint",
]
