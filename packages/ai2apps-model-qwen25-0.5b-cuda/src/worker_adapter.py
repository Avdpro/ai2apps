# SPDX-License-Identifier: Apache-2.0
"""CUDA Transformers adapter for the pinned Qwen2.5 smoke model."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from ai2apps.model_worker.protocol import (
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerRequest,
    ModelWorkerStream,
)


def _error(message: str, *, code: str = "invalid_request_error", status: int = 400):
    raise ModelWorkerError(message, code=code, status_code=status)


def _sse(value: Mapping[str, Any]) -> bytes:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return f"data: {encoded}\n\n".encode()


def _messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        _error("messages must be a non-empty array")
    result: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or not isinstance(item.get("role"), str):
            _error(f"messages[{index}] must contain a role")
        content = item.get("content", "")
        if isinstance(content, list):
            text = []
            for part in content:
                if not isinstance(part, Mapping) or part.get("type") not in {
                    "text",
                    "input_text",
                }:
                    _error("This text-only CUDA Package does not accept media parts")
                text.append(str(part.get("text", "")))
            content = "\n".join(text)
        if not isinstance(content, str):
            _error(f"messages[{index}].content must be text")
        result.append({"role": str(item["role"]), "content": content})
    return result


class CudaTransformersChatAdapter:
    def __init__(self, context: ModelWorkerContext) -> None:
        self.context = context
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._model_id: str | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        # Keep health checks cheap while the Host downloads or imports weights.
        return None

    async def stop(self) -> None:
        async with self._lock:
            self._model = None
            self._tokenizer = None
            self._model_id = None
            with suppress(Exception):
                import torch

                torch.cuda.empty_cache()

    async def _ensure_loaded(self, model_id: str) -> tuple[Any, Any]:
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None:
            _error(f"Unsupported model: {model_id}")
        if checkpoint.path is None:
            _error(
                f"Checkpoint is not installed: {checkpoint.repo_id}@{checkpoint.revision}",
                code="model_unavailable",
                status=503,
            )
        async with self._lock:
            if self._model is not None and self._model_id == checkpoint.model_id:
                return self._model, self._tokenizer

            def load():
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                if not torch.cuda.is_available():
                    _error("CUDA is unavailable inside the Model Worker", status=503)
                tokenizer = AutoTokenizer.from_pretrained(
                    checkpoint.path,
                    local_files_only=True,
                    trust_remote_code=False,
                )
                model = AutoModelForCausalLM.from_pretrained(
                    checkpoint.path,
                    local_files_only=True,
                    trust_remote_code=False,
                    dtype=torch.bfloat16,
                )
                model.to("cuda:0")
                model.eval()
                return model, tokenizer

            try:
                self._model, self._tokenizer = await asyncio.to_thread(load)
            except ModelWorkerError:
                raise
            except Exception as error:
                raise ModelWorkerError(
                    f"Unable to load {checkpoint.repo_id}: {error}",
                    code="model_load_failed",
                    status_code=503,
                ) from error
            self._model_id = checkpoint.model_id
            return self._model, self._tokenizer

    @staticmethod
    def _generate(
        model: Any,
        tokenizer: Any,
        messages: list[dict[str, str]],
        body: Mapping[str, Any],
    ) -> tuple[str, int, int]:
        import torch

        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        encoded = tokenizer([prompt], return_tensors="pt").to("cuda:0")
        try:
            maximum = max(
                1,
                min(
                    int(body.get("max_tokens", body.get("max_output_tokens", 256))),
                    4096,
                ),
            )
            temperature = float(body.get("temperature", 0.7))
            top_p = float(body.get("top_p", 0.9))
        except (TypeError, ValueError) as error:
            raise ModelWorkerError(
                "Generation parameters are invalid", code="invalid_request_error"
            ) from error
        options: dict[str, Any] = {
            "max_new_tokens": maximum,
            "do_sample": temperature > 0,
            "pad_token_id": tokenizer.eos_token_id,
        }
        if temperature > 0:
            options.update(temperature=temperature, top_p=top_p)
        with torch.inference_mode():
            output = model.generate(**encoded, **options)
        prompt_tokens = int(encoded.input_ids.shape[-1])
        generated = output[0, prompt_tokens:]
        text = tokenizer.decode(generated, skip_special_tokens=True)
        return text, prompt_tokens, int(generated.shape[-1])

    async def invoke(self, request: ModelWorkerRequest):
        body = dict(request.payload)
        model_id = body.get("model")
        if not isinstance(model_id, str) or not model_id:
            _error("model is required")
        body.pop("_ai2apps_model_settings", None)
        model, tokenizer = await self._ensure_loaded(model_id)
        if request.operation == "chat_completions":
            messages = _messages(body.get("messages"))
            if body.get("stream"):
                return ModelWorkerStream(
                    self._chat_stream(model, tokenizer, messages, body, model_id, request.request_id),
                    headers={"Cache-Control": "no-cache"},
                )
            text, prompt_tokens, output_tokens = await asyncio.to_thread(
                self._generate, model, tokenizer, messages, body
            )
            return self._chat_response(
                model_id, request.request_id, text, prompt_tokens, output_tokens
            )
        if request.operation == "responses":
            messages = []
            if isinstance(body.get("instructions"), str) and body["instructions"]:
                messages.append({"role": "system", "content": body["instructions"]})
            input_value = body.get("input")
            if isinstance(input_value, str):
                messages.append({"role": "user", "content": input_value})
            elif isinstance(input_value, list):
                messages.extend(_messages(input_value))
            else:
                _error("input must be text or an array")
            text, prompt_tokens, output_tokens = await asyncio.to_thread(
                self._generate, model, tokenizer, messages, body
            )
            return self._responses_response(
                model_id, request.request_id, text, prompt_tokens, output_tokens
            )
        _error(f"Unsupported operation: {request.operation}")

    @staticmethod
    def _chat_response(
        model_id: str, request_id: str, text: str, prompt_tokens: int, output_tokens: int
    ) -> dict[str, Any]:
        response_id = request_id if request_id.startswith("chatcmpl-") else f"chatcmpl-{request_id}"
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": prompt_tokens + output_tokens,
            },
        }

    async def _chat_stream(
        self,
        model: Any,
        tokenizer: Any,
        messages: list[dict[str, str]],
        body: Mapping[str, Any],
        model_id: str,
        request_id: str,
    ):
        text, prompt_tokens, output_tokens = await asyncio.to_thread(
            self._generate, model, tokenizer, messages, body
        )
        response = self._chat_response(
            model_id, request_id, text, prompt_tokens, output_tokens
        )
        response_id = response["id"]
        yield _sse(
            {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": response["created"],
                "model": model_id,
                "choices": [
                    {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
                ],
            }
        )
        yield _sse(
            {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": response["created"],
                "model": model_id,
                "choices": [
                    {"index": 0, "delta": {"content": text}, "finish_reason": None}
                ],
            }
        )
        yield _sse(
            {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": response["created"],
                "model": model_id,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
        )
        yield b"data: [DONE]\n\n"

    @staticmethod
    def _responses_response(
        model_id: str, request_id: str, text: str, prompt_tokens: int, output_tokens: int
    ) -> dict[str, Any]:
        response_id = request_id if request_id.startswith("resp_") else f"resp_{request_id}"
        return {
            "id": response_id,
            "object": "response",
            "created_at": int(time.time()),
            "status": "completed",
            "model": model_id,
            "output": [
                {
                    "id": "msg_" + uuid.uuid4().hex,
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": text, "annotations": []}
                    ],
                }
            ],
            "output_text": text,
            "usage": {
                "input_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": prompt_tokens + output_tokens,
            },
        }


def create_adapter(context: ModelWorkerContext):
    return CudaTransformersChatAdapter(context)
