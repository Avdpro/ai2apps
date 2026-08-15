from __future__ import annotations

from ai2apps.fusion import FusionToolCall
from ai2apps.fusion.tooling import normalize_tool_calls, validate_tool_calls


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
]


def test_normalize_accepts_openai_and_parser_shapes():
    calls = normalize_tool_calls(
        [
            {"id": "a", "name": "lookup", "arguments": {"query": "one"}},
            {
                "id": "b",
                "function": {"name": "lookup", "arguments": '{"query":"two"}'},
            },
        ]
    )

    assert [call.id for call in calls] == ["a", "b"]
    assert [call.name for call in calls] == ["lookup", "lookup"]
    assert calls[0].arguments == '{"query":"one"}'


def test_validation_enforces_schema_choice_ids_and_limits():
    calls = (
        FusionToolCall("same", "lookup", "{}"),
        FusionToolCall("same", "other", "[]"),
    )

    errors = validate_tool_calls(
        calls,
        TOOLS,
        {"type": "function", "function": {"name": "lookup"}},
        max_calls=1,
    )

    assert any("exceeds limit" in error for error in errors)
    assert any("unique" in error for error in errors)
    assert any("required property" in error for error in errors)
    assert any("unknown tool" in error for error in errors)


def test_required_choice_rejects_empty_candidate():
    errors = validate_tool_calls((), TOOLS, "required", max_calls=8)
    assert errors == ("tool_choice requires a tool call",)
