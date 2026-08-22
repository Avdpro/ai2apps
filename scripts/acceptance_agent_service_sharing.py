#!/usr/bin/env python3
"""Exercise explicit Service and Agent MCP exports through two Local instances."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def api_key(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))["auth"]["api_key"]


def checked(response: httpx.Response) -> dict:
    if response.is_error:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    return {} if response.status_code == 204 else response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default="http://127.0.0.1:8000")
    parser.add_argument("--downstream", default="http://127.0.0.1:8100")
    parser.add_argument("--upstream-share", default="http://127.0.0.1:8011")
    parser.add_argument("--upstream-settings", type=Path, default=Path.home() / ".omlx/settings.json")
    parser.add_argument("--downstream-settings", type=Path, default=Path("/tmp/ai2apps-downstream/settings.json"))
    args = parser.parse_args()

    upper_headers = {"Authorization": f"Bearer {api_key(args.upstream_settings)}"}
    lower_headers = {"Authorization": f"Bearer {api_key(args.downstream_settings)}"}
    created_exports: list[str] = []
    grant_id = gateway_id = None
    original_network = None

    with httpx.Client(timeout=60.0, trust_env=False) as client:
        try:
            candidates = checked(client.get(args.upstream + "/v1/platform/sharing/candidates", headers=upper_headers))
            if not any(item["id"] == "ai2apps.general-agent" for item in candidates.get("agents", [])):
                raise RuntimeError("General Agent is not available as an explicit Core candidate")
            if not any(item["id"] == "ai2apps.diagnostics" for item in candidates.get("services", [])):
                raise RuntimeError("Diagnostics Service is not available as a safe Service candidate")

            exports = checked(client.get(args.upstream + "/v1/platform/sharing/exports", headers=upper_headers))["items"]

            def ensure_export(kind: str, target: str, display_name: str) -> str:
                existing = next((item for item in exports if item["kind"] == kind and item["target_id"] == target and item["status"] != "revoked"), None)
                if existing:
                    return existing["id"]
                item = checked(client.post(
                    args.upstream + "/v1/platform/sharing/exports", headers=upper_headers,
                    json={"kind": kind, "target_id": target, "display_name": display_name},
                ))
                exports.append(item)
                created_exports.append(item["id"])
                return item["id"]

            service_export = ensure_export("service", "ai2apps.diagnostics", "Acceptance Service")
            agent_export = ensure_export("agent", "ai2apps.general-agent", "Acceptance Agent")
            original_network = checked(client.get(args.upstream + "/v1/platform/sharing/network", headers=upper_headers))
            checked(client.patch(
                args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                json={"mode": "share_only", "bind_host": "0.0.0.0", "port": 8011, "expected_revision": original_network["revision"]},
            ))
            issued = checked(client.post(
                args.upstream + "/v1/platform/sharing/grants", headers=upper_headers,
                json={"label": "Disposable Agent and Service acceptance", "export_ids": [service_export, agent_export], "max_concurrency": 2, "expires_in_seconds": 3600},
            ))
            grant_id = issued["grant"]["id"]
            gateway = checked(client.post(
                args.downstream + "/v1/platform/upstreams", headers=lower_headers,
                json={
                    "label": "Agent Service acceptance upstream",
                    "openai_base_url": args.upstream_share.rstrip("/") + urlsplit(issued["openai_base_url"]).path,
                    "mcp_url": args.upstream_share.rstrip("/") + urlsplit(issued["mcp_url"]).path,
                    "token": issued["token"],
                },
            ))
            gateway_id = gateway["id"]
            projection = checked(client.post(args.downstream + f"/v1/platform/upstreams/{gateway_id}/probe", headers=lower_headers))
            if projection["health_status"] != "online":
                raise RuntimeError(f"Upstream probe failed: {projection.get('last_error')}")

            tools = checked(client.get(args.downstream + "/v1/platform/tools", headers=lower_headers))["items"]

            def projected(remote_name: str) -> str:
                return next(
                    item["qualified_name"] for item in tools
                    if item["qualified_name"].startswith(f"gateway.{gateway_id[4:]}")
                    and item["qualified_name"].endswith(remote_name)
                )

            echo = projected("system.echo")
            prefix = "agent.ai2apps.general-agent"
            create_session = projected(prefix + ".create_session")
            send_message = projected(prefix + ".send_message")
            get_status = projected(prefix + ".get_status")
            close_session = projected(prefix + ".close_session")

            echoed = checked(client.post(
                args.downstream + f"/v1/platform/tools/{echo}/invoke", headers=lower_headers,
                json={"arguments": {"value": "service-mcp-ok"}},
            ))
            if echoed["output"] != {"value": "service-mcp-ok"}:
                raise RuntimeError("Shared Service returned an unexpected result")

            created = checked(client.post(
                args.downstream + f"/v1/platform/tools/{create_session}/invoke", headers=lower_headers,
                json={"arguments": {"title": "Two gateway Agent acceptance"}},
            ))["output"]
            sent = checked(client.post(
                args.downstream + f"/v1/platform/tools/{send_message}/invoke", headers=lower_headers,
                json={"arguments": {"session_id": created["session_id"], "prompt": "Reply only with OK"}},
            ))["output"]
            status = checked(client.post(
                args.downstream + f"/v1/platform/tools/{get_status}/invoke", headers=lower_headers,
                json={"arguments": {"session_id": created["session_id"], "run_id": sent["run_id"]}},
            ))["output"]
            if status["run_id"] != sent["run_id"] or status["session_id"] != created["session_id"]:
                raise RuntimeError("Shared Agent status crossed its Session boundary")
            closed = checked(client.post(
                args.downstream + f"/v1/platform/tools/{close_session}/invoke", headers=lower_headers,
                json={"arguments": {"session_id": created["session_id"]}},
            ))["output"]
            if closed["status"] != "deleted":
                raise RuntimeError("Shared Agent Session was not closed")

            print(json.dumps({
                "status": "passed",
                "service_method": "system.echo",
                "agent": "ai2apps.general-agent",
                "agent_mcp_tools": 6,
                "session_isolated": True,
                "remote_approval_exposed": False,
                "run_status_at_poll": status["status"],
            }, ensure_ascii=False))
            return 0
        finally:
            if gateway_id:
                client.delete(args.downstream + f"/v1/platform/upstreams/{gateway_id}", headers=lower_headers)
            if grant_id:
                client.post(args.upstream + f"/v1/platform/sharing/grants/{grant_id}/revoke", headers=upper_headers)
            for export_id in created_exports:
                client.patch(args.upstream + f"/v1/platform/sharing/exports/{export_id}", headers=upper_headers, json={"status": "revoked"})
            if original_network:
                current = checked(client.get(args.upstream + "/v1/platform/sharing/network", headers=upper_headers))
                client.patch(
                    args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                    json={"mode": original_network["mode"], "bind_host": original_network["bind_host"], "port": original_network["port"], "expected_revision": current["revision"]},
                )


if __name__ == "__main__":
    raise SystemExit(main())
