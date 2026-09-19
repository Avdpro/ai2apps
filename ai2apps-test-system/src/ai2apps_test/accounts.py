from __future__ import annotations

import json
import os
import plistlib
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

from ai2apps.acefox_bidi import AceFoxAgentEndpoint, AceFoxBiDiConnection
from ai2apps.browser.shell_bidi_gateway import ShellBiDiEndpoint
from ai2apps.helper_control import HelperControlClient, HelperControlError
from ai2apps.secrets.backends import MacOSKeychainBackend

from .state import append_timeline, now_text, save_state

POOL_SCHEMA = "ai2apps.test-account-pool.v1"
BROKER_TOKEN_KEY = "broker-access-token"
LEASE_SECRET_PREFIX = "lease."
KEYCHAIN_SERVICE = "AI2Apps Test Account Leases"
_RUN_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9]+$")
_LEASE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class TestAccountError(RuntimeError):
    code = "test_account_error"


class TestAccountConfigurationError(TestAccountError):
    code = "account_pool_unavailable"


class TestAccountBrokerError(TestAccountError):
    code = "account_broker_error"


class TestAccountAuthenticationError(TestAccountBrokerError):
    code = "account_broker_credential_rejected"


class TestAccountPoolError(TestAccountBrokerError):
    code = "test_account_pool_exhausted"


class TestAccountTransportError(TestAccountBrokerError):
    code = "account_broker_transport_uncertain"


class TestAccountLoginError(TestAccountError):
    code = "test_account_login_failed"


class TestShellNativeContextError(TestAccountLoginError):
    """The privileged Shell UI is visible but is not a BiDi browsing context."""


class TestInstanceResetError(RuntimeError):
    """The fixed Test Helper could not complete its signed instance reset."""


class SecretVault(Protocol):
    def store(self, key: str, value: str) -> None: ...
    def load(self, key: str) -> str: ...
    def delete(self, key: str) -> None: ...


Request = Callable[[str, str, dict[str, Any] | None, str], dict[str, Any]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


@dataclass(frozen=True)
class AccountPool:
    pool_id: str
    broker_origin: str
    lease_ttl_seconds: int
    accounts: frozenset[str]


class TestAccountKeychainBackend(MacOSKeychainBackend):
    """Handle macOS versions returning errSecParam for an absent generic item."""

    def _find_item(self, key: str, *, include_password: bool = False):
        status, item, password = super()._find_item(
            key, include_password=include_password
        )
        if status == -50 and not item.value:
            status = self._ERR_SEC_ITEM_NOT_FOUND
        return status, item, password


def load_pool(repo_root: Path) -> AccountPool:
    path = repo_root / "tests" / "ats" / "test-accounts.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise TestAccountConfigurationError(
            "test account pool configuration is unavailable"
        ) from error
    accounts = value.get("accounts")
    if value.get("schemaVersion") != POOL_SCHEMA:
        raise TestAccountConfigurationError("test account pool schema is invalid")
    if not isinstance(accounts, list) or len(accounts) != 10:
        raise TestAccountConfigurationError("test account pool must contain 10 accounts")
    normalized = frozenset(str(item).strip().lower() for item in accounts)
    expected = frozenset(f"test{index}@ai2apps.com" for index in range(1, 11))
    if normalized != expected:
        raise TestAccountConfigurationError("test account allowlist is invalid")
    origin = str(value.get("brokerOrigin", "")).rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise TestAccountConfigurationError("test account broker origin is invalid")
    ttl = int(value.get("leaseTtlSeconds", 0))
    if not 300 <= ttl <= 14_400:
        raise TestAccountConfigurationError("test account lease TTL is invalid")
    if value.get("poolId") != "desktop-test-v1":
        raise TestAccountConfigurationError("test account pool ID is invalid")
    return AccountPool("desktop-test-v1", origin, ttl, normalized)


