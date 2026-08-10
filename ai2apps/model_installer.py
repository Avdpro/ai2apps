"""Verified Cache-MoE model catalog and installation pipeline."""

from __future__ import annotations

import asyncio
import enum
import hashlib
import json
import os
import re
import struct
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_METADATA_DIR = ".ai2apps"
_LEGACY_METADATA_DIR = ".dynamoe"
_MODEL_MANIFEST = "ai2apps-model.json"
_LEGACY_MODEL_MANIFEST = "dynamoe-model.json"


def _metadata_dir(source_dir: Path) -> Path:
    current = source_dir / _METADATA_DIR
    legacy = source_dir / _LEGACY_METADATA_DIR
    if current.exists() or not legacy.exists():
        return current
    return legacy


def _source_record(source_dir: Path) -> tuple[Path, dict[str, Any]]:
    for directory in (_METADATA_DIR, _LEGACY_METADATA_DIR):
        path = source_dir / directory / "source.json"
        try:
            value = json.loads(path.read_text())
        except (OSError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            return path, value
    return source_dir / _METADATA_DIR / "source.json", {}

CATALOG = (
    {
        "id": "deepseek-v4-flash",
        "name": "DeepSeek V4 Flash",
        "description": "DeepSeek V4 Flash with the dedicated AI2Apps Flesh engine.",
        "family": "deepseek_v4",
        "engine": {
            "id": "deepseek-v4-flesh",
            "name": "DeepSeek V4 Flesh",
            "version": 1,
            "scope_asset": "engines/deepseek_v4_flash/scope-profile.json",
            "scope_pack": "engines/deepseek_v4_flash/scope-pack.json",
        },
        "sources": (
            {
                "id": "huggingface",
                "label": "HuggingFace",
                "repo_id": "deepseek-ai/DeepSeek-V4-Flash",
                "revision": "60d8d70770c6776ff598c94bb586a859a38244f1",
            },
        ),
        "scope_name": "general",
        "conversion": {
            "format": "omlx-moe-expert-major-set",
            "version": 1,
            "variant": "deepseek-v4-expert-major-v1",
        },
        "memory_tiers": (
            {"id": "lean", "label": "Lean", "experts": 20, "estimated_gb": 33},
            {"id": "compact", "label": "Compact", "experts": 40, "estimated_gb": 43},
            {"id": "optimal", "label": "Optimal", "experts": 60, "estimated_gb": 54},
        ),
    },
    {
        "id": "deepseek-v4-flash-2bit",
        "name": "DeepSeek V4 Flash 2-bit",
        "description": "MLX 2-bit DQ checkpoint with the dedicated AI2Apps Flesh engine.",
        "family": "deepseek_v4",
        "engine": {
            "id": "deepseek-v4-flesh",
            "name": "DeepSeek V4 Flesh",
            "version": 1,
            "scope_asset": "engines/deepseek_v4_flash/scope-profile.json",
            "scope_pack": "engines/deepseek_v4_flash/scope-pack.json",
        },
        "sources": (
            {
                "id": "huggingface",
                "label": "HuggingFace",
                "repo_id": "mlx-community/DeepSeek-V4-Flash-2bit-DQ",
                "revision": "722bf559b7de93575b2320973cf2002e05bfe6c9",
            },
        ),
        "scope_name": "general",
        "conversion": {
            "format": "omlx-moe-expert-major-set",
            "version": 1,
            "variant": "deepseek-v4-expert-major-v1",
        },
        "memory_tiers": (
            {"id": "lean", "label": "Lean", "experts": 20, "estimated_gb": 17},
            {"id": "compact", "label": "Compact", "experts": 40, "estimated_gb": 24},
            {"id": "optimal", "label": "Optimal", "experts": 60, "estimated_gb": 30},
        ),
    },
    {
        "id": "qwen3.6-35b-a3b-4bit",
        "name": "Qwen3.6 35B A3B 4-bit",
        "description": "MLX 4-bit checkpoint with the dedicated AI2Apps Tiered engine.",
        "family": "qwen3_6",
        "engine": {
            "id": "qwen3.6-tiered",
            "name": "Qwen3.6 Tiered",
            "version": 1,
            "scope_asset": "engines/qwen3_6_35b_a3b/scope-profile.json",
            "scope_pack": "engines/qwen3_6_35b_a3b/scope-pack.json",
            "scope_env": "OMLX_QWEN36_SCOPE_PROFILE",
        },
        "sources": (
            {
                "id": "huggingface",
                "label": "HuggingFace",
                "repo_id": "mlx-community/Qwen3.6-35B-A3B-4bit",
                "revision": "38740b847e4cb78f352aba30aa41c76e08e6eb46",
            },
        ),
        "scope_name": "general",
        "conversion": {
            "format": "omlx-moe-expert-major-set",
            "version": 1,
            "variant": "qwen3.6-affine-q4-gate-up-fused-v2",
        },
        "arena_tail_slots": 24,
        "memory_tiers": (
            {"id": "lean", "label": "Lean", "experts": 80, "estimated_gb": 9},
            {"id": "compact", "label": "Compact", "experts": 96, "estimated_gb": 10},
            {"id": "optimal", "label": "Optimal", "experts": 120, "estimated_gb": 12},
        ),
    },
)

_EXPERT_RE = re.compile(
    r"^layers\.(?P<layer>\d+)\.ffn\.experts\.(?P<expert>\d+)\."
    r"(?P<projection>w[123])\.(?P<part>weight|scale)$"
)
_STACKED_EXPERT_RE = re.compile(
    r"^(?:model\.)?layers\.(?P<layer>\d+)\.ffn\.switch_mlp\."
    r"(?P<projection>gate_proj|down_proj|up_proj)\."
    r"(?P<part>weight|scales|biases)$"
)
_QWEN36_STACKED_EXPERT_RE = re.compile(
    r"^(?:language_model\.)?model\.layers\.(?P<layer>\d+)\.mlp\.switch_mlp\."
    r"(?P<projection>gate_proj|down_proj|up_proj)\."
    r"(?P<part>weight|scales|biases)$"
)
_PARTS = tuple(
    (projection, part)
    for projection in ("w1", "w2", "w3")
    for part in ("weight", "scale")
)
_PROJECTIONS = {"w1": "gate_proj", "w2": "down_proj", "w3": "up_proj"}


class InstallStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INDEXING = "indexing"
    CONVERTING = "converting"
    CONFIGURING = "configuring"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class InstallTask:
    task_id: str
    model_id: str
    weight_source: str
    repo_id: str
    revision: str
    memory_tier: str = "auto"
    status: InstallStatus = InstallStatus.PENDING
    phase: str = "Queued"
    progress: float = 0.0
    detail: str = ""
    error: str = ""
    child_task_id: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model_id": self.model_id,
            "weight_source": self.weight_source,
            "repo_id": self.repo_id,
            "revision": self.revision,
            "memory_tier": self.memory_tier,
            "status": self.status.value,
            "phase": self.phase,
            "progress": round(self.progress, 1),
            "detail": self.detail,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "cache_hit": self.cache_hit,
        }


