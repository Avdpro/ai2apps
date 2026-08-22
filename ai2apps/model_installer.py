"""Verified Cache-MoE model catalog and installation pipeline."""

from __future__ import annotations

import asyncio
import enum
import fcntl
import hashlib
import json
import os
import re
import shutil
import struct
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai2apps.shared_model_cache import (
    SharedModelReference,
    configured_shared_model_cache,
    publish_configured_shared_model_reference,
    reconcile_configured_shared_model_references,
    remove_configured_shared_model_reference,
    shared_model_cache_gate,
)

_METADATA_DIR = ".ai2apps"
_LEGACY_METADATA_DIR = ".dynamoe"
_MODEL_MANIFEST = "ai2apps-model.json"
_LEGACY_MODEL_MANIFEST = "dynamoe-model.json"
STORAGE_POLICIES = frozenset({"keep_source", "delete_after", "stream_reclaim"})


def installed_shared_model_source_reference(source_dir: Path) -> tuple[str, str] | None:
    """Return the retained shared source named by one committed install."""

    if configured_shared_model_cache() is None:
        return None
    manifest_path = source_dir / _MODEL_MANIFEST
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("installed model manifest is unreadable") from exc
    source = manifest.get("source")
    if (
        manifest.get("format") != "ai2apps-cache-moe-model"
        or manifest.get("version") != 2
        or not isinstance(source, dict)
        or not isinstance(source.get("repo_id"), str)
        or not isinstance(source.get("revision"), str)
    ):
        raise ValueError("installed model manifest source is invalid")
    checkpoint_layout = manifest.get("checkpoint_layout")
    if checkpoint_layout is not None:
        if not isinstance(checkpoint_layout, dict):
            raise ValueError("installed model checkpoint layout is invalid")
        if checkpoint_layout.get("source_retained") is False:
            return None
        raise ValueError("installed model source retention is ambiguous")
    reference = SharedModelReference(
        "validation", source["repo_id"], source["revision"], 1.0
    )
    reference.validate()
    return reference.repo_id, reference.revision


def reconcile_installed_shared_model_references(
    model_dir: Path, recipes: tuple[dict[str, Any], ...]
):
    """Reconcile one cold Local instance from trusted Package/install state."""

    if configured_shared_model_cache() is None:
        return reconcile_configured_shared_model_references(())
    expected: list[tuple[str, str]] = []
    for recipe in recipes:
        sources = recipe.get("sources", ())
        if len(sources) != 1:
            raise ValueError("model preparation recipe must have exactly one source")
        source = sources[0]
        repo_id = source.get("repo_id")
        revision = source.get("revision")
        if not isinstance(repo_id, str) or not isinstance(revision, str):
            raise ValueError("model preparation source identity is incomplete")
        if recipe.get("recipe") == "native":
            if recipe.get("installed") is True:
                expected.append((repo_id, revision))
            continue

        installed_reference = installed_shared_model_source_reference(
            model_dir / repo_id
        )
        if installed_reference is None:
            continue
        if installed_reference != (repo_id, revision):
            raise ValueError("installed model manifest does not match active recipe")
        expected.append(installed_reference)
    return reconcile_configured_shared_model_references(expected)


@contextmanager
def _shared_cache_revision_lock(
    hub_cache: Path, repo_id: str, revision: str
) -> Iterator[None]:
    """Serialize publication of one shared Hub snapshot across Local instances."""

    lock_root = hub_cache / ".ai2apps-locks"
    lock_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(lock_root, 0o700)
    identity = hashlib.sha256(f"model\0{repo_id}\0{revision}".encode()).hexdigest()
    lock_path = lock_root / f"{identity}.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _git_blob_sha1(path: Path, size: int) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {size}\0".encode())
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _matches_hf_digest(path: Path, size: int, digest: str, *, lfs: bool) -> bool:
    if not path.is_file() or path.stat().st_size != size:
        return False
    actual = _sha256_file(path) if lfs else _git_blob_sha1(path, size)
    return actual == digest


