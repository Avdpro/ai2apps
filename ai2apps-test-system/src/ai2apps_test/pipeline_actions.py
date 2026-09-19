from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from ai2apps.helper_control import HelperControlClient, HelperControlError

from .accounts import (
    TestAccountError,
    TestAppAccountSession,
    TestInstanceResetError,
    default_manager,
    reset_test_instance,
)


class PipelineActionError(RuntimeError):
    pass


def _native(session: TestAppAccountSession, operation: str) -> None:
    try:
        completed = subprocess.run(
            [str(session._native_helper_binary())],
            input=json.dumps({"operation": operation}),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PipelineActionError(f"{operation} could not be completed") from error
    if completed.returncode or completed.stdout.strip() != operation:
        raise PipelineActionError(f"{operation} was not confirmed")


def _helper_client(session: TestAppAccountSession, timeout_seconds: float) -> HelperControlClient:
    endpoint = session.support / "run" / "helper-control.json"
    token_path = session.support / "run" / "helper-control.token"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            token = token_path.read_text(encoding="utf-8").strip()
            return HelperControlClient(
                endpoint_path=str(endpoint),
                token=token,
                timeout_seconds=min(3, timeout_seconds),
            )
        except OSError as error:
            last_error = error
            time.sleep(0.2)
    raise PipelineActionError("Test Helper control channel is unavailable") from last_error


def _process_pid(session: TestAppAccountSession, descriptor: str) -> int | None:
    try:
        value = json.loads((session.support / "run" / descriptor).read_text())
        if value.get("instance_id") != "test":
            return None
        pid = int(value["pid"])
        os.kill(pid, 0)
        return pid
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _local_pid(session: TestAppAccountSession) -> int | None:
    return _process_pid(session, "local.json")


def _wait_new_local(
    session: TestAppAccountSession, previous_pid: int | None, timeout_seconds: float
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        pid = _local_pid(session)
        if pid is not None and (previous_pid is None or pid != previous_pid):
            return
        time.sleep(0.2)
    raise PipelineActionError("Test Local did not become ready after the action")


def _wait_new_shell(
    session: TestAppAccountSession, previous_pid: int | None, timeout_seconds: float
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        pid = _process_pid(session, "shell.json")
        if pid is not None and (previous_pid is None or pid != previous_pid):
            return
        time.sleep(0.2)
    raise PipelineActionError("Test Shell did not become ready after the action")


def execute_pipeline_action(
    repo_root: Path,
    action: str,
    state: dict[str, Any],
    *,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    session = TestAppAccountSession(repo_root, timeout_seconds=timeout_seconds)
    try:
        if action == "restart-local":
            session._launch()
            previous = _local_pid(session)
            _helper_client(session, timeout_seconds).restart_local(
                actor_user_id="ai2apps-test-harness"
            )
            _wait_new_local(session, previous, timeout_seconds)
        elif action == "restart-app":
            previous = _process_pid(session, "shell.json")
            _native(session, "quit-shell")
            session._launch()
            _wait_new_shell(session, previous, timeout_seconds)
        elif action == "quit-all-relaunch":
            _native(session, "quit")
            session._launch()
            _wait_new_local(session, None, timeout_seconds)
            _wait_new_shell(session, None, timeout_seconds)
        elif action == "reset-data":
            reset_test_instance(repo_root, timeout_seconds=timeout_seconds)
            session._launch()
            _wait_new_local(session, None, timeout_seconds)
            _wait_new_shell(session, None, timeout_seconds)
            lease = state.get("testAccountLease")
            if isinstance(lease, dict) and lease.get("status") == "leased":
                default_manager(repo_root).authenticate(
                    repo_root, str(state["runId"]), lease
                )
        else:
            raise PipelineActionError(f"unsupported pipeline action: {action}")
    except (HelperControlError, TestAccountError, TestInstanceResetError) as error:
        raise PipelineActionError(str(error)) from error
    return {"status": "passed", "summary": f"Pipeline action completed: {action}"}
