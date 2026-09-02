#!/usr/bin/env python3
"""Build an Ornith 1.5 mixed-precision MLX VLM checkpoint.

The community MLX checkpoint contains the Q4 language model but omits the
official vision tower.  This tool combines that checkpoint with the visual
tensors from the official BF16 shard without loading either model into RAM:

* text/tokenizer files are hard-linked (copy fallback),
* ``model.visual.*`` tensors are copied byte-for-byte into an MLX sidecar and
  renamed to ``vision_tower.*``, and
* the official processor and vision config are installed beside the model.

The result intentionally keeps the vision tower in BF16.  mlx-vlm quantizes a
module only when the checkpoint contains a matching ``.scales`` tensor, so a
Q4 language model and BF16 vision tower can coexist without runtime patches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
from pathlib import Path
from typing import Any

import numpy as np

SOURCE_PREFIX = "model.visual."
TARGET_PREFIX = "vision_tower."
# Keep this sidecar in the model root.  mlx-vlm then discovers it through its
# native safetensors glob before Qwen's MTP load_weights wrapper is installed.
# A nested OptiQ sidecar relies on a late load_weights injection that MTP can
# bypass, producing a strict-load error for every vision parameter.
SIDECAR_RELATIVE_PATH = "ornith15_vision_bf16.safetensors"
PROCESSOR_FILES = (
    "processor_config.json",
    "preprocessor_config.json",
    "video_preprocessor_config.json",
)


def _read_header(path: Path) -> tuple[int, dict[str, Any]]:
    with path.open("rb") as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise ValueError(f"Not a safetensors file: {path}")
        (header_length,) = struct.unpack("<Q", raw_length)
        if header_length <= 0 or header_length > 512 * 1024 * 1024:
            raise ValueError(f"Invalid safetensors header length in {path}")
        return 8 + header_length, json.loads(handle.read(header_length))


def _sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def extract_visual_sidecar(source: Path, output: Path) -> dict[str, Any]:
    """Stream visual tensor payloads into an MLX-named safetensors sidecar."""

    source_data_start, source_header = _read_header(source)
    tensors: list[tuple[str, dict[str, Any], int, int, bool]] = []
    output_offset = 0
    output_header: dict[str, Any] = {
        "__metadata__": {
            "format": "mlx",
            "source_prefix": SOURCE_PREFIX,
            "precision": "bfloat16",
        }
    }

    for source_name, tensor in source_header.items():
        if source_name == "__metadata__" or not source_name.startswith(SOURCE_PREFIX):
            continue
        source_start, source_end = (int(value) for value in tensor["data_offsets"])
        byte_count = source_end - source_start
        target_name = TARGET_PREFIX + source_name[len(SOURCE_PREFIX) :]
        target_tensor = {
            key: value for key, value in tensor.items() if key != "data_offsets"
        }
        transpose_patch_embed = source_name.endswith("patch_embed.proj.weight")
        if transpose_patch_embed:
            shape = tuple(int(value) for value in tensor["shape"])
            if len(shape) != 5:
                raise ValueError(
                    f"Expected 5D Qwen patch embedding weight, received {shape}"
                )
            # PyTorch Conv3d: [out, in, temporal, height, width].
            # MLX Conv3d:     [out, temporal, height, width, in].
            target_tensor["shape"] = [shape[0], shape[2], shape[3], shape[4], shape[1]]
        target_tensor["data_offsets"] = [output_offset, output_offset + byte_count]
        output_header[target_name] = target_tensor
        tensors.append(
            (target_name, tensor, source_start, byte_count, transpose_patch_embed)
        )
        output_offset += byte_count

    if not tensors:
        raise ValueError(f"No {SOURCE_PREFIX} tensors found in {source}")

    header_bytes = json.dumps(
        output_header, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    header_bytes += b" " * ((8 - len(header_bytes) % 8) % 8)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    with source.open("rb") as source_handle, temporary.open("wb") as output_handle:
        output_handle.write(struct.pack("<Q", len(header_bytes)))
        output_handle.write(header_bytes)
        for _name, tensor, source_start, byte_count, transpose_patch_embed in tensors:
            source_handle.seek(source_data_start + source_start)
            if transpose_patch_embed:
                raw = source_handle.read(byte_count)
                if len(raw) != byte_count:
                    raise EOFError(f"Truncated tensor payload in {source}")
                dtype = tensor["dtype"]
                if dtype not in {"BF16", "F16"}:
                    raise ValueError(
                        f"Unsupported patch embedding dtype for raw transpose: {dtype}"
                    )
                shape = tuple(int(value) for value in tensor["shape"])
                value = np.frombuffer(raw, dtype=np.uint16).reshape(shape)
                output_handle.write(value.transpose(0, 2, 3, 4, 1).tobytes())
                continue
            remaining = byte_count
            while remaining:
                chunk = source_handle.read(min(8 * 1024 * 1024, remaining))
                if not chunk:
                    raise EOFError(f"Truncated tensor payload in {source}")
                output_handle.write(chunk)
                remaining -= len(chunk)
        output_handle.flush()
        os.fsync(output_handle.fileno())
    temporary.replace(output)

    return {
        "tensor_count": len(tensors),
        "tensor_bytes": output_offset,
        "first_tensor": tensors[0][0],
        "last_tensor": tensors[-1][0],
        "patch_embed_layout": "out,temporal,height,width,in",
    }


def _link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def build_checkpoint(
    text_checkpoint: Path,
    official_metadata: Path,
    official_visual_shard: Path,
    output: Path,
    *,
    source_revision: str | None = None,
) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    text_config = json.loads((text_checkpoint / "config.json").read_text())
    official_config = json.loads((official_metadata / "config.json").read_text())
    vision_config = official_config.get("vision_config")
    if not isinstance(vision_config, dict) or not vision_config:
        raise ValueError("Official config has no populated vision_config")

    excluded = {"config.json", *PROCESSOR_FILES}
    link_modes: dict[str, int] = {}
    for source in sorted(text_checkpoint.iterdir()):
        if not source.is_file() or source.name in excluded:
            continue
        mode = _link_or_copy(source, output / source.name)
        link_modes[mode] = link_modes.get(mode, 0) + 1

    for filename in PROCESSOR_FILES:
        source = official_metadata / filename
        if not source.is_file():
            raise FileNotFoundError(f"Missing official processor file: {source}")
        shutil.copy2(source, output / filename)

    sidecar = output / SIDECAR_RELATIVE_PATH
    visual = extract_visual_sidecar(official_visual_shard, sidecar)

    text_config["vision_config"] = vision_config
    text_config["optiq_vision"] = {
        "sidecar": SIDECAR_RELATIVE_PATH,
        "precision": "bfloat16",
        "source": "ornith-ai/Ornith-1.5-35B-A3B",
        "revision": source_revision,
    }
    (output / "config.json").write_text(
        json.dumps(text_config, ensure_ascii=False, indent=2) + "\n"
    )

    manifest = {
        "format": "ai2apps-ornith15-mlx-vision-v1",
        "language_checkpoint": str(text_checkpoint.resolve()),
        "vision_source": "ornith-ai/Ornith-1.5-35B-A3B",
        "vision_source_revision": source_revision,
        "vision_source_shard": official_visual_shard.name,
        "vision_source_shard_sha256": _sha256(official_visual_shard),
        "vision_sidecar": SIDECAR_RELATIVE_PATH,
        "vision_sidecar_sha256": _sha256(sidecar),
        "vision": visual,
        "file_materialization": link_modes,
    }
    (output / "VISION_SIDECAR.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-checkpoint", type=Path, required=True)
    parser.add_argument("--official-metadata", type=Path, required=True)
    parser.add_argument("--official-visual-shard", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision")
    args = parser.parse_args()
    manifest = build_checkpoint(
        args.text_checkpoint,
        args.official_metadata,
        args.official_visual_shard,
        args.output,
        source_revision=args.source_revision,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
