#!/usr/bin/env python3
"""Finish the two outstanding Qwen3.8 ModelScope uploads from this Mac.

The ModelScope write token is read once from stdin and is only passed to
official ``ms-hub`` child processes through their environment.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    "/Users/avdpropang/.omlx/models/"
    "Vontra/Qwen3.8-Flash-Next-MLX-4bit"
)
DEFAULT_REPO = "avdpro/Qwen3.8-Flash-Next-MLX-4bit"
FILES = ("LICENSE", "model-00022-of-00022.safetensors")
JOB_ROOT = ROOT / "artifacts/modelscope-uploads/qwen38-flash-next-4bit-local-finish"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_state(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--repo-id", default=DEFAULT_REPO)
    parser.add_argument("--ms-hub", type=Path, default=ROOT / ".venv/bin/ms-hub")
    args = parser.parse_args()

    source = args.source.expanduser().resolve(strict=True)
    ms_hub = args.ms_hub.expanduser().resolve(strict=True)
    paths = [source / name for name in FILES]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)

    token = sys.stdin.read().strip()
    if len(token) < 20 or not token.isascii() or any(ch.isspace() for ch in token):
        raise RuntimeError("stdin did not contain a valid token-shaped ASCII value")

    JOB_ROOT.mkdir(parents=True, exist_ok=True)
    state_path = JOB_ROOT / "state.json"
    log_path = JOB_ROOT / "upload.log"
    state: dict[str, object] = {
        "status": "uploading",
        "repo_id": args.repo_id,
        "files": [path.name for path in paths],
        "completed_files": [],
        "total_bytes": sum(path.stat().st_size for path in paths),
        "uploaded_bytes": 0,
        "started_at": now(),
        "pid": os.getpid(),
    }
    write_state(state_path, state)

    env = dict(os.environ)
    env["MODELSCOPE_API_TOKEN"] = token
    env["MODELSCOPE_API_TIMEOUT"] = "600"
    # Force even LICENSE through LFS so ModelScope cannot normalize text bytes.
    env["UPLOAD_LFS_ENFORCE_THRESHOLD"] = "1"
    token = ""

    try:
        uploaded = 0
        completed: list[str] = []
        with log_path.open("a", buffering=1) as log:
            for path in paths:
                state.update({"current_file": path.name, "updated_at": now()})
                write_state(state_path, state)
                log.write(f"[{now()}] uploading {path.name} ({path.stat().st_size} bytes)\n")
                result = subprocess.run(
                    [
                        str(ms_hub),
                        "upload",
                        args.repo_id,
                        str(path),
                        path.name,
                        "--repo-type",
                        "model",
                        "--revision",
                        "master",
                        "--commit-message",
                        f"Complete byte-identical mirror: {path.name}",
                        "--max-workers",
                        "4",
                        "--use-cache",
                    ],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                if result.returncode:
                    raise RuntimeError(
                        f"ms-hub failed for {path.name} with exit code {result.returncode}"
                    )
                uploaded += path.stat().st_size
                completed.append(path.name)
                state.update(
                    {
                        "completed_files": completed,
                        "uploaded_bytes": uploaded,
                        "updated_at": now(),
                    }
                )
                write_state(state_path, state)
        env.pop("MODELSCOPE_API_TOKEN", None)
        state.update(
            {
                "status": "complete",
                "current_file": None,
                "completed_at": now(),
                "updated_at": now(),
            }
        )
        write_state(state_path, state)
        return 0
    except Exception as exc:
        env.pop("MODELSCOPE_API_TOKEN", None)
        state.update({"status": "failed", "error": str(exc), "updated_at": now()})
        write_state(state_path, state)
        with log_path.open("a") as log:
            log.write(f"[{now()}] failed: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
