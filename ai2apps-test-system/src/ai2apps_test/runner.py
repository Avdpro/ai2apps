from __future__ import annotations

import json
import platform
import subprocess
import sys
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .accounts import (
    TestInstanceResetError,
    acquire_for_run,
    heartbeat_for_run,
    release_for_run,
    requires_account,
    reset_test_instance,
)
from .catalog import (
    build_catalog_bundle,
    catalog_diagnostics,
    catalog_digest,
    select_cases,
)
from .catalog_store import CatalogStore
from .executors.builtin import execute_builtin, execute_command
from .inventory import discover_inventory, inventory_digest
from .model import PRIORITIES, TERMINAL_STATUSES, Case, priority_includes
from .pipeline_actions import execute_pipeline_action
from .redact import redact_text
from .report import write_reports
from .state import (
    append_timeline,
    create_run,
    find_run,
    now_text,
    read_json,
    save_state,
)


def _git_revision(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def doctor(repo_root: Path) -> dict[str, Any]:
    components = discover_inventory(repo_root)
    app = repo_root / "apps" / "ai2apps-acefox" / ".build" / "AI2Apps-test.app"
    checks = {
        "repo": repo_root.is_dir(),
        "catalog": (repo_root / "tests" / "ats" / "catalog" / "base.json").is_file(),
        "testApp": app.is_dir(),
        "python": sys.version_info >= (3, 11),
        "inventory": bool(components),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "componentCount": len(components),
        "testApp": str(app),
        "pythonVersion": platform.python_version(),
    }


def compile_plan(
    repo_root: Path,
    priority: str | None,
    selected_ids: set[str] | None = None,
    groups: set[str] | None = None,
    driver: str = "codex",
    test_data_mode: str = "preserve",
    include_groups: set[str] | None = None,
    include_case_ids: set[str] | None = None,
    excluded_ids: set[str] | None = None,
) -> dict[str, Any]:
    if priority is not None and priority not in PRIORITIES:
        raise ValueError(f"invalid priority: {priority}")
    components = discover_inventory(repo_root)
    catalog_groups, catalog = build_catalog_bundle(repo_root, components)
    cases = select_cases(catalog, priority, selected_ids=selected_ids, groups=groups, include_groups=include_groups, include_case_ids=include_case_ids, excluded_ids=excluded_ids)
    required_ids = [
        case.id
        for case in catalog
        if case.required and priority is not None and priority_includes(priority, case.priority)
    ]
    return {
        "schemaVersion": "ai2apps.test-plan.v1",
        "createdAt": now_text(),
        "priority": priority,
        "driver": driver,
        "testDataMode": test_data_mode,
        "gitRevision": _git_revision(repo_root),
        "inventoryDigest": inventory_digest(components),
        "catalogDigest": catalog_digest(catalog),
        "componentCount": len(components),
        "catalogCaseCount": len(catalog),
        "catalogGroupCount": len(catalog_groups),
        "catalogDiagnostics": catalog_diagnostics(components, catalog, repo_root=repo_root),
        "selection": {"priority": priority, "groupIds": sorted(include_groups or []), "caseIds": sorted(include_case_ids or []), "excludedCaseIds": sorted(excluded_ids or [])},
        "requiredCaseIds": required_ids,
        "cases": [case.to_dict() for case in cases],
    }


def compile_pipeline(
    repo_root: Path, pipeline_id: str, driver: str = "codex"
) -> dict[str, Any]:
    components = discover_inventory(repo_root)
    catalog_groups, catalog = build_catalog_bundle(repo_root, components)
    pipeline = CatalogStore(repo_root).get("pipelines", pipeline_id)
    from .catalog_validation import require_valid, validate_pipeline

    by_id = {case.id: case for case in catalog}
    require_valid(validate_pipeline(pipeline, set(by_id)))
    if not pipeline.get("enabled", True):
        raise ValueError("pipeline is disabled")
    cases: list[dict[str, Any]] = []
    from .pipeline_expansion import expand_pipeline
    expanded, sources = expand_pipeline(pipeline, CatalogStore(repo_root), set(by_id))
    for index, step in enumerate(expanded, start=1):
        step_case_id = f"pipeline.{step['id']}"
        if step["type"] == "action":
            cases.append(
                {
                    "id": step_case_id,
                    "name": f"{index}. {step['action']}",
                    "priority": None,
                    "group": f"Pipeline · {pipeline['name']}",
                    "executor": "pipeline-action",
                    "action": step["action"],
                    "humanInstructions": step.get("humanInstructions", ""),
                    "confirmTimeoutSeconds": step.get("confirmTimeoutSeconds", 120),
                    "loginMode": step.get("loginMode", "none"),
                    "accountEmail": step.get("accountEmail"),
                    "requires": ["test-account"] if step["action"] == "start-helper" and step.get("loginMode", "none") != "none" else [],
                    "required": True,
                    "expectedStatus": "passed",
                    "pipelineStepId": step["id"],
                    "stepEnabled": step.get("enabled", True),
                    "sourceType": "pipeline",
                }
            )
            continue
        source = by_id[step["caseId"]]
        value = source.to_dict()
        mode = step.get('executionMode', 'run' if step.get('enabled', True) else 'skip')
        value.update(
            id=step_case_id,
            name=f"{index}. {value['name']}",
            required=True,
            expectedStatus=step.get("expectedStatus", "passed"),
            sourceCaseId=source.id,
            pipelineStepId=step["id"],
            stepEnabled=mode != 'skip',
            executionMode=mode,
        )
        if mode == 'manual':
            sections = [value['name']]
            for label, field in [('说明', 'description'), ('操作步骤', 'instructions'), ('预期结果', 'expectations'), ('清理动作', 'cleanup'), ('测试素材', 'fixtures')]:
                content = value.get(field)
                if content:
                    sections.append(label + '\n' + ('\n'.join(str(item) for item in content) if isinstance(content, (list, tuple)) else str(content)))
            value.update(executor='pipeline-action', action='human-test',
                         humanInstructions='\n\n'.join(sections),
                         confirmTimeoutSeconds=step.get('confirmTimeoutSeconds', 120))
        cases.append(value)
    for value, step in zip(cases, expanded):
        value.update(step['_origin'])
        if len(step['_origin']['pipelineStepPath']) > 1:
            value['name'] += ' · ' + step['_origin']['sourcePipelineName']
    return {
        "schemaVersion": "ai2apps.test-plan.v1",
        "createdAt": now_text(),
        "priority": None,
        "driver": driver,
        "testDataMode": "pipeline",
        "gitRevision": _git_revision(repo_root),
        "inventoryDigest": inventory_digest(components),
        "catalogDigest": catalog_digest(catalog),
        "componentCount": len(components),
        "catalogCaseCount": len(catalog),
        "catalogGroupCount": len(catalog_groups),
        "catalogDiagnostics": catalog_diagnostics(
            components, catalog, repo_root=repo_root
        ),
        "selection": {"pipelineId": pipeline_id},
        "pipelineSources": sources,
        "pipeline": {
            "id": pipeline_id,
            "name": pipeline["name"],
            "revision": pipeline.get("revision", ""),
        },
        "requiredCaseIds": [case["id"] for case in cases],
        "cases": cases,
    }


def _case_from_dict(value: dict[str, Any]) -> Case:
    return Case(
        id=value["id"],
        name=value["name"],
        priority=value["priority"],
        group=value["group"],
        executor=value["executor"],
        component_id=value.get("componentId", value.get("component_id")),
        command=tuple(value.get("command", [])),
        timeout_seconds=int(value.get("timeoutSeconds", value.get("timeout_seconds", 300))),
        requires=tuple(value.get("requires", [])),
        tags=tuple(value.get("tags", [])),
        description=value.get("description", ""),
        required=bool(value.get("required", True)),
        instructions=tuple(value.get("instructions", [])),
        expectations=tuple(value.get("expectations", [])),
        cleanup=tuple(value.get("cleanup", [])),
        fixtures=tuple(value.get("fixtures", [])),
    )


def _expected_result(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = case.get("expectedStatus")
    if expected in {"stop-when-failed", "stop-when-succeed"}:
        return {**result, "observedStatus": result.get("status"), "expectedStatus": expected}
    if expected not in TERMINAL_STATUSES:
        return result
    observed = result.get("status")
    normalized = {**result, "observedStatus": observed, "expectedStatus": expected}
    if observed == expected:
        normalized["status"] = "passed"
        normalized["summary"] = (
            f"Observed expected {expected}: {result.get('summary', '')}".rstrip()
        )
    elif expected != "passed":
        normalized["status"] = "failed"
        normalized["summary"] = (
            f"Expected {expected}, observed {observed}: {result.get('summary', '')}".rstrip()
        )
    return normalized


def _stop_pipeline_if_matched(
    run_dir: Path, state: dict[str, Any], case: dict[str, Any], result: dict[str, Any]
) -> bool:
    trigger = {"stop-when-failed": "failed", "stop-when-succeed": "passed"}.get(
        case.get("expectedStatus", "")
    )
    if trigger is None or result.get("observedStatus", result.get("status")) != trigger:
        return False
    reason = f"Pipeline 已按 {case['expectedStatus']} 停止：{case['name']} 实际结果为 {trigger}"
    state["pipelineStop"] = {
        "caseId": case["id"], "policy": case["expectedStatus"],
        "observedStatus": trigger, "summary": reason, "stoppedAt": now_text(),
    }
    for remaining in state["plan"]["cases"]:
        if remaining["id"] not in state["results"]:
            state["results"][remaining["id"]] = {
                "status": "skipped", "skipReason": "pipeline-stop",
                "summary": reason, "completedAt": now_text(),
            }
    state["pipelineCursor"] = len(state["plan"]["cases"])
    state.pop("currentCaseId", None)
    state.pop("currentCaseName", None)
    save_state(run_dir, state)
    append_timeline(run_dir, {"event": "pipeline_stopped", **state["pipelineStop"]})
    return True


def _advance_pipeline(
    repo_root: Path,
    run_dir: Path,
    state: dict[str, Any],
    is_cancelled: Callable[[], bool],
    *, defer_human: bool = False,
) -> dict[str, Any]:
    cases = state["plan"]["cases"]
    cursor = int(state.get("pipelineCursor", 0))
    while cursor < len(cases):
        case_data = cases[cursor]
        if case_data["id"] in state["results"]:
            cursor += 1
            continue
        if is_cancelled():
            return state
        if case_data.get("stepEnabled", True) is False:
            state["results"][case_data["id"]] = {
                "status": "skipped", "skipReason": "step-disabled",
                "summary": "步骤未勾选，未执行", "durationSeconds": 0,
                "completedAt": now_text(),
            }
            save_state(run_dir, state)
            cursor += 1
            continue
        if case_data["executor"] == "codex-ui" and state.get("pipelineStartupBlocker"):
            state["results"][case_data["id"]] = {
                "status": "blocked", "observedStatus": "blocked",
                "expectedStatus": case_data.get("expectedStatus", "passed"),
                "summary": "前置启动/登录失败，未执行 UI Case：" + state["pipelineStartupBlocker"],
                "details": {"category": "dependency", "executed": False},
                "completedAt": now_text(), "durationSeconds": 0,
            }
            save_state(run_dir, state)
            cursor += 1
            continue
        if case_data["executor"] == "codex-ui":
            state["pipelineCursor"] = cursor
            state["currentCaseId"] = case_data["id"]
            state["currentCaseName"] = case_data["name"]
            save_state(run_dir, state)
            return state
        if defer_human and case_data['executor'] == 'pipeline-action':
            waiting = 'waiting_human' if case_data.get('action') == 'human-test' else 'waiting_controller'
            state.update(status=waiting, pipelineCursor=cursor,
                         currentCaseId=case_data['id'], currentCaseName=case_data['name'])
            # record_result publishes the handoff with its final state write.
            # Publishing here could let the controller advance before record
            # finishes, then have its new state overwritten by record.
            return state
        state.setdefault("caseStartedAt", {}).setdefault(case_data["id"], now_text())
        append_timeline(
            run_dir, {"event": "pipeline_step_started", "caseId": case_data["id"]}
        )
        state["currentCaseId"] = case_data["id"]
        state["currentCaseName"] = case_data["name"]
        save_state(run_dir, state)
        try:
            if case_data["executor"] == "pipeline-action":
                if case_data['action'] == 'human-test':
                    from .human_action import execute
                    result = execute(run_dir, case_data, is_cancelled)
                    latest = read_json(run_dir / 'state.json')
                    if latest['status'] in {'cancelled', 'cancelling', 'completed'}:
                        return latest
                elif not (case_data['action'] == 'start-helper' and case_data.get('loginMode', 'none') != 'none'):
                    result = execute_pipeline_action(repo_root, str(case_data["action"]), state)
                    latest = read_json(run_dir / 'state.json')
                    if latest['status'] in {'cancelled', 'cancelling', 'completed'}:
                        return latest
                if case_data["action"] == "start-helper" and case_data.get("loginMode", "none") != "none":
                    requested = case_data.get("accountEmail")
                    lease = state.get("testAccountLease", {})
                    if requested and lease.get("status") == "leased" and lease.get("email") != requested:
                        raise ValueError("This Run already leases another account; account switching is not allowed")
                    if not acquire_for_run(repo_root, run_dir, state, only_case_id=case_data["id"], account_email=requested):
                        result = state["results"].pop(case_data["id"])
                        if "accessibility-permission" in result.get("summary", ""):
                            result["summary"] += "；请在 macOS 隐私与安全性→辅助功能中授权负责原生登录的测试进程，然后重试。"
                    else:
                        # Authentication prepares identity before launching the
                        # Test instance. Never launch it just to quit it again.
                        result = execute_pipeline_action(repo_root, 'start-helper', state)
            else:
                case = _case_from_dict(case_data)
                result = (
                    execute_builtin(repo_root, case, is_cancelled)
                    if case.executor == "builtin"
                    else execute_command(
                        repo_root,
                        case,
                        run_dir / "logs" / f"{case.id}.log",
                        is_cancelled,
                    )
                )
        except Exception as error:
            result = {
                "status": "blocked",
                "summary": f"Pipeline step blocked: {redact_text(str(error))}",
            }
        if case_data.get("action") == "start-helper":
            if result.get("status") == "passed":
                state.pop("pipelineStartupBlocker", None)
            else:
                state["pipelineStartupBlocker"] = result.get("summary", "启动失败")
        diagnostics = state.pop('_actionDiagnostics', None)
        if diagnostics is not None:
            from .state import atomic_write_json
            diagnostic_path = f"logs/{case_data['id']}-restart-local.json"
            atomic_write_json(run_dir / diagnostic_path, {'action': 'restart-local', 'events': diagnostics})
            result.setdefault('evidence', []).append(diagnostic_path)
        result = _expected_result(case_data, result)
        result["completedAt"] = now_text()
        _record_timing(state, case_data["id"], result)
        state["results"][case_data["id"]] = result
        if _stop_pipeline_if_matched(run_dir, state, case_data, result):
            return state
        append_timeline(
            run_dir,
            {
                "event": "pipeline_step_completed",
                "caseId": case_data["id"],
                "status": result["status"],
                "observedStatus": result.get("observedStatus", result["status"]),
            },
        )
        cursor += 1
        state["pipelineCursor"] = cursor
        save_state(run_dir, state)
    state.pop("currentCaseId", None)
    state.pop("currentCaseName", None)
    save_state(run_dir, state)
    return state


def start_run(
    repo_root: Path,
    plan: dict[str, Any],
    *,
    cancellation_requested: Callable[[], bool] | None = None,
    on_created: Callable[[str, Path], None] | None = None,
) -> tuple[str, Path, dict[str, Any]]:
    run_id, run_dir, state = create_run(repo_root, plan)
    if on_created is not None:
        on_created(run_id, run_dir)
    is_cancelled = cancellation_requested or (lambda: False)
    state["status"] = "running"
    save_state(run_dir, state)
    append_timeline(run_dir, {"event": "run_started", "priority": plan["priority"]})
    if plan.get("pipeline"):
        state["pipelineCursor"] = 0
        state = _advance_pipeline(repo_root, run_dir, state, is_cancelled)
        if state['status'] in {'completed', 'cancelled', 'cancelling'}:
            return run_id, run_dir, state
        if is_cancelled():
            return cancel_run(repo_root, run_id)
        pending = next_agent_job(state)
        state["status"] = "awaiting_agent" if pending else "ready_to_finalize"
        save_state(run_dir, state)
        write_reports(run_dir, state)
        return run_id, run_dir, state
    if plan.get("testDataMode") == "fresh-install":
        append_timeline(run_dir, {"event": "fresh_install_started"})
        try:
            reset_test_instance(repo_root)
        except TestInstanceResetError as error:
            for case_data in plan["cases"]:
                state["results"][case_data["id"]] = {
                    "status": "blocked",
                    "summary": f"Fresh-install reset blocked: {error}",
                    "completedAt": now_text(),
                }
            state["status"] = "completed"
            save_state(run_dir, state)
            append_timeline(run_dir, {"event": "fresh_install_failed"})
            write_reports(run_dir, state, finalize_pending=True)
            return run_id, run_dir, state
        append_timeline(run_dir, {"event": "fresh_install_completed"})
    for case_data in plan["cases"]:
        if is_cancelled():
            return cancel_run(repo_root, run_id)
        case = _case_from_dict(case_data)
        if case.executor == "codex-ui":
            if plan.get("driver") == "terminal":
                state["results"][case.id] = {
                    "status": "blocked",
                    "summary": "Computer Use case requires the Codex driver",
                    "completedAt": now_text(),
                }
                save_state(run_dir, state)
            continue
        state.setdefault("caseStartedAt", {}).setdefault(case.id, now_text())
        append_timeline(run_dir, {"event": "case_started", "caseId": case.id})
        state["currentCaseId"] = case.id
        state["currentCaseName"] = case.name
        save_state(run_dir, state)
        try:
            if case.executor == "builtin":
                result = execute_builtin(repo_root, case, is_cancelled)
            elif case.executor == "command":
                result = execute_command(
                    repo_root,
                    case,
                    run_dir / "logs" / f"{case.id}.log",
                    is_cancelled,
                )
            else:
                result = {
                    "status": "blocked",
                    "summary": f"unknown executor: {case.executor}",
                }
        except Exception as error:
            detail = redact_text(traceback.format_exc())
            log_path = run_dir / "logs" / f"{case.id}.executor-error.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(detail, encoding="utf-8")
            result = {
                "status": "failed",
                "summary": f"executor error: {type(error).__name__}: {redact_text(str(error))}",
                "details": {"outputTail": detail[-2000:]},
                "evidence": [str(log_path.relative_to(repo_root))],
            }
        result["completedAt"] = now_text()
        state["results"][case.id] = result
        _record_timing(state, case.id, result)
        state.pop("currentCaseId", None)
        state.pop("currentCaseName", None)
        save_state(run_dir, state)
        append_timeline(
            run_dir,
            {"event": "case_completed", "caseId": case.id, "status": result["status"]},
        )
        if is_cancelled():
            return cancel_run(repo_root, run_id)
    pending = next_agent_job(state)
    if pending:
        acquire_for_run(repo_root, run_dir, state)
        pending = next_agent_job(state)
    state["status"] = "awaiting_agent" if pending else "ready_to_finalize"
    if pending:
        state["currentCaseId"] = pending["case"]["id"]
        state["currentCaseName"] = pending["case"]["name"]
    else:
        state.pop("currentCaseId", None)
        state.pop("currentCaseName", None)
    save_state(run_dir, state)
    write_reports(run_dir, state)
    return run_id, run_dir, state


def next_agent_job(state: dict[str, Any]) -> dict[str, Any] | None:
    cases = state["plan"]["cases"]
    if state["plan"].get("pipeline"):
        cursor = int(state.get("pipelineCursor", 0))
        cases = cases[cursor : cursor + 1]
    for case in cases:
        if case["executor"] == "codex-ui" and case["id"] not in state["results"]:
            instructions = [
                "Target only com.ai2apps.desktop.test / instance test.",
                'For Computer Use, use cua.getApp with the Harness-validated shellAppPath supplied by next. Never use an archived App, display name, or the outer AI2Apps-test.app launcher. If shellAppPath is unavailable, record blocked.',
                "On timeout or ambiguity, recheck next and retry only its validated shellAppPath; record target, error and retry outcome. Never switch instances or use the outer launcher.",
                "Read fresh UI state before and after every action.",
                "The privileged AI2Apps Shell chrome is not a BiDi browsing context; use Computer Use for Shell navigation, App/Mini-Entry launching, native UI, visible-state checks, and cross-context drag.",
                "Use the protected AI2Apps WebDriver BiDi Gateway only for a Case that explicitly targets an AI Browser webpage and provides a validated authenticated Test-bound context; never substitute generic Chrome/Firefox BiDi or enumerate generic browser contexts for Shell Cases.",
                "Store evidence under this run directory and record a structured result.",
                "Pipeline human-test actions are completed only by the user in Test Center. Never call /api/human-action, confirm on behalf of the user, or submit their result. The Harness waits for the user and advances the Pipeline.",
                "For TTS/audio-output Cases, read docs/tts-audio-verification.md. Start audio-capture for this Run and current Case; wait for recording before clicking playback. Stop after playback finishes, require captured, then audio-check the recorded WAV against the actual spoken text using local Qwen ASR. Include all returned evidence. Never synthesize replacement audio, capture the microphone, or fall back to a global system mix. Permission, capture, or session problems are blocked; ASR mismatch requires listening review and does not alone prove a TTS defect. Text match does not verify voice quality or physical speaker output.",
                "Uninstall Apps, services, and models through Discover's installed-package management UI.",
                "When uninstalling a model, preserve checkpoint caches unless this Case explicitly requires deleting them. Do not select cache-deletion options or delete checkpoint files as routine cleanup.",
            ]
            if requires_account(case):
                instructions.insert(
                    1,
                    "Use the Harness-managed Test account lease; never read, print, or place its password in a Codex prompt or result.",
                )
            if state["plan"].get("pipeline"):
                instructions.append("Pipeline initial startup and account login are explicit Harness actions. Do not implicitly start an unavailable instance or authenticate it. Exception: when the current Case requires installing a model or Runtime and the Test UI explicitly requests a restart to finish that installation, you may accept that UI restart for the Test instance only. This is installation continuation, not initial startup. Record the restart prompt and installation progress before restarting. Check next immediately before and after; cancellation is terminal. After restart, discard stale Computer Use handles and element IDs, obtain a fresh validated shellAppPath from next, reconnect with cua.getApp(shellAppPath), and read fresh UI state. Confirm Test identity, session readiness and installation completion, then resume the same Case. Never report pass merely because restart succeeded. Do not use arbitrary kill/launch commands, reset data, switch instances, log in manually, or delete checkpoint caches. If restart fails, loops, or the session is unavailable, record evidence and blocked; do not use this exception for unrelated recovery restarts.")
            if case.get("instructions"):
                instructions.extend(f"Case action: {value}" for value in case["instructions"])
            if case.get("fixtures"):
                instructions.extend(
                    f"Managed fixture (relative to the parent product repository): {value}"
                    for value in case["fixtures"]
                )
            if case.get("expectations"):
                instructions.extend(f"Expected result: {value}" for value in case["expectations"])
            if case.get("cleanup"):
                instructions.extend(f"Cleanup: {value}" for value in case["cleanup"])
            if case.get("expectedStatus"):
                instructions.append(
                    "Record only the observed Case outcome. The Pipeline expects "
                    f"{case['expectedStatus']}; the Harness, not Codex, will compare "
                    "that expectation with the observed status."
                )
            return {
                "status": "pending",
                "runId": state["runId"],
                "case": case,
                "instructions": instructions,
            }
    return None


def _record_timing(state: dict[str, Any], case_id: str, result: dict[str, Any]) -> None:
    started = state.get("caseStartedAt", {}).get(case_id)
    if started:
        result["startedAt"] = started
        result["durationSeconds"] = max(0, (datetime.fromisoformat(result["completedAt"]) - datetime.fromisoformat(started)).total_seconds())


def get_next(repo_root: Path, run_id: str) -> dict[str, Any]:
    run_dir = find_run(repo_root, run_id)
    state = read_json(run_dir / "state.json")
    if state.get("status") in {"cancelled", "cancelling"}:
        return {"status": "cancelled", "runId": run_id}
    if state.get('status') == 'waiting_human':
        return {'status': 'waiting_human', 'runId': run_id,
                'message': 'Human step is owned by Test Center. Do not submit a result or finalize. Wait and poll next until pending/done/cancelled.'}
    if state.get('status') == 'waiting_controller':
        return {'status': 'waiting_controller', 'runId': run_id,
                'message': 'Lifecycle action is owned by the host controller. Do not execute it or finalize. Wait and poll next until pending/done/cancelled.'}
    heartbeat_for_run(repo_root, run_dir, state)
    job = next_agent_job(state)
    if job:
        from .shell_target import test_shell_path
        try:
            job["shellAppPath"] = test_shell_path(repo_root)
            job["instructions"].append("Connect using cua.getApp(" + json.dumps(job["shellAppPath"]) + "). This is the validated current Test Shell, not the outer launcher.")
        except (OSError, ValueError) as error:
            job["shellTargetError"] = str(error)
            job["instructions"].append("Test Shell path validation failed; record blocked without connecting to another target.")
        state.setdefault("caseStartedAt", {}).setdefault(job["case"]["id"], now_text())
        save_state(run_dir, state)
    return job or {"status": "done", "runId": run_id}


def record_result(
    repo_root: Path, run_id: str, case_id: str, result: dict[str, Any]
) -> dict[str, Any]:
    run_dir = find_run(repo_root, run_id)
    state = read_json(run_dir / "state.json")
    if state.get("status") in {"cancelled", "cancelling"}:
        raise ValueError("test run was cancelled")
    heartbeat_for_run(repo_root, run_dir, state)
    case_ids = {
        case["id"] for case in state["plan"]["cases"] if case["executor"] == "codex-ui"
    }
    if case_id not in case_ids:
        raise ValueError(f"case is not a Codex UI job in this run: {case_id}")
    if state["plan"].get("pipeline"):
        pending = next_agent_job(state)
        expected_case_id = pending["case"]["id"] if pending else None
        if case_id != expected_case_id:
            raise ValueError(
                "pipeline results must be recorded for the current ordered step: "
                f"{expected_case_id or 'none'}"
            )
    status = result.get("status")
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"invalid result status: {status}")
    evidence = result.get("evidence", [])
    if not isinstance(evidence, list) or not all(
        isinstance(item, str) for item in evidence
    ):
        raise ValueError("evidence must be a list of paths")
    if status in {"passed", "failed"} and not evidence:
        raise ValueError("passed and failed UI results require evidence")
    normalized_evidence: list[str] = []
    for item in evidence:
        path = Path(item)
        if not path.is_absolute():
            path = run_dir / path
        resolved = path.resolve()
        if run_dir.resolve() not in resolved.parents or not resolved.is_file():
            raise ValueError(
                f"evidence must be an existing file inside the run: {item}"
            )
        normalized_evidence.append(str(resolved.relative_to(run_dir.resolve())))
    normalized = {
        "status": status,
        "summary": str(result.get("summary", "")),
        "evidence": normalized_evidence,
        "details": result.get("details", {}),
        "completedAt": now_text(),
    }
    normalized = _expected_result(
        next(case for case in state["plan"]["cases"] if case["id"] == case_id),
        normalized,
    )
    _record_timing(state, case_id, normalized)
    state["results"][case_id] = normalized
    if state["plan"].get("pipeline"):
        case = next(case for case in state["plan"]["cases"] if case["id"] == case_id)
        if not _stop_pipeline_if_matched(run_dir, state, case, normalized):
            state["pipelineCursor"] = int(state.get("pipelineCursor", 0)) + 1
            state = _advance_pipeline(repo_root, run_dir, state, lambda: False, defer_human=True)
            if state['status'] in {'cancelled', 'cancelling', 'completed'}:
                return state
    pending = next_agent_job(state)
    state["status"] = "awaiting_agent" if pending else (state['status'] if state.get('status') in {'waiting_human', 'waiting_controller'} else "ready_to_finalize")
    if pending:
        state["currentCaseId"] = pending["case"]["id"]
        state["currentCaseName"] = pending["case"]["name"]
    elif state['status'] not in {'waiting_human', 'waiting_controller'}:
        state.pop("currentCaseId", None)
        state.pop("currentCaseName", None)
    save_state(run_dir, state)
    append_timeline(
        run_dir,
        {
            "event": "case_completed",
            "caseId": case_id,
            "status": normalized["status"],
            "observedStatus": normalized.get("observedStatus", status),
        },
    )
    write_reports(run_dir, state)
    return normalized


def resume_human_pipeline(repo_root: Path, run_dir: Path, is_cancelled) -> dict[str, Any]:
    state = read_json(run_dir / 'state.json')
    if state.get('status') not in {'waiting_human', 'waiting_controller'}:
        return state
    state = _advance_pipeline(repo_root, run_dir, state, is_cancelled)
    if is_cancelled() or state['status'] in {'cancelled', 'cancelling', 'completed'}:
        return state
    state['status'] = 'awaiting_agent' if next_agent_job(state) else 'ready_to_finalize'
    save_state(run_dir, state)
    write_reports(run_dir, state)
    return state


def finalize_run(repo_root: Path, run_id: str) -> dict[str, Any]:
    run_dir = find_run(repo_root, run_id)
    state = read_json(run_dir / "state.json")
    if state.get("status") == "cancelled":
        return write_reports(run_dir, state, finalize_pending=True)
    if state.get('status') == 'waiting_controller':
        raise ValueError('Pipeline still has pending controller actions')
    # Human checkpoints remain pending after the last Codex UI result. Neither
    # automatic nor explicit finalization may destroy that user's opportunity.
    if state['plan'].get('pipeline') and any(
        case.get('action') == 'human-test' and case['id'] not in state['results']
        and case.get('stepEnabled', True)
        for case in state['plan']['cases']
    ):
        raise ValueError('Pipeline still has pending human steps; complete or cancel them before finalizing')
    for case in state["plan"]["cases"]:
        if case["id"] not in state["results"]:
            state["results"][case["id"]] = {
                "status": "blocked",
                "summary": "case was not executed",
                "completedAt": now_text(),
            }
    release_for_run(repo_root, run_dir, state)
    state["status"] = "completed"
    save_state(run_dir, state)
    append_timeline(run_dir, {"event": "run_finalized"})
    return write_reports(run_dir, state, finalize_pending=True)


def cancel_run(
    repo_root: Path, run_id: str
) -> tuple[str, Path, dict[str, Any]]:
    run_dir = find_run(repo_root, run_id)
    state = read_json(run_dir / "state.json")
    if state.get("status") == "cancelled":
        return run_id, run_dir, state
    for case in state["plan"]["cases"]:
        if case["id"] not in state["results"]:
            state["results"][case["id"]] = {
                "status": "skipped",
                "summary": "cancelled by user",
                "completedAt": now_text(),
            }
    release_for_run(repo_root, run_dir, state)
    state.pop("currentCaseId", None)
    state.pop("currentCaseName", None)
    state["status"] = "cancelled"
    state["cancelledAt"] = now_text()
    save_state(run_dir, state)
    append_timeline(run_dir, {"event": "run_cancelled"})
    write_reports(run_dir, state, finalize_pending=True)
    return run_id, run_dir, state
