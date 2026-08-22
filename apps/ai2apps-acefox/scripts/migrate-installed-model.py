#!/usr/bin/env python3
"""Explicitly migrate one trusted installed model into an AI2Apps model root."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import stat
import uuid
from pathlib import Path

REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REVISION = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise SystemExit(f"migrate-installed-model: {message}")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path.name}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path.name} must contain an object")
    return value


def validate_source(source: Path, repo_id: str, revision: str) -> dict[str, int]:
    if not REPO_ID.fullmatch(repo_id):
        fail("repo-id is invalid")
    if not REVISION.fullmatch(revision):
        fail("revision must be a pinned lowercase 40-hex commit")
    if source.is_symlink() or not source.is_dir():
        fail("source must be a real directory")
    if not (source / "config.json").is_file():
        fail("source is missing config.json")
    if not any(source.glob("model*.safetensors")):
        fail("source is missing model safetensors")

    source_contract = source / ".ai2apps" / "source.json"
    if source_contract.exists():
        contract = load_json(source_contract)
        if contract.get("repo_id") != repo_id or contract.get("revision") != revision:
            fail("source contract does not match the explicit repo/revision")
    install_contract = source / "ai2apps-model.json"
    if install_contract.exists():
        contract = load_json(install_contract)
        declared = contract.get("source")
        if not isinstance(declared, dict):
            fail("install manifest source is invalid")
        if declared.get("repo_id") != repo_id or declared.get("revision") != revision:
            fail("install manifest does not match the explicit repo/revision")

    files = 0
    links = 0
    logical_bytes = 0
    for root, directories, names in os.walk(source, followlinks=False):
        root_path = Path(root)
        for name in directories:
            candidate = root_path / name
            if candidate.is_symlink():
                fail("directory symlinks are not accepted")
        for name in names:
            candidate = root_path / name
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                target = candidate.resolve(strict=True)
                target_metadata = target.stat()
                if not stat.S_ISREG(target_metadata.st_mode):
                    fail("every symlink must resolve to a regular file")
                links += 1
                logical_bytes += target_metadata.st_size
            elif stat.S_ISREG(metadata.st_mode):
                logical_bytes += metadata.st_size
            else:
                fail("source contains a non-regular file")
            files += 1
    return {"files": files, "materialized_links": links, "logical_bytes": logical_bytes}


def clone_file(source: Path, destination: Path, allow_full_copy: bool) -> None:
    clonefile = getattr(ctypes.CDLL(None, use_errno=True), "clonefile", None)
    if clonefile is not None:
        clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        clonefile.restype = ctypes.c_int
        if clonefile(os.fsencode(source), os.fsencode(destination), 0) == 0:
            return
        error = ctypes.get_errno()
    else:
        error = 0
    if not allow_full_copy:
        fail(
            "APFS clone failed"
            + (f" with errno {error}" if error else "")
            + "; rerun with --allow-full-copy only if a full copy is intended"
        )
    shutil.copyfile(source, destination, follow_symlinks=True)


def copy_tree(source: Path, staging: Path, allow_full_copy: bool) -> None:
    staging.mkdir(mode=0o700)
    for root, directories, names in os.walk(source, followlinks=False):
        relative = Path(root).relative_to(source)
        destination_root = staging / relative
        for name in directories:
            (destination_root / name).mkdir(mode=0o700)
        for name in names:
            source_file = Path(root) / name
            resolved_source = source_file.resolve(strict=True) if source_file.is_symlink() else source_file
            destination_file = destination_root / name
            clone_file(resolved_source, destination_file, allow_full_copy)
            destination_file.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-full-copy", action="store_true")
    args = parser.parse_args()

    source = args.source.expanduser().absolute()
    destination_root = args.destination_root.expanduser().absolute()
    inventory = validate_source(source, args.repo_id, args.revision)
    destination = destination_root.joinpath(*args.repo_id.split("/"))
    if destination.exists() or destination.is_symlink():
        fail("destination model already exists")

    result = {
        "schema": "ai2apps.manual-model-migration/v1",
        "status": "validated" if not args.execute else "migrated",
        "repo_id": args.repo_id,
        "revision": args.revision,
        **inventory,
    }
    if not args.execute:
        print(json.dumps(result, sort_keys=True))
        return

    destination_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination_root.chmod(0o700)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if parent.is_symlink():
        fail("destination parent must be a real directory")
    staging = parent / f".{destination.name}.migration-{uuid.uuid4().hex}"
    try:
        copy_tree(source, staging, args.allow_full_copy)
        copied = validate_source(staging, args.repo_id, args.revision)
        if copied != inventory:
            fail("post-copy inventory does not match the source")
        source_contract = staging / ".ai2apps" / "source.json"
        source_contract.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source_contract.write_text(
            json.dumps(
                {
                    "format": "ai2apps-hf-source",
                    "version": 1,
                    "repo_id": args.repo_id,
                    "revision": args.revision,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        source_contract.chmod(0o600)
        os.rename(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
