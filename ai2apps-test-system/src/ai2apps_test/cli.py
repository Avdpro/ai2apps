from __future__ import annotations

import argparse
import getpass
import json
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from .accounts import (
    BROKER_TOKEN_KEY,
    clear_broker_token,
    configure_broker_token,
    default_manager,
    heartbeat_for_run,
    keychain_vault,
    load_pool,
    release_for_run,
)
from .catalog import (
    build_catalog_bundle,
    catalog_diagnostics,
    group_catalog,
    migrate_base_catalog,
)
from .catalog_store import CatalogStore
from .codex_driver import CodexDriverError, CodexDriverProcess, start_codex_driver
from .inventory import discover_inventory
from .model import Case
from .report import write_reports
from .runner import (
    cancel_run,
    compile_pipeline,
    compile_plan,
    doctor,
    finalize_run,
    get_next,
    record_result,
    resume_human_pipeline,
    start_run,
)
from .selector import control
from .state import append_timeline, find_run, now_text, read_json, save_state


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai2apps-test")
    parser.add_argument(
        "--fresh-install",
        dest="root_fresh_install",
        action="store_true",
        help="open the default selector and reset the Test instance before running",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor")
    capture = subparsers.add_parser("audio-capture")
    capture.add_argument("action", choices=("permission", "start", "status", "stop"))
    capture.add_argument("--run")
    capture.add_argument("--case")
    capture.add_argument("--capture")
    capture.add_argument("--seconds", type=int, default=120)
    audio = subparsers.add_parser("audio-check")
    audio.add_argument("--run", required=True)
    audio.add_argument("--audio", type=Path, required=True)
    audio.add_argument("--checkpoint", type=Path)
    audio.add_argument("--expected-text", required=True)
    audio.add_argument("--language", default="Chinese")
    plan = subparsers.add_parser("plan")
    plan.add_argument("--priority", choices=("P0", "P1", "P2", "P3"), default="P1")
    plan.add_argument("--group", action="append", default=[])
    plan.add_argument("--case", action="append", default=[])
    plan.add_argument("--exclude-case", action="append", default=[])
    plan.add_argument("--fresh-install", action="store_true")
    run = subparsers.add_parser("run")
    run.add_argument("--priority", choices=("P0", "P1", "P2", "P3"), default="P1")
    run.add_argument("--driver", choices=("codex", "terminal"), default="codex")
    run.add_argument("--group", action="append", default=[])
    run.add_argument("--case", action="append", default=[])
    run.add_argument("--exclude-case", action="append", default=[])
    run.add_argument("--selected-file", type=Path)
    run.add_argument("--unattended", action="store_true")
    run.add_argument("--fresh-install", action="store_true")
    select = subparsers.add_parser("select")
    select.add_argument("--priority", choices=("P0", "P1", "P2", "P3"), default="P1")
    select.add_argument("--driver", choices=("codex", "terminal"), default="codex")
    select.add_argument("--no-open", action="store_true")
    select.add_argument("--fresh-install", action="store_true")
    next_parser = subparsers.add_parser("next")
    next_parser.add_argument("--run", required=True)
    record = subparsers.add_parser("record")
    record.add_argument("--run", required=True)
    record.add_argument("--case", required=True)
    record.add_argument("--result", type=Path, required=True)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--run", required=True)
    report = subparsers.add_parser("report")
    report.add_argument("--run", required=True)
    report.add_argument("--open", action="store_true")
    account = subparsers.add_parser("account")
    account.add_argument(
        "action", choices=("doctor", "configure", "clear", "heartbeat", "cleanup")
    )
    account.add_argument("--run")
    catalog = subparsers.add_parser("catalog")
    catalog_actions = catalog.add_subparsers(dest="catalog_action", required=True)
    catalog_list = catalog_actions.add_parser("list")
    catalog_list.add_argument("--archived", action="store_true")
    catalog_actions.add_parser("validate")
    catalog_actions.add_parser("diagnostics")
    review_inventory = catalog_actions.add_parser("review-inventory")
    review_inventory.add_argument("--apply", action="store_true")
    migrate = catalog_actions.add_parser("migrate")
    migrate.add_argument("--check", action="store_true")
    migrate.add_argument("--apply", action="store_true")
    pipeline = subparsers.add_parser("pipeline")
    pipeline_actions = pipeline.add_subparsers(dest="pipeline_action", required=True)
    pipeline_actions.add_parser("list")
    pipeline_plan = pipeline_actions.add_parser("plan")
    pipeline_plan.add_argument("--id", required=True)
    pipeline_run = pipeline_actions.add_parser("run")
    pipeline_run.add_argument("--id", required=True)
    pipeline_run.add_argument("--driver", choices=("codex", "terminal"), default="codex")
    pipeline_run.add_argument("--unattended", action="store_true")
    return parser


def _parse_args(
    parser: argparse.ArgumentParser, argv: list[str] | None = None
) -> argparse.Namespace:
    args = parser.parse_args(argv)
    if args.command is None:
        default_argv = ["select"]
        if args.root_fresh_install:
            default_argv.append("--fresh-install")
        return parser.parse_args(default_argv)
    if args.root_fresh_install:
        if not hasattr(args, "fresh_install"):
            parser.error("--fresh-install requires plan, run, select, or no command")
        args.fresh_install = True
    return args


def _selected_ids(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("selected", payload) if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        raise ValueError("selected file must contain a list of case IDs")
    return set(values)


def _run(
    repo_root: Path,
    priority: str,
    driver: str,
    selected: set[str] | None,
    groups: set[str] | None,
    unattended: bool,
    fresh_install: bool,
    include_case_ids: set[str] | None = None,
    excluded_ids: set[str] | None = None,
    pipeline_id: str | None = None,
) -> int:
    response = _execute_run(
        repo_root,
        priority,
        driver,
        selected,
        groups,
        wait_for_ui=unattended,
        fresh_install=fresh_install,
        include_case_ids=include_case_ids,
        excluded_ids=excluded_ids,
        pipeline_id=pipeline_id,
    )
    _print(response)
    if response.get("conclusion") in {"PASS", "SCOPED_PASS"}:
        return 0
    return 2 if response.get("status") in {"awaiting_agent", "blocked"} else 1


def _execute_run(
    repo_root: Path,
    priority: str,
    driver: str,
    selected: set[str] | None,
    groups: set[str] | None,
    *,
    cancel_event: threading.Event | None = None,
    on_created: Any = None,
    wait_for_ui: bool = False,
    fresh_install: bool = False,
    include_case_ids: set[str] | None = None,
    excluded_ids: set[str] | None = None,
    trial_case: dict[str, Any] | None = None,
    pipeline_id: str | None = None,
) -> dict[str, Any]:
    driver_process: CodexDriverProcess | None = None
    driver_exit_recorded = False

    def update_driver(value: dict[str, Any], event: str) -> dict[str, Any]:
        latest = read_json(run_dir / "state.json")
        latest["codexDriver"] = value
        save_state(run_dir, latest)
        append_timeline(run_dir, {"event": event, **value})
        write_reports(run_dir, latest)
        return latest

    def stop_driver() -> None:
        nonlocal driver_process
        if driver_process is None:
            return
        driver_process.stop()
        driver_process = None

    health = doctor(repo_root)
    if not health["ok"]:
        return {"status": "blocked", "doctor": health, "conclusion": "BLOCKED"}
    plan = (
        compile_pipeline(repo_root, pipeline_id, driver)
        if pipeline_id
        else compile_plan(
            repo_root,
            priority,
            selected_ids=selected,
            include_groups=groups,
            include_case_ids=include_case_ids,
            excluded_ids=excluded_ids,
            driver=driver,
            test_data_mode="fresh-install" if fresh_install else "preserve",
        )
    )
    if trial_case is not None:
        group = CatalogStore(repo_root).get("groups", str(trial_case.get("groupId", "")))
        trial = Case(
            id=str(trial_case["id"]), name=str(trial_case["name"]), priority=trial_case.get("priority"), group=str(group["name"]),
            executor=str(trial_case["executor"]), component_id=trial_case.get("componentId"), timeout_seconds=int(trial_case.get("timeoutSeconds", 300)),
            requires=tuple(trial_case.get("requires", [])), tags=tuple(trial_case.get("tags", [])), description=str(trial_case.get("description", "")), required=False,
            group_id=str(trial_case["groupId"]), enabled=True, lifecycle="trial", source_type="user-authored", source_path=str(trial_case.get("sourcePath", "")), editable=True,
            instructions=tuple(trial_case.get("instructions", [])), expectations=tuple(trial_case.get("expectations", [])), cleanup=tuple(trial_case.get("cleanup", [])), fixtures=tuple(trial_case.get("fixtures", [])), revision=str(trial_case.get("revision", "")),
        )
        plan["cases"] = [trial.to_dict()]
        plan["requiredCaseIds"] = []
        plan["trialRun"] = True
    is_cancelled = cancel_event.is_set if cancel_event is not None else None
    run_id, run_dir, state = start_run(
        repo_root,
        plan,
        cancellation_requested=is_cancelled,
        on_created=on_created,
    )
    if state["status"] == "cancelled":
        result = read_json(run_dir / "result.json")
        return {
            "runId": run_id,
            "status": "cancelled",
            "conclusion": result["conclusion"],
            "runDirectory": str(run_dir),
            "report": str(run_dir / "report.html"),
        }
    pending_ui = any(
        case["executor"] == "codex-ui" and case["id"] not in state["results"]
        for case in plan["cases"]
    )
    if pending_ui and wait_for_ui:
        driver_start_failed = False
        if driver == "codex":
            try:
                driver_process = start_codex_driver(repo_root, run_id, run_dir)
                state = update_driver(
                    driver_process.public_state(), "codex_driver_started"
                )
            except (CodexDriverError, OSError) as error:
                driver_start_failed = True
                state = update_driver(
                    {
                        "status": "failed",
                        "summary": str(error),
                        "failedAt": now_text(),
                    },
                    "codex_driver_start_failed",
                )
        if driver_start_failed and cancel_event is None:
            return {
                "runId": run_id,
                "status": "awaiting_agent",
                "conclusion": "RUNNING",
                "runDirectory": str(run_dir),
                "report": str(run_dir / "report.html"),
                "nextCommand": f"./bin/ai2apps-test next --run {run_id}",
            }
        while True:
            if cancel_event is not None and cancel_event.wait(timeout=0.2):
                stop_driver()
                _, _, state = cancel_run(repo_root, run_id)
                result = read_json(run_dir / "result.json")
                return {
                    "runId": run_id,
                    "status": state["status"],
                    "conclusion": result["conclusion"],
                    "runDirectory": str(run_dir),
                    "report": str(run_dir / "report.html"),
                }
            if cancel_event is None:
                time.sleep(0.2)
            state = read_json(run_dir / "state.json")
            if state.get('status') in {'waiting_human', 'waiting_controller'}:
                state = resume_human_pipeline(repo_root, run_dir,
                    lambda: cancel_event is not None and cancel_event.is_set())
                if cancel_event is not None and cancel_event.is_set():
                    continue
                if (driver == 'codex' and driver_process is not None
                        and driver_process.poll() is not None
                        and any(case['executor'] == 'codex-ui' and case['id'] not in state['results'] for case in plan['cases'])):
                    driver_process.close_log()
                    try:
                        driver_process = start_codex_driver(repo_root, run_id, run_dir)
                        driver_exit_recorded = False
                        state = update_driver(driver_process.public_state(), 'codex_driver_restarted_after_human')
                    except (CodexDriverError, OSError) as error:
                        driver_process = None
                        state = update_driver({'status':'failed', 'summary':str(error)}, 'codex_driver_start_failed')
            if state["status"] == "cancelled":
                stop_driver()
                result = read_json(run_dir / "result.json")
                return {
                    "runId": run_id,
                    "status": "cancelled",
                    "conclusion": result["conclusion"],
                    "runDirectory": str(run_dir),
                    "report": str(run_dir / "report.html"),
                }
            pending_ui = any(
                case["executor"] == "codex-ui"
                and case["id"] not in state["results"]
                for case in plan["cases"]
            )
            if driver_process is not None and not driver_exit_recorded:
                exit_code = driver_process.poll()
                if exit_code is not None:
                    driver_process.close_log()
                    driver_exit_recorded = True
                    state = read_json(run_dir / "state.json")
                    pending_ui = any(
                        case["executor"] == "codex-ui"
                        and case["id"] not in state["results"]
                        for case in plan["cases"]
                    )
                    previous = state.get("codexDriver", {})
                    driver_state = {
                        **previous,
                        "status": "completed" if exit_code == 0 else "failed",
                        "exitCode": exit_code,
                        "finishedAt": now_text(),
                    }
                    if pending_ui:
                        driver_state["status"] = "failed"
                        driver_state["summary"] = (
                            "Codex exited before completing every selected UI Case; "
                            "manual takeover is available"
                        )
                    state = update_driver(driver_state, "codex_driver_exited")
                    if pending_ui and cancel_event is None:
                        return {
                            "runId": run_id,
                            "status": "awaiting_agent",
                            "conclusion": "RUNNING",
                            "runDirectory": str(run_dir),
                            "report": str(run_dir / "report.html"),
                            "nextCommand": (
                                f"./bin/ai2apps-test next --run {run_id}"
                            ),
                        }
            if not pending_ui and not any(case['id'] not in state['results'] for case in plan['cases']):
                result = finalize_run(repo_root, run_id)
                if driver_process is not None and not driver_exit_recorded:
                    exit_code = driver_process.wait(timeout=10)
                    if exit_code is None:
                        stop_driver()
                        status = "stopped"
                        summary = "Codex completed every UI Case but did not exit promptly"
                    else:
                        driver_process.close_log()
                        status = "completed" if exit_code == 0 else "failed"
                        summary = ""
                    latest = read_json(run_dir / "state.json")
                    driver_state = {
                        **latest.get("codexDriver", {}),
                        "status": status,
                        "finishedAt": now_text(),
                        **({"exitCode": exit_code} if exit_code is not None else {}),
                        **({"summary": summary} if summary else {}),
                    }
                    update_driver(driver_state, "codex_driver_exited")
                return {
                    "runId": run_id,
                    "status": "completed",
                    "conclusion": result["conclusion"],
                    "runDirectory": str(run_dir),
                    "report": str(run_dir / "report.html"),
                }
    if not pending_ui and not any(case['id'] not in state['results'] for case in plan['cases']):
        result = finalize_run(repo_root, run_id)
        state["status"] = "completed"
    else:
        result = {"conclusion": "RUNNING"}
    response = {
        "runId": run_id,
        "status": state["status"],
        "conclusion": result["conclusion"],
        "runDirectory": str(run_dir),
        "report": str(run_dir / "report.html"),
        "nextCommand": f"./bin/ai2apps-test next --run {run_id}"
        if pending_ui
        else f"./bin/ai2apps-test finalize --run {run_id}",
    }
    return response


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = _parse_args(parser, argv)
    repo_root = _repo_root()
    if args.command == "audio-capture":
        from . import audio_capture
        if args.action == "permission":
            value = audio_capture.permission()
        else:
            if not args.run:
                parser.error("audio-capture requires --run")
            directory = find_run(repo_root, args.run)
            if args.action == "start":
                if not args.case:
                    parser.error("audio-capture start requires --case")
                value = audio_capture.start(repo_root, directory, args.case, args.seconds)
            else:
                if not args.capture:
                    parser.error("audio-capture stop/status requires --capture")
                value = getattr(audio_capture, args.action)(directory, args.capture)
        _print(value)
        return 0 if value["status"] in {"ready", "recording", "captured"} else 2
    if args.command == "audio-check":
        from .audio_check import check_audio, discover_checkpoint
        value = check_audio(find_run(repo_root, args.run), args.audio, args.checkpoint or discover_checkpoint(),
                            args.expected_text, args.language)
        _print(value)
        return 0 if value["status"] == "content-matched" else 2
    if args.command == "doctor":
        value = doctor(repo_root)
        _print(value)
        return 0 if value["ok"] else 2
    if args.command == "plan":
        _print(
            compile_plan(
                repo_root,
                args.priority,
                include_groups=set(args.group) or None,
                include_case_ids=set(args.case) or None,
                excluded_ids=set(args.exclude_case) or None,
                test_data_mode="fresh-install" if args.fresh_install else "preserve",
            )
        )
        return 0
    if args.command == "run":
        return _run(
            repo_root,
            args.priority,
            args.driver,
            _selected_ids(args.selected_file),
            set(args.group) or None,
            args.unattended,
            args.fresh_install,
            set(args.case) or None,
            set(args.exclude_case) or None,
        )
    if args.command == "select":
        components = discover_inventory(repo_root)
        catalog_groups, catalog = build_catalog_bundle(repo_root, components)

        def run_selection(
            selection: dict[str, Any],
            cancel_event: threading.Event,
            publish_run: Any,
        ) -> dict[str, Any]:
            return _execute_run(
                repo_root,
                selection["priority"],
                args.driver,
                set(selection["selected"]),
                None,
                cancel_event=cancel_event,
                on_created=publish_run,
                wait_for_ui=True,
                fresh_install=args.fresh_install,
                include_case_ids=(set(selection.get("caseIds", [])) | set(selection.get("selected", []))) or None,
                excluded_ids=set(selection.get("excludedCaseIds", [])) or None,
                trial_case=selection.get("trialCase"),
                pipeline_id=selection.get("pipelineId"),
            )

        outcome = control(
            {"priority": args.priority, "groups": group_catalog(catalog, catalog_groups)},
            run_selection,
            open_browser=not args.no_open,
            repo_root=repo_root,
            keep_open=True,
        )
        if outcome.get("phase") == "cancelled" and not outcome.get("runId"):
            _print({"status": "cancelled"})
            return 2
        _print(outcome)
        return 0 if outcome.get("conclusion") in {"PASS", "SCOPED_PASS"} else 2
    if args.command == "pipeline":
        if args.pipeline_action == "list":
            _print({"pipelines": CatalogStore(repo_root).list_objects("pipelines")})
            return 0
        if args.pipeline_action == "plan":
            _print(compile_pipeline(repo_root, args.id))
            return 0
        if args.pipeline_action == "run":
            return _run(
                repo_root,
                "P1",
                args.driver,
                None,
                None,
                args.unattended,
                False,
                pipeline_id=args.id,
            )
    if args.command == "catalog":
        store = CatalogStore(repo_root)
        if args.catalog_action == "review-inventory":
            components = discover_inventory(repo_root)
            _, cases = build_catalog_bundle(repo_root, components)
            diagnostics = catalog_diagnostics(components, cases, repo_root=repo_root)
            if args.apply:
                from .state import atomic_write_json
                atomic_write_json(repo_root / "tests" / "ats" / "catalog" / "reviewed-inventory.json", {"schemaVersion": 1, "components": diagnostics["currentContracts"]})
            _print({"status": "applied" if args.apply else "preview", "componentCount": len(components), "newlyDiscovered": diagnostics["newlyDiscovered"], "changedContracts": diagnostics["changedContracts"]})
            return 0
        if args.catalog_action == "list":
            components = discover_inventory(repo_root)
            groups, cases = build_catalog_bundle(repo_root, components)
            _print({"groups": [group.to_dict() for group in groups], "cases": [case.to_dict() for case in cases], "archived": {"groups": store.list_objects("groups", True), "cases": store.list_objects("cases", True)} if args.archived else {}})
            return 0
        if args.catalog_action in {"validate", "diagnostics"}:
            components = discover_inventory(repo_root)
            groups, cases = build_catalog_bundle(repo_root, components)
            diagnostics = catalog_diagnostics(components, cases, {"groups": len(store.list_objects("groups", True)), "cases": len(store.list_objects("cases", True))}, repo_root)
            _print(diagnostics if args.catalog_action == "diagnostics" else {"ok": True, "groupCount": len(groups), "caseCount": len(cases), "diagnostics": diagnostics})
            return 0
        if args.check and args.apply:
            parser.error("catalog migrate accepts either --check or --apply")
        _print(migrate_base_catalog(repo_root, apply=args.apply))
        return 0
    if args.command == "next":
        _print(get_next(repo_root, args.run))
        return 0
    if args.command == "record":
        result = json.loads(args.result.read_text(encoding="utf-8"))
        _print(record_result(repo_root, args.run, args.case, result))
        return 0
    if args.command == "finalize":
        result = finalize_run(repo_root, args.run)
        _print(result)
        return {"PASS": 0, "SCOPED_PASS": 0, "FAIL": 1}.get(result["conclusion"], 2)
    if args.command == "report":
        run_dir = find_run(repo_root, args.run)
        state = read_json(run_dir / "state.json")
        result = write_reports(
            run_dir, state, finalize_pending=state["status"] == "completed"
        )
        if args.open:
            webbrowser.open((run_dir / "report.html").as_uri())
        _print({"result": result["conclusion"], "report": str(run_dir / "report.html")})
        return 0
    if args.command == "account":
        if args.action == "doctor":
            pool = load_pool(repo_root)
            try:
                configured = bool(keychain_vault().load(BROKER_TOKEN_KEY))
            except KeyError:
                configured = False
            except Exception as error:
                _print(
                    {
                        "ok": False,
                        "poolId": pool.pool_id,
                        "accountCount": len(pool.accounts),
                        "brokerOrigin": pool.broker_origin,
                        "credentialConfigured": False,
                        "error": f"Keychain unavailable: {type(error).__name__}",
                    }
                )
                return 2
            authorized = False
            diagnostic_error = None
            if configured:
                try:
                    authorized = default_manager(repo_root).authorization_is_valid()
                except Exception as error:
                    diagnostic_error = f"Broker diagnostic failed: {type(error).__name__}"
            _print(
                {
                    "ok": configured and authorized,
                    "poolId": pool.pool_id,
                    "accountCount": len(pool.accounts),
                    "brokerOrigin": pool.broker_origin,
                    "credentialConfigured": configured,
                    "credentialAuthorized": authorized,
                    **({"error": diagnostic_error} if diagnostic_error else {}),
                }
            )
            return 0 if configured and authorized else 2
        if args.action == "configure":
            credential = getpass.getpass("Test account broker credential: ")
            configure_broker_token(credential)
            _print({"status": "configured", "storage": "macOS Keychain"})
            return 0
        if args.action == "clear":
            clear_broker_token()
            _print({"status": "cleared"})
            return 0
        if not args.run:
            parser.error(f"account {args.action} requires --run")
        run_dir = find_run(repo_root, args.run)
        state = read_json(run_dir / "state.json")
        if args.action == "heartbeat":
            healthy = heartbeat_for_run(
                repo_root, run_dir, state, force=True
            )
            _print(
                {
                    "runId": args.run,
                    "status": state.get("testAccountLease", {}).get(
                        "heartbeatStatus", "not_leased"
                    ),
                    "expiresAt": state.get("testAccountLease", {}).get("expiresAt"),
                }
            )
            return 0 if healthy else 2
        cleaned = release_for_run(repo_root, run_dir, state)
        _print(
            {
                "runId": args.run,
                "status": state.get("testAccountLease", {}).get("status", "not_leased"),
            }
        )
        return 0 if cleaned else 2
    parser.error("unknown command")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
