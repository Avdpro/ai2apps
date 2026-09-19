from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_text() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def runs_root(repo_root: Path) -> Path:
    return repo_root / "ai2apps-test-system" / "artifacts" / "runs"


def create_run(
    repo_root: Path, plan: dict[str, Any]
) -> tuple[str, Path, dict[str, Any]]:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{os.getpid()}"
    run_dir = runs_root(repo_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    state = {
        "schemaVersion": "ai2apps.test-run.v1",
        "runId": run_id,
        "status": "created",
        "createdAt": now_text(),
        "updatedAt": now_text(),
        "plan": plan,
        "results": {},
    }
    atomic_write_json(run_dir / "plan.json", plan)
    atomic_write_json(run_dir / "state.json", state)
    return run_id, run_dir, state


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updatedAt"] = now_text()
    atomic_write_json(run_dir / "state.json", state)


def append_timeline(run_dir: Path, event: dict[str, Any]) -> None:
    payload = {"at": now_text(), **event}
    with (run_dir / "timeline.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def find_run(repo_root: Path, run_id: str) -> Path:
    if not run_id or "/" in run_id or ".." in run_id:
        raise ValueError("invalid run ID")
    run_dir = runs_root(repo_root) / run_id
    if not (run_dir / "state.json").is_file():
        raise FileNotFoundError(f"test run not found: {run_id}")
    return run_dir
