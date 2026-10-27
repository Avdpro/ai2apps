"""OpenAI Chat/Responses wire adaptation owned by inference transport.

This module only translates provider protocols; it does not interpret Tool names,
App identities, business results, authorization, or Agent execution policies.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse

from .provider_errors import redacted_provider_error


def responses_body(chat: dict[str, Any]) -> dict[str, Any]:
    items = []
    for message in chat.get("messages", []):
        role = message["role"]
        if role == "tool":
            items.append({"type": "function_call_output", "call_id": message["tool_call_id"],
                          "output": message.get("content") or ""})
            continue
        content = message.get("content")
        if content:
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part["type"] == "text":
                        parts.append({"type": "output_text" if role == "assistant" else "input_text", "text": part["text"]})
                    elif part["type"] == "image_url":
                        image = part["image_url"]
                        parts.append({"type": "input_image", "image_url": image["url"],
                                      "detail": image.get("detail") or "auto"})
                    else:
                        raise HTTPException(400, f"Responses adapter does not support content type: {part['type']}")
                content = parts
            items.append({"role": role, "content": content})
        for call in message.get("tool_calls") or []:
            items.append({"type": "function_call", "call_id": call["id"],
                          "name": call["function"]["name"], "arguments": call["function"]["arguments"]})
    body = {"model": chat["model"], "input": items, "store": False, "stream": chat.get("stream", False)}
    limit = chat.get("max_completion_tokens", chat.get("max_tokens"))
    if limit is not None:
        body["max_output_tokens"] = limit
    if chat.get("reasoning_effort") is not None:
        body["reasoning"] = {"effort": chat["reasoning_effort"]}
    if chat.get("tools"):
        # Chat schemas are non-strict by default; Responses defaults differ.
        body["tools"] = [{"type": "function", "strict": False, **tool["function"]} for tool in chat["tools"]]
    choice = chat.get("tool_choice")
    if choice is not None:
        body["tool_choice"] = ({"type": "function", "name": choice["function"]["name"]}
                               if isinstance(choice, dict) else choice)
    if chat.get("response_format"):
        fmt = chat["response_format"]
        body["text"] = {"format": ({"type": "json_schema", **fmt["json_schema"]}
                                     if fmt["type"] == "json_schema" else fmt)}
    return body


def chat_response(response: dict[str, Any]) -> dict[str, Any]:
    text, calls = [], []
    for item in response.get("output", []):
        if item["type"] == "function_call":
            calls.append({"id": item["call_id"], "type": "function", "function": {
                "name": item["name"], "arguments": item["arguments"]}})
        elif item["type"] == "message":
            text.extend(part.get("text", part.get("refusal", "")) for part in item.get("content", []))
    message = {"role": "assistant", "content": "".join(text) or None}
    if calls:
        message["tool_calls"] = calls
    usage = response.get("usage") or {}
    reason = "tool_calls" if calls else "stop"
    if response.get("status") == "incomplete":
        reason = "length"
    return {"id": response["id"], "object": "chat.completion", "created": response.get("created_at", int(time.time())),
            "model": response.get("model", ""), "choices": [{"index": 0, "message": message, "finish_reason": reason}],
            "usage": {"prompt_tokens": usage.get("input_tokens", 0), "completion_tokens": usage.get("output_tokens", 0),
                      "total_tokens": usage.get("total_tokens", 0),
                      "prompt_tokens_details": usage.get("input_tokens_details", {}),
                      "completion_tokens_details": usage.get("output_tokens_details", {})}}


async def proxy_responses(chat: dict[str, Any], *, provider: dict[str, Any], transport=None) -> Response:
    body = responses_body(chat)
    client = httpx.AsyncClient(timeout=httpx.Timeout(3600, connect=15), transport=transport)
    try:
        upstream = await client.send(client.build_request("POST", provider["base_url"].rstrip("/") + "/responses",
            headers={"Authorization": f"Bearer {provider['api_key']}"}, json=body), stream=bool(body["stream"]))
        if upstream.status_code >= 400:
            await upstream.aread()
            raise HTTPException(upstream.status_code, redacted_provider_error(upstream, provider["api_key"]))
        if not body["stream"]:
            result = upstream.json()
            if result.get("error") or result.get("status") in {"failed", "cancelled"}:
                raise HTTPException(502, "Responses request failed: " + redacted_provider_error(upstream, provider["api_key"]))
            return Response(json.dumps(chat_response(result)), media_type="application/json")
    except httpx.TimeoutException as exc:
        await client.aclose()
        raise HTTPException(504, "Cloud provider timed out") from exc
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(502, "Cloud provider is unavailable") from exc
    except BaseException:
        await client.aclose()
        raise
    finally:
        if not body["stream"]:
            await client.aclose()

    async def stream():
        identity = {"id": "", "object": "chat.completion.chunk", "created": int(time.time()), "model": chat["model"]}
        calls: dict[str, int] = {}
        def chunk(delta, finish=None, usage=None):
            value = {**identity, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
            if usage is not None:
                value["usage"] = usage
            return "data: " + json.dumps(value) + "\n\n"
        try:
            async for line in upstream.aiter_lines():
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                kind = event.get("type")
                if kind == "response.created":
                    identity["id"] = event["response"]["id"]
                    yield chunk({"role": "assistant"})
                elif kind in {"response.output_text.delta", "response.refusal.delta"}:
                    yield chunk({"content": event["delta"]})
                elif kind == "response.output_item.added" and event["item"]["type"] == "function_call":
                    item = event["item"]
                    calls[item["id"]] = len(calls)
                    yield chunk({"tool_calls": [{"index": calls[item["id"]], "id": item["call_id"], "type": "function",
                                                  "function": {"name": item["name"], "arguments": item.get("arguments", "")}}]})
                elif kind == "response.function_call_arguments.delta":
                    yield chunk({"tool_calls": [{"index": calls[event["item_id"]], "function": {"arguments": event["delta"]}}]})
                elif kind in {"response.completed", "response.incomplete"}:
                    result = chat_response(event["response"])
                    yield chunk({}, result["choices"][0]["finish_reason"], result["usage"])
                    yield "data: [DONE]\n\n"
                    return
                elif kind in {"error", "response.failed"}:
                    yield "data: " + json.dumps({"error": {"message": redacted_provider_error(httpx.Response(502, json=event.get("response", event)), provider["api_key"])}}) + "\n\n"
                    return
            yield 'data: {"error":{"message":"Responses stream ended before completion"}}\n\n'
        finally:
            await upstream.aclose()
            await client.aclose()
    return StreamingResponse(stream(), media_type="text/event-stream")