def _snapshot_matches_hf_tree(snapshot: Path, files: dict[str, Any]) -> bool:
    """Verify a published snapshot against its pinned local-dir tree record."""

    if not checkpoint_is_complete(snapshot):
        return False
    for relative, metadata in files.items():
        if (
            not isinstance(relative, str)
            or relative.startswith("/")
            or ".." in relative.split("/")
            or not isinstance(metadata, dict)
        ):
            return False
        size = metadata.get("size")
        digest = metadata.get("lfs_sha256") or metadata.get("blob_id")
        if (
            not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", digest)
            or not _matches_hf_digest(
                snapshot / relative,
                size,
                digest,
                lfs=bool(metadata.get("lfs_sha256")),
            )
        ):
            return False
    return True


def _import_local_checkpoint_to_hf_cache_unlocked(
    source_dir: Path, repo_id: str, revision: str, hub_cache: Path
) -> Path | None:
    """No-copy import a verified HF local-dir checkout into the shared cache.

    ``snapshot_download(local_dir=...)`` records an immutable tree containing
    the commit revision and content hashes. Verify every byte before creating
    hard-linked cache blobs, then expose the standard snapshot layout expected
    by the isolated Model Worker. A cross-filesystem source simply falls back
    to the normal download path.
    """

    tree_path = source_dir / ".cache" / "huggingface" / "trees" / f"{revision}.json"
    try:
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
        files = tree["files"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if tree.get("format_version") != 1 or not isinstance(files, dict) or not files:
        return None
    repo_root = hub_cache / ("models--" + repo_id.replace("/", "--"))
    blobs = repo_root / "blobs"
    snapshot = repo_root / "snapshots" / revision
    if snapshot.exists():
        return snapshot if _snapshot_matches_hf_tree(snapshot, files) else None
    staged = snapshot.with_name(f".{revision}.{uuid.uuid4().hex}.partial")
    try:
        blobs.mkdir(parents=True, exist_ok=True)
        staged.mkdir(parents=True, exist_ok=False)
        for relative, metadata in files.items():
            if (
                not isinstance(relative, str)
                or relative.startswith("/")
                or ".." in relative.split("/")
                or not isinstance(metadata, dict)
            ):
                return None
            source = source_dir / relative
            size = metadata.get("size")
            digest = metadata.get("lfs_sha256") or metadata.get("blob_id")
            if (
                not source.is_file()
                or not isinstance(size, int)
                or source.stat().st_size != size
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", digest)
            ):
                return None
            is_lfs = bool(metadata.get("lfs_sha256"))
            if not _matches_hf_digest(source, size, digest, lfs=is_lfs):
                return None
            blob = blobs / digest
            if blob.exists():
                # Never let a pre-existing, damaged cache blob become trusted
                # merely because its filename looks like a content digest.
                if not _matches_hf_digest(blob, size, digest, lfs=is_lfs):
                    return None
            else:
                os.link(source, blob)
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(Path(os.path.relpath(blob, target.parent)))
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        staged.replace(snapshot)
        return snapshot if _snapshot_matches_hf_tree(snapshot, files) else None
    except (OSError, ValueError):
        return None
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)


def import_local_checkpoint_to_hf_cache(
    source_dir: Path, repo_id: str, revision: str, hub_cache: Path
) -> Path | None:
    """Atomically import a verified checkout into a cross-instance Hub cache."""

    tree_path = source_dir / ".cache" / "huggingface" / "trees" / f"{revision}.json"
    if not tree_path.is_file():
        return None
    with (
        shared_model_cache_gate(hub_cache, exclusive=False),
        _shared_cache_revision_lock(hub_cache, repo_id, revision),
    ):
        return _import_local_checkpoint_to_hf_cache_unlocked(
            source_dir, repo_id, revision, hub_cache
        )


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
    storage_policy: str = "delete_after"
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
            "storage_policy": self.storage_policy,
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


def _is_externalized_routed_tensor(name: str, family: str) -> bool:
    """Return whether a tensor is represented by the canonical expert store."""

    if name.startswith("mtp."):
        # The current DeepSeek V4 runtime intentionally serves the main model
        # only and sanitize already discards these weights.
        return family == "deepseek_v4"
    if family == "qwen3_6":
        return _QWEN36_STACKED_EXPERT_RE.match(name) is not None
    return (
        _EXPERT_RE.match(name) is not None
        or _STACKED_EXPERT_RE.match(name) is not None
    )


