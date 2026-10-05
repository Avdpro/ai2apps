"""Lossless-storage tool-result projection with an explicit source reference."""

import hashlib

from .core import Node, canonical


def prune_tool_result(node, reference, threshold=32768):
    body = node.body
    text = body.get("content")
    if (
        body.get("role") != "tool"
        or not isinstance(text, str)
        or len(text.encode()) <= threshold
    ):
        return None
    try:
        import json

        if json.loads(text).get("type") == "ai2apps.session-tool-reference/v1":
            return None
    except (ValueError, AttributeError):
        pass
    body["content"] = canonical(
        {
            "type": "ai2apps.session-tool-reference/v1",
            "notice": "Partial original tool result. Read omitted evidence before relying on it; tool completion is not task completion.",
            "source": reference,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "total_characters": len(text),
            "head": text[:2048],
            "tail": text[-1024:],
            "omitted_characters": len(text) - 3072,
        }
    )
    if len(canonical(body).encode()) >= len(node.body_json.encode()):
        return None
    return Node.message(node.id, body, pinned=node.pinned)
