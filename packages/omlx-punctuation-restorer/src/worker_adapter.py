from __future__ import annotations

import asyncio
import unicodedata
import uuid

from ai2apps.model_worker import ModelWorkerError


def _signature(text: str) -> str:
    return "".join(
        character.casefold()
        for character in text
        if not character.isspace()
        and not unicodedata.category(character).startswith("P")
    )


def _terminal_punctuation(text: str) -> str:
    value = text.strip()
    if not value or value[-1] in ".!?。！？":
        return value
    has_cjk = any("\u3400" <= character <= "\u9fff" for character in value)
    return value + ("。" if has_cjk else ".")


class PunctuationAdapter:
    def __init__(self, context):
        self.context = context
        self._restorer = None
        self._checkpoint = None
        self._lock = asyncio.Lock()

    async def start(self):
        return None

    async def stop(self):
        self._restorer = None
        self._checkpoint = None

    async def _restorer_for(self, model_id: str):
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None:
            raise ModelWorkerError("Unsupported punctuation model")
        if checkpoint.path is None:
            raise ModelWorkerError(
                "Punctuation checkpoint is not installed",
                code="model_unavailable",
                status_code=503,
            )
        async with self._lock:
            if self._restorer is not None and self._checkpoint == checkpoint.path:
                return self._restorer

            def load():
                try:
                    import sherpa_onnx
                except ImportError as exc:
                    raise RuntimeError(
                        "The AI2Apps oMLX Runtime is missing sherpa-onnx"
                    ) from exc
                model_path = checkpoint.path / "model.int8.onnx"
                if not model_path.is_file():
                    raise RuntimeError("Pinned punctuation model is missing model.int8.onnx")
                config = sherpa_onnx.OfflinePunctuationConfig(
                    model=sherpa_onnx.OfflinePunctuationModelConfig(
                        ct_transformer=str(model_path),
                        num_threads=2,
                        provider="cpu",
                    )
                )
                return sherpa_onnx.OfflinePunctuation(config)

            self._restorer = await asyncio.to_thread(load)
            self._checkpoint = checkpoint.path
            return self._restorer

    async def invoke(self, request):
        if request.operation != "chat_completions":
            raise ModelWorkerError("Unsupported punctuation operation")
        body = dict(request.payload)
        model_id = body.get("model")
        messages = body.get("messages")
        if not isinstance(model_id, str) or not isinstance(messages, list):
            raise ModelWorkerError("model and messages are required")
        source = next(
            (
                item.get("content")
                for item in reversed(messages)
                if isinstance(item, dict)
                and item.get("role") == "user"
                and isinstance(item.get("content"), str)
            ),
            None,
        )
        if not isinstance(source, str) or not source.strip():
            raise ModelWorkerError("Punctuation input must not be empty")
        restorer = await self._restorer_for(model_id)
        candidate = await asyncio.to_thread(restorer.add_punctuation, source.strip())
        candidate = str(candidate or "").strip()
        preserved = bool(candidate) and _signature(candidate) == _signature(source)
        output = candidate if preserved else _terminal_punctuation(source)
        completion_id = f"chatcmpl-punc-{uuid.uuid4().hex}"
        return {
            "id": completion_id,
            "object": "chat.completion",
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": output},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "punctuation": {"preserves_words": preserved},
        }


def create_adapter(context):
    return PunctuationAdapter(context)
