"""Build compute-ready Qwen4 expert-major stores from MLX safetensors.

The Qwen3.8 Flash Next MLX checkpoint stores each projection as one stacked
``[512, ...]`` tensor.  This converter copies one row from each stacked tensor
into a page-aligned expert record and fuses gate/up rows in the exact order
consumed by the runtime ``SwitchGLU``.  Decode misses consequently require one
contiguous pread and no reshape, transpose, dequantization, or concatenation.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .moe_expert_store import FORMAT, HEADER_BYTES, VERSION, set_no_cache

_PROJECTIONS = ("gate_proj", "up_proj", "down_proj")
_COMPONENTS = ("weight", "scales", "biases")
_RUNTIME_ORDER = tuple(
    f"{projection}.{component}"
    for projection in ("gate_up_proj", "down_proj")
    for component in _COMPONENTS
)


@dataclass(frozen=True)
class TensorRows:
    key: str
    path: Path
    offset: int
    dtype: str
    shape: tuple[int, ...]
    row_bytes: int


def _read_exact(fd: int, size: int, offset: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.pread(fd, remaining, offset)
        if not chunk:
            raise EOFError(f"short read at offset {offset}: wanted {remaining} bytes")
        chunks.append(chunk)
        remaining -= len(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def _write_all(fd: int, data: bytes | bytearray | memoryview) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write while creating Qwen4 expert store")
        view = view[written:]


def _safetensors_header(path: Path) -> tuple[int, dict[str, Any]]:
    with path.open("rb") as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise ValueError(f"invalid safetensors header in {path}")
        header_length = int.from_bytes(raw_length, "little")
        header = json.loads(handle.read(header_length))
    return 8 + header_length, header


def discover_qwen4_expert_rows(
    checkpoint: str | os.PathLike[str],
) -> dict[int, dict[str, TensorRows]]:
    """Resolve all stacked routed-expert tensors to row-addressable ranges."""

    root = Path(checkpoint).expanduser().resolve()
    index_path = root / "model.safetensors.index.json"
    weight_map = json.loads(index_path.read_text()).get("weight_map")
    if not isinstance(weight_map, dict):
        raise ValueError(f"missing weight_map in {index_path}")

    wanted: dict[int, dict[str, str]] = {}
    for layer in range(48):
        prefix = f"language_model.model.layers.{layer}.mlp.switch_mlp"
        for projection in _PROJECTIONS:
            for component in _COMPONENTS:
                name = f"{projection}.{component}"
                key = f"{prefix}.{name}"
                if key in weight_map:
                    wanted.setdefault(layer, {})[name] = key
    if not wanted:
        raise ValueError(f"no Qwen4 stacked experts found in {index_path}")

    shard_names = {
        str(weight_map[key])
        for tensors in wanted.values()
        for key in tensors.values()
    }
    headers = {}
    for shard_name in shard_names:
        path = root / shard_name
        data_start, header = _safetensors_header(path)
        headers[shard_name] = (path, data_start, header)

    result: dict[int, dict[str, TensorRows]] = {}
    for layer, tensors in wanted.items():
        if set(tensors) != {
            f"{projection}.{component}"
            for projection in _PROJECTIONS
            for component in _COMPONENTS
        }:
            raise ValueError(f"Qwen4 layer {layer} routed tensors are incomplete")
        rows: dict[str, TensorRows] = {}
        for name, key in tensors.items():
            shard_name = str(weight_map[key])
            path, data_start, header = headers[shard_name]
            info = header.get(key)
            if not isinstance(info, dict):
                raise ValueError(f"{key} is absent from indexed shard {path}")
            start, end = (int(value) for value in info["data_offsets"])
            shape = tuple(int(value) for value in info["shape"])
            if not shape or shape[0] != 512:
                raise ValueError(f"unexpected Qwen4 expert shape for {key}: {shape}")
            total_bytes = end - start
            if total_bytes % shape[0]:
                raise ValueError(f"Qwen4 tensor is not row-addressable: {key}")
            rows[name] = TensorRows(
                key=key,
                path=path,
                offset=data_start + start,
                dtype=str(info["dtype"]),
                shape=shape,
                row_bytes=total_bytes // shape[0],
            )
        result[layer] = rows
    return result


def create_qwen4_expert_major_store(
    checkpoint: str | os.PathLike[str],
    layer: int,
    output: str | os.PathLike[str],
    *,
    force: bool = False,
    discovered: dict[int, dict[str, TensorRows]] | None = None,
) -> dict[str, Any]:
    """Write one Qwen4 layer as 512 fixed, compute-ready expert records."""

    root = Path(checkpoint).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    if output_path.exists() and not force:
        raise FileExistsError(f"output already exists: {output_path}")
    layers = discovered or discover_qwen4_expert_rows(root)
    sources = layers.get(layer)
    if sources is None:
        raise KeyError(f"Qwen4 checkpoint has no routed expert layer {layer}")

    tensors: list[dict[str, Any]] = []
    cursor = 0
    for name in _RUNTIME_ORDER:
        if name.startswith("gate_up_proj."):
            component = name.rsplit(".", 1)[1]
            parts = (sources[f"gate_proj.{component}"], sources[f"up_proj.{component}"])
        else:
            parts = (sources[name],)
        first = parts[0]
        if any(part.dtype != first.dtype or part.shape[1:] != first.shape[1:] for part in parts):
            raise ValueError(f"Qwen4 layer {layer} cannot fuse {name}")
        shape = (sum(part.shape[1] for part in parts), *first.shape[2:])
        nbytes = sum(part.row_bytes for part in parts)
        tensors.append(
            {
                "name": name,
                "dtype": first.dtype,
                "shape": list(shape),
                "offset": cursor,
                "nbytes": nbytes,
            }
        )
        cursor += nbytes
    record_bytes = cursor
    if record_bytes % 4096:
        raise ValueError(
            f"Qwen4 layer {layer} record is not page aligned: {record_bytes}"
        )

    header = {
        "format": FORMAT,
        "version": VERSION,
        "variant": "qwen4-exp-affine-q4-gate-up-fused-v1",
        "runtime_layout": "fused-switch-glu",
        "layer": layer,
        "num_experts": 512,
        "record_bytes": record_bytes,
        "data_offset": HEADER_BYTES,
        "source": str(root),
        "tensors": tensors,
    }
    encoded = json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > HEADER_BYTES - 8:
        raise ValueError("Qwen4 expert-store header exceeds one page")
    header_page = len(encoded).to_bytes(8, "little") + encoded
    header_page += bytes(HEADER_BYTES - len(header_page))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_name(output_path.name + ".partial")
    partial.unlink(missing_ok=True)
    output_fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    set_no_cache(output_fd)
    source_fds: dict[Path, int] = {}
    digest = hashlib.sha256()
    try:
        _write_all(output_fd, header_page)
        for expert in range(512):
            for name in _RUNTIME_ORDER:
                if name.startswith("gate_up_proj."):
                    component = name.rsplit(".", 1)[1]
                    parts = (
                        sources[f"gate_proj.{component}"],
                        sources[f"up_proj.{component}"],
                    )
                else:
                    parts = (sources[name],)
                for source in parts:
                    fd = source_fds.get(source.path)
                    if fd is None:
                        fd = os.open(source.path, os.O_RDONLY)
                        source_fds[source.path] = fd
                    raw = _read_exact(
                        fd,
                        source.row_bytes,
                        source.offset + expert * source.row_bytes,
                    )
                    _write_all(output_fd, raw)
                    digest.update(raw)
        os.fsync(output_fd)
    except Exception:
        os.close(output_fd)
        partial.unlink(missing_ok=True)
        raise
    else:
        os.close(output_fd)
    finally:
        for fd in source_fds.values():
            os.close(fd)
    os.replace(partial, output_path)
    return {
        "path": str(output_path),
        "layer": layer,
        "experts": 512,
        "record_bytes": record_bytes,
        "file_bytes": output_path.stat().st_size,
        "sha256_payload": digest.hexdigest(),
        "variant": header["variant"],
    }


def verify_qwen4_expert_major_store(
    checkpoint: str | os.PathLike[str],
    layer: int,
    store: str | os.PathLike[str],
    *,
    experts: tuple[int, ...] = (0, 127, 255, 511),
    discovered: dict[int, dict[str, TensorRows]] | None = None,
) -> dict[str, Any]:
    """Compare sampled compute-ready records byte-for-byte with safetensors."""

    if not experts or any(not 0 <= expert < 512 for expert in experts):
        raise ValueError("Qwen4 verification experts must be within [0, 512)")
    sources = (discovered or discover_qwen4_expert_rows(checkpoint))[layer]
    store_path = Path(store).expanduser().resolve()
    store_fd = os.open(store_path, os.O_RDONLY)
    source_fds: dict[Path, int] = {}
    checked = 0
    digest = hashlib.sha256()
    try:
        encoded_length = int.from_bytes(_read_exact(store_fd, 8, 0), "little")
        header = json.loads(_read_exact(store_fd, encoded_length, 8))
        if header.get("variant") != "qwen4-exp-affine-q4-gate-up-fused-v1":
            raise ValueError(f"unexpected Qwen4 store variant: {store_path}")
        record_bytes = int(header["record_bytes"])
        data_offset = int(header["data_offset"])
        for expert in dict.fromkeys(experts):
            expected_parts: list[bytes] = []
            for name in _RUNTIME_ORDER:
                if name.startswith("gate_up_proj."):
                    component = name.rsplit(".", 1)[1]
                    parts = (
                        sources[f"gate_proj.{component}"],
                        sources[f"up_proj.{component}"],
                    )
                else:
                    parts = (sources[name],)
                for source in parts:
                    fd = source_fds.get(source.path)
                    if fd is None:
                        fd = os.open(source.path, os.O_RDONLY)
                        source_fds[source.path] = fd
                    expected_parts.append(
                        _read_exact(
                            fd,
                            source.row_bytes,
                            source.offset + expert * source.row_bytes,
                        )
                    )
            expected = b"".join(expected_parts)
            actual = _read_exact(
                store_fd,
                record_bytes,
                data_offset + expert * record_bytes,
            )
            if actual != expected:
                raise ValueError(
                    f"Qwen4 store mismatch at layer {layer}, expert {expert}"
                )
            checked += len(actual)
            digest.update(actual)
    finally:
        os.close(store_fd)
        for fd in source_fds.values():
            os.close(fd)
    return {
        "layer": layer,
        "experts": list(dict.fromkeys(experts)),
        "checked_bytes": checked,
        "sha256_samples": digest.hexdigest(),
        "store": str(store_path),
    }


__all__ = [
    "create_qwen4_expert_major_store",
    "discover_qwen4_expert_rows",
    "verify_qwen4_expert_major_store",
]
