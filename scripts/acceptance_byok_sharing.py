#!/usr/bin/env python3
"""Verify that a Local BYOK model can be shared without exposing its Provider key."""

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
    parser.add_argument("--model", default="cloud/openai/gpt-5.6-luna")
    parser.add_argument("--upstream-settings", type=Path, default=Path.home() / ".omlx/settings.json")
    parser.add_argument("--downstream-settings", type=Path, default=Path("/tmp/ai2apps-downstream/settings.json"))
    args = parser.parse_args()

    upper_headers = {"Authorization": f"Bearer {api_key(args.upstream_settings)}"}
    lower_headers = {"Authorization": f"Bearer {api_key(args.downstream_settings)}"}
    grant_id = gateway_id = export_id = None
    created_export = False
    original_network = None

    with httpx.Client(timeout=180.0, trust_env=False) as client:
        try:
            models = checked(client.get(args.upstream + "/v1/models", headers=upper_headers))["data"]
            model = next((item for item in models if item["id"] == args.model), None)
            if not model:
                raise RuntimeError(f"BYOK model is not available: {args.model}")
            if model.get("source") != "local_byok" or model.get("shareable") is not True:
                raise RuntimeError(f"Model has unsafe sharing metadata: {model}")

            exports = checked(client.get(args.upstream + "/v1/platform/sharing/exports", headers=upper_headers))["items"]
            existing = next(
                (item for item in exports if item["kind"] == "model" and item["target_id"] == args.model and item["status"] != "revoked"),
                None,
            )
            if existing:
                export_id = existing["id"]
            else:
                exported = checked(client.post(
                    args.upstream + "/v1/platform/sharing/exports", headers=upper_headers,
                    json={"kind": "model", "target_id": args.model, "display_name": "BYOK acceptance model"},
                ))
                export_id = exported["id"]
                created_export = True

            original_network = checked(client.get(args.upstream + "/v1/platform/sharing/network", headers=upper_headers))
            checked(client.patch(
                args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                json={"mode": "share_only", "bind_host": "0.0.0.0", "port": 8011, "expected_revision": original_network["revision"]},
            ))
            issued = checked(client.post(
                args.upstream + "/v1/platform/sharing/grants", headers=upper_headers,
                json={
                    "label": "Disposable BYOK sharing acceptance",
                    "export_ids": [export_id],
                    "max_concurrency": 1,
                    # Probe consumes models + MCP discovery; the model call is request 3.
                    "max_requests": 3,
                    "expires_in_seconds": 3600,
                },
            ))
            grant_id = issued["grant"]["id"]
            openai_base_url = args.upstream_share.rstrip("/") + urlsplit(issued["openai_base_url"]).path
            mcp_url = args.upstream_share.rstrip("/") + urlsplit(issued["mcp_url"]).path

            gateway = checked(client.post(
                args.downstream + "/v1/platform/upstreams", headers=lower_headers,
                json={"label": "BYOK acceptance upstream", "openai_base_url": openai_base_url, "mcp_url": mcp_url, "token": issued["token"]},
            ))
            gateway_id = gateway["id"]
            projection = checked(client.post(
                args.downstream + f"/v1/platform/upstreams/{gateway_id}/probe", headers=lower_headers,
            ))
            if projection["health_status"] != "online":
                raise RuntimeError(f"Upstream probe failed: {projection.get('last_error')}")

            projected_id = f"gateway/{gateway_id}/{args.model}"
            projected = checked(client.get(args.downstream + "/v1/models", headers=lower_headers))["data"]
            if not any(item["id"] == projected_id and item.get("source") == "upstream_gateway" and item.get("shareable") is False for item in projected):
                raise RuntimeError("Downstream model projection is missing or incorrectly marked shareable")

            completion = checked(client.post(
                args.downstream + "/v1/chat/completions", headers=lower_headers,
                json={"model": projected_id, "messages": [{"role": "user", "content": "Reply only with OK"}], "max_tokens": 8, "stream": False},
            ))
            if not completion.get("choices"):
                raise RuntimeError("Shared BYOK model returned no choices")

            exhausted = client.post(
                args.downstream + "/v1/chat/completions", headers=lower_headers,
                json={"model": projected_id, "messages": [{"role": "user", "content": "Reply only with OK"}], "max_tokens": 1, "stream": False},
            )
            if exhausted.status_code != 502 or "upstream_gateway_error" not in exhausted.text:
                raise RuntimeError(f"Request budget was not enforced: HTTP {exhausted.status_code} {exhausted.text[:300]}")

            grants = checked(client.get(args.upstream + "/v1/platform/sharing/grants", headers=upper_headers))["items"]
            grant = next(item for item in grants if item["id"] == grant_id)
            if grant["request_count"] != 3 or grant["max_requests"] != 3:
                raise RuntimeError(f"Unexpected request budget state: {grant}")

            print(json.dumps({
                "status": "passed",
                "source": model["source"],
                "upstream_model": args.model,
                "projected_model": projected_id,
                "request_count": grant["request_count"],
                "max_requests": grant["max_requests"],
                "provider_key_exposed": False,
                "upstream_reshareable": False,
            }, ensure_ascii=False))
            return 0
        finally:
            if gateway_id:
                client.delete(args.downstream + f"/v1/platform/upstreams/{gateway_id}", headers=lower_headers)
            if grant_id:
                client.post(args.upstream + f"/v1/platform/sharing/grants/{grant_id}/revoke", headers=upper_headers)
            if created_export and export_id:
                client.patch(
                    args.upstream + f"/v1/platform/sharing/exports/{export_id}",
                    headers=upper_headers,
                    json={"status": "revoked"},
                )
            if original_network:
                current = checked(client.get(args.upstream + "/v1/platform/sharing/network", headers=upper_headers))
                client.patch(
                    args.upstream + "/v1/platform/sharing/network", headers=upper_headers,
                    json={
                        "mode": original_network["mode"],
                        "bind_host": original_network["bind_host"],
                        "port": original_network["port"],
                        "expected_revision": current["revision"],
                    },
                )


if __name__ == "__main__":
    raise SystemExit(main())