def _copy_safetensors_subset(
    source: Path,
    destination: Path,
    names: set[str],
) -> tuple[int, dict[str, dict[str, Any]]]:
    """Copy selected tensors without decoding or allocating their payloads."""

    with source.open("rb") as handle:
        raw_length = handle.read(8)
        if len(raw_length) != 8:
            raise ValueError(f"invalid safetensors header: {source}")
        (header_length,) = struct.unpack("<Q", raw_length)
        raw_header = handle.read(header_length)
        complete_header = json.loads(raw_header)
    metadata = complete_header.get("__metadata__")
    source_header = {
        key: value
        for key, value in complete_header.items()
        if key != "__metadata__"
    }
    missing = names - set(source_header)
    if missing:
        raise ValueError(
            f"safetensors subset references missing tensors: {sorted(missing)[:3]}"
        )

    selected = sorted(
        ((name, source_header[name]) for name in names),
        key=lambda item: int(item[1]["data_offsets"][0]),
    )
    output_header: dict[str, Any] = {}
    if metadata is not None:
        output_header["__metadata__"] = metadata
    cursor = 0
    for name, spec in selected:
        start, end = (int(value) for value in spec["data_offsets"])
        length = end - start
        output_header[name] = {
            "dtype": spec["dtype"],
            "shape": spec["shape"],
            "data_offsets": [cursor, cursor + length],
        }
        cursor += length

    encoded = json.dumps(output_header, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 8)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    source_fd = os.open(source, os.O_RDONLY)
    output_fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(output_fd, struct.pack("<Q", len(encoded)))
        os.write(output_fd, encoded)
        source_data_start = 8 + header_length
        for _name, spec in selected:
            start, end = (int(value) for value in spec["data_offsets"])
            offset = source_data_start + start
            remaining = end - start
            while remaining:
                chunk = os.pread(source_fd, min(8 * 1024 * 1024, remaining), offset)
                if not chunk:
                    raise EOFError(f"short safetensors read from {source}")
                view = memoryview(chunk)
                while view:
                    written = os.write(output_fd, view)
                    if written <= 0:
                        raise OSError(f"short safetensors write to {partial}")
                    view = view[written:]
                offset += len(chunk)
                remaining -= len(chunk)
        os.fsync(output_fd)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    finally:
        os.close(source_fd)
        os.close(output_fd)
    partial.replace(destination)
    return cursor, {
        name: output_header[name]
        for name, _spec in selected
    }


def build_backbone_checkpoint(
    source_dir: Path,
    output_dir: Path,
    family: str,
) -> dict[str, Any]:
    """Create a raw-copy backbone checkpoint with routed experts removed."""

    index_path = source_dir / "model.safetensors.index.json"
    index = json.loads(index_path.read_text())
    weight_map = index["weight_map"]
    output_dir.mkdir(parents=True, exist_ok=True)
    new_weight_map: dict[str, str] = {}
    shards: dict[str, Any] = {}
    total_size = 0
    for shard_name in sorted(set(weight_map.values())):
        source = source_dir / shard_name
        _data_start, header = _read_safetensors_header(source)
        selected = {
            name
            for name in header
            if weight_map.get(name) == shard_name
            and not _is_externalized_routed_tensor(name, family)
        }
        if not selected:
            shards[shard_name] = {
                "backbone_file": None,
                "source_bytes": source.stat().st_size,
                "backbone_bytes": 0,
            }
            continue
        destination = output_dir / shard_name
        payload_bytes, _ = _copy_safetensors_subset(source, destination, selected)
        total_size += payload_bytes
        new_weight_map.update({name: shard_name for name in selected})
        shards[shard_name] = {
            "backbone_file": shard_name,
            "source_bytes": source.stat().st_size,
            "backbone_bytes": destination.stat().st_size,
            "sha256": _sha256_file(destination),
        }
    if not new_weight_map:
        raise ValueError("prepared backbone checkpoint contains no weights")
    new_index = {
        **{key: value for key, value in index.items() if key != "weight_map"},
        "metadata": {
            **(index.get("metadata") or {}),
            "total_size": total_size,
        },
        "weight_map": new_weight_map,
    }
    partial_index = output_dir / "model.safetensors.index.json.partial"
    partial_index.write_text(json.dumps(new_index, indent=2, sort_keys=True) + "\n")
    partial_index.replace(output_dir / "model.safetensors.index.json")
    journal = {
        "format": "ai2apps-backbone-checkpoint",
        "version": 1,
        "family": family,
        "source_dir": str(source_dir.resolve()),
        "total_payload_bytes": total_size,
        "shards": shards,
    }
    partial_journal = output_dir / "backbone-manifest.json.partial"
    partial_journal.write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n")
    partial_journal.replace(output_dir / "backbone-manifest.json")
    return journal


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    partial.replace(path)


