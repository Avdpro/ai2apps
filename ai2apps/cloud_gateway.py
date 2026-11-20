# SPDX-License-Identifier: BUSL-1.1
# See LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md.
"""OpenAI-compatible gateway for user-enabled cloud models."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import httpx
from fastapi import HTTPException, Response
from fastapi.responses import StreamingResponse

from .model_manager import ModelManagerStore
from .model_worker.reasoning_capabilities import adapt_reasoning_effort, ReasoningEffortError, validate_reasoning_effort
from .fusion.provider_errors import redacted_provider_error as _redacted_error
from .fusion.provider_errors import provider_retry_headers, rate_limit_detail

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
    "reasoning_effort",
}

AI2APPS_CLOUD_PROVIDER_ID = "ai2apps"
AI2APPS_CLOUD_MODEL_PREFIX = f"cloud/{AI2APPS_CLOUD_PROVIDER_ID}/"


_MODERN_TOKEN_PARAMETER_MODELS: set[tuple[str, str]] = set()
_RESPONSES_TOOL_MODELS: set[tuple[str, str]] = set()


def _chat_url(provider: dict[str, Any]) -> str:
    root = provider["base_url"].rstrip("/")
    if provider["protocol"] == "anthropic" and not root.endswith("/v1"):
        root = f"{root}/v1"
    return f"{root}/chat/completions"


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


def _managed_model_id(model: str) -> str | None:
    if not model.startswith("cloud/"):
        return None
    value = model[len("cloud/") :]
    if value.startswith(f"{AI2APPS_CLOUD_PROVIDER_ID}/"):
        value = value[len(AI2APPS_CLOUD_PROVIDER_ID) + 1 :]
    return value if "/" in value else None


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
    # The managed Cloud contract does not yet declare a reasoning control field.
    # Never silently discard caller intent or pretend that its default is low.
    try:
        effort = validate_reasoning_effort(getattr(request, "reasoning_effort", None))
    except ReasoningEffortError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if effort is not None:
        raise HTTPException(status_code=400, detail="Managed Cloud API does not yet declare reasoning_effort support")
    from .cloud_structured_output import requested_format
    response_format = requested_format(request)
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
    if response_format is not None:
        body["responseFormat"] = response_format
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


def _openai_usage(value: Any) -> dict[str, Any]:
    usage = value if isinstance(value, dict) else {}
    prompt = int(usage.get("inputTokens") or 0)
    completion = int(usage.get("outputTokens") or 0)
    result = {"prompt_tokens":prompt,"completion_tokens":completion,"total_tokens":prompt+completion}
    cached=usage.get("cachedInputTokens")
    if type(cached) is int and 0<=cached<=prompt:
        result['prompt_tokens_details']={'cached_tokens':cached}
    for key in ('cacheUsageReported','cacheUsageSource','providerCurrencyCost'):
        if key in usage:result[key]=usage[key]
    observation=usage.get('cacheObservation')
    if isinstance(observation,dict) and observation.get('schemaVersion') == 'ai2apps.cache-observation.v1':
        result['cacheObservation']={k:observation[k] for k in (
            'schemaVersion','inputTokens','hitTokens','missTokens','integrity','source','hitSource','missSource') if k in observation}
        counts=[observation.get(k) for k in ('inputTokens','hitTokens','missTokens')]
        valid=(observation.get('integrity')=='valid'
               and all(type(v) is int and v>=0 for v in counts)
               and counts[0]==prompt and counts[1]+counts[2]==prompt)
        if valid and usage.get('cacheUsageReported') is True:
            result['prompt_tokens_details']={'cached_tokens':counts[1]}
        else:
            result.pop('prompt_tokens_details',None)
            result['cacheUsageReported']=False
    if result.get('cacheUsageReported') is False:
        result.pop('prompt_tokens_details',None)
    return result



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


async def _check_ai2apps_tool_limit(cloud_client, body, authorization_headers=None):
    """Honor the authenticated catalog's effective limit without truncating tools."""
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        return
    try:
        response = await cloud_client.request(
            "GET", "/v1/ai/models", headers=authorization_headers or {},
        )
        try:
            if response.status_code != 200:
                return  # The submission endpoint remains authoritative.
            payload = response.json()
        finally:
            await response.aclose()
    except (httpx.HTTPError, ValueError):
        return
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return
    for model in items:
        if not isinstance(model, dict) or model.get("id") != body.get("model"):
            continue
        capabilities = model.get("capabilities")
        if not isinstance(capabilities, dict):
            return
        options = capabilities.get("toolOptions")
        if not isinstance(options, dict):
            return
        limit = options.get("maxTools")
        if type(limit) is not int or limit < 0:
            return
        if len(tools) > limit:
            raise HTTPException(status_code=400, detail={
                "code": "INVALID_AI_TOOLS",
                "message": f"Selected model accepts at most {limit} tools; received {len(tools)}. Select fewer authorized tools or another model.",
                "retryable": False, "param": "tools",
                "details": {"reason": "tool_count_exceeded", "limit": limit,
                            "actual": len(tools), "model": body.get("model"),
                            "protocol": options.get("protocol")},
            })
        return


