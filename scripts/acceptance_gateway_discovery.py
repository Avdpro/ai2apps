#!/usr/bin/env python3
"""Verify two running Locals discover each other without printing credentials."""

from __future__ import annotations

import json
from pathlib import Path

import httpx


def api_key(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))["auth"]["api_key"]


def checked(response: httpx.Response) -> dict:
    if response.is_error:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def main() -> int:
    nodes = (
        ("upper", "http://127.0.0.1:8000", Path.home() / ".omlx/settings.json", 8011),
        ("lower", "http://127.0.0.1:8100", Path("/tmp/ai2apps-downstream/settings.json"), 8111),
    )
    originals: dict[str, dict] = {}
    headers = {name: {"Authorization": f"Bearer {api_key(settings)}"} for name, _, settings, _ in nodes}
    with httpx.Client(timeout=15.0, trust_env=False) as client:
        try:
            for name, base, _, port in nodes:
                current = checked(client.get(base + "/v1/platform/sharing/network", headers=headers[name]))
                originals[name] = current
                checked(client.patch(
                    base + "/v1/platform/sharing/network", headers=headers[name],
                    json={"mode": "share_only", "bind_host": "0.0.0.0", "port": port, "expected_revision": current["revision"]},
                ))
            results = {
                name: checked(client.post(base + "/v1/platform/sharing/discovery/refresh", headers=headers[name]))
                for name, base, _, _ in nodes
            }
            upper_ports = {item["port"] for item in results["upper"]["items"]}
            lower_ports = {item["port"] for item in results["lower"]["items"]}
            if 8111 not in upper_ports or 8011 not in lower_ports:
                raise RuntimeError(f"Mutual discovery failed: upper={upper_ports}, lower={lower_ports}")
            print(json.dumps({
                "status": "passed",
                "upper_discovered_ports": sorted(upper_ports),
                "lower_discovered_ports": sorted(lower_ports),
                "credentials_advertised": False,
            }))
            return 0
        finally:
            for name, base, _, _ in nodes:
                original = originals.get(name)
                if original is None:
                    continue
                current = checked(client.get(base + "/v1/platform/sharing/network", headers=headers[name]))
                checked(client.patch(
                    base + "/v1/platform/sharing/network", headers=headers[name],
                    json={"mode": original["mode"], "bind_host": original["bind_host"], "port": original["port"], "expected_revision": current["revision"]},
                ))


if __name__ == "__main__":
    raise SystemExit(main())
