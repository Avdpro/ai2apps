"""Single-request DeepSeek V4.1 engine for the Model Worker protocol."""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omlx.api.stream_codec import (
    ModelStreamCodec,
    PrefixTextStreamCodec,
    validate_model_stream_codec,
)

_IMAGE_DATA_URL = re.compile(
    r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\r\n]+)$"
)
_IMAGE_SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
_MAX_IMAGE_BYTES = 32 * 1024 * 1024
_DEFAULT_STREAM_CODEC = PrefixTextStreamCodec()


def _decode_generated_prefix(tokenizer, token_ids: list[int], eos_token_id: int | None) -> str:
    """Decode an append-only generation prefix without hiding reasoning markers.

    DeepSeek V4.1 represents ``<think>`` and ``</think>`` as special tokens.  The
    Worker-level reasoning parser therefore needs those markers in the engine's
    text stream.  Rust tokenizers can also expose a trailing replacement
    character while a multi-byte UTF-8 sequence is incomplete; withholding that
    unstable suffix prevents the next token from making the decoded prefix
    regress and being replayed as duplicate content.
    """

    return _DEFAULT_STREAM_CODEC.decode_prefix(
        tokenizer, token_ids, eos_token_id=eos_token_id
    )


def _append_only_text_delta(previous: str, current: str) -> tuple[str, str]:
    """Return the stable current prefix and only its newly appended suffix."""

    return _DEFAULT_STREAM_CODEC.append_delta(previous, current)


@dataclass(slots=True)
class DeepseekV41Output:
    text: str
    new_text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    token_ids: tuple[int, ...] = ()
    logits_sha256: tuple[str, ...] = ()


