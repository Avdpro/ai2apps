"""Built-in resumable model -> Tool -> model Agent executor."""

from __future__ import annotations

import asyncio
import copy
import fnmatch
import hashlib
import json
import re
from typing import Any

from ai2apps.core import MessageRole, MessageStatus, ResourceNotFoundError
from ai2apps.events import EventStore
from ai2apps.services import ToolDescriptorRecord, ToolGateway
from ai2apps.storage import MessagePartInput, PlatformDatabase
from ai2apps.storage.repositories import MessageRepository

from .models import (
    AgentAction,
    AgentExecutionContext,
    CompleteAction,
    FailAction,
    ModelCallAction,
    RunStepRecord,
    RunStepStatus,
    ToolCallAction,
)
from .repository import AgentRepository
from .runtime import AgentRuntime

_SAFE_TOOL_NAME = re.compile(r"[^A-Za-z0-9_-]")
_MODEL_OPTION_KEYS = frozenset(
    {
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "reasoning_effort",
        "seed",
        "stop",
    }
)


def _tool_alias(name: str) -> str:
    alias = _SAFE_TOOL_NAME.sub("__", name).strip("_") or "tool"
    if alias != name or len(alias) > 64:
        digest = hashlib.sha256(name.encode()).hexdigest()[:10]
        alias = f"{alias[:53]}_{digest}"
    return alias


