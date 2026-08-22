# SPDX-License-Identifier: Apache-2.0
"""Deterministic registry for built-in and installable model adapters."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
from typing import Any

from .base import ModelAdapterContext

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "omlx.model_adapters"


class ModelAdapterRegistrationError(ValueError):
    """Raised when an adapter does not satisfy the minimum contract."""


class ModelAdapterRegistry:
    """Process-local adapter registry with lazy entry-point discovery.

    Matching is deterministic: higher priority wins, then ``adapter_id``.
    Broken third-party entry points are isolated and logged so one optional
    package cannot prevent the server from starting.  Once an adapter matches,
    exceptions from its operation are *not* swallowed: silently falling back
    after a weight transform or loader failure could produce incorrect output.
    """

    def __init__(self, *, load_entry_points: bool = True) -> None:
        self._adapters: dict[str, Any] = {}
        self._load_entry_points = load_entry_points
        self._entry_points_loaded = False
        self._lock = threading.RLock()

    @staticmethod
    def _validate(adapter: Any) -> tuple[str, int]:
        adapter_id = getattr(adapter, "adapter_id", None)
        if not isinstance(adapter_id, str) or not adapter_id.strip():
            raise ModelAdapterRegistrationError(
                "model adapter must declare a non-empty string adapter_id"
            )
        if not callable(getattr(adapter, "match", None)):
            raise ModelAdapterRegistrationError(
                f"model adapter {adapter_id!r} must define match(context)"
            )
        priority = getattr(adapter, "priority", 0)
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ModelAdapterRegistrationError(
                f"model adapter {adapter_id!r} priority must be an integer"
            )
        return adapter_id, priority

    def register(self, adapter: Any, *, replace: bool = False) -> None:
        adapter_id, _ = self._validate(adapter)
        with self._lock:
            if adapter_id in self._adapters and not replace:
                raise ModelAdapterRegistrationError(
                    f"model adapter {adapter_id!r} is already registered"
                )
            self._adapters[adapter_id] = adapter

    def unregister(self, adapter_id: str) -> None:
        with self._lock:
            self._adapters.pop(adapter_id, None)

    @staticmethod
    def _entry_points() -> Iterable[Any]:
        discovered = metadata.entry_points()
        if hasattr(discovered, "select"):
            return discovered.select(group=ENTRY_POINT_GROUP)
        return discovered.get(ENTRY_POINT_GROUP, ())  # pragma: no cover - py3.9

    @staticmethod
    def _materialize(loaded: Any) -> Any:
        if isinstance(loaded, type):
            return loaded()
        if callable(loaded) and not callable(getattr(loaded, "match", None)):
            return loaded()
        return loaded

    def load_entry_points(self) -> None:
        with self._lock:
            if self._entry_points_loaded or not self._load_entry_points:
                return
            self._entry_points_loaded = True

        # Loading package code can be slow or re-enter imports.  Keep it out of
        # the registry lock and merge each validated result atomically.
        try:
            entry_points = sorted(
                self._entry_points(), key=lambda item: (item.name, item.value)
            )
        except Exception:
            logger.exception("Could not enumerate %s entry points", ENTRY_POINT_GROUP)
            return

        for entry_point in entry_points:
            try:
                adapter = self._materialize(entry_point.load())
                self.register(adapter)
            except Exception as exc:
                logger.warning(
                    "Ignoring model adapter entry point %s=%s: %s",
                    entry_point.name,
                    entry_point.value,
                    exc,
                )

    def adapters(self) -> tuple[Any, ...]:
        self.load_entry_points()
        with self._lock:
            return tuple(
                sorted(
                    self._adapters.values(),
                    key=lambda adapter: (
                        -int(getattr(adapter, "priority", 0)),
                        str(adapter.adapter_id),
                    ),
                )
            )

    def matching(self, context: ModelAdapterContext) -> tuple[Any, ...]:
        matches: list[Any] = []
        for adapter in self.adapters():
            try:
                matched = adapter.match(context)
            except Exception as exc:
                logger.warning(
                    "Model adapter %s match failed for %s: %s",
                    adapter.adapter_id,
                    context.model_path,
                    exc,
                )
                continue
            if matched:
                matches.append(adapter)
        return tuple(matches)

    def classify(self, context: ModelAdapterContext) -> str | None:
        for adapter in self.matching(context):
            operation = getattr(adapter, "classify", None)
            if not callable(operation):
                continue
            result = operation(context)
            if result is not None:
                return result
        return None

    def prepare(self, context: ModelAdapterContext) -> tuple[str, ...]:
        prepared: list[str] = []
        for adapter in self.matching(context):
            operation = getattr(adapter, "prepare", None)
            if not callable(operation):
                continue
            operation(context)
            prepared.append(adapter.adapter_id)
        return tuple(prepared)

    def load(self, context: ModelAdapterContext) -> tuple[Any, Any] | None:
        for adapter in self.matching(context):
            operation = getattr(adapter, "load", None)
            if not callable(operation):
                continue
            loaded = operation(context)
            if loaded is not None:
                return loaded
        return None

    def installation_recipes(self) -> tuple[dict[str, Any], ...]:
        """Collect optional checkpoint recipes from active adapter packages."""
        recipes: list[dict[str, Any]] = []
        identities: set[str] = set()
        for adapter in self.adapters():
            operation = getattr(adapter, "installation_recipes", None)
            if not callable(operation):
                continue
            provided = operation()
            if not isinstance(provided, (list, tuple)):
                raise ModelAdapterRegistrationError(
                    f"model adapter {adapter.adapter_id!r} returned invalid recipes"
                )
            for recipe in provided:
                recipe_id = recipe.get("id") if isinstance(recipe, dict) else None
                if not isinstance(recipe_id, str) or not recipe_id.strip():
                    raise ModelAdapterRegistrationError(
                        f"model adapter {adapter.adapter_id!r} returned an invalid recipe"
                    )
                if recipe_id in identities:
                    raise ModelAdapterRegistrationError(
                        f"duplicate model installation recipe: {recipe_id}"
                    )
                identities.add(recipe_id)
                recipes.append(recipe)
        return tuple(recipes)


# Production Host registry never imports distribution entry points. Built-in
# adapters may still be registered explicitly by trusted application code.
_default_registry = ModelAdapterRegistry(load_entry_points=False)


def get_model_adapter_registry() -> ModelAdapterRegistry:
    return _default_registry


def adapter_context(
    model_path: str | Path,
    config: dict[str, Any],
    *,
    model_settings: Any | None = None,
    for_vlm: bool = False,
) -> ModelAdapterContext:
    return ModelAdapterContext(
        model_path=Path(model_path),
        config=config,
        model_settings=model_settings,
        for_vlm=for_vlm,
    )
