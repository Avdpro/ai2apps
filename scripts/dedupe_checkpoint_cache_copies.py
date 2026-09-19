#!/usr/bin/env python3
"""Deduplicate verified checkpoint copies against the AI2Apps shared cache.

The script keeps every existing cache path intact.  Once a candidate file has
the exact size and SHA-256 recorded by the signed checkpoint manifest, the
candidate's backing file is atomically replaced with a hard link to the
verified shared snapshot file.  Hugging Face snapshot symlinks are preserved;
their blob targets are replaced instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path


HOME = Path.home()
SHARED_ROOT = HOME / "Library/Caches/AI2Apps/shared/checkpoint-cache-v1"
SHA256_NAME = re.compile(r"[0-9a-f]{64}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=8 * 1024 * 1024) as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def cache_roots() -> list[tuple[str, Path]]:
    roots = [("global-hf", HOME / ".cache/huggingface/hub")]
    instances = HOME / "Library/Caches/AI2Apps/instances"
    for root in sorted(instances.glob("*/model-weights/huggingface/hub")):
        roots.append((f"instance:{root.parents[2].name}", root))
    backup = (
        HOME
        / "Library/Application Support/AI2Apps"
        / "app-dev-reset-backup-20260910-0019/cache/model-weights/huggingface/hub"
    )
    if backup.exists():
        roots.append(("app-dev-reset-backup", backup))
    return [(label, root) for label, root in roots if root.exists()]


def shared_snapshots() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for metadata in SHARED_ROOT.glob("snapshots/*/*/.ai2apps/distribution.json"):
        record = json.loads(metadata.read_text())
        result[record["distributionId"]] = metadata.parent.parent
    return result


def candidate_trees(
    *, root: Path, repo_id: str, revision: str, manifest_key: str
) -> list[tuple[str, Path]]:
    repo = root / ("models--" + repo_id.replace("/", "--"))
    candidates = [
        ("hf-snapshot", repo / "snapshots" / revision),
        ("distribution", repo / "distributions" / manifest_key),
    ]
    return [(kind, path) for kind, path in candidates if path.exists()]


def verified(path: Path, *, expected_size: int, expected_sha256: str) -> bool:
    if not path.exists() or path.stat().st_size != expected_size:
        return False
    resolved = path.resolve()
    if SHA256_NAME.fullmatch(resolved.name) and resolved.name == expected_sha256:
        return True
    return sha256_file(resolved) == expected_sha256


def replace_with_hardlink(source: Path, candidate: Path) -> bool:
    source = source.resolve()
    target = candidate.resolve()
    source_stat = source.stat()
    target_stat = target.stat()
    if (source_stat.st_dev, source_stat.st_ino) == (target_stat.st_dev, target_stat.st_ino):
        return False
    if source_stat.st_dev != target_stat.st_dev:
        raise RuntimeError(f"cross-device hard link is not possible: {target}")
    parent = target.parent
    original_parent_mode = stat.S_IMODE(parent.stat().st_mode)
    restored_parent_mode = False
    if not original_parent_mode & stat.S_IWUSR:
        parent.chmod(original_parent_mode | stat.S_IWUSR)
        restored_parent_mode = True
    temporary: Path | None = None
    try:
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.dedupe-", dir=parent)
        os.close(fd)
        temporary = Path(temporary_name)
        temporary.unlink()
        os.link(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if restored_parent_mode:
            parent.chmod(original_parent_mode)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="replace verified copies with hard links")
    parser.add_argument("--report", type=Path, help="write a JSON audit report")
    parser.add_argument(
        "--distribution-id",
        action="append",
        help="limit the audit to one distribution; may be repeated",
    )
    args = parser.parse_args()
    selected = set(args.distribution_id or [])

    snapshots = shared_snapshots()
    groups: list[dict[str, object]] = []
    linked_bytes = 0
    linked_files = 0

    for manifest_path in sorted((SHARED_ROOT / "manifests").glob("*.json")):
        manifest = json.loads(manifest_path.read_text())
        distribution_id = manifest["distributionId"]
        if selected and distribution_id not in selected:
            continue
        shared = snapshots.get(distribution_id)
        if shared is None:
            continue
        for label, root in cache_roots():
            for kind, candidate in candidate_trees(
                root=root,
                repo_id=manifest["repoId"],
                revision=manifest["revision"],
                manifest_key=manifest_path.stem,
            ):
                record: dict[str, object] = {
                    "cache": label,
                    "kind": kind,
                    "distributionId": distribution_id,
                    "candidate": str(candidate),
                    "shared": str(shared),
                    "verifiedFiles": 0,
                    "verifiedBytes": 0,
                    "linkedFiles": 0,
                    "linkedBytes": 0,
                    "alreadyLinkedFiles": 0,
                    "alreadyLinkedBytes": 0,
                    "missingOrDifferent": [],
                }
                for item in manifest["files"]:
                    relative = Path(item["path"])
                    source = shared / relative
                    target = candidate / relative
                    size = int(item["size"])
                    expected = item["sha256"].split(":", 1)[-1]
                    same_inode = False
                    if source.exists() and target.exists():
                        source_stat = source.resolve().stat()
                        target_stat = target.resolve().stat()
                        same_inode = (
                            source_stat.st_size == size
                            and target_stat.st_size == size
                            and (source_stat.st_dev, source_stat.st_ino)
                            == (target_stat.st_dev, target_stat.st_ino)
                        )
                    if not same_inode and (
                        not source.exists()
                        or not verified(
                            target, expected_size=size, expected_sha256=expected
                        )
                    ):
                        record["missingOrDifferent"].append(str(relative))
                        continue
                    record["verifiedFiles"] += 1
                    record["verifiedBytes"] += size
                    if same_inode:
                        record["alreadyLinkedFiles"] += 1
                        record["alreadyLinkedBytes"] += size
                    if args.apply and replace_with_hardlink(source, target):
                        record["linkedFiles"] += 1
                        record["linkedBytes"] += size
                        linked_files += 1
                        linked_bytes += size
                groups.append(record)
                print(
                    f"{label} {distribution_id}: "
                    f"verified={record['verifiedFiles']} "
                    f"linked={record['linkedFiles']} "
                    f"shared-inode={record['alreadyLinkedFiles']} "
                    f"different={len(record['missingOrDifferent'])}"
                )

    report = {
        "format": "ai2apps-checkpoint-dedupe-report",
        "version": 1,
        "mode": "apply" if args.apply else "audit",
        "sharedRoot": str(SHARED_ROOT),
        "linkedFiles": linked_files,
        "linkedBytes": linked_bytes,
        "groups": groups,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("mode", "linkedFiles", "linkedBytes")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
