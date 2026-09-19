#!/usr/bin/env python3
"""Build final Qwen3.6 fused expert records without importing MLX."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path


HEADER_BYTES = 4096
KEY = re.compile(
    r"(?:^|\.)layers\.(\d+)\.mlp\.switch_mlp\."
    r"(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$"
)
SOURCE_NAMES = tuple(
    f"{projection}.{component}"
    for projection in ("gate_proj", "up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
)
RUNTIME_NAMES = tuple(
    f"{projection}.{component}"
    for projection in ("gate_up_proj", "down_proj")
    for component in ("weight", "scales", "biases")
)


def _header(path: Path):
    with path.open("rb") as handle:
        length = int.from_bytes(handle.read(8), "little")
        return 8 + length, json.loads(handle.read(length))


def _read_exact(fd: int, size: int, offset: int) -> bytes:
    pieces = []
    while size:
        value = os.pread(fd, size, offset)
        if not value:
            raise EOFError(f"short read at {offset}")
        pieces.append(value)
        size -= len(value)
        offset += len(value)
    return b"".join(pieces)


def _write_all(fd: int, value: bytes) -> None:
    view = memoryview(value)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write")
        view = view[written:]


def discover(root: Path):
    config = json.loads((root / "config.json").read_text())
    text = config.get("text_config") or config
    layers = int(text["num_hidden_layers"])
    experts = int(text["num_experts"])
    weight_map = json.loads((root / "model.safetensors.index.json").read_text())["weight_map"]
    wanted = {}
    for key in weight_map:
        match = KEY.search(key)
        if match:
            wanted.setdefault(int(match[1]), {})[f"{match[2]}.{match[3]}"] = key
    if set(wanted) != set(range(layers)):
        raise ValueError("routed layer set differs from config")
    shard_headers = {}
    for shard in {weight_map[key] for values in wanted.values() for key in values.values()}:
        path = root / shard
        base, values = _header(path)
        shard_headers[shard] = (path, base, values)
    result = {}
    for layer, values in wanted.items():
        if set(values) != set(SOURCE_NAMES):
            raise ValueError(f"incomplete layer {layer}")
        rows = {}
        for name, key in values.items():
            path, base, tensors = shard_headers[weight_map[key]]
            value = tensors[key]
            lo, hi = value["data_offsets"]
            shape = tuple(value["shape"])
            if shape[0] != experts or (hi - lo) % experts:
                raise ValueError(f"non-row-addressable tensor: {key}")
            rows[name] = {
                "key": key, "path": path, "offset": base + lo,
                "dtype": value["dtype"], "shape": shape,
                "row_bytes": (hi - lo) // experts,
            }
        result[layer] = rows
    return result, layers, experts


def build_layer(root: Path, rows, layer: int, experts: int, target: Path, repo: str, revision: str):
    source = rows[layer]
    tensors = []
    cursor = 0
    for name in RUNTIME_NAMES:
        if name.startswith("gate_up_proj."):
            component = name.rsplit(".", 1)[1]
            parts = (source[f"gate_proj.{component}"], source[f"up_proj.{component}"])
        else:
            parts = (source[name],)
        first = parts[0]
        if any(item["dtype"] != first["dtype"] or item["shape"][2:] != first["shape"][2:] for item in parts):
            raise ValueError(f"cannot fuse {name}")
        shape = (sum(item["shape"][1] for item in parts), *first["shape"][2:])
        nbytes = sum(item["row_bytes"] for item in parts)
        tensors.append({"name": name, "dtype": first["dtype"], "shape": list(shape), "offset": cursor, "nbytes": nbytes})
        cursor += nbytes
    if cursor % HEADER_BYTES:
        raise ValueError("record is not page aligned")
    meta = {
        "format": "omlx-moe-expert-major", "version": 1,
        "variant": "qwen3.6-affine-q4-gate-up-fused-direct-v3",
        "runtime_layout": "fused-switch-glu", "layer": layer,
        "num_experts": experts, "record_bytes": cursor, "data_offset": HEADER_BYTES,
        "source": repo, "source_revision": revision, "tensors": tensors,
    }
    encoded = json.dumps(meta, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > HEADER_BYTES - 8:
        raise ValueError("header overflow")
    page = len(encoded).to_bytes(8, "little") + encoded + bytes(HEADER_BYTES - 8 - len(encoded))
    partial = target.with_suffix(target.suffix + ".partial")
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    source_fds = {}
    digest = hashlib.sha256()
    try:
        _write_all(fd, page)
        for expert in range(experts):
            for name in RUNTIME_NAMES:
                if name.startswith("gate_up_proj."):
                    component = name.rsplit(".", 1)[1]
                    parts = (source[f"gate_proj.{component}"], source[f"up_proj.{component}"])
                else:
                    parts = (source[name],)
                for part in parts:
                    source_fd = source_fds.get(part["path"])
                    if source_fd is None:
                        source_fd = os.open(part["path"], os.O_RDONLY)
                        source_fds[part["path"]] = source_fd
                    value = _read_exact(source_fd, part["row_bytes"], part["offset"] + expert * part["row_bytes"])
                    _write_all(fd, value)
                    digest.update(value)
        os.fsync(fd)
    finally:
        os.close(fd)
        for source_fd in source_fds.values():
            os.close(source_fd)
    os.replace(partial, target)
    return {"file_bytes": target.stat().st_size, "record_bytes": cursor, "sha256_payload": digest.hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows, layers, experts = discover(root)
    manifest = {}
    for layer in range(layers):
        started = time.perf_counter()
        target = output / f"layer-{layer:03d}.moe"
        result = build_layer(root, rows, layer, experts, target, args.source_repo, args.source_revision)
        manifest[str(layer)] = {"file": target.name, "file_bytes": result["file_bytes"], "num_experts": experts, "record_bytes": result["record_bytes"]}
        print(json.dumps({"layer": layer, "seconds": round(time.perf_counter() - started, 3), **result}), flush=True)
    (output / "manifest.json").write_text(json.dumps({
        "format": "omlx-moe-expert-major-set", "version": 1,
        "variant": "qwen3.6-affine-q4-gate-up-fused-direct-v3", "layers": manifest,
    }, indent=2))


if __name__ == "__main__":
    main()