async def _proxy_ai2apps_chat_completion(
    request: Any,
    cloud_client: Any,
    *,
    authorization_headers: dict[str, str] | None = None,
) -> Response:
    if cloud_client is None:
        raise HTTPException(status_code=503, detail="AI2Apps Cloud client is not ready")
    body = _ai2apps_request_body(request)
    from .cloud_structured_output import check_capability, validate_complete, MAX_BYTES
    structured_limit = await check_capability(cloud_client, body, authorization_headers)
    await _check_ai2apps_tool_limit(cloud_client, body, authorization_headers)
    try:
        upstream = await cloud_client.request(
            "POST",
            "/v1/ai/responses",
            json=body,
            headers={
                **(authorization_headers or {}),
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
                "retryable": bool(error.get("retryable", upstream.status_code == 429)),
            }
            for field in ("param", "details"):
                if field in error:
                    detail[field] = error[field]
        except (TypeError, ValueError):
            detail = {
                "code": "AI2APPS_CLOUD_REQUEST_FAILED",
                "message": f"AI2Apps Cloud returned HTTP {upstream.status_code}",
                "retryable": upstream.status_code == 429,
            }
        status = upstream.status_code
        await upstream.aclose()
        raise HTTPException(status_code=status, detail=detail, headers=provider_retry_headers(upstream))

    gateway_model = request.model
    if not request.stream:
        try:
            try:
                payload = upstream.json()
            except ValueError:
                if structured_limit is not None:
                    from .cloud_structured_output import reject
                    reject('AI_STRUCTURED_OUTPUT_INCOMPLETE','Cloud did not return a confirmed structured result.',status=502)
                raise
        finally:
            await upstream.aclose()
        output = payload.get("output", []) if isinstance(payload, dict) else []
        if structured_limit is not None and not isinstance(output,list):
            from .cloud_structured_output import reject
            reject('AI_STRUCTURED_OUTPUT_INCOMPLETE','Cloud structured output was invalid.',status=502)
        text = "".join(
            str(item.get("text") or "")
            for item in output
            if isinstance(item, dict) and item.get("type") == "output_text"
        )
        if structured_limit is not None:
            validate_complete(payload, text, structured_limit)
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
                    "points",
                    "status",
                    "stopReason",
                    "responseFormat",
                    "structuredOutput",
                )
                if payload.get(key) is not None
            },
        }
        return Response(content=json.dumps(response), media_type="application/json")

    async def stream_body():
        buffer = ""
        request_id = f"chatcmpl-{uuid.uuid4().hex}"
        tool_indices: dict[str, int] = {}
        structured_text = ""
        terminal = False
        try:
            async for chunk in upstream.aiter_text():
                buffer += chunk.replace("\r\n", "\n")
                if structured_limit is not None and len(buffer.encode('utf-8'))>MAX_BYTES*2:
                    from .cloud_structured_output import reject
                    reject('AI_STRUCTURED_OUTPUT_TOO_LARGE','Cloud event exceeded the structured-output size limit.',status=502)
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
                    if structured_limit is not None and not isinstance(data,dict):
                        from .cloud_structured_output import reject
                        reject('AI_STRUCTURED_OUTPUT_INCOMPLETE','Invalid Cloud event.',status=502)
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
                        if structured_limit is not None:
                            structured_text += str(data.get("delta") or "")
                            if len(structured_text.encode('utf-8')) > structured_limit:
                                from .cloud_structured_output import reject
                                reject('AI_STRUCTURED_OUTPUT_TOO_LARGE','Structured output exceeded the declared size limit.',status=502)
                        else:
                            yield _chat_chunk(gateway_model, request_id, {"content": str(data.get("delta") or "")})
                    elif event == "tool_call.delta":
                        if structured_limit is not None:
                            from .cloud_structured_output import reject
                            reject('AI_STRUCTURED_OUTPUT_INCOMPLETE','Unexpected tool output in a structured response.',status=502)
                        call_id = str(data.get("callId") or "")
                        index = tool_indices.setdefault(call_id, len(tool_indices))
                        function: dict[str, Any] = {"arguments": str(data.get("argumentsDelta") or "")}
                        if data.get("name"):
                            function["name"] = str(data["name"])
                        yield _chat_chunk(gateway_model, request_id, {"tool_calls": [{"index": index, "id": call_id, "type": "function", "function": function}]})
                    elif event == "response.completed":
                        if structured_limit is not None and terminal:
                            from .cloud_structured_output import reject
                            reject('AI_STRUCTURED_OUTPUT_INCOMPLETE','Duplicate Cloud terminal event.',status=502)
                        if structured_limit is not None:
                            validate_complete(data, structured_text, structured_limit)
                            yield _chat_chunk(gateway_model, request_id, {"content": structured_text})
                        terminal = True
                        yield _chat_chunk(
                            gateway_model,
                            request_id,
                            {"ai2apps_cloud": {"phase": "completed", **data}},
                            _finish_reason(data.get("stopReason")),
                            data.get("usage"),
                        )
                    elif event == "response.failed":
                        terminal = True
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
            if structured_limit is not None and not terminal:
                from .cloud_structured_output import reject
                reject('AI_STRUCTURED_OUTPUT_INCOMPLETE','Cloud stream ended without a successful terminal event.',status=502)
            yield b"data: [DONE]\n\n"
        except httpx.HTTPError:
            if structured_limit is None:
                raise
            yield _chat_chunk(gateway_model, request_id, {"ai2apps_cloud":{"phase":"failed","error":{"code":"AI_STRUCTURED_OUTPUT_INCOMPLETE","message":"Cloud stream disconnected before a confirmed result.","retryable":False}}}, "stop")
            yield b"data: [DONE]\n\n"
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail,dict) else {"code":"AI_STRUCTURED_OUTPUT_INCOMPLETE","message":"Structured output failed.","retryable":False}
            yield _chat_chunk(gateway_model, request_id, {"ai2apps_cloud":{"phase":"failed","error":detail}}, "stop")
            yield b"data: [DONE]\n\n"
        finally:
            await upstream.aclose()

    return StreamingResponse(stream_body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def proxy_cloud_chat_completion(
    request: Any,
    *,
    base_path: Any,
    cloud_client: Any | None = None,
    model_manager: ModelManagerStore | None = None,
    authorization_headers: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Response:
    """Proxy a selected virtual model through its configured provider."""

    store = model_manager or ModelManagerStore(base_path)
    provider = store.resolve_cloud_model(request.model)
    if provider is None and request.model.startswith("cloud/"):
        managed_model = request.model[len("cloud/") :]
        if managed_model.startswith(f"{AI2APPS_CLOUD_PROVIDER_ID}/"):
            managed_model = managed_model[len(AI2APPS_CLOUD_PROVIDER_ID) + 1 :]
        provider_id = managed_model.split("/", 1)[0]
        local_provider = next(
            (item for item in store.list_cloud() if item["id"] == provider_id), None
        )
        if request.model.startswith(AI2APPS_CLOUD_MODEL_PREFIX) or local_provider is None or not local_provider["configured"]:
            original_model = request.model
            request.model = f"{AI2APPS_CLOUD_MODEL_PREFIX}{managed_model}"
            try:
                return await _proxy_ai2apps_chat_completion(
                    request,
                    cloud_client,
                    authorization_headers=authorization_headers,
                )
            finally:
                request.model = original_model
    if provider is None:
        raise HTTPException(status_code=404, detail="Cloud model is not enabled")

    serialized = request.model_dump(mode="json", exclude_none=True, by_alias=True)
    body = {key: value for key, value in serialized.items() if key in _OPENAI_CHAT_FIELDS}
    body["model"] = provider["model_id"]
    reasoning_control = (provider.get('capabilities') or {}).get('reasoningControl')
    try:
        body = adapt_reasoning_effort(body, reasoning_control)
    except ReasoningEffortError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if reasoning_control and reasoning_control.get('format') == 'responses':
        # The existing Responses adapter owns endpoint and message conversion.
        # Give it the already-mapped native effort through its Chat input contract.
        if body.get('reasoning') is not None:
            body['reasoning_effort'] = body.pop('reasoning')['effort']
        from .fusion.openai_responses import proxy_responses
        return await proxy_responses(body, provider=provider, transport=transport)
    modern_parameter_key = (provider["base_url"], provider["model_id"])
    if modern_parameter_key in _MODERN_TOKEN_PARAMETER_MODELS:
        body = _modern_openai_chat_body(body)
    if body.get("tools") and modern_parameter_key in _RESPONSES_TOOL_MODELS:
        from .fusion.openai_responses import proxy_responses
        return await proxy_responses(body, provider=provider, transport=transport)
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

    # Validation failures have not executed a Tool. Adapt only an explicit
    # endpoint incompatibility, never retry an ambiguous upstream execution.
    if upstream.status_code >= 400:
        await upstream.aread()
        detail = _redacted_error(upstream, provider["api_key"])
        if _needs_max_completion_tokens(upstream.status_code, detail, body):
            await upstream.aclose()
            body = _modern_openai_chat_body(body)
            if len(_MODERN_TOKEN_PARAMETER_MODELS) >= 512:
                _MODERN_TOKEN_PARAMETER_MODELS.clear()
            _MODERN_TOKEN_PARAMETER_MODELS.add(modern_parameter_key)
            try:
                upstream = await client.send(client.build_request(
                    "POST", _chat_url(provider), headers=headers, json=body), stream=bool(request.stream))
            except httpx.HTTPError as exc:
                await client.aclose()
                raise HTTPException(504 if isinstance(exc, httpx.TimeoutException) else 502,
                                    "Cloud provider is unavailable") from exc
        if upstream.status_code >= 400:
            await upstream.aread()
            detail = _redacted_error(upstream, provider["api_key"])
            status = upstream.status_code
            await upstream.aclose()
            await client.aclose()
            # Require the official endpoint and its explicit validation response;
            # do not reinterpret third-party providers or authentication errors.
            if (status == 400 and body.get("tools")
                    and provider["base_url"].rstrip("/") == "https://api.openai.com/v1"
                    and "responses" in detail.lower()
                    and ("function" in detail.lower() or "tools" in detail.lower())):
                from .fusion.openai_responses import proxy_responses
                response = await proxy_responses(body, provider=provider, transport=transport)
                if len(_RESPONSES_TOOL_MODELS) >= 512:
                    _RESPONSES_TOOL_MODELS.clear()
                _RESPONSES_TOOL_MODELS.add(modern_parameter_key)
                return response
            raise HTTPException(status_code=status, detail=rate_limit_detail(upstream, detail),
                                headers=provider_retry_headers(upstream))

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
