from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
from pathlib import Path

from ai2apps_test.accounts import (
    AccountPool,
    TestAccountBrokerError,
    TestAccountLoginError,
    TestAccountManager,
    TestAccountTransportError,
    TestAppAccountSession,
    TestShellNativeContextError,
    _probe_authorization,
    acquire_for_run,
    configure_broker_token,
    load_pool,
    release_for_run,
)
from ai2apps_test.catalog import build_catalog, select_cases
from ai2apps_test.cli import _execute_run, _parse_args, _parser
from ai2apps_test.codex_driver import (
    build_command,
    driver_prompt,
    handoff_prompt,
    read_codex_output,
)
from ai2apps_test.inventory import discover_inventory, inventory_digest
from ai2apps_test.model import Case, priority_includes
from ai2apps_test.redact import redact_text
from ai2apps_test.report import conclusion, write_reports
from ai2apps_test.runner import next_agent_job, start_run
from ai2apps_test.selector import HTML, _status_payload
from ai2apps_test.state import create_run, read_json, save_state

REPO_ROOT = Path(__file__).resolve().parents[2]


class MemoryVault:
    def __init__(self) -> None:
        self.values = {"broker-access-token": "machine-credential"}

    def store(self, key: str, value: str) -> None:
        self.values[key] = value

    def load(self, key: str) -> str:
        if key not in self.values:
            raise KeyError(key)
        return self.values[key]

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


def test_top_level_fresh_install_opens_fresh_selector() -> None:
    args = _parse_args(_parser(), ["--fresh-install"])
    assert args.command == "select"
    assert args.fresh_install is True


def test_fresh_install_remains_available_after_subcommand() -> None:
    args = _parse_args(_parser(), ["run", "--fresh-install"])
    assert args.command == "run"
    assert args.fresh_install is True


def test_priority_selection_is_cumulative() -> None:
    assert priority_includes("P3", "P0")
    assert priority_includes("P2", "P2")
    assert not priority_includes("P1", "P2")


def test_inventory_discovers_apps_and_packaged_mini_apps() -> None:
    inventory = discover_inventory(REPO_ROOT)
    identities = {(item.kind, item.id) for item in inventory}
    assert ("app", "ai2apps.general-chat") in identities
    assert ("builtin-mini-entry", "ai2apps.general-chat.mini-entry") in identities
    assert ("package-app", "ai2apps/media-voice-studio-suite") in identities
    assert ("packaged-mini-app", "ai2apps.media-voice.video-subtitles") in identities
    assert len(inventory_digest(inventory)) == 64


def test_catalog_generates_all_priorities_for_shipping_app() -> None:
    inventory = discover_inventory(REPO_ROOT)
    catalog = build_catalog(REPO_ROOT, inventory)
    chat = [case for case in catalog if case.component_id == "ai2apps.general-chat"]
    assert {case.priority for case in chat} == {"P0", "P1", "P2", "P3"}
    p1 = select_cases(catalog, "P1")
    assert p1
    assert all(case.priority in {"P0", "P1"} for case in p1)


def test_reports_distinguish_blocked_and_scoped_pass(tmp_path: Path) -> None:
    case = Case("sample", "Sample", "P0", "Group", "builtin")
    plan = {"priority": "P0", "requiredCaseIds": ["sample"], "cases": [case.to_dict()]}
    _, run_dir, state = create_run(tmp_path, plan)
    assert run_dir.parent == tmp_path / "ai2apps-test-system" / "artifacts" / "runs"
    running = write_reports(run_dir, state)
    assert running["conclusion"] == "RUNNING"
    state["results"]["sample"] = {"status": "blocked", "summary": "not available"}
    final = write_reports(run_dir, state, finalize_pending=True)
    assert final["conclusion"] == "BLOCKED"
    assert (run_dir / "report.html").is_file()
    assert (run_dir / "junit.xml").is_file()


def test_account_cleanup_failure_cannot_be_reported_as_cancelled_or_passed() -> None:
    state = {
        "status": "cancelled",
        "plan": {"cases": [], "requiredCaseIds": []},
        "results": {},
        "testAccountLease": {"status": "release_failed"},
    }
    assert conclusion(state, finalize_pending=True) == "BLOCKED"