def checkpoint_is_complete(path: Path) -> bool:
    """Return whether a local checkpoint view contains all indexed shards."""

    if not (path / "config.json").is_file():
        return False
    index_path = path / "model.safetensors.index.json"
    if index_path.is_file():
        try:
            weight_map = json.loads(index_path.read_text())["weight_map"]
        except (KeyError, OSError, TypeError, json.JSONDecodeError):
            return False
        return bool(weight_map) and all(
            (path / shard).is_file() for shard in set(weight_map.values())
        )
    return any(path.glob("*.safetensors"))


def link_cached_snapshot(snapshot: Path, destination: Path) -> None:
    """Create a no-copy model view backed by an HF snapshot/blob cache."""

    destination.mkdir(parents=True, exist_ok=True)
    for source in snapshot.rglob("*"):
        relative = source.relative_to(snapshot)
        target = destination / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            continue
        target.symlink_to(source.resolve())


def _read_safetensors_header(path: Path) -> tuple[int, dict[str, dict[str, Any]]]:
    with path.open("rb") as handle:
        raw = handle.read(8)
        if len(raw) != 8:
            raise ValueError(f"invalid safetensors header: {path}")
        (length,) = struct.unpack("<Q", raw)
        if length <= 0 or length > 512 * 1024 * 1024:
            raise ValueError(f"invalid safetensors header length: {path}")
        header = json.loads(handle.read(length))
    header.pop("__metadata__", None)
    return 8 + length, header


