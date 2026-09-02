"""Build cache-friendly GLM-5 expert stores from MLX safetensors.

GLM-5.3 MLX checkpoints store every routed expert as nine independent
safetensors entries.  This module repacks those entries into the fixed-record
``ExpertMajorStore`` format without allocating MLX arrays or loading a shard in
full.  Each expert can then be fetched with one contiguous ``pread``.
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

_EXPERT_KEY = re.compile(
    r"(?:^|\.)layers\.(\d+)\.mlp\.experts\.(\d+)\."
    r"(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$"
)
_SOURCE_TENSOR_ORDER = tuple(
    f"{projection}.{component}"
    for projection in ("gate_proj", "up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
)
_RUNTIME_TENSOR_ORDER = tuple(
    f"{projection}.{component}"
    for projection in ("gate_up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
)


@dataclass(frozen=True)
class _TensorSource:
    key: str
    path: Path
    offset: int
    nbytes: int
    dtype: str
    shape: tuple[int, ...]


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
        count = os.write(fd, view)
        if count <= 0:
            raise OSError("short write while creating GLM-5 expert store")
        view = view[count:]


def _read_safetensors_header(path: Path) -> tuple[int, dict[str, Any]]:
    with path.open("rb") as handle:
        raw_len = handle.read(8)
        if len(raw_len) != 8:
            raise ValueError(f"invalid safetensors header in {path}")
        header_len = int.from_bytes(raw_len, "little")
        header = json.loads(handle.read(header_len))
    return 8 + header_len, header


def discover_glm5_experts(
    checkpoint: str | os.PathLike[str],
) -> dict[int, dict[int, dict[str, _TensorSource]]]:
    """Resolve every per-expert tensor to a byte range in its source shard."""

    root = Path(checkpoint).expanduser().resolve()
    index_path = root / "model.safetensors.index.json"
    index = json.loads(index_path.read_text())
    weight_map = index.get("weight_map")
    if not isinstance(weight_map, dict):
        raise ValueError(f"missing weight_map in {index_path}")

    relevant: dict[str, tuple[int, int, str]] = {}
    shards: set[str] = set()
    for key, shard in weight_map.items():
        match = _EXPERT_KEY.search(key)
        if match is None:
            continue
        layer = int(match.group(1))
        expert = int(match.group(2))
        name = f"{match.group(3)}.{match.group(4)}"
        relevant[key] = (layer, expert, name)
        shards.add(str(shard))
    if not relevant:
        raise ValueError(f"no GLM-5 per-expert tensors found in {index_path}")

    headers: dict[str, tuple[Path, int, dict[str, Any]]] = {}
    for shard in sorted(shards):
        path = root / shard
        if not path.is_file():
            raise FileNotFoundError(f"checkpoint shard is missing: {path}")
        data_start, header = _read_safetensors_header(path)
        headers[shard] = (path, data_start, header)

    layers: dict[int, dict[int, dict[str, _TensorSource]]] = {}
    for key, (layer, expert, name) in relevant.items():
        shard = str(weight_map[key])
        path, data_start, header = headers[shard]
        info = header.get(key)
        if not isinstance(info, dict):
            raise ValueError(f"{key} is absent from indexed shard {path}")
        start, end = (int(value) for value in info["data_offsets"])
        source = _TensorSource(
            key=key,
            path=path,
            offset=data_start + start,
            nbytes=end - start,
            dtype=str(info["dtype"]),
            shape=tuple(int(value) for value in info["shape"]),
        )
        bucket = layers.setdefault(layer, {}).setdefault(expert, {})
        if name in bucket:
            raise ValueError(f"duplicate GLM-5 expert tensor {key}")
        bucket[name] = source
    return layers


def create_glm5_expert_major_store(
    checkpoint: str | os.PathLike[str],
    layer: int,
    output: str | os.PathLike[str],
    *,
    force: bool = False,
    discovered: dict[int, dict[int, dict[str, _TensorSource]]] | None = None,
) -> dict[str, Any]:
    """Repack one GLM-5 sparse layer into fixed expert-major records."""

    root = Path(checkpoint).expanduser().resolve()
    output_path = Path(output).expanduser().resolve()
    if output_path.exists() and not force:
        raise FileExistsError(f"output already exists: {output_path}")
    layers = discovered if discovered is not None else discover_glm5_experts(root)
    experts = layers.get(layer)
    if not experts:
        raise KeyError(f"GLM-5 checkpoint has no sparse expert layer {layer}")
    expert_ids = sorted(experts)
    if expert_ids != list(range(len(expert_ids))):
        raise ValueError(f"layer {layer} expert IDs are not contiguous from zero")

    first = experts[0]
    if set(first) != set(_SOURCE_TENSOR_ORDER):
        missing = sorted(set(_SOURCE_TENSOR_ORDER) - set(first))
        extra = sorted(set(first) - set(_SOURCE_TENSOR_ORDER))
        raise ValueError(
            f"layer {layer} expert layout mismatch: missing={missing}, extra={extra}"
        )
    tensors: list[dict[str, Any]] = []
    cursor = 0
    # Persist the exact tensors consumed by the fused GLM SwitchGLU.  Affine
    # quantization is row-local, so gate/up can be fused by concatenating their
    # already-packed rows.  No dequantization, transpose, or numerical rewrite
    # is involved.
    output_sources: dict[str, tuple[_TensorSource, ...]] = {}
    for component in ("weight", "scales", "biases"):
        gate = first[f"gate_proj.{component}"]
        up = first[f"up_proj.{component}"]
        if gate.dtype != up.dtype or gate.shape[1:] != up.shape[1:]:
            raise ValueError(
                f"layer {layer} cannot fuse gate/up {component}: "
                f"gate={(gate.dtype, gate.shape)}, up={(up.dtype, up.shape)}"
            )
        output_sources[f"gate_up_proj.{component}"] = (gate, up)
        output_sources[f"down_proj.{component}"] = (first[f"down_proj.{component}"],)

    for name in _RUNTIME_TENSOR_ORDER:
        sources = output_sources[name]
        source = sources[0]
        shape = (sum(item.shape[0] for item in sources), *source.shape[1:])
        nbytes = sum(item.nbytes for item in sources)
        tensors.append(
            {
                "name": name,
                "dtype": source.dtype,
                "shape": list(shape),
                "offset": cursor,
                "nbytes": nbytes,
            }
        )
        cursor += nbytes
    record_bytes = cursor
    if record_bytes % 4096:
        raise ValueError(
            f"GLM-5 layer {layer} expert record is not page aligned: {record_bytes}"
        )

    for expert_id in expert_ids:
        current = experts[expert_id]
        if set(current) != set(_SOURCE_TENSOR_ORDER):
            raise ValueError(f"layer {layer} expert {expert_id} is incomplete")
        for name in _SOURCE_TENSOR_ORDER:
            source = current[name]
            template = first[name]
            if (source.dtype, source.shape, source.nbytes) != (
                template.dtype,
                template.shape,
                template.nbytes,
            ):
                raise ValueError(
                    f"layer {layer} expert {expert_id} {name} layout changed"
                )

    revision = root.name if len(root.name) == 40 else None
    header = {
        "format": FORMAT,
        "version": VERSION,
        "variant": "glm5-next-affine-q4-gate-up-fused-v2",
        "runtime_layout": "fused-switch-glu",
        "layer": layer,
        "num_experts": len(expert_ids),
        "record_bytes": record_bytes,
        "data_offset": HEADER_BYTES,
        "source": str(root),
        "source_revision": revision,
        "tensors": tensors,
    }
    encoded = json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > HEADER_BYTES - 8:
        raise ValueError("GLM-5 expert-store header exceeds one page")
    header_page = len(encoded).to_bytes(8, "little") + encoded
    header_page += bytes(HEADER_BYTES - len(header_page))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".partial")
    temporary.unlink(missing_ok=True)
    output_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    set_no_cache(output_fd)
    source_fds: dict[Path, int] = {}
    digest = hashlib.sha256()
    try:
        _write_all(output_fd, header_page)
        for expert_id in expert_ids:
            current = experts[expert_id]
            for name in _RUNTIME_TENSOR_ORDER:
                if name.startswith("gate_up_proj."):
                    component = name.rsplit(".", 1)[1]
                    sources = (
                        current[f"gate_proj.{component}"],
                        current[f"up_proj.{component}"],
                    )
                else:
                    sources = (current[name],)
                for source in sources:
                    source_fd = source_fds.get(source.path)
                    if source_fd is None:
                        source_fd = os.open(source.path, os.O_RDONLY)
                        source_fds[source.path] = source_fd
                    raw = _read_exact(source_fd, source.nbytes, source.offset)
                    _write_all(output_fd, raw)
                    digest.update(raw)
        os.fsync(output_fd)
    except Exception:
        os.close(output_fd)
        temporary.unlink(missing_ok=True)
        raise
    else:
        os.close(output_fd)
    finally:
        for source_fd in source_fds.values():
            os.close(source_fd)
    os.replace(temporary, output_path)
    return {
        "path": str(output_path),
        "layer": layer,
        "experts": len(expert_ids),
        "record_bytes": record_bytes,
        "file_bytes": output_path.stat().st_size,
        "sha256_payload": digest.hexdigest(),
        "variant": header["variant"],
    }


__all__ = ["create_glm5_expert_major_store", "discover_glm5_experts"]
