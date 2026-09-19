#!/usr/bin/env python3
"""Find large files that duplicate entries in the AI2Apps shared cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


HOME = Path.home()
REPOSITORY = Path(__file__).resolve().parents[1]
SHARED_ROOT = HOME / "Library/Caches/AI2Apps/shared/checkpoint-cache-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=8 * 1024 * 1024) as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def manifest_index(
    minimum_size: int, selected_distribution_ids: set[str]
) -> dict[int, dict[str, Path]]:
    snapshots: dict[str, Path] = {}
    for metadata in SHARED_ROOT.glob("snapshots/*/*/.ai2apps/distribution.json"):
        record = json.loads(metadata.read_text())
        snapshots[record["distributionId"]] = metadata.parent.parent
    result: dict[int, dict[str, Path]] = defaultdict(dict)
    for manifest_path in (SHARED_ROOT / "manifests").glob("*.json"):
        manifest = json.loads(manifest_path.read_text())
        if (
            selected_distribution_ids
            and manifest["distributionId"] not in selected_distribution_ids
        ):
            continue
        snapshot = snapshots.get(manifest["distributionId"])
        if snapshot is None:
            continue
        for item in manifest["files"]:
            size = int(item["size"])
            if size < minimum_size:
                continue
            digest = item["sha256"].split(":", 1)[-1]
            result[size][digest] = snapshot / item["path"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        help="root to scan; may be repeated",
    )
    parser.add_argument("--minimum-size", type=int, default=1024 * 1024)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument(
        "--distribution-id",
        action="append",
        help="limit the audit to one distribution; may be repeated",
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    roots = args.root or [REPOSITORY, HOME / ".cache/modelscope"]
    index = manifest_index(args.minimum_size, set(args.distribution_id or []))
    shared_inodes = {
        (path.stat().st_dev, path.stat().st_ino)
        for hashes in index.values()
        for path in hashes.values()
        if path.exists()
    }

    seen: set[tuple[int, int]] = set()
    candidates: list[tuple[Path, int, dict[str, Path]]] = []
    for root in roots:
        if not root.exists():
            continue
        for directory, names, files in os.walk(root):
            names[:] = [
                name
                for name in names
                if name not in {".git", ".venv", "node_modules", "__pycache__"}
            ]
            for name in files:
                path = Path(directory) / name
                try:
                    if path.is_symlink():
                        continue
                    metadata = path.stat()
                except OSError:
                    continue
                inode = (metadata.st_dev, metadata.st_ino)
                if inode in seen or inode in shared_inodes or metadata.st_size not in index:
                    continue
                seen.add(inode)
                candidates.append((path, metadata.st_size, index[metadata.st_size]))

    matches: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(sha256_file, path): (path, size, hashes)
            for path, size, hashes in candidates
        }
        for future in as_completed(futures):
            path, size, hashes = futures[future]
            digest = future.result()
            source = hashes.get(digest)
            if source is not None:
                matches.append(
                    {
                        "path": str(path),
                        "size": size,
                        "sha256": digest,
                        "shared": str(source),
                    }
                )

    matches.sort(key=lambda item: str(item["path"]))
    report = {
        "format": "ai2apps-checkpoint-duplicate-audit",
        "version": 1,
        "sharedRoot": str(SHARED_ROOT),
        "roots": [str(root) for root in roots],
        "candidateFiles": len(candidates),
        "candidateBytes": sum(size for _, size, _ in candidates),
        "matchedFiles": len(matches),
        "matchedBytes": sum(int(item["size"]) for item in matches),
        "matches": matches,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("candidateFiles", "candidateBytes", "matchedFiles", "matchedBytes")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
