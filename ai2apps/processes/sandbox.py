"""Portable command wrapping for enforced macOS and Linux process sandboxes."""

from __future__ import annotations

import json
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import ProcessServiceError


@dataclass(frozen=True, slots=True)
class SandboxLaunch:
    argv: tuple[str, ...]
    cwd: Path
    backend: str
    enforced: bool


class ProcessSandboxAdapter(Protocol):
    name: str

    def wrap(
        self,
        argv: tuple[str, ...],
        workspace: Path,
        temporary: Path,
        cwd: Path,
        *,
        network_enabled: bool,
    ) -> SandboxLaunch: ...


class MacOSSandboxAdapter:
    name = "macos-seatbelt"

    def __init__(self, sandbox_exec: str = "/usr/bin/sandbox-exec") -> None:
        self.sandbox_exec = sandbox_exec

    def wrap(self, argv, workspace, temporary, cwd, *, network_enabled):
        if not Path(self.sandbox_exec).is_file():
            raise ProcessServiceError(
                "sandbox_unavailable", "macOS sandbox-exec is unavailable"
            )
        policy_directory = workspace.parent / "policy"
        policy_directory.mkdir(parents=True, exist_ok=True)
        policy = policy_directory / "process.sb"
        writable = [workspace.resolve(), temporary.resolve()]
        readable = [
            Path("/System"),
            Path("/usr"),
            Path("/bin"),
            Path("/sbin"),
            Path("/Library"),
            Path("/private/var/db"),
            Path("/dev"),
            Path("/opt/homebrew"),
            Path("/usr/local"),
        ]
        lines = [
            "(version 1)",
            "(deny default)",
            '(import "system.sb")',
            "(allow process*)",
            "(allow sysctl-read)",
            "(allow file-read-metadata)",
        ]
        for path in readable + writable:
            if path.exists():
                lines.append(f"(allow file-read* (subpath {json.dumps(str(path))}))")
        for path in writable:
            lines.append(f"(allow file-write* (subpath {json.dumps(str(path))}))")
        lines.append("(allow network*)" if network_enabled else "(deny network*)")
        policy.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return SandboxLaunch(
            (self.sandbox_exec, "-f", str(policy), "--", *argv),
            cwd,
            self.name,
            True,
        )


class LinuxBubblewrapAdapter:
    name = "linux-bubblewrap"

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("bwrap")

    def wrap(self, argv, workspace, temporary, cwd, *, network_enabled):
        if self.executable is None:
            raise ProcessServiceError(
                "sandbox_unavailable", "Linux Process Service requires bubblewrap"
            )
        command = [
            self.executable,
            "--die-with-parent",
            "--new-session",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
        ]
        if not network_enabled:
            command.append("--unshare-net")
        for root in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc"):
            if Path(root).exists():
                command.extend(("--ro-bind", root, root))
        command.extend(
            (
                "--dev",
                "/dev",
                "--proc",
                "/proc",
                "--tmpfs",
                "/tmp",
                "--bind",
                str(workspace),
                str(workspace),
                "--bind",
                str(temporary),
                str(temporary),
                "--chdir",
                str(cwd),
                "--",
                *argv,
            )
        )
        return SandboxLaunch(tuple(command), cwd, self.name, True)


class TestSandboxAdapter:
    """Explicit test double; production selection never chooses this adapter."""

    name = "test-sandbox"

    def wrap(self, argv, workspace, temporary, cwd, *, network_enabled):
        return SandboxLaunch(tuple(argv), cwd, self.name, True)


def default_sandbox_adapter() -> ProcessSandboxAdapter:
    system = platform.system()
    if system == "Darwin":
        return MacOSSandboxAdapter()
    if system == "Linux":
        return LinuxBubblewrapAdapter()
    raise ProcessServiceError(
        "sandbox_unavailable", f"No enforced Process sandbox for {system}"
    )