class DeepseekV41Engine:
    """Run the frozen lossless Top-6/L1-40/L0-8 standard profile."""

    def __init__(
        self,
        checkpoint: str | Path,
        *,
        max_context: int | None = None,
        stream_codec: ModelStreamCodec | None = None,
    ):
        self.checkpoint = Path(checkpoint).expanduser().resolve()
        self.max_context = int(
            max_context or os.environ.get("OMLX_DSV41_MAX_CONTEXT", "4096")
        )
        if not 2048 <= self.max_context <= 32768:
            raise ValueError("DeepSeek V4.1 context must be in [2048, 32768]")
        self._model = None
        self._tokenizer = None
        self._lock = asyncio.Lock()
        self._stream_codec = validate_model_stream_codec(
            stream_codec or _DEFAULT_STREAM_CODEC
        )

    async def start(self) -> None:
        if self._model is not None:
            return
        from omlx.engine_core import get_mlx_executor

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(get_mlx_executor(), self._start_sync)

    def _start_sync(self) -> None:
        import mlx.core as mx
        from tokenizers import Tokenizer

        from omlx.ssd_checkpoint import inspect_ssd_checkpoint

        from .adaptive import AdaptiveModel
        from .storage import Storage

        marker = inspect_ssd_checkpoint(
            self.checkpoint,
            expected_family="deepseek_v41",
            expected_layout="dsv41-original-fp4-six-segment-v1",
        )
        expert_store = (self.checkpoint / marker["expert_store"]).resolve()
        config = json.loads(
            (self.checkpoint / "inference/config.json").read_text(encoding="utf-8")
        )
        config.update(dspark_block_size=0, max_batch_size=1, temperature=0)
        vision_max_tokens = int(os.environ.get("OMLX_DSV41_VISION_MAX_TOKENS", "256"))
        if vision_max_tokens not in {256, 512, 1024}:
            raise ValueError("DeepSeek V4.1 vision tokens must be 256, 512, or 1024")
        config["vision_max_n_token"] = vision_max_tokens
        tokenizer = Tokenizer.from_file(str(self.checkpoint / "tokenizer.json"))
        mx.set_cache_limit(2 * 2**30)
        mx.set_memory_limit(60_000_000_000)
        store = Storage(self.checkpoint)
        try:
            model = AdaptiveModel(
                config,
                store,
                tokenizer,
                expert_store,
                self.max_context,
                40,
                hot_slots=8,
                matrix_prefill=True,
                prefill_slots=64,
                prefill_top=None,
                prefill_hot_direct=True,
                decode_dispatch="legacy",
                attention_chunk=64,
            )
            model.l1_policy = "eviction_dual"
            model.reuse_hot_promotions = True
            model.slot_swap_promotions = True
        except BaseException:
            store.close()
            raise
        self._tokenizer = tokenizer
        self._model = model

    async def stop(self) -> None:
        model, self._model = self._model, None
        self._tokenizer = None
        if model is None:
            return
        from omlx.engine_core import get_mlx_executor

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(get_mlx_executor(), model.close)

    @staticmethod
    def _messages(messages: list[dict[str, Any]], tools) -> list[dict[str, Any]]:
        prepared = copy.deepcopy(messages)
        for message in prepared:
            content = message.get("content")
            if not isinstance(content, list):
                continue
            blocks = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") in {"text", "input_text", "output_text"}:
                    blocks.append({"type": "text", "text": str(part.get("text", ""))})
                    continue
                if part.get("type") == "image_url":
                    blocks.append(part)
                    continue
                if part.get("type") == "input_image":
                    source = part.get("image_url") or part.get("url")
                    blocks.append({"type": "image_url", "image_url": source})
                    continue
                blocks.append(part)
            message["content_blocks"] = blocks
        if tools and prepared:
            prepared[0]["tools"] = tools
        return prepared

    @staticmethod
    def _materialize_images(records: list[dict[str, Any]], directory: Path) -> list[Path]:
        paths = []
        total = 0
        for index, record in enumerate(records):
            value = record.get("url") or record.get("data")
            if not isinstance(value, str):
                raise ValueError("DeepSeek V4.1 image source is invalid")
            match = _IMAGE_DATA_URL.fullmatch(value)
            if match is None:
                raise ValueError(
                    "DeepSeek V4.1 accepts request-local PNG, JPEG, or WebP data URLs"
                )
            try:
                payload = base64.b64decode(match.group(2), validate=True)
            except ValueError as exc:
                raise ValueError("DeepSeek V4.1 image data URL is malformed") from exc
            total += len(payload)
            if not payload or total > _MAX_IMAGE_BYTES:
                raise ValueError("DeepSeek V4.1 image payload exceeds the 32 MiB limit")
            path = directory / f"image-{index:03d}{_IMAGE_SUFFIXES[match.group(1)]}"
            path.write_bytes(payload)
            paths.append(path)
        return paths

    @staticmethod
    def _reasoning_options(chat_template_kwargs):
        options = dict(chat_template_kwargs or {})
        thinking_mode = options.get("thinking_mode")
        if thinking_mode is None:
            thinking_mode = "thinking" if options.get("enable_thinking", True) else "chat"
        if thinking_mode not in {"chat", "thinking"}:
            raise ValueError("DeepSeek V4.1 thinking_mode must be 'chat' or 'thinking'")
        return thinking_mode, options.get("reasoning_effort")

    def _prepare_sync(self, messages, tools, seed, chat_template_kwargs):
        import mlx.core as mx

        from .encoding import encode_messages
        from .vision import Vision, prepare_images

        if self._model is None or self._tokenizer is None:
            raise RuntimeError("DeepSeek V4.1 engine is not started")
        if seed is not None:
            mx.random.seed(int(seed))
        self._model.reset_sequence()
        thinking_mode, reasoning_effort = self._reasoning_options(
            chat_template_kwargs
        )
        prompt, media = encode_messages(
            self._messages(messages, tools),
            thinking_mode=thinking_mode,
            reasoning_effort=reasoning_effort,
            return_multi_modal_data=True,
        )
        ids = self._tokenizer.encode(prompt).ids
        image_records = media["images"]
        if image_records:
            with tempfile.TemporaryDirectory(prefix="ai2apps-dsv41-images-") as raw:
                images, _image_ids, _types = prepare_images(
                    self._materialize_images(image_records, Path(raw)), self._model.c
                )
                expanded = []
                vision_types = []
                image_iter = iter(images)
                for token in ids:
                    if token == self._model.c.image_token_id:
                        try:
                            image = next(image_iter)
                        except StopIteration as exc:
                            raise ValueError("DeepSeek V4.1 image placeholder mismatch") from exc
                        image.start = len(expanded)
                        expanded.extend([token] * len(image.types))
                        vision_types.extend(image.types)
                    else:
                        expanded.append(token)
                        vision_types.append(-1)
                try:
                    next(image_iter)
                except StopIteration:
                    pass
                else:
                    raise ValueError("DeepSeek V4.1 image placeholder mismatch")
                if not hasattr(self._model, "vision"):
                    self._model.vision = Vision(self._model.s, self._model.c)
                    self._model.vision.load()
                self._model.vision_images = images
                self._model.vision_types = mx.array([vision_types], dtype=mx.int32)
                ids = expanded
        if not ids:
            raise ValueError("DeepSeek V4.1 prompt is empty")
        if len(ids) >= self.max_context:
            raise ValueError(
                f"DeepSeek V4.1 prompt has {len(ids)} tokens; limit is {self.max_context - 1}"
            )
        logits = self._model(mx.array([ids], dtype=mx.int32), 0)
        mx.eval(logits)
        if self._model.prefill_executor is not None:
            self._model.prefill_executor.release()
        return ids, logits

    def _decode_sync(self, token: int, position: int):
        import mlx.core as mx

        logits = self._model(mx.array([[token]], dtype=mx.int32), position)
        mx.eval(logits)
        return logits

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 0,
        min_p: float = 0.0,
        repetition_penalty: float = 1.0,
        presence_penalty: float = 0.0,
        tools=None,
        stop=None,
        seed=None,
        chat_template_kwargs=None,
        **_kwargs,
    ):
        import mlx.core as mx
        from mlx_lm.sample_utils import make_logits_processors, make_sampler

        from omlx.engine_core import get_mlx_executor

        await self.start()
        sampler = make_sampler(
            temp=max(0.0, float(temperature)),
            top_p=float(top_p),
            top_k=int(top_k),
            min_p=float(min_p),
        )
        processors = make_logits_processors(
            repetition_penalty=(
                None if float(repetition_penalty) == 1.0 else float(repetition_penalty)
            ),
            presence_penalty=(
                None if float(presence_penalty) == 0.0 else float(presence_penalty)
            ),
        )
        stop_strings = (
            [stop] if isinstance(stop, str) else [str(value) for value in (stop or [])]
        )
        loop = asyncio.get_running_loop()
        executor = get_mlx_executor()
        async with self._lock:
            prompt_ids, logits = await loop.run_in_executor(
                executor,
                self._prepare_sync,
                messages,
                tools,
                seed,
                chat_template_kwargs,
            )
            thinking_mode, _reasoning_effort = self._reasoning_options(
                chat_template_kwargs
            )
            generated: list[int] = []
            logits_hashes: list[str] = []
            emitted_text = ""
            eos = self._tokenizer.token_to_id("<｜end▁of▁sentence｜>")
            finish_reason = "length"
            for index in range(max(1, int(max_tokens))):
                import numpy as np

                logits_hashes.append(
                    hashlib.sha256(
                        np.array(logits.astype(mx.float32)).tobytes()
                    ).hexdigest()
                )
                processed = logits
                for processor in processors:
                    processed = processor(generated, processed)
                token = int(sampler(processed).item())
                generated.append(token)
                text = self._stream_codec.decode_prefix(
                    self._tokenizer, generated, eos_token_id=eos
                )
                stopped = token == eos
                for marker in stop_strings:
                    offset = text.find(marker)
                    if offset >= 0:
                        text = text[:offset]
                        stopped = True
                        break
                emitted_text, new_text = self._stream_codec.append_delta(
                    emitted_text, text
                )
                text = emitted_text
                finish_reason = "stop" if stopped else "length"
                tool_calls = None
                if stopped and tools:
                    from .encoding import parse_message_from_completion_text

                    parsed = parse_message_from_completion_text(text, thinking_mode)
                    tool_calls = parsed.get("tool_calls")
                yield DeepseekV41Output(
                    text=text,
                    new_text=new_text,
                    prompt_tokens=len(prompt_ids),
                    completion_tokens=len(generated),
                    finish_reason=finish_reason if stopped else None,
                    tool_calls=tool_calls,
                    token_ids=tuple(generated),
                    logits_sha256=tuple(logits_hashes),
                )
                if stopped:
                    break
                if index + 1 < int(max_tokens):
                    logits = await loop.run_in_executor(
                        executor,
                        self._decode_sync,
                        token,
                        len(prompt_ids) + index,
                    )

    async def chat(self, messages: list[dict[str, Any]], **kwargs):
        final = None
        async for output in self.stream_chat(messages, **kwargs):
            final = output
        if final is None:
            return DeepseekV41Output(text="", finish_reason="length")
        return final


__all__ = ["DeepseekV41Engine", "DeepseekV41Output"]
