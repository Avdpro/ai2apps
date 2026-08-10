"""BaseEngine facade that exposes a FusionOrchestrator to oMLX APIs."""

from __future__ import annotations

import inspect
from typing import Any, AsyncIterator

from omlx.engine.base import BaseEngine, GenerationOutput

from .engine import FusionOrchestrator
from .types import FusionEvent, FusionRequest, FusionResult, StreamMode


class FusionEngine(BaseEngine):
    def __init__(
        self,
        orchestrator: FusionOrchestrator,
        generator_engine: BaseEngine,
        *,
        owned_engines: tuple[BaseEngine, ...] = (),
    ):
        self.orchestrator = orchestrator
        self.generator_engine = generator_engine
        self.owned_engines = owned_engines
        self._started = False
        self._active_requests = 0

    @property
    def model_name(self) -> str:
        return self.orchestrator.config.model_id

    @property
    def tokenizer(self) -> Any:
        return self.generator_engine.tokenizer

    @property
    def model_type(self) -> str:
        return "ai2apps_fusion"

    @property
    def grammar_compiler(self):
        return getattr(self.generator_engine, "grammar_compiler", None)

    @property
    def prefix_cache_enabled(self) -> bool:
        return bool(getattr(self.generator_engine, "prefix_cache_enabled", False))

    async def start(self) -> None:
        if self._started:
            return
        engines = (self.generator_engine, *self.owned_engines)
        seen: set[int] = set()
        for engine in engines:
            if id(engine) in seen:
                continue
            seen.add(id(engine))
            await engine.start()
        self._started = True

    async def stop(self) -> None:
        seen: set[int] = set()
        for engine in reversed((self.generator_engine, *self.owned_engines)):
            if id(engine) in seen:
                continue
            seen.add(id(engine))
            await engine.stop()
        for backend in (
            self.orchestrator.reviewer,
            self.orchestrator.resolver,
        ):
            close = getattr(backend, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result
        self._started = False

    def count_chat_tokens(self, messages, tools=None, **kwargs) -> int:
        return self.generator_engine.count_chat_tokens(messages, tools, **kwargs)

    async def preflight_chat(self, messages, tools=None, request_id=None, **kwargs):
        await self.generator_engine.preflight_chat(
            messages, tools=tools, request_id=request_id, **kwargs
        )

    async def preflight_completion(self, prompt, request_id=None, **kwargs):
        await self.generator_engine.preflight_completion(
            prompt, request_id=request_id, **kwargs
        )

    def _request(self, messages, kwargs) -> FusionRequest:
        if kwargs.get("tools"):
            raise ValueError("Fusion v1 does not support tool calling")
        kwargs.pop("tools", None)
        mode = StreamMode(
            str(
                kwargs.pop(
                    "ai2apps_stream_mode",
                    kwargs.pop("dynamoe_stream_mode", "reasoning"),
                )
            )
        )
        session_id = str(
            kwargs.pop("fusion_session_id", None)
            or kwargs.get("flesh_session_id", None)
            or "default"
        )
        max_tokens = int(kwargs.pop("max_tokens", 256))
        high_risk = bool(kwargs.pop("fusion_high_risk", False))
        prompt_risk = kwargs.pop("fusion_prompt_risk", None)
        return FusionRequest(
            messages=messages,
            session_id=session_id,
            max_tokens=max_tokens,
            stream_mode=mode,
            sampling=dict(kwargs),
            high_risk=high_risk,
            prompt_risk=prompt_risk,
        )

    async def chat(self, messages, **kwargs) -> GenerationOutput:
        if not self._started:
            await self.start()
        request = self._request(messages, kwargs)
        self._active_requests += 1
        try:
            result = await self.orchestrator.generate(request)
        finally:
            self._active_requests -= 1
        return self._result_output(result)

    async def stream_chat(self, messages, **kwargs) -> AsyncIterator[GenerationOutput]:
        if not self._started:
            await self.start()
        request = self._request(messages, kwargs)
        self._active_requests += 1
        try:
            async for event in self.orchestrator.stream(request):
                result = event.metadata.get("result")
                if isinstance(result, FusionResult):
                    yield self._result_output(result, event=event)
                else:
                    yield GenerationOutput(
                        text="",
                        new_text="",
                        finished=False,
                        finish_reason=None,
                        fusion_event=self._event_payload(event),
                    )
        finally:
            self._active_requests -= 1

    async def generate(self, prompt, **kwargs) -> GenerationOutput:
        return await self.chat([{"role": "user", "content": prompt}], **kwargs)

    async def stream_generate(
        self, prompt, **kwargs
    ) -> AsyncIterator[GenerationOutput]:
        async for output in self.stream_chat(
            [{"role": "user", "content": prompt}], **kwargs
        ):
            yield output

    def has_active_requests(self) -> bool:
        return self._active_requests > 0

    def get_stats(self) -> dict[str, Any]:
        return {
            "engine_type": "fusion",
            "model_name": self.model_name,
            "loaded": self._started,
            "active_requests": self._active_requests,
            "generator": self.generator_engine.model_name,
            "resolver_enabled": self.orchestrator.config.resolver_enabled,
            "gate_policy": self.orchestrator.config.gate_policy,
        }

    def get_cache_stats(self):
        return self.generator_engine.get_cache_stats()

    @staticmethod
    def _event_payload(event: FusionEvent) -> dict[str, Any]:
        metadata = {
            key: value
            for key, value in event.metadata.items()
            if key != "result"
        }
        return {
            "phase": event.phase,
            "channel": event.channel,
            "text": event.text,
            "draft_id": event.draft_id,
            "metadata": metadata,
        }

    def _result_output(
        self, result: FusionResult, event: FusionEvent | None = None
    ) -> GenerationOutput:
        return GenerationOutput(
            text=result.text,
            new_text="",
            finished=True,
            completion_tokens=result.signals.output_tokens,
            finish_reason=result.signals.finish_reason,
            fusion_event=(self._event_payload(event) if event else None),
        )
