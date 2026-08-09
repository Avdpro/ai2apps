"""Fixed-record, expert-major storage for cacheable MoE weights.

The format deliberately has no per-read parsing or tensor-name lookup.  Every
expert in a layer occupies one page-aligned, fixed-size record and its MXFP4
or affine-quantized tensors occur in the exact order described by the file
header. A cache loader can therefore fetch an expert with one contiguous
``pread``.

This module only implements storage and CPU staging.  Publishing a record into
an MLX slot remains a separate synchronization concern: callers must not reuse
a staging buffer or overwrite a slot while Metal is consuming it.
"""

from __future__ import annotations

import hashlib
import fcntl
import json
import mmap
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Iterator


FORMAT = "omlx-moe-expert-major"
VERSION = 1
HEADER_BYTES = 4096
_DARWIN_F_NOCACHE = 48


def set_no_cache(fd: int) -> None:
    """Ask Darwin to bypass the unified buffer cache for this descriptor."""

    if os.uname().sysname == "Darwin":
        fcntl.fcntl(fd, _DARWIN_F_NOCACHE, 1)


@cache
def _record_copy_kernel():
    import mlx.core as mx

    return mx.fast.metal_kernel(
        name="omlx_moe_record_copy_u8",
        input_names=["source"],
        output_names=["destination"],
        source="""
            uint elem = thread_position_in_grid.x;
            if (elem < N4) {
                const device uint4* source4 =
                    reinterpret_cast<const device uint4*>(source);
                device uint4* destination4 =
                    reinterpret_cast<device uint4*>(destination);
                destination4[elem] = source4[elem];
            }
        """,
        ensure_row_contiguous=True,
    )


