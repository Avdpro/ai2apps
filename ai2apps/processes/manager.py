"""Asynchronous, Session-owned, resource-bounded process execution."""

from __future__ import annotations

import asyncio
import base64
import os
import platform
import resource
import shutil
import signal
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import psutil

from ai2apps.config import (
    DEFAULT_PROCESS_CPU_TIME_SECONDS,
    DEFAULT_PROCESS_IDLE_TIME_SECONDS,
    DEFAULT_PROCESS_MEMORY_LIMIT_BYTES,
    DEFAULT_PROCESS_OUTPUT_LIMIT_BYTES,
    DEFAULT_PROCESS_WALL_TIME_SECONDS,
    DEFAULT_SESSION_PROCESS_LIMIT,
)
from ai2apps.core import EntityIdKind, new_entity_id
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase
from ai2apps.workspace import WorkspaceRepository

from .authority import BrokerAuthority
from .models import ProcessLimits, ProcessRecord, ProcessServiceError, ProcessStatus
from .repository import ProcessRepository
from .sandbox import ProcessSandboxAdapter, default_sandbox_adapter

_MAX_ARGV_ITEMS = 64
_MAX_ARG_BYTES = 32 * 1024
_MAX_STDIN_BYTES = 64 * 1024
_READ_CHUNK_BYTES = 16 * 1024
_LITERAL_ENV_KEYS = frozenset({"LANG", "LC_ALL", "TZ", "TERM"})
_TERMINATION_GRACE_SECONDS = 1.0


class SecretProvider(Protocol):
    """Resolve an opaque secret reference without storing its value in SQLite."""

    def resolve(
        self, reference: str, *, session_id: str, run_id: str | None
    ) -> str: ...


@dataclass(slots=True)
class _LiveProcess:
    process: asyncio.subprocess.Process
    record: ProcessRecord
    tasks: tuple[asyncio.Task[None], ...]


