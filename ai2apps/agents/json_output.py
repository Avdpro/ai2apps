"""Shared bounded repair policy for declarative model JSON (never browser retries)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

MAX_JSON_REPAIRS = 2
_logger = logging.getLogger(__name__)


def parse_model_json(output: Any) -> Any:
    try:
        content = output['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError('Model response has no message content') from error
    if isinstance(content, (dict, list)):
        return content
    if not isinstance(content, str):
        raise ValueError('Model response content must be JSON text')
    text = content.strip()
    if text.startswith('```'):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == '```':
            lines.pop()
        text = '\n'.join(lines).strip()
    # Do not silently change values, remove arbitrary prose, or evaluate model code.
    def reject_constant(value):
        raise ValueError(f"Non-JSON numeric constant: {value}")
    return json.loads(text, parse_constant=reject_constant)


def repair_json_request(request: dict[str, Any], output: Any, error: Any) -> dict[str, Any]:
    try:
        content = output['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        content = output
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, default=str)
    return {**request, 'messages': [*request.get('messages', []),
        {'role': 'assistant', 'content': content[:16000]},
        {'role': 'user', 'content': (
            'The previous response failed JSON parsing or validation. Repair it and return '
            'one complete JSON value matching the original required schema and constraints. '
            'Use double-quoted keys and strings. No commentary or Markdown fences. '
            'Preserve the requested values; do not invent data or execute actions. '
            'Validation error: ' + str(error)[:2000])}]}


@dataclass
class JsonRepairBudget:
    used: int = 0

    def consume(self, error: Any, *, model: str = '', stage: str = '') -> bool:
        _logger.warning('Agent JSON validation model=%s stage=%s repair=%s exhausted=%s error_type=%s',
                        model, stage, self.used, self.used >= MAX_JSON_REPAIRS, type(error).__name__)
        if self.used >= MAX_JSON_REPAIRS:
            return False
        self.used += 1
        return True
