"""Transport boundary for Parent Local capability calls."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .models import UpstreamGateway


@dataclass(frozen=True, slots=True)
class ParentCallContext:
    actor_user_id: str
    installation_id: str
    membership_epoch: int


@dataclass(frozen=True, slots=True)
class ParentProbe:
    models: tuple[dict[str, Any], ...]
    tools: tuple[dict[str, Any], ...]
    node_id: str | None
    ancestor_node_ids: tuple[str, ...]


class ParentModelResponse:
    """Own the HTTP client for buffered and streaming model responses."""

    def __init__(self, client: httpx.AsyncClient, response: httpx.Response) -> None:
        self.client = client
        self.response = response

    async def close(self) -> None:
        await self.response.aclose()
        await self.client.aclose()


class ParentTransport(Protocol):
    async def probe(self, gateway: UpstreamGateway, token: str) -> ParentProbe: ...

    async def invoke_tool(
        self, gateway: UpstreamGateway, token: str, name: str,
        arguments: dict[str, Any], *, context: ParentCallContext | None = None,
    ) -> dict[str, Any]: ...

    async def open_model(
        self, gateway: UpstreamGateway, token: str, payload: dict[str, Any],
        *, stream: bool, context: ParentCallContext | None = None,
    ) -> ParentModelResponse: ...


class DirectParentTransport:
    """Call a Parent Local's scoped LAN Share Grant directly."""

    def __init__(self, *, probe_timeout: float = 10.0, tool_timeout: float = 30.0) -> None:
        self.probe_timeout = probe_timeout
        self.tool_timeout = tool_timeout

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def probe(self, gateway: UpstreamGateway, token: str) -> ParentProbe:
        headers = self._headers(token)
        async with httpx.AsyncClient(timeout=self.probe_timeout, trust_env=False) as client:
            model_response = await client.get(gateway.openai_base_url + "/models", headers=headers)
            identity_response = await client.post(
                gateway.mcp_url, headers=headers,
                json={
                    "jsonrpc": "2.0", "id": "identity", "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26", "capabilities": {},
                        "clientInfo": {"name": "AI2Apps Parent Local", "version": "1"},
                    },
                },
            )
            tool_response = await client.post(
                gateway.mcp_url, headers=headers,
                json={"jsonrpc": "2.0", "id": "probe", "method": "tools/list"},
            )
        identity_response.raise_for_status()
        tool_response.raise_for_status()
        if getattr(model_response, "status_code", 200) == 404:
            models: list[dict[str, Any]] = []
        else:
            model_response.raise_for_status()
            value = model_response.json().get("data", [])
            models = value if isinstance(value, list) else []
        tool_value = tool_response.json().get("result", {}).get("tools", [])
        tools = tool_value if isinstance(tool_value, list) else []
        server_info = identity_response.json().get("result", {}).get("serverInfo", {})
        node_id = server_info.get("nodeId") if isinstance(server_info, dict) else None
        ancestor_value = server_info.get("ancestorNodeIds", []) if isinstance(server_info, dict) else []
        ancestors = tuple(ancestor_value) if isinstance(ancestor_value, list) else ()
        return ParentProbe(tuple(models), tuple(tools), node_id, ancestors)

    async def invoke_tool(
        self, gateway: UpstreamGateway, token: str, name: str,
        arguments: dict[str, Any], *, context: ParentCallContext | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.tool_timeout, trust_env=False) as client:
            response = await client.post(
                gateway.mcp_url, headers=self._headers(token),
                json={
                    "jsonrpc": "2.0", "id": secrets.token_hex(8), "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Parent MCP returned an invalid response")
        return payload

    async def open_model(
        self, gateway: UpstreamGateway, token: str, payload: dict[str, Any],
        *, stream: bool, context: ParentCallContext | None = None,
    ) -> ParentModelResponse:
        client = httpx.AsyncClient(timeout=None, trust_env=False)
        try:
            request = client.build_request(
                "POST", gateway.openai_base_url + "/chat/completions",
                headers=self._headers(token), json=payload,
            )
            response = await client.send(request, stream=stream)
            return ParentModelResponse(client, response)
        except Exception:
            await client.aclose()
            raise


class CloudRelayParentTransport:
    """Call an upstream Local through the Cloud Federation NodeLink relay."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @staticmethod
    def _headers(
        gateway: UpstreamGateway, token: str,
        context: ParentCallContext | None = None,
    ) -> dict[str, str]:
        if not gateway.node_link_id or not gateway.downstream_installation_id:
            raise RuntimeError("Cloud Relay parent metadata is incomplete")
        headers = {
            "Authorization": f"NodeLink {token}",
            "Accept": "application/json",
        }
        if context is not None:
            if context.installation_id != gateway.downstream_installation_id:
                raise RuntimeError("Cloud Relay actor belongs to another installation")
            headers.update({
                "X-AI2Apps-Actor-User-Id": context.actor_user_id,
                "X-AI2Apps-Membership-Epoch": str(context.membership_epoch),
                "X-AI2Apps-Ancestor-Node-Ids": gateway.downstream_installation_id,
                "Idempotency-Key": "fed_" + secrets.token_hex(16),
            })
        return headers

    async def probe(self, gateway: UpstreamGateway, token: str) -> ParentProbe:
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.get(
                gateway.openai_base_url + "/exports",
                headers=self._headers(gateway, token),
            )
        response.raise_for_status()
        value = response.json()
        items = value.get("items", []) if isinstance(value, dict) else []
        models: list[dict[str, Any]] = []
        tools: list[dict[str, Any]] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            export_id, kind = item.get("exportId"), item.get("kind")
            descriptor = item.get("descriptor") if isinstance(item.get("descriptor"), dict) else {}
            if not export_id:
                continue
            if kind == "model.chat":
                models.append({"id": export_id, **descriptor})
            elif isinstance(kind, str) and kind.startswith("mcp."):
                tools.append({
                    "name": export_id,
                    "description": item.get("displayName") or descriptor.get("description") or export_id,
                    "inputSchema": descriptor.get("inputSchema", {"type": "object"}),
                })
        return ParentProbe(tuple(models), tuple(tools), gateway.remote_node_id, ())

    async def invoke_tool(
        self, gateway: UpstreamGateway, token: str, name: str,
        arguments: dict[str, Any], *, context: ParentCallContext | None = None,
    ) -> dict[str, Any]:
        if context is None:
            raise RuntimeError("Cloud Relay MCP calls require a Local member identity")
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            response = await client.post(
                gateway.mcp_url,
                headers=self._headers(gateway, token, context),
                json={"jsonrpc": "2.0", "id": secrets.token_hex(8), "method": "tools/call", "params": {"name": name, "arguments": arguments}},
            )
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise RuntimeError("Cloud Relay MCP returned an invalid response")
        return value

    async def open_model(
        self, gateway: UpstreamGateway, token: str, payload: dict[str, Any],
        *, stream: bool, context: ParentCallContext | None = None,
    ) -> ParentModelResponse:
        if context is None:
            raise RuntimeError("Cloud Relay model calls require a Local member identity")
        client = httpx.AsyncClient(timeout=None, trust_env=False)
        try:
            request = client.build_request(
                "POST", gateway.openai_base_url + "/chat/completions",
                headers=self._headers(gateway, token, context), json=payload,
            )
            response = await client.send(request, stream=stream)
            return ParentModelResponse(client, response)
        except Exception:
            await client.aclose()
            raise
