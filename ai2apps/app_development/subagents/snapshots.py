"""Materialized source snapshots and optimistic patch merging."""

import hashlib
import json
import shutil
from pathlib import Path

from ..core import DraftError, atomic_write, files, safe_path
from .contracts import SubagentError


def inventory_id(inventory):
    return hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_id(root):
    inventory, _ = files(root)
    return inventory_id(inventory)


def capture(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise SubagentError("snapshot_exists", "Snapshot destination already exists.")
    before, excluded = files(source)
    destination.mkdir(parents=True)
    try:
        for relative in before:
            target = safe_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_path(source, relative), target)
        copied, _ = files(destination)
        after, _ = files(source)
        if before != after or copied != before:
            raise SubagentError(
                "snapshot_changed", "Source changed during snapshot capture."
            )
        return {
            "schema_version": 1,
            "snapshot_id": inventory_id(before),
            "files": before,
            "excluded": excluded,
        }
    except Exception:
        shutil.rmtree(destination)
        raise


def merge_patch(draft, baseline, worker, expected_revision):
    """CAS merge into a parent draft, never the original project. No deletions."""
    with draft.lock:
        if draft.review()["revision"] != expected_revision:
            raise SubagentError(
                "stale_parent", "Review the parent draft again before merging."
            )
        before, _ = files(baseline)
        after, _ = files(worker)
        current, _ = files(draft.workspace)
        paths = [
            p for p in sorted(set(before) | set(after)) if before.get(p) != after.get(p)
        ]
        for p in paths:
            if p not in after:
                raise SubagentError(
                    "deletion_unsupported", "Worker deletions cannot be merged."
                )
            if current.get(p) != before.get(p):
                raise SubagentError("merge_conflict", "Parent draft changed: " + p)
        # Quota/path preflight precedes writes. Journal/backups allow partial-I/O recovery.
        proposed = dict(current)
        proposed.update({p: after[p] for p in paths})
        from ..core import MAX_BYTES, MAX_FILES

        if (
            len(proposed) > MAX_FILES
            or sum(v["bytes"] for v in proposed.values()) > MAX_BYTES
        ):
            raise SubagentError("merge_quota", "Merged draft exceeds source limits.")
        payloads = {}
        for p in paths:
            content = safe_path(worker, p).read_bytes()
            if (
                len(content) != after[p]["bytes"]
                or hashlib.sha256(content).hexdigest() != after[p]["sha256"]
            ):
                raise SubagentError(
                    "snapshot_changed", "Worker changed during merge: " + p
                )
            payloads[p] = content
        value = draft._load()
        if value.get("applied"):
            raise DraftError("draft_applied", "Cannot merge into an applied draft.")
        backup = draft.state.parent / "merge-backups" / expected_revision
        journal = {"paths": paths, "completed": []}
        value["merge_journal"] = journal
        draft._save(value)
        for p in paths:
            target = safe_path(draft.workspace, p)
            if target.exists():
                atomic_write(safe_path(backup, p), target.read_bytes())
            if files(draft.workspace)[0].get(p) != before.get(p):
                raise SubagentError(
                    "merge_conflict", "Parent changed during merge: " + p
                )
            atomic_write(target, payloads[p])
            journal["completed"].append(p)
            value["observed"].pop(p, None)
            draft._save(value)
        return {"merged": paths, "revision": draft.review()["revision"]}
