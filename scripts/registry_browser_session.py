"""Read one explicitly authorized publishing session from the live Dev Shell.

Never log protocol replies, credentials, or cookie values. This is a privileged
CLI client of the existing authenticated BiDi broker, not a browser REST API.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
from websockets.asyncio.client import connect

from ai2apps.browser.shell_bidi_gateway import (
    ShellBiDiEndpoint, ShellBiDiSessionBroker, _bootstrap_command,
)
from ai2apps.cloud_client import cloud_browser_cookie_name


def select_session_cookie(result: dict, cookie_name: str) -> str:
    cookies = result.get("cookies", [])
    matches = [c for c in cookies if isinstance(c, dict)
               and c.get("name") == cookie_name
               and c.get("domain") == "127.0.0.1" and c.get("path") == "/"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one scoped publishing session cookie")
    value = matches[0].get("value", {})
    if not isinstance(value, dict) or value.get("type") != "string":
        raise ValueError("Unsupported publishing session cookie encoding")
    session = value.get("value")
    if not isinstance(session, str) or not session or len(session) > 4096:
        raise ValueError("Invalid publishing session cookie")
    return "browser:" + session


async def live_browser_session_namespace(base_path: Path, security_instance_id: str) -> str:
    """Use only the selected instance and its exact app-shell Profile; fail closed."""
    stage = "instance identity"
    try:
        base_path = base_path.resolve(strict=True)
        if base_path.name != "data":
            raise ValueError("Expected an instance data directory")
        instance = base_path.parent
        run = instance / "run"
        local = json.loads((run / "local.json").read_text())
        port = local["actual_port"]
        if type(port) is not int or not 1024 <= port <= 65535 or local["instance_id"] != instance.name:
            raise ValueError("Invalid Local identity")
        stage = "Local bootstrap"
        async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
            response = await client.get(f"http://127.0.0.1:{port}/v1/platform/client/bootstrap")
            response.raise_for_status()
            bootstrap = response.json()
        if bootstrap.get("installation_id") != security_instance_id or bootstrap.get("instance_id") != instance.name:
            raise ValueError("Local installation mismatch")
        stage = "Shell endpoint"
        endpoint = ShellBiDiEndpoint.load(run / "shell-automation.json")

        class InstanceBroker(ShellBiDiSessionBroker):
            @staticmethod
            def _state_path():
                return run / "shell-bidi-session.json"

        stage = "shared BiDi session"
        session = await InstanceBroker().ensure(endpoint, connect)
        stage = "Shell Profile validation"
        profile = session.capabilities.get("moz:profile")
        expected = instance / "browser-profiles" / "app-shell"
        if not isinstance(profile, str) or Path(profile).resolve() != expected.resolve():
            raise ValueError("Shell Profile mismatch")
        name = cloud_browser_cookie_name(security_instance_id)
        stage = "scoped cookie request"
        async with connect(session.web_socket_url,
                           additional_headers={"Authorization": endpoint.authorization},
                           open_timeout=5, close_timeout=2, max_size=65536, proxy=None) as socket:
            result = await _bootstrap_command(socket, 1, "storage.getCookies", {
                "filter": {"name": name, "domain": "127.0.0.1", "path": "/"},
                "partition": {"type": "storageKey", "userContext": "default"},
            })
        # Disconnect only this attachment; never end the Shell's shared session.
        return select_session_cookie(result, name)
    except Exception:
        # Protocol/server exceptions may echo credentials. Never chain them.
        raise RuntimeError(
            f"Live publishing session unavailable ({stage}). Open the selected instance's "
            "Shell and verify its login/Profile; no database fallback was attempted."
        ) from None