def keychain_vault() -> SecretVault:
    try:
        return TestAccountKeychainBackend(service=KEYCHAIN_SERVICE)
    except Exception as error:
        raise TestAccountConfigurationError(
            "macOS Keychain is unavailable for test account leases"
        ) from error


def _http_request(
    method: str, url: str, payload: dict[str, Any] | None, token: str
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.build_opener(_NoRedirect).open(
            request, timeout=30
        ) as response:
            raw = response.read(1_048_577)
    except urllib.error.HTTPError as error:
        # A broker response may contain a lease secret, so never include its body.
        if error.code >= 500:
            raise TestAccountTransportError(
                f"test account broker response was uncertain ({error.code})"
            ) from error
        if error.code == 401:
            raise TestAccountAuthenticationError(
                "test account broker credential was rejected"
            ) from error
        if error.code == 409:
            raise TestAccountPoolError(
                "test account pool is exhausted or the Run is already complete"
            ) from error
        raise TestAccountBrokerError(
            f"test account broker request failed ({error.code})"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise TestAccountTransportError(
            "test account broker response was uncertain (unreachable)"
        ) from error
    if len(raw) > 1_048_576:
        raise TestAccountBrokerError("test account broker response is too large")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise TestAccountBrokerError("test account broker returned invalid JSON") from error
    if not isinstance(value, dict):
        raise TestAccountBrokerError("test account broker returned an invalid response")
    return value


def _probe_authorization(origin: str, token: str) -> bool:
    """Validate the Bearer before request validation, without acquiring a lease."""

    request = urllib.request.Request(
        origin + "/v1/test-account-leases",
        data=json.dumps(
            {
                "poolId": "credential-probe-invalid-by-design",
                "runId": "account-doctor",
                "client": {
                    "bundleId": "com.ai2apps.desktop.test",
                    "instanceId": "test",
                },
            }
        ).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=15):
            raise TestAccountBrokerError(
                "test account broker accepted an invalid diagnostic request"
            )
    except urllib.error.HTTPError as error:
        if error.code == 400:
            return True
        if error.code == 401:
            return False
        raise TestAccountBrokerError(
            f"test account broker diagnostic failed ({error.code})"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise TestAccountTransportError(
            "test account broker diagnostic is unreachable"
        ) from error


class TestAccountManager:
    def __init__(
        self,
        pool: AccountPool,
        vault: SecretVault,
        request: Request = _http_request,
    ) -> None:
        self.pool = pool
        self.vault = vault
        self.request = request

    def _broker_token(self) -> str:
        try:
            token = self.vault.load(BROKER_TOKEN_KEY)
        except KeyError as error:
            raise TestAccountConfigurationError(
                "test account broker credential is not configured in Keychain"
            ) from error
        if not token:
            raise TestAccountConfigurationError("test account broker credential is empty")
        return token

    def authorization_is_valid(self) -> bool:
        return _probe_authorization(self.pool.broker_origin, self._broker_token())

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError("invalid run ID for test account lease")

    def acquire(self, run_id: str) -> dict[str, Any]:
        self._validate_run_id(run_id)
        token = self._broker_token()
        request_payload = {
            "poolId": self.pool.pool_id,
            "runId": run_id,
            "ttlSeconds": self.pool.lease_ttl_seconds,
            "client": {
                "bundleId": "com.ai2apps.desktop.test",
                "instanceId": "test",
            },
        }
        try:
            response = self.request(
                "POST",
                f"{self.pool.broker_origin}/v1/test-account-leases",
                request_payload,
                token,
            )
        except TestAccountTransportError:
            # Cloud rotates both one-time secrets for the same Run on recovery.
            response = self.request(
                "POST",
                f"{self.pool.broker_origin}/v1/test-account-leases",
                request_payload,
                token,
            )
        lease_id = str(response.get("leaseId", ""))
        email = str(response.get("email", "")).strip().lower()
        password = response.get("password")
        lease_token = response.get("leaseToken")
        expires_at = str(response.get("expiresAt", ""))
        try:
            lease_id = str(UUID(lease_id))
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise TestAccountBrokerError(
                "test account broker lease response is invalid"
            ) from error
        if (
            email not in self.pool.accounts
            or not isinstance(password, str)
            or not 8 <= len(password.encode("utf-8")) <= 128
            or not isinstance(lease_token, str)
            or not _LEASE_TOKEN.fullmatch(lease_token)
            or expiry.tzinfo is None
        ):
            raise TestAccountBrokerError("test account broker lease response is invalid")
        secret = json.dumps(
            {"password": password, "leaseToken": lease_token},
            separators=(",", ":"),
        )
        try:
            self.vault.store(LEASE_SECRET_PREFIX + run_id, secret)
        except Exception as error:
            try:
                self.request(
                    "POST",
                    f"{self.pool.broker_origin}/v1/test-account-leases/{lease_id}/release",
                    {"runId": run_id, "leaseToken": lease_token},
                    token,
                )
            finally:
                raise TestAccountConfigurationError(
                    "test account lease could not be stored in Keychain"
                ) from error
        return {
            "status": "leased",
            "leaseId": lease_id,
            "email": email,
            "expiresAt": expires_at,
            "ttlSeconds": self.pool.lease_ttl_seconds,
            "acquiredAt": now_text(),
        }

    def heartbeat(self, run_id: str, lease: dict[str, Any]) -> dict[str, Any]:
        self._validate_run_id(run_id)
        secret = self.secret(run_id)
        response = self.request(
            "POST",
            f"{self.pool.broker_origin}/v1/test-account-leases/{lease['leaseId']}/heartbeat",
            {
                "runId": run_id,
                "leaseToken": secret["leaseToken"],
                "ttlSeconds": self.pool.lease_ttl_seconds,
            },
            self._broker_token(),
        )
        if response.get("status") != "active" or not response.get("expiresAt"):
            raise TestAccountBrokerError("test account heartbeat was not confirmed")
        renewed = dict(lease)
        renewed.pop("heartbeatCode", None)
        renewed.pop("heartbeatSummary", None)
        renewed.update(
            expiresAt=str(response["expiresAt"]),
            heartbeatStatus="active",
            lastHeartbeatAt=now_text(),
        )
        return renewed

    def secret(self, run_id: str) -> dict[str, str]:
        self._validate_run_id(run_id)
        try:
            value = json.loads(self.vault.load(LEASE_SECRET_PREFIX + run_id))
        except (KeyError, json.JSONDecodeError) as error:
            raise TestAccountConfigurationError(
                "test account lease secret is unavailable in Keychain"
            ) from error
        if not isinstance(value.get("password"), str) or not isinstance(
            value.get("leaseToken"), str
        ):
            raise TestAccountConfigurationError("test account lease secret is invalid")
        return value

    def authenticate(self, repo_root: Path, run_id: str, lease: dict[str, Any]) -> None:
        secret = self.secret(run_id)
        TestAppAccountSession(repo_root).login(
            str(lease["email"]), secret["password"]
        )

    def release(self, run_id: str, lease: dict[str, Any]) -> dict[str, Any]:
        self._validate_run_id(run_id)
        secret = self.secret(run_id)
        token = self._broker_token()
        response = self.request(
            "POST",
            f"{self.pool.broker_origin}/v1/test-account-leases/{lease['leaseId']}/release",
            {"runId": run_id, "leaseToken": secret["leaseToken"]},
            token,
        )
        if response.get("status") != "released":
            raise TestAccountBrokerError("test account broker did not confirm release")
        try:
            self.vault.delete(LEASE_SECRET_PREFIX + run_id)
        except Exception as error:
            raise TestAccountConfigurationError(
                "released test account secret could not be removed from Keychain"
            ) from error
        return {**lease, "status": "released", "releasedAt": now_text()}


class TestAppAccountSession:
    """Log the fixed Test instance in without exposing its password to Codex."""

    def __init__(self, repo_root: Path, *, timeout_seconds: float = 60) -> None:
        self.repo_root = repo_root
        self.timeout_seconds = timeout_seconds
        self.app = (
            repo_root / "apps" / "ai2apps-acefox" / ".build" / "AI2Apps-test.app"
        )
        self.support = (
            self._expected_test_support()
        )

    @staticmethod
    def _expected_test_support() -> Path:
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "AI2Apps"
            / "instances"
            / "test"
        )

    def _launch(self) -> None:
        try:
            info = plistlib.loads((self.app / "Contents" / "Info.plist").read_bytes())
        except (OSError, plistlib.InvalidFileException) as error:
            raise TestAccountLoginError("Test App metadata is unavailable") from error
        if (
            info.get("CFBundleIdentifier") != "com.ai2apps.desktop.test"
            or info.get("AI2AppsInstanceID") != "test"
        ):
            raise TestAccountLoginError("Test App bundle identity is invalid")
        completed = subprocess.run(
            ["open", str(self.app)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode:
            raise TestAccountLoginError("Test App could not be launched")

    def _local_origin(self) -> str:
        descriptor = self.support / "run" / "local.json"
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            try:
                value = json.loads(descriptor.read_text(encoding="utf-8"))
                port = int(value["actual_port"])
                pid = int(value["pid"])
                if value.get("instance_id") != "test" or not 1 <= port <= 65535:
                    raise ValueError("identity mismatch")
                os.kill(pid, 0)
                return f"http://127.0.0.1:{port}"
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                time.sleep(0.2)
        raise TestAccountLoginError("Test instance Local service did not become ready")

    def _shell_endpoint(self) -> AceFoxAgentEndpoint:
        descriptor = self.support / "run" / "shell-automation.json"
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            try:
                raw = json.loads(descriptor.read_text(encoding="utf-8"))
                if raw.get("instance_id") != "test":
                    raise ValueError("identity mismatch")
                endpoint = ShellBiDiEndpoint.load(descriptor)
                return AceFoxAgentEndpoint(
                    web_socket_url=endpoint.web_socket_url,
                    authorization=endpoint.authorization,
                    profile_id="app-shell",
                    pid=endpoint.pid,
                )
            except Exception:
                time.sleep(0.2)
        raise TestAccountLoginError("Test Shell BiDi endpoint did not become ready")

    def _shell_context(
        self, connection: AceFoxBiDiConnection, origin: str
    ) -> str:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            tree = connection.command("browsingContext.getTree", {"maxDepth": 8})
            top_level = tree.get("contexts", [])
            if not isinstance(top_level, list) or not top_level:
                raise TestShellNativeContextError(
                    "Test Shell uses a native privileged page without a BiDi context"
                )
            pending = list(top_level)
            while pending:
                context = pending.pop(0)
                if str(context.get("url", "")).startswith(origin + "/"):
                    value = context.get("context")
                    if isinstance(value, str) and value:
                        return value
                children = context.get("children", [])
                if isinstance(children, list):
                    pending.extend(
                        item for item in children if isinstance(item, dict)
                    )
            time.sleep(0.2)
        raise TestAccountLoginError("Test Shell page context is unavailable")

    def _native_helper_binary(self) -> Path:
        source = Path(__file__).with_name("native_login.swift")
        build_dir = self.repo_root / ".build" / "ai2apps-test"
        binary = build_dir / "native-login"
        module_cache = build_dir / "swift-module-cache"
        try:
            needs_build = (
                not binary.exists()
                or binary.stat().st_mtime_ns < source.stat().st_mtime_ns
            )
            if needs_build:
                build_dir.mkdir(parents=True, exist_ok=True)
                completed = subprocess.run(
                    [
                        "xcrun",
                        "swiftc",
                        "-module-cache-path",
                        str(module_cache),
                        str(source),
                        "-o",
                        str(binary),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=60,
                    check=False,
                )
                if completed.returncode:
                    raise TestAccountLoginError(
                        "Test Shell native login helper could not be built"
                    )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TestAccountLoginError(
                "Test Shell native login helper is unavailable"
            ) from error
        return binary

    def _prepare_test_identity(self) -> None:
        """Remove only stale Local identity rows from the fixed test instance."""

        expected_support = self._expected_test_support()
        if self.support != expected_support:
            raise TestAccountLoginError("Test instance identity path is invalid")

        try:
            completed = subprocess.run(
                [str(self._native_helper_binary())],
                input=json.dumps({"operation": "quit"}),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TestAccountLoginError(
                "Test instance could not be stopped for identity reset"
            ) from error
        if completed.returncode != 0 or completed.stdout.strip() != "quit":
            raise TestAccountLoginError(
                "Test instance could not be stopped for identity reset"
            )

        descriptors = ["local.json", "shell.json", "helper.json"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            live = False
            for name in descriptors:
                try:
                    pid = int(
                        json.loads((self.support / "run" / name).read_text())["pid"]
                    )
                    os.kill(pid, 0)
                    live = True
                except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue
            if not live:
                break
            time.sleep(0.1)
        else:
            raise TestAccountLoginError(
                "Test instance did not stop before identity reset"
            )

        database = self.support / "data" / "platform" / "ai2apps-platform.sqlite3"
        if not database.exists():
            return
        try:
            with sqlite3.connect(database, timeout=10) as connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("DELETE FROM local_login_sessions")
                connection.execute("DELETE FROM installation_memberships")
                connection.execute("DELETE FROM installations")
        except sqlite3.Error as error:
            raise TestAccountLoginError(
                "Test instance stale identity could not be reset"
            ) from error

    def _login_with_native_accessibility(self, email: str, password: str) -> None:
        """Drive only the fixed Test Shell through AX; pass credentials via stdin."""

        request = json.dumps(
            {"operation": "login", "email": email, "password": password}
        )
        try:
            completed = subprocess.run(
                [str(self._native_helper_binary())],
                input=request,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=self.timeout_seconds + 15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TestAccountLoginError(
                "Test Shell native login automation did not complete"
            ) from error
        outcome = completed.stdout.strip()
        if completed.returncode != 0 or outcome != "authenticated":
            safe_outcomes = {
                "test-shell-count",
                "fields-unavailable",
                "fields-not-settable",
                "submit-unavailable",
                "submit-failed",
                "binding-submit-failed",
                "accessibility-permission",
                "timeout",
            }
            summary = outcome if outcome in safe_outcomes else "automation-error"
            raise TestAccountLoginError(
                f"Test Shell native login automation failed ({summary})"
            )

    @staticmethod
    def _remote_string(response: dict[str, Any]) -> str:
        if response.get("type") != "success":
            raise TestAccountLoginError("Test Shell login script raised an exception")
        result = response.get("result", {})
        if result.get("type") != "string":
            raise TestAccountLoginError("Test Shell login script returned invalid data")
        return str(result.get("value", ""))

    def login(self, email: str, password: str) -> None:
        self._prepare_test_identity()
        self._launch()
        # The privileged Test Shell page is native chrome and is deliberately not
        # exposed as a WebDriver BiDi browsing context.  Waiting for or connecting
        # to that nonexistent context turns a normal login into a startup-race
        # failure before the native fallback can run.  Wait only for Local, then
        # drive the fixed test bundle through macOS Accessibility.
        self._local_origin()
        self._login_with_native_accessibility(email, password)

    def logout(self) -> None:
        try:
            origin = self._local_origin()
            with AceFoxBiDiConnection(self._shell_endpoint()) as connection:
                context = self._shell_context(connection, origin)
                connection.command(
                    "script.evaluate",
                    {
                        "expression": "fetch('/v1/platform/cloud/auth/logout',{method:'POST',credentials:'same-origin'}).then(()=>true,()=>false)",
                        "awaitPromise": True,
                        "target": {"context": context},
                    },
                    timeout_seconds=10,
                )
        except Exception:
            # Cloud TTL and password rotation still revoke the remote session.
            return


def reset_test_instance(repo_root: Path, *, timeout_seconds: float = 60) -> None:
    """Reset only the fixed Test roots through the authenticated Test Helper."""

    session = TestAppAccountSession(repo_root, timeout_seconds=timeout_seconds)
    helper = (
        session.app
        / "Contents"
        / "Library"
        / "LoginItems"
        / "AI2AppsHelper.app"
        / "Contents"
        / "Info.plist"
    )
    try:
        app_info = plistlib.loads((session.app / "Contents" / "Info.plist").read_bytes())
        helper_info = plistlib.loads(helper.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise TestInstanceResetError("Test App reset metadata is unavailable") from error
    if (
        app_info.get("CFBundleIdentifier") != "com.ai2apps.desktop.test"
        or app_info.get("AI2AppsInstanceID") != "test"
        or helper_info.get("AI2AppsAllowInstanceDataReset") is not True
    ):
        raise TestInstanceResetError("Test App reset identity is invalid")

    session._launch()
    endpoint = session.support / "run" / "helper-control.json"
    token_path = session.support / "run" / "helper-control.token"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            token = token_path.read_text(encoding="utf-8").strip()
            client = HelperControlClient(
                endpoint_path=str(endpoint),
                token=token,
                timeout_seconds=min(3, timeout_seconds),
            )
            client.reset_instance_data(
                actor_user_id="ai2apps-test-harness",
                confirm_instance_id="test",
            )
            break
        except (OSError, HelperControlError) as error:
            last_error = error
            time.sleep(0.2)
    else:
        raise TestInstanceResetError(
            "Test Helper did not accept the fresh-install reset"
        ) from last_error

    cache_root = (
        Path.home() / "Library" / "Caches" / "AI2Apps" / "instances" / "test"
    )
    while time.monotonic() < deadline:
        if not session.support.exists() and not cache_root.exists():
            return
        time.sleep(0.2)
    raise TestInstanceResetError("Test Helper did not finish the fresh-install reset")


def default_manager(repo_root: Path) -> TestAccountManager:
    return TestAccountManager(load_pool(repo_root), keychain_vault())


def requires_account(case: dict[str, Any]) -> bool:
    return "test-account" in case.get("requires", [])


def acquire_for_run(
    repo_root: Path,
    run_dir: Path,
    state: dict[str, Any],
    *,
    manager: TestAccountManager | None = None,
) -> bool:
    pending = [
        case
        for case in state["plan"]["cases"]
        if case["id"] not in state["results"] and requires_account(case)
    ]
    if not pending or state.get("testAccountLease", {}).get("status") == "leased":
        return True
    state["testAccountLease"] = {
        "status": "acquiring",
        "summary": "Selecting and preparing an isolated test account",
    }
    save_state(run_dir, state)
    append_timeline(run_dir, {"event": "test_account_acquiring"})
    try:
        active_manager = manager or default_manager(repo_root)
        lease = active_manager.acquire(state["runId"])
        state["testAccountLease"] = {**lease, "sessionStatus": "starting"}
        save_state(run_dir, state)
        active_manager.authenticate(repo_root, state["runId"], lease)
    except TestAccountError as error:
        public_lease: dict[str, Any] = {}
        cleanup_status = "not_needed"
        cleanup_error: TestAccountError | None = None
        if "lease" in locals():
            public_lease = {
                key: lease[key]
                for key in ("leaseId", "email", "expiresAt", "ttlSeconds", "acquiredAt")
                if key in lease
            }
            try:
                active_manager.release(state["runId"], lease)
                cleanup_status = "released"
            except TestAccountError as release_error:
                cleanup_status = "release_failed"
                cleanup_error = release_error
        state["testAccountLease"] = {
            **public_lease,
            "status": "release_failed"
            if cleanup_status == "release_failed"
            else "unavailable",
            "code": error.code,
            "summary": str(error),
            "cleanupStatus": cleanup_status,
            **(
                {
                    "cleanupCode": cleanup_error.code,
                    "cleanupSummary": str(cleanup_error),
                }
                if cleanup_error is not None
                else {}
            ),
        }
        for case in pending:
            state["results"][case["id"]] = {
                "status": "blocked",
                "summary": f"Test account setup blocked: {error}",
                "details": {"code": error.code},
                "completedAt": now_text(),
            }
        save_state(run_dir, state)
        append_timeline(run_dir, {"event": "test_account_unavailable", "code": error.code})
        return False
    state["testAccountLease"] = {
        **lease,
        "sessionStatus": "authenticated",
        "authenticatedAt": now_text(),
    }
    save_state(run_dir, state)
    append_timeline(
        run_dir,
        {
            "event": "test_account_acquired",
            "leaseId": lease["leaseId"],
            "email": lease["email"],
            "expiresAt": lease["expiresAt"],
        },
    )
    return True


def release_for_run(
    repo_root: Path,
    run_dir: Path,
    state: dict[str, Any],
    *,
    manager: TestAccountManager | None = None,
) -> bool:
    lease = state.get("testAccountLease")
    if not isinstance(lease, dict) or lease.get("status") not in {
        "leased",
        "release_failed",
    }:
        return True
    try:
        active_manager = manager or default_manager(repo_root)
        TestAppAccountSession(repo_root, timeout_seconds=2).logout()
        released = active_manager.release(state["runId"], lease)
    except TestAccountError as error:
        state["testAccountLease"] = {
            **lease,
            "status": "release_failed",
            "code": error.code,
            "summary": str(error),
        }
        save_state(run_dir, state)
        append_timeline(
            run_dir,
            {"event": "test_account_release_failed", "code": error.code},
        )
        return False
    state["testAccountLease"] = released
    save_state(run_dir, state)
    append_timeline(
        run_dir,
        {"event": "test_account_released", "leaseId": released["leaseId"]},
    )
    return True


def heartbeat_for_run(
    repo_root: Path,
    run_dir: Path,
    state: dict[str, Any],
    *,
    manager: TestAccountManager | None = None,
    force: bool = False,
) -> bool:
    lease = state.get("testAccountLease")
    if not isinstance(lease, dict) or lease.get("status") != "leased":
        return True
    if not force:
        last_text = lease.get("lastHeartbeatAt") or lease.get("acquiredAt")
        try:
            last = datetime.fromisoformat(str(last_text)).astimezone(UTC)
        except (TypeError, ValueError):
            last = datetime.min.replace(tzinfo=UTC)
        ttl = int(lease.get("ttlSeconds", 7200))
        if (datetime.now(UTC) - last).total_seconds() < max(60, ttl // 2):
            return True
    try:
        renewed = (manager or default_manager(repo_root)).heartbeat(
            state["runId"], lease
        )
    except TestAccountError as error:
        state["testAccountLease"] = {
            **lease,
            "heartbeatStatus": "failed",
            "heartbeatCode": error.code,
            "heartbeatSummary": str(error),
        }
        save_state(run_dir, state)
        append_timeline(
            run_dir,
            {"event": "test_account_heartbeat_failed", "code": error.code},
        )
        return False
    state["testAccountLease"] = renewed
    save_state(run_dir, state)
    append_timeline(
        run_dir,
        {
            "event": "test_account_heartbeat",
            "leaseId": renewed["leaseId"],
            "expiresAt": renewed["expiresAt"],
        },
    )
    return True


def configure_broker_token(value: str, *, vault: SecretVault | None = None) -> None:
    value = value.strip()
    if len(value.encode("utf-8")) < 32 or any(character.isspace() for character in value):
        raise ValueError("broker credential is invalid")
    (vault or keychain_vault()).store(BROKER_TOKEN_KEY, value)


def clear_broker_token(*, vault: SecretVault | None = None) -> None:
    (vault or keychain_vault()).delete(BROKER_TOKEN_KEY)
