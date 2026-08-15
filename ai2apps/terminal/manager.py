"""Lifecycle and byte transport for system-owned interactive PTY sessions."""

from __future__ import annotations

import asyncio
import errno
import fcntl
import os
import pty
import secrets
import shutil
import signal
import struct
import subprocess
import sys
import termios
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_READ_BYTES = 64 * 1024
_BACKLOG_BYTES = 2 * 1024 * 1024
_MAX_SESSIONS = 12
_QUEUE_CHUNKS = 256
_INPUT_BUFFER_BYTES = 256 * 1024
_EXITED_HISTORY = 24
_TERMINATION_GRACE_SECONDS = 1.0


class TerminalServiceError(RuntimeError):
    """A stable error suitable for an HTTP API response."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class TerminalSession:
    id: str
    title: str
    cwd: str
    shell: str
    pid: int
    cols: int
    rows: int
    created_at: datetime
    owner: str = "terminal"
    owner_id: str | None = None
    status: str = "running"
    exit_code: int | None = None
    finished_at: datetime | None = None
    master_fd: int = field(default=-1, repr=False)
    process: subprocess.Popen[bytes] | None = field(default=None, repr=False)
    backlog: deque[bytes] = field(default_factory=deque, repr=False)
    backlog_bytes: int = field(default=0, repr=False)
    subscribers: dict[str, asyncio.Queue[bytes | dict[str, Any]]] = field(
        default_factory=dict, repr=False
    )
    input_buffer: bytearray = field(default_factory=bytearray, repr=False)
    wait_task: asyncio.Task[None] | None = field(default=None, repr=False)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "cwd": self.cwd,
            "shell": self.shell,
            "pid": self.pid,
            "cols": self.cols,
            "rows": self.rows,
            "owner": self.owner,
            "owner_id": self.owner_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "created_at": self.created_at.isoformat(),
            "finished_at": (
                None if self.finished_at is None else self.finished_at.isoformat()
            ),
        }


class TerminalManager:
    """Own PTYs independently from browser connections."""

    def __init__(
        self,
        *,
        default_cwd: str | Path | None = None,
        max_sessions: int = _MAX_SESSIONS,
        backlog_bytes: int = _BACKLOG_BYTES,
    ) -> None:
        if max_sessions <= 0 or backlog_bytes <= 0:
            raise ValueError("terminal limits must be positive")
        self.default_cwd = Path(default_cwd or os.getcwd()).resolve()
        self.max_sessions = max_sessions
        self.backlog_limit = backlog_bytes
        self._sessions: dict[str, TerminalSession] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping = False

    async def startup(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stopping = False

    async def shutdown(self) -> None:
        self._stopping = True
        await asyncio.gather(
            *(self.close(item.id) for item in tuple(self._sessions.values())),
            return_exceptions=True,
        )
        self._loop = None

    def list(self, *, owner: str | None = None) -> list[dict[str, Any]]:
        return [
            item.public()
            for item in sorted(
                self._sessions.values(), key=lambda value: value.created_at
            )
            if owner is None or item.owner == owner
        ]

    def get(self, session_id: str) -> TerminalSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise TerminalServiceError("not_found", "Terminal session not found")
        return session

    @staticmethod
    def _shell() -> str:
        candidate = os.environ.get("SHELL", "")
        if candidate and Path(candidate).is_absolute() and os.access(candidate, os.X_OK):
            return str(Path(candidate).resolve())
        for name in ("zsh", "bash", "sh"):
            resolved = shutil.which(name)
            if resolved:
                return str(Path(resolved).resolve())
        raise TerminalServiceError("shell_unavailable", "No interactive shell found")

    def _cwd(self, value: str | None) -> Path:
        if value is None or not value.strip():
            path = self.default_cwd
        else:
            if "\x00" in value or len(value.encode("utf-8")) > 4096:
                raise TerminalServiceError("invalid_cwd", "Invalid working directory")
            path = Path(value).expanduser().resolve()
        if not path.is_dir():
            raise TerminalServiceError("invalid_cwd", "Working directory does not exist")
        return path

    async def create(
        self,
        *,
        title: str | None = None,
        cwd: str | None = None,
        cols: int = 100,
        rows: int = 30,
        command: list[str] | tuple[str, ...] | None = None,
        environment: dict[str, str] | None = None,
        owner: str = "terminal",
        owner_id: str | None = None,
    ) -> TerminalSession:
        if self._stopping:
            raise TerminalServiceError("stopping", "Terminal service is stopping")
        self._prune_exited()
        active = sum(item.status == "running" for item in self._sessions.values())
        if active >= self.max_sessions:
            raise TerminalServiceError(
                "session_limit", f"At most {self.max_sessions} terminals may run"
            )
        loop = asyncio.get_running_loop()
        self._loop = loop
        if owner not in {"terminal", "coder", "system"}:
            raise TerminalServiceError("invalid_owner", "Invalid terminal owner")
        if owner_id is not None and (
            not owner_id or "\x00" in owner_id or len(owner_id.encode("utf-8")) > 200
        ):
            raise TerminalServiceError("invalid_owner", "Invalid terminal owner ID")
        workdir = self._cwd(cwd)
        shell = self._shell()
        cols, rows = self._dimensions(cols, rows)
        master_fd, slave_fd = pty.openpty()
        try:
            self._set_winsize(slave_fd, cols, rows)
            child_environment = dict(os.environ)
            child_environment.update(
                {
                    "TERM": child_environment.get("TERM", "xterm-256color"),
                    "COLORTERM": "truecolor",
                    "TERM_PROGRAM": "AI2Apps",
                }
            )
            for key, value in (environment or {}).items():
                if not key or "\x00" in key or "=" in key or "\x00" in value:
                    raise TerminalServiceError(
                        "invalid_environment", "Invalid terminal environment"
                    )
                child_environment[key] = value
            child_argv = [
                sys.executable,
                "-m",
                "ai2apps.terminal.child",
                "--cwd",
                str(workdir),
                "--shell",
                shell,
            ]
            if command:
                if any(not isinstance(item, str) or not item or "\x00" in item for item in command):
                    raise TerminalServiceError("invalid_command", "Invalid command")
                child_argv.extend(("--exec", *command))
            process = subprocess.Popen(
                child_argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                env=child_environment,
            )
        except BaseException:
            os.close(master_fd)
            raise
        finally:
            os.close(slave_fd)

        os.set_blocking(master_fd, False)
        session_id = f"term_{secrets.token_hex(16)}"
        label = (title or "Terminal").strip()[:80] or "Terminal"
        session = TerminalSession(
            id=session_id,
            title=label,
            cwd=str(workdir),
            shell=shell,
            pid=process.pid,
            cols=cols,
            rows=rows,
            created_at=datetime.now(UTC),
            owner=owner,
            owner_id=owner_id,
            master_fd=master_fd,
            process=process,
        )
        self._sessions[session_id] = session
        loop.add_reader(master_fd, self._read_ready, session_id)
        session.wait_task = asyncio.create_task(
            self._wait(session_id), name=f"terminal-wait-{session_id}"
        )
        return session

    def _prune_exited(self) -> None:
        exited = sorted(
            (item for item in self._sessions.values() if item.status != "running"),
            key=lambda item: item.finished_at or item.created_at,
            reverse=True,
        )
        for session in exited[_EXITED_HISTORY:]:
            session.subscribers.clear()
            self._sessions.pop(session.id, None)

    @staticmethod
    def _dimensions(cols: int, rows: int) -> tuple[int, int]:
        if not 20 <= cols <= 1000 or not 5 <= rows <= 500:
            raise TerminalServiceError("invalid_size", "Invalid terminal dimensions")
        return int(cols), int(rows)

    @staticmethod
    def _set_winsize(fd: int, cols: int, rows: int) -> None:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def resize(self, session_id: str, cols: int, rows: int) -> None:
        session = self.get(session_id)
        if session.status != "running":
            return
        cols, rows = self._dimensions(cols, rows)
        try:
            self._set_winsize(session.master_fd, cols, rows)
        except OSError as error:
            raise TerminalServiceError("closed", "Terminal is closed") from error
        session.cols = cols
        session.rows = rows

    def write(self, session_id: str, data: str | bytes) -> None:
        session = self.get(session_id)
        if session.status != "running" or session.master_fd < 0:
            raise TerminalServiceError("closed", "Terminal is closed")
        payload = data.encode("utf-8") if isinstance(data, str) else data
        if len(payload) > 64 * 1024:
            raise TerminalServiceError("input_too_large", "Terminal input is too large")
        if len(session.input_buffer) + len(payload) > _INPUT_BUFFER_BYTES:
            raise TerminalServiceError("input_backpressure", "Terminal input is busy")
        session.input_buffer.extend(payload)
        self._flush_input(session_id)

    def _flush_input(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None or session.master_fd < 0:
            return
        while session.input_buffer:
            try:
                written = os.write(session.master_fd, session.input_buffer)
            except BlockingIOError:
                if self._loop is not None:
                    self._loop.add_writer(
                        session.master_fd, self._flush_input, session_id
                    )
                return
            except OSError:
                session.input_buffer.clear()
                return
            del session.input_buffer[:written]
        if self._loop is not None:
            self._loop.remove_writer(session.master_fd)

    def subscribe(
        self, session_id: str
    ) -> tuple[str, asyncio.Queue[bytes | dict[str, Any]], bytes]:
        session = self.get(session_id)
        subscriber_id = secrets.token_hex(12)
        queue: asyncio.Queue[bytes | dict[str, Any]] = asyncio.Queue(_QUEUE_CHUNKS)
        session.subscribers[subscriber_id] = queue
        return subscriber_id, queue, b"".join(session.backlog)

    def unsubscribe(self, session_id: str, subscriber_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.subscribers.pop(subscriber_id, None)

    def _append_output(self, session: TerminalSession, data: bytes) -> None:
        session.backlog.append(data)
        session.backlog_bytes += len(data)
        while session.backlog_bytes > self.backlog_limit and session.backlog:
            removed = session.backlog.popleft()
            session.backlog_bytes -= len(removed)
        for queue in tuple(session.subscribers.values()):
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(data)

    def _broadcast_event(self, session: TerminalSession, event: dict[str, Any]) -> None:
        for queue in tuple(session.subscribers.values()):
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(event)

    def _read_ready(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None or session.master_fd < 0:
            return
        while True:
            try:
                data = os.read(session.master_fd, _READ_BYTES)
            except BlockingIOError:
                return
            except OSError as error:
                if error.errno in (errno.EIO, errno.EBADF):
                    self._remove_reader(session)
                    return
                raise
            if not data:
                self._remove_reader(session)
                return
            self._append_output(session, data)

    def _remove_reader(self, session: TerminalSession) -> None:
        if self._loop is not None and session.master_fd >= 0:
            self._loop.remove_reader(session.master_fd)
            self._loop.remove_writer(session.master_fd)

    async def _wait(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is None or session.process is None:
            return
        exit_code = await asyncio.to_thread(session.process.wait)
        self._read_ready(session_id)
        self._remove_reader(session)
        if session.master_fd >= 0:
            with suppress(OSError):
                os.close(session.master_fd)
            session.master_fd = -1
        session.status = "exited"
        session.exit_code = exit_code
        session.finished_at = datetime.now(UTC)
        self._broadcast_event(
            session,
            {"type": "exit", "exit_code": exit_code, "session": session.public()},
        )

    async def close(self, session_id: str) -> None:
        session = self.get(session_id)
        process = session.process
        if process is not None and process.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGHUP)
            try:
                await asyncio.wait_for(
                    asyncio.shield(session.wait_task),
                    timeout=_TERMINATION_GRACE_SECONDS,
                )
            except TimeoutError:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                if session.wait_task is not None:
                    await session.wait_task
        self._remove_reader(session)
        if session.master_fd >= 0:
            with suppress(OSError):
                os.close(session.master_fd)
            session.master_fd = -1
        session.subscribers.clear()
        self._sessions.pop(session_id, None)