def _provider_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return an OpenAI-compatible function schema without weakening execution validation.

    Providers reject composition keywords at the function parameters root even
    when the schema is otherwise a valid object schema. The Tool gateway still
    validates calls against the original schema before execution.
    """

    normalized = copy.deepcopy(schema)
    normalized["type"] = "object"
    for keyword in ("oneOf", "anyOf", "allOf", "enum", "const", "not"):
        normalized.pop(keyword, None)
    return normalized


def _tool_catalog(tools: tuple[ToolDescriptorRecord, ...]):
    aliases: dict[str, ToolDescriptorRecord] = {}
    definitions = []
    for tool in sorted(tools, key=lambda item: item.qualified_name):
        alias = _tool_alias(tool.qualified_name)
        owner = aliases.get(alias)
        if owner is not None and owner.qualified_name != tool.qualified_name:
            digest = hashlib.sha256(tool.qualified_name.encode()).hexdigest()[:10]
            alias = f"{alias[:53]}_{digest}"
        aliases[alias] = tool
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": alias,
                    "description": tool.description or tool.display_name,
                    "parameters": _provider_tool_schema(tool.input_schema),
                },
            }
        )
    return aliases, definitions


def _part_content(kind: str, content: dict[str, Any]):
    if kind == "text":
        return content.get("text", "")
    if kind in {"openai_content", "chat_ui_content"}:
        return content.get("content")
    return json.dumps(content, ensure_ascii=False, sort_keys=True)


def _normalize_attachment_references(value):
    """Keep durable IDs in history without sending unresolved files to providers."""
    if not isinstance(value, list):
        return value
    normalized = []
    for part in value:
        if not isinstance(part, dict) or part.get("type") != "file":
            normalized.append(part)
            continue
        file_value = part.get("file") or {}
        attachment_id = file_value.get("file_id") or file_value.get("attachment_id")
        if not attachment_id:
            normalized.append(part)
            continue
        filename = file_value.get("filename") or "document"
        normalized.append(
            {
                "type": "text",
                "text": (
                    f"[Attached document: {filename}; attachment_id={attachment_id}. "
                    "Use attachment.status, document.read, or document.search to inspect it.]"
                ),
            }
        )
    return normalized


def _session_message(record) -> dict[str, Any] | None:
    if record.message.status is not MessageStatus.COMPLETED:
        return None
    role = record.message.role
    if role is MessageRole.APP:
        role = MessageRole.USER
    contents = [_part_content(part.kind, part.content) for part in record.parts]
    if len(contents) == 1:
        content = _normalize_attachment_references(contents[0])
    else:
        text_parts = [item for item in contents if isinstance(item, str)]
        content = (
            "\n".join(text_parts) if len(text_parts) == len(contents) else _normalize_attachment_references(contents)
        )
    return {"role": role.value, "content": content}


def _model_message(output: dict[str, Any]):
    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, None, "Model response has no choices"
    choice = choices[0]
    if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
        return None, None, "Model response choice has no message"
    message = choice["message"]
    tool_calls = message.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        return None, None, "Model response tool_calls must be an array"
    return message, choice.get("finish_reason"), None


def _tool_action_key(model_sequence: int, index: int, call_id: str) -> str:
    digest = hashlib.sha256(call_id.encode()).hexdigest()[:12]
    return f"tool:{model_sequence}:{index}:{digest}"


class GeneralAgentExecutor:
    """Reconstruct execution from durable Messages and Steps on every turn."""

    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore,
        tools: ToolGateway,
    ) -> None:
        self.messages = MessageRepository(database, events)
        self.tools = tools

    def _messages_for_run(self, context: AgentExecutionContext):
        records = self.messages.list_for_session(context.run.session_id, limit=1_000)
        delegated = context.run.parent_run_id is not None
        requested_message_id = context.run.input.get("message_id")
        if requested_message_id is not None:
            try:
                requested = self.messages.get(
                    requested_message_id,
                    session_id=context.run.session_id,
                )
            except ResourceNotFoundError:
                return None, "input_message_not_found"
            if requested.message.role is not MessageRole.USER:
                return None, "input_message_must_be_user"
            cutoff = requested.message.sequence
        elif delegated:
            parent_message_id = context.run.delegation.get("context", {}).get(
                "parent_message_id"
            )
            parent_message = next(
                (
                    item
                    for item in records
                    if item.message.id == parent_message_id
                ),
                None,
            )
            cutoff = (
                parent_message.message.sequence
                if parent_message is not None
                else (records[-1].message.sequence if records else 0)
            )
        else:
            generated_input = next(
                (
                    item
                    for item in records
                    if item.message.metadata.get("agent_run_id") == context.run.id
                    and item.message.metadata.get("agent_input")
                ),
                None,
            )
            if generated_input is None:
                return None, "missing_agent_input"
            cutoff = generated_input.message.sequence
        messages = []
        instructions = context.definition.manifest.get("instructions")
        if isinstance(instructions, str) and instructions:
            messages.append({"role": "system", "content": instructions})
        run_instructions = context.run.input.get("instructions")
        if isinstance(run_instructions, str) and run_instructions.strip():
            messages.append({"role": "system", "content": run_instructions})
        eligible = []
        for item in records:
            if item.message.sequence > cutoff:
                continue
            if item.message.metadata.get(
                "agent_run_id"
            ) == context.run.id and not item.message.metadata.get("agent_input"):
                continue
            converted = _session_message(item)
            if converted is not None:
                eligible.append(converted)
        configured_limit = context.definition.manifest.get("context_message_limit", 200)
        message_limit = (
            configured_limit
            if isinstance(configured_limit, int) and configured_limit > 0
            else 200
        )
        omitted = max(0, len(eligible) - message_limit)
        if omitted:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"{omitted} earlier Session messages were omitted by the "
                        "Agent context limit."
                    ),
                }
            )
        messages.extend(eligible[-message_limit:])
        if delegated:
            task = context.run.delegation.get("task") or context.run.input.get("prompt")
            messages.append({"role": "user", "content": str(task)})
        return messages, None

    def _ensure_prompt(self, context: AgentExecutionContext):
        prompt = context.run.input.get("prompt")
        rich_content = context.run.input.get("content")
        supplied = sum(
            value is not None
            for value in (context.run.input.get("message_id"), prompt, rich_content)
        )
        if supplied > 1:
            return "ambiguous_agent_input"
        if context.run.input.get("message_id") is not None:
            return None
        if prompt is None and rich_content is None:
            return "missing_agent_input"
        if prompt is not None and (not isinstance(prompt, str) or not prompt.strip()):
            return "prompt_must_be_non_empty_text"
        if rich_content is not None and (
            not isinstance(rich_content, list) or not rich_content
        ):
            return "content_must_be_non_empty_array"
        if context.run.parent_run_id is not None:
            return None
        part = (
            MessagePartInput(kind="text", content={"text": prompt})
            if prompt is not None
            else MessagePartInput(
                kind="openai_content",
                content={"content": rich_content},
            )
        )
        self.messages.append(
            session_id=context.run.session_id,
            role=MessageRole.USER,
            parts=(part,),
            idempotency_key=f"agent-run:{context.run.id}:user",
            metadata={"agent_run_id": context.run.id, "agent_input": True},
            trace_id=context.run.id,
        )
        # The generated input is part of context, unlike a generated assistant
        # result, so callers on the next pass address it explicitly.
        return None

    def _available_tools(self, context: AgentExecutionContext):
        candidates = self.tools.list_tools(
            self.tools.context_for_session(
                caller_id=f"agent:{context.definition.agent_key}",
                session_id=context.run.session_id,
                granted_capabilities=frozenset(context.run.granted_capabilities),
                trace_id=context.run.id,
            ),
            include_requiring_approval=True,
        )
        patterns = context.definition.manifest.get("allowed_tools", ["*"])
        if not isinstance(patterns, list) or not all(
            isinstance(item, str) for item in patterns
        ):
            return (), "invalid_agent_tool_policy"
        allowed = tuple(
            tool
            for tool in candidates
            if any(
                fnmatch.fnmatchcase(tool.qualified_name, pattern)
                for pattern in patterns
            )
        )
        requested = context.run.input.get("tools")
        if requested is None:
            return allowed, None
        if not isinstance(requested, list) or not all(
            isinstance(item, str) for item in requested
        ):
            return (), "tools_must_be_an_array_of_names"
        by_name = {tool.qualified_name: tool for tool in allowed}
        if any(name not in by_name for name in requested):
            return (), "requested_tool_not_available"
        requested_set = set(requested)
        return tuple(
            tool for tool in allowed if tool.qualified_name in requested_set
        ), None

    @staticmethod
    def _transcript(
        base: list[dict[str, Any]],
        steps: tuple[RunStepRecord, ...],
    ):
        transcript = list(base)
        by_action = {step.action_key: step for step in steps}
        latest_model = None
        for step in steps:
            if step.kind != "model" or step.status is not RunStepStatus.COMPLETED:
                continue
            message, finish_reason, error = _model_message(step.output or {})
            if error is not None:
                return transcript, None, None, error
            latest_model = (step, message, finish_reason)
            assistant = {"role": "assistant", "content": message.get("content")}
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                assistant["tool_calls"] = tool_calls
            transcript.append(assistant)
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    return transcript, latest_model, None, "Malformed model Tool call"
                call_id = call.get("id") or f"call-{index}"
                action_key = _tool_action_key(step.sequence, index, str(call_id))
                tool_step = by_action.get(action_key)
                if tool_step is None or tool_step.status is not RunStepStatus.COMPLETED:
                    continue
                transcript.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call_id),
                        "content": json.dumps(
                            tool_step.output,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    }
                )
        return transcript, latest_model, by_action, None

    @staticmethod
    def _total_model_tokens(steps: tuple[RunStepRecord, ...]) -> int:
        total = 0
        for step in steps:
            if step.kind != "model" or step.status is not RunStepStatus.COMPLETED:
                continue
            usage = (step.output or {}).get("usage")
            if not isinstance(usage, dict):
                continue
            value = usage.get("total_tokens")
            if isinstance(value, int) and value > 0:
                total += value
        return total

    async def __call__(self, context: AgentExecutionContext) -> AgentAction:
        ensured = await asyncio.to_thread(self._ensure_prompt, context)
        if ensured is not None:
            return FailAction(ensured, "Agent prompt must be non-empty text")

        base, base_error = await asyncio.to_thread(self._messages_for_run, context)
        if base_error is not None:
            return FailAction(base_error, "Input Message is not valid for this Run")
        tools, tool_error = await asyncio.to_thread(self._available_tools, context)
        if tool_error is not None:
            return FailAction(tool_error, "Requested Tool selection is invalid")
        aliases, tool_definitions = _tool_catalog(tools)
        transcript, latest, by_action, transcript_error = self._transcript(
            base, context.steps
        )
        if transcript_error is not None:
            return FailAction("invalid_model_response", transcript_error)
        used_tokens = self._total_model_tokens(context.steps)
        configured_budget = context.definition.manifest.get(
            "max_total_model_tokens", 100_000
        )
        token_budget = (
            configured_budget
            if isinstance(configured_budget, int) and configured_budget > 0
            else 100_000
        )
        delegated_budget = context.run.delegation.get("budget", {}).get(
            "max_model_tokens"
        )
        if isinstance(delegated_budget, int) and delegated_budget > 0:
            token_budget = min(token_budget, delegated_budget)
        run_budget = context.run.input.get("run_budget", {}).get("max_model_tokens")
        if isinstance(run_budget, int) and run_budget > 0:
            token_budget = min(token_budget, run_budget)
        if used_tokens > token_budget:
            return FailAction(
                "model_token_budget_exceeded",
                f"Agent model token budget exceeded ({used_tokens}/{token_budget})",
            )

        if latest is not None:
            model_step, message, finish_reason = latest
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return await asyncio.to_thread(
                    self._complete, context, message, finish_reason
                )
            if used_tokens >= token_budget:
                return FailAction(
                    "model_token_budget_exceeded",
                    f"Agent model token budget exhausted ({used_tokens}/{token_budget})",
                )
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict) or not isinstance(
                    call.get("function"), dict
                ):
                    return FailAction(
                        "malformed_tool_call", "Malformed model Tool call"
                    )
                call_id = str(call.get("id") or f"call-{index}")
                action_key = _tool_action_key(model_step.sequence, index, call_id)
                if action_key in by_action:
                    continue
                function = call["function"]
                alias = function.get("name")
                tool = aliases.get(alias) if isinstance(alias, str) else None
                if tool is None:
                    return FailAction(
                        "tool_not_available",
                        f"Model requested unavailable Tool alias: {alias}",
                    )
                arguments = function.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments or "{}")
                    except json.JSONDecodeError:
                        return FailAction(
                            "invalid_tool_arguments",
                            f"Model returned invalid JSON for {tool.qualified_name}",
                        )
                if not isinstance(arguments, dict):
                    return FailAction(
                        "invalid_tool_arguments",
                        f"Arguments for {tool.qualified_name} must be an object",
                    )
                repeats = 0
                completed_tools = [
                    step
                    for step in context.steps
                    if step.kind == "tool" and step.status is RunStepStatus.COMPLETED
                ]
                for prior in reversed(completed_tools):
                    if (
                        prior.tool_name != tool.qualified_name
                        or prior.input != arguments
                    ):
                        break
                    repeats += 1
                configured_repeats = context.definition.manifest.get(
                    "max_repeated_tool_calls", 3
                )
                max_repeats = (
                    configured_repeats
                    if isinstance(configured_repeats, int) and configured_repeats > 0
                    else 3
                )
                if repeats >= max_repeats:
                    return FailAction(
                        "repeated_tool_call",
                        f"Repeated Tool call limit reached for {tool.qualified_name}",
                    )
                return ToolCallAction(
                    call_id=action_key,
                    tool_name=tool.qualified_name,
                    arguments=arguments,
                    timeout_ms=tool.timeout_ms,
                )

        round_number = 1 + sum(step.kind == "model" for step in context.steps)
        request: dict[str, Any] = {
            "model": context.run.input.get("model", ""),
            "messages": transcript,
            "ai2apps_idempotency_key": (
                f"agent-{context.run.id}-model-{round_number}"
            ),
        }
        if tool_definitions:
            request["tools"] = tool_definitions
            request["tool_choice"] = "auto"
        options = context.run.input.get("model_options", {})
        if not isinstance(options, dict):
            return FailAction(
                "invalid_model_options", "model_options must be an object"
            )
        request.update(
            {key: value for key, value in options.items() if key in _MODEL_OPTION_KEYS}
        )
        return ModelCallAction(call_id=f"model:{round_number}", request=request)

    def _complete(self, context, message, finish_reason) -> CompleteAction:
        content = message.get("content")
        if content is None:
            content = ""
        generated_images = []
        for step in context.steps:
            if (
                step.kind != "tool"
                or step.status is not RunStepStatus.COMPLETED
                or step.tool_name != "image.generate"
                or not isinstance(step.output, dict)
            ):
                continue
            artifact = step.output.get("artifact")
            url = artifact.get("download_url") if isinstance(artifact, dict) else None
            if isinstance(url, str) and url:
                generated_images.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": url,
                            "artifact_id": artifact.get("id"),
                            "filename": artifact.get("name"),
                        },
                    }
                )
        if generated_images:
            text_parts = []
            if isinstance(content, str) and content:
                text_parts.append({"type": "text", "text": content})
            elif isinstance(content, list):
                text_parts.extend(content)
            content = [*text_parts, *generated_images]
        latest_model = next(
            step
            for step in reversed(context.steps)
            if step.kind == "model" and step.status is RunStepStatus.COMPLETED
        )
        usage = (latest_model.output or {}).get("usage")
        cloud_lifecycle = [
            item
            for step in context.steps
            if (
                step.kind == "model"
                or (step.kind == "tool" and step.tool_name == "image.generate")
            )
            and isinstance(step.output, dict)
            for item in (step.output.get("ai2apps_cloud") or [])
            if isinstance(item, dict)
        ]
        if context.run.parent_run_id is not None:
            return CompleteAction(
                {
                    "content": content,
                    "finish_reason": finish_reason,
                    "usage": usage,
                    "ai2apps_cloud": cloud_lifecycle,
                    "total_model_tokens": self._total_model_tokens(context.steps),
                }
            )
        part = (
            MessagePartInput(kind="text", content={"text": content})
            if isinstance(content, str)
            else MessagePartInput(kind="openai_content", content={"content": content})
        )
        result = self.messages.append(
            session_id=context.run.session_id,
            role=MessageRole.ASSISTANT,
            parts=(part,),
            idempotency_key=f"agent-run:{context.run.id}:assistant",
            metadata={
                "agent_run_id": context.run.id,
                "agent_definition_id": context.definition.id,
                "ai2apps_cloud": cloud_lifecycle,
            },
            trace_id=context.run.id,
        )
        return CompleteAction(
            {
                "message_id": result.value.message.id,
                "content": content,
                "finish_reason": finish_reason,
                "usage": usage,
                "ai2apps_cloud": cloud_lifecycle,
                "total_model_tokens": self._total_model_tokens(context.steps),
            }
        )


def install_general_agent(
    repository: AgentRepository,
    runtime: AgentRuntime,
    database: PlatformDatabase,
    events: EventStore,
    tools: ToolGateway,
) -> None:
    repository.ensure_definition(
        agent_key="ai2apps.general-agent",
        package_version="1.0.0",
        display_name="General Agent",
        description="Durable model and Tool loop for conversation Sessions.",
        executor_key="builtin:general-agent",
        concurrency_group="model:foreground",
        concurrency_limit=1,
        max_steps=24,
        timeout_seconds=900,
        manifest={
            "builtin": True,
            "discoverable": True,
            "aliases": ["general", "agent"],
            "invocation_schema": {"type": "object", "properties": {}},
            "allowed_tools": ["*"],
            "context_message_limit": 200,
            "max_total_model_tokens": 100_000,
            "max_repeated_tool_calls": 3,
        },
    )
    runtime.bind_executor(
        "builtin:general-agent",
        GeneralAgentExecutor(database, events, tools),
    )
