"""Utilities for consuming an OpenAI chat-completion stream for an Agent.

The Agent runtime still needs a complete response so it can durably decide
whether to call a Tool or finish the Run.  This accumulator lets the provider
consume the response as a stream (and report progress) without changing that
decision contract.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _append_text(target: dict[str, Any], source: dict[str, Any], key: str) -> None:
    value = source.get(key)
    if isinstance(value, str):
        target[key] = str(target.get(key) or "") + value


class ChatCompletionStreamAccumulator:
    """Reassemble OpenAI-compatible SSE chunks into one completion object."""

    def __init__(self) -> None:
        self._root: dict[str, Any] = {}
        self._choices: dict[int, dict[str, Any]] = {}
        self._cloud_lifecycle: list[dict[str, Any]] = []
        self._cloud_failure: dict[str, Any] | None = None
        self.output_characters = 0
        self.fragments = 0
        self.has_tool_calls = False

    def add(self, chunk: dict[str, Any]) -> None:
        for key in (
            "id",
            "created",
            "model",
            "system_fingerprint",
            "service_tier",
        ):
            if key in chunk and chunk[key] is not None:
                self._root[key] = chunk[key]
        if isinstance(chunk.get("usage"), dict):
            self._root["usage"] = deepcopy(chunk["usage"])

        choices = chunk.get("choices")
        if not isinstance(choices, list):
            return
        for raw_choice in choices:
            if not isinstance(raw_choice, dict):
                continue
            index = raw_choice.get("index", 0)
            if not isinstance(index, int):
                index = 0
            choice = self._choices.setdefault(
                index,
                {
                    "index": index,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                },
            )
            delta = raw_choice.get("delta")
            if not isinstance(delta, dict):
                delta = {}
            cloud = delta.get("ai2apps_cloud")
            if isinstance(cloud, dict):
                self._cloud_lifecycle.append(deepcopy(cloud))
                if cloud.get("phase") == "failed":
                    error = cloud.get("error")
                    self._cloud_failure = deepcopy(error if isinstance(error, dict) else cloud)
            message = choice["message"]
            if isinstance(delta.get("role"), str):
                message["role"] = delta["role"]
            for key in ("content", "reasoning_content", "refusal"):
                before = len(str(message.get(key) or ""))
                _append_text(message, delta, key)
                after = len(str(message.get(key) or ""))
                self.output_characters += after - before
            if any(isinstance(delta.get(key), str) for key in ("content", "reasoning_content")):
                self.fragments += 1

            tool_deltas = delta.get("tool_calls")
            if isinstance(tool_deltas, list):
                self.has_tool_calls = self.has_tool_calls or bool(tool_deltas)
                tools = message.setdefault("tool_calls", [])
                by_index = {
                    item["index"]: item
                    for item in tools
                    if isinstance(item, dict) and isinstance(item.get("index"), int)
                }
                for tool_delta in tool_deltas:
                    if not isinstance(tool_delta, dict):
                        continue
                    tool_index = tool_delta.get("index", 0)
                    if not isinstance(tool_index, int):
                        tool_index = 0
                    tool = by_index.get(tool_index)
                    if tool is None:
                        tool = {
                            "index": tool_index,
                            "id": "",
                            "type": "",
                            "function": {"name": "", "arguments": ""},
                        }
                        tools.append(tool)
                        by_index[tool_index] = tool
                    if isinstance(tool_delta.get("id"), str):
                        tool["id"] = str(tool.get("id") or "") + tool_delta["id"]
                    if isinstance(tool_delta.get("type"), str):
                        tool["type"] = tool_delta["type"]
                    function = tool_delta.get("function")
                    if isinstance(function, dict):
                        _append_text(tool["function"], function, "name")
                        _append_text(tool["function"], function, "arguments")

            if raw_choice.get("finish_reason") is not None:
                choice["finish_reason"] = raw_choice["finish_reason"]
            if raw_choice.get("logprobs") is not None:
                choice["logprobs"] = deepcopy(raw_choice["logprobs"])

    def result(self) -> dict[str, Any]:
        if self._cloud_failure is not None:
            code = str(self._cloud_failure.get("code") or "AI2APPS_CLOUD_REQUEST_FAILED")
            message = str(self._cloud_failure.get("message") or code)
            raise ValueError(f"{code}: {message}")
        if not self._choices:
            raise ValueError("Model Runtime stream did not contain a completion choice")
        choices = []
        for index in sorted(self._choices):
            choice = deepcopy(self._choices[index])
            message = choice["message"]
            tools = message.get("tool_calls")
            if isinstance(tools, list):
                tools.sort(key=lambda item: item.get("index", 0))
                for tool in tools:
                    tool.pop("index", None)
                    if not tool.get("type"):
                        tool["type"] = "function"
            if not message.get("reasoning_content"):
                message.pop("reasoning_content", None)
            if not message.get("refusal"):
                message.pop("refusal", None)
            choices.append(choice)
        return {
            "id": self._root.get("id", ""),
            "object": "chat.completion",
            "created": self._root.get("created", 0),
            "model": self._root.get("model", ""),
            "choices": choices,
            **{
                key: deepcopy(self._root[key])
                for key in ("system_fingerprint", "service_tier", "usage")
                if key in self._root
            },
            **(
                {"ai2apps_cloud": deepcopy(self._cloud_lifecycle)}
                if self._cloud_lifecycle
                else {}
            ),
        }
