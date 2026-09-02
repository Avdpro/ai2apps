#!/usr/bin/env python3
"""Resumable, state-reporting ModelScope folder upload for a remote host."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def checkpoint_files(
    root: Path,
    *,
    expected_shards: int,
    extra_safetensors: tuple[str, ...] = (),
) -> list[Path]:
    index_path = root / "model.safetensors.index.json"
    if not index_path.is_file():
        raise RuntimeError(f"checkpoint index is missing: {index_path}")
    index = json.loads(index_path.read_text())
    weight_map = index.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        raise RuntimeError("checkpoint index has no weight_map")
    shard_names = sorted({str(name) for name in weight_map.values()})
    if len(shard_names) != expected_shards:
        raise RuntimeError(
            f"expected {expected_shards} checkpoint shards, found {len(shard_names)}"
        )
    missing = [name for name in shard_names if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"checkpoint is missing {len(missing)} indexed shards")
    files = [path for path in root.iterdir() if path.is_file()]
    metadata = sorted(
        (path for path in files if path.suffix != ".safetensors"),
        key=lambda path: (
            0 if path.name == "README.md" else 2 if path.name.startswith(".") else 1,
            path.name,
        ),
    )
    extras = set(extra_safetensors)
    if any(Path(name).name != name or not name.endswith(".safetensors") for name in extras):
        raise ValueError("extra safetensors must be plain .safetensors filenames")
    missing_extras = sorted(name for name in extras if not (root / name).is_file())
    if missing_extras:
        raise RuntimeError(f"checkpoint is missing extra safetensors: {missing_extras}")
    weights = sorted(path for path in files if path.suffix == ".safetensors")
    if {path.name for path in weights} != set(shard_names) | extras:
        raise RuntimeError("checkpoint shard set does not match the index")
    return metadata + weights


def run_logged(
    command: list[str], *, env: dict[str, str], log_path: Path
) -> None:
    with log_path.open("a", buffering=1) as log:
        log.write(f"[{utc_now()}] exec: {' '.join(command[:2])} ...\n")
        result = subprocess.run(
            command,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if result.returncode:
        raise RuntimeError(f"command failed with exit code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--ms-hub", type=Path, required=True)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--expected-shards", type=int, default=43)
    parser.add_argument("--extra-safetensors", action="append", default=[])
    parser.add_argument("--license", default="MIT")
    parser.add_argument("--skip-create", action="store_true")
    parser.add_argument("--keep-token", action="store_true")
    parser.add_argument(
        "--description",
        default="GLM-5.3 Flash MLX 4-bit MTP checkpoint mirror for AI2Apps.",
    )
    args = parser.parse_args()

    source = args.source.expanduser().resolve(strict=True)
    token_file = args.token_file.expanduser().resolve(strict=True)
    ms_hub = args.ms_hub.expanduser().resolve(strict=True)
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    if args.max_workers < 1:
        raise ValueError("--max-workers must be positive")

    token = token_file.read_text().strip()
    if not token:
        raise RuntimeError("ModelScope token file is empty")
    env = dict(os.environ)
    env["MODELSCOPE_API_TOKEN"] = token
    # ModelScope's commit endpoint can take longer than the SDK's 60-second
    # default after the blob upload has finished. Use the SDK's documented
    # environment setting for every ms-hub subprocess.
    env.setdefault("MODELSCOPE_API_TIMEOUT", "600")
    token = ""

    if args.expected_shards < 1:
        raise ValueError("--expected-shards must be positive")
    files = checkpoint_files(
        source,
        expected_shards=args.expected_shards,
        extra_safetensors=tuple(args.extra_safetensors),
    )
    if not files:
        raise RuntimeError(f"checkpoint folder is empty: {source}")
    total_bytes = sum(path.stat().st_size for path in files)
    previous = load_json(args.state)
    completed = {
        str(name) for name in previous.get("completed_files", []) if isinstance(name, str)
    }
    uploaded_bytes = sum(
        path.stat().st_size for path in files if path.name in completed
    )
    started_at = str(previous.get("started_at") or utc_now())
    state: dict[str, object] = {
        "status": "starting",
        "repo_id": args.repo_id,
        "source": str(source),
        "total_bytes": total_bytes,
        "uploaded_bytes": uploaded_bytes,
        "completed_files": sorted(completed),
        "total_files": len(files),
        "started_at": started_at,
        "updated_at": utc_now(),
        "pid": os.getpid(),
    }
    write_json(args.state, state)

    try:
        if not args.skip_create:
            create_command = [
                str(ms_hub),
                "create",
                args.repo_id,
                "--repo-type",
                "model",
                "--visibility",
                "public",
                "--exist-ok",
            ]
            if args.license:
                create_command.extend(["--license", args.license])
            if args.description:
                create_command.extend(["--description", args.description])
            run_logged(create_command, env=env, log_path=args.log)
        for path in files:
            if path.name in completed:
                continue
            state.update(
                {
                    "status": "uploading",
                    "current_file": path.name,
                    "current_file_bytes": path.stat().st_size,
                    "uploaded_bytes": uploaded_bytes,
                    "updated_at": utc_now(),
                }
            )
            write_json(args.state, state)
            run_logged(
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
                    f"Mirror {path.name}",
                    "--max-workers",
                    str(args.max_workers),
                    "--use-cache",
                ],
                env=env,
                log_path=args.log,
            )
            completed.add(path.name)
            uploaded_bytes += path.stat().st_size
            state.update(
                {
                    "uploaded_bytes": uploaded_bytes,
                    "completed_files": sorted(completed),
                    "updated_at": utc_now(),
                }
            )
            write_json(args.state, state)

        if not args.keep_token:
            token_file.unlink(missing_ok=True)
        state.update(
            {
                "status": "complete",
                "uploaded_bytes": total_bytes,
                "completed_files": sorted(completed),
                "current_file": None,
                "current_file_bytes": 0,
                "credential_deleted": not args.keep_token,
                "completed_at": utc_now(),
                "updated_at": utc_now(),
            }
        )
        write_json(args.state, state)
        return 0
    except Exception as exc:
        state.update(
            {
                "status": "failed",
                "error": str(exc),
                "updated_at": utc_now(),
            }
        )
        write_json(args.state, state)
        with args.log.open("a") as log:
            log.write(f"[{utc_now()}] failed: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
