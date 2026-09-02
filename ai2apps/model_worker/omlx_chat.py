# SPDX-License-Identifier: Apache-2.0
"""Reusable oMLX chat lifecycle and OpenAI protocol adapter for Model Workers."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
from typing import Any

from .protocol import (
    ModelWorkerCheckpoint,
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerRequest,
    ModelWorkerStream,
)


def _error(message: str, *, code: str = "invalid_request_error", status: int = 400):
    raise ModelWorkerError(message, code=code, status_code=status)


def _messages(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _error("messages must be a non-empty array")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or not isinstance(item.get("role"), str):
            _error(f"messages[{index}] must contain a role")
        if not isinstance(item.get("content", ""), (str, list)):
            _error(f"messages[{index}].content must be text or content parts")
        result.append(dict(item))
    return result


def _responses_messages(value: Any, instructions: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(instructions, str) and instructions:
        result.append({"role": "system", "content": instructions})
    if isinstance(value, str):
        result.append({"role": "user", "content": value})
        return result
    if not isinstance(value, list):
        _error("input must be text or an array")
    for item in value:
        if not isinstance(item, dict):
            continue
        content = item.get("content", "")
        if isinstance(content, list):
            parts: list[dict[str, Any]] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type")
                if part_type in {"input_text", "output_text", "text"}:
                    parts.append({"type": "text", "text": str(part.get("text", ""))})
                elif part_type in {"input_image", "image_url"}:
                    image = part.get("image_url") or part.get("url")
                    parts.append({"type": "image_url", "image_url": image})
            content = parts
        result.append({"role": str(item.get("role", "user")), "content": content})
    return _messages(result)


def _generation_kwargs(body: Mapping[str, Any]) -> dict[str, Any]:
    try:
        result = {
            "max_tokens": max(
                1, min(int(body.get("max_tokens", body.get("max_output_tokens", 256))), 131072)
            ),
            "temperature": float(body.get("temperature", 0.7)),
            "top_p": float(body.get("top_p", 0.9)),
            "top_k": int(body.get("top_k", 0)),
            "min_p": float(body.get("min_p", 0.0)),
            "repetition_penalty": float(body.get("repetition_penalty", 1.0)),
            "presence_penalty": float(body.get("presence_penalty", 0.0)),
            "tools": body.get("tools"),
            "stop": body.get("stop"),
            "seed": body.get("seed"),
        }
        session_id = body.get("ai2apps_session_id") or body.get("flesh_session_id")
        if session_id:
            session_id = str(session_id)
            result["flesh_session_id"] = session_id
            result["flesh_kv_policy"] = str(
                body.get("flesh_kv_policy") or body.get("kv_cache_policy") or "session"
            )
            result["cache_extra_keys"] = ("ai2apps-session-v1", session_id)
            result["kv_cache_policy"] = result["flesh_kv_policy"]
        boost = (
            body.get("ai2apps_fusion_generator_engine_boost")
            or body.get("ai2apps_engine_boost")
            or body.get("dynamoe_engine_boost")
            or body.get("flesh_boost_mode")
        )
        if boost:
            result["flesh_boost_mode"] = str(boost)
        return result
    except (TypeError, ValueError) as exc:
        raise ModelWorkerError(
            "Generation parameters are invalid", code="invalid_request_error", status_code=400
        ) from exc


def _usage(output: Any) -> dict[str, Any]:
    prompt = int(getattr(output, "prompt_tokens", 0) or 0)
    completion = int(getattr(output, "completion_tokens", 0) or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "prompt_tokens_details": {
            "cached_tokens": int(getattr(output, "cached_tokens", 0) or 0)
        },
    }


def _sse(value: Mapping[str, Any]) -> bytes:
    return f"data: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()


class OmlxChatAdapter:
    """Common lifecycle and OpenAI wire format for oMLX chat Packages.

    Model Packages normally subclass this and override ``create_engine`` only
    when a model needs package-local patches or a specialized oMLX engine.
    """

    def __init__(self, context: ModelWorkerContext) -> None:
        self.context = context
        self._engine: Any | None = None
        self._checkpoint: ModelWorkerCheckpoint | None = None
        self._engine_key: tuple[Any, ...] | None = None
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        # Loading is intentionally lazy so an installed Package can be healthy
        # while its pinned checkpoint is still being downloaded/prepared.
        return None

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            await self._stop_engine()

    async def _stop_engine(self) -> None:
        engine, self._engine = self._engine, None
        self._checkpoint = None
        self._engine_key = None
        if engine is not None:
            stop = getattr(engine, "stop", None)
            if callable(stop):
                result = stop()
                if hasattr(result, "__await__"):
                    await result

    async def create_engine(
        self,
        checkpoint: ModelWorkerCheckpoint,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> Any:
        if checkpoint.path is None:
            _error(
                f"Checkpoint is not installed: {checkpoint.repo_id}@{checkpoint.revision}",
                code="model_unavailable",
                status=503,
            )
        from omlx.engine.batched import BatchedEngine

        return BatchedEngine(str(checkpoint.path), trust_remote_code=False)

    def engine_key(
        self,
        checkpoint: ModelWorkerCheckpoint,
        runtime_options: Mapping[str, Any],
    ) -> tuple[Any, ...]:
        return (
            checkpoint.model_id,
            json.dumps(runtime_options, sort_keys=True, separators=(",", ":")),
        )

    async def engine_for(
        self,
        model_id: str,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> tuple[Any, ModelWorkerCheckpoint]:
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None:
            _error(f"Unsupported model: {model_id}")
        if checkpoint.path is None:
            _error(
                f"Checkpoint is not installed: {checkpoint.repo_id}@{checkpoint.revision}",
                code="model_unavailable",
                status=503,
            )
        options = dict(runtime_options or {})
        requested_key = self.engine_key(checkpoint, options)
        async with self._lifecycle_lock:
            if self._engine is not None and self._engine_key == requested_key:
                return self._engine, checkpoint
            await self._stop_engine()
            try:
                engine = await self.create_engine(checkpoint, options)
                start = getattr(engine, "start", None)
                if callable(start):
                    result = start()
                    if hasattr(result, "__await__"):
                        await result
            except ModelWorkerError:
                raise
            except Exception as exc:
                raise ModelWorkerError(
                    f"Unable to load {checkpoint.repo_id}: {exc}",
                    code="model_load_failed",
                    status_code=503,
                ) from exc
            self._engine = engine
            self._checkpoint = checkpoint
            self._engine_key = requested_key
            return engine, checkpoint

    async def invoke(self, request: ModelWorkerRequest):
        body = dict(request.payload)
        model = body.get("model")
        if not isinstance(model, str) or not model:
            _error("model is required")
        runtime_options = body.pop("_ai2apps_model_settings", {})
        if not isinstance(runtime_options, dict):
            _error("Internal model settings are invalid")
        engine, _ = await self.engine_for(model, runtime_options)
        if request.operation == "chat_completions":
            return await self._chat(engine, model, body, request.request_id)
        if request.operation == "responses":
            return await self._responses(engine, model, body, request.request_id)
        _error(f"Unsupported operation: {request.operation}")

    async def _chat(
        self,
        engine: Any,
        model: str,
        body: dict[str, Any],
        request_id: str,
    ):
        messages = _messages(body.get("messages"))
        response_id = request_id if request_id.startswith("chatcmpl-") else f"chatcmpl-{request_id}"
        if body.get("stream"):
            return ModelWorkerStream(
                self._chat_stream(engine, model, messages, body, response_id),
                headers={"Cache-Control": "no-cache"},
            )
        output = await engine.chat(messages, **_generation_kwargs(body))
        message: dict[str, Any] = {
            "role": "assistant",
            "content": str(getattr(output, "text", "")),
        }
        tool_calls = getattr(output, "tool_calls", None)
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": getattr(output, "finish_reason", None) or "stop",
                }
            ],
            "usage": _usage(output),
        }

    async def _chat_stream(
        self,
        engine: Any,
        model: str,
        messages: list[dict[str, Any]],
        body: Mapping[str, Any],
        response_id: str,
    ) -> AsyncIterator[bytes]:
        created = int(time.time())
        yield _sse(
            {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
        )
        stream = engine.stream_chat(messages, **_generation_kwargs(body))
        final: Any = None
        try:
            async for output in stream:
                final = output
                text = getattr(output, "new_text", "")
                if text:
                    yield _sse(
                        {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {"index": 0, "delta": {"content": text}, "finish_reason": None}
                            ],
                        }
                    )
        finally:
            close = getattr(stream, "aclose", None)
            if callable(close):
                with suppress(Exception):
                    await close()
        yield _sse(
            {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": getattr(final, "finish_reason", None) or "stop",
                    }
                ],
            }
        )
        yield b"data: [DONE]\n\n"

    async def _responses(
        self,
        engine: Any,
        model: str,
        body: dict[str, Any],
        request_id: str,
    ):
        messages = _responses_messages(body.get("input"), body.get("instructions"))
        response_id = request_id if request_id.startswith("resp_") else f"resp_{request_id}"
        if body.get("stream"):
            return ModelWorkerStream(
                self._responses_stream(engine, model, messages, body, response_id),
                headers={"Cache-Control": "no-cache"},
            )
        output = await engine.chat(messages, **_generation_kwargs(body))
        text = str(getattr(output, "text", ""))
        usage = _usage(output)
        return {
            "id": response_id,
            "object": "response",
            "created_at": int(time.time()),
            "status": "completed",
            "model": model,
            "output": [
                {
                    "id": "msg_" + uuid.uuid4().hex,
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text, "annotations": []}],
                }
            ],
            "output_text": text,
            "usage": {
                "input_tokens": usage["prompt_tokens"],
                "output_tokens": usage["completion_tokens"],
                "total_tokens": usage["total_tokens"],
            },
        }

    async def _responses_stream(
        self,
        engine: Any,
        model: str,
        messages: list[dict[str, Any]],
        body: Mapping[str, Any],
        response_id: str,
    ) -> AsyncIterator[bytes]:
        created = int(time.time())
        message_id = "msg_" + uuid.uuid4().hex
        base = {
            "id": response_id,
            "object": "response",
            "created_at": created,
            "status": "in_progress",
            "model": model,
            "output": [],
        }
        yield _sse({"type": "response.created", "response": base})
        yield _sse(
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {"id": message_id, "type": "message", "status": "in_progress", "role": "assistant", "content": []},
            }
        )
        stream = engine.stream_chat(messages, **_generation_kwargs(body))
        final: Any = None
        text_parts: list[str] = []
        try:
            async for output in stream:
                final = output
                delta = str(getattr(output, "new_text", "") or "")
                if delta:
                    text_parts.append(delta)
                    yield _sse(
                        {
                            "type": "response.output_text.delta",
                            "item_id": message_id,
                            "output_index": 0,
                            "content_index": 0,
                            "delta": delta,
                        }
                    )
        finally:
            close = getattr(stream, "aclose", None)
            if callable(close):
                with suppress(Exception):
                    await close()
        text = "".join(text_parts)
        yield _sse(
            {
                "type": "response.output_text.done",
                "item_id": message_id,
                "output_index": 0,
                "content_index": 0,
                "text": text,
            }
        )
        usage = _usage(final)
        completed = dict(base)
        completed["status"] = "completed"
        completed["output_text"] = text
        completed["usage"] = {
            "input_tokens": usage["prompt_tokens"],
            "output_tokens": usage["completion_tokens"],
            "total_tokens": usage["total_tokens"],
        }
        yield _sse({"type": "response.completed", "response": completed})
        yield b"data: [DONE]\n\n"
