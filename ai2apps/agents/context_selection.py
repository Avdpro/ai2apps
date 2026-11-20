"""Action keys for host-owned context selection model steps.

Its model usage remains in the Run budget. Its response is a selector result,
so it must never be consumed as the task's answer or tool calls.
"""

CONTEXT_SELECTION = "owner-context-selection"


def is_context_selection(key: str) -> bool:
    return key == CONTEXT_SELECTION or key.startswith(CONTEXT_SELECTION + ":")
