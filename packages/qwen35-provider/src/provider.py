#!/usr/bin/env python3
"""OpenAI-compatible Qwen3.5 provider hosted by an AI2Apps Service Package."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

MODEL_IDS = {
    "mlx-community/Qwen3.5-2B-4bit": "ai2apps.qwen35/qwen3.5-2b-4bit",
    "mlx-community/Qwen3.5-0.8B-4bit": "ai2apps.qwen35/qwen3.5-0.8b-4bit",
}
MODEL_REPOSITORIES = frozenset(MODEL_IDS)
DEFAULT_MODEL = "mlx-community/Qwen3.5-2B-4bit"


def _model_error(message: str, *, status: int = 400, code: str = "invalid_request_error"):
    raise HTTPException(
        status_code=status,
        detail={"error": {"message": message, "type": code, "code": code}},
    )


def _normalize_messages(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _model_error("messages must be a non-empty array")
    messages: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or not isinstance(item.get("role"), str):
            _model_error(f"messages[{index}] must contain a role")
        content = item.get("content", "")
        if not isinstance(content, (str, list)):
            _model_error(f"messages[{index}].content must be text or content parts")
        messages.append(dict(item))
    return messages


def _responses_messages(value: Any, instructions: Any = None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if isinstance(instructions, str) and instructions:
        messages.append({"role": "system", "content": instructions})
    if isinstance(value, str):
        messages.append({"role": "user", "content": value})
        return messages
    if not isinstance(value, list):
        _model_error("input must be text or an array")
    for item in value:
        if not isinstance(item, dict):
            continue
        role = item.get("role", "user")
        content = item.get("content", "")
        if isinstance(content, list):
            normalized = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type")
                if part_type in {"input_text", "output_text", "text"}:
                    normalized.append({"type": "text", "text": str(part.get("text", ""))})
                elif part_type in {"input_image", "image_url"}:
                    normalized.append(
                        {
                            "type": "image_url",
                            "image_url": part.get("image_url") or {"url": part.get("image_url") or part.get("url")},
                        }
                    )
            content = normalized
        messages.append({"role": role, "content": content})
    return _normalize_messages(messages)


class QwenProvider:
    def __init__(self) -> None:
        self._engine: Any | None = None
        self._repository: str | None = None
        self._lock = asyncio.Lock()
        raw = os.environ.get("AI2APPS_MODEL_CHECKPOINTS_JSON", "[]")
        try:
            checkpoints = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("Host checkpoint declaration is invalid") from error
        if not isinstance(checkpoints, list):
            raise RuntimeError("Host checkpoint declaration must be an array")
        self._checkpoints: dict[str, Path] = {}
        repositories_by_model_id = {
            model_id: repository for repository, model_id in MODEL_IDS.items()
        }
        for item in checkpoints:
            if not isinstance(item, dict):
                continue
            repository = repositories_by_model_id.get(item.get("model_id"))
            path = item.get("path")
            if repository is not None and isinstance(path, str) and path:
                self._checkpoints[repository] = Path(path).resolve()

    def _resolve_checkpoint(self, repository: str) -> Path:
        if repository not in MODEL_REPOSITORIES:
            _model_error(f"Unsupported Qwen3.5 checkpoint: {repository}")
        checkpoint = self._checkpoints.get(repository)
        if checkpoint is None or not checkpoint.is_dir():
            _model_error(
                f"Host-managed checkpoint is unavailable for {repository}",
                status=503,
                code="model_unavailable",
            )
        return checkpoint

    async def engine(self, repository: str):
        async with self._lock:
            if self._engine is not None and self._repository == repository:
                return self._engine
            if self._engine is not None:
                await self._engine.stop()
                self._engine = None
                self._repository = None
            checkpoint = await asyncio.to_thread(self._resolve_checkpoint, repository)
            from omlx.engine.vlm import VLMBatchedEngine

            engine = VLMBatchedEngine(str(checkpoint), trust_remote_code=False)
            await engine.start()
            self._engine = engine
            self._repository = repository
            return engine

    async def close(self) -> None:
        async with self._lock:
            if self._engine is not None:
                await self._engine.stop()
            self._engine = None
            self._repository = None


provider = QwenProvider()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await provider.close()


app = FastAPI(title="Qwen3.5 AI2Apps Provider", version="0.1.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def openai_http_error(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(exc.detail, status_code=exc.status_code)
    return JSONResponse(
        {"error": {"message": str(exc.detail), "type": "request_error", "code": "request_error"}},
        status_code=exc.status_code,
    )


@app.get("/health")
async def health():
    return {
        "status": "ready",
        "service": os.environ.get("AI2APPS_SERVICE_ID", "ai2apps.qwen35"),
        "loaded_model": provider._repository,
        "capabilities": ["work", "conversation", "image_recognition"],
    }


@app.get("/v1/models")
async def models():
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": item, "object": "model", "created": now, "owned_by": "ai2apps.qwen35"}
            for item in sorted(MODEL_REPOSITORIES)
        ],
    }


def _generation_kwargs(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_tokens": max(1, min(int(body.get("max_tokens", body.get("max_output_tokens", 256))), 8192)),
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


def _chat_response(model: str, output: Any, request_id: str) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": output.text}
    if output.tool_calls:
        message["tool_calls"] = output.tool_calls
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": output.finish_reason or "stop"}],
        "usage": {
            "prompt_tokens": output.prompt_tokens,
            "completion_tokens": output.completion_tokens,
            "total_tokens": output.prompt_tokens + output.completion_tokens,
            "prompt_tokens_details": {"cached_tokens": output.cached_tokens},
        },
    }


async def _chat_stream(model: str, engine: Any, messages: list[dict[str, Any]], body: dict[str, Any], request_id: str) -> AsyncIterator[bytes]:
    created = int(time.time())
    first = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(first, ensure_ascii=False)}\n\n".encode()
    final = None
    async for output in engine.stream_chat(messages, **_generation_kwargs(body)):
        final = output
        if output.new_text:
            chunk = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": output.new_text}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode()
    finish = getattr(final, "finish_reason", None) or "stop"
    done = {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
    }
    yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n".encode()
    stream_options = body.get("stream_options")
    if isinstance(stream_options, dict) and stream_options.get("include_usage") is True:
        if final is None:
            _model_error("Model stream ended without token usage", status=502, code="model_stream_error")
        usage = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [],
            "usage": {
                "prompt_tokens": final.prompt_tokens,
                "completion_tokens": final.completion_tokens,
                "total_tokens": final.prompt_tokens + final.completion_tokens,
                "prompt_tokens_details": {"cached_tokens": final.cached_tokens},
            },
        }
        yield f"data: {json.dumps(usage, ensure_ascii=False)}\n\n".encode()
    yield b"data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = str(body.get("model") or DEFAULT_MODEL)
    messages = _normalize_messages(body.get("messages"))
    engine = await provider.engine(model)
    request_id = "chatcmpl-" + uuid.uuid4().hex
    if body.get("stream"):
        return StreamingResponse(
            _chat_stream(model, engine, messages, body, request_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
    output = await engine.chat(messages, **_generation_kwargs(body))
    return _chat_response(model, output, request_id)


@app.post("/v1/responses")
async def responses(request: Request):
    body = await request.json()
    if body.get("stream"):
        _model_error("Streaming Responses API is not implemented by this package yet")
    model = str(body.get("model") or DEFAULT_MODEL)
    messages = _responses_messages(body.get("input"), body.get("instructions"))
    engine = await provider.engine(model)
    output = await engine.chat(messages, **_generation_kwargs(body))
    response_id = "resp_" + uuid.uuid4().hex
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
                "content": [{"type": "output_text", "text": output.text, "annotations": []}],
            }
        ],
        "output_text": output.text,
        "usage": {
            "input_tokens": output.prompt_tokens,
            "output_tokens": output.completion_tokens,
            "total_tokens": output.prompt_tokens + output.completion_tokens,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("AI2APPS_SERVICE_PORT", "0")))
    args = parser.parse_args()
    if not args.port:
        parser.error("--port or AI2APPS_SERVICE_PORT is required")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
