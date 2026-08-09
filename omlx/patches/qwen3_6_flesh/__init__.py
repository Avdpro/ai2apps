"""Qwen3.6 Cache-MoE runtime components.

This package is intentionally independent from ``patches.deepseek_v4``.
Qwen may share storage primitives and the public serving contract, but its
router, layer layout, scope policy, cache state, and engine lifecycle live
here so changes cannot leak between model families.
"""

from .scope_policy import (
    Qwen36ScopeCatalog,
    Qwen36ScopePolicy,
    configure_qwen36_scope_policy,
    load_qwen36_scope_policy,
)

__all__ = [
    "Qwen36ScopeCatalog",
    "Qwen36ScopePolicy",
    "configure_qwen36_scope_policy",
    "load_qwen36_scope_policy",
]
