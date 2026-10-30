"""Normalize Worker chat output using the engine's actual tokenizer protocol."""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

from jsonschema import validate, ValidationError
from omlx.api.tool_calling import _parse_tool_calls_impl
from omlx.api.parser_tool_calls import convert_parser_tool_calls
from .protocol import ModelWorkerError


def invalid(message):
    raise ModelWorkerError(message, code='invalid_tool_call', status_code=502)


class ToolOutput:
    def __init__(self, engine, tools, choice=None):
        self.tools = tools if choice != 'none' else []
        self.choice = choice
        self.tokenizer = getattr(engine, 'tokenizer', None) or getattr(engine, '_tokenizer', None) or SimpleNamespace()
        self.buffer = ''
        self.holding = False
        self.starts = ['<tool_call>', '<|tool_call_start|>']
        marker = getattr(self.tokenizer, 'tool_call_start', None)
        if marker:
            self.starts.append(marker)

    def feed(self, text):
        if not self.tools:
            return text
        self.buffer += text
        if len(self.buffer) > 1024 * 1024:
            invalid('Tool output exceeds the protocol buffer limit')
        if self.holding:
            return ''
        # Preserve ordinary prose streaming. Buffer at protocol/code prefixes;
        # only final, validated calls are emitted, once, after generation ends.
        chars = {'<', '`', '['} | {s[0] for s in self.starts}
        pos = next((i for i, c in enumerate(self.buffer) if c in chars), len(self.buffer))
        safe, self.buffer = self.buffer[:pos], self.buffer[pos:]
        self.holding = bool(self.buffer)
        return safe

    def finish(self, native=None):
        text = self.buffer
        if not self.tools:
            return text, []
        # Code examples are prose, not authority. Do not mask code delimiters
        # contained inside a real protocol envelope's argument values.
        protected = []
        pairs = [('<tool_call>', '</tool_call>'), ('<|tool_call_start|>', '<|tool_call_end|>')]
        start = getattr(self.tokenizer, 'tool_call_start', None)
        end = getattr(self.tokenizer, 'tool_call_end', None)
        if start:
            pairs.append((start, end))
        pairs += [(m.group(), '</'+m.group()[1:]) for m in re.finditer(r'<[\w.-]+:tool_call>', text)]
        spans = []
        for start, end in pairs:
            pattern = re.escape(start) + ('.*?' + re.escape(end) if end else '.*$')
            spans.extend((m.start(), m.end()) for m in re.finditer(pattern, text, re.S))
        def quote(m):
            if any(a <= m.start() < b for a, b in spans):
                return m.group()
            protected.append(m.group())
            return f'\x00quoted{len(protected)-1}\x00'
        masked = re.sub(r'```[\s\S]*?(?:```|\Z)|`[^`\n]*(?:`|\Z)', quote, text)
        starts = list(self.starts)
        starts += [m.group() for m in re.finditer(r'<[\w.-]+:tool_call>', masked)]
        present = [s for s in starts if s in masked]
        for marker in starts:
            if any(masked.endswith(marker[:size]) for size in range(6, len(marker))):
                invalid('Truncated tool-call start marker')
        calls = []
        cleaned = masked
        if present:
            for start, end in pairs:
                if start in masked and end and masked.count(start) != masked.count(end):
                    invalid('Unbalanced tool-call envelope')
            # Validate every generic XML envelope independently: a valid first
            # call must not hide a malformed/truncated second one.
            if '<tool_call>' in masked:
                blocks = re.findall(r'<tool_call>.*?</tool_call>', masked, re.S)
                if len(blocks) != masked.count('<tool_call>'):
                    invalid('Truncated tool-call envelope')
                for block in blocks:
                    _, parsed = _parse_tool_calls_impl(block, self.tokenizer, self.tools)
                    if not parsed:
                        invalid('Could not parse tool-call envelope')
            cleaned, parsed = _parse_tool_calls_impl(masked, self.tokenizer, self.tools)
            if not parsed:
                invalid('Could not parse model tool-call protocol')
            calls = [call.model_dump() for call in parsed]
        if native:
            normalized = []
            for item in native:
                item = item.model_dump() if hasattr(item, 'model_dump') else dict(item)
                if 'function' in item:
                    normalized.append(item)
                else:
                    if isinstance(item.get('arguments'), dict):
                        item['arguments'] = json.dumps(item['arguments'], ensure_ascii=False)
                    converted = convert_parser_tool_calls([item])
                    if len(converted) != 1:
                        invalid('Invalid engine structured tool call')
                    normalized.append(converted[0].model_dump())
            if calls:
                signature = lambda items: [(c['function']['name'], json.loads(c['function']['arguments'])) for c in items]
                try:
                    agrees = signature(calls) == signature(normalized)
                except (KeyError, TypeError, ValueError):
                    invalid('Invalid engine structured tool call')
                if not agrees:
                    invalid('Engine structured calls disagree with raw protocol')
            calls = normalized
        definitions = {t['function']['name']: t['function'] for t in self.tools}
        if self.choice == 'required' and not calls:
            invalid('Model did not return a required tool call')
        for call in calls:
            try:
                fn = call['function']; name = fn['name']
                if name not in definitions:
                    invalid('Model requested an undeclared tool')
                if isinstance(self.choice, dict) and name != self.choice.get('function', {}).get('name'):
                    invalid('Model did not use the explicitly selected tool')
                args = json.loads(fn['arguments'])
                if not isinstance(args, dict):
                    invalid('Tool arguments must be an object')
                validate(args, definitions[name].get('parameters', {'type': 'object'}))
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                invalid('Invalid tool-call arguments: ' + type(exc).__name__)
        for i, value in enumerate(protected):
            cleaned = cleaned.replace(f'\x00quoted{i}\x00', value)
        return cleaned, calls
