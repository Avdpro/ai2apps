"""Checkpoint layout validation shared by installers and Service Workers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _indexed_shards_are_complete(root: Path) -> bool:
    """Validate every safetensors index without allowing path traversal."""

    for index_path in root.rglob("*.safetensors.index.json"):
        payload = _read_json_object(index_path)
        weight_map = None if payload is None else payload.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            return False
        for shard in set(weight_map.values()):
            if (
                not isinstance(shard, str)
                or not shard
                or shard.startswith("/")
                or ".." in Path(shard).parts
            ):
                return False
            candidate = index_path.parent / shard
            try:
                candidate.relative_to(root)
            except ValueError:
                return False
            if not candidate.is_file():
                return False
    return True


def _diffusers_checkpoint_is_complete(root: Path) -> bool:
    model_index = _read_json_object(root / "model_index.json")
    if model_index is None or not isinstance(model_index.get("_class_name"), str):
        return False

    component_count = 0
    for name, specification in model_index.items():
        if name.startswith("_") or not isinstance(specification, list):
            continue
        if not specification or specification[0] is None:
            continue
        metadata = specification[2] if len(specification) > 2 else None
        subfolder = metadata.get("subfolder") if isinstance(metadata, dict) else None
        relative = subfolder if isinstance(subfolder, str) and subfolder else name
        component = (root / relative).resolve()
        try:
            component.relative_to(root.resolve())
        except ValueError:
            return False
        if not component.is_dir() or not any(component.iterdir()):
            return False
        component_count += 1

    return (
        component_count > 0
        and _indexed_shards_are_complete(root)
        and any(path.is_file() for path in root.rglob("*.safetensors"))
    )


def checkpoint_is_complete(path: Path) -> bool:
    """Return whether a native or multi-component Diffusers checkpoint is complete."""

    root = path.resolve()
    if (root / "model_index.json").is_file():
        return _diffusers_checkpoint_is_complete(root)

    onnx_files = tuple(root.glob("*.onnx"))
    if onnx_files:
        native_config = next(
            (
                root / name
                for name in ("config.json", "config.yaml", "config.yml")
                if (root / name).is_file()
            ),
            None,
        )
        return native_config is not None and any(path.is_file() for path in onnx_files)

    native_config = next(
        (
            root / name
            for name in ("config.json", "config.yaml", "config.yml")
            if (root / name).is_file()
        ),
        None,
    )
    if native_config is None:
        return False
    return _indexed_shards_are_complete(root) and any(
        path.is_file() for path in root.glob("*.safetensors")
    )
