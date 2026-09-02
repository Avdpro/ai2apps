#!/usr/bin/env python3
"""Stage Qwen3.8 Flash Next Q4 over SSH and manage its ModelScope upload."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    "/Users/avdpropang/.omlx/models/"
    "Vontra/Qwen3.8-Flash-Next-MLX-4bit"
)
DEFAULT_HOST = "192.168.1.98"
DEFAULT_REPO = "avdpro/Qwen3.8-Flash-Next-MLX-4bit"
SPEC = (
    ROOT
    / "packages/omlx-model-qwen38-flash-next-4bit/"
    "META/checkpoint-distribution.json"
)
REMOTE_ROOT = "ai2apps-modelscope-staging/qwen3.8-flash-next-mlx-4bit"
LOCAL_JOB = ROOT / "artifacts/modelscope-uploads/qwen38-flash-next-4bit"
EXPECTED_FILES = 33
EXPECTED_SHARDS = 22
EXPECTED_BYTES = 111_601_662_416
BASELINE_BYTES_PER_SECOND = 20_000_000_000 / 3600


def q(value: str | Path) -> str:
    return shlex.quote(str(value))


def run(command: list[str], *, check: bool = True, capture: bool = False):
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def ssh(host: str, command: str, *, capture: bool = False):
    return run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, command],
        capture=capture,
    )


def selected_files(source: Path) -> list[Path]:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    patterns = spec["includePatterns"]
    files = sorted(
        path
        for path in source.iterdir()
        if path.is_file()
        and any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
    )
    missing = [pattern for pattern in patterns if not (source / pattern).is_file()]
    total = sum(path.stat().st_size for path in files)
    if missing:
        raise RuntimeError(f"checkpoint is missing selected files: {missing}")
    if len(files) != EXPECTED_FILES or total != EXPECTED_BYTES:
        raise RuntimeError(
            f"selected checkpoint mismatch: {len(files)} files and {total} bytes"
        )
    return files


def remote_paths() -> dict[str, str]:
    root = f"$HOME/{REMOTE_ROOT}"
    return {
        "root": root,
        "source": f"{root}/checkpoint",
        "job": f"{root}/job",
        "runner": f"{root}/job/remote_modelscope_folder_upload.py",
        "creator": f"{root}/job/remote_modelscope_create_then_upload.py",
        "state": f"{root}/job/state.json",
        "log": f"{root}/job/upload.log",
        "pid": f"{root}/job/upload.pid",
        "token": "$HOME/.modelscope/credentials/api_token",
        "ms_hub": "$HOME/ai2apps-modelscope-staging/.venv/bin/ms-hub",
        "python": "$HOME/ai2apps-modelscope-staging/.venv/bin/python",
    }


def prepare_remote(host: str) -> None:
    paths = remote_paths()
    ssh(host, f"mkdir -p {paths['source']} {paths['job']}")
    run(
        [
            "scp",
            "-q",
            str(ROOT / "scripts/remote_modelscope_folder_upload.py"),
            f"{host}:{REMOTE_ROOT}/job/remote_modelscope_folder_upload.py",
        ]
    )
    run(
        [
            "scp",
            "-q",
            str(ROOT / "scripts/remote_modelscope_create_then_upload.py"),
            f"{host}:{REMOTE_ROOT}/job/remote_modelscope_create_then_upload.py",
        ]
    )


def start_remote_upload(host: str, repo_id: str, *, skip_create: bool = False) -> None:
    paths = remote_paths()
    if skip_create:
        launcher = (
            f"{paths['python']} {paths['runner']} "
            f"--source {paths['source']} --repo-id {q(repo_id)} "
            f"--state {paths['state']} --log {paths['log']} "
            f"--token-file {paths['token']} --ms-hub {paths['ms_hub']} "
            f"--expected-shards {EXPECTED_SHARDS} --skip-create"
        )
    else:
        launcher = (
            f"{paths['python']} {paths['creator']} "
            f"--source {paths['source']} --repo-id {q(repo_id)} "
            f"--state {paths['state']} --log {paths['log']} "
            f"--token-file {paths['token']} --ms-hub {paths['ms_hub']} "
            f"--runner {paths['runner']} "
            f"--expected-shards {EXPECTED_SHARDS} "
            f"--license {q('Qwen-Community-1.0')} "
            f"--description {q('Byte-identical Qwen3.8 Flash Next MLX 4-bit mirror for AI2Apps.')}"
        )
    command = (
        f"test -s {paths['token']} || {{ echo missing_remote_api_token; exit 41; }}; "
        f"if test -f {paths['pid']} && kill -0 $(cat {paths['pid']}) 2>/dev/null; "
        "then echo remote_upload_already_running; exit 0; fi; "
        f"nohup {launcher} "
        f"> {paths['job']}/launcher.log 2>&1 < /dev/null & "
        f"echo $! > {paths['pid']}; echo remote_upload_started=$(cat {paths['pid']})"
    )
    ssh(host, command)


def remote_has_token(host: str) -> bool:
    paths = remote_paths()
    result = ssh(
        host,
        f"if test -s {paths['token']}; then echo yes; else echo no; fi",
        capture=True,
    )
    return result.stdout.strip().splitlines()[-1] == "yes"


def runner(source: Path, host: str, repo_id: str, *, skip_create: bool = False) -> int:
    LOCAL_JOB.mkdir(parents=True, exist_ok=True)
    log_path = LOCAL_JOB / "stage.log"
    state_path = LOCAL_JOB / "stage-state.json"
    files_from = LOCAL_JOB / "files-from.txt"
    files = selected_files(source)
    files_from.write_text("\n".join(path.name for path in files) + "\n")
    state = {
        "status": "staging",
        "source": str(source),
        "host": host,
        "repo_id": repo_id,
        "total_bytes": EXPECTED_BYTES,
        "total_files": EXPECTED_FILES,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
    }
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    try:
        prepare_remote(host)
        with log_path.open("a", buffering=1) as log:
            result = subprocess.run(
                [
                    "rsync",
                    "-aL",
                    "--partial",
                    "--progress",
                    f"--files-from={files_from}",
                    f"{source}/",
                    f"{host}:{REMOTE_ROOT}/checkpoint/",
                ],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        if result.returncode:
            raise RuntimeError(f"rsync failed with exit code {result.returncode}")
        state.update(
            {"status": "staged", "staged_at": datetime.now(timezone.utc).isoformat()}
        )
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        if not remote_has_token(host):
            state.update(
                {
                    "status": "staged_waiting_for_credential",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            return 0
        start_remote_upload(host, repo_id, skip_create=skip_create)
        state.update(
            {
                "status": "remote_upload_started",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        return 0
    except Exception as exc:
        state.update(
            {
                "status": "failed",
                "error": str(exc),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        with log_path.open("a") as log:
            log.write(f"failed: {exc}\n")
        return 1


def start(source: Path, host: str, repo_id: str, *, skip_create: bool = False) -> None:
    source = source.expanduser().resolve(strict=True)
    selected_files(source)
    LOCAL_JOB.mkdir(parents=True, exist_ok=True)
    pid_path = LOCAL_JOB / "stage.pid"
    if pid_path.is_file():
        try:
            os.kill(int(pid_path.read_text().strip()), 0)
        except (OSError, ValueError):
            pass
        else:
            print(f"staging already running with PID {pid_path.read_text().strip()}")
            return
    launcher_log = (LOCAL_JOB / "launcher.log").open("ab")
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_run",
            "--source",
            str(source),
            "--host",
            host,
            "--repo-id",
            repo_id,
            *(["--skip-create"] if skip_create else []),
        ],
        stdin=subprocess.DEVNULL,
        stdout=launcher_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    pid_path.write_text(f"{process.pid}\n")
    print(f"background staging started with PID {process.pid}")
    print(f"status: {Path(__file__).name} status")


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "unknown"
    minutes = int(seconds // 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def status(host: str) -> None:
    paths = remote_paths()
    command = (
        f"{paths['python']} -c "
        + q(
            "import json,pathlib; "
            f"root=pathlib.Path.home()/'{REMOTE_ROOT}'; "
            "src=root/'checkpoint'; state=root/'job/state.json'; "
            "files=[p for p in src.iterdir() if p.is_file()] if src.exists() else []; "
            "d={'staged_bytes':sum(p.stat().st_size for p in files),"
            "'staged_files':len(files),'remote_state':json.loads(state.read_text()) if state.is_file() else None}; "
            "print(json.dumps(d))"
        )
    )
    result = ssh(host, command, capture=True)
    remote = json.loads(result.stdout.strip().splitlines()[-1])
    local_state_path = LOCAL_JOB / "stage-state.json"
    local = json.loads(local_state_path.read_text()) if local_state_path.is_file() else {}
    staged = int(remote.get("staged_bytes") or 0)
    remote_state = remote.get("remote_state") or {}
    uploaded = int(remote_state.get("uploaded_bytes") or 0)
    print(
        f"stage: {staged / 1e9:.2f}/{EXPECTED_BYTES / 1e9:.2f} GB "
        f"({staged / EXPECTED_BYTES:.1%})"
    )
    print(f"stage_files: {remote.get('staged_files', 0)}/{EXPECTED_FILES}")
    print(f"stage_status: {local.get('status', 'unknown')}")
    stage_started = local.get("started_at")
    stage_elapsed = None
    if isinstance(stage_started, str):
        stage_elapsed = time.time() - datetime.fromisoformat(stage_started).timestamp()
    if staged < EXPECTED_BYTES:
        stage_rate = (
            staged / stage_elapsed
            if stage_elapsed and stage_elapsed > 0 and staged > 0
            else None
        )
        print(
            "stage_eta: "
            + format_duration(
                (EXPECTED_BYTES - staged) / stage_rate if stage_rate else None
            )
        )
    if remote_state:
        print(
            f"upload: {uploaded / 1e9:.2f}/{EXPECTED_BYTES / 1e9:.2f} GB "
            f"({uploaded / EXPECTED_BYTES:.1%})"
        )
        print(f"upload_status: {remote_state.get('status')}")
        print(f"current_file: {remote_state.get('current_file')}")
        started = remote_state.get("started_at")
        elapsed = None
        if isinstance(started, str):
            elapsed = time.time() - datetime.fromisoformat(started).timestamp()
        rate = uploaded / elapsed if elapsed and uploaded else BASELINE_BYTES_PER_SECOND
        print(f"upload_eta: {format_duration((EXPECTED_BYTES - uploaded) / rate)}")
    else:
        print("upload_status: waiting_for_staging_or_token")
        print(
            "upload_eta_after_start: "
            + format_duration(EXPECTED_BYTES / BASELINE_BYTES_PER_SECOND)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    start_parser.add_argument("--host", default=DEFAULT_HOST)
    start_parser.add_argument("--repo-id", default=DEFAULT_REPO)
    start_parser.add_argument("--skip-create", action="store_true")
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--host", default=DEFAULT_HOST)
    upload_parser = subparsers.add_parser("start-upload")
    upload_parser.add_argument("--host", default=DEFAULT_HOST)
    upload_parser.add_argument("--repo-id", default=DEFAULT_REPO)
    upload_parser.add_argument("--skip-create", action="store_true")
    run_parser = subparsers.add_parser("_run")
    run_parser.add_argument("--source", type=Path, required=True)
    run_parser.add_argument("--host", required=True)
    run_parser.add_argument("--repo-id", required=True)
    run_parser.add_argument("--skip-create", action="store_true")
    args = parser.parse_args()
    if args.command == "start":
        start(args.source, args.host, args.repo_id, skip_create=args.skip_create)
        return 0
    if args.command == "status":
        status(args.host)
        return 0
    if args.command == "start-upload":
        prepare_remote(args.host)
        start_remote_upload(args.host, args.repo_id, skip_create=args.skip_create)
        return 0
    if args.command == "_run":
        return runner(
            args.source.resolve(strict=True),
            args.host,
            args.repo_id,
            skip_create=args.skip_create,
        )
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
