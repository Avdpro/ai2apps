"""OpenAI-compatible gateway for user-enabled cloud models."""

from __future__ import annotations

import base64
import binascii
import json
import re
import time
import uuid
from typing import Any

import httpx
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse

from .model_manager import ModelManagerStore

_OPENAI_CHAT_FIELDS = {
    "model",
    "messages",
    "temperature",
    "top_p",
    "max_tokens",
    "stream",
    "stream_options",
    "stop",
    "presence_penalty",
    "frequency_penalty",
    "tools",
    "tool_choice",
    "response_format",
    "seed",
}

AI2APPS_CLOUD_PROVIDER_ID = "ai2apps"
AI2APPS_CLOUD_MODEL_PREFIX = f"cloud/{AI2APPS_CLOUD_PROVIDER_ID}/"
_IMAGE_DATA_URL = re.compile(
    r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$"
)
_MODERN_TOKEN_PARAMETER_MODELS: set[tuple[str, str]] = set()


def _chat_url(provider: dict[str, Any]) -> str:
    root = provider["base_url"].rstrip("/")
    if provider["protocol"] == "anthropic" and not root.endswith("/v1"):
        root = f"{root}/v1"
    return f"{root}/chat/completions"


def _redacted_error(response: httpx.Response, secret: str) -> str:
    """Return a bounded upstream error without ever reflecting credentials."""

    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
            else:
                message = payload.get("detail") or error
            if isinstance(message, str) and message:
                return message.replace(secret, "[redacted]")[:1000]
    except (ValueError, TypeError):
        pass
    return f"Cloud provider returned HTTP {response.status_code}"


def _needs_max_completion_tokens(status: int, detail: str, body: dict[str, Any]) -> bool:
    """Recognize OpenAI's validation error for modern completion limits."""

    message = detail.lower()
    return (
        status == 400
        and "max_tokens" in body
        and "max_tokens" in message
        and "max_completion_tokens" in message
    )


def _modern_openai_chat_body(body: dict[str, Any]) -> dict[str, Any]:
    modern = dict(body)
    token_limit = modern.pop("max_tokens", None)
    if token_limit is not None:
        modern["max_completion_tokens"] = token_limit
    # GPT-5-class Chat Completions models also reject non-default sampling
    # temperature. Let the provider apply its model default.
    modern.pop("temperature", None)
    return modern


