"""Adapters for existing oMLX engines and OpenAI-compatible reviewers."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from omlx.api.thinking import extract_thinking
from omlx.api.tool_calling import extract_tool_calls_with_thinking

from .prompts import (
    REVIEW_DECISION_RETRY_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    build_checkpoint_review_messages,
    build_realization_messages,
    build_reasoning_handoff_messages,
    build_redirect_messages,
    build_review_jsonl,
    build_review_messages,
    build_revision_messages,
    build_tool_replan_messages,
    build_tool_review_messages,
    reviewable_messages,
)
from .serde import (
    checkpoint_decision_from_json,
    review_decision_from_json,
    review_decision_from_mapping,
    tool_review_decision_from_json,
)
from .tooling import normalize_tool_calls
from .types import (
    CheckpointAction,
    CheckpointDecision,
    DraftChunk,
    FusionRequest,
    FusionToolCall,
    GateSignals,
    ReviewAction,
    ReviewDecision,
    StructuredPatch,
    ToolReviewDecision,
)


@dataclass
class _ReviewerPassState:
    """Exact append-only prompt lineage committed by a successful review."""

    prompt_messages: list[dict[str, Any]]
    covered_conversation: list[dict[str, object]]
    epoch: int


@dataclass
class _GeneratorPassState:
    """Raw append-only generator transcript behind the visible conversation."""

    prompt_messages: list[dict[str, Any]]
    covered_conversation: list[dict[str, Any]]


class _ThinkingAuditDetector:
    """Detect a bounded, semantically useful thinking checkpoint."""

    _BOUNDARIES = (".", "!", "?", ";", "。", "！", "？", "；", "\n\n")

    def __init__(self, tokenizer: Any, *, min_tokens: int, max_tokens: int):
        self.tokenizer = tokenizer
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.text = ""
        self.start_index: int | None = None
        self.start_marker = ""
        self.start_completion_tokens = 0
        self.thinking_tokens = 0
        self.start_markers = self._markers("think_start", "<think>")
        self.end_markers = self._markers("think_end", "</think>")

    def _markers(self, attribute: str, fallback: str) -> tuple[str, ...]:
        values = [fallback]
        try:
            value = getattr(self.tokenizer, attribute, None)
        except (AttributeError, TypeError, ValueError):
            value = None
        if isinstance(value, str) and value and value not in values:
            values.append(value)
        return tuple(values)

    def _count_tokens(self, text: str, completion_tokens: int) -> int:
        encode = getattr(self.tokenizer, "encode", None)
        if callable(encode):
            try:
                return len(encode(text, add_special_tokens=False))
            except TypeError:
                try:
                    return len(encode(text))
                except Exception:
                    pass
            except Exception:
                pass
        return max(0, completion_tokens - self.start_completion_tokens)

    def feed(self, text: str, *, completion_tokens: int, finished: bool) -> bool:
        self.text += text
        if self.start_index is None:
            matches = [
                (self.text.find(marker), marker)
                for marker in self.start_markers
                if self.text.find(marker) >= 0
            ]
            if not matches:
                keep = max(len(marker) for marker in self.start_markers) - 1
                if keep > 0 and len(self.text) > keep:
                    self.text = self.text[-keep:]
                return False
            self.start_index, self.start_marker = min(matches, key=lambda item: item[0])
            self.start_completion_tokens = completion_tokens

        body_start = self.start_index + len(self.start_marker)
        end_matches = [
            self.text.find(marker, body_start)
            for marker in self.end_markers
            if self.text.find(marker, body_start) >= 0
        ]
        closed = bool(end_matches)
        body_end = min(end_matches) if end_matches else len(self.text)
        body = self.text[body_start:body_end]
        self.thinking_tokens = self._count_tokens(body, completion_tokens)
        at_boundary = body.endswith("\n\n") or body.rstrip().endswith(
            self._BOUNDARIES[:-1]
        )
        return (
            closed
            or finished
            or self.thinking_tokens >= self.max_tokens
            or (self.thinking_tokens >= self.min_tokens and at_boundary)
        )


class OMLXGeneratorTurn:
    """One provisional turn backed by an existing oMLX BaseEngine."""

    def __init__(
        self,
        engine: Any,
        request: FusionRequest,
        continuity: OMLXGeneratorBackend | None = None,
        covered_conversation: Sequence[Mapping[str, Any]] | None = None,
    ):
        self.engine = engine
        self.request = request
        self.continuity = continuity
        self._finished = False
        self._checkpoint_tokens = 0
        self._prompt_tokens = 0
        self._cached_tokens = 0
        self._draft_parts: list[str] = []
        self._covered_conversation = [
            dict(message)
            for message in (covered_conversation or request.messages)
        ]

    def _cache_metrics(self, **extra: Any) -> dict[str, Any]:
        return {
            "prompt_tokens": self._prompt_tokens,
            "cached_tokens": self._cached_tokens,
            **extra,
        }

    def _kwargs(self, *, max_tokens: int | None = None) -> dict[str, Any]:
        values = dict(self.request.sampling)
        values.pop("fusion_reviewer_l1_mode", None)
        values.pop("fusion_reviewer_boost_mode", None)
        values.pop("fusion_reviewer_prefill_boost_mode", None)
        values.pop("fusion_reviewer_decode_boost_mode", None)
        values["max_tokens"] = max_tokens or self.request.max_tokens
        values.setdefault("flesh_session_id", self.request.session_id)
        # Prefix blocks are content-addressed and session-namespaced. A PASS
        # can therefore reuse the complete prompt+draft lineage, while a
        # changed canonical answer can only match the safe common prefix.
        # Strict requests retain the old no-store behavior.
        kv_policy = str(values.get("flesh_kv_policy", "strict")).lower()
        values.setdefault("skip_cache_store", kv_policy == "strict")
        if self.request.tools:
            values["tools"] = list(self.request.tools)
        return values

    def _cache_runtime_kwargs(self) -> dict[str, Any]:
        values = {
            key: self.request.sampling[key]
            for key in (
                "flesh_l1_mode",
                "flesh_boost_mode",
                "flesh_prefill_boost_mode",
                "flesh_decode_boost_mode",
            )
            if key in self.request.sampling
        }
        values["flesh_session_id"] = self.request.session_id
        return values

    def _history_content(self, raw_draft: str) -> str:
        """Include template-owned generation prefix in the committed transcript.

        Qwen can place an empty ``<think>...</think>`` marker in the rendered
        generation prompt even when thinking is disabled.  That marker is KV
        input, not streamed output.  Recover it through a rendered probe so the
        next historical assistant message reproduces the exact token lineage.
        """
        if self.request.tools:
            return raw_draft
        render = getattr(self.engine, "_apply_chat_template", None)
        tokenizer = getattr(self.engine, "tokenizer", None) or getattr(
            self.engine, "_tokenizer", None
        )
        if not callable(render) or tokenizer is None:
            return raw_draft
        try:
            template_kwargs = self.request.sampling.get("chat_template_kwargs")
            prompt = render(
                [dict(message) for message in self.request.messages],
                None,
                chat_template_kwargs=template_kwargs,
                is_partial=False,
            )
            probe = render(
                [
                    *[dict(message) for message in self.request.messages],
                    {
                        "role": "assistant",
                        "content": "OMLX_GENERATOR_PREFIX_PROBE_7f31c9",
                    },
                ],
                None,
                chat_template_kwargs=template_kwargs,
                is_partial=False,
            )
            prompt_tokens = list(tokenizer.encode(prompt))
            probe_tokens = list(tokenizer.encode(probe))
            boundary = 0
            for actual, candidate in zip(prompt_tokens, probe_tokens):
                if actual != candidate:
                    break
                boundary += 1
            prefix = tokenizer.decode(prompt_tokens[boundary:])
            if prefix and not raw_draft.startswith(prefix):
                return prefix + raw_draft
        except Exception:
            return raw_draft
        return raw_draft

    async def _stream_tool_candidate(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
    ) -> AsyncIterator[DraftChunk]:
        raw_parts: list[str] = []
        raw_calls: Any = None
        last = None
        async for output in self._stream_segment(messages, max_tokens=max_tokens):
            last = output
            if output.new_text:
                raw_parts.append(str(output.new_text))
            if getattr(output, "tool_calls", None):
                raw_calls = output.tool_calls
        raw = "".join(raw_parts)
        thinking, regular = extract_thinking(raw)
        extraction = extract_tool_calls_with_thinking(
            thinking,
            regular,
            getattr(self.engine, "tokenizer", None),
            list(self.request.tools),
        )
        if raw_calls:
            calls = normalize_tool_calls(raw_calls)
        else:
            calls = normalize_tool_calls(extraction.tool_calls)
        cleaned_text = extraction.cleaned_text
        if cleaned_text:
            yield DraftChunk(text=cleaned_text)
        completion_tokens = int(getattr(last, "completion_tokens", 0) or 0)
        finish_reason = str(getattr(last, "finish_reason", "stop") or "stop")
        self._finished = True
        yield DraftChunk(
            finished=True,
            finish_reason=finish_reason,
            token_count=completion_tokens,
            signals=GateSignals(
                output_tokens=completion_tokens,
                finish_reason=finish_reason,
                extra=self._cache_metrics(),
            ),
            tool_calls=calls,
        )

    async def _stream_segment(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        is_partial: bool = False,
        store_checkpoint: bool = False,
    ) -> AsyncIterator[Any]:
        kwargs = self._kwargs(max_tokens=max_tokens)
        if store_checkpoint:
            kwargs["skip_cache_store"] = False
        if is_partial:
            kwargs["is_partial"] = True
        async for output in self.engine.stream_chat(messages=messages, **kwargs):
            self._prompt_tokens = max(
                self._prompt_tokens,
                int(getattr(output, "prompt_tokens", 0) or 0),
            )
            self._cached_tokens = max(
                self._cached_tokens,
                int(getattr(output, "cached_tokens", 0) or 0),
            )
            yield output

    async def stream_draft(self) -> AsyncIterator[DraftChunk]:
        if self.request.tools:
            async for chunk in self._stream_tool_candidate(
                [dict(message) for message in self.request.messages],
                max_tokens=self.request.max_tokens,
            ):
                yield chunk
            return
        last = None
        checkpoint_enabled = (
            self.request.metadata.get("mid_generation_review_enabled") is True
        )
        checkpoint_tokens = int(
            self.request.metadata.get("mid_generation_checkpoint_tokens", 0) or 0
        )
        will_checkpoint = (
            checkpoint_enabled
            and checkpoint_tokens > 0
            and self.request.max_tokens > checkpoint_tokens
        )
        segment_tokens = (
            checkpoint_tokens if will_checkpoint else self.request.max_tokens
        )
        thinking_audit_enabled = (
            self.request.metadata.get("thinking_audit_enabled") is True
        )
        detector = None
        if thinking_audit_enabled:
            detector = _ThinkingAuditDetector(
                getattr(self.engine, "tokenizer", None),
                min_tokens=int(
                    self.request.metadata.get("thinking_audit_min_tokens", 128)
                ),
                max_tokens=int(
                    self.request.metadata.get("thinking_audit_max_tokens", 256)
                ),
            )
        # Token progress belongs to the pipeline UI even when checkpoint
        # auditing is disabled. Reuse the audit detector when present;
        # otherwise keep a non-triggering detector solely for counting the
        # generated thinking prefix.
        progress_detector = detector or _ThinkingAuditDetector(
            getattr(self.engine, "tokenizer", None),
            min_tokens=2**31 - 1,
            max_tokens=2**31 - 1,
        )
        async for output in self._stream_segment(
            [dict(message) for message in self.request.messages],
            max_tokens=segment_tokens,
            store_checkpoint=will_checkpoint,
        ):
            last = output
            completion_tokens = int(
                getattr(output, "completion_tokens", 0) or 0
            )
            checkpoint_triggered = progress_detector.feed(
                str(output.new_text or ""),
                completion_tokens=completion_tokens,
                finished=bool(getattr(output, "finished", False)),
            )
            if output.new_text:
                self._draft_parts.append(str(output.new_text))
                yield DraftChunk(
                    text=output.new_text,
                    token_count=completion_tokens,
                    signals=GateSignals(
                        output_tokens=completion_tokens,
                        extra={
                            "thinking_tokens": progress_detector.thinking_tokens
                        },
                    ),
                )
            if detector is not None and checkpoint_triggered:
                finish_reason = str(
                    getattr(output, "finish_reason", "checkpoint") or "checkpoint"
                )
                is_finished = bool(getattr(output, "finished", False))
                self._checkpoint_tokens = completion_tokens
                self._finished = is_finished
                yield DraftChunk(
                    token_count=completion_tokens,
                    finished=is_finished,
                    finish_reason=finish_reason,
                    signals=GateSignals(
                        output_tokens=completion_tokens,
                        finish_reason=finish_reason,
                        extra=self._cache_metrics(
                            thinking_tokens=detector.thinking_tokens
                        ),
                    ),
                    checkpoint=True,
                    checkpoint_reason="thinking",
                )
                return
        completion_tokens = int(getattr(last, "completion_tokens", 0) or 0)
        finish_reason = str(getattr(last, "finish_reason", "stop") or "stop")
        if will_checkpoint and finish_reason == "length":
            self._checkpoint_tokens = completion_tokens
            yield DraftChunk(
                token_count=completion_tokens,
                finish_reason=finish_reason,
                signals=GateSignals(
                    output_tokens=completion_tokens,
                    finish_reason=finish_reason,
                    extra=self._cache_metrics(),
                ),
                checkpoint=True,
                checkpoint_reason="token_limit",
            )
            return
        self._finished = True
        yield DraftChunk(
            finished=True,
            finish_reason=finish_reason,
            token_count=completion_tokens,
            signals=GateSignals(
                output_tokens=completion_tokens,
                finish_reason=finish_reason,
                extra=self._cache_metrics(),
            ),
        )

    async def resume_from_checkpoint(
        self, draft: str, decision: CheckpointDecision
    ) -> AsyncIterator[DraftChunk]:
        if decision.action == CheckpointAction.CONTINUE:
            remaining = max(1, self.request.max_tokens - self._checkpoint_tokens)
            messages = [dict(message) for message in self.request.messages]
            messages.append({"role": "assistant", "content": draft})
            is_partial = True
        elif decision.action == CheckpointAction.REDIRECT:
            remaining = self.request.max_tokens
            messages = build_redirect_messages(self.request.messages, draft, decision)
            is_partial = False
        elif decision.action == CheckpointAction.REASONING_HANDOFF:
            remaining = self.request.max_tokens
            messages = build_reasoning_handoff_messages(
                self.request.messages, draft, decision
            )
            is_partial = False
        else:
            raise ValueError("ABORT checkpoint decision cannot resume generation")

        last = None
        async for output in self._stream_segment(
            messages,
            max_tokens=remaining,
            is_partial=is_partial,
        ):
            last = output
            if output.new_text:
                completion_tokens = int(
                    getattr(output, "completion_tokens", 0) or 0
                )
                yield DraftChunk(
                    text=output.new_text,
                    token_count=(
                        completion_tokens + self._checkpoint_tokens
                        if decision.action == CheckpointAction.CONTINUE
                        else completion_tokens
                    ),
                )
        self._finished = True
        completion_tokens = int(getattr(last, "completion_tokens", 0) or 0)
        if decision.action == CheckpointAction.CONTINUE:
            completion_tokens += self._checkpoint_tokens
        finish_reason = str(getattr(last, "finish_reason", "stop") or "stop")
        yield DraftChunk(
            finished=True,
            finish_reason=finish_reason,
            token_count=completion_tokens,
            signals=GateSignals(
                output_tokens=completion_tokens,
                finish_reason=finish_reason,
                extra=self._cache_metrics(),
            ),
        )

    async def revise(
        self, draft: str, decision: ReviewDecision
    ) -> tuple[StructuredPatch, ...]:
        output = await self.engine.chat(
            messages=build_revision_messages(
                self.request.messages, draft, _sha256(draft), decision
            ),
            max_tokens=min(self.request.max_tokens, 512),
            temperature=0.0,
            top_p=1.0,
            **self._cache_runtime_kwargs(),
        )
        text = str(getattr(output, "text", ""))
        try:
            payload = json.loads(_strip_json_fence(text))
        except json.JSONDecodeError as exc:
            raise ValueError("generator revision is not valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("generator revision must be a JSON object")
        value = dict(payload)
        value.setdefault("action", "patch")
        parsed = review_decision_from_mapping(
            value, base_sha256=_sha256(draft)
        )
        if parsed.action != ReviewAction.PATCH:
            raise ValueError("generator revision must contain PATCH operations")
        return parsed.patches

    async def replan_tool_calls(
        self, draft: str, decision: ToolReviewDecision
    ) -> AsyncIterator[DraftChunk]:
        async for chunk in self._stream_tool_candidate(
            build_tool_replan_messages(self.request.messages, draft, decision),
            max_tokens=self.request.max_tokens,
        ):
            yield chunk

    async def realize(self, draft: str, blueprint: Mapping[str, object]) -> str:
        sampling = dict(self.request.sampling)
        sampling.pop("max_tokens", None)
        sampling.pop("fusion_reviewer_l1_mode", None)
        sampling.pop("fusion_reviewer_boost_mode", None)
        sampling.pop("fusion_reviewer_prefill_boost_mode", None)
        sampling.pop("fusion_reviewer_decode_boost_mode", None)
        sampling.setdefault("flesh_session_id", self.request.session_id)
        sampling.setdefault("skip_cache_store", True)
        output = await self.engine.chat(
            messages=build_realization_messages(self.request.messages, blueprint),
            max_tokens=self.request.max_tokens,
            **sampling,
        )
        return str(getattr(output, "text", ""))

    async def commit_draft(self) -> None:
        if self.continuity is not None:
            raw_draft = "".join(self._draft_parts)
            history_draft = self._history_content(raw_draft)
            _, visible_draft = extract_thinking(raw_draft)
            covered = [dict(message) for message in self._covered_conversation]
            covered.append(
                {"role": "assistant", "content": visible_draft.strip()}
            )
            prompt_messages = [dict(message) for message in self.request.messages]
            prompt_messages.append(
                {"role": "assistant", "content": history_draft}
            )
            self.continuity.commit_pass(
                self.request.session_id,
                prompt_messages=prompt_messages,
                covered_conversation=covered,
            )

    async def commit_final(self, text: str) -> None:
        del text
        if self.continuity is not None:
            self.continuity.require_compaction(self.request.session_id)

    async def abort(self) -> None:
        return None


class OMLXGeneratorBackend:
    def __init__(self, engine: Any):
        self.engine = engine
        self._compact_sessions: set[str] = set()
        self._pass_states: dict[str, _GeneratorPassState] = {}
        self.pass_commits = 0
        self.compact_rebases = 0

    @staticmethod
    def _compact_messages(
        messages: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        compacted: list[dict[str, Any]] = []
        for source in messages:
            message = dict(source)
            if message.get("role") == "assistant":
                message.pop("reasoning_content", None)
                message.pop("reasoning", None)
                message.pop("thinking", None)
                message.pop("_thinking", None)
                content = message.get("content")
                if isinstance(content, str) and "</think>" in content:
                    _, regular = extract_thinking(content)
                    message["content"] = regular.lstrip()
            compacted.append(message)
        return compacted

    def commit_pass(
        self,
        session_id: str,
        *,
        prompt_messages: Sequence[Mapping[str, Any]],
        covered_conversation: Sequence[Mapping[str, Any]],
    ) -> None:
        self._compact_sessions.discard(session_id)
        self._pass_states[session_id] = _GeneratorPassState(
            prompt_messages=[dict(message) for message in prompt_messages],
            covered_conversation=[
                dict(message) for message in covered_conversation
            ],
        )
        self.pass_commits += 1

    def require_compaction(self, session_id: str) -> None:
        self._pass_states.pop(session_id, None)
        self._compact_sessions.add(session_id)

    def stats(self) -> dict[str, Any]:
        return {
            "policy": "adaptive",
            "pass_commits": self.pass_commits,
            "compact_rebases": self.compact_rebases,
            "pending_compactions": len(self._compact_sessions),
        }

    async def begin_turn(self, request: FusionRequest) -> OMLXGeneratorTurn:
        covered_conversation = [dict(message) for message in request.messages]
        if request.session_id in self._compact_sessions:
            self._compact_sessions.remove(request.session_id)
            request = replace(
                request,
                messages=self._compact_messages(request.messages),
            )
            self.compact_rebases += 1
        else:
            state = self._pass_states.get(request.session_id)
            if state is not None and covered_conversation[
                : len(state.covered_conversation)
            ] == state.covered_conversation:
                delta = covered_conversation[len(state.covered_conversation) :]
                request = replace(
                    request,
                    messages=[
                        *[dict(message) for message in state.prompt_messages],
                        *[dict(message) for message in delta],
                    ],
                )
            elif state is not None:
                self._pass_states.pop(request.session_id, None)
        return OMLXGeneratorTurn(
            self.engine,
            request,
            self,
            covered_conversation=covered_conversation,
        )


class OMLXReviewerBackend:
    """Use a loaded local oMLX engine as a constrained reviewer."""

    # Local reviews enforce their own inactivity timeout while consuming the
    # token stream.  The orchestrator must not wrap them in a fixed wall-clock
    # timeout, otherwise a healthy long-running review is cancelled mid-output.
    manages_inactivity_timeout = True

    class OutputError(ValueError):
        """A public reviewer decision could not be parsed."""

        def __init__(self, cause: Exception, transcript: Mapping[str, Any]):
            super().__init__(str(cause))
            self.error_type = type(cause).__name__
            self.transcript = dict(transcript)

    def __init__(
        self,
        engine: Any,
        *,
        max_tokens: int = 8192,
        checkpoint_max_tokens: int = 256,
        inactivity_timeout_seconds: float = 30.0,
        cache_moe_defaults: Mapping[str, Any] | None = None,
    ):
        if inactivity_timeout_seconds <= 0:
            raise ValueError("reviewer inactivity timeout must be positive")
        self.engine = engine
        self.max_tokens = max_tokens
        self.checkpoint_max_tokens = checkpoint_max_tokens
        self.inactivity_timeout_seconds = inactivity_timeout_seconds
        self.cache_moe_defaults = dict(cache_moe_defaults or {})
        self._review_pass_states: dict[str, _ReviewerPassState] = {}
        self._review_pass_epochs: dict[str, int] = {}
        self._review_pass_locks: dict[str, asyncio.Lock] = {}
        self._decision_grammars: dict[bool, Any] = {}
        self._decision_grammar_attempted: set[bool] = set()

    def _get_decision_grammar(self, *, reasoning: bool) -> Any | None:
        """Compile JSON output grammar, including the model's think channel."""
        if reasoning in self._decision_grammar_attempted:
            return self._decision_grammars.get(reasoning)
        self._decision_grammar_attempted.add(reasoning)
        compiler = getattr(self.engine, "grammar_compiler", None)
        if compiler is None:
            return None
        try:
            if not reasoning:
                grammar = compiler.compile_builtin_json_grammar()
            else:
                model_type = str(getattr(self.engine, "model_type", "") or "")
                if model_type in {"deepseek_v4", "deepseek_v4_mtp"}:
                    reasoning_parser = "deepseek_v4"
                elif "deepseek" in model_type:
                    reasoning_parser = "deepseek_r1"
                elif model_type in {"qwen3_5", "qwen3_5_moe", "qwen3_6"}:
                    reasoning_parser = "qwen_3_5"
                else:
                    return None
                # Reuse the serving layer's structural-tag compiler: it keeps
                # the reasoning channel unconstrained, then replaces the
                # public channel with builtin JSON. At a forced </think>, the
                # next valid non-whitespace token is therefore '{'.
                from omlx.server import _compile_with_structural_tag

                grammar = _compile_with_structural_tag(
                    compiler,
                    {"type": "json_schema", "json_schema": {}},
                    reasoning_parser,
                    {"enable_thinking": True},
                )
            self._decision_grammars[reasoning] = grammar
            return grammar
        except Exception:
            return None

    def _runtime_kwargs(self, request: FusionRequest, phase: str) -> dict[str, Any]:
        legacy_override = request.sampling.get("fusion_reviewer_boost_mode")
        legacy_default = self.cache_moe_defaults.get("engine_boost", "natural")
        values = {
            "flesh_l1_mode": request.sampling.get(
                "fusion_reviewer_l1_mode",
                self.cache_moe_defaults.get("l1_mode", "auto"),
            ),
            "flesh_prefill_boost_mode": request.sampling.get(
                "fusion_reviewer_prefill_boost_mode",
                legacy_override
                or self.cache_moe_defaults.get("prefill_boost", legacy_default),
            ),
            "flesh_decode_boost_mode": request.sampling.get(
                "fusion_reviewer_decode_boost_mode",
                legacy_override
                or self.cache_moe_defaults.get("decode_boost", legacy_default),
            ),
        }
        values["flesh_session_id"] = f"fusion-{phase}:{request.session_id}"
        # Final PASS reviews form an append-only transcript. Checkpoint/tool
        # reviews still replace their payload and therefore remain strict.
        values["flesh_kv_policy"] = (
            "session" if phase.startswith("review-pass-") else "strict"
        )
        values["skip_cache_store"] = False
        values["cache_exact_system_prefix"] = True
        return values

    def _reset_review_pass_state(self, session_id: str) -> int:
        self._review_pass_states.pop(session_id, None)
        epoch = self._review_pass_epochs.get(session_id, 0) + 1
        self._review_pass_epochs[session_id] = epoch
        return epoch

    def _build_append_only_review_messages(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, object]], int, int]:
        conversation = reviewable_messages(request.messages)
        state = self._review_pass_states.get(request.session_id)
        if state is not None and conversation[: len(state.covered_conversation)] == (
            state.covered_conversation
        ):
            delta = conversation[len(state.covered_conversation) :]
            messages = [dict(message) for message in state.prompt_messages]
            messages.append(
                {
                    "role": "user",
                    "content": build_review_jsonl(delta, draft, draft_sha256),
                }
            )
            return messages, conversation, state.epoch, len(state.prompt_messages)

        if state is not None:
            epoch = self._reset_review_pass_state(request.session_id)
        else:
            epoch = self._review_pass_epochs.get(request.session_id, 0)
        return (
            build_review_messages(request.messages, draft, draft_sha256),
            conversation,
            epoch,
            0,
        )

    async def _stream_text(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        request: FusionRequest,
        phase: str,
        progress: Callable[[Mapping[str, Any]], None] | None = None,
        exact_message_prefix_count: int = 0,
        thinking_budget: int | None = None,
        chat_template_kwargs: Mapping[str, Any] | None = None,
        compiled_grammar: Any | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Collect a local review while timing out only on stalled progress."""

        review_request_id = f"fusion-review-{uuid.uuid4().hex}"
        runtime_kwargs = self._runtime_kwargs(request, phase)
        if exact_message_prefix_count > 0:
            runtime_kwargs["cache_exact_message_prefix_count"] = (
                exact_message_prefix_count
            )
        stream = self.engine.stream_chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.0,
            top_p=1.0,
            # A structured reviewer must leave room for its public JSON
            # decision. Without a bounded thinking phase, reasoning models can
            # consume the whole response budget and finish with no parseable
            # output even though token generation remained healthy.
            # The main reviewer must finish its audit before committing a
            # decision. A forced </think> made incomplete reviews collapse to
            # plausible-looking PASS JSON. None lets the model end reasoning
            # naturally; the structural grammar constrains only what follows.
            thinking_budget=thinking_budget,
            request_id=review_request_id,
            **(
                {"chat_template_kwargs": dict(chat_template_kwargs)}
                if chat_template_kwargs is not None
                else {}
            ),
            **(
                {"compiled_grammar": compiled_grammar}
                if compiled_grammar is not None
                else {}
            ),
            **runtime_kwargs,
        ).__aiter__()
        parts: list[str] = []
        last_output: Any = None
        last_tokens = 0
        last_progress = time.monotonic()
        started = last_progress
        prefill_done = asyncio.Event()
        protocol_drift = False

        def report(metadata: Mapping[str, Any]) -> None:
            if progress is not None:
                progress(dict(metadata))

        report(
            {
                "stage": "prefill",
                "request_id": review_request_id,
                "prompt_messages": [dict(message) for message in messages],
                "processed": 0,
                "total": 0,
                "elapsed": 0.0,
            }
        )

        async def poll_prefill() -> None:
            nonlocal last_progress
            from omlx.prefill_progress import get_prefill_tracker

            tracker = get_prefill_tracker()
            last_snapshot: tuple[int, int, float] | None = None
            while not prefill_done.is_set():
                entry = tracker.get_request_progress(review_request_id)
                if entry is not None:
                    snapshot = (
                        int(entry.get("processed", 0) or 0),
                        int(entry.get("total", 0) or 0),
                        float(entry.get("speed", 0) or 0),
                    )
                    if snapshot != last_snapshot:
                        last_snapshot = snapshot
                        last_progress = time.monotonic()
                        report({"stage": "prefill", **entry})
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(prefill_done.wait(), timeout=0.25)

        prefill_task = asyncio.create_task(poll_prefill())

        try:
            while True:
                next_output = asyncio.create_task(stream.__anext__())
                try:
                    while not next_output.done():
                        remaining = self.inactivity_timeout_seconds - (
                            time.monotonic() - last_progress
                        )
                        if remaining <= 0:
                            next_output.cancel()
                            await asyncio.gather(next_output, return_exceptions=True)
                            raise TimeoutError("local reviewer made no token progress")
                        await asyncio.wait({next_output}, timeout=min(0.25, remaining))
                    output = await next_output
                except StopAsyncIteration:
                    break

                prefill_done.set()
                last_output = output
                new_text = str(getattr(output, "new_text", "") or "")
                completion_tokens = int(getattr(output, "completion_tokens", 0) or 0)
                if new_text:
                    parts.append(new_text)
                if new_text or completion_tokens > last_tokens:
                    last_progress = time.monotonic()
                    report(
                        {
                            "stage": "generating",
                            "request_id": review_request_id,
                            "delta": new_text,
                            "tokens": completion_tokens,
                            "duration_seconds": round(time.monotonic() - started, 3),
                            "prompt_tokens": int(
                                getattr(output, "prompt_tokens", 0) or 0
                            ),
                        }
                    )
                last_tokens = max(last_tokens, completion_tokens)
                combined = "".join(parts)
                if "</think>" in combined:
                    public_tail = combined.rsplit("</think>", 1)[1].lstrip()
                    # thinking_budget can force the closing tag without
                    # changing the model's intent. Stop at the first public
                    # prose token instead of letting analysis consume the
                    # entire output budget. JSON and a legacy JSON fence are
                    # the only valid starts after the boundary.
                    if public_tail and public_tail[0] not in "{`":
                        protocol_drift = True
                        report(
                            {
                                "stage": "decision_retry",
                                "request_id": review_request_id,
                                "reason": "non_json_after_thinking_boundary",
                                "tokens": completion_tokens,
                            }
                        )
                        aclose = getattr(stream, "aclose", None)
                        if callable(aclose):
                            with contextlib.suppress(Exception):
                                await aclose()
                        break
        finally:
            prefill_done.set()
            await prefill_task

        text = "".join(parts)
        if not text and last_output is not None:
            text = str(getattr(last_output, "text", "") or "")
        return text, {
            "output": text,
            "tokens": last_tokens,
            "duration_seconds": round(time.monotonic() - started, 3),
            "request_id": review_request_id,
            "protocol_drift": protocol_drift,
            "finish_reason": str(
                getattr(last_output, "finish_reason", "") or ""
            ),
        }

    async def review_tool_calls(
        self,
        request: FusionRequest,
        draft: str,
        tool_calls: tuple[FusionToolCall, ...],
        validation_errors: tuple[str, ...],
        *,
        final: bool = False,
    ) -> ToolReviewDecision:
        text, _ = await self._stream_text(
            build_tool_review_messages(
                request.messages,
                request.tools,
                draft,
                tool_calls,
                validation_errors,
                final=final,
            ),
            max_tokens=self.checkpoint_max_tokens,
            request=request,
            phase="tool-review",
            thinking_budget=max(
                32, min(self.checkpoint_max_tokens // 2, 128)
            ),
        )
        return tool_review_decision_from_json(text)

    async def review_checkpoint(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> CheckpointDecision:
        text, _ = await self._stream_text(
            build_checkpoint_review_messages(
                request.messages,
                draft,
                draft_sha256,
                allow_reasoning_handoff=(
                    request.metadata.get("reviewer_guidance_mode")
                    == "reasoning_handoff"
                ),
                reasoning_handoff_max_tokens=int(
                    request.metadata.get("reasoning_handoff_max_tokens", 256)
                ),
            ),
            max_tokens=self.checkpoint_max_tokens,
            request=request,
            phase="checkpoint",
            thinking_budget=max(
                32, min(self.checkpoint_max_tokens // 2, 128)
            ),
        )
        return checkpoint_decision_from_json(text)

    async def review(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> ReviewDecision:
        return await self._review(request, draft, draft_sha256, progress=None)

    async def review_with_progress(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
        progress: Callable[[Mapping[str, Any]], None],
    ) -> ReviewDecision:
        return await self._review(request, draft, draft_sha256, progress=progress)

    async def _review(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        *,
        progress: Callable[[Mapping[str, Any]], None] | None,
    ) -> ReviewDecision:
        lock = self._review_pass_locks.setdefault(request.session_id, asyncio.Lock())
        async with lock:
            (
                messages,
                conversation,
                epoch,
                exact_message_prefix_count,
            ) = self._build_append_only_review_messages(
                request, draft, draft_sha256
            )
            try:
                text, transcript = await self._stream_text(
                    messages,
                    max_tokens=self.max_tokens,
                    request=request,
                    phase=f"review-pass-{epoch}",
                    progress=progress,
                    exact_message_prefix_count=exact_message_prefix_count,
                    compiled_grammar=self._get_decision_grammar(reasoning=True),
                )
                try:
                    decision = review_decision_from_json(
                        text, base_sha256=draft_sha256
                    )
                except ValueError as parse_error:
                    # Never turn incomplete reasoning into a plausible-looking
                    # decision.  A model that exhausted its budget before a
                    # natural </think> has not finished auditing, so forcing a
                    # JSON-only continuation can incorrectly collapse real
                    # defects into PASS.  Retry only after a completed analysis
                    # whose public decision channel drifted from JSON.
                    if (
                        "</think>" not in text
                        or transcript.get("finish_reason") == "length"
                    ):
                        raise parse_error
                    initial_output = text
                    retry_messages = [
                        *[dict(message) for message in messages],
                        {"role": "assistant", "content": initial_output},
                        {"role": "user", "content": REVIEW_DECISION_RETRY_PROMPT},
                    ]
                    retry_text, retry_transcript = await self._stream_text(
                        retry_messages,
                        max_tokens=384,
                        request=request,
                        phase=f"review-decision-retry-{epoch}",
                        progress=progress,
                        thinking_budget=0,
                        chat_template_kwargs={
                            "enable_thinking": False,
                            "preserve_thinking": True,
                        },
                        compiled_grammar=self._get_decision_grammar(reasoning=False),
                    )
                    decision = review_decision_from_json(
                        retry_text, base_sha256=draft_sha256
                    )
                    messages = retry_messages
                    text = retry_text
                    transcript = {
                        **retry_transcript,
                        "decision_retry": True,
                        "initial_output": initial_output,
                    }
            except Exception as exc:
                if isinstance(exc, self.OutputError):
                    raise
                if "transcript" in locals():
                    raise self.OutputError(exc, transcript) from exc
                raise

            if decision.action == ReviewAction.PASS:
                _, visible_draft = extract_thinking(draft)
                covered = [dict(message) for message in conversation]
                covered.append(
                    {"role": "assistant", "content": visible_draft.strip()}
                )
                committed_messages = [dict(message) for message in messages]
                # Keep the exact generated transcript, including any bounded
                # reviewer reasoning, so the next rendered prompt is a true
                # token-prefix extension and can restore the complete KV.
                committed_messages.append({"role": "assistant", "content": text})
                self._review_pass_states[request.session_id] = _ReviewerPassState(
                    prompt_messages=committed_messages,
                    covered_conversation=covered,
                    epoch=epoch,
                )
            return replace(
                decision,
                metadata={
                    **dict(decision.metadata),
                    "reviewer_transcript": transcript,
                },
            )

    async def resolve(
        self,
        request: FusionRequest,
        draft: str,
        review: ReviewDecision,
    ) -> ReviewDecision:
        messages = build_review_messages(request.messages, draft, _sha256(draft))
        messages[0]["content"] += (
            "\nYou are the final resolver. Prefer PATCH; otherwise return "
            "ESCALATE with a short authoritative blueprint."
        )
        messages[1]["content"] += "\nLocal review:\n" + json.dumps(
            {
                "summary": review.summary,
                "risk": review.risk,
                "confidence": review.confidence,
                "blueprint": dict(review.blueprint),
            },
            ensure_ascii=False,
        )
        text, _ = await self._stream_text(
            messages,
            max_tokens=self.max_tokens,
            request=request,
            phase="resolve",
        )
        return review_decision_from_json(
            text, base_sha256=_sha256(draft)
        )


class OpenAICompatibleReviewBackend:
    """Remote reviewer/resolver adapter with no persistent credential storage."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        max_tokens: int = 768,
        checkpoint_max_tokens: int = 256,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
    ):
        if not base_url or not model or not api_key:
            raise ValueError(
                "remote Fusion backend requires base_url, model, and api_key"
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.checkpoint_max_tokens = checkpoint_max_tokens
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._owns_client = client is None

    async def _chat_content(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
    ) -> tuple[str, Mapping[str, Any]]:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        token_limit = max_tokens or self.max_tokens
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": token_limit,
            "response_format": {"type": "json_object"},
        }
        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        # GPT-5-class Chat Completions endpoints reject the legacy
        # ``max_tokens`` field and do not accept temperature overrides.  Keep
        # the generic request first for third-party OpenAI-compatible servers,
        # then retry the modern spelling when the upstream rejects it.
        if int(getattr(response, "status_code", 200)) == 400:
            modern_payload = dict(payload)
            modern_payload.pop("temperature", None)
            modern_payload.pop("max_tokens", None)
            modern_payload["max_completion_tokens"] = token_limit
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=modern_payload,
            )
        if bool(getattr(response, "is_error", False)):
            detail = ""
            try:
                body = response.json()
                error = body.get("error", {}) if isinstance(body, Mapping) else {}
                detail = str(
                    error.get("message", "")
                    if isinstance(error, Mapping)
                    else error
                )
            except (ValueError, TypeError):
                detail = str(getattr(response, "text", ""))
            detail = detail.replace(self.api_key, "[redacted]").strip()[:1000]
            raise RuntimeError(
                f"external reviewer HTTP {getattr(response, 'status_code', 'error')}"
                + (f": {detail}" if detail else "")
            )
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("remote Fusion response has no assistant content") from exc
        usage = payload.get("usage", {}) if isinstance(payload, Mapping) else {}
        return str(content), usage if isinstance(usage, Mapping) else {}

    async def _complete(
        self,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int | None = None,
        base_sha256: str | None = None,
    ) -> ReviewDecision:
        content, usage = await self._chat_content(
            messages, max_tokens=max_tokens
        )
        decision = review_decision_from_json(
            content, base_sha256=base_sha256
        )
        return replace(
            decision,
            metadata={
                **dict(decision.metadata),
                "reviewer_transcript": {
                    "output": content,
                    "tokens": int(usage.get("completion_tokens", 0) or 0),
                    "duration_seconds": 0,
                    "source": "external",
                },
            },
        )

    async def review_and_repair(
        self,
        request: FusionRequest,
        draft: str,
        *,
        max_tokens: int | None = None,
    ) -> tuple[
        str,
        str,
        Mapping[str, Any],
        list[dict[str, Any]],
        str,
        str,
    ]:
        """Run an explicit cloud review and return a corrected full answer."""

        conversation = reviewable_messages(request.messages)
        _, visible_draft = extract_thinking(draft)

        system = (
            "You are an external reviewer for an already generated answer. "
            "Check factual, logical, computational, code, and explicit-request "
            "errors. Return exactly one JSON object and no prose. If the answer "
            "is deliverable return {\"action\":\"PASS\"}. If any defect exists, "
            "return {\"action\":\"REPLACE\",\"explanation\":\"a concise, specific "
            "description of the defects and corrections\",\"answer\":\"the complete "
            "corrected answer\"}. The explanation is required for REPLACE and should "
            "help the user decide whether to apply it. Preserve all correct material "
            "and repair every defect."
        )
        prompt_messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "conversation": conversation,
                        "answer": visible_draft.strip(),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        content, usage = await self._chat_content(
            prompt_messages,
            max_tokens=max_tokens or self.max_tokens,
        )
        try:
            value = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError as exc:
            raise ValueError("external review is not valid JSON") from exc
        if not isinstance(value, Mapping):
            raise ValueError("external review must return a JSON object")
        action = str(value.get("action", "")).upper()
        if action == "PASS":
            return draft, "pass", usage, prompt_messages, content, ""
        if action != "REPLACE":
            raise ValueError("external review action must be PASS or REPLACE")
        answer = value.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("external REPLACE review has no corrected answer")
        explanation = value.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            raise ValueError("external REPLACE review has no explanation")
        return (
            answer,
            "replace",
            usage,
            prompt_messages,
            content,
            explanation.strip(),
        )

    async def review_checkpoint(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> CheckpointDecision:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": build_checkpoint_review_messages(
                    request.messages,
                    draft,
                    draft_sha256,
                    allow_reasoning_handoff=(
                        request.metadata.get("reviewer_guidance_mode")
                        == "reasoning_handoff"
                    ),
                    reasoning_handoff_max_tokens=int(
                        request.metadata.get("reasoning_handoff_max_tokens", 256)
                    ),
                ),
                "temperature": 0,
                "max_tokens": self.checkpoint_max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(
                "remote Fusion checkpoint response has no assistant content"
            ) from exc
        return checkpoint_decision_from_json(str(content))

    async def review_tool_calls(
        self,
        request: FusionRequest,
        draft: str,
        tool_calls: tuple[FusionToolCall, ...],
        validation_errors: tuple[str, ...],
        *,
        final: bool = False,
    ) -> ToolReviewDecision:
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": build_tool_review_messages(
                    request.messages,
                    request.tools,
                    draft,
                    tool_calls,
                    validation_errors,
                    final=final,
                ),
                "temperature": 0,
                "max_tokens": self.checkpoint_max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("remote Fusion tool review has no content") from exc
        return tool_review_decision_from_json(str(content))

    async def review(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> ReviewDecision:
        return await self._complete(
            build_review_messages(request.messages, draft, draft_sha256),
            base_sha256=draft_sha256,
        )

    async def resolve(
        self,
        request: FusionRequest,
        draft: str,
        review: ReviewDecision,
    ) -> ReviewDecision:
        payload = {
            "conversation": list(request.messages),
            "draft": draft,
            "local_review": {
                "summary": review.summary,
                "risk": review.risk,
                "confidence": review.confidence,
                "blueprint": dict(review.blueprint),
            },
        }
        system = (
            REVIEW_SYSTEM_PROMPT
            + "\nYou are the final resolver. Prefer a minimal PATCH. If the core "
            "solution must change, return ESCALATE with an authoritative short "
            "blueprint."
        )
        return await self._complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            base_sha256=_sha256(draft),
        )

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        first_newline = stripped.find("\n")
        if first_newline >= 0:
            return stripped[first_newline + 1 : -3].strip()
    return stripped


def _sha256(text: str) -> str:
    from .patching import text_sha256

    return text_sha256(text)