def test_redaction_removes_credentials_and_user_name() -> None:
    value = redact_text(
        'Authorization: Bearer secret-token\nCookie: sid=private\n'
        '"password":"temporary-password"\nleaseToken=lease-secret\n'
        "/Users/alice/file.txt"
    )
    assert "secret-token" not in value
    assert "sid=private" not in value
    assert "temporary-password" not in value
    assert "lease-secret" not in value
    assert "/Users/alice" not in value


def test_base_catalog_is_valid_json() -> None:
    path = REPO_ROOT / "tests" / "ats" / "catalog" / "base.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["schemaVersion"] == "ai2apps.test-catalog.v1"
    assert len({case["id"] for case in value["cases"]}) == len(value["cases"])


def test_test_account_pool_is_exact_allowlist() -> None:
    pool = load_pool(REPO_ROOT)
    assert pool.accounts == frozenset(
        f"test{index}@ai2apps.com" for index in range(1, 11)
    )
    assert pool.lease_ttl_seconds == 7200


def test_account_lease_keeps_password_and_token_out_of_public_state() -> None:
    vault = MemoryVault()
    calls = []

    def request(method, url, payload, token):
        calls.append((method, url, payload, token))
        if url.endswith("/release"):
            return {"status": "released"}
        return {
            "leaseId": "c505e206-822a-4ac6-8347-a544b74195d3",
            "email": "test3@ai2apps.com",
            "password": "temporary-password",
            "leaseToken": "a" * 43,
            "expiresAt": "2026-09-08T08:00:00Z",
        }

    pool = AccountPool(
        "desktop-test-v1",
        "https://coder.ai2apps.com",
        7200,
        frozenset(f"test{index}@ai2apps.com" for index in range(1, 11)),
    )
    manager = TestAccountManager(pool, vault, request)
    run_id = "20260908T053358Z-94042"
    public = manager.acquire(run_id)

    assert "password" not in public
    assert "leaseToken" not in public
    assert "temporary-password" not in json.dumps(public)
    assert "temporary-password" in vault.values["lease." + run_id]
    released = manager.release(run_id, public)
    assert released["status"] == "released"
    assert "lease." + run_id not in vault.values
    assert calls[-1][2]["leaseToken"] == "a" * 43


def test_account_broker_rejects_non_allowlisted_response() -> None:
    vault = MemoryVault()
    pool = AccountPool(
        "desktop-test-v1",
        "https://coder.ai2apps.com",
        7200,
        frozenset(f"test{index}@ai2apps.com" for index in range(1, 11)),
    )
    manager = TestAccountManager(
        pool,
        vault,
        lambda *_: {
            "leaseId": "c505e206-822a-4ac6-8347-a544b74195d3",
            "email": "someone@ai2apps.com",
            "password": "temporary-password",
            "leaseToken": "a" * 43,
            "expiresAt": "2026-09-08T08:00:00Z",
        },
    )
    try:
        manager.acquire("20260908T053358Z-94042")
    except TestAccountBrokerError:
        pass
    else:
        raise AssertionError("non-allowlisted account was accepted")


def test_account_doctor_probe_authenticates_without_acquiring(
    monkeypatch,
) -> None:
    seen = []

    class FakeOpener:
        def open(self, request, timeout):
            seen.append((request, timeout))
            raise urllib.error.HTTPError(
                request.full_url, 400, "invalid pool", {}, None
            )

    monkeypatch.setattr(
        "ai2apps_test.accounts.urllib.request.build_opener",
        lambda *_args: FakeOpener(),
    )
    assert _probe_authorization("https://coder.ai2apps.com", "x" * 32)
    request, timeout = seen[0]
    assert timeout == 15
    assert request.get_method() == "POST"
    assert json.loads(request.data)["poolId"] == "credential-probe-invalid-by-design"
    assert request.get_header("Authorization") == "Bearer " + "x" * 32


