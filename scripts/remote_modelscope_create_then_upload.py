#!/usr/bin/env python3
"""Create a ModelScope model with a long timeout, then run an upload worker."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from modelscope_hub.api import HubApi


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_state(path: Path, **updates: object) -> None:
    value = json.loads(path.read_text()) if path.is_file() else {}
    value.update(updates, updated_at=utc_now())
    temporary = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--ms-hub", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--expected-shards", type=int, required=True)
    parser.add_argument("--license", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--create-timeout", type=int, default=600)
    args = parser.parse_args()

    token = args.token_file.expanduser().read_text().strip()
    if not token:
        raise RuntimeError("ModelScope token file is empty")
    write_state(args.state, status="creating_repo", repo_id=args.repo_id)
    try:
        api = HubApi(token=token)
        api.legacy._timeout = args.create_timeout
        api.create_repo(
            args.repo_id,
            "model",
            visibility="public",
            license=args.license or None,
            description=args.description or None,
        )
        token = ""
        write_state(args.state, status="repo_created")
        command = [
            sys.executable,
            str(args.runner),
            "--source",
            str(args.source),
            "--repo-id",
            args.repo_id,
            "--state",
            str(args.state),
            "--log",
            str(args.log),
            "--token-file",
            str(args.token_file),
            "--ms-hub",
            str(args.ms_hub),
            "--expected-shards",
            str(args.expected_shards),
            "--skip-create",
        ]
        return subprocess.run(command, stdin=subprocess.DEVNULL).returncode
    except Exception as exc:
        token = ""
        write_state(args.state, status="failed", error=str(exc))
        with args.log.open("a") as log:
            log.write(f"[{utc_now()}] create failed: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