def build_storage_transition(
    source_dir: Path,
    backbone_dir: Path,
    offset_manifest: Path,
    *,
    repo_id: str,
    revision: str,
    policy: str,
) -> Path:
    """Create the crash-resumable source-shard reclamation journal."""

    offsets = json.loads(offset_manifest.read_text())
    last_layers: dict[str, int] = {}
    for raw_layer, layer in offsets["layers"].items():
        layer_number = int(raw_layer)
        for expert in layer.get("experts", ()):
            for tensor in expert.get("tensors", ()):
                raw_file = tensor.get("file", layer.get("file"))
                if raw_file:
                    shard = Path(raw_file).name
                    last_layers[shard] = max(last_layers.get(shard, -1), layer_number)
    backbone = json.loads((backbone_dir / "backbone-manifest.json").read_text())
    unknown = set(last_layers) - set(backbone["shards"])
    if unknown:
        raise ValueError(f"offset references unknown source shards: {sorted(unknown)}")
    # A shard may contain backbone tensors only. It has no expert consumer and
    # can therefore be replaced as soon as conversion starts.
    for shard in backbone["shards"]:
        last_layers.setdefault(shard, -1)
    path = _metadata_dir(source_dir) / "storage-transition.json"
    value = {
        "format": "ai2apps-storage-transition",
        "version": 1,
        "repo_id": repo_id,
        "revision": revision,
        "policy": policy,
        "state": "converting",
        "offset_manifest": str(offset_manifest.resolve()),
        "backbone_dir": str(backbone_dir.resolve()),
        "last_layers": last_layers,
        "reclaimed_shards": [],
        "reclaimed_source_bytes": 0,
        "source_cache_linked": any(
            (source_dir / shard).is_symlink() for shard in backbone["shards"]
        ),
    }
    _write_json_atomic(path, value)
    return path


def reclaim_stream_shards(
    source_dir: Path,
    transition_path: Path,
    completed_layer: int,
) -> list[str]:
    """Replace source shards whose final consumer has committed."""

    transition = json.loads(transition_path.read_text())
    if transition.get("state") != "converting":
        return []
    backbone_dir = Path(transition["backbone_dir"])
    backbone = json.loads((backbone_dir / "backbone-manifest.json").read_text())
    reclaimed = set(transition.get("reclaimed_shards", ()))
    released: list[str] = []
    for shard, last_layer in sorted(transition["last_layers"].items()):
        if shard in reclaimed or int(last_layer) > completed_layer:
            continue
        source = source_dir / shard
        expected = backbone["shards"][shard]
        replacement = backbone_dir / shard
        if expected["backbone_file"] is not None:
            if not replacement.is_file():
                # A crash after os.replace but before the journal commit is
                # recoverable when the root file already has the expected hash.
                if not source.is_file() or _sha256_file(source) != expected["sha256"]:
                    raise FileNotFoundError(f"prepared backbone shard is missing: {shard}")
            else:
                source.unlink(missing_ok=True)
                os.replace(replacement, source)
        else:
            source.unlink(missing_ok=True)
        reclaimed.add(shard)
        released.append(shard)
        transition["reclaimed_source_bytes"] = int(
            transition.get("reclaimed_source_bytes", 0)
        ) + int(expected["source_bytes"])
        transition["reclaimed_shards"] = sorted(reclaimed)
        _write_json_atomic(transition_path, transition)
    return released


def commit_backbone_index(source_dir: Path, transition_path: Path) -> dict[str, Any]:
    """Commit the prepared index after every source shard was reclaimed."""

    transition = json.loads(transition_path.read_text())
    if set(transition.get("reclaimed_shards", ())) != set(transition["last_layers"]):
        raise ValueError("cannot commit backbone index before all shards are reclaimed")
    backbone_dir = Path(transition["backbone_dir"])
    prepared_index = backbone_dir / "model.safetensors.index.json"
    if not prepared_index.is_file():
        raise FileNotFoundError("prepared backbone index is missing")
    source_index = source_dir / "model.safetensors.index.json"
    archived_index = _metadata_dir(source_dir) / "source-model.safetensors.index.json"
    if not archived_index.exists():
        os.replace(source_index, archived_index)
    os.replace(prepared_index, source_index)
    transition["state"] = "prepared"
    _write_json_atomic(transition_path, transition)
    return transition