def test_account_doctor_probe_reports_rejected_credential(monkeypatch) -> None:
    class FakeOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, 401, "unauthorized", {}, None
            )

    monkeypatch.setattr(
        "ai2apps_test.accounts.urllib.request.build_opener",
        lambda *_args: FakeOpener(),
    )
    assert not _probe_authorization("https://coder.ai2apps.com", "x" * 32)


def test_account_configuration_normalizes_outer_whitespace() -> None:
    vault = MemoryVault()
    configure_broker_token("  " + "x" * 32 + "\n", vault=vault)
    assert vault.values["broker-access-token"] == "x" * 32


def test_uncertain_acquire_retries_same_run_and_uses_fresh_secrets() -> None:
    vault = MemoryVault()
    pool = AccountPool(
        "desktop-test-v1",
        "https://coder.ai2apps.com",
        7200,
        frozenset(f"test{index}@ai2apps.com" for index in range(1, 11)),
    )
    calls = []

    def request(method, url, payload, token):
        calls.append((method, url, payload, token))
        if len(calls) == 1:
            raise TestAccountTransportError("response lost")
        return {
            "leaseId": "c505e206-822a-4ac6-8347-a544b74195d3",
            "email": "test2@ai2apps.com",
            "password": "fresh-temporary-password",
            "leaseToken": "b" * 43,
            "expiresAt": "2026-09-08T08:00:00Z",
        }

    manager = TestAccountManager(pool, vault, request)
    run_id = "20260908T053358Z-94042"
    manager.acquire(run_id)

    assert len(calls) == 2
    assert calls[0][2]["runId"] == calls[1][2]["runId"] == run_id
    assert "fresh-temporary-password" in vault.values["lease." + run_id]


def test_heartbeat_uses_keychain_capability_without_exposing_it() -> None:
    vault = MemoryVault()
    pool = AccountPool(
        "desktop-test-v1",
        "https://coder.ai2apps.com",
        7200,
        frozenset(f"test{index}@ai2apps.com" for index in range(1, 11)),
    )
    calls = []

    def request(method, url, payload, token):
        calls.append((method, url, payload, token))
        if url.endswith("/heartbeat"):
            return {"status": "active", "expiresAt": "2026-09-08T09:00:00Z"}
        return {
            "leaseId": "c505e206-822a-4ac6-8347-a544b74195d3",
            "email": "test5@ai2apps.com",
            "password": "temporary-password",
            "leaseToken": "c" * 43,
            "expiresAt": "2026-09-08T08:00:00Z",
        }

    manager = TestAccountManager(pool, vault, request)
    run_id = "20260908T053358Z-94042"
    lease = manager.acquire(run_id)
    renewed = manager.heartbeat(run_id, lease)

    assert renewed["heartbeatStatus"] == "active"
    assert "leaseToken" not in renewed
    assert "password" not in renewed
    assert calls[-1][2]["leaseToken"] == "c" * 43


def test_account_setup_failure_blocks_only_dependent_cases(tmp_path: Path) -> None:
    account_case = Case(
        "ui.account",
        "Needs account",
        "P0",
        "UI",
        "codex-ui",
        requires=("test-account",),
    )
    public_case = Case("ui.public", "Public UI", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [account_case.id, public_case.id],
        "cases": [account_case.to_dict(), public_case.to_dict()],
    }
    _, run_dir, state = create_run(tmp_path, plan)

    class BrokenManager:
        def acquire(self, _run_id):
            raise TestAccountBrokerError("broker unavailable")

    assert not acquire_for_run(tmp_path, run_dir, state, manager=BrokenManager())
    assert state["results"][account_case.id]["status"] == "blocked"
    assert public_case.id not in state["results"]
    assert "password" not in json.dumps(state)


