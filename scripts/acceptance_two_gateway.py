#!/usr/bin/env python3
"""Run a disposable upstream/downstream Local acceptance flow without printing secrets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def api_key(settings_path: Path) -> str:
    return json.loads(settings_path.read_text(encoding="utf-8"))["auth"]["api_key"]


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
    parser.add_argument("--skip-model-call", action="store_true")
    args = parser.parse_args()

    upper_headers = {"Authorization": f"Bearer {api_key(args.upstream_settings)}"}
    lower_headers = {"Authorization": f"Bearer {api_key(args.downstream_settings)}"}
    grant_id = gateway_id = None
    created_exports: list[str] = []
    original_network = original_routing = None

    with httpx.Client(timeout=180.0, trust_env=False) as client:
        try:
            exports = checked(client.get(args.upstream + "/v1/platform/sharing/exports", headers=upper_headers))["items"]

            def ensure_export(kind: str, target_id: str, display_name: str) -> str:
                for item in exports:
                    if item["kind"] == kind and item["target_id"] == target_id and item["status"] != "revoked":
                        return item["id"]
                item = checked(client.post(
                    args.upstream + "/v1/platform/sharing/exports", headers=upper_headers,
                    json={"kind": kind, "target_id": target_id, "display_name": display_name},
                ))
                exports.append(item)
                created_exports.append(item["id"])
                return item["id"]

            echo_export = ensure_export("tool", "system.echo", "Acceptance Echo")
            models = checked(client.get(args.upstream + "/v1/models", headers=upper_headers))["data"]
            local_ids = [item["id"] for item in models if not item["id"].startswith(("cloud/", "gateway/"))]
            if not local_ids:
                raise RuntimeError("Upstream has no local model to share")
            model_id = next((value for value in local_ids if "Qwen3-0.6B" in value), local_ids[0])
            model_export = ensure_export("model", model_id, "Acceptance Model")

            original_network = checked(client.get(args.upstream + "/v1/platform/sharing/network", headers=upper_headers))
            checked(client.patch(
                args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                json={"mode": "share_only", "bind_host": "0.0.0.0", "port": 8011, "expected_revision": original_network["revision"]},
            ))
            issued = checked(client.post(
                args.upstream + "/v1/platform/sharing/grants", headers=upper_headers,
                json={"label": "Disposable downstream acceptance", "export_ids": [echo_export, model_export], "max_concurrency": 2, "expires_in_seconds": 3600},
            ))
            grant_id = issued["grant"]["id"]
            openai_base_url = args.upstream_share.rstrip("/") + urlsplit(issued["openai_base_url"]).path
            mcp_url = args.upstream_share.rstrip("/") + urlsplit(issued["mcp_url"]).path

            gateway = checked(client.post(
                args.downstream + "/v1/platform/upstreams", headers=lower_headers,
                json={
                    "label": "Current Local parent", "openai_base_url": openai_base_url,
                    "mcp_url": mcp_url, "token": issued["token"],
                    "remote_node_id": issued["node_id"],
                    "ancestor_node_ids": issued.get("ancestor_node_ids", []),
                    "is_parent": True, "priority": 100,
                    "route_models": True, "route_mcp": True,
                },
            ))
            gateway_id = gateway["id"]
            if not gateway["is_default"] or gateway["remote_node_id"] != issued["node_id"]:
                raise RuntimeError("First Parent Local was not identity-bound and selected as default")
            projection = checked(client.post(
                args.downstream + f"/v1/platform/upstreams/{gateway_id}/probe", headers=lower_headers,
            ))
            if projection["health_status"] != "online":
                raise RuntimeError(f"Upstream probe failed: {projection.get('last_error')}")

            projected_models = checked(client.get(args.downstream + "/v1/models", headers=lower_headers))["data"]
            projected_model = next(item["id"] for item in projected_models if item["id"].startswith(f"gateway/{gateway_id}/"))
            tools = checked(client.get(args.downstream + "/v1/platform/tools", headers=lower_headers))["items"]
            projected_tool = next(item["qualified_name"] for item in tools if item["qualified_name"].startswith(f"gateway.{gateway_id[4:]}") and item["qualified_name"].endswith("system.echo"))
            invoked = checked(client.post(
                args.downstream + f"/v1/platform/tools/{projected_tool}/invoke", headers=lower_headers,
                json={"arguments": {"value": "two-gateway-ok"}},
            ))
            if invoked["output"] != {"value": "two-gateway-ok"}:
                raise RuntimeError(f"Unexpected projected Tool output: {invoked['output']}")

            if not args.skip_model_call:
                original_routing = checked(client.get(
                    args.downstream + "/v1/platform/upstreams/routing", headers=lower_headers,
                ))
                checked(client.patch(
                    args.downstream + "/v1/platform/upstreams/routing", headers=lower_headers,
                    json={"model_policy": "parent_first", "expected_revision": original_routing["revision"]},
                ))
                completion = checked(client.post(
                    args.downstream + "/v1/chat/completions", headers=lower_headers,
                    json={"model": model_id, "messages": [{"role": "user", "content": "Reply only with OK"}], "max_tokens": 8, "stream": False},
                ))
                if not completion.get("choices"):
                    raise RuntimeError("Projected model returned no choices")

            activity = checked(client.get(
                args.downstream + "/v1/platform/upstreams/activity",
                headers=lower_headers,
                params={"gateway_id": gateway_id, "limit": 20},
            ))["items"]
            expected_operations = {"probe", "tool"}
            if not args.skip_model_call:
                expected_operations.add("model")
            if not expected_operations.issubset({item["operation"] for item in activity}):
                raise RuntimeError(f"Missing upstream activity metadata: {activity}")

            degraded_after_disconnect = False
            if not args.skip_model_call:
                active_network = checked(client.get(
                    args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                ))
                checked(client.patch(
                    args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                    json={"mode": "disabled", "bind_host": active_network["bind_host"], "port": active_network["port"], "expected_revision": active_network["revision"]},
                ))
                failed = client.post(
                    args.downstream + "/v1/chat/completions", headers=lower_headers,
                    json={"model": projected_model, "messages": [{"role": "user", "content": "Reply only with OK"}], "max_tokens": 1, "stream": False},
                )
                if failed.status_code not in {404, 502}:
                    raise RuntimeError(f"Disconnected upstream returned HTTP {failed.status_code}")
                downstream_gateway = next(
                    item for item in checked(client.get(args.downstream + "/v1/platform/upstreams", headers=lower_headers))["items"]
                    if item["id"] == gateway_id
                )
                remaining_models = checked(client.get(args.downstream + "/v1/models", headers=lower_headers))["data"]
                if downstream_gateway["health_status"] != "offline" or any(item["id"] == projected_model for item in remaining_models):
                    raise RuntimeError("Disconnected gateway did not degrade and remove its model projection")
                degraded_after_disconnect = True
                disabled_network = checked(client.get(
                    args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                ))
                checked(client.patch(
                    args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                    json={"mode": "share_only", "bind_host": "0.0.0.0", "port": 8011, "expected_revision": disabled_network["revision"]},
                ))
                recovered = checked(client.post(
                    args.downstream + f"/v1/platform/upstreams/{gateway_id}/probe", headers=lower_headers,
                ))
                if recovered["health_status"] != "online":
                    raise RuntimeError("Gateway did not recover after its listener returned")

            print(json.dumps({
                "status": "passed", "upstream": args.upstream,
                "downstream": args.downstream, "projected_model": projected_model,
                "projected_tool": projected_tool, "activity_count": len(activity),
                "degraded_after_disconnect": degraded_after_disconnect,
            }, ensure_ascii=False))
            return 0
        finally:
            if original_routing:
                current_routing = checked(client.get(
                    args.downstream + "/v1/platform/upstreams/routing", headers=lower_headers,
                ))
                client.patch(
                    args.downstream + "/v1/platform/upstreams/routing", headers=lower_headers,
                    json={"model_policy": original_routing["model_policy"], "expected_revision": current_routing["revision"]},
                )
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
