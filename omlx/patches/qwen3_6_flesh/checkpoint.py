"""Qwen3.6 Cache-MoE checkpoint transformations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from omlx.cache.moe_expert_store import (
    FORMAT,
    HEADER_BYTES,
    VERSION,
    ExpertMajorStore,
    set_no_cache,
)


FUSED_LAYOUT = (
    ("gate_up_proj.weight", "U32", (1024, 256)),
    ("gate_up_proj.scales", "BF16", (1024, 32)),
    ("gate_up_proj.biases", "BF16", (1024, 32)),
    ("down_proj.weight", "U32", (2048, 64)),
    ("down_proj.scales", "BF16", (2048, 8)),
    ("down_proj.biases", "BF16", (2048, 8)),
)


def _write_all(fd: int, data: bytes | bytearray | memoryview) -> None:
    view = memoryview(data)
    while view:
        count = os.write(fd, view)
        if count <= 0:
            raise OSError("short write while creating Qwen fused store")
        view = view[count:]


def create_qwen36_fused_store(
    source: str | os.PathLike[str],
    output: str | os.PathLike[str],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Rewrite one Qwen expert layer into its post-fusion runtime layout."""

    source_path = Path(source).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    if output_path.exists() and not force:
        raise FileExistsError(f"output already exists: {output_path}")
    with ExpertMajorStore(source_path) as store:
        source_names = {tensor.name for tensor in store.tensors}
        required = {
            f"{projection}.{suffix}"
            for projection in ("gate_proj", "up_proj", "down_proj")
            for suffix in ("weight", "scales", "biases")
        }
        if not required.issubset(source_names):
            raise ValueError("source is not a split affine-Q4 Qwen expert store")

        dtype_bytes = {"U32": 4, "BF16": 2}
        tensors = []
        cursor = 0
        for name, dtype, shape in FUSED_LAYOUT:
            elements = 1
            for size in shape:
                elements *= size
            nbytes = elements * dtype_bytes[dtype]
            tensors.append(
                {
                    "name": name,
                    "dtype": dtype,
                    "shape": list(shape),
                    "offset": cursor,
                    "nbytes": nbytes,
                }
            )
            cursor += nbytes
        if cursor != store.record_bytes or cursor % 4096:
            raise ValueError("Qwen fused record must preserve page-aligned size")

        header = {
            "format": FORMAT,
            "version": VERSION,
            "variant": "qwen3.6-affine-q4-gate-up-fused-v2",
            "layer": store.layer,
            "num_experts": store.num_experts,
            "record_bytes": cursor,
            "data_offset": HEADER_BYTES,
            "source": str(source_path),
            "tensors": tensors,
        }
        encoded = json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
        if len(encoded) > HEADER_BYTES - 8:
            raise ValueError("Qwen fused expert header exceeds one page")
        header_page = len(encoded).to_bytes(8, "little") + encoded
        header_page += bytes(HEADER_BYTES - len(header_page))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(output_path.name + ".partial")
        if temporary.exists():
            temporary.unlink()
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        set_no_cache(fd)
        digest = hashlib.sha256()
        try:
            _write_all(fd, header_page)
            for expert_id in range(store.num_experts):
                views = {
                    layout.name: bytes(raw)
                    for layout, raw in store.tensor_views(store.read(expert_id))
                }
                record = b"".join(
                    (
                        views["gate_proj.weight"],
                        views["up_proj.weight"],
                        views["gate_proj.scales"],
                        views["up_proj.scales"],
                        views["gate_proj.biases"],
                        views["up_proj.biases"],
                        views["down_proj.weight"],
                        views["down_proj.scales"],
                        views["down_proj.biases"],
                    )
                )
                if len(record) != cursor:
                    raise RuntimeError("Qwen fused record size mismatch")
                _write_all(fd, record)
                digest.update(record)
            os.fsync(fd)
        except Exception:
            os.close(fd)
            temporary.unlink(missing_ok=True)
            raise
        else:
            os.close(fd)
        os.replace(temporary, output_path)
        return {
            "path": str(output_path),
            "layer": store.layer,
            "experts": store.num_experts,
            "record_bytes": cursor,
            "file_bytes": output_path.stat().st_size,
            "sha256_payload": digest.hexdigest(),
            "variant": header["variant"],
        }


__all__ = ["create_qwen36_fused_store"]