class ProcessManager:
    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore,
        workspace: WorkspaceRepository,
        *,
        sandbox: ProcessSandboxAdapter | None = None,
        broker: BrokerAuthority | None = None,
        secrets: SecretProvider | None = None,
        session_limit: int = DEFAULT_SESSION_PROCESS_LIMIT,
    ) -> None:
        if session_limit <= 0:
            raise ValueError("session_limit must be positive")
        self.repository = ProcessRepository(database, events)
        self.workspace = workspace
        self.sandbox = sandbox or default_sandbox_adapter()
        self.broker = broker or BrokerAuthority()
        self.secrets = secrets
        self.session_limit = session_limit
        self._live: dict[str, _LiveProcess] = {}
        self._output_locks: dict[str, asyncio.Lock] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping = False

    async def startup(self) -> int:
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        await asyncio.to_thread(self._reap_previous_runtime)
        return await asyncio.to_thread(self.repository.recover_orphans)

    def _reap_previous_runtime(self) -> None:
        """Kill only stale process groups whose PID birth time matches our record."""

        for record in self.repository.active():
            if record.pid is None or record.started_at is None:
                continue
            try:
                process = psutil.Process(record.pid)
                same_process = (
                    abs(process.create_time() - record.started_at.timestamp()) < 5.0
                )
                if same_process and os.getpgid(record.pid) == record.pid:
                    os.killpg(record.pid, signal.SIGKILL)
            except (psutil.Error, ProcessLookupError, PermissionError, OSError):
                continue

    async def shutdown(self) -> None:
        self._stopping = True
        await asyncio.gather(
            *(
                self.cancel(
                    item.record.id,
                    session_id=item.record.session_id,
                    run_id=item.record.run_id,
                )
                for item in tuple(self._live.values())
            ),
            return_exceptions=True,
        )
        self._loop = None

    @staticmethod
    def _limits(values: Mapping[str, object] | None) -> ProcessLimits:
        raw = values or {}

        def bounded(name: str, default: int, maximum: int) -> int:
            value = raw.get(name, default)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ProcessServiceError("invalid_limits", f"{name} must be positive")
            return min(value, maximum)

        return ProcessLimits(
            wall_time_seconds=bounded(
                "wall_time_seconds",
                DEFAULT_PROCESS_WALL_TIME_SECONDS,
                DEFAULT_PROCESS_WALL_TIME_SECONDS,
            ),
            idle_time_seconds=bounded(
                "idle_time_seconds",
                DEFAULT_PROCESS_IDLE_TIME_SECONDS,
                DEFAULT_PROCESS_IDLE_TIME_SECONDS,
            ),
            cpu_time_seconds=bounded(
                "cpu_time_seconds",
                DEFAULT_PROCESS_CPU_TIME_SECONDS,
                DEFAULT_PROCESS_CPU_TIME_SECONDS,
            ),
            memory_bytes=bounded(
                "memory_bytes",
                DEFAULT_PROCESS_MEMORY_LIMIT_BYTES,
                DEFAULT_PROCESS_MEMORY_LIMIT_BYTES,
            ),
            output_bytes=bounded(
                "output_bytes",
                DEFAULT_PROCESS_OUTPUT_LIMIT_BYTES,
                DEFAULT_PROCESS_OUTPUT_LIMIT_BYTES,
            ),
        )

    @staticmethod
    def _argv(argv: object) -> tuple[str, ...]:
        if (
            not isinstance(argv, list)
            or not 1 <= len(argv) <= _MAX_ARGV_ITEMS
            or not all(
                isinstance(item, str) and item and "\x00" not in item for item in argv
            )
            or sum(len(item.encode("utf-8")) for item in argv) > _MAX_ARG_BYTES
        ):
            raise ProcessServiceError(
                "invalid_argv", "argv must be a bounded non-empty string array"
            )
        return tuple(argv)

    def _environment(
        self,
        values: Mapping[str, object] | None,
        *,
        session_id: str,
        run_id: str | None,
        workspace: Path,
        temporary: Path,
    ) -> dict[str, str]:
        search_roots = ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]
        for root in ("/opt/homebrew/bin", "/usr/local/bin"):
            if Path(root).is_dir():
                search_roots.append(root)
        result = {
            "PATH": ":".join(search_roots),
            "TMPDIR": str(temporary),
            "HOME": str(workspace),
            "AI2APPS_SESSION_ID": session_id,
            "AI2APPS_WORKSPACE": str(workspace),
        }
        for key, value in (values or {}).items():
            if (
                not isinstance(key, str)
                or not key
                or "\x00" in key
                or not (key in _LITERAL_ENV_KEYS or key.startswith("AI2APPS_"))
            ):
                raise ProcessServiceError(
                    "environment_denied", f"Environment key is not allowed: {key!r}"
                )
            if isinstance(value, str):
                resolved = value
            elif isinstance(value, dict) and set(value) == {"secret_ref"}:
                reference = value["secret_ref"]
                if (
                    not isinstance(reference, str)
                    or not reference
                    or self.secrets is None
                ):
                    raise ProcessServiceError(
                        "secret_unavailable",
                        f"Secret reference for {key} cannot be resolved",
                    )
                resolved = self.secrets.resolve(
                    reference, session_id=session_id, run_id=run_id
                )
            else:
                raise ProcessServiceError(
                    "invalid_environment", f"Environment value for {key} is invalid"
                )
            if "\x00" in resolved or len(resolved.encode("utf-8")) > 16 * 1024:
                raise ProcessServiceError(
                    "invalid_environment", f"Environment value for {key} is invalid"
                )
            result[key] = resolved
        return result

    @staticmethod
    def _resolve_executable(
        argv: tuple[str, ...], environment: Mapping[str, str], workspace: Path
    ) -> tuple[str, ...]:
        executable = argv[0]
        if "/" not in executable:
            executable = shutil.which(executable, path=environment["PATH"]) or ""
        path = Path(executable)
        if not executable or not path.is_absolute() or not path.is_file():
            raise ProcessServiceError(
                "executable_not_found", f"Executable not found: {argv[0]}"
            )
        resolved = path.resolve()
        allowed = any(
            resolved == root or root in resolved.parents
            for root in (
                Path("/usr"),
                Path("/bin"),
                Path("/sbin"),
                Path("/opt/homebrew"),
                Path("/usr/local"),
                workspace.resolve(),
            )
        )
        if not allowed:
            raise ProcessServiceError(
                "executable_denied",
                "Executable must be system-provided or in the Session workspace",
            )
        if not os.access(resolved, os.X_OK):
            raise ProcessServiceError(
                "executable_denied", "Executable is not executable"
            )
        return (str(resolved), *argv[1:])

    @staticmethod
    def _resource_limiter(limits: ProcessLimits):
        def apply() -> None:
            def set_limit(kind: int, value: int) -> None:
                try:
                    _soft, hard = resource.getrlimit(kind)
                    bounded = (
                        value if hard == resource.RLIM_INFINITY else min(value, hard)
                    )
                    resource.setrlimit(kind, (bounded, bounded))
                except (OSError, ValueError):
                    # Some kernels expose but do not implement every RLIMIT.
                    pass

            set_limit(resource.RLIMIT_CPU, limits.cpu_time_seconds)
            set_limit(resource.RLIMIT_FSIZE, limits.output_bytes)
            if platform.system() == "Darwin":
                set_limit(resource.RLIMIT_RSS, limits.memory_bytes)
            else:
                set_limit(resource.RLIMIT_AS, limits.memory_bytes)

        return apply

    async def start(
        self,
        *,
        session_id: str,
        run_id: str | None,
        caller_id: str,
        argv: object,
        cwd: str = ".",
        environment: Mapping[str, object] | None = None,
        network_enabled: bool = False,
        limits: Mapping[str, object] | None = None,
    ) -> ProcessRecord:
        if self._stopping:
            raise ProcessServiceError("service_stopping", "Process Service is stopping")
        if self.repository.active_count(session_id) >= self.session_limit:
            raise ProcessServiceError(
                "session_process_limit", "Session concurrent Process limit reached"
            )
        process_argv = self._argv(argv)
        process_limits = self._limits(limits)
        self.workspace.ensure_sandbox(session_id)
        workspace = self.workspace._root(session_id).resolve(strict=True)
        temporary = self.workspace._temporary_root(session_id).resolve(strict=True)
        process_cwd = self.workspace._resolve(session_id, cwd)
        if not process_cwd.is_dir():
            raise ProcessServiceError(
                "invalid_cwd", "cwd must be a workspace directory"
            )
        process_environment = self._environment(
            environment,
            session_id=session_id,
            run_id=run_id,
            workspace=workspace,
            temporary=temporary,
        )
        process_argv = self._resolve_executable(
            process_argv, process_environment, workspace
        )
        launch = self.sandbox.wrap(
            process_argv,
            workspace,
            temporary,
            process_cwd,
            network_enabled=bool(network_enabled),
        )
        if not launch.enforced:
            raise ProcessServiceError(
                "sandbox_unavailable", "Process sandbox is not enforced"
            )
        record = self.repository.create(
            session_id=session_id,
            run_id=run_id,
            caller_id=caller_id,
            argv=process_argv,
            cwd=cwd,
            environment_keys=tuple(sorted(process_environment)),
            sandbox_backend=launch.backend,
            network_enabled=bool(network_enabled),
            limits=process_limits,
        )
        request_id = new_entity_id(EntityIdKind.BROKER_REQUEST)
        envelope = self.broker.issue(
            request_id=request_id,
            session_id=session_id,
            run_id=run_id,
            operation="process.spawn",
        )
        self.repository.issue_broker_request(
            request_id=request_id,
            process_id=record.id,
            session_id=session_id,
            run_id=run_id,
            operation="process.spawn",
            nonce=envelope.nonce,
            token_digest=envelope.token_digest,
            expires_at=envelope.expires_at,
            evidence={"sandbox": launch.backend, "argv0": process_argv[0]},
        )
        try:
            self.broker.verify(
                envelope.token,
                session_id=session_id,
                run_id=run_id,
                operation="process.spawn",
            )
            child = await asyncio.create_subprocess_exec(
                *launch.argv,
                cwd=launch.cwd,
                env=process_environment,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                preexec_fn=self._resource_limiter(process_limits),
            )
        except BaseException as error:
            self.repository.resolve_broker_request(request_id, "denied")
            self.repository.settle(
                record.id,
                ProcessStatus.FAILED,
                exit_code=None,
                error={"code": "spawn_failed", "message": str(error)},
            )
            if isinstance(error, asyncio.CancelledError):
                raise
            if isinstance(error, ProcessServiceError):
                raise
            raise ProcessServiceError("spawn_failed", str(error)) from error
        self.repository.resolve_broker_request(request_id, "accepted")
        record = self.repository.mark_running(record.id, child.pid)
        readers = (
            asyncio.create_task(
                self._read_output(record.id, "stdout", child.stdout),
                name=f"{record.id}-stdout",
            ),
            asyncio.create_task(
                self._read_output(record.id, "stderr", child.stderr),
                name=f"{record.id}-stderr",
            ),
        )
        watchdog = asyncio.create_task(
            self._watchdog(record.id), name=f"{record.id}-watchdog"
        )
        waiter = asyncio.create_task(self._wait(record.id), name=f"{record.id}-wait")
        self._live[record.id] = _LiveProcess(
            child, record, (*readers, watchdog, waiter)
        )
        self._output_locks[record.id] = asyncio.Lock()
        return record

    def _owned(
        self, process_id: str, *, session_id: str, run_id: str | None
    ) -> ProcessRecord:
        record = self.repository.get(process_id, session_id=session_id)
        if record.run_id is not None and record.run_id != run_id:
            # Do not reveal whether a different Run owns this Process.
            raise ProcessServiceError("process_not_found", "Process not found")
        return record

    async def _read_output(
        self, process_id: str, stream: str, reader: asyncio.StreamReader | None
    ) -> None:
        if reader is None:
            return
        try:
            while data := await reader.read(_READ_CHUNK_BYTES):
                lock = self._output_locks.setdefault(process_id, asyncio.Lock())
                async with lock:
                    record = await asyncio.to_thread(self.repository.get, process_id)
                    remaining = max(
                        0, record.limits["output_bytes"] - record.output_bytes
                    )
                    captured = data[:remaining]
                    try:
                        content = captured.decode("utf-8")
                        encoding = "utf-8"
                    except UnicodeDecodeError:
                        content = base64.b64encode(captured).decode("ascii")
                        encoding = "base64"
                    if captured:
                        await asyncio.to_thread(
                            self.repository.append_log,
                            process_id,
                            stream,
                            encoding,
                            content,
                            len(captured),
                        )
                    limit_reached = len(captured) < len(data) or not remaining
                if limit_reached:
                    await self._terminate(
                        process_id,
                        ProcessStatus.OUTPUT_LIMIT,
                        {"code": "output_limit_exceeded"},
                    )
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._terminate(
                process_id,
                ProcessStatus.FAILED,
                {"code": "output_capture_failed"},
            )

    async def _watchdog(self, process_id: str) -> None:
        while process_id in self._live:
            await asyncio.sleep(0.1)
            record = await asyncio.to_thread(self.repository.get, process_id)
            if record.status.terminal:
                return
            now = datetime.now(UTC)
            live = self._live.get(process_id)
            if live is not None:
                try:
                    rss = psutil.Process(live.process.pid).memory_info().rss
                except psutil.Error:
                    rss = 0
                if rss > record.limits["memory_bytes"]:
                    await self._terminate(
                        process_id,
                        ProcessStatus.FAILED,
                        {"code": "memory_limit_exceeded"},
                    )
                    return
            if (now - record.created_at).total_seconds() >= record.limits[
                "wall_time_seconds"
            ]:
                await self._terminate(
                    process_id, ProcessStatus.TIMED_OUT, {"code": "wall_time_exceeded"}
                )
                return
            if (now - record.last_activity_at).total_seconds() >= record.limits[
                "idle_time_seconds"
            ]:
                await self._terminate(
                    process_id,
                    ProcessStatus.IDLE_TIMEOUT,
                    {"code": "idle_time_exceeded"},
                )
                return

    async def _wait(self, process_id: str) -> None:
        live = self._live.get(process_id)
        if live is None:
            # start() installs the map immediately after creating this task.
            await asyncio.sleep(0)
            live = self._live.get(process_id)
        if live is None:
            return
        return_code = await live.process.wait()
        for task in live.tasks[:2]:
            with suppress(asyncio.CancelledError):
                await task
        record = await asyncio.to_thread(self.repository.get, process_id)
        if not record.status.terminal:
            status = ProcessStatus.EXITED if return_code == 0 else ProcessStatus.FAILED
            await asyncio.to_thread(
                self.repository.settle,
                process_id,
                status,
                exit_code=return_code,
                error=None if return_code == 0 else {"code": "nonzero_exit"},
            )
        current = asyncio.current_task()
        for task in live.tasks:
            if task is not current and not task.done():
                task.cancel()
        self._live.pop(process_id, None)
        self._output_locks.pop(process_id, None)

    async def _terminate(
        self, process_id: str, status: ProcessStatus, error: dict[str, str]
    ) -> ProcessRecord:
        live = self._live.get(process_id)
        settled = await asyncio.to_thread(
            self.repository.settle,
            process_id,
            status,
            exit_code=None,
            error=error,
        )
        if live is not None and live.process.returncode is None:
            with suppress(ProcessLookupError):
                os.killpg(live.process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(live.process.wait(), _TERMINATION_GRACE_SECONDS)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    os.killpg(live.process.pid, signal.SIGKILL)
                await live.process.wait()
        return settled

    async def write_stdin(
        self,
        process_id: str,
        data: str,
        *,
        session_id: str,
        run_id: str | None,
        close: bool = False,
    ) -> ProcessRecord:
        record = self._owned(process_id, session_id=session_id, run_id=run_id)
        encoded = data.encode("utf-8")
        if len(encoded) > _MAX_STDIN_BYTES:
            raise ProcessServiceError("stdin_limit", "stdin write exceeds 64 KiB")
        live = self._live.get(process_id)
        if (
            record.status is not ProcessStatus.RUNNING
            or live is None
            or live.process.stdin is None
        ):
            raise ProcessServiceError("process_not_running", "Process is not running")
        if not record.stdin_open:
            raise ProcessServiceError("stdin_closed", "Process stdin is closed")
        if encoded:
            live.process.stdin.write(encoded)
            await live.process.stdin.drain()
        if close:
            live.process.stdin.close()
            with suppress(BrokenPipeError, ConnectionResetError):
                await live.process.stdin.wait_closed()
        await asyncio.to_thread(self.repository.touch, process_id, stdin_open=not close)
        return await asyncio.to_thread(self.repository.get, process_id)

    async def cancel(
        self, process_id: str, *, session_id: str, run_id: str | None
    ) -> ProcessRecord:
        record = self._owned(process_id, session_id=session_id, run_id=run_id)
        if record.status.terminal:
            return record
        return await self._terminate(
            process_id, ProcessStatus.CANCELLED, {"code": "cancelled"}
        )

    def status(
        self, process_id: str, *, session_id: str, run_id: str | None
    ) -> ProcessRecord:
        return self._owned(process_id, session_id=session_id, run_id=run_id)

    async def wait(
        self,
        process_id: str,
        *,
        session_id: str,
        run_id: str | None,
        timeout_ms: int = 30_000,
    ) -> ProcessRecord:
        if timeout_ms <= 0 or timeout_ms > 300_000:
            raise ProcessServiceError(
                "invalid_wait_timeout", "timeout_ms must be between 1 and 300000"
            )

        async def terminal() -> ProcessRecord:
            while True:
                record = await asyncio.to_thread(
                    self._owned,
                    process_id,
                    session_id=session_id,
                    run_id=run_id,
                )
                if record.status.terminal:
                    return record
                await asyncio.sleep(0.05)

        try:
            async with asyncio.timeout(timeout_ms / 1_000):
                return await terminal()
        except TimeoutError as error:
            raise ProcessServiceError(
                "process_wait_timeout", "Process did not finish before timeout"
            ) from error

    def logs(
        self,
        process_id: str,
        *,
        session_id: str,
        run_id: str | None,
        after: int = 0,
        limit: int = 200,
    ):
        self._owned(process_id, session_id=session_id, run_id=run_id)
        return self.repository.logs(process_id, after=after, limit=limit)

    async def cancel_run(self, run_id: str) -> None:
        records = await asyncio.to_thread(self.repository.active_for_run, run_id)
        await asyncio.gather(
            *(
                self.cancel(record.id, session_id=record.session_id, run_id=run_id)
                for record in records
            ),
            return_exceptions=True,
        )

    def schedule_cancel_by_run(self, run_id: str) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self.cancel_run(run_id))
        )
