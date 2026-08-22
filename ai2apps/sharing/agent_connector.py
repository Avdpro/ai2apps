"""Shared MCP connector contract for explicitly exported Agents."""

from __future__ import annotations

from typing import Any

from .models import CapabilityExport, ShareGrant


AGENT_OPERATIONS = (
    "create_session", "send_message", "get_status", "get_messages", "cancel", "close_session",
)


def agent_connector_tools(export: CapabilityExport) -> list[dict[str, Any]]:
    prefix = f"agent.{export.target_id}"
    session = {"session_id": {"type": "string"}}
    return [
        {"name": f"{prefix}.create_session", "title": f"Create {export.display_name} session", "description": "Create an isolated temporary Session for this shared Agent.", "inputSchema": {"type": "object", "properties": {"title": {"type": "string", "maxLength": 200}}, "additionalProperties": False}},
        {"name": f"{prefix}.send_message", "title": f"Send message to {export.display_name}", "description": "Start an asynchronous Agent Run in a shared Session.", "inputSchema": {"type": "object", "properties": {**session, "prompt": {"type": "string", "minLength": 1}, "parameters": {"type": "object"}, "model": {"type": "string"}, "instructions": {"type": "string"}, "idempotency_key": {"type": "string"}}, "required": ["session_id", "prompt"], "additionalProperties": False}},
        {"name": f"{prefix}.get_status", "title": f"Get {export.display_name} Run status", "description": "Read status and final output for a shared Agent Run.", "inputSchema": {"type": "object", "properties": {**session, "run_id": {"type": "string"}}, "required": ["session_id", "run_id"], "additionalProperties": False}},
        {"name": f"{prefix}.get_messages", "title": f"Get {export.display_name} messages", "description": "Read messages from a shared Agent Session.", "inputSchema": {"type": "object", "properties": {**session, "after": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, "required": ["session_id"], "additionalProperties": False}},
        {"name": f"{prefix}.cancel", "title": f"Cancel {export.display_name} Run", "description": "Cancel a shared Agent Run.", "inputSchema": {"type": "object", "properties": {**session, "run_id": {"type": "string"}}, "required": ["session_id", "run_id"], "additionalProperties": False}},
        {"name": f"{prefix}.close_session", "title": f"Close {export.display_name} session", "description": "Close a shared Agent Session and prevent further use.", "inputSchema": {"type": "object", "properties": session, "required": ["session_id"], "additionalProperties": False}},
    ]


def resolve_agent_connector(exports: tuple[CapabilityExport, ...] | list[CapabilityExport], name: str):
    for export in exports:
        prefix = f"agent.{export.target_id}."
        if export.status == "active" and name.startswith(prefix):
            operation = name[len(prefix):]
            if operation in AGENT_OPERATIONS:
                return export, operation
    return None, None


def invoke_agent_connector(manager, grant: ShareGrant, export: CapabilityExport, operation: str, arguments: dict[str, Any]):
    agent_key = export.target_id
    if operation == "create_session":
        return manager.create_agent_session(grant, agent_key, title=arguments.get("title", ""))
    if operation == "send_message":
        return manager.send_agent_message(
            grant, agent_key, arguments.get("session_id", ""), prompt=arguments.get("prompt", ""),
            parameters=arguments.get("parameters"), model=arguments.get("model"),
            instructions=arguments.get("instructions"), idempotency_key=arguments.get("idempotency_key"),
        )
    if operation == "get_status":
        return manager.agent_run_status(grant, agent_key, arguments.get("session_id", ""), arguments.get("run_id", ""))
    if operation == "get_messages":
        return manager.agent_messages(grant, agent_key, arguments.get("session_id", ""), after=arguments.get("after", 0), limit=arguments.get("limit", 100))
    if operation == "cancel":
        return manager.cancel_agent_run(grant, agent_key, arguments.get("session_id", ""), arguments.get("run_id", ""))
    if operation == "close_session":
        return manager.close_agent_session(grant, agent_key, arguments.get("session_id", ""))
    raise ValueError("Unknown shared Agent operation")