def _decode_image_data_url(value: Any, label: str) -> tuple[bytes, str, str]:
    match = _IMAGE_DATA_URL.fullmatch(str(value or ""))
    if match is None:
        raise HTTPException(status_code=400, detail=f"{label} must be a PNG, JPEG, or WebP Data URL")
    try:
        data = base64.b64decode("".join(match.group(2).split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} contains invalid base64") from exc
    extension = "jpg" if match.group(1) == "image/jpeg" else match.group(1).split("/", 1)[1]
    return data, match.group(1), extension


def _managed_model_id(model: str) -> str | None:
    if not model.startswith("cloud/"):
        return None
    value = model[len("cloud/") :]
    if value.startswith(f"{AI2APPS_CLOUD_PROVIDER_ID}/"):
        value = value[len(AI2APPS_CLOUD_PROVIDER_ID) + 1 :]
    return value if "/" in value else None


def _local_image_url(provider: dict[str, Any], edit: bool) -> str:
    root = provider["base_url"].rstrip("/")
    return f"{root}/images/{'edits' if edit else 'generations'}"


async def request_cloud_image(
    payload: dict[str, Any],
    *,
    edit: bool,
    base_path: Any,
    cloud_client: Any | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Generate or edit one image through the selected local/account route."""

    model = str(payload.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="Image model is required")
    store = ModelManagerStore(base_path)
    provider = store.resolve_cloud_model(model)
    managed_model = _managed_model_id(model)
    if provider is None and managed_model is not None:
        provider_id = managed_model.split("/", 1)[0]
        local_provider = next(
            (item for item in store.list_cloud() if item["id"] == provider_id), None
        )
        if model.startswith(AI2APPS_CLOUD_MODEL_PREFIX) or local_provider is None or not local_provider["configured"]:
            if cloud_client is None:
                raise HTTPException(status_code=503, detail="AI2Apps Cloud client is not ready")
            cloud_body = {
                key: value
                for key, value in payload.items()
                if key
                in {
                    "prompt",
                    "size",
                    "quality",
                    "outputFormat",
                    "outputCompression",
                    "n",
                    "imageDataUrls",
                    "maskDataUrl",
                }
            }
            cloud_body["model"] = managed_model
            try:
                upstream = await cloud_client.request(
                    "POST",
                    f"/v1/ai/images/{'edits' if edit else 'generations'}",
                    json=cloud_body,
                    headers={
                        "Idempotency-Key": str(
                            payload.get("idempotencyKey") or f"local-image-{uuid.uuid4()}"
                        )
                    },
                )
            except httpx.TimeoutException as exc:
                raise HTTPException(status_code=504, detail="AI2Apps Cloud timed out") from exc
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="AI2Apps Cloud is unavailable") from exc
            try:
                if upstream.status_code >= 400:
                    try:
                        error_payload = upstream.json()
                    except ValueError:
                        error_payload = {}
                    error = (
                        error_payload.get("error", {})
                        if isinstance(error_payload, dict)
                        else {}
                    )
                    raise HTTPException(
                        status_code=upstream.status_code,
                        detail={
                            "code": str(
                                error.get("code")
                                or "AI2APPS_CLOUD_IMAGE_REQUEST_FAILED"
                            ),
                            "message": str(
                                error.get("message")
                                or "AI2Apps Cloud image request failed"
                            )[:1000],
                            "retryable": bool(error.get("retryable", False)),
                        },
                    )
                result = upstream.json()
                if not isinstance(result, dict) or not isinstance(result.get("image"), dict):
                    raise HTTPException(status_code=502, detail="AI2Apps Cloud returned an invalid image response")
                return result
            finally:
                await upstream.aclose()
    if provider is None:
        raise HTTPException(status_code=404, detail="Image model is not enabled")
    if provider.get("protocol") != "openai":
        raise HTTPException(status_code=400, detail="Selected provider does not support the image API")

    model_id = str(provider["model_id"])
    common = {
        "model": model_id,
        "prompt": str(payload.get("prompt") or ""),
        "size": str(payload.get("size") or "1024x1024"),
        "quality": str(payload.get("quality") or "auto"),
        "n": 1,
    }
    output_format = str(payload.get("outputFormat") or "png")
    normalized_model_id = model_id.lower()
    is_gpt_image = normalized_model_id.startswith("gpt-image-") or normalized_model_id == "chatgpt-image-latest"
    if is_gpt_image:
        common["output_format"] = output_format
        if payload.get("outputCompression") is not None:
            common["output_compression"] = payload["outputCompression"]
    else:
        # DALL-E endpoints still use the legacy response_format switch. GPT Image
        # models return b64_json without it and reject the parameter entirely.
        common["response_format"] = "b64_json"
    headers = {"Authorization": f"Bearer {provider['api_key']}"}
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=15.0, read=3600.0, write=120.0, pool=30.0),
        transport=transport,
    )
    try:
        if edit:
            values = payload.get("imageDataUrls")
            if not isinstance(values, list) or not 1 <= len(values) <= 4:
                raise HTTPException(status_code=400, detail="imageDataUrls must contain 1 to 4 images")
            files = []
            for index, value in enumerate(values):
                data, media_type, extension = _decode_image_data_url(value, f"imageDataUrls[{index}]")
                files.append(("image[]", (f"image-{index + 1}.{extension}", data, media_type)))
            if payload.get("maskDataUrl") is not None:
                data, media_type, extension = _decode_image_data_url(payload["maskDataUrl"], "maskDataUrl")
                files.append(("mask", (f"mask.{extension}", data, media_type)))
            request = client.build_request(
                "POST", _local_image_url(provider, True), headers=headers, data=common, files=files
            )
        else:
            request = client.build_request(
                "POST", _local_image_url(provider, False), headers={**headers, "Content-Type": "application/json"}, json=common
            )
        upstream = await client.send(request)
        if upstream.status_code >= 400:
            detail = _redacted_error(upstream, provider["api_key"])
            raise HTTPException(status_code=upstream.status_code, detail=detail)
        result = upstream.json()
        images = result.get("data") if isinstance(result, dict) else None
        image = images[0] if isinstance(images, list) and images else None
        if not isinstance(image, dict):
            raise HTTPException(status_code=502, detail="Image provider returned no image")
        value = image.get("b64_json")
        data_url = (
            f"data:image/{'jpeg' if output_format == 'jpeg' else output_format};base64,{value}"
            if value
            else image.get("url")
        )
        if not data_url:
            raise HTTPException(status_code=502, detail="Image provider returned an invalid image")
        return {
            "image": {
                "dataUrl": data_url,
                "size": common["size"],
                "quality": common["quality"],
                "format": output_format,
            },
            "usage": result.get("usage"),
            "provider": "local",
            "model": model,
        }
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Image provider timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Image provider is unavailable") from exc
    finally:
        await client.aclose()


async def proxy_cloud_image_request(payload: dict[str, Any], **kwargs: Any) -> Response:
    result = await request_cloud_image(payload, **kwargs)
    return Response(content=json.dumps(result), media_type="application/json")


def _content_parts(content: Any) -> list[dict[str, str]]:
    if isinstance(content, str):
        return [{"type": "input_text", "text": content}] if content else []
    result: list[dict[str, str]] = []
    for part in content or []:
        value = part.model_dump(exclude_none=True) if hasattr(part, "model_dump") else part
        if not isinstance(value, dict):
            continue
        if value.get("type") in {"text", "input_text"} and value.get("text"):
            result.append({"type": "input_text", "text": str(value["text"])})
        elif value.get("type") == "image_url":
            image = value.get("image_url")
            url = image.get("url") if isinstance(image, dict) else None
            if url:
                result.append({"type": "input_image", "imageUrl": str(url)})
    return result


def _ai2apps_request_body(request: Any) -> dict[str, Any]:
    system: list[str] = []
    messages: list[dict[str, Any]] = []
    for message in request.messages:
        role = str(message.role)
        parts = _content_parts(message.content)
        if role in {"system", "developer"}:
            system.extend(part["text"] for part in parts if part["type"] == "input_text")
            continue
        item: dict[str, Any] = {"role": role, "content": parts}
        if role == "assistant" and message.tool_calls:
            item["toolCalls"] = [
                {
                    "callId": str(call.get("id") or ""),
                    "name": str((call.get("function") or {}).get("name") or ""),
                    "arguments": str((call.get("function") or {}).get("arguments") or "{}"),
                }
                for call in message.tool_calls
            ]
        if role == "tool":
            item["toolCallId"] = str(message.tool_call_id or "")
        messages.append(item)
    body: dict[str, Any] = {
        "model": request.model[len(AI2APPS_CLOUD_MODEL_PREFIX) :],
        "input": messages,
        "maxOutputTokens": request.max_tokens or 1024,
        "stream": bool(request.stream),
    }
    if system:
        body["system"] = "\n\n".join(system)
    if request.temperature is not None:
        body["temperature"] = request.temperature
    if request.tools:
        body["tools"] = [
            {
                "name": tool.function.get("name"),
                "description": tool.function.get("description", ""),
                "parameters": tool.function.get("parameters", {"type": "object"}),
            }
            for tool in request.tools
        ]
    return body


def _openai_usage(value: Any) -> dict[str, int]:
    usage = value if isinstance(value, dict) else {}
    prompt = int(usage.get("inputTokens") or 0)
    completion = int(usage.get("outputTokens") or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def _finish_reason(value: Any) -> str:
    return {
        "tool_calls": "tool_calls",
        "length": "length",
        "content_filter": "content_filter",
    }.get(str(value), "stop")


def _chat_chunk(model: str, request_id: str, delta: dict[str, Any], finish: str | None = None, usage: Any = None) -> bytes:
    payload: dict[str, Any] = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    if usage is not None:
        payload["usage"] = _openai_usage(usage)
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


async def _proxy_ai2apps_chat_completion(request: Any, cloud_client: Any) -> Response:
    if cloud_client is None:
        raise HTTPException(status_code=503, detail="AI2Apps Cloud client is not ready")
    body = _ai2apps_request_body(request)
    try:
        upstream = await cloud_client.request(
            "POST",
            "/v1/ai/responses",
            json=body,
            headers={
                "Idempotency-Key": str(
                    getattr(request, "ai2apps_idempotency_key", None)
                    or f"local-chat-{uuid.uuid4()}"
                )
            },
            stream=bool(request.stream),
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="AI2Apps Cloud timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="AI2Apps Cloud is unavailable") from exc

    if upstream.status_code >= 400:
        await upstream.aread()
        try:
            payload = upstream.json()
            error = payload.get("error", {}) if isinstance(payload, dict) else {}
            detail = {
                "code": str(error.get("code") or "AI2APPS_CLOUD_REQUEST_FAILED"),
                "message": str(
                    error.get("message") or "AI2Apps Cloud request failed"
                )[:1000],
                "retryable": bool(error.get("retryable", False)),
            }
        except (TypeError, ValueError):
            detail = {
                "code": "AI2APPS_CLOUD_REQUEST_FAILED",
                "message": f"AI2Apps Cloud returned HTTP {upstream.status_code}",
                "retryable": False,
            }
        status = upstream.status_code
        await upstream.aclose()
        raise HTTPException(status_code=status, detail=detail)

    gateway_model = request.model
    if not request.stream:
        try:
            payload = upstream.json()
        finally:
            await upstream.aclose()
        output = payload.get("output", []) if isinstance(payload, dict) else []
        text = "".join(
            str(item.get("text") or "")
            for item in output
            if isinstance(item, dict) and item.get("type") == "output_text"
        )
        tool_calls = [
            {
                "id": str(item.get("callId") or ""),
                "type": "function",
                "function": {
                    "name": str(item.get("name") or ""),
                    "arguments": str(item.get("arguments") or "{}"),
                },
            }
            for item in output
            if isinstance(item, dict) and item.get("type") == "tool_call"
        ]
        response = {
            "id": str(payload.get("requestId") or f"chatcmpl-{uuid.uuid4().hex}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": gateway_model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text or None, **({"tool_calls": tool_calls} if tool_calls else {})},
                "finish_reason": _finish_reason(payload.get("stopReason")),
            }],
            "usage": _openai_usage(payload.get("usage")),
            "ai2apps_cloud": {
                key: payload.get(key)
                for key in (
                    "requestId",
                    "charged",
                    "released",
                    "balance",
                    "pricingVersion",
                    "stopReason",
                )
                if payload.get(key) is not None
            },
        }
        return Response(content=json.dumps(response), media_type="application/json")

    async def stream_body():
        buffer = ""
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        tool_indices: dict[str, int] = {}
        try:
            async for chunk in upstream.aiter_text():
                buffer += chunk.replace("\r\n", "\n")
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    event = "message"
                    data_lines: list[str] = []
                    for line in frame.split("\n"):
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line[5:].strip())
                    if not data_lines:
                        continue
                    try:
                        data = json.loads("\n".join(data_lines))
                    except json.JSONDecodeError:
                        continue
                    if event == "response.created" and data.get("requestId"):
                        request_id = str(data["requestId"])
                        yield _chat_chunk(
                            gateway_model,
                            request_id,
                            {
                                "role": "assistant",
                                "content": "",
                                "ai2apps_cloud": {
                                    "phase": "created",
                                    **data,
                                },
                            },
                        )
                    elif event == "output_text.delta":
                        yield _chat_chunk(gateway_model, request_id, {"content": str(data.get("delta") or "")})
                    elif event == "tool_call.delta":
                        call_id = str(data.get("callId") or "")
                        index = tool_indices.setdefault(call_id, len(tool_indices))
                        function: dict[str, Any] = {"arguments": str(data.get("argumentsDelta") or "")}
                        if data.get("name"):
                            function["name"] = str(data["name"])
                        yield _chat_chunk(gateway_model, request_id, {"tool_calls": [{"index": index, "id": call_id, "type": "function", "function": function}]})
                    elif event == "response.completed":
                        yield _chat_chunk(
                            gateway_model,
                            request_id,
                            {"ai2apps_cloud": {"phase": "completed", **data}},
                            _finish_reason(data.get("stopReason")),
                            data.get("usage"),
                        )
                    elif event == "response.failed":
                        error = data.get("error") if isinstance(data.get("error"), dict) else {}
                        yield _chat_chunk(
                            gateway_model,
                            request_id,
                            {
                                "ai2apps_cloud": {
                                    "phase": "failed",
                                    **data,
                                    "error": error,
                                }
                            },
                            "stop",
                        )
            yield b"data: [DONE]\n\n"
        finally:
            await upstream.aclose()

    return StreamingResponse(stream_body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def proxy_cloud_chat_completion(
    request: Any,
    *,
    base_path: Any,
    cloud_client: Any | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Response:
    """Proxy a selected virtual model through its configured provider."""

    store = ModelManagerStore(base_path)
    provider = store.resolve_cloud_model(request.model)
    if provider is None and request.model.startswith("cloud/"):
        managed_model = request.model[len("cloud/") :]
        if managed_model.startswith(f"{AI2APPS_CLOUD_PROVIDER_ID}/"):
            managed_model = managed_model[len(AI2APPS_CLOUD_PROVIDER_ID) + 1 :]
        provider_id = managed_model.split("/", 1)[0]
        local_provider = next(
            (item for item in store.list_cloud() if item["id"] == provider_id), None
        )
        if local_provider is None or not local_provider["configured"]:
            original_model = request.model
            request.model = f"{AI2APPS_CLOUD_MODEL_PREFIX}{managed_model}"
            try:
                return await _proxy_ai2apps_chat_completion(request, cloud_client)
            finally:
                request.model = original_model
    if provider is None:
        raise HTTPException(status_code=404, detail="Cloud model is not enabled")

    serialized = request.model_dump(mode="json", exclude_none=True, by_alias=True)
    body = {key: value for key, value in serialized.items() if key in _OPENAI_CHAT_FIELDS}
    body["model"] = provider["model_id"]
    modern_parameter_key = (provider["base_url"], provider["model_id"])
    if modern_parameter_key in _MODERN_TOKEN_PARAMETER_MODELS:
        body = _modern_openai_chat_body(body)
    headers = {
        "Authorization": f"Bearer {provider['api_key']}",
        "Accept": "text/event-stream" if request.stream else "application/json",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(connect=15.0, read=3600.0, write=120.0, pool=30.0)
    client = httpx.AsyncClient(timeout=timeout, transport=transport)
    try:
        upstream_request = client.build_request(
            "POST", _chat_url(provider), headers=headers, json=body
        )
        upstream = await client.send(upstream_request, stream=bool(request.stream))
    except httpx.TimeoutException as exc:
        await client.aclose()
        raise HTTPException(status_code=504, detail="Cloud provider timed out") from exc
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail="Cloud provider is unavailable") from exc

    if upstream.status_code >= 400:
        await upstream.aread()
        detail = _redacted_error(upstream, provider["api_key"])
        status = upstream.status_code
        if _needs_max_completion_tokens(status, detail, body):
            await upstream.aclose()
            modern_body = _modern_openai_chat_body(body)
            if len(_MODERN_TOKEN_PARAMETER_MODELS) >= 512:
                _MODERN_TOKEN_PARAMETER_MODELS.clear()
            _MODERN_TOKEN_PARAMETER_MODELS.add(modern_parameter_key)
            try:
                upstream = await client.send(
                    client.build_request(
                        "POST",
                        _chat_url(provider),
                        headers=headers,
                        json=modern_body,
                    ),
                    stream=bool(request.stream),
                )
            except httpx.TimeoutException as exc:
                await client.aclose()
                raise HTTPException(status_code=504, detail="Cloud provider timed out") from exc
            except httpx.HTTPError as exc:
                await client.aclose()
                raise HTTPException(status_code=502, detail="Cloud provider is unavailable") from exc
            if upstream.status_code >= 400:
                await upstream.aread()
                detail = _redacted_error(upstream, provider["api_key"])
                status = upstream.status_code
                await upstream.aclose()
                await client.aclose()
                raise HTTPException(status_code=status, detail=detail)
        else:
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(status_code=status, detail=detail)

    content_type = upstream.headers.get(
        "content-type", "text/event-stream" if request.stream else "application/json"
    )
    if not request.stream:
        content = await upstream.aread()
        await upstream.aclose()
        await client.aclose()
        return Response(
            content=content,
            status_code=upstream.status_code,
            headers={"content-type": content_type},
        )

    async def stream_body():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=upstream.status_code,
        headers={"content-type": content_type},
    )
