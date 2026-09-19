#!/usr/bin/env python3
"""Export Qwen3.6/Ornith fused expert records with a compact backbone."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from ssd_checkpoint_io import CHUNK, clone, header, safe_file, sha, subset


PATTERN = re.compile(
    r"^language_model\.model\.layers\.(\d+)\.mlp\.switch_mlp\."
    r"(gate_proj|up_proj|down_proj)\.(weight|scales|biases)$"
)
ALLOWED_VARIANTS = {
    "qwen3.6-affine-q4-gate-up-fused-v2",
    "qwen3.6-affine-q4-gate-up-fused-direct-v3",
}


def _store_header(path: Path) -> dict:
    with path.open("rb") as handle:
        length = int.from_bytes(handle.read(8), "little")
        if not 0 < length <= 4088:
            raise ValueError(f"invalid expert store header: {path}")
        return json.loads(handle.read(length))


def _rewrite_store_identity(path: Path, repo: str, revision: str) -> dict:
    value = _store_header(path)
    value["source"] = repo
    value["source_revision"] = revision
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > 4088:
        raise ValueError(f"expert store header overflow: {path}")
    with path.open("r+b") as handle:
        handle.write(len(encoded).to_bytes(8, "little"))
        handle.write(encoded)
        handle.write(bytes(4088 - len(encoded)))
        handle.flush()
        os.fsync(handle.fileno())
    return value


def _copy_metadata(source: Path, stage: Path) -> None:
    names = (
        ".gitattributes", "LICENSE", "README.md", "assets", "chat_template.jinja",
        "config.json", "configuration.json", "generation_config.json", "preprocessor_config.json",
        "processor_config.json", "tokenizer.json", "tokenizer_config.json",
        "video_preprocessor_config.json", "vocab.json", "VISION_SIDECAR.json",
        "ornith15_vision_bf16.safetensors",
    )
    for name in names:
        src = source / name
        dst = stage / name
        if src.is_dir():
            shutil.copytree(src, dst)
        elif src.is_file():
            if src.stat().st_size >= 16 * 1024 * 1024:
                clone(src, dst)
            else:
                shutil.copyfile(src, dst)


def build(source: Path, store: Path, output: Path, repo: str, revision: str) -> dict:
    if output.exists():
        raise FileExistsError(output)
    stage = output.with_name(output.name + ".partial")
    stage.mkdir(parents=True, exist_ok=False)
    (stage / "experts").mkdir()
    config = json.loads((source / "config.json").read_text())
    text_config = config.get("text_config") or config
    layers = int(text_config["num_hidden_layers"])
    experts = int(text_config["num_experts"])
    index_path = source / "model.safetensors.index.json"
    index = json.loads(index_path.read_text())
    weight_map = index["weight_map"]
    entries = {}
    headers = {}
    for shard in sorted(set(weight_map.values())):
        path = safe_file(source, shard)
        base, values = header(path)
        headers[shard] = (base, values)
        for key, value in values.items():
            if key == "__metadata__":
                continue
            if weight_map.get(key) != shard or key in entries:
                raise ValueError(f"source index mismatch: {key}")
            entries[key] = (path, base, value)
    if set(entries) != set(weight_map):
        raise ValueError("source index is incomplete")
    external = {key for key in entries if PATTERN.fullmatch(key)}
    expected = {
        f"language_model.model.layers.{layer}.mlp.switch_mlp.{projection}.{component}"
        for layer in range(layers)
        for projection in ("gate_proj", "up_proj", "down_proj")
        for component in ("weight", "scales", "biases")
    }
    if external != expected:
        raise ValueError(f"incomplete Qwen routed tensor coverage: found={len(external)} expected={len(expected)}")

    files = {}
    locations = {}
    tensor_hashes = {}
    expert_bytes = 0
    layer_manifest = {}
    variant = None
    for layer in range(layers):
        source_store = store / f"layer-{layer:03d}.moe"
        target = stage / "experts" / source_store.name
        clone(source_store, target)
        meta = _rewrite_store_identity(target, repo, revision)
        if meta.get("variant") not in ALLOWED_VARIANTS:
            raise ValueError(f"unsupported Qwen store variant: {meta.get('variant')}")
        if variant is None:
            variant = meta["variant"]
        if variant != meta["variant"]:
            raise ValueError("mixed Qwen store variants")
        if (
            meta.get("layer") != layer or meta.get("num_experts") != experts
            or meta.get("data_offset") != 4096
            or target.stat().st_size != 4096 + experts * int(meta["record_bytes"])
        ):
            raise ValueError(f"expert store coverage mismatch at layer {layer}")
        tensors = {item["name"]: item for item in meta["tensors"]}
        with target.open("rb") as packed:
            for projection in ("gate_proj", "up_proj", "down_proj"):
                for component in ("weight", "scales", "biases"):
                    key = f"language_model.model.layers.{layer}.mlp.switch_mlp.{projection}.{component}"
                    src, base, value = entries[key]
                    lo, hi = value["data_offsets"]
                    if value["shape"][0] != experts or (hi - lo) % experts:
                        raise ValueError(f"stacked expert tensor differs: {key}")
                    row = (hi - lo) // experts
                    tensor_name = f"{'gate_up_proj' if projection != 'down_proj' else projection}.{component}"
                    layout = tensors[tensor_name]
                    if projection == "down_proj":
                        offset_in_tensor = 0
                        expected_nbytes = row
                        expected_shape = value["shape"][1:]
                    else:
                        gate_key = f"language_model.model.layers.{layer}.mlp.switch_mlp.gate_proj.{component}"
                        gate_value = entries[gate_key][2]
                        gate_row = (gate_value["data_offsets"][1] - gate_value["data_offsets"][0]) // experts
                        offset_in_tensor = gate_row if projection == "up_proj" else 0
                        up_key = f"language_model.model.layers.{layer}.mlp.switch_mlp.up_proj.{component}"
                        up_value = entries[up_key][2]
                        up_row = (up_value["data_offsets"][1] - up_value["data_offsets"][0]) // experts
                        expected_nbytes = gate_row + up_row
                        expected_shape = list(gate_value["shape"][1:])
                        expected_shape[0] += int(up_value["shape"][1])
                    if layout["dtype"] != value["dtype"] or layout["nbytes"] != expected_nbytes or layout["shape"] != list(expected_shape):
                        raise ValueError(f"fused expert layout differs: {key}")
                    digest = hashlib.sha256()
                    with src.open("rb") as src_handle:
                        src_handle.seek(base + lo)
                        for expert in range(experts):
                            packed.seek(4096 + expert * meta["record_bytes"] + layout["offset"] + offset_in_tensor)
                            left = row
                            while left:
                                a = src_handle.read(min(CHUNK, left))
                                b = packed.read(len(a))
                                if not a or a != b:
                                    raise ValueError(f"expert payload differs: {key}")
                                digest.update(a)
                                left -= len(a)
                    tensor_hashes[key] = digest.hexdigest()
                    locations[key] = {
                        "file": f"experts/{target.name}",
                        "offset": 4096 + layout["offset"] + offset_in_tensor,
                        "count": experts, "stride": meta["record_bytes"], "row_bytes": row,
                        "dtype": value["dtype"], "shape": value["shape"],
                    }
        digest = sha(target)
        files[f"experts/{target.name}"] = {"size": target.stat().st_size, "sha256": digest}
        expert_bytes += target.stat().st_size
        layer_manifest[str(layer)] = {
            "file": target.name, "file_bytes": target.stat().st_size,
            "num_experts": experts, "record_bytes": meta["record_bytes"],
        }
        print(json.dumps({"phase": "verified_experts", "layer": layer}), flush=True)
    (stage / "experts" / "manifest.json").write_text(json.dumps({
        "format": "omlx-moe-expert-major-set", "version": 1,
        "variant": variant, "layers": layer_manifest,
    }, indent=2))

    new_map = {}
    backbone_bytes = 0
    for shard, (base, values) in headers.items():
        selected = {key: value for key, value in values.items() if key != "__metadata__" and key not in external}
        if not selected:
            continue
        target = safe_file(stage, shard)
        target.parent.mkdir(parents=True, exist_ok=True)
        size, digests = subset(safe_file(source, shard), target, selected, base)
        tensor_hashes.update(digests)
        backbone_bytes += size
        new_map.update({key: shard for key in selected})
        print(json.dumps({"phase": "verified_backbone", "shard": shard}), flush=True)
    (stage / "model.safetensors.index.json").write_text(json.dumps({
        "metadata": {"total_size": backbone_bytes}, "weight_map": new_map,
    }, indent=2))
    _copy_metadata(source, stage)
    (stage / "external-tensors.json").write_text(json.dumps(locations, sort_keys=True))
    (stage / "source-tensor-sha256.json").write_text(json.dumps(tensor_hashes, sort_keys=True))
    for path in sorted(stage.rglob("*")):
        name = path.relative_to(stage).as_posix()
        if path.is_file() and name not in files:
            files[name] = {"size": path.stat().st_size, "sha256": sha(path)}
    manifest = {
        "schema": "ai2apps.ssd-checkpoint/v1", "family": "qwen3_6",
        "layout": variant, "source": {"repo_id": repo, "revision": revision, "index_sha256": sha(index_path)},
        "index_sha256": sha(stage / "model.safetensors.index.json"),
        "expert_store": "experts", "layers": layers, "experts_per_layer": experts,
        "tensor_count": len(entries), "backbone_payload_bytes": backbone_bytes,
        "expert_file_bytes": expert_bytes, "verification": "all_tensor_payloads_equal",
        "files": files, "builder_sha256": sha(Path(__file__)),
        "io_helper_sha256": sha(Path(__file__).with_name("ssd_checkpoint_io.py")),
    }
    (stage / "ssd-checkpoint.json").write_text(json.dumps(manifest, indent=2))
    stage.rename(output)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expert-store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-revision", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_revision):
        parser.error("source revision must be immutable 40-hex")
    result = build(args.source.resolve(), args.expert_store.resolve(), args.output.resolve(), args.source_repo, args.source_revision)
    print(json.dumps({key: value for key, value in result.items() if key != "files"}, indent=2))


if __name__ == "__main__":
    main()
