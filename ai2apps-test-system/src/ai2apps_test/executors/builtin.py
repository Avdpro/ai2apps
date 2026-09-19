from __future__ import annotations

import ast
import json
import os
import plistlib
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..model import Case
from ..redact import redact_text

Cancelled = Callable[[], bool]


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    cancelled: bool = False
    timed_out: bool = False


def _stop_process(process: subprocess.Popen[str], *, force: bool = False) -> None:
    with suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    cancelled: Cancelled,
    environment: dict[str, str] | None = None,
) -> ProcessResult:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    while True:
        if cancelled():
            _stop_process(process)
            try:
                stdout, stderr = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                _stop_process(process, force=True)
                stdout, stderr = process.communicate()
            return ProcessResult(
                process.returncode or -signal.SIGTERM,
                stdout,
                stderr,
                cancelled=True,
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _stop_process(process)
            try:
                stdout, stderr = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                _stop_process(process, force=True)
                stdout, stderr = process.communicate()
            return ProcessResult(
                process.returncode or -signal.SIGTERM,
                stdout,
                stderr,
                timed_out=True,
            )
        try:
            stdout, stderr = process.communicate(timeout=min(0.2, remaining))
            return ProcessResult(process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            continue


def _result(status: str, started: float, **values: Any) -> dict[str, Any]:
    return {
        "status": status,
        "durationSeconds": round(time.monotonic() - started, 3),
        **values,
    }


def _python_syntax(
    repo_root: Path, started: float, cancelled: Cancelled
) -> dict[str, Any]:
    failures: list[str] = []
    count = 0
    for root_name in ("ai2apps", "omlx", "ai2apps-test-system/src/ai2apps_test"):
        for path in (repo_root / root_name).rglob("*.py"):
            if cancelled():
                return _result("skipped", started, summary="cancelled by user")
            if "__pycache__" in path.parts:
                continue
            count += 1
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as error:
                failures.append(f"{path.relative_to(repo_root)}: {error}")
    return _result(
        "failed" if failures else "passed",
        started,
        summary=f"parsed {count} Python files",
        failures=failures,
    )


def _json_contracts(
    repo_root: Path, started: float, cancelled: Cancelled
) -> dict[str, Any]:
    failures: list[str] = []
    count = 0
    for pattern in (
        "packages/*/ai2apps.json",
        "packages/*/META/*.json",
        "ai2apps/**/*.json",
    ):
        for path in repo_root.glob(pattern):
            if cancelled():
                return _result("skipped", started, summary="cancelled by user")
            count += 1
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                failures.append(f"{path.relative_to(repo_root)}: {error}")
    return _result(
        "failed" if failures else "passed",
        started,
        summary=f"parsed {count} JSON files",
        failures=failures,
    )


def _yaml_contracts(
    repo_root: Path, started: float, cancelled: Cancelled
) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return _result("blocked", started, summary="PyYAML is unavailable")
    failures: list[str] = []
    count = 0
    patterns = (
        "packages/*/*.yaml",
        "packages/*/META/*.yaml",
        "ai2apps/provisioning/profiles/*.yaml",
    )
    for pattern in patterns:
        for path in repo_root.glob(pattern):
            if cancelled():
                return _result("skipped", started, summary="cancelled by user")
            count += 1
            try:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as error:
                failures.append(f"{path.relative_to(repo_root)}: {error}")
    return _result(
        "failed" if failures else "passed",
        started,
        summary=f"parsed {count} YAML files",
        failures=failures,
    )


def _javascript_syntax(
    repo_root: Path, started: float, cancelled: Cancelled
) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        return _result("blocked", started, summary="node is unavailable")
    failures: list[str] = []
    count = 0
    roots = (repo_root / "ai2apps" / "web" / "static" / "js", repo_root / "packages")
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.js"):
            if cancelled():
                return _result("skipped", started, summary="cancelled by user")
            count += 1
            completed = _run_process(
                [node, "--check", str(path)],
                cwd=repo_root,
                timeout=30,
                cancelled=cancelled,
            )
            if completed.cancelled:
                return _result("skipped", started, summary="cancelled by user")
            if completed.returncode:
                failures.append(
                    f"{path.relative_to(repo_root)}: {redact_text(completed.stderr.strip())}"
                )
    return _result(
        "failed" if failures else "passed",
        started,
        summary=f"checked {count} JavaScript files",
        failures=failures,
    )


def _bundle_identity(
    repo_root: Path, started: float, cancelled: Cancelled
) -> dict[str, Any]:
    app = repo_root / "apps" / "ai2apps-acefox" / ".build" / "AI2Apps-test.app"
    plist_path = app / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return _result(
            "blocked",
            started,
            summary="Test App is missing at apps/ai2apps-acefox/.build/AI2Apps-test.app",
        )
    with plist_path.open("rb") as stream:
        info = plistlib.load(stream)
    expected = {
        "CFBundleIdentifier": "com.ai2apps.desktop.test",
        "AI2AppsInstanceID": "test",
        "AI2AppsRuntimeProfile": "cloud",
    }
    failures = [
        f"{key}: expected {value!r}, got {info.get(key)!r}"
        for key, value in expected.items()
        if info.get(key) != value
    ]
    if info.get("AI2AppsDevelopment"):
        failures.append("AI2AppsDevelopment must not be enabled")
    return _result(
        "failed" if failures else "passed",
        started,
        summary=f"Test App Build {info.get('CFBundleVersion', 'unknown')}",
        failures=failures,
        metadata={
            "app": "apps/ai2apps-acefox/.build/AI2Apps-test.app",
            "build": info.get("CFBundleVersion"),
        },
    )


def _verify_release_app(
    repo_root: Path, started: float, cancelled: Cancelled
) -> dict[str, Any]:
    script = repo_root / "apps" / "ai2apps-acefox" / "scripts" / "verify-release-app.sh"
    app = repo_root / "apps" / "ai2apps-acefox" / ".build" / "AI2Apps-test.app"
    if not script.is_file() or not app.is_dir():
        return _result(
            "blocked", started, summary="release verifier or Test App is missing"
        )
    environment = os.environ.copy()
    environment["APP"] = str(app)
    completed = _run_process(
        [str(script)],
        cwd=repo_root,
        timeout=300,
        cancelled=cancelled,
        environment=environment,
    )
    if completed.cancelled:
        return _result("skipped", started, summary="cancelled by user")
    if completed.timed_out:
        return _result("failed", started, summary="timed out after 300s")
    return _result(
        "passed" if completed.returncode == 0 else "failed",
        started,
        summary=f"release verifier exit code {completed.returncode}",
        output=redact_text(completed.stdout + completed.stderr),
    )


BUILTINS = {
    "static.python-syntax": _python_syntax,
    "static.javascript-syntax": _javascript_syntax,
    "static.json-contracts": _json_contracts,
    "static.yaml-contracts": _yaml_contracts,
    "bundle.test-identity": _bundle_identity,
    "bundle.verify-release-app": _verify_release_app,
}


def execute_builtin(
    repo_root: Path, case: Case, cancelled: Cancelled | None = None
) -> dict[str, Any]:
    started = time.monotonic()
    is_cancelled = cancelled or (lambda: False)
    if is_cancelled():
        return _result("skipped", started, summary="cancelled by user")
    function = BUILTINS.get(case.id)
    if function is None:
        if case.id.startswith("component.package-") and case.id.endswith(".contract"):
            return _result(
                "passed", started, summary="package manifest was discovered and parsed"
            )
        return _result("blocked", started, summary=f"no builtin executor for {case.id}")
    return function(repo_root, started, is_cancelled)


def execute_command(
    repo_root: Path,
    case: Case,
    log_path: Path,
    cancelled: Cancelled | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    is_cancelled = cancelled or (lambda: False)
    if not case.command:
        return _result("blocked", started, summary="command is empty")
    completed = _run_process(
        list(case.command),
        cwd=repo_root,
        timeout=case.timeout_seconds,
        cancelled=is_cancelled,
    )
    output = redact_text(completed.stdout + completed.stderr)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    if completed.cancelled:
        return _result(
            "skipped",
            started,
            summary="cancelled by user",
            evidence=[str(log_path.relative_to(repo_root))],
        )
    if completed.timed_out:
        return _result(
            "failed",
            started,
            summary=f"timed out after {case.timeout_seconds}s",
            details={"outputTail": output[-2000:]},
            evidence=[str(log_path.relative_to(repo_root))],
        )
    return _result(
        "passed" if completed.returncode == 0 else "failed",
        started,
        summary=f"exit code {completed.returncode}",
        exitCode=completed.returncode,
        details={"outputTail": output[-2000:]} if completed.returncode else {},
        evidence=[str(log_path.relative_to(repo_root))],
    )
