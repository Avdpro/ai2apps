# SPDX-License-Identifier: Apache-2.0
"""CUDA Transformers adapter for Qwen3-VL."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
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


def _data_image(value: Any):
    from PIL import Image

    url = value.get("url") if isinstance(value, Mapping) else value
    if not isinstance(url, str) or not url.startswith("data:image/") or ";base64," not in url:
        _error("No-network CUDA VLM Workers require image data URLs")
    encoded = url.split(",", 1)[1]
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ModelWorkerError("Image data URL is invalid") from error
    if len(content) > 32 * 1024 * 1024:
        _error("Image exceeds the 32 MiB VLM input limit")
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
        return image.convert("RGB")
    except Exception as error:
        raise ModelWorkerError("Image data URL is not a supported image") from error


def _messages(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _error("messages must be a non-empty array")
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or not isinstance(item.get("role"), str):
            _error(f"messages[{index}] must contain a role")
        raw_content = item.get("content", "")
        if isinstance(raw_content, str):
            content: Any = raw_content
        elif isinstance(raw_content, list):
            content = []
            for part in raw_content:
                if not isinstance(part, Mapping):
                    _error("Multimodal message parts must be objects")
                kind = part.get("type")
                if kind in {"text", "input_text"}:
                    content.append({"type": "text", "text": str(part.get("text", ""))})
                elif kind in {"image", "image_url", "input_image"}:
                    source = part.get("image_url", part.get("image"))
                    content.append({"type": "image", "image": _data_image(source)})
                else:
                    _error(f"Unsupported Qwen3-VL content type: {kind}")
        else:
            _error(f"messages[{index}].content is invalid")
        result.append({"role": str(item["role"]), "content": content})
    return result


class CudaQwen3VLAdapter:
    def __init__(self, context: ModelWorkerContext) -> None:
        self.context = context
        self._model: Any | None = None
        self._processor: Any | None = None
        self._model_id: str | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        async with self._lock:
            self._model = self._processor = self._model_id = None
            with suppress(Exception):
                import torch

                torch.cuda.empty_cache()

    async def _ensure_loaded(self, model_id: str):
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None:
            _error(f"Unsupported model: {model_id}")
        if checkpoint.path is None:
            _error("Checkpoint is not installed", code="model_unavailable", status=503)
        async with self._lock:
            if self._model is not None and self._model_id == checkpoint.model_id:
                return self._model, self._processor

            def load():
                import torch
                from transformers import AutoModelForMultimodalLM, AutoProcessor

                if not torch.cuda.is_available():
                    _error("CUDA is unavailable inside the Model Worker", status=503)
                processor = AutoProcessor.from_pretrained(
                    checkpoint.path, local_files_only=True, trust_remote_code=False
                )
                model = AutoModelForMultimodalLM.from_pretrained(
                    checkpoint.path,
                    local_files_only=True,
                    trust_remote_code=False,
                    dtype=torch.bfloat16,
                ).to("cuda:0")
                return model.eval(), processor

            try:
                self._model, self._processor = await asyncio.to_thread(load)
            except ModelWorkerError:
                raise
            except Exception as error:
                raise ModelWorkerError(
                    f"Unable to load {checkpoint.repo_id}: {error}",
                    code="model_load_failed",
                    status_code=503,
                ) from error
            self._model_id = checkpoint.model_id
            return self._model, self._processor

    @staticmethod
    def _generate(model: Any, processor: Any, messages, body):
        import torch

        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)
        maximum = max(1, min(int(body.get("max_tokens") or 256), 4096))
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=maximum, do_sample=False)
        prompt_tokens = int(inputs["input_ids"].shape[-1])
        generated = output[0, prompt_tokens:]
        return processor.decode(generated, skip_special_tokens=True), prompt_tokens, int(generated.shape[-1])

    @staticmethod
    def _response(model_id: str, request_id: str, text: str, prompt: int, output: int):
        return {
            "id": request_id if request_id.startswith("chatcmpl-") else f"chatcmpl-{request_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_id,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": output, "total_tokens": prompt + output},
        }

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "chat_completions":
            _error(f"Unsupported operation: {request.operation}")
        body = dict(request.payload)
        model_id = body.get("model")
        if not isinstance(model_id, str) or not model_id:
            _error("model is required")
        model, processor = await self._ensure_loaded(model_id)
        messages = _messages(body.get("messages"))
        text, prompt, output = await asyncio.to_thread(
            self._generate, model, processor, messages, body
        )
        response = self._response(model_id, request.request_id, text, prompt, output)
        if not body.get("stream"):
            return response

        async def chunks():
            value = {
                "id": response["id"], "object": "chat.completion.chunk",
                "created": response["created"], "model": model_id,
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()
            yield b"data: [DONE]\n\n"

        return ModelWorkerStream(chunks(), headers={"Cache-Control": "no-cache"})


def create_adapter(context: ModelWorkerContext):
    return CudaQwen3VLAdapter(context)
