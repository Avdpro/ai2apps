#!/usr/bin/env python3
"""Wait for the remaining dual-Hub uploads and finalize immutable receipts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download
from modelscope_hub import HubApi


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/chat-checkpoint-migration-20260914"
ITEMS = (
    ("dsv4", "DeepSeek-V4-Flash-SSD"),
    ("dsv4-2bit", "DeepSeek-V4-Flash-2bit-DQ-SSD"),
    ("qwen36", "Qwen3.6-35B-A3B-4bit-SSD"),
    ("ornith15", "Ornith-1.5-35B-A3B-MLX-4bit-Vision-SSD"),
)


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temporary, path)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for value in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(value)
    return digest.hexdigest()


def _wait() -> None:
    while True:
        states = []
        for key, _name in ITEMS:
            for hub in ("hf", "ms"):
                path = BASE / f"{hub}-{key}-upload.json"
                states.append(json.loads(path.read_text()) if path.is_file() else {"status": "pending"})
        failed = [item for item in states if item.get("status") == "failed"]
        if failed:
            raise RuntimeError(f"upload failed: {[item.get('repo') for item in failed]}")
        if all(item.get("status") == "uploaded" for item in states):
            return
        print(json.dumps({"phase": "waiting", "statuses": {item.get("repo", "pending"): item.get("status") for item in states}}), flush=True)
        time.sleep(60)


def _ms_revision(repo: str) -> str:
    result = subprocess.run(
        ["git", "ls-remote", f"https://www.modelscope.cn/{repo}.git", "refs/heads/master"],
        check=True, capture_output=True, text=True,
    )
    revision = result.stdout.split()[0]
    if len(revision) != 40:
        raise ValueError(f"invalid ModelScope revision for {repo}")
    return revision


def _diff(expected: dict, actual: dict) -> dict:
    return {
        "missing": sorted(set(expected) - set(actual)),
        "extra": sorted(set(actual) - set(expected)),
        "mismatch": {
            key: {"expected": expected[key], "actual": actual[key]}
            for key in sorted(set(expected) & set(actual))
            if expected[key] != actual[key]
        },
    }


def _finalize(key: str, name: str, hf: HfApi, ms: HubApi) -> None:
    checkpoint = BASE / name
    hf_repo = f"Avdpro/{name}"
    ms_repo = f"ai2apps/{name}"
    initial_hf_revision = hf.model_info(hf_repo).sha
    remote_attributes = Path(hf_hub_download(hf_repo, ".gitattributes", revision=initial_hf_revision)).read_bytes()
    attributes = checkpoint / ".gitattributes"
    marker = checkpoint / "ssd-checkpoint.json"
    manifest = json.loads(marker.read_text())
    changed = attributes.read_bytes() != remote_attributes
    if changed:
        attributes.write_bytes(remote_attributes)
        manifest["files"][".gitattributes"] = {
            "size": len(remote_attributes),
            "sha256": hashlib.sha256(remote_attributes).hexdigest(),
        }
        _write(marker, manifest)
        hf.create_commit(
            repo_id=hf_repo,
            repo_type="model",
            operations=[
                CommitOperationAdd(path_in_repo=".gitattributes", path_or_fileobj=str(attributes)),
                CommitOperationAdd(path_in_repo="ssd-checkpoint.json", path_or_fileobj=str(marker)),
            ],
            commit_message="Finalize SSD checkpoint metadata manifest",
        )
        ms.upload_folder(
            ms_repo, "model", checkpoint,
            allow_patterns=[".gitattributes", "ssd-checkpoint.json"],
            max_workers=2, use_cache=True, sync_remote_repo=False,
            disable_tqdm=True,
            commit_message="Finalize SSD checkpoint metadata manifest",
        )

    hf_revision = hf.model_info(hf_repo).sha
    ms_revision = _ms_revision(ms_repo)
    manifest = json.loads(marker.read_text())
    expected = {name: {"size": item["size"], "sha256": item["sha256"]} for name, item in manifest["files"].items()}
    expected["ssd-checkpoint.json"] = {"size": marker.stat().st_size, "sha256": _sha(marker)}

    hf_info = hf.model_info(hf_repo, revision=hf_revision, files_metadata=True)
    hf_files = {}
    for item in hf_info.siblings:
        if item.lfs:
            digest = item.lfs.sha256
        else:
            path = Path(hf_hub_download(hf_repo, item.rfilename, revision=hf_revision))
            digest = _sha(path)
        hf_files[item.rfilename] = {"size": item.size, "sha256": digest}
    ms_files = {
        item.path: {"size": item.size, "sha256": item.sha256}
        for item in ms.list_repo_files(ms_repo, "model", revision=ms_revision, recursive=True)
        if not item.is_dir
    }
    hf_diff = _diff(expected, hf_files)
    ms_diff = _diff(expected, ms_files)
    passed = not any(hf_diff.values()) and not any(ms_diff.values())
    receipt = {
        "status": "passed" if passed else "failed",
        "files": len(expected), "bytes": sum(item["size"] for item in expected.values()),
        "hf_repo": hf_repo, "hf_revision": hf_revision,
        "ms_repo": ms_repo, "ms_revision": ms_revision,
        "manifest_sha256": expected["ssd-checkpoint.json"]["sha256"],
        "method": "MS authoritative final-file SHA256 + HF LFS object SHA256/non-LFS downloaded bytes; full file set and size equality; no second full model download",
        "hf_diff": hf_diff, "ms_diff": ms_diff, "verified_at": time.time(),
    }
    _write(BASE / f"{key}-dual-source-verification.json", receipt)
    for hub, revision in (("hf", hf_revision), ("ms", ms_revision)):
        state_path = BASE / f"{hub}-{key}-upload.json"
        state = json.loads(state_path.read_text())
        state.update(
            revision=revision, manifest_sha256=receipt["manifest_sha256"],
            bytes=receipt["bytes"], metadata_updated=changed,
            remote_verified=passed, remote_verified_at=receipt["verified_at"],
        )
        _write(state_path, state)
    print(json.dumps({"phase": "verified", "key": key, **receipt}), flush=True)
    if not passed:
        raise RuntimeError(f"dual-source verification failed for {name}")


def main() -> None:
    _wait()
    hf = HfApi()
    ms = HubApi()
    for key, name in ITEMS:
        _finalize(key, name, hf, ms)
    _write(BASE / "remaining-ssd-upload-complete-20260917.json", {
        "status": "passed", "completed_at": time.time(),
        "items": [key for key, _name in ITEMS],
    })


if __name__ == "__main__":
    main()
