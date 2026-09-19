#!/usr/bin/env python3
"""Replace audited checkpoint duplicates with APFS copy-on-write clones."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import stat
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


HOME = Path.home()
REPOSITORY = Path(__file__).resolve().parents[1]
SHARED_ROOT = HOME / "Library/Caches/AI2Apps/shared/checkpoint-cache-v1"
ALLOWED_TARGET_ROOTS = (REPOSITORY, HOME / ".cache/modelscope")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=8 * 1024 * 1024) as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def manifest_sources() -> dict[tuple[str, str], Path]:
    snapshots: dict[str, Path] = {}
    for metadata in SHARED_ROOT.glob("snapshots/*/*/.ai2apps/distribution.json"):
        record = json.loads(metadata.read_text())
        snapshots[record["distributionId"]] = metadata.parent.parent
    result: dict[tuple[str, str], Path] = {}
    for manifest_path in (SHARED_ROOT / "manifests").glob("*.json"):
        manifest = json.loads(manifest_path.read_text())
        snapshot = snapshots.get(manifest["distributionId"])
        if snapshot is None:
            continue
        for item in manifest["files"]:
            digest = item["sha256"].split(":", 1)[-1]
            result[(digest, str(snapshot / item["path"]))] = snapshot / item["path"]
    return result


def clonefile(source: Path, target: Path) -> None:
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    clone = library.clonefile
    clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    clone.restype = ctypes.c_int

    target_stat = target.stat()
    parent = target.parent
    parent_mode = stat.S_IMODE(parent.stat().st_mode)
    restore_parent_mode = not parent_mode & stat.S_IWUSR
    if restore_parent_mode:
        parent.chmod(parent_mode | stat.S_IWUSR)
    temporary: Path | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{target.name}.clone-", dir=parent)
        os.close(fd)
        temporary = Path(name)
        temporary.unlink()
        if clone(os.fsencode(source), os.fsencode(temporary), 0) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(target))
        temporary.chmod(stat.S_IMODE(target_stat.st_mode))
        os.utime(temporary, ns=(target_stat.st_atime_ns, target_stat.st_mtime_ns))
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if restore_parent_mode:
            parent.chmod(parent_mode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    audit = json.loads(args.audit_report.read_text())
    allowed_sources = manifest_sources()
    checked: list[dict[str, object]] = []

    def check(item: dict[str, object]) -> dict[str, object]:
        target = Path(str(item["path"]))
        source = Path(str(item["shared"]))
        digest = str(item["sha256"])
        size = int(item["size"])
        result = dict(item)
        result["status"] = "rejected"
        if not any(is_within(target, root) for root in ALLOWED_TARGET_ROOTS):
            result["reason"] = "target-outside-allowed-roots"
        elif not is_within(source, SHARED_ROOT):
            result["reason"] = "source-outside-shared-root"
        elif allowed_sources.get((digest, str(source))) != source:
            result["reason"] = "source-not-in-signed-manifest"
        elif target.is_symlink() or not target.is_file() or target.stat().st_size != size:
            result["reason"] = "target-missing-symlink-or-size-changed"
        elif sha256_file(target) != digest:
            result["reason"] = "target-sha256-changed"
        else:
            result["status"] = "verified"
        return result

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(check, item) for item in audit["matches"]]
        for future in as_completed(futures):
            checked.append(future.result())

    cloned_files = 0
    cloned_bytes = 0
    errors: list[dict[str, object]] = []
    for item in checked:
        if item["status"] != "verified" or not args.apply:
            continue
        target = Path(str(item["path"]))
        source = Path(str(item["shared"]))
        try:
            clonefile(source, target)
            item["status"] = "cloned"
            cloned_files += 1
            cloned_bytes += int(item["size"])
        except Exception as error:
            item["status"] = "error"
            item["reason"] = repr(error)
            errors.append(item)

    report = {
        "format": "ai2apps-checkpoint-clone-dedupe-report",
        "version": 1,
        "mode": "apply" if args.apply else "audit",
        "clonedFiles": cloned_files,
        "clonedBytes": cloned_bytes,
        "errors": errors,
        "items": checked,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("mode", "clonedFiles", "clonedBytes", "errors")}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
