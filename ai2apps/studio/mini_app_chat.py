"""Declaration helpers for the optional Studio Mini-App Chat contract."""

from __future__ import annotations

from typing import Any

SCHEMA = "ai2apps.mini-app-chat/v1"
MAX_SYSTEM_PROMPT = 16_000
MAX_TOOLS = 64
MAX_HELP_BYTES = 32 * 1024
HELP_TOOL_NAME = "read_mini_app_help"


def builtin_chat_capability(mini_app_id: str) -> dict[str, Any]:
    """Capability marker for host adapters whose live contract comes from Studio."""

    return {
        "schema": SCHEMA,
        "enabled": True,
        "provider": "host-adapter",
        "context": {"transport": "studio-bridge", "maxBytes": 64 * 1024},
        "help": {
            "resource": f"help/mini_apps/{mini_app_id}/help.md",
            "format": "markdown",
            "maxBytes": MAX_HELP_BYTES,
        },
    }


def validate_chat_declaration(value: Any) -> None:
    """Validate the signed, static portion of a Package Mini-App Chat contract."""

    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError(f"chat.schema must be {SCHEMA}")
    if value.get("enabled") is not True:
        raise ValueError("chat.enabled must be true")
    prompt = value.get("system_prompt", "")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_SYSTEM_PROMPT:
        raise ValueError("chat.system_prompt must be 1-16000 characters")
    context = value.get("context")
    if not isinstance(context, dict) or context.get("transport") != "studio-bridge":
        raise ValueError("chat.context.transport must be studio-bridge")
    help_resource = value.get("help")
    if not isinstance(help_resource, dict):
        raise ValueError("chat.help must declare a help.md resource")
    resource = help_resource.get("resource")
    max_bytes = help_resource.get("max_bytes", MAX_HELP_BYTES)
    if (
        not isinstance(resource, str)
        or not resource.endswith("help.md")
        or resource.startswith(("/", "."))
        or ".." in resource.split("/")
    ):
        raise ValueError("chat.help.resource must be a safe Package-relative help.md path")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or not 1 <= max_bytes <= MAX_HELP_BYTES:
        raise ValueError("chat.help.max_bytes must be between 1 and 32768")
    tools = value.get("tools")
    if not isinstance(tools, list) or len(tools) > MAX_TOOLS:
        raise ValueError("chat.tools must contain 0-64 Tool declarations")
    names: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("Every chat Tool must be an object")
        name = tool.get("name")
        schema = tool.get("input_schema")
        if (
            not isinstance(name, str)
            or not name
            or len(name) > 64
            or not all(char.isalnum() or char in {"_", "-"} for char in name)
            or name in names
            or name == HELP_TOOL_NAME
        ):
            raise ValueError("Chat Tool names must be unique identifiers")
        names.add(name)
        if not isinstance(tool.get("description"), str) or not tool["description"].strip():
            raise ValueError("Every chat Tool requires a description")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError("Every chat Tool input_schema must be an object schema")
        if tool.get("confirmation", "never") not in {"never", "always"}:
            raise ValueError("chat Tool confirmation must be never or always")