def build_deepseek_offset_manifest(source_dir: Path, output_dir: Path) -> Path:
    """Build the direct-read index needed by the expert-major converter."""

    config = json.loads((source_dir / "config.json").read_text())
    if config.get("model_type") != "deepseek_v4":
        raise ValueError("AI2Apps recipe expects a deepseek_v4 checkpoint")
    num_layers = int(config["num_hidden_layers"])
    num_experts = int(config["n_routed_experts"])
    first_routed_layer = int(config.get("first_k_dense_replace", 0))
    index = json.loads(
        (source_dir / "model.safetensors.index.json").read_text()
    )["weight_map"]

    tensors: dict[str, dict[str, Any]] = {}
    for shard_name in sorted(set(index.values())):
        shard = source_dir / shard_name
        if not shard.is_file():
            raise FileNotFoundError(f"missing checkpoint shard: {shard.name}")
        data_start, header = _read_safetensors_header(shard)
        for name, spec in header.items():
            if index.get(name) != shard_name:
                raise ValueError(f"checkpoint index/header disagree for {name}")
            start, end = (int(value) for value in spec["data_offsets"])
            tensors[name] = {
                "shard": shard,
                "absolute_offset": data_start + start,
                "nbytes": end - start,
                "dtype": spec["dtype"],
                "shape": tuple(int(value) for value in spec["shape"]),
            }

    found: dict[tuple[int, int], dict[tuple[str, str], tuple[str, dict]]] = {}
    stacked: dict[int, dict[tuple[str, str], tuple[str, dict]]] = {}
    for name, tensor in tensors.items():
        match = _EXPERT_RE.match(name)
        if match is not None:
            key = (int(match["layer"]), int(match["expert"]))
            part = (match["projection"], match["part"])
            found.setdefault(key, {})[part] = (name, tensor)
            continue
        match = _STACKED_EXPERT_RE.match(name)
        if match is not None:
            layer = int(match["layer"])
            part = (match["projection"], match["part"])
            stacked.setdefault(layer, {})[part] = (name, tensor)

    expected = {
        (layer, expert)
        for layer in range(first_routed_layer, num_layers)
        for expert in range(num_experts)
    }
    raw_layout = bool(found)
    stacked_layout = bool(stacked)
    if raw_layout == stacked_layout:
        raise ValueError(
            "checkpoint must contain either per-expert or stacked routed tensors"
        )
    if raw_layout and set(found) != expected:
        missing = sorted(expected - set(found))[:5]
        raise ValueError(f"checkpoint routed expert set is incomplete: {missing}")
    if stacked_layout and set(stacked) != set(range(first_routed_layer, num_layers)):
        missing = sorted(set(range(first_routed_layer, num_layers)) - set(stacked))[:5]
        raise ValueError(f"checkpoint routed expert layers are incomplete: {missing}")

    layers: dict[str, Any] = {}
    for layer in range(first_routed_layer, num_layers):
        records = []
        layer_shards: set[Path] = set()
        expert_bytes: int | None = None
        for expert in range(num_experts):
            if raw_layout:
                parts = found[(layer, expert)]
                expected_parts = set(_PARTS)
            else:
                parts = stacked[layer]
                expected_parts = {
                    (projection, part)
                    for projection in ("gate_proj", "down_proj", "up_proj")
                    for part in ("weight", "scales", "biases")
                }
            if set(parts) != expected_parts:
                raise ValueError(f"layer {layer} expert {expert} is incomplete")
            record = []
            for projection, part in sorted(expected_parts):
                source_name, tensor = parts[(projection, part)]
                shard = tensor["shard"]
                layer_shards.add(shard)
                shape = tensor["shape"]
                dtype = tensor["dtype"]
                absolute_offset = tensor["absolute_offset"]
                nbytes = tensor["nbytes"]
                if stacked_layout:
                    if not shape or shape[0] != num_experts or nbytes % num_experts:
                        raise ValueError(f"invalid stacked expert tensor {source_name}")
                    if dtype not in {"U32", "BF16", "F16"}:
                        raise ValueError(
                            f"unsupported affine expert tensor {source_name}: {dtype}"
                        )
                    nbytes //= num_experts
                    absolute_offset += expert * nbytes
                    shape = shape[1:]
                    runtime_dtype = dtype
                    runtime_shape = shape
                    runtime_part = part
                elif part == "weight":
                    if dtype != "I8" or shape[-1] % 4:
                        raise ValueError(f"unsupported FP4 tensor {source_name}")
                    runtime_dtype = "U32"
                    runtime_shape = (*shape[:-1], shape[-1] // 4)
                    runtime_part = "weight"
                else:
                    if dtype != "F8_E8M0":
                        raise ValueError(f"unsupported FP4 scale {source_name}")
                    runtime_dtype = "U8"
                    runtime_shape = shape
                    runtime_part = "scales"
                record.append(
                    {
                        "name": f"{_PROJECTIONS.get(projection, projection)}.{runtime_part}",
                        "source_tensor": source_name,
                        "file": os.path.relpath(shard, output_dir),
                        "absolute_offset": absolute_offset,
                        "nbytes": nbytes,
                        "dtype": runtime_dtype,
                        "shape": list(runtime_shape),
                    }
                )
            size = sum(item["nbytes"] for item in record)
            if expert_bytes is None:
                expert_bytes = size
            elif size != expert_bytes:
                raise ValueError("routed experts do not have a uniform record size")
            records.append({"expert_bytes": size, "tensors": record})
        assert layer_shards and expert_bytes is not None
        layers[str(layer)] = {
            "storage": (
                "direct-safetensors"
                if len(layer_shards) == 1
                else "direct-safetensors-multifile"
            ),
            "expert_count": num_experts,
            "expert_bytes": expert_bytes,
            "experts": records,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "offset-manifest.json"
    partial = destination.with_suffix(".json.partial")
    partial.write_text(
        json.dumps(
            {
                "version": 2,
                "format": "dmoe-offset-manifest",
                "source": {
                    "model": source_dir.name,
                    "directory": str(source_dir),
                    "model_type": "deepseek_v4",
                },
                "num_layers": num_layers,
                "num_experts": num_experts,
                "first_routed_layer": first_routed_layer,
                "layers": layers,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    partial.replace(destination)
    return destination


def build_qwen36_offset_manifest(source_dir: Path, output_dir: Path) -> Path:
    """Index a Qwen3.6 affine-Q4 checkpoint without copying its shards."""

    config = json.loads((source_dir / "config.json").read_text())
    if config.get("model_type") != "qwen3_5_moe":
        raise ValueError("AI2Apps Qwen recipe expects a qwen3_5_moe checkpoint")
    text_config = config.get("text_config") or {}
    num_layers = int(text_config["num_hidden_layers"])
    num_experts = int(text_config["num_experts"])
    quantization = config.get("quantization") or config.get("quantization_config") or {}
    if int(quantization.get("bits", 0)) != 4 or quantization.get("mode") != "affine":
        raise ValueError("AI2Apps Qwen recipe requires an affine 4-bit checkpoint")

    index = json.loads(
        (source_dir / "model.safetensors.index.json").read_text()
    )["weight_map"]
    tensors: dict[str, dict[str, Any]] = {}
    for shard_name in sorted(set(index.values())):
        shard = source_dir / shard_name
        if not shard.is_file():
            raise FileNotFoundError(f"missing checkpoint shard: {shard.name}")
        data_start, header = _read_safetensors_header(shard)
        for name, spec in header.items():
            if index.get(name) != shard_name:
                raise ValueError(f"checkpoint index/header disagree for {name}")
            start, end = (int(value) for value in spec["data_offsets"])
            tensors[name] = {
                "shard": shard,
                "absolute_offset": data_start + start,
                "nbytes": end - start,
                "dtype": spec["dtype"],
                "shape": tuple(int(value) for value in spec["shape"]),
            }

    stacked: dict[int, dict[tuple[str, str], tuple[str, dict[str, Any]]]] = {}
    for name, tensor in tensors.items():
        match = _QWEN36_STACKED_EXPERT_RE.match(name)
        if match is None:
            continue
        layer = int(match["layer"])
        part = (match["projection"], match["part"])
        stacked.setdefault(layer, {})[part] = (name, tensor)

    expected_layers = set(range(num_layers))
    if set(stacked) != expected_layers:
        missing = sorted(expected_layers - set(stacked))[:5]
        raise ValueError(f"Qwen routed expert layers are incomplete: {missing}")
    expected_parts = {
        (projection, part)
        for projection in ("gate_proj", "down_proj", "up_proj")
        for part in ("weight", "scales", "biases")
    }

    layers: dict[str, Any] = {}
    for layer in range(num_layers):
        parts = stacked[layer]
        if set(parts) != expected_parts:
            raise ValueError(f"Qwen layer {layer} routed tensors are incomplete")
        records = []
        expert_bytes: int | None = None
        for expert in range(num_experts):
            record = []
            for projection, part in sorted(expected_parts):
                source_name, tensor = parts[(projection, part)]
                shape = tensor["shape"]
                nbytes = int(tensor["nbytes"])
                dtype = tensor["dtype"]
                if (
                    dtype not in {"U32", "BF16"}
                    or not shape
                    or shape[0] != num_experts
                    or nbytes % num_experts
                ):
                    raise ValueError(f"invalid Qwen expert tensor {source_name}")
                expert_nbytes = nbytes // num_experts
                record.append(
                    {
                        "name": f"{projection}.{part}",
                        "source_tensor": source_name,
                        "file": os.path.relpath(tensor["shard"], output_dir),
                        "absolute_offset": (
                            int(tensor["absolute_offset"]) + expert * expert_nbytes
                        ),
                        "nbytes": expert_nbytes,
                        "dtype": dtype,
                        "shape": list(shape[1:]),
                    }
                )
            size = sum(item["nbytes"] for item in record)
            if expert_bytes is None:
                expert_bytes = size
            elif size != expert_bytes:
                raise ValueError("Qwen routed experts do not have a uniform size")
            records.append({"expert_bytes": size, "tensors": record})
        assert expert_bytes is not None
        if expert_bytes % 4096:
            raise ValueError("Qwen expert records must be page aligned")
        layers[str(layer)] = {
            "storage": "direct-safetensors-multifile",
            "expert_count": num_experts,
            "expert_bytes": expert_bytes,
            "experts": records,
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "offset-manifest.json"
    partial = destination.with_suffix(".json.partial")
    partial.write_text(
        json.dumps(
            {
                "version": 2,
                "format": "dmoe-offset-manifest",
                "source": {
                    "model": source_dir.name,
                    "directory": str(source_dir),
                    "model_type": "qwen3_5_moe",
                },
                "num_layers": num_layers,
                "num_experts": num_experts,
                "first_routed_layer": 0,
                "layers": layers,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    partial.replace(destination)
    return destination


class AI2AppsInstaller:
    def __init__(self, hf_downloader: Any):
        self.hf_downloader = hf_downloader
        self.tasks: dict[str, InstallTask] = {}
        self._runners: dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()
        self._sem = asyncio.Semaphore(1)

    @staticmethod
    def _scope_pack_metadata(
        recipe: dict[str, Any], profile: Path
    ) -> dict[str, Any] | None:
        """Validate and return metadata for a packaged Scope Pack.

        Development overrides remain supported for research, but release assets
        are always checksummed before they are exposed through the catalog.
        """

        relative = recipe["engine"].get("scope_pack")
        if not relative:
            return None
        manifest_path = Path(__file__).parent / relative
        packaged_profile = (
            Path(__file__).parent / recipe["engine"]["scope_asset"]
        ).resolve()
        if profile.resolve() != packaged_profile:
            return None
        if not manifest_path.is_file():
            raise RuntimeError(f"packaged Scope Pack manifest missing: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid Scope Pack manifest: {manifest_path}") from exc
        if manifest.get("format") not in {
            "ai2apps-scope-pack",
            "dynamoe-scope-pack",
        } or manifest.get("version") != 1:
            raise RuntimeError(f"unsupported Scope Pack manifest: {manifest_path}")
        if manifest.get("family") != recipe["family"]:
            raise RuntimeError(
                f"Scope Pack family mismatch for {recipe['id']}: "
                f"{manifest.get('family')!r}"
            )
        if manifest.get("engine") != recipe["engine"]["id"]:
            raise RuntimeError(f"Scope Pack engine mismatch for {recipe['id']}")
        if manifest.get("profile", {}).get("file") != profile.name:
            raise RuntimeError(
                f"Scope Pack profile filename mismatch for {recipe['id']}"
            )
        expected = str(manifest.get("profile", {}).get("sha256", "")).lower()
        actual = hashlib.sha256(profile.read_bytes()).hexdigest()
        if not expected or actual != expected:
            raise RuntimeError(
                f"Scope Pack checksum mismatch for {recipe['id']}: "
                f"expected {expected or '<missing>'}, got {actual}"
            )
        compatible = manifest.get("compatibility", {}).get("model_ids", [])
        if recipe["id"] not in compatible:
            raise RuntimeError(
                f"Scope Pack does not declare support for {recipe['id']}"
            )
        source_revisions = manifest.get("compatibility", {}).get(
            "source_revisions", {}
        )
        expected_revision = recipe["sources"][0]["revision"]
        if source_revisions.get(recipe["id"]) != expected_revision:
            raise RuntimeError(
                f"Scope Pack checkpoint revision mismatch for {recipe['id']}"
            )
        return manifest

    @staticmethod
    def _scope_profile(recipe: dict[str, Any]) -> Path | None:
        packaged = Path(__file__).parent / recipe["engine"]["scope_asset"]
        if packaged.is_file():
            profile = packaged.resolve()
            AI2AppsInstaller._scope_pack_metadata(recipe, profile)
            return profile
        # Development compatibility only. Release builds ship the profile in
        # the engine package above; research artifacts remain external here.
        env_name = recipe["engine"].get(
            "scope_env", "OMLX_DEEPSEEK_V4_SCOPE_PROFILE"
        )
        external = os.environ.get(env_name, "").strip()
        if external and Path(external).expanduser().is_file():
            return Path(external).expanduser().resolve()
        return None

    @classmethod
    def catalog(cls) -> list[dict[str, Any]]:
        result = []
        for recipe in CATALOG:
            profile = cls._scope_profile(recipe)
            if profile is None:
                # A catalog entry is installable by definition. Do not expose
                # half-supported models whose dedicated engine assets are absent.
                continue
            item = {key: value for key, value in recipe.items()}
            item["sources"] = list(item["sources"])
            item["memory_tiers"] = list(item["memory_tiers"])
            item["engine"] = dict(item["engine"])
            item["engine_ready"] = True
            pack = cls._scope_pack_metadata(recipe, profile)
            if pack is not None:
                item["scope_pack"] = {
                    "id": pack["id"],
                    "version": pack["pack_version"],
                    "sha256": pack["profile"]["sha256"],
                }
            result.append(item)
        return result

    def _recipe(self, model_id: str) -> dict[str, Any]:
        for recipe in CATALOG:
            if recipe["id"] == model_id:
                return recipe
        raise ValueError(f"unsupported AI2Apps model: {model_id}")

    @staticmethod
    def _prepare_cached_checkpoint(
        repo_id: str,
        revision: str,
        token: str,
        destination: Path,
    ) -> bool:
        source_record, recorded = _source_record(destination)
        expected_source = {
            "version": 1,
            "repo_id": repo_id,
            "revision": revision,
        }
        if (
            checkpoint_is_complete(destination)
            and recorded.get("format")
            in {"ai2apps-hf-source", "dynamoe-hf-source"}
            and all(recorded.get(key) == value for key, value in expected_source.items())
        ):
            return True
        try:
            from huggingface_hub import snapshot_download

            snapshot = Path(
                snapshot_download(
                    repo_id=repo_id,
                    revision=revision,
                    token=token or None,
                    local_files_only=True,
                )
            )
        except Exception:
            return False
        if snapshot.name != revision or not checkpoint_is_complete(snapshot):
            return False
        # An unrecorded complete destination may belong to another revision.
        # Let snapshot_download reconcile it instead of mixing shard sets.
        if checkpoint_is_complete(destination):
            return False
        link_cached_snapshot(snapshot, destination)
        if not checkpoint_is_complete(destination):
            return False
        source_record = destination / _METADATA_DIR / "source.json"
        source_record.parent.mkdir(parents=True, exist_ok=True)
        partial = source_record.with_suffix(".json.partial")
        partial.write_text(
            json.dumps(
                {
                    "format": "ai2apps-hf-source",
                    "version": 1,
                    "repo_id": repo_id,
                    "revision": revision,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        partial.replace(source_record)
        return True

    @staticmethod
    def _write_source_record(task: InstallTask, source_dir: Path) -> None:
        path = source_dir / _METADATA_DIR / "source.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".json.partial")
        partial.write_text(
            json.dumps(
                {
                    "format": "ai2apps-hf-source",
                    "version": 1,
                    "repo_id": task.repo_id,
                    "revision": task.revision,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        partial.replace(path)

    async def start(
        self,
        model_id: str,
        weight_source: str,
        memory_tier: str,
        token: str,
    ) -> InstallTask:
        recipe = self._recipe(model_id)
        source = next(
            (item for item in recipe["sources"] if item["id"] == weight_source),
            None,
        )
        if source is None:
            raise ValueError(f"unsupported weight source: {weight_source}")
        if memory_tier not in {"auto", "lean", "compact", "optimal"}:
            raise ValueError(f"unsupported memory tier: {memory_tier}")
        scope_profile = self._scope_profile(recipe)
        if scope_profile is None:
            raise ValueError(
                "The dedicated AI2Apps engine package is incomplete; reinstall AI2Apps"
            )
        task = InstallTask(
            task_id=str(uuid.uuid4()),
            model_id=model_id,
            weight_source=weight_source,
            repo_id=source["repo_id"],
            revision=source["revision"],
            memory_tier=memory_tier,
        )
        self.tasks[task.task_id] = task
        self._runners[task.task_id] = asyncio.create_task(
            self._run(task, recipe, token, scope_profile)
        )
        return task

    async def _run(
        self,
        task: InstallTask,
        recipe: dict,
        token: str,
        scope_profile: Path,
    ) -> None:
        try:
            async with self._sem:
                from omlx.cache.moe_expert_store import (
                    ExpertMajorStore,
                    create_expert_major_store,
                )

                task.status = InstallStatus.DOWNLOADING
                source_dir = self.hf_downloader.model_dir / task.repo_id
                task.phase = "Checking local HuggingFace cache"
                task.cache_hit = await asyncio.to_thread(
                    self._prepare_cached_checkpoint,
                    task.repo_id,
                    task.revision,
                    token,
                    source_dir,
                )
                if task.cache_hit:
                    task.progress = 55.0
                    task.detail = "Reused local checkpoint without downloading"
                else:
                    task.phase = "Downloading checkpoint"
                    child = await self.hf_downloader.start_download(
                        task.repo_id,
                        token,
                        revision=task.revision,
                        notify_complete=False,
                        cache_mode=True,
                    )
                    task.child_task_id = child.task_id
                    while child.status.value in {"pending", "downloading"}:
                        if task.task_id in self._cancelled:
                            await self.hf_downloader.cancel_download(child.task_id)
                            return
                        task.progress = child.progress * 0.55
                        task.detail = (
                            f"{child.downloaded_size} / {child.total_size} bytes"
                        )
                        await asyncio.sleep(0.5)
                    if child.status.value != "completed":
                        raise RuntimeError(
                            child.error or f"download {child.status.value}"
                        )
                    self._write_source_record(task, source_dir)

                work_dir = _metadata_dir(source_dir)
                task.status = InstallStatus.INDEXING
                task.phase = "Indexing checkpoint"
                task.progress = 56.0
                config = json.loads((source_dir / "config.json").read_text())
                is_qwen = recipe["family"] == "qwen3_6"
                if is_qwen:
                    offset_manifest = await asyncio.to_thread(
                        build_qwen36_offset_manifest,
                        source_dir,
                        work_dir / "offsets-qwen36",
                    )
                    text_config = config.get("text_config") or {}
                    num_layers = int(text_config["num_hidden_layers"])
                    routed_layers = list(range(num_layers))
                    split_store_dir = work_dir / "expert-store-split"
                    store_dir = work_dir / "expert-store-fused"
                else:
                    offset_manifest = await asyncio.to_thread(
                        build_deepseek_offset_manifest,
                        source_dir,
                        work_dir / "offsets",
                    )
                    num_layers = int(config["num_hidden_layers"])
                    first_routed_layer = int(
                        config.get("first_k_dense_replace", 0)
                    )
                    routed_layers = list(range(first_routed_layer, num_layers))
                    split_store_dir = None
                    store_dir = work_dir / "expert-store"
                conversion_identity = {
                    "format": "ai2apps-conversion-state",
                    "version": 1,
                    "model_id": task.model_id,
                    "repo_id": task.repo_id,
                    "revision": task.revision,
                    "conversion": recipe["conversion"],
                }
                conversion_state_path = work_dir / "conversion.json"
                try:
                    previous_conversion = json.loads(
                        conversion_state_path.read_text()
                    )
                except (OSError, TypeError, json.JSONDecodeError):
                    previous_conversion = {}
                if previous_conversion.get("format") == "dynamoe-conversion-state":
                    previous_conversion["format"] = "ai2apps-conversion-state"
                same_conversion = all(
                    previous_conversion.get(key) == value
                    for key, value in conversion_identity.items()
                )
                legacy_complete = previous_conversion == conversion_identity
                completed_layers = (
                    set(routed_layers)
                    if legacy_complete
                    else {
                        int(layer)
                        for layer in previous_conversion.get(
                            "completed_layers", []
                        )
                    }
                    if same_conversion
                    else set()
                )
                split_completed_layers = (
                    set(routed_layers)
                    if legacy_complete and is_qwen
                    else {
                        int(layer)
                        for layer in previous_conversion.get(
                            "split_completed_layers", []
                        )
                    }
                    if same_conversion
                    else set()
                )

                def write_conversion_state() -> None:
                    state = {
                        **conversion_identity,
                        "completed_layers": sorted(completed_layers),
                        "split_completed_layers": sorted(
                            split_completed_layers
                        ),
                    }
                    partial = conversion_state_path.with_suffix(
                        ".json.partial"
                    )
                    partial.write_text(
                        json.dumps(state, indent=2, sort_keys=True) + "\n"
                    )
                    partial.replace(conversion_state_path)

                # Persist the conversion identity before producing any layer.
                # A cancellation can then resume only layers committed below;
                # stale files from another revision/variant are never reused.
                write_conversion_state()
                task.status = InstallStatus.CONVERTING
                task.phase = "Converting experts"
                for index, layer in enumerate(routed_layers):
                    if task.task_id in self._cancelled:
                        task.status = InstallStatus.CANCELLED
                        task.phase = "Cancelled"
                        return
                    output = store_dir / f"layer-{layer:03d}.moe"
                    valid = False
                    if layer in completed_layers and output.is_file():
                        try:
                            with ExpertMajorStore(output) as existing:
                                names = {item.name for item in existing.tensors}
                                valid = existing.layer == layer and (
                                    "gate_up_proj.weight" in names
                                    if is_qwen
                                    else True
                                )
                        except Exception:
                            output.unlink(missing_ok=True)
                    if not valid:
                        completed_layers.discard(layer)
                    if not valid:
                        if is_qwen:
                            from omlx.patches.qwen3_6_flesh.checkpoint import (
                                create_qwen36_fused_store,
                            )

                            assert split_store_dir is not None
                            split_output = (
                                split_store_dir / f"layer-{layer:03d}.moe"
                            )
                            split_valid = False
                            if (
                                layer in split_completed_layers
                                and split_output.is_file()
                            ):
                                try:
                                    with ExpertMajorStore(split_output) as existing:
                                        split_valid = existing.layer == layer
                                except Exception:
                                    split_output.unlink(missing_ok=True)
                            if not split_valid:
                                split_completed_layers.discard(layer)
                            if not split_valid:
                                await asyncio.to_thread(
                                    create_expert_major_store,
                                    offset_manifest,
                                    layer,
                                    split_output,
                                    force=True,
                                )
                                split_completed_layers.add(layer)
                                write_conversion_state()
                            await asyncio.to_thread(
                                create_qwen36_fused_store,
                                split_output,
                                output,
                                force=True,
                            )
                        else:
                            await asyncio.to_thread(
                                create_expert_major_store,
                                offset_manifest,
                                layer,
                                output,
                                force=True,
                            )
                        completed_layers.add(layer)
                        write_conversion_state()
                    task.progress = 58.0 + 37.0 * (index + 1) / len(routed_layers)
                    task.detail = f"MoE layer {index + 1} / {len(routed_layers)}"
                self._write_store_manifest(
                    store_dir, ExpertMajorStore, conversion_identity
                )
                write_conversion_state()

                task.status = InstallStatus.CONFIGURING
                task.phase = "Configuring dedicated engine"
                task.progress = 97.0
                install_manifest = {
                    "format": "ai2apps-cache-moe-model",
                    "version": 2,
                    "model_id": task.model_id,
                    "family": recipe["family"],
                    "engine": recipe["engine"],
                    "source": {
                        "provider": task.weight_source,
                        "repo_id": task.repo_id,
                        "revision": task.revision,
                    },
                    "scope": {
                        "profile": str(scope_profile),
                        "default": recipe["scope_name"],
                    },
                    "expert_store": str(store_dir.resolve()),
                    "conversion": recipe["conversion"],
                    "memory_tier": task.memory_tier,
                    "installed_at": time.time(),
                }
                scope_pack = self._scope_pack_metadata(recipe, scope_profile)
                if scope_pack is not None:
                    install_manifest["scope"]["pack"] = {
                        "id": scope_pack["id"],
                        "version": scope_pack["pack_version"],
                        "sha256": scope_pack["profile"]["sha256"],
                    }
                if is_qwen:
                    install_manifest["arena_tail_slots"] = int(
                        recipe.get("arena_tail_slots", 24)
                    )
                manifest_path = source_dir / _MODEL_MANIFEST
                partial = manifest_path.with_suffix(".json.partial")
                partial.write_text(json.dumps(install_manifest, indent=2) + "\n")
                partial.replace(manifest_path)

                task.status = InstallStatus.VALIDATING
                task.phase = "Validating installation"
                task.progress = 99.0
                self._validate(
                    source_dir,
                    store_dir,
                    scope_profile,
                    recipe["scope_name"],
                    len(routed_layers),
                    recipe["family"],
                )
                if self.hf_downloader._on_complete:
                    await self.hf_downloader._on_complete()
                task.status = InstallStatus.COMPLETED
                task.phase = "Ready"
                task.progress = 100.0
                task.detail = str(source_dir)
                task.completed_at = time.time()
        except asyncio.CancelledError:
            task.status = InstallStatus.CANCELLED
            task.phase = "Cancelled"
        except Exception as exc:
            task.status = InstallStatus.FAILED
            task.phase = "Failed"
            task.error = str(exc)

    @staticmethod
    def _write_store_manifest(
        store_dir: Path,
        store_class: Any,
        conversion_state: dict[str, Any],
    ) -> None:
        layers = {}
        for path in sorted(store_dir.glob("layer-*.moe")):
            with store_class(path) as store:
                layers[str(store.layer)] = {
                    "file": path.name,
                    "num_experts": store.num_experts,
                    "record_bytes": store.record_bytes,
                    "file_bytes": path.stat().st_size,
                }
        partial = store_dir / "manifest.json.partial"
        partial.write_text(
            json.dumps(
                {
                    "format": "omlx-moe-expert-major-set",
                    "version": 1,
                    "source": {
                        "repo_id": conversion_state["repo_id"],
                        "revision": conversion_state["revision"],
                    },
                    "conversion": conversion_state["conversion"],
                    "layers": layers,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        partial.replace(store_dir / "manifest.json")

    @staticmethod
    def _validate(
        source_dir: Path,
        store_dir: Path,
        scope_profile: Path,
        scope_name: str,
        routed_layer_count: int,
        family: str = "deepseek_v4",
    ) -> None:
        profile = json.loads(scope_profile.read_text())
        if family == "qwen3_6":
            from omlx.cache.moe_expert_store import ExpertMajorStore
            from omlx.patches.qwen3_6_flesh.scope_policy import Qwen36ScopeCatalog

            catalog = Qwen36ScopeCatalog.load(scope_profile)
            if scope_name not in catalog.scope_ids:
                raise ValueError("Qwen Scope Pack does not contain the default scope")
        else:
            if profile.get("format") != "dmoe-deepseek-tiered-policy":
                raise ValueError("unsupported AI2Apps Scope Pack")
            if scope_name not in profile.get("scopes", {}):
                raise ValueError("Scope Pack does not contain the default scope")
        manifest = json.loads((store_dir / "manifest.json").read_text())
        if len(manifest.get("layers", {})) != routed_layer_count:
            raise ValueError("expert store layer count mismatch")
        if family == "qwen3_6":
            first = store_dir / manifest["layers"]["0"]["file"]
            with ExpertMajorStore(first) as store:
                names = {item.name for item in store.tensors}
            if "gate_up_proj.weight" not in names:
                raise ValueError("Qwen expert store is not gate/up fused")
        if not (source_dir / _MODEL_MANIFEST).is_file():
            raise ValueError("AI2Apps install manifest was not committed")

    async def cancel(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task is None or task.status in {
            InstallStatus.COMPLETED,
            InstallStatus.FAILED,
            InstallStatus.CANCELLED,
        }:
            return False
        self._cancelled.add(task_id)
        if task.child_task_id:
            await self.hf_downloader.cancel_download(task.child_task_id)
        task.status = InstallStatus.CANCELLED
        task.phase = "Cancelled"
        return True

    async def retry(self, task_id: str, token: str) -> InstallTask:
        old = self.tasks.get(task_id)
        if old is None or old.status not in {InstallStatus.FAILED, InstallStatus.CANCELLED}:
            raise ValueError("task is not retryable")
        return await self.start(
            old.model_id, old.weight_source, old.memory_tier, token
        )

    def get_tasks(self) -> list[dict[str, Any]]:
        return [
            task.to_dict()
            for task in sorted(self.tasks.values(), key=lambda item: item.created_at)
        ]
