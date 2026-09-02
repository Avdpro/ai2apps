#!/usr/bin/env python3
"""Produce a reproducible Release A acceptance report for Knowledge Core."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from benchmarks.knowledge.evaluate_answers import evaluate_live  # noqa: E402
from benchmarks.knowledge.evaluate_retrieval import evaluate  # noqa: E402

FORMAT = "ai2apps-knowledge-release-a-gate"
VERSION = 1
MODEL_FREE_FLOORS = {
    "recall_at_k": 1.0,
    "mrr": 1.0,
    "citation_precision_at_k": 1.0,
    "no_answer_accuracy": 1.0,
    "answer_citation_precision": 1.0,
    "answer_citation_coverage": 1.0,
    "answer_claim_support": 1.0,
    "citation_authorization_accuracy": 1.0,
}
FOCUSED_TESTS = (
    "tests/test_ai2apps_knowledge_store.py",
    "tests/test_ai2apps_knowledge_retrieval.py",
    "tests/test_ai2apps_knowledge_indexer.py",
    "tests/test_ai2apps_knowledge_platform.py",
    "tests/test_ai2apps_knowledge_eval.py",
    "tests/test_ai2apps_knowledge_answer_eval.py",
    "tests/test_ai2apps_platform_storage.py::test_database_bootstrap_creates_current_platform_schema",
)


def _git_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _source_dirty(root: Path) -> bool | None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return bool(result.stdout) if result.returncode == 0 else None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _focused_tests(root: Path) -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "-q", *FOCUSED_TESTS]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    return {
        "status": "pass" if result.returncode == 0 else "fail",
        "return_code": result.returncode,
        "targets": list(FOCUSED_TESTS),
        "output_tail": output[-8_000:],
    }


def run_gate(
    root: Path,
    *,
    run_tests: bool,
    live_endpoint: str | None = None,
    live_model: str | None = None,
    require_live: bool = False,
) -> dict[str, Any]:
    fixture = root / "benchmarks/knowledge/eval_cases.json"
    answer_cases = root / "benchmarks/knowledge/answer_eval_cases.json"
    metrics = evaluate(fixture, limit=5)
    failed_metrics = {
        key: {"actual": metrics[key], "floor": floor}
        for key, floor in MODEL_FREE_FLOORS.items()
        if float(metrics[key]) < floor
    }
    checks: list[dict[str, Any]] = [
        {
            "id": "model_free_quality",
            "status": "fail" if failed_metrics else "pass",
            "metrics": metrics,
            "floors": MODEL_FREE_FLOORS,
            "failures": failed_metrics,
        }
    ]
    checks.append(
        _focused_tests(root)
        if run_tests
        else {
            "id": "focused_tests",
            "status": "pending",
            "detail": "skipped by operator",
            "targets": list(FOCUSED_TESTS),
        }
    )
    if "id" not in checks[-1]:
        checks[-1]["id"] = "focused_tests"

    live_report = None
    if live_endpoint and live_model:
        try:
            live_report = evaluate_live(
                fixture,
                answer_cases,
                endpoint=live_endpoint,
                model=live_model,
            )
            checks.append(
                {
                    "id": "live_answer_quality",
                    "status": "pass" if live_report["passed"] else "fail",
                    "metrics": live_report["metrics"],
                }
            )
        except Exception as error:
            checks.append(
                {
                    "id": "live_answer_quality",
                    "status": "fail",
                    "detail": str(error),
                }
            )
    else:
        checks.append(
            {
                "id": "live_answer_quality",
                "status": "fail" if require_live else "pending",
                "detail": "provide both --live-endpoint and --live-model",
            }
        )

    failed = [value["id"] for value in checks if value["status"] == "fail"]
    pending = [value["id"] for value in checks if value["status"] == "pending"]
    return {
        "format": FORMAT,
        "version": VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_commit": _git_commit(root),
        "source_dirty": _source_dirty(root),
        "fixture_digests": {
            "eval_cases.json": _sha256(fixture),
            "answer_eval_cases.json": _sha256(answer_cases),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "passed": not failed,
        "release_ready": not failed and not pending,
        "failed_checks": failed,
        "pending_checks": pending,
        "checks": checks,
        "live_answer_report": live_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--live-endpoint", help="OpenAI-compatible /v1 URL")
    parser.add_argument("--live-model")
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.live_endpoint) != bool(args.live_model):
        parser.error("--live-endpoint and --live-model must be provided together")
    report = run_gate(
        args.root.resolve(),
        run_tests=not args.skip_tests,
        live_endpoint=args.live_endpoint,
        live_model=args.live_model,
        require_live=args.require_live,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
