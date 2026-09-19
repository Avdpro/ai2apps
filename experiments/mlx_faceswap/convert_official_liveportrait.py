#!/usr/bin/env python3
"""Reproducibly convert official LivePortrait PyTorch weights to MLX layouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np

OFFICIAL_REPO = "KlingTeam/LivePortrait"
OFFICIAL_REVISION = "82a4fa6735ca58432b6ce39301b4b9ee066dea47"
CORE_MODELS = {
    "appearance_feature_extractor": {
        "source": "liveportrait/base_models/appearance_feature_extractor.pth",
        "renames": ((r"resblocks_3d\.3dr(\d+)\.", r"resblocks_3d.\1."),),
    },
    "motion_extractor": {
        "source": "liveportrait/base_models/motion_extractor.pth",
        "prefix": "detector.",
    },
    "spade_generator": {
        "source": "liveportrait/base_models/spade_generator.pth",
    },
    "warping_module": {
        "source": "liveportrait/base_models/warping_module.pth",
    },
}
STITCHING_SOURCE = (
    "liveportrait/retargeting_models/stitching_retargeting_module.pth"
)
STITCHING_MODELS = {
    "stitching": "retarget_shoulder",
    "stitching_eye": "retarget_eye",
    "stitching_lip": "retarget_mouth",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path):
    import torch  # Development/build dependency only.  # noqa: PLC0415

    value = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(value, dict) and isinstance(value.get("model"), dict):
        return value["model"]
    if isinstance(value, dict) and isinstance(value.get("state_dict"), dict):
        return value["state_dict"]
    return value


def _numpy(value) -> np.ndarray:
    return value.detach().cpu().float().numpy()


def _fold_spectral_norm(values: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    result = dict(values)
    for name in list(values):
        if not name.endswith(".weight_orig"):
            continue
        prefix = name[: -len(".weight_orig")]
        u_name, v_name = prefix + ".weight_u", prefix + ".weight_v"
        if u_name not in values or v_name not in values:
            continue
        weight, u, v = values[name], values[u_name], values[v_name]
        sigma = float(u @ weight.reshape(weight.shape[0], -1) @ v)
        if abs(sigma) < 1e-12:
            raise ValueError(f"invalid spectral norm for {prefix}")
        for old_name in (name, u_name, v_name):
            result.pop(old_name, None)
        result[prefix + ".weight"] = weight / sigma
    return result


def _convert_core(
    state, *, prefix: str = "", renames: tuple[tuple[str, str], ...] = ()
) -> dict[str, np.ndarray]:
    values = _fold_spectral_norm({name: _numpy(value) for name, value in state.items()})
    compiled = [(re.compile(pattern), replacement) for pattern, replacement in renames]
    result = {}
    for name, value in values.items():
        if name.endswith(".num_batches_tracked"):
            continue
        output_name = name.removeprefix(prefix)
        for pattern, replacement in compiled:
            output_name = pattern.sub(replacement, output_name)
        if name.endswith(".weight") and value.ndim == 4:
            value = value.transpose(0, 2, 3, 1)
        elif name.endswith(".weight") and value.ndim == 5:
            value = value.transpose(0, 2, 3, 4, 1)
        result[output_name] = np.ascontiguousarray(value, dtype=np.float32)
    return result


def _layer_index(name: str) -> int:
    match = re.search(r"(?:^|\.)(\d+)\.weight$", name)
    if match is None:
        raise ValueError(f"cannot determine stitching layer index: {name}")
    return int(match.group(1))


def _convert_stitching(state: dict, module: str) -> dict[str, np.ndarray]:
    layers = state[module]
    weights = sorted(
        (name for name in layers if name.endswith(".weight")), key=_layer_index
    )
    result = {}
    for index, weight_name in enumerate(weights):
        bias_name = weight_name.removesuffix(".weight") + ".bias"
        result[f"layers.{index}.weight"] = np.ascontiguousarray(
            _numpy(layers[weight_name]), dtype=np.float32
        )
        result[f"layers.{index}.bias"] = np.ascontiguousarray(
            _numpy(layers[bias_name]), dtype=np.float32
        )
    return result


def _canonical_tensor_digest(values: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in sorted(values):
        value = values[name]
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(str(value.dtype).encode("ascii") + b"\0")
        digest.update(json.dumps(value.shape).encode("ascii") + b"\0")
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def _write(output: Path, values: dict[str, np.ndarray]) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(output, **values)
    return {
        "file": output.name,
        "sha256": _sha256(output),
        "tensor_content_sha256": _canonical_tensor_digest(values),
        "tensors": len(values),
        "bytes": output.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("official_snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--revision", default=OFFICIAL_REVISION)
    args = parser.parse_args()
    if args.revision != OFFICIAL_REVISION:
        raise ValueError("unreviewed LivePortrait revision")

    sources = {}
    outputs = {}
    for name, spec in CORE_MODELS.items():
        source = args.official_snapshot / str(spec["source"])
        sources[str(spec["source"])] = {
            "sha256": _sha256(source),
            "bytes": source.stat().st_size,
        }
        converted = _convert_core(
            _load(source),
            prefix=str(spec.get("prefix", "")),
            renames=tuple(spec.get("renames", ())),
        )
        outputs[name] = _write(args.output / f"{name}.npz", converted)

    stitching_source = args.official_snapshot / STITCHING_SOURCE
    stitching = _load(stitching_source)
    sources[STITCHING_SOURCE] = {
        "sha256": _sha256(stitching_source),
        "bytes": stitching_source.stat().st_size,
    }
    for name, module in STITCHING_MODELS.items():
        outputs[name] = _write(
            args.output / f"{name}.npz", _convert_stitching(stitching, module)
        )

    receipt = {
        "schema": "ai2apps.mlx-liveportrait-conversion/v1",
        "source": {"repo_id": OFFICIAL_REPO, "revision": args.revision},
        "sources": sources,
        "outputs": outputs,
    }
    receipt_path = args.output / "conversion-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