def test_login_failure_records_successful_lease_cleanup(tmp_path: Path) -> None:
    case = Case(
        "ui.account",
        "Needs account",
        "P0",
        "UI",
        "codex-ui",
        requires=("test-account",),
    )
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    _, run_dir, state = create_run(tmp_path, plan)

    class LoginFails:
        def acquire(self, _run_id):
            return {
                "status": "leased",
                "leaseId": "lease-1",
                "email": "test4@ai2apps.com",
                "expiresAt": "2026-09-08T09:00:00Z",
            }

        def authenticate(self, _repo_root, _run_id, _lease):
            raise TestAccountLoginError("Shell is still starting")

        def release(self, _run_id, lease):
            return {**lease, "status": "released"}

    assert not acquire_for_run(tmp_path, run_dir, state, manager=LoginFails())
    account = state["testAccountLease"]
    assert account["email"] == "test4@ai2apps.com"
    assert account["status"] == "unavailable"
    assert account["cleanupStatus"] == "released"


def test_test_shell_context_waits_for_initial_navigation(tmp_path: Path) -> None:
    calls = []

    class FakeConnection:
        def command(self, method, params):
            calls.append((method, params))
            if len(calls) == 1:
                return {
                    "contexts": [
                        {
                            "context": "other",
                            "url": "http://127.0.0.1:9999/",
                            "children": [],
                        }
                    ]
                }
            return {
                "contexts": [
                    {
                        "context": "shell",
                        "url": "http://127.0.0.1:56892/admin?redirect=/",
                        "children": [],
                    }
                ]
            }

    session = TestAppAccountSession(tmp_path, timeout_seconds=1)
    assert session._shell_context(FakeConnection(), "http://127.0.0.1:56892") == (
        "shell"
    )
    assert len(calls) == 2


def test_empty_shell_bidi_tree_selects_native_ui_fallback(tmp_path: Path) -> None:
    class EmptyConnection:
        def command(self, _method, _params):
            return {"contexts": []}

    session = TestAppAccountSession(tmp_path, timeout_seconds=1)
    try:
        session._shell_context(EmptyConnection(), "http://127.0.0.1:56892")
    except TestShellNativeContextError:
        pass
    else:
        raise AssertionError("native Shell context was treated as a BiDi page")


def test_native_shell_login_keeps_secret_out_of_process_arguments(
    tmp_path: Path, monkeypatch
) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="authenticated\n")

    monkeypatch.setattr("ai2apps_test.accounts.subprocess.run", fake_run)
    session = TestAppAccountSession(tmp_path, timeout_seconds=1)
    monkeypatch.setattr(
        session, "_native_helper_binary", lambda: tmp_path / "native-login"
    )
    session._login_with_native_accessibility(
        "test1@ai2apps.com", "temporary-password-secret"
    )
    command, options = calls[0]
    assert command == [str(tmp_path / "native-login")]
    assert "temporary-password-secret" not in json.dumps(command)
    assert json.loads(options["input"]) == {
        "operation": "login",
        "email": "test1@ai2apps.com",
        "password": "temporary-password-secret",
    }
    assert options["stderr"] is subprocess.DEVNULL


def test_native_shell_login_submits_with_return_before_button_fallback() -> None:
    source = (
        Path(__file__).parents[1]
        / "src"
        / "ai2apps_test"
        / "native_login.swift"
    ).read_text()
    return_submit = source.index("submitLoginWithReturn(passwordField")
    observed_submit = source.index("loginSubmissionStarted(appElement)")
    button_fallback = source.index('button(nodes, named: "Sign in")', observed_submit)
    assert return_submit < observed_submit < button_fallback
    assert "keyDown.postToPid(pid)" in source
    assert "keyUp.postToPid(pid)" in source


