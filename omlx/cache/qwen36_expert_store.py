"""Build compute-ready Qwen3.5/3.6 expert stores in one streaming pass.

Official MLX checkpoints keep each routed projection stacked as
``[num_experts, ...]``.  This converter addresses rows directly in the source
safetensors and writes the exact fused ``SwitchGLU`` record consumed by the
native SSD-to-unified-memory loader.  It never materializes a shard or creates
the historical split gate/up intermediate store.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .moe_expert_store import FORMAT, HEADER_BYTES, VERSION, set_no_cache

_KEY = re.compile(
    r"(?:^|\.)layers\.(\d+)\.mlp\.switch_mlp\."
    r"(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$"
)
_SOURCE_NAMES = tuple(
    f"{projection}.{component}"
    for projection in ("gate_proj", "up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
)
_RUNTIME_NAMES = tuple(
    f"{projection}.{component}"
    for projection in ("gate_up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
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


def _write_all(fd: int, data: bytes | memoryview) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write while creating Qwen3.6 expert store")
        view = view[written:]


def _header(path: Path) -> tuple[int, dict[str, Any]]:
    with path.open("rb") as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise ValueError(f"invalid safetensors header in {path}")
        header_length = int.from_bytes(raw_length, "little")
        payload = json.loads(handle.read(header_length))
    return 8 + header_length, payload


def discover_qwen36_expert_rows(
    checkpoint: str | os.PathLike[str],
) -> dict[int, dict[str, TensorRows]]:
    """Resolve every stacked routed tensor to a row-addressable byte range."""

    root = Path(checkpoint).expanduser().resolve()
    config = json.loads((root / "config.json").read_text())
    text_config = config.get("text_config") or config
    num_experts = int(text_config.get("num_experts", 0))
    num_layers = int(text_config.get("num_hidden_layers", 0))
    if config.get("model_type") != "qwen3_5_moe":
        raise ValueError(f"checkpoint is not qwen3_5_moe: {root}")
    if num_experts <= 0 or num_layers <= 0:
        raise ValueError(f"invalid Qwen MoE dimensions in {root / 'config.json'}")

    index_path = root / "model.safetensors.index.json"
    weight_map = json.loads(index_path.read_text()).get("weight_map")
    if not isinstance(weight_map, dict):
        raise ValueError(f"missing weight_map in {index_path}")

    wanted: dict[int, dict[str, str]] = {}
    for key in weight_map:
        match = _KEY.search(key)
        if match is None:
            continue
        layer = int(match.group(1))
        name = f"{match.group(2)}.{match.group(3)}"
        wanted.setdefault(layer, {})[name] = key
    if set(wanted) != set(range(num_layers)):
        raise ValueError(
            f"Qwen routed layers differ from config: found={sorted(wanted)}, "
            f"expected=0..{num_layers - 1}"
        )

    shard_names = {
        str(weight_map[key])
        for tensors in wanted.values()
        for key in tensors.values()
    }
    headers = {}
    for shard_name in shard_names:
        path = root / shard_name
        if not path.is_file():
            raise FileNotFoundError(f"checkpoint shard is missing: {path}")
        data_start, payload = _header(path)
        headers[shard_name] = (path, data_start, payload)

    result: dict[int, dict[str, TensorRows]] = {}
    for layer, tensors in wanted.items():
        if set(tensors) != set(_SOURCE_NAMES):
            raise ValueError(f"Qwen layer {layer} routed tensors are incomplete")
        rows = {}
        for name, key in tensors.items():
            shard_name = str(weight_map[key])
            path, data_start, payload = headers[shard_name]
            info = payload.get(key)
            if not isinstance(info, dict):
                raise ValueError(f"{key} is absent from indexed shard {path}")
            start, end = (int(value) for value in info["data_offsets"])
            shape = tuple(int(value) for value in info["shape"])
            if not shape or shape[0] != num_experts:
                raise ValueError(f"unexpected Qwen expert shape for {key}: {shape}")
            total_bytes = end - start
            if total_bytes % num_experts:
                raise ValueError(f"Qwen tensor is not row-addressable: {key}")
            rows[name] = TensorRows(
                key=key,
                path=path,
                offset=data_start + start,
                dtype=str(info["dtype"]),
                shape=shape,
                row_bytes=total_bytes // num_experts,
            )
        result[layer] = rows
    return result


def create_qwen36_direct_store(
    checkpoint: str | os.PathLike[str],
    layer: int,
    output: str | os.PathLike[str],
    *,
    force: bool = False,
    discovered: dict[int, dict[str, TensorRows]] | None = None,
) -> dict[str, Any]:
    """Write one Qwen layer as final fused, page-aligned expert records."""

    root = Path(checkpoint).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    if output_path.exists() and not force:
        raise FileExistsError(f"output already exists: {output_path}")
    layers = discovered or discover_qwen36_expert_rows(root)
    sources = layers.get(layer)
    if sources is None:
        raise KeyError(f"Qwen checkpoint has no routed expert layer {layer}")
    num_experts = next(iter(sources.values())).shape[0]

    tensors: list[dict[str, Any]] = []
    cursor = 0
    for name in _RUNTIME_NAMES:
        if name.startswith("gate_up_proj."):
            component = name.rsplit(".", 1)[1]
            parts = (sources[f"gate_proj.{component}"], sources[f"up_proj.{component}"])
        else:
            parts = (sources[name],)
        first = parts[0]
        if any(
            item.dtype != first.dtype or item.shape[2:] != first.shape[2:]
            for item in parts
        ):
            raise ValueError(f"Qwen layer {layer} cannot fuse {name}")
        shape = (sum(item.shape[1] for item in parts), *first.shape[2:])
        nbytes = sum(item.row_bytes for item in parts)
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
        raise ValueError(f"Qwen layer {layer} record is not page aligned: {record_bytes}")

    header = {
        "format": FORMAT,
        "version": VERSION,
        "variant": "qwen3.6-affine-q4-gate-up-fused-direct-v3",
        "runtime_layout": "fused-switch-glu",
        "layer": layer,
        "num_experts": num_experts,
        "record_bytes": record_bytes,
        "data_offset": HEADER_BYTES,
        "source": str(root),
        "source_revision": root.name if len(root.name) == 40 else None,
        "tensors": tensors,
    }
    encoded = json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > HEADER_BYTES - 8:
        raise ValueError("Qwen expert-store header exceeds one page")
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
        for expert in range(num_experts):
            for name in _RUNTIME_NAMES:
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
        "experts": num_experts,
        "record_bytes": record_bytes,
        "file_bytes": output_path.stat().st_size,
        "sha256_payload": digest.hexdigest(),
        "variant": header["variant"],
    }


__all__ = ["create_qwen36_direct_store", "discover_qwen36_expert_rows"]
