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
from collections import deque
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
_DEFAULT_MAX_CONTEXT = 32768
_SSD_ELEVATED_PRESSURE = 1.0 / 6.0
_SSD_CRITICAL_PRESSURE = 0.25


def _generation_finish_reason(
    stopped: bool, index: int, max_tokens: int
) -> str | None:
    if stopped:
        return "stop"
    if index + 1 >= max(1, int(max_tokens)):
        return "length"
    return None


def _effective_generation_limit(
    requested_max_tokens: int, prompt_tokens: int, max_context: int
) -> int:
    """Cap output at the remaining context instead of overrunning the engine."""

    remaining = int(max_context) - int(prompt_tokens)
    if remaining <= 0:
        raise ValueError("Prompt leaves no room for generation")
    return min(max(1, int(requested_max_tokens)), remaining)


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
            max_context
            if max_context is not None
            else os.environ.get("OMLX_DSV41_MAX_CONTEXT", str(_DEFAULT_MAX_CONTEXT))
        )
        if not 2048 <= self.max_context <= 32768:
            raise ValueError("DeepSeek V4.1 context must be in [2048, 32768]")
        self._model = None
        self._tokenizer = None
        self._lock = asyncio.Lock()
        self._active_session_id: str | None = None
        from .boost import DeepseekV41BoostController

        self._boost = DeepseekV41BoostController(self)
        self._stream_codec = validate_model_stream_codec(
            stream_codec or _DEFAULT_STREAM_CODEC
        )
        self._routed_expert_bytes_per_token = 0
        self._ssd_window_samples: deque[tuple[int, int, int]] = deque(maxlen=32)
        self._ssd_recent_10_tokens = self._empty_ssd_window()
        self._ssd_window_session_id: str | None = None
        self._ssd_recent_by_session: dict[str, dict[str, Any]] = {}
        self._ssd_turn_baseline: tuple[int, int] | None = None
        self._ssd_turn_by_session: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _empty_ssd_window() -> dict[str, Any]:
        return {
            "tokens": 0,
            "expert_loads": 0,
            "bytes_loaded": 0,
            "pressure": 0.0,
            "pressure_percent": 0.0,
            "severity": "healthy",
        }

    def _ssd_storage_totals(self) -> tuple[int, int, int]:
        """Return materialized SSD expert reads and the exact Top-6 denominator."""

        if self._model is None:
            return 0, 0, 0
        expert_loads = 0
        loaded_bytes = 0
        routed_bytes_per_token = 0
        activated = int(self._model.c.n_activated_experts)
        for bank in self._model.banks.values():
            record_bytes = int(bank.info["record_bytes"])
            bank_bytes = int(bank.bytes)
            expert_loads += bank_bytes // record_bytes if record_bytes > 0 else 0
            loaded_bytes += bank_bytes
            routed_bytes_per_token += record_bytes * activated
        return expert_loads, loaded_bytes, routed_bytes_per_token

    def _reset_ssd_window(self, session_id: str) -> None:
        loads, loaded_bytes, routed_bytes = self._ssd_storage_totals()
        self._routed_expert_bytes_per_token = routed_bytes
        self._ssd_window_samples.clear()
        self._ssd_window_samples.append((0, loads, loaded_bytes))
        self._ssd_window_session_id = session_id
        self._ssd_turn_baseline = (loads, loaded_bytes)
        self._ssd_recent_10_tokens = self._empty_ssd_window()
        self._ssd_recent_by_session[session_id] = dict(
            self._ssd_recent_10_tokens
        )
        self._ssd_turn_by_session[session_id] = dict(
            self._ssd_recent_10_tokens
        )

    def _record_ssd_window(self, token_count: int) -> None:
        loads, loaded_bytes, _routed_bytes = self._ssd_storage_totals()
        if self._ssd_window_samples and self._ssd_window_samples[-1][0] == token_count:
            self._ssd_window_samples[-1] = (token_count, loads, loaded_bytes)
        else:
            self._ssd_window_samples.append((token_count, loads, loaded_bytes))
        cutoff = max(token_count - 10, 0)
        baseline_token, baseline_loads, baseline_bytes = self._ssd_window_samples[0]
        for sample_token, sample_loads, sample_bytes in self._ssd_window_samples:
            if sample_token > cutoff:
                break
            baseline_token, baseline_loads, baseline_bytes = (
                sample_token,
                sample_loads,
                sample_bytes,
            )
        window_tokens = min(max(token_count - baseline_token, 0), 10)
        recent_loads = max(loads - baseline_loads, 0)
        recent_bytes = max(loaded_bytes - baseline_bytes, 0)
        routed_bytes = window_tokens * self._routed_expert_bytes_per_token
        pressure = recent_bytes / routed_bytes if routed_bytes > 0 else 0.0
        severity = (
            "critical"
            if pressure >= _SSD_CRITICAL_PRESSURE
            else "elevated"
            if pressure > _SSD_ELEVATED_PRESSURE
            else "healthy"
        )
        self._ssd_recent_10_tokens = {
            "tokens": window_tokens,
            "expert_loads": recent_loads,
            "bytes_loaded": recent_bytes,
            "pressure": pressure,
            "pressure_percent": pressure * 100.0,
            "severity": severity,
        }
        if self._ssd_window_session_id is None:
            return
        self._ssd_recent_by_session[self._ssd_window_session_id] = dict(
            self._ssd_recent_10_tokens
        )
        turn_baseline_loads, turn_baseline_bytes = self._ssd_turn_baseline or (
            loads,
            loaded_bytes,
        )
        turn_loads = max(loads - turn_baseline_loads, 0)
        turn_bytes = max(loaded_bytes - turn_baseline_bytes, 0)
        turn_routed_bytes = token_count * self._routed_expert_bytes_per_token
        turn_pressure = (
            turn_bytes / turn_routed_bytes if turn_routed_bytes > 0 else 0.0
        )
        turn_severity = (
            "critical"
            if turn_pressure >= _SSD_CRITICAL_PRESSURE
            else "elevated"
            if turn_pressure > _SSD_ELEVATED_PRESSURE
            else "healthy"
        )
        self._ssd_turn_by_session[self._ssd_window_session_id] = {
            "tokens": token_count,
            "expert_loads": turn_loads,
            "bytes_loaded": turn_bytes,
            "pressure": turn_pressure,
            "pressure_percent": turn_pressure * 100.0,
            "severity": turn_severity,
        }

    def get_live_metrics(self, session_id: str | None = None) -> dict[str, Any]:
        """Return already-materialized Decode telemetry without syncing MLX."""

        resolved_session = session_id or self._ssd_window_session_id
        recent = (
            self._ssd_recent_by_session.get(resolved_session)
            if resolved_session is not None
            else None
        )
        turn = (
            self._ssd_turn_by_session.get(resolved_session)
            if resolved_session is not None
            else None
        )
        return {
            "ssd_recent_10_tokens": dict(recent or self._ssd_recent_10_tokens),
            "ssd_turn_average": dict(turn) if turn is not None else {},
        }

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

    def _prepare_sync(self, messages, tools, seed, chat_template_kwargs, session_id, boost_mode):
        import mlx.core as mx

        from .encoding import encode_messages
        from .vision import Vision, prepare_images

        if self._model is None or self._tokenizer is None:
            raise RuntimeError("DeepSeek V4.1 engine is not started")
        if seed is not None:
            mx.random.seed(int(seed))
        self._model.reset_sequence()
        self._boost.prepare(session_id, boost_mode)
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
        self._model.complete_forward(logits)
        if self._model.prefill_executor is not None:
            self._model.prefill_executor.release()
        self._reset_ssd_window(session_id)
        return ids, logits

    def _decode_sync(self, token: int, position: int, session_id: str):
        import mlx.core as mx

        self._boost.apply_pending(session_id)
        logits = self._model(mx.array([[token]], dtype=mx.int32), position)
        self._model.complete_forward(logits)
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
        **kwargs,
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
        session_id = str(kwargs.pop("flesh_session_id", "default"))
        boost_mode = kwargs.pop("flesh_boost_mode", None)
        async with self._lock:
            self._active_session_id = session_id
            try:
                prompt_ids, logits = await loop.run_in_executor(
                    executor,
                    self._prepare_sync,
                    messages,
                    tools,
                    seed,
                    chat_template_kwargs,
                    session_id,
                    boost_mode,
                )
                thinking_mode, _reasoning_effort = self._reasoning_options(
                    chat_template_kwargs
                )
                generation_limit = _effective_generation_limit(
                    max_tokens, len(prompt_ids), self.max_context
                )
                generated: list[int] = []
                logits_hashes: list[str] = []
                emitted_text = ""
                eos = self._tokenizer.token_to_id("<｜end▁of▁sentence｜>")
                finish_reason = "length"
                for index in range(generation_limit):
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
                    finish_reason = _generation_finish_reason(
                        stopped, index, generation_limit
                    )
                    tool_calls = None
                    if stopped and tools:
                        from .encoding import parse_message_from_completion_text

                        parsed = parse_message_from_completion_text(text, thinking_mode)
                        tool_calls = parsed.get("tool_calls")
                    # The first sampled token comes from Prefill logits. Count
                    # only completed one-token forwards in the Decode pressure
                    # denominator so short turns do not under-report SSD load.
                    self._record_ssd_window(max(len(generated) - 1, 0))
                    yield DeepseekV41Output(
                        text=text,
                        new_text=new_text,
                        prompt_tokens=len(prompt_ids),
                        completion_tokens=len(generated),
                        finish_reason=finish_reason,
                        tool_calls=tool_calls,
                        token_ids=tuple(generated),
                        logits_sha256=tuple(logits_hashes),
                    )
                    if stopped:
                        break
                    if index + 1 < generation_limit:
                        logits = await loop.run_in_executor(
                            executor,
                            self._decode_sync,
                            token,
                            len(prompt_ids) + index,
                            session_id,
                        )
            finally:
                self._active_session_id = None

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        return self._boost.request(session_id, mode)

    def get_stats(self) -> dict[str, Any]:
        boost = self._boost.stats()
        return {
            "engine_boost": boost,
            "flesh": {
                "engine_boost": boost,
                "ssd_recent_10_tokens": dict(self._ssd_recent_10_tokens),
                "ssd_health_thresholds": {
                    "elevated_above_percent": _SSD_ELEVATED_PRESSURE * 100.0,
                    "critical_at_percent": _SSD_CRITICAL_PRESSURE * 100.0,
                    "routed_expert_bytes_per_token": (
                        self._routed_expert_bytes_per_token
                    ),
                },
                "ssd_recent_by_session": {
                    session_id: dict(window)
                    for session_id, window in self._ssd_recent_by_session.items()
                },
                "ssd_turn_by_session": {
                    session_id: dict(window)
                    for session_id, window in self._ssd_turn_by_session.items()
                },
            },
        }

    async def chat(self, messages: list[dict[str, Any]], **kwargs):
        final = None
        async for output in self.stream_chat(messages, **kwargs):
            final = output
        if final is None:
            return DeepseekV41Output(text="", finish_reason="length")
        return final


__all__ = ["DeepseekV41Engine", "DeepseekV41Output"]
