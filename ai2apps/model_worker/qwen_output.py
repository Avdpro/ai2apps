"""Incremental Qwen thinking/tool framing for the CUDA development adapter."""
import json
import re
import uuid


def parse_call(text, tools):
    definitions = {item["function"]["name"]: item["function"] for item in tools}
    try:
        obj = json.loads(text)
        name, args = obj["name"], obj["arguments"]
        if isinstance(args, str):
            args = json.loads(args)
    except (ValueError, KeyError, TypeError):
        match = re.fullmatch(r"\s*<function=([^>]+)>(.*?)</function>\s*", text, re.S)
        if not match:
            raise ValueError("Invalid Qwen tool-call framing")
        name, body = match.groups()
        if name not in definitions:
            raise ValueError("Model requested an undeclared tool")
        args = {}
        schema = definitions[name].get("parameters", {}).get("properties", {})
        cursor = 0
        for field in re.finditer(r"<parameter=([^>]+)>(.*?)</parameter>", body, re.S):
            if body[cursor:field.start()].strip():
                raise ValueError("Unexpected tool argument text")
            key, value = field.groups()
            if key in args:
                raise ValueError("Duplicate tool argument")
            value = value.strip()
            args[key] = value if schema.get(key, {}).get("type") == "string" else json.loads(value)
            cursor = field.end()
        if body[cursor:].strip():
            raise ValueError("Unexpected trailing tool argument text")
    if name not in definitions or not isinstance(args, dict):
        raise ValueError("Invalid or undeclared tool call")
    from jsonschema import validate
    validate(args, definitions[name].get("parameters", {"type": "object"}))
    return {"id": "call_" + uuid.uuid4().hex, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


class OutputParser:
    def __init__(self, thinking=False, tools=()):
        self.mode = "reasoning_content" if thinking else "content"
        self.buffer = ""
        self.tools = tools
        self.calls = 0

    def feed(self, text, final=False):
        self.buffer += text
        events = []
        markers = ("<think>", "</think>", "<tool_call>", "<|im_end|>", "<|endoftext|>")
        while self.buffer:
            if self.mode == "tool":
                end = self.buffer.find("</tool_call>")
                if end < 0:
                    if len(self.buffer) > 65536:
                        raise ValueError("Tool call exceeds the output bound")
                    if final:
                        raise ValueError("Truncated tool call")
                    break
                call = parse_call(self.buffer[:end].strip(), self.tools)
                events.append({"tool_calls": [{"index": self.calls, **call}]})
                self.calls += 1
                self.buffer = self.buffer[end + len("</tool_call>"):]
                self.mode = "content"
                continue
            active_markers = tuple(mark for mark in markers
                                   if self.mode != "reasoning_content" or mark != "<tool_call>")
            found = [(self.buffer.find(mark), mark) for mark in active_markers if mark in self.buffer]
            if found:
                position, mark = min(found)
                if position:
                    events.append({self.mode: self.buffer[:position]})
                self.buffer = self.buffer[position + len(mark):]
                if mark == "<think>":
                    self.mode = "reasoning_content"
                elif mark == "</think>":
                    self.mode = "content"
                elif mark == "<tool_call>":
                    self.mode = "tool"
                continue
            keep = 0
            if not final:
                for mark in active_markers:
                    for size in range(1, min(len(mark), len(self.buffer) + 1)):
                        if self.buffer.endswith(mark[:size]):
                            keep = max(keep, size)
            safe = len(self.buffer) - keep
            if safe:
                events.append({self.mode: self.buffer[:safe]})
                self.buffer = self.buffer[safe:]
            break
        return events