def resume_storage_transition(
    source_dir: Path,
    *,
    repo_id: str,
    revision: str,
    policy: str,
) -> Path | None:
    """Return a structurally valid interrupted transition, if one exists."""

    path = _metadata_dir(source_dir) / "storage-transition.json"
    try:
        value = json.loads(path.read_text())
    except (OSError, TypeError, json.JSONDecodeError):
        return None
    expected = {
        "format": "ai2apps-storage-transition",
        "repo_id": repo_id,
        "revision": revision,
        "policy": policy,
        "state": "converting",
    }
    if any(value.get(key) != item for key, item in expected.items()):
        return None
    offset_manifest = Path(value.get("offset_manifest", ""))
    backbone_dir = Path(value.get("backbone_dir", ""))
    try:
        backbone = json.loads((backbone_dir / "backbone-manifest.json").read_text())
    except (OSError, TypeError, json.JSONDecodeError):
        return None
    if not offset_manifest.is_file():
        return None
    reclaimed = set(value.get("reclaimed_shards", ()))
    for shard, spec in backbone.get("shards", {}).items():
        root_file = source_dir / shard
        if shard not in reclaimed and not root_file.is_file():
            return None
        if shard in reclaimed and spec.get("backbone_file") is not None:
            staged = backbone_dir / shard
            if not root_file.is_file() and not staged.is_file():
                return None
    return path


def _materialize_linked_files(root: Path) -> int:
    """Replace cache-backed symlinks with local files before cache eviction."""

    copied = 0
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        target = path.resolve(strict=True)
        partial = path.with_name(path.name + ".materializing")
        shutil.copy2(target, partial)
        os.replace(partial, path)
        copied += 1
    return copied


