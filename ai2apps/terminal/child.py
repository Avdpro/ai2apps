"""Small PTY child bootstrap used by :mod:`ai2apps.terminal.manager`.

Keeping controlling-terminal setup in a freshly spawned interpreter avoids
using ``preexec_fn`` or ``fork()`` in the multi-threaded API server process.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import sys
import termios


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--shell", required=True)
    parser.add_argument("--exec", dest="command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()

    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.chdir(arguments.cwd)
    if arguments.command:
        os.execvpe(arguments.command[0], arguments.command, os.environ)
    os.execve(arguments.shell, [arguments.shell, "-l"], os.environ)


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        message = f"ai2apps terminal bootstrap failed: {error}\r\n"
        os.write(2, message.encode("utf-8", "replace"))
        sys.exit(126)