def _read_exact(fd: int, size: int, offset: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.pread(fd, remaining, offset)
        if not chunk:
            raise EOFError(f"short read at offset {offset}: wanted {remaining} bytes")
        chunks.append(chunk)
        offset += len(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_all(fd: int, data: bytes | bytearray | memoryview) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write while creating expert-major store")
        view = view[written:]


@dataclass(frozen=True)
class TensorLayout:
    name: str
    dtype: str
    shape: tuple[int, ...]
    offset: int
    nbytes: int


class ExpertMajorStore:
    """Read one layer of fixed-size expert records."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._fd = os.open(self.path, os.O_RDONLY)
        try:
            raw_header = _read_exact(self._fd, HEADER_BYTES, 0)
            header_len = int.from_bytes(raw_header[:8], "little")
            if not 0 < header_len <= HEADER_BYTES - 8:
                raise ValueError(f"invalid expert-major header length: {header_len}")
            header = json.loads(raw_header[8 : 8 + header_len])
            if header.get("format") != FORMAT or header.get("version") != VERSION:
                raise ValueError(f"unsupported expert-major file: {self.path}")
            self.layer = int(header["layer"])
            self.num_experts = int(header["num_experts"])
            self.record_bytes = int(header["record_bytes"])
            self.data_offset = int(header["data_offset"])
            self.tensors = tuple(
                TensorLayout(
                    name=item["name"],
                    dtype=item["dtype"],
                    shape=tuple(item["shape"]),
                    offset=int(item["offset"]),
                    nbytes=int(item["nbytes"]),
                )
                for item in header["tensors"]
            )
            expected = self.data_offset + self.num_experts * self.record_bytes
            actual = os.fstat(self._fd).st_size
            if actual != expected:
                raise ValueError(
                    f"expert-major size mismatch: expected {expected}, found {actual}"
                )
        except Exception:
            os.close(self._fd)
            raise
        self._mapping: mmap.mmap | None = None

    def close(self) -> None:
        if self._mapping is not None:
            self._mapping.close()
            self._mapping = None
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> "ExpertMajorStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def expert_offset(self, expert_id: int) -> int:
        if not 0 <= expert_id < self.num_experts:
            raise IndexError(f"expert {expert_id} outside [0, {self.num_experts})")
        return self.data_offset + expert_id * self.record_bytes

    def allocate_staging(self) -> bytearray:
        return bytearray(self.record_bytes)

    def set_no_cache(self) -> None:
        set_no_cache(self._fd)

    def read(self, expert_id: int) -> bytes:
        return _read_exact(self._fd, self.record_bytes, self.expert_offset(expert_id))

    def read_into(self, expert_id: int, staging: bytearray) -> memoryview:
        if len(staging) != self.record_bytes:
            raise ValueError(
                f"staging buffer is {len(staging)} bytes, expected {self.record_bytes}"
            )
        view = memoryview(staging)
        done = 0
        offset = self.expert_offset(expert_id)
        while done < self.record_bytes:
            count = os.preadv(self._fd, [view[done:]], offset + done)
            if count <= 0:
                raise EOFError(f"short preadv for expert {expert_id}")
            done += count
        return view

    def mmap_view(self, expert_id: int) -> memoryview:
        if self._mapping is None:
            self._mapping = mmap.mmap(self._fd, 0, access=mmap.ACCESS_READ)
        start = self.expert_offset(expert_id)
        return memoryview(self._mapping)[start : start + self.record_bytes]

    def tensor_views(
        self, record: bytes | bytearray | memoryview
    ) -> Iterator[tuple[TensorLayout, memoryview]]:
        view = memoryview(record)
        if len(view) != self.record_bytes:
            raise ValueError(
                f"record is {len(view)} bytes, expected {self.record_bytes}"
            )
        for tensor in self.tensors:
            yield tensor, view[tensor.offset : tensor.offset + tensor.nbytes]

    def mlx_tensor_views(
        self,
        record: bytes | bytearray | memoryview,
        *,
        copy_record: bool = False,
    ) -> dict[str, Any]:
        """Expose six typed MLX views backed by one contiguous record.

        With ``copy_record=False`` the returned arrays share the CPU record;
        the caller must keep it alive.  With ``copy_record=True`` one Metal
        launch copies the whole record to an MLX-owned allocation before the
        views are made.  The latter is the safe prototype for publishing a
        cache slot and replaces six array creations/copies with one.
        """

        import mlx.core as mx
        import numpy as np

        raw = memoryview(record)
        if len(raw) != self.record_bytes:
            raise ValueError(
                f"record is {len(raw)} bytes, expected {self.record_bytes}"
            )
        base = mx.array(np.frombuffer(raw, dtype=np.uint8))
        if copy_record:
            kernel = _record_copy_kernel()
            (base,) = kernel(
                inputs=[base],
                template=[("N4", self.record_bytes // 16)],
                grid=(self.record_bytes // 16, 1, 1),
                threadgroup=(256, 1, 1),
                output_shapes=[(self.record_bytes,)],
                output_dtypes=[mx.uint8],
            )
        dtype_map = {
            "U8": mx.uint8,
            "U32": mx.uint32,
            "F16": mx.float16,
            "BF16": mx.bfloat16,
        }
        result = {}
        for tensor in self.tensors:
            value = base[tensor.offset : tensor.offset + tensor.nbytes]
            dtype = dtype_map[tensor.dtype]
            if dtype != mx.uint8:
                value = value.view(dtype)
            result[tensor.name] = value.reshape(tensor.shape)
        return result


def create_expert_major_store(
    offset_manifest: str | os.PathLike[str],
    layer: int,
    output: str | os.PathLike[str],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Repack one layer from a DMoE offset manifest without MLX allocation."""

    output_path = Path(output)
    if output_path.exists() and not force:
        raise FileExistsError(f"output already exists: {output_path}")
    manifest_path = Path(offset_manifest).resolve()
    manifest = json.loads(manifest_path.read_text())
    layer_info = manifest["layers"][str(layer)]
    # DMoE has emitted two offset-manifest layouts over the life of the
    # project.  DeepSeek manifests enumerate the source ranges for every
    # expert, while the Qwen3.6 converter already writes a fixed-stride,
    # expert-major ``layer-NNN.bin`` and records one relative tensor layout.
    # Accept both without importing any DMoE runtime code.
    if "experts" not in layer_info:
        return _wrap_fixed_stride_layer(
            manifest_path,
            layer,
            layer_info,
            output_path,
        )

    experts = layer_info["experts"]
    if len(experts) != int(layer_info["expert_count"]):
        raise ValueError("offset manifest expert count mismatch")

    default_file = layer_info.get("file")
    source_files = {
        tensor.get("file", default_file)
        for expert in experts
        for tensor in expert["tensors"]
    }
    if None in source_files:
        raise ValueError("offset manifest tensor is missing its source file")
    source_paths = {
        str(name): (manifest_path.parent / str(name)).resolve()
        for name in source_files
    }
    first = experts[0]["tensors"]
    tensor_layout: list[dict[str, Any]] = []
    cursor = 0
    for tensor in first:
        tensor_layout.append(
            {
                "name": tensor["name"],
                "dtype": tensor["dtype"],
                "shape": tensor["shape"],
                "offset": cursor,
                "nbytes": int(tensor["nbytes"]),
            }
        )
        cursor += int(tensor["nbytes"])
    record_bytes = cursor
    if record_bytes != int(layer_info["expert_bytes"]):
        raise ValueError("record size differs from manifest expert_bytes")
    if record_bytes % 4096:
        raise ValueError("expert records must be page aligned")

    header = {
        "format": FORMAT,
        "version": VERSION,
        "layer": layer,
        "num_experts": len(experts),
        "record_bytes": record_bytes,
        "data_offset": HEADER_BYTES,
        "source": (
            str(next(iter(source_paths.values())))
            if len(source_paths) == 1
            else [str(path) for path in sorted(source_paths.values())]
        ),
        "source_manifest": str(manifest_path),
        "tensors": tensor_layout,
    }
    encoded = json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > HEADER_BYTES - 8:
        raise ValueError("expert-major header exceeds one page")
    header_page = len(encoded).to_bytes(8, "little") + encoded
    header_page += bytes(HEADER_BYTES - len(header_page))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".partial")
    if temporary.exists():
        temporary.unlink()

    source_fds = {
        name: os.open(path, os.O_RDONLY) for name, path in source_paths.items()
    }
    output_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    # Conversion is a one-shot stream; retaining a multi-GiB destination in the
    # page cache only contaminates the subsequent cold-read benchmark.
    set_no_cache(output_fd)
    digest = hashlib.sha256()
    try:
        _write_all(output_fd, header_page)
        staging = bytearray(record_bytes)
        staging_view = memoryview(staging)
        for expert_id, expert in enumerate(experts):
            tensors = expert["tensors"]
            if len(tensors) != len(tensor_layout):
                raise ValueError(f"expert {expert_id} tensor count mismatch")
            cursor = 0
            for expected, tensor in zip(tensor_layout, tensors, strict=True):
                nbytes = int(tensor["nbytes"])
                if (
                    tensor["name"] != expected["name"]
                    or tensor["dtype"] != expected["dtype"]
                    or tensor["shape"] != expected["shape"]
                    or nbytes != expected["nbytes"]
                ):
                    raise ValueError(f"expert {expert_id} layout mismatch")
                source_name = str(tensor.get("file", default_file))
                staging_view[cursor : cursor + nbytes] = _read_exact(
                    source_fds[source_name],
                    nbytes,
                    int(tensor["absolute_offset"]),
                )
                cursor += nbytes
            _write_all(output_fd, staging_view)
            digest.update(staging_view)
        os.fsync(output_fd)
    except Exception:
        os.close(output_fd)
        for source_fd in source_fds.values():
            os.close(source_fd)
        temporary.unlink(missing_ok=True)
        raise
    else:
        os.close(output_fd)
        for source_fd in source_fds.values():
            os.close(source_fd)
    os.replace(temporary, output_path)
    return {
        "path": str(output_path.resolve()),
        "layer": layer,
        "experts": len(experts),
        "record_bytes": record_bytes,
        "file_bytes": output_path.stat().st_size,
        "sha256_payload": digest.hexdigest(),
    }


def _wrap_fixed_stride_layer(
    manifest_path: Path,
    layer: int,
    layer_info: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    """Add an oMLX header to an already expert-major DMoE layer file."""

    source = (manifest_path.parent / layer_info["file"]).resolve()
    num_experts = int(layer_info["expert_count"])
    record_bytes = int(layer_info.get("expert_stride", layer_info["expert_bytes"]))
    if record_bytes != int(layer_info["expert_bytes"]):
        raise ValueError("fixed-stride manifest contains record padding")
    if record_bytes % 4096:
        raise ValueError("expert records must be page aligned")
    expected_source_bytes = num_experts * record_bytes
    if source.stat().st_size != expected_source_bytes:
        raise ValueError(
            "fixed-stride source size mismatch: "
            f"expected {expected_source_bytes}, found {source.stat().st_size}"
        )

    tensor_layout = []
    occupied: list[tuple[int, int]] = []
    for tensor in layer_info["tensors"]:
        offset = int(tensor["relative_offset"])
        nbytes = int(tensor["nbytes"])
        if offset < 0 or nbytes <= 0 or offset + nbytes > record_bytes:
            raise ValueError(f"invalid fixed-stride tensor range: {tensor['name']}")
        occupied.append((offset, offset + nbytes))
        tensor_layout.append(
            {
                "name": tensor["name"],
                "dtype": tensor["dtype"],
                "shape": tensor["shape"],
                "offset": offset,
                "nbytes": nbytes,
            }
        )
    occupied.sort()
    if any(end > next_start for (_, end), (next_start, _) in zip(occupied, occupied[1:])):
        raise ValueError("fixed-stride tensor ranges overlap")

    header = {
        "format": FORMAT,
        "version": VERSION,
        "layer": layer,
        "num_experts": num_experts,
        "record_bytes": record_bytes,
        "data_offset": HEADER_BYTES,
        "source": str(source),
        "source_manifest": str(manifest_path),
        "tensors": tensor_layout,
    }
    encoded = json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > HEADER_BYTES - 8:
        raise ValueError("expert-major header exceeds one page")
    header_page = len(encoded).to_bytes(8, "little") + encoded
    header_page += bytes(HEADER_BYTES - len(header_page))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".partial")
    if temporary.exists():
        temporary.unlink()
    source_fd = os.open(source, os.O_RDONLY)
    output_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    set_no_cache(output_fd)
    digest = hashlib.sha256()
    try:
        _write_all(output_fd, header_page)
        offset = 0
        chunk_bytes = 8 * 1024 * 1024
        while offset < expected_source_bytes:
            chunk = _read_exact(
                source_fd,
                min(chunk_bytes, expected_source_bytes - offset),
                offset,
            )
            _write_all(output_fd, chunk)
            digest.update(chunk)
            offset += len(chunk)
        os.fsync(output_fd)
    except Exception:
        os.close(output_fd)
        os.close(source_fd)
        temporary.unlink(missing_ok=True)
        raise
    else:
        os.close(output_fd)
        os.close(source_fd)
    os.replace(temporary, output_path)
    return {
        "path": str(output_path.resolve()),
        "layer": layer,
        "experts": num_experts,
        "record_bytes": record_bytes,
        "file_bytes": output_path.stat().st_size,
        "sha256_payload": digest.hexdigest(),
        "source_layout": "fixed-stride",
    }