def release_hf_cache_revision(
    source_dir: Path,
    repo_id: str,
    revision: str,
    *,
    cache_linked: bool,
) -> dict[str, Any]:
    """Materialize the model view and delete only its exact HF cache revision."""

    result: dict[str, Any] = {
        "attempted": False,
        "freed_bytes": 0,
        "materialized_files": 0,
    }
    if not cache_linked:
        return result
    result["attempted"] = True
    try:
        linked_targets = [path.resolve() for path in source_dir.rglob("*") if path.is_symlink()]
        cache_repo = next(
            (
                parent
                for target in linked_targets
                for parent in target.parents
                if parent.name.startswith("models--")
            ),
            None,
        )
        if cache_repo is None:
            raise ValueError("could not identify the linked Hugging Face cache")
        result["materialized_files"] = _materialize_linked_files(source_dir)

        from huggingface_hub import scan_cache_dir

        cache = scan_cache_dir(cache_repo.parent)
        repo = next(
            (item for item in cache.repos if item.repo_id == repo_id and item.repo_type == "model"),
            None,
        )
        if repo is None:
            raise ValueError(f"Hugging Face cache entry is missing: {repo_id}")
        matching = [item.commit_hash for item in repo.revisions if item.commit_hash == revision]
        if len(matching) != 1:
            raise ValueError("the exact Hugging Face cache revision was not found")
        strategy = cache.delete_revisions(matching[0])
        result["freed_bytes"] = int(strategy.expected_freed_size)
        strategy.execute()
        result["completed"] = True
    except Exception as exc:  # Installation remains valid after materialization.
        result["completed"] = False
        result["error"] = str(exc)
    return result


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
    def __init__(
        self,
        hf_downloader: Any,
        package_recipes: tuple[dict[str, Any], ...] = (),
        on_ready: Any | None = None,
    ):
        self.hf_downloader = hf_downloader
        self.package_recipes = package_recipes
        self.on_ready = on_ready
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
        manifest_path = Path(relative)
        if not manifest_path.is_absolute():
            manifest_path = Path(__file__).parent / manifest_path
        packaged_profile = Path(recipe["engine"]["scope_asset"])
        if not packaged_profile.is_absolute():
            packaged_profile = Path(__file__).parent / packaged_profile
        packaged_profile = packaged_profile.resolve()
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
        packaged = Path(recipe["engine"]["scope_asset"])
        if not packaged.is_absolute():
            packaged = Path(__file__).parent / packaged
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

    @staticmethod
    def _materialize_scope_profile(
        source_dir: Path,
        scope_profile: Path,
        scope_pack: dict[str, Any] | None,
    ) -> Path:
        """Copy package-owned runtime data into the installed model directory.

        Adapter packages may be upgraded or uninstalled independently.  A
        prepared checkpoint must therefore never retain a runtime dependency
        on an adapter package's immutable version directory.
        """
        payload = scope_profile.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if scope_pack is not None:
            expected = str(scope_pack["profile"]["sha256"]).lower()
            if digest != expected:
                raise RuntimeError(
                    f"Scope Pack checksum mismatch: expected {expected}, got {digest}"
                )
        destination = _metadata_dir(source_dir) / "scope-assets" / f"{digest}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"installed Scope Pack asset is corrupt: {destination}")
            return destination.resolve()
        partial = destination.with_suffix(".json.partial")
        partial.write_bytes(payload)
        partial.replace(destination)
        return destination.resolve()

    @classmethod
    def _recipes(cls) -> tuple[dict[str, Any], ...]:
        """Read recipes only from active, signed model-adapter packages."""
        from omlx.model_adapters import get_model_adapter_registry

        return get_model_adapter_registry().installation_recipes()

    @classmethod
    def catalog(
        cls, package_recipes: tuple[dict[str, Any], ...] = ()
    ) -> list[dict[str, Any]]:
        result = []
        recipes = package_recipes or cls._recipes()
        for recipe in recipes:
            if recipe.get("internal"):
                continue
            if recipe.get("recipe") == "native":
                item = {key: value for key, value in recipe.items()}
                item["sources"] = list(item["sources"])
                item["memory_tiers"] = list(item.get("memory_tiers", ()))
                item["engine"] = dict(item.get("engine", {}))
                item["engine_ready"] = True
                result.append(item)
                continue
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
        for recipe in self.package_recipes or self._recipes():
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
        storage_policy: str | None = None,
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
        supported_storage = set(recipe.get("storage_policies", ("keep_source",)))
        if storage_policy is None:
            storage_policy = (
                "delete_after"
                if "delete_after" in supported_storage
                else "keep_source"
            )
        if storage_policy not in STORAGE_POLICIES:
            raise ValueError(f"unsupported storage policy: {storage_policy}")
        if storage_policy not in supported_storage:
            raise ValueError(
                f"{model_id} does not support storage policy: {storage_policy}"
            )
        if recipe.get("recipe") == "native":
            task = InstallTask(
                task_id=str(uuid.uuid4()),
                model_id=model_id,
                weight_source=weight_source,
                repo_id=source["repo_id"],
                revision=source["revision"],
                memory_tier="auto",
                storage_policy="keep_source",
            )
            self.tasks[task.task_id] = task
            self._runners[task.task_id] = asyncio.create_task(
                self._run_native(task, recipe, token)
            )
            return task

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
            storage_policy=storage_policy,
        )
        self.tasks[task.task_id] = task
        self._runners[task.task_id] = asyncio.create_task(
            self._run(task, recipe, token, scope_profile)
        )
        return task

    async def _run_native(
        self, task: InstallTask, recipe: dict[str, Any], token: str
    ) -> None:
        """Download a native checkpoint and its required internal checkpoints."""

        try:
            async with self._sem:
                task.status = InstallStatus.DOWNLOADING
                recipes = {
                    item["id"]: item
                    for item in (self.package_recipes or self._recipes())
                }
                for required_id in recipe.get("required_model_ids", ()):
                    required = recipes.get(required_id)
                    if required is None or required.get("recipe") != "native":
                        raise RuntimeError(
                            f"required native model is unavailable: {required_id}"
                        )
                    await self._ensure_native_checkpoint(
                        task, required, token, dependency=True
                    )
                    if task.status == InstallStatus.CANCELLED:
                        return
                task.cache_hit = await self._ensure_native_checkpoint(
                    task, recipe, token, dependency=False
                )
                if task.status == InstallStatus.CANCELLED:
                    return
                task.status = InstallStatus.VALIDATING
                task.phase = "Activating model Worker"
                task.progress = 99.0
                task.status = InstallStatus.COMPLETED
                task.phase = "Ready"
                task.progress = 100.0
                task.detail = f"{task.repo_id}@{task.revision}"
                task.completed_at = time.time()
        except asyncio.CancelledError:
            task.status = InstallStatus.CANCELLED
            task.phase = "Cancelled"
        except Exception as exc:
            task.status = InstallStatus.FAILED
            task.phase = "Failed"
            task.error = str(exc)

    async def _ensure_native_checkpoint(
        self,
        task: InstallTask,
        recipe: dict[str, Any],
        token: str,
        *,
        dependency: bool,
    ) -> bool:
        """Ensure one pinned native checkpoint exists, then activate its Worker."""

        from ai2apps.packages.supervisor import ManagedServiceSupervisor

        source = recipe["sources"][0]
        repo_id = source["repo_id"]
        revision = source["revision"]
        label = recipe.get("name", recipe["id"])
        prefix = "Preparing required model" if dependency else "Preparing model"
        task.phase = f"{prefix}: {label}"
        source_dir = self.hf_downloader.model_dir / repo_id
        await asyncio.to_thread(
            publish_configured_shared_model_reference,
            repo_id=repo_id,
            revision=revision,
        )
        imported = await asyncio.to_thread(
            import_local_checkpoint_to_hf_cache,
            source_dir,
            repo_id,
            revision,
            ManagedServiceSupervisor._huggingface_hub_cache(),
        )
        cache_hit = imported is not None
        if not cache_hit:
            child = await self.hf_downloader.start_download(
                repo_id,
                token,
                revision=revision,
                notify_complete=False,
                cache_mode=True,
            )
            task.child_task_id = child.task_id
            while child.status.value in {"pending", "downloading"}:
                if task.task_id in self._cancelled:
                    await self.hf_downloader.cancel_download(child.task_id)
                    task.status = InstallStatus.CANCELLED
                    task.phase = "Cancelled"
                    return False
                task.progress = child.progress
                task.detail = (
                    f"{label}: {child.downloaded_size} / {child.total_size} bytes"
                )
                await asyncio.sleep(0.5)
            if child.status.value != "completed":
                raise RuntimeError(child.error or f"download {child.status.value}")
            cache_hit = bool(getattr(child, "cache_hit", False))
        else:
            task.detail = f"Reused existing pinned checkpoint for {label}"
        if self.on_ready is not None:
            await self.on_ready(recipe)
        return cache_hit

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
                await asyncio.to_thread(
                    publish_configured_shared_model_reference,
                    repo_id=task.repo_id,
                    revision=task.revision,
                )
                task.phase = "Checking local HuggingFace cache"
                resumed_transition = None
                if task.storage_policy == "stream_reclaim":
                    resumed_transition = await asyncio.to_thread(
                        resume_storage_transition,
                        source_dir,
                        repo_id=task.repo_id,
                        revision=task.revision,
                        policy=task.storage_policy,
                    )
                    _source_path, source_record = _source_record(source_dir)
                    task.cache_hit = resumed_transition is not None or (
                        checkpoint_is_complete(source_dir)
                        and all(
                            source_record.get(key) == value
                            for key, value in {
                                "repo_id": task.repo_id,
                                "revision": task.revision,
                            }.items()
                        )
                    )
                else:
                    task.cache_hit = await asyncio.to_thread(
                        self._prepare_cached_checkpoint,
                        task.repo_id,
                        task.revision,
                        token,
                        source_dir,
                    )
                if task.cache_hit:
                    task.progress = 55.0
                    task.detail = (
                        "Resuming low-disk conversion"
                        if resumed_transition is not None
                        else "Reused local checkpoint without downloading"
                    )
                else:
                    task.phase = "Downloading checkpoint"
                    child = await self.hf_downloader.start_download(
                        task.repo_id,
                        token,
                        revision=task.revision,
                        notify_complete=False,
                        cache_mode=task.storage_policy != "stream_reclaim",
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
                    if resumed_transition is not None:
                        transition = json.loads(resumed_transition.read_text())
                        offset_manifest = Path(transition["offset_manifest"])
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
                transition_path = resumed_transition
                if task.storage_policy != "keep_source" and not is_qwen:
                    if transition_path is None:
                        backbone_dir = work_dir / "backbone-staging"
                        task.phase = "Preparing compact backbone"
                        await asyncio.to_thread(
                            build_backbone_checkpoint,
                            source_dir,
                            backbone_dir,
                            recipe["family"],
                        )
                        transition_path = await asyncio.to_thread(
                            build_storage_transition,
                            source_dir,
                            backbone_dir,
                            offset_manifest,
                            repo_id=task.repo_id,
                            revision=task.revision,
                            policy=task.storage_policy,
                        )
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
                    if (
                        transition_path is not None
                        and task.storage_policy == "stream_reclaim"
                    ):
                        released = await asyncio.to_thread(
                            reclaim_stream_shards,
                            source_dir,
                            transition_path,
                            layer,
                        )
                        if released:
                            task.detail = (
                                f"MoE layer {index + 1} / {len(routed_layers)} · "
                                f"reclaimed {len(released)} source shard(s)"
                            )
                    task.progress = 58.0 + 37.0 * (index + 1) / len(routed_layers)
                    if not (
                        transition_path is not None
                        and task.storage_policy == "stream_reclaim"
                        and released
                    ):
                        task.detail = f"MoE layer {index + 1} / {len(routed_layers)}"
                self._write_store_manifest(
                    store_dir, ExpertMajorStore, conversion_identity
                )
                write_conversion_state()

                checkpoint_layout = None
                if transition_path is not None:
                    if task.storage_policy == "delete_after":
                        await asyncio.to_thread(
                            reclaim_stream_shards,
                            source_dir,
                            transition_path,
                            max(routed_layers),
                        )
                    transition = await asyncio.to_thread(
                        commit_backbone_index,
                        source_dir,
                        transition_path,
                    )
                    checkpoint_layout = {
                        "format": "ai2apps-backbone-expert-store",
                        "version": 1,
                        "source_retained": False,
                        "storage_policy": task.storage_policy,
                        "reclaimed_source_bytes": transition[
                            "reclaimed_source_bytes"
                        ],
                    }

                task.status = InstallStatus.CONFIGURING
                task.phase = "Configuring dedicated engine"
                task.progress = 97.0
                scope_pack = self._scope_pack_metadata(recipe, scope_profile)
                runtime_scope_profile = self._materialize_scope_profile(
                    source_dir, scope_profile, scope_pack
                )
                install_manifest = {
                    "format": "ai2apps-cache-moe-model",
                    "version": 2,
                    "model_id": task.model_id,
                    "family": recipe["family"],
                    "execution_modes": list(
                        recipe.get("execution_modes", ("cached",))
                    ),
                    "engine": {
                        key: value
                        for key, value in recipe["engine"].items()
                        if key not in {"scope_asset", "scope_pack", "scope_env"}
                    },
                    "source": {
                        "provider": task.weight_source,
                        "repo_id": task.repo_id,
                        "revision": task.revision,
                    },
                    "scope": {
                        "profile": str(runtime_scope_profile),
                        "default": recipe["scope_name"],
                    },
                    "expert_store": str(store_dir.resolve()),
                    "conversion": recipe["conversion"],
                    "memory_tier": task.memory_tier,
                    "installed_at": time.time(),
                }
                if checkpoint_layout is not None:
                    install_manifest["checkpoint_layout"] = checkpoint_layout
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
                    runtime_scope_profile,
                    recipe["scope_name"],
                    len(routed_layers),
                    recipe["family"],
                )
                if checkpoint_layout is not None:
                    task.phase = "Releasing original checkpoint"
                    cleanup = await asyncio.to_thread(
                        release_hf_cache_revision,
                        source_dir,
                        task.repo_id,
                        task.revision,
                        cache_linked=bool(transition.get("source_cache_linked")),
                    )
                    checkpoint_layout["hf_cache_cleanup"] = cleanup
                    install_manifest["checkpoint_layout"] = checkpoint_layout
                    _write_json_atomic(manifest_path, install_manifest)
                    await asyncio.to_thread(
                        remove_configured_shared_model_reference,
                        repo_id=task.repo_id,
                        revision=task.revision,
                    )
                if self.hf_downloader._on_complete:
                    await self.hf_downloader._on_complete()
                if self.on_ready is not None:
                    await self.on_ready(recipe)
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
        if not checkpoint_is_complete(source_dir):
            raise ValueError("prepared checkpoint is incomplete")
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
            old.model_id,
            old.weight_source,
            old.memory_tier,
            token,
            old.storage_policy,
        )

    def get_tasks(self) -> list[dict[str, Any]]:
        return [
            task.to_dict()
            for task in sorted(self.tasks.values(), key=lambda item: item.created_at)
        ]
