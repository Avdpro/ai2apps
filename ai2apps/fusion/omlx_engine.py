"""BaseEngine facade that exposes a FusionOrchestrator to oMLX APIs."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Mapping
from dataclasses import replace
from typing import Any

from omlx.engine.base import BaseEngine, GenerationOutput

from .engine import FusionOrchestrator
from .control import begin_fusion_session, end_fusion_session, request_skip_review
from .types import FusionEvent, FusionRequest, FusionResult, StreamMode


class FusionEngine(BaseEngine):
    def __init__(
        self,
        orchestrator: FusionOrchestrator,
        generator_engine: BaseEngine,
        *,
        owned_engines: tuple[BaseEngine, ...] = (),
        cache_moe_defaults: Mapping[str, Any] | None = None,
    ):
        self.orchestrator = orchestrator
        self.generator_engine = generator_engine
        self.owned_engines = owned_engines
        self.cache_moe_defaults = {
            role: dict(settings)
            for role, settings in (cache_moe_defaults or {}).items()
            if isinstance(settings, Mapping)
        }
        self._started = False
        self._active_requests = 0
        self._active_sessions: set[str] = set()

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

    @property
    def supports_kv_continuity(self) -> bool:
        return bool(
            getattr(self.generator_engine, "supports_kv_continuity", False)
        )

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
        await self.close_backends()
        self._started = False

    async def close_backends(self) -> None:
        """Close Fusion-owned remote clients without stopping pooled engines."""
        for backend in (
            self.orchestrator.reviewer,
            self.orchestrator.resolver,
        ):
            close = getattr(backend, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result

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

    def _request(self, messages, kwargs) -> tuple[FusionRequest, FusionOrchestrator]:
        tools = tuple(kwargs.pop("tools", None) or ())
        tool_choice = kwargs.pop("tool_choice", None)
        mode = StreamMode(
            str(
                kwargs.pop(
                    "ai2apps_stream_mode",
                    kwargs.pop("dynamoe_stream_mode", "reasoning"),
                )
            )
        )
        # Provisional tool syntax must never reach a client. Tool requests use
        # the canonical-only transport regardless of the requested mode.
        if tools:
            mode = StreamMode.FINAL
        session_id = str(
            kwargs.pop("fusion_session_id", None)
            or kwargs.get("flesh_session_id", None)
            or "default"
        )
        max_tokens = int(kwargs.pop("max_tokens", 256))
        high_risk = bool(kwargs.pop("fusion_high_risk", False))
        prompt_risk = kwargs.pop("fusion_prompt_risk", None)
        override_map = {
            "gate_policy": kwargs.pop("fusion_gate_policy", None),
            "mid_generation_review_enabled": kwargs.pop(
                "fusion_mid_generation_review_enabled", None
            ),
            "thinking_audit_enabled": kwargs.pop(
                "fusion_thinking_audit_enabled", None
            ),
            "reviewer_guidance_mode": kwargs.pop(
                "fusion_reviewer_guidance_mode", None
            ),
        }
        checkpoint_tokens = kwargs.pop("fusion_checkpoint_tokens", None)
        if checkpoint_tokens is not None:
            override_map["mid_generation_checkpoint_tokens"] = int(
                checkpoint_tokens
            )
        overrides = {
            key: value for key, value in override_map.items() if value is not None
        }
        orchestrator = self.orchestrator
        if overrides:
            orchestrator = FusionOrchestrator(
                replace(self.orchestrator.config, **overrides),
                self.orchestrator.generator,
                self.orchestrator.reviewer,
                self.orchestrator.resolver,
                self.orchestrator.validator,
            )
        generator_cache = self.cache_moe_defaults.get("generator", {})
        reviewer_cache = self.cache_moe_defaults.get("reviewer", {})
        legacy_generator_boost = kwargs.get("flesh_boost_mode")
        legacy_reviewer_boost = kwargs.get("fusion_reviewer_boost_mode")
        kwargs.setdefault("flesh_l1_mode", generator_cache.get("l1_mode", "auto"))
        kwargs.setdefault(
            "flesh_prefill_boost_mode",
            legacy_generator_boost or generator_cache.get(
                "prefill_boost",
                generator_cache.get("engine_boost", "natural"),
            ),
        )
        kwargs.setdefault(
            "flesh_decode_boost_mode",
            legacy_generator_boost or generator_cache.get(
                "decode_boost",
                generator_cache.get("engine_boost", "natural"),
            ),
        )
        kwargs.setdefault(
            "fusion_reviewer_l1_mode", reviewer_cache.get("l1_mode", "auto")
        )
        kwargs.setdefault(
            "fusion_reviewer_prefill_boost_mode",
            legacy_reviewer_boost or reviewer_cache.get(
                "prefill_boost",
                reviewer_cache.get("engine_boost", "natural"),
            ),
        )
        kwargs.setdefault(
            "fusion_reviewer_decode_boost_mode",
            legacy_reviewer_boost or reviewer_cache.get(
                "decode_boost",
                reviewer_cache.get("engine_boost", "natural"),
            ),
        )
        request = FusionRequest(
            messages=messages,
            session_id=session_id,
            max_tokens=max_tokens,
            stream_mode=mode,
            sampling=dict(kwargs),
            high_risk=high_risk,
            prompt_risk=prompt_risk,
            tools=tools,
            tool_choice=tool_choice,
        )
        return request, orchestrator

    async def chat(self, messages, **kwargs) -> GenerationOutput:
        if not self._started:
            await self.start()
        request, orchestrator = self._request(messages, kwargs)
        self._active_requests += 1
        self._active_sessions.add(request.session_id)
        begin_fusion_session(request.session_id)
        try:
            result = await orchestrator.generate(request)
        finally:
            end_fusion_session(request.session_id)
            self._active_requests -= 1
            self._active_sessions.discard(request.session_id)
        return self._result_output(result)

    async def stream_chat(self, messages, **kwargs) -> AsyncIterator[GenerationOutput]:
        if not self._started:
            await self.start()
        request, orchestrator = self._request(messages, kwargs)
        self._active_requests += 1
        self._active_sessions.add(request.session_id)
        begin_fusion_session(request.session_id)
        try:
            async for event in orchestrator.stream(request):
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
            end_fusion_session(request.session_id)
            self._active_requests -= 1
            self._active_sessions.discard(request.session_id)

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
        stats = {
            "engine_type": "fusion",
            "model_name": self.model_name,
            "loaded": self._started,
            "active_requests": self._active_requests,
            "generator": self.generator_engine.model_name,
            "resolver_enabled": self.orchestrator.config.resolver_enabled,
            "gate_policy": self.orchestrator.config.gate_policy,
        }
        continuity_stats = getattr(self.orchestrator.generator, "stats", None)
        if callable(continuity_stats):
            stats["generator_kv"] = continuity_stats()
        return stats

    def get_cache_stats(self):
        return self.generator_engine.get_cache_stats()

    def request_l1_optimization(self, session_id: str) -> dict[str, Any]:
        trigger = getattr(self.generator_engine, "request_l1_optimization", None)
        if not callable(trigger):
            return {"accepted": False, "reason": "generator does not support adaptive L1"}
        return trigger(session_id)

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        setter = getattr(self.generator_engine, "request_engine_boost", None)
        if not callable(setter):
            return {"accepted": False, "reason": "generator does not support Engine Boost"}
        return setter(session_id, mode)

    def request_skip_review(self, session_id: str) -> dict[str, Any]:
        if not session_id:
            return {"accepted": False, "reason": "session_id is required"}
        if session_id not in self._active_sessions:
            return {"accepted": False, "reason": "Fusion session is not active"}
        request_skip_review(session_id)
        return {"accepted": True, "session_id": session_id}

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
            prompt_tokens=int(result.signals.extra.get("prompt_tokens", 0) or 0),
            completion_tokens=result.signals.output_tokens,
            cached_tokens=int(result.signals.extra.get("cached_tokens", 0) or 0),
            finish_reason=(
                "tool_calls" if result.tool_calls else result.signals.finish_reason
            ),
            tool_calls=(
                [call.to_mapping() for call in result.tool_calls]
                if result.tool_calls
                else None
            ),
            fusion_event=(self._event_payload(event) if event else None),
        )
