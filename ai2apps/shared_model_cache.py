"""Fail-closed references and garbage collection for the shared HF cache.

Only immutable, commit-pinned Hugging Face snapshots may be referenced.  Each
AI2Apps instance owns its reference directory, while collection is serialized
against reference publication and AI2Apps snapshot import with one cache-wide
reader/writer lock.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import stat
import time
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_FORMAT = "ai2apps-shared-model-reference"
_MANAGED_FORMAT = "ai2apps-managed-shared-model-snapshot"
_VERSION = 1
_INSTANCE_RE = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?")
_REPO_RE = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,94}[A-Za-z0-9])?"
    r"/[A-Za-z0-9](?:[A-Za-z0-9._-]{0,94}[A-Za-z0-9])?"
)
_REVISION_RE = re.compile(r"[0-9a-f]{40}")


class SharedModelCacheError(RuntimeError):
    """The shared cache cannot be proven safe to mutate."""


@dataclass(frozen=True)
class SharedModelReference:
    instance_id: str
    repo_id: str
    revision: str
    created_at: float

    def validate(self) -> None:
        if not _INSTANCE_RE.fullmatch(self.instance_id):
            raise SharedModelCacheError("invalid AI2Apps instance identity")
        if not _REPO_RE.fullmatch(self.repo_id) or "--" in self.repo_id:
            raise SharedModelCacheError("invalid Hugging Face repository identity")
        if not _REVISION_RE.fullmatch(self.revision):
            raise SharedModelCacheError("shared model revision must be a pinned commit")
        if (
            isinstance(self.created_at, bool)
            or not isinstance(self.created_at, (int, float))
            or not math.isfinite(self.created_at)
            or self.created_at <= 0
        ):
            raise SharedModelCacheError("invalid shared model reference timestamp")

    @property
    def identity(self) -> str:
        return hashlib.sha256(
            f"model\0{self.repo_id}\0{self.revision}".encode()
        ).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "format": _FORMAT,
            "version": _VERSION,
            "instance_id": self.instance_id,
            "repo_id": self.repo_id,
            "revision": self.revision,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class SharedModelCollectionResult:
    dry_run: bool
    scanned_snapshots: int
    protected_snapshots: tuple[str, ...]
    unmanaged_snapshots: tuple[str, ...]
    collected_snapshots: tuple[str, ...]
    collected_blobs: tuple[str, ...]
    reclaimed_bytes: int


@dataclass(frozen=True)
class SharedModelReconciliationResult:
    expected_references: int
    published_references: int
    removed_references: int


def _assert_private_directory(path: Path, *, create: bool) -> None:
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        info = path.lstat()
    except OSError as exc:
        raise SharedModelCacheError(f"cannot inspect cache directory: {path}") from exc
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise SharedModelCacheError(f"cache path is not a real directory: {path}")
    if info.st_uid != os.getuid():
        raise SharedModelCacheError(f"cache directory has another owner: {path}")
    if info.st_mode & 0o077:
        try:
            path.chmod(0o700)
        except OSError as exc:
            raise SharedModelCacheError(f"cache directory is not owner-only: {path}") from exc


def _lock_root(hub_cache: Path) -> Path:
    _assert_private_directory(hub_cache, create=True)
    root = hub_cache / ".ai2apps-locks"
    _assert_private_directory(root, create=True)
    return root


@contextmanager
def shared_model_cache_gate(hub_cache: Path, *, exclusive: bool) -> Iterator[None]:
    """Coordinate cache import/reference readers with the collector writer."""

    lock_path = _lock_root(hub_cache) / "cache-gc.lock"
    try:
        descriptor = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
    except OSError as exc:
        raise SharedModelCacheError("cannot open shared model cache gate") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise SharedModelCacheError("shared model cache gate is not owner-controlled")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _reference_root(hub_cache: Path, *, create: bool) -> Path:
    root = hub_cache / ".ai2apps-references"
    if root.exists() or create:
        _assert_private_directory(root, create=create)
    return root


def _managed_root(hub_cache: Path, *, create: bool) -> Path:
    root = hub_cache / ".ai2apps-managed"
    if root.exists() or create:
        _assert_private_directory(root, create=create)
    return root


def _atomic_write_private(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("short write while publishing shared model reference")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise SharedModelCacheError("cannot publish shared model reference") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def publish_shared_model_reference(
    hub_cache: Path,
    *,
    instance_id: str,
    repo_id: str,
    revision: str,
) -> SharedModelReference:
    reference = SharedModelReference(instance_id, repo_id, revision, time.time())
    reference.validate()
    with shared_model_cache_gate(hub_cache, exclusive=False):
        _publish_shared_model_reference_unlocked(hub_cache, reference)
    return reference


def _publish_shared_model_reference_unlocked(
    hub_cache: Path, reference: SharedModelReference
) -> None:
    root = _reference_root(hub_cache, create=True)
    instance_root = root / reference.instance_id
    _assert_private_directory(instance_root, create=True)
    payload = json.dumps(
        reference.to_dict(), sort_keys=True, separators=(",", ":")
    ).encode() + b"\n"
    _atomic_write_private(instance_root / f"{reference.identity}.json", payload)
    # The reference must become visible first.  If the process crashes
    # before the managed marker is committed, collection ignores the
    # snapshot; the inverse order could expose an unreferenced candidate.
    _publish_managed_snapshot_unlocked(hub_cache, reference)


def _publish_managed_snapshot_unlocked(
    hub_cache: Path, reference: SharedModelReference
) -> None:
    root = _managed_root(hub_cache, create=True)
    payload = json.dumps(
        {
            "format": _MANAGED_FORMAT,
            "version": _VERSION,
            "repo_id": reference.repo_id,
            "revision": reference.revision,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode() + b"\n"
    _atomic_write_private(root / f"{reference.identity}.json", payload)


def mark_shared_model_snapshot_managed(
    hub_cache: Path, *, repo_id: str, revision: str
) -> None:
    """Opt one verified snapshot into reference-aware collection."""

    reference = SharedModelReference("migration", repo_id, revision, 1.0)
    reference.validate()
    with shared_model_cache_gate(hub_cache, exclusive=False):
        _publish_managed_snapshot_unlocked(hub_cache, reference)


def configured_shared_model_cache() -> tuple[str, Path] | None:
    """Return the supervised instance and exact shared Hub path, if enabled."""

    mode = os.environ.get("AI2APPS_MODEL_CACHE_MODE")
    if mode in {None, "", "isolated"}:
        return None
    if mode != "shared":
        raise SharedModelCacheError("unsupported supervised model cache mode")
    instance_id = os.environ.get("AI2APPS_INSTANCE_ID", "")
    model_root_value = os.environ.get("AI2APPS_MODEL_CACHE_ROOT", "")
    hub_value = os.environ.get("HF_HUB_CACHE", "")
    model_root = Path(model_root_value)
    hub_cache = Path(hub_value)
    if (
        not instance_id
        or not model_root.is_absolute()
        or not hub_cache.is_absolute()
        or hub_cache != model_root / "huggingface" / "hub"
    ):
        raise SharedModelCacheError("inconsistent supervised shared cache paths")
    model_root = model_root.resolve()
    hub_cache = hub_cache.resolve()
    if hub_cache != model_root / "huggingface" / "hub":
        raise SharedModelCacheError("resolved shared cache paths do not match")
    reference_identity = SharedModelReference(instance_id, "owner/model", "0" * 40, 1.0)
    reference_identity.validate()
    return instance_id, hub_cache


def publish_configured_shared_model_reference(
    *, repo_id: str, revision: str
) -> SharedModelReference | None:
    """Publish a reference only for an explicitly supervised shared cache.

    A normal CLI process has no AI2Apps cache mode and remains unchanged.  A
    supervised process that claims shared mode must provide the complete,
    internally consistent environment set by ``LocalLaunchPlan``.
    """

    configured = configured_shared_model_cache()
    if configured is None:
        return None
    instance_id, hub_cache = configured
    return publish_shared_model_reference(
        hub_cache,
        instance_id=instance_id,
        repo_id=repo_id,
        revision=revision,
    )


def remove_configured_shared_model_reference(*, repo_id: str, revision: str) -> bool:
    configured = configured_shared_model_cache()
    if configured is None:
        return False
    instance_id, hub_cache = configured
    return remove_shared_model_reference(
        hub_cache,
        instance_id=instance_id,
        repo_id=repo_id,
        revision=revision,
    )


def remove_shared_model_reference(
    hub_cache: Path,
    *,
    instance_id: str,
    repo_id: str,
    revision: str,
) -> bool:
    reference = SharedModelReference(instance_id, repo_id, revision, 1.0)
    reference.validate()
    with shared_model_cache_gate(hub_cache, exclusive=False):
        return _remove_shared_model_reference_unlocked(hub_cache, reference)


def _remove_shared_model_reference_unlocked(
    hub_cache: Path, reference: SharedModelReference
) -> bool:
    root = _reference_root(hub_cache, create=False)
    if not root.exists():
        return False
    instance_root = root / reference.instance_id
    if not instance_root.exists():
        return False
    _assert_private_directory(instance_root, create=False)
    path = instance_root / f"{reference.identity}.json"
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise SharedModelCacheError("shared model reference is not a regular file")
    path.unlink()
    return True


def _decode_reference(path: Path) -> SharedModelReference:
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_size > 16 * 1024
        ):
            raise SharedModelCacheError("unsafe shared model reference metadata")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("format") != _FORMAT or value.get("version") != _VERSION:
            raise SharedModelCacheError("unsupported shared model reference metadata")
        reference = SharedModelReference(
            instance_id=value["instance_id"],
            repo_id=value["repo_id"],
            revision=value["revision"],
            created_at=value["created_at"],
        )
        reference.validate()
        if path.name != f"{reference.identity}.json":
            raise SharedModelCacheError("shared model reference identity mismatch")
        return reference
    except SharedModelCacheError:
        raise
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SharedModelCacheError("invalid shared model reference metadata") from exc


def _load_references_unlocked(hub_cache: Path) -> tuple[SharedModelReference, ...]:
    root = _reference_root(hub_cache, create=False)
    if not root.exists():
        return ()
    references: list[SharedModelReference] = []
    for instance_root in sorted(root.iterdir()):
        _assert_private_directory(instance_root, create=False)
        for path in sorted(instance_root.iterdir()):
            if path.name.startswith(".") and path.name.endswith(".partial"):
                raise SharedModelCacheError("incomplete shared model reference exists")
            references.append(_decode_reference(path))
    return tuple(references)


def _load_managed_unlocked(hub_cache: Path) -> tuple[SharedModelReference, ...]:
    root = _managed_root(hub_cache, create=False)
    if not root.exists():
        return ()
    managed: list[SharedModelReference] = []
    for path in sorted(root.iterdir()):
        try:
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_size > 16 * 1024
            ):
                raise SharedModelCacheError("unsafe managed snapshot metadata")
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("format") != _MANAGED_FORMAT or value.get("version") != _VERSION:
                raise SharedModelCacheError("unsupported managed snapshot metadata")
            reference = SharedModelReference(
                "migration", value["repo_id"], value["revision"], 1.0
            )
            reference.validate()
            if path.name != f"{reference.identity}.json":
                raise SharedModelCacheError("managed snapshot identity mismatch")
            managed.append(reference)
        except SharedModelCacheError:
            raise
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SharedModelCacheError("invalid managed snapshot metadata") from exc
    return tuple(managed)


def list_shared_model_references(hub_cache: Path) -> tuple[SharedModelReference, ...]:
    with shared_model_cache_gate(hub_cache, exclusive=False):
        return _load_references_unlocked(hub_cache)


def reconcile_configured_shared_model_references(
    expected: Iterable[tuple[str, str]],
) -> SharedModelReconciliationResult:
    """Make this supervised instance's references match a complete truth set.

    Callers must derive ``expected`` from durable, validated install metadata,
    and must invoke reconciliation only while no model installation task can be
    active.  The cache gate spans validation and mutation so collection cannot
    observe the conservative publish-before-remove transition halfway through.
    References owned by other instances are never changed.
    """

    configured = configured_shared_model_cache()
    if configured is None:
        return SharedModelReconciliationResult(0, 0, 0)
    instance_id, hub_cache = configured
    expected_references: dict[str, SharedModelReference] = {}
    for repo_id, revision in expected:
        reference = SharedModelReference(instance_id, repo_id, revision, time.time())
        reference.validate()
        expected_references[reference.identity] = reference

    with shared_model_cache_gate(hub_cache, exclusive=False):
        existing = {
            item.identity: item
            for item in _load_references_unlocked(hub_cache)
            if item.instance_id == instance_id
        }
        published = 0
        for identity in sorted(expected_references.keys() - existing.keys()):
            _publish_shared_model_reference_unlocked(
                hub_cache, expected_references[identity]
            )
            published += 1
        removed = 0
        for identity in sorted(existing.keys() - expected_references.keys()):
            if _remove_shared_model_reference_unlocked(hub_cache, existing[identity]):
                removed += 1
    return SharedModelReconciliationResult(
        expected_references=len(expected_references),
        published_references=published,
        removed_references=removed,
    )


def _snapshot_path(hub_cache: Path, reference: SharedModelReference) -> Path:
    return (
        hub_cache
        / ("models--" + reference.repo_id.replace("/", "--"))
        / "snapshots"
        / reference.revision
    )


def _blob_targets(snapshot: Path, blob_root: Path) -> set[Path]:
    targets: set[Path] = set()
    for path in snapshot.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            target = path.resolve(strict=True)
            target.relative_to(blob_root)
        except (OSError, ValueError) as exc:
            raise SharedModelCacheError("snapshot has an unsafe blob link") from exc
        targets.add(target)
    return targets


def collect_unreferenced_hf_snapshots(
    hub_cache: Path, *, dry_run: bool = True
) -> SharedModelCollectionResult:
    """Collect only commit snapshots not named by any instance reference.

    Any malformed reference or unsafe symlink aborts the entire operation.  The
    returned relative paths are bounded operational metadata and do not contain
    instance IDs.
    """

    with shared_model_cache_gate(hub_cache, exclusive=True):
        references = _load_references_unlocked(hub_cache)
        protected = {_snapshot_path(hub_cache, item) for item in references}
        managed = {
            _snapshot_path(hub_cache, item)
            for item in _load_managed_unlocked(hub_cache)
        }
        candidates: list[Path] = []
        protected_existing: list[Path] = []
        unmanaged_existing: list[Path] = []
        retained_blobs: set[Path] = set()
        candidate_blobs: set[Path] = set()
        scanned = 0

        for repo_root in sorted(hub_cache.glob("models--*")):
            info = repo_root.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise SharedModelCacheError("unsafe repository cache entry")
            snapshots = repo_root / "snapshots"
            if not snapshots.exists():
                continue
            snapshot_info = snapshots.lstat()
            if not stat.S_ISDIR(snapshot_info.st_mode) or stat.S_ISLNK(snapshot_info.st_mode):
                raise SharedModelCacheError("unsafe snapshots directory")
            blob_root = repo_root / "blobs"
            for snapshot in sorted(snapshots.iterdir()):
                child_info = snapshot.lstat()
                if not stat.S_ISDIR(child_info.st_mode) or stat.S_ISLNK(child_info.st_mode):
                    raise SharedModelCacheError("unsafe snapshot entry")
                if not _REVISION_RE.fullmatch(snapshot.name):
                    continue
                scanned += 1
                blobs = _blob_targets(snapshot, blob_root)
                if snapshot in protected:
                    protected_existing.append(snapshot)
                    retained_blobs.update(blobs)
                elif snapshot in managed:
                    candidates.append(snapshot)
                    candidate_blobs.update(blobs)
                else:
                    unmanaged_existing.append(snapshot)
                    retained_blobs.update(blobs)

        collectible_blobs = sorted(candidate_blobs - retained_blobs)
        reclaimed_bytes = 0
        for blob in collectible_blobs:
            try:
                info = blob.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise SharedModelCacheError("unsafe cache blob")
            reclaimed_bytes += info.st_size

        if not dry_run:
            for snapshot in candidates:
                shutil.rmtree(snapshot)
            for blob in collectible_blobs:
                blob.unlink(missing_ok=True)

        def relative(path: Path) -> str:
            return str(path.relative_to(hub_cache))

        return SharedModelCollectionResult(
            dry_run=dry_run,
            scanned_snapshots=scanned,
            protected_snapshots=tuple(relative(path) for path in protected_existing),
            unmanaged_snapshots=tuple(relative(path) for path in unmanaged_existing),
            collected_snapshots=tuple(relative(path) for path in candidates),
            collected_blobs=tuple(relative(path) for path in collectible_blobs),
            reclaimed_bytes=reclaimed_bytes,
        )