def test_test_identity_reset_removes_only_identity_rows(
    tmp_path: Path, monkeypatch
) -> None:
    support = tmp_path / "instances" / "test"
    database = support / "data" / "platform" / "ai2apps-platform.sqlite3"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE installations (id TEXT PRIMARY KEY);
            CREATE TABLE installation_memberships (installation_id TEXT);
            CREATE TABLE local_login_sessions (token_digest TEXT);
            CREATE TABLE package_state (id TEXT PRIMARY KEY);
            INSERT INTO installations VALUES ('stale-installation');
            INSERT INTO installation_memberships VALUES ('stale-installation');
            INSERT INTO local_login_sessions VALUES ('stale-session');
            INSERT INTO package_state VALUES ('preserved-package');
            """
        )

    session = TestAppAccountSession(tmp_path, timeout_seconds=1)
    session.support = support
    monkeypatch.setattr(session, "_expected_test_support", lambda: support)
    monkeypatch.setattr(
        session, "_native_helper_binary", lambda: tmp_path / "native-login"
    )
    monkeypatch.setattr(
        "ai2apps_test.accounts.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [str(tmp_path / "native-login")], 0, stdout="quit\n"
        ),
    )

    session._prepare_test_identity()

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM installations").fetchone() == (
            0,
        )
        assert connection.execute(
            "SELECT count(*) FROM installation_memberships"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM local_login_sessions"
        ).fetchone() == (0,)
        assert connection.execute("SELECT id FROM package_state").fetchone() == (
            "preserved-package",
        )


def test_fresh_install_uses_helper_reset_before_running_cases(
    tmp_path: Path, monkeypatch
) -> None:
    case = Case("ui.sample", "Visible case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "testDataMode": "fresh-install",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    calls = []
    monkeypatch.setattr(
        "ai2apps_test.runner.reset_test_instance", lambda _root: calls.append("reset")
    )

    _, _, state = start_run(tmp_path, plan)

    assert calls == ["reset"]
    assert state["status"] == "awaiting_agent"


def test_fresh_install_failure_blocks_selected_cases(tmp_path: Path, monkeypatch) -> None:
    case = Case("ui.sample", "Visible case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "testDataMode": "fresh-install",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }

    def fail(_root):
        from ai2apps_test.accounts import TestInstanceResetError

        raise TestInstanceResetError("synthetic reset failure")

    monkeypatch.setattr("ai2apps_test.runner.reset_test_instance", fail)

    _, _, state = start_run(tmp_path, plan)

    assert state["status"] == "completed"
    assert state["results"][case.id]["status"] == "blocked"
    assert "synthetic reset failure" in state["results"][case.id]["summary"]


def test_test_shell_login_uses_native_ui_without_connecting_to_bidi(
    tmp_path: Path, monkeypatch
) -> None:
    calls = []
    session = TestAppAccountSession(tmp_path, timeout_seconds=1)
    monkeypatch.setattr(
        session, "_prepare_test_identity", lambda: calls.append("prepare")
    )
    monkeypatch.setattr(session, "_launch", lambda: calls.append("launch"))
    monkeypatch.setattr(
        session,
        "_local_origin",
        lambda: calls.append("local") or "http://127.0.0.1:63022",
    )
    monkeypatch.setattr(
        session,
        "_shell_endpoint",
        lambda: (_ for _ in ()).throw(AssertionError("BiDi must not be used")),
    )
    monkeypatch.setattr(
        session,
        "_login_with_native_accessibility",
        lambda email, password: calls.append((email, password)),
    )

    session.login("test1@ai2apps.com", "temporary-password-secret")

    assert calls == [
        "prepare",
        "launch",
        "local",
        ("test1@ai2apps.com", "temporary-password-secret"),
    ]


def test_account_lifecycle_publishes_only_safe_state_and_releases(
    tmp_path: Path, monkeypatch
) -> None:
    account_case = Case(
        "ui.account",
        "Needs account",
        "P0",
        "UI",
        "codex-ui",
        requires=("test-account",),
    )
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [account_case.id],
        "cases": [account_case.to_dict()],
    }
    _, run_dir, state = create_run(tmp_path, plan)
    events = []

    class FakeManager:
        def acquire(self, _run_id):
            events.append("acquire")
            return {
                "status": "leased",
                "leaseId": "lease-1",
                "email": "test4@ai2apps.com",
                "expiresAt": "2026-09-08T08:00:00Z",
            }

        def authenticate(self, _repo_root, _run_id, _lease):
            events.append("authenticate")

        def release(self, _run_id, lease):
            events.append("release")
            return {**lease, "status": "released"}

    class FakeSession:
        def __init__(self, *_args, **_kwargs):
            pass

        def logout(self):
            events.append("logout")

    monkeypatch.setattr("ai2apps_test.accounts.TestAppAccountSession", FakeSession)
    manager = FakeManager()
    assert acquire_for_run(tmp_path, run_dir, state, manager=manager)
    assert state["testAccountLease"]["sessionStatus"] == "authenticated"
    assert "password" not in json.dumps(state)
    assert release_for_run(tmp_path, run_dir, state, manager=manager)
    assert state["testAccountLease"]["status"] == "released"
    assert events == ["acquire", "authenticate", "logout", "release"]


def test_terminal_driver_blocks_computer_use_jobs(tmp_path: Path) -> None:
    case = Case("ui.sample", "Sample UI", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "terminal",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    _, run_dir, _ = start_run(tmp_path, plan)
    state = read_json(run_dir / "state.json")
    assert state["results"][case.id]["status"] == "blocked"
    assert state["status"] == "ready_to_finalize"


def test_running_command_can_be_cancelled(tmp_path: Path) -> None:
    slow = Case(
        "command.slow",
        "Slow command",
        "P0",
        "Commands",
        "command",
        command=(sys.executable, "-c", "import time; time.sleep(30)"),
        timeout_seconds=60,
    )
    later = Case("builtin.later", "Later", "P0", "Commands", "builtin")
    plan = {
        "priority": "P0",
        "driver": "terminal",
        "requiredCaseIds": [slow.id, later.id],
        "cases": [slow.to_dict(), later.to_dict()],
    }
    cancelled = threading.Event()
    created = threading.Event()
    outcome: list[tuple[str, Path, dict[str, object]]] = []

    def run() -> None:
        outcome.append(
            start_run(
                tmp_path,
                plan,
                cancellation_requested=cancelled.is_set,
                on_created=lambda _run_id, _run_dir: created.set(),
            )
        )

    worker = threading.Thread(target=run)
    worker.start()
    assert created.wait(timeout=2)
    time.sleep(0.2)
    cancelled.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    _, run_dir, state = outcome[0]
    assert state["status"] == "cancelled"
    assert state["results"][slow.id]["status"] == "skipped"
    assert state["results"][later.id]["status"] == "skipped"
    assert read_json(run_dir / "result.json")["conclusion"] == "CANCELLED"


def test_progress_payload_reports_current_case(tmp_path: Path) -> None:
    case = Case("ui.sample", "Visible case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    run_id, run_dir, state = create_run(tmp_path, plan)
    state.update(status="running", currentCaseId=case.id, currentCaseName=case.name)
    save_state(run_dir, state)
    payload = _status_payload(
        {"phase": "running", "runId": run_id, "runDirectory": str(run_dir)},
        threading.Lock(),
    )
    assert payload["currentCaseName"] == case.name
    assert payload["groups"][0]["cases"][0]["status"] == "running"
    assert payload["percent"] == 0
    assert "中止测试" in HTML


def test_codex_driver_command_and_prompt_are_scoped(tmp_path: Path) -> None:
    command = build_command("/usr/local/bin/codex", tmp_path)
    assert command == [
        "/usr/local/bin/codex",
        "-a",
        "never",
        "exec",
        "--sandbox",
        "workspace-write",
        "-C",
        str(tmp_path),
        "--json",
        "-",
    ]
    assert "danger-full-access" not in command
    prompt = driver_prompt("20260908T075756Z-2632")
    assert "com.ai2apps.desktop.test" in prompt
    assert 'cua.getApp("com.ai2apps.desktop.test.shell")' in prompt
    assert "禁止将它们传给 cua.getApp" in prompt
    assert "不修改 AI2Apps 产品代码" in prompt
    assert "./bin/ai2apps-test next" in prompt
    assert ".agents/skills/ai2apps-test/SKILL.md" in prompt
    assert "Shell chrome 不是 WebDriver BiDi browsing context" in prompt
    assert "Shell 导航、App/Mini-Entry 启动" in prompt
    assert "通用 Chrome/Firefox BiDi" in prompt
    assert handoff_prompt("20260908T075756Z-2632") == (
        "接管并完成 Run `20260908T075756Z-2632`"
    )


def test_codex_job_routes_shell_ui_to_computer_use() -> None:
    case = Case("ui.shell", "Shell UI", "P0", "UI", "codex-ui")
    state = {"runId": "run-1", "plan": {"cases": [case.to_dict()]}, "results": {}}

    job = next_agent_job(state)

    assert job is not None
    instructions = "\n".join(job["instructions"])
    assert "Shell chrome is not a BiDi browsing context" in instructions
    assert "use Computer Use for Shell navigation" in instructions
    assert 'cua.getApp("com.ai2apps.desktop.test.shell")' in instructions
    assert "Never pass com.ai2apps.desktop.test or the outer AI2Apps-test.app path" in instructions
    assert "verify the target first" in instructions
    assert "explicitly targets an AI Browser webpage" in instructions
    assert "never substitute generic Chrome/Firefox BiDi" in instructions


def test_unattended_run_starts_codex_and_finalizes(tmp_path: Path, monkeypatch) -> None:
    case = Case("ui.sample", "Visible case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    started = []

    class FakeDriver:
        log_path = tmp_path / "driver.jsonl"

        def public_state(self):
            return {"status": "running", "pid": 123, "log": str(self.log_path)}

        def poll(self):
            run_dir = started[0]
            state = read_json(run_dir / "state.json")
            state["results"][case.id] = {
                "status": "blocked",
                "summary": "synthetic completion",
                "completedAt": "2026-09-08T00:00:00Z",
            }
            save_state(run_dir, state)
            return None

        def close_log(self):
            pass

        def wait(self, timeout):
            return 0

        def stop(self):
            raise AssertionError("completed driver should not be stopped")

    def fake_start(_repo_root, _run_id, run_dir):
        started.append(run_dir)
        return FakeDriver()

    monkeypatch.setattr(
        "ai2apps_test.cli.doctor", lambda _root: {"ok": True}
    )
    monkeypatch.setattr(
        "ai2apps_test.cli.compile_plan", lambda *_args, **_kwargs: plan
    )
    monkeypatch.setattr("ai2apps_test.cli.start_codex_driver", fake_start)
    result = _execute_run(
        tmp_path, "P0", "codex", {case.id}, None, wait_for_ui=True
    )
    assert started
    assert result["status"] == "completed"
    assert result["conclusion"] == "BLOCKED"
    state = read_json(started[0] / "state.json")
    assert state["codexDriver"]["status"] == "completed"


def test_progress_payload_exposes_driver_and_manual_handoff(tmp_path: Path) -> None:
    case = Case("ui.sample", "Visible case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    run_id, run_dir, state = create_run(tmp_path, plan)
    state.update(
        status="awaiting_agent",
        codexDriver={"status": "failed", "summary": "process exited"},
    )
    save_state(run_dir, state)
    payload = _status_payload(
        {"phase": "running", "runId": run_id, "runDirectory": str(run_dir)},
        threading.Lock(),
    )
    assert payload["codexDriver"]["status"] == "failed"
    assert payload["handoffPrompt"] == f"接管并完成 Run `{run_id}`"
    assert "手工接管" in payload["message"]
    assert "复制接管指令" in HTML


def test_progress_payload_includes_redacted_codex_live_output(tmp_path: Path) -> None:
    case = Case("ui.sample", "Visible case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    run_id, run_dir, state = create_run(tmp_path, plan)
    log_path = run_dir / "logs" / "codex-driver.jsonl"
    log_path.parent.mkdir(parents=True)
    events = [
        {"type": "thread.started", "thread_id": "thread-1"},
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "status": "completed",
                "text": "正在检查 Test App",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "status": "completed",
                "command": 'probe --password="do-not-show"',
                "aggregated_output": "ready",
            },
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
    )
    state.update(
        status="awaiting_agent",
        codexDriver={"status": "running", "log": str(log_path)},
    )
    save_state(run_dir, state)

    payload = _status_payload(
        {"phase": "running", "runId": run_id, "runDirectory": str(run_dir)},
        threading.Lock(),
    )

    output = payload["codexOutput"]
    assert [entry["title"] for entry in output["entries"]] == [
        "Codex 会话已启动",
        "Codex",
        "命令执行结果",
    ]
    assert "正在检查 Test App" in json.dumps(output, ensure_ascii=False)
    assert "do-not-show" not in json.dumps(output)
    assert "[REDACTED]" in json.dumps(output)
    assert output["updatedAt"]
    assert "Codex CLI 实时输出" in HTML


def test_codex_live_output_is_bounded_and_ignores_partial_json(tmp_path: Path) -> None:
    log_path = tmp_path / "codex.jsonl"
    events = [
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "status": "completed",
                "text": f"message-{index}",
            },
        }
        for index in range(5)
    ]
    log_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n{partial",
        encoding="utf-8",
    )

    output = read_codex_output(log_path, max_events=2)

    assert [entry["detail"] for entry in output["entries"]] == [
        "message-3",
        "message-4",
    ]


def test_progress_payload_explains_account_preflight_block(tmp_path: Path) -> None:
    case = Case("ui.sample", "Visible case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    run_id, run_dir, state = create_run(tmp_path, plan)
    state.update(
        status="completed",
        testAccountLease={
            "status": "unavailable",
            "summary": "test account broker credential was rejected",
        },
    )
    state["results"][case.id] = {"status": "blocked", "summary": "preflight"}
    save_state(run_dir, state)
    payload = _status_payload(
        {"phase": "completed", "runId": run_id, "runDirectory": str(run_dir)},
        threading.Lock(),
    )
    assert payload["handoffPrompt"] is None
    assert payload["message"].startswith("Codex 未启动：测试账号前置检查失败")
    assert "cleanupStatus" in HTML


def test_codex_queue_exposes_current_case(tmp_path: Path) -> None:
    case = Case("ui.current", "Current UI case", "P0", "UI", "codex-ui")
    plan = {
        "priority": "P0",
        "driver": "codex",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    _, _, state = start_run(tmp_path, plan)
    assert state["status"] == "awaiting_agent"
    assert state["currentCaseId"] == case.id
    assert state["currentCaseName"] == case.name


def test_executor_error_fails_only_one_case_and_continues(tmp_path: Path) -> None:
    broken = Case(
        "command.missing",
        "Missing command",
        "P0",
        "Commands",
        "command",
        command=("/definitely/not/an/ai2apps-test-command",),
    )
    healthy = Case(
        "command.healthy",
        "Healthy command",
        "P0",
        "Commands",
        "command",
        command=(sys.executable, "-c", "print('ok')"),
    )
    plan = {
        "priority": "P0",
        "driver": "terminal",
        "requiredCaseIds": [broken.id, healthy.id],
        "cases": [broken.to_dict(), healthy.to_dict()],
    }
    _, run_dir, state = start_run(tmp_path, plan)
    assert state["results"][broken.id]["status"] == "failed"
    assert "executor error" in state["results"][broken.id]["summary"]
    assert state["results"][healthy.id]["status"] == "passed"
    assert (run_dir / "logs" / f"{broken.id}.executor-error.log").is_file()


def test_progress_payload_includes_live_issue_details(tmp_path: Path) -> None:
    case = Case("case.failed", "Failed case", "P0", "Problem Group", "builtin")
    plan = {
        "priority": "P0",
        "driver": "terminal",
        "requiredCaseIds": [case.id],
        "cases": [case.to_dict()],
    }
    run_id, run_dir, state = create_run(tmp_path, plan)
    state["status"] = "running"
    state["results"][case.id] = {
        "status": "failed",
        "summary": "expected ready view",
        "details": {"outputTail": "assertion failed near toolbar"},
        "evidence": ["screenshots/failure.png"],
    }
    save_state(run_dir, state)
    payload = _status_payload(
        {"phase": "running", "runId": run_id, "runDirectory": str(run_dir)},
        threading.Lock(),
    )
    assert payload["issues"] == [
        {
            "id": case.id,
            "name": case.name,
            "priority": "P0",
            "status": "failed",
            "summary": "expected ready view",
            "group": "Problem Group",
            "detail": "assertion failed near toolbar",
            "evidence": ["screenshots/failure.png"],
        }
    ]
    assert "当前发现的问题" in HTML
    assert "测试默认继续，可随时中止" in HTML
