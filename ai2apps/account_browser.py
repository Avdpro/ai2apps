"""Open the public Cloud wallet using the OS default browser, without credentials."""

import asyncio
import sys
from urllib.parse import urlencode


def recharge_url() -> str:
    return "https://home.ai2apps.com/signin?" + urlencode({
        "returnTo": "/account?panel=credit-purchase#credit",
    })


async def open_recharge_page() -> None:
    if sys.platform != "darwin":
        raise ValueError("System browser launch is currently supported on macOS only")
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/open", recharge_url(),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.wait(), timeout=10)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise ValueError("Unable to open the system browser")
