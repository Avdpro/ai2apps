"""Minimal Adapter example; replace DemoBackend with a real inference engine."""

from __future__ import annotations

import json
import time

from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerStream


class DemoAdapter:
    def __init__(self, context):
        self.context = context

    async def start(self) -> None:
        """Load the engine/checkpoint here. Called once after Worker startup."""

    async def stop(self) -> None:
        """Release the engine here. Called once during graceful shutdown."""

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "chat_completions":
            return {
                "error": {
                    "code": "operation_not_supported",
                    "message": f"Unsupported operation: {request.operation}",
                }
            }
        model = str(request.payload.get("model", "example/demo-checkpoint"))
        if request.payload.get("stream"):
            return ModelWorkerStream(self._stream(model, request.request_id))
        return {
            "id": request.request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Model Worker is ready."},
                    "finish_reason": "stop",
                }
            ],
        }

    async def _stream(self, model: str, request_id: str):
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "delta": {"content": "Model Worker is ready."}, "finish_reason": None}
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n".encode()
        yield b"data: [DONE]\n\n"


def create_adapter(context):
    return DemoAdapter(context)
