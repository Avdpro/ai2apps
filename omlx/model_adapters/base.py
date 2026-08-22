# SPDX-License-Identifier: Apache-2.0
"""Public contracts for installable oMLX model adapters.

Adapters are intentionally small.  They may classify a checkpoint, prepare
third-party model registrations before load, or take over a custom checkpoint
load.  Returning ``None`` from an optional operation preserves oMLX's built-in
fallback behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ModelAdapterContext:
    """Immutable checkpoint metadata passed to adapter operations."""

    model_path: Path
    config: dict[str, Any]
    model_settings: Any | None = None
    for_vlm: bool = False


@runtime_checkable
class ModelAdapter(Protocol):
    """Structural contract implemented by built-in and external adapters.

    Only ``adapter_id`` and ``match`` are required at runtime.  ``priority``
    defaults to zero, and the operation methods are optional.  This keeps a
    classification-only package from importing MLX or model runtime modules.
    """

    adapter_id: str
    priority: int

    def match(self, context: ModelAdapterContext) -> bool:
        """Return whether this adapter owns the checkpoint family."""

    def classify(self, context: ModelAdapterContext) -> str | None:
        """Optionally return oMLX's model category (``llm``, ``vlm``, ...)."""

    def prepare(self, context: ModelAdapterContext) -> None:
        """Optionally install model registrations or patches before loading."""

    def load(self, context: ModelAdapterContext) -> tuple[Any, Any] | None:
        """Optionally return ``(model, tokenizer_or_processor)``."""

    def installation_recipes(self) -> tuple[dict[str, Any], ...]:
        """Optionally expose trusted checkpoint preparation recipes."""
