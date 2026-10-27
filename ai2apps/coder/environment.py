"""Discover the user's CLI search path for desktop-launched Coder sessions."""
from __future__ import annotations

import os
from pathlib import Path
import pwd
import subprocess
import time

_cached_shell_path: tuple[tuple[str, str], float, str] | None = None


def _login_shell_path() -> str:
    global _cached_shell_path
    shell = os.environ.get("SHELL", "")
    if not shell or not Path(shell).is_absolute():
        shell = pwd.getpwuid(os.getuid()).pw_shell
    key = (shell, os.environ.get("PATH", ""))
    now = time.monotonic()
    if _cached_shell_path and _cached_shell_path[0] == key and now < _cached_shell_path[1]:
        return _cached_shell_path[2]
    discovered = ""
    try:
        # Interactive login startup includes zshrc/bashrc version-manager setup.
        # Markers isolate PATH from banners or other shell startup output.
        result = subprocess.run(
            [shell, "-ilc", "printf '\\n__AI2APPS_PATH_BEGIN__\\n'; /usr/bin/printenv PATH; printf '__AI2APPS_PATH_END__\\n'"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=3, cwd=Path.home(),
        )
        if result.returncode == 0:
            discovered = result.stdout.split("__AI2APPS_PATH_BEGIN__\n", 1)[1].split(
                "\n__AI2APPS_PATH_END__", 1
            )[0].strip()
    except (OSError, subprocess.TimeoutExpired, IndexError, UnicodeError):
        pass
    _cached_shell_path = (key, now + 30, discovered)
    return discovered


def cli_search_path(managed_root: Path) -> str:
    """Keep explicit inherited paths first; supplement GUI and version-manager paths."""
    candidates = [
        str(managed_root / "node_modules" / ".bin"),
        *os.environ.get("PATH", "").split(os.pathsep),
        *_login_shell_path().split(os.pathsep),
        "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin",
    ]
    # Never turn an empty/relative PATH component into project-local execution.
    return os.pathsep.join(dict.fromkeys(
        part for part in candidates if part and Path(part).is_absolute()
    ))
