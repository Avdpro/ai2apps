"""Unified discovery surface for built-in and installed Studio Mini-Apps."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from ai2apps.identity import RequestPrincipal

from .mini_app_chat import builtin_chat_capability


class StudioMiniAppRegistry:
    """Merge host-owned Mini-Apps with signed Package declarations."""

    SCHEMA = "ai2apps.studio-mini-app-list/v1"

    def __init__(self, extension_manager) -> None:
        self.extension_manager = extension_manager

    def list(
        self,
        studio_id: str,
        *,
        builtins: Iterable[dict[str, Any]] = (),
        principal: RequestPrincipal | None = None,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        conflicts: set[str] = set()

        for declaration in builtins:
            item = json.loads(json.dumps(declaration))
            mini_app_id = str(item.get("id", ""))
            if not mini_app_id or mini_app_id in seen:
                continue
            item.setdefault("source", "builtin")
            if item.get("entry", {}).get("kind") == "host-adapter":
                item.setdefault("chat", builtin_chat_capability(mini_app_id))
            seen.add(mini_app_id)
            items.append(item)

        discover = getattr(self.extension_manager, "list_studio_mini_apps", None)
        package_items = (
            ()
            if discover is None
            else discover(studio_id, principal=principal)
        )
        package_counts: dict[str, int] = {}
        for item in package_items:
            mini_app_id = str(item.get("id", ""))
            package_counts[mini_app_id] = package_counts.get(mini_app_id, 0) + 1
        conflicts.update(
            mini_app_id
            for mini_app_id, count in package_counts.items()
            if count > 1 or mini_app_id in seen
        )

        def order(item: dict[str, Any]) -> tuple[int, str]:
            placements = item.get("placements", [])
            selected = next(
                (
                    placement
                    for placement in placements
                    if isinstance(placement, dict)
                    and placement.get("studio") == studio_id
                ),
                {},
            )
            value = selected.get("order", item.get("order", 1000))
            return (value if isinstance(value, int) else 1000, str(item.get("id", "")))

        for declaration in sorted(package_items, key=order):
            mini_app_id = str(declaration.get("id", ""))
            if not mini_app_id or mini_app_id in conflicts:
                continue
            seen.add(mini_app_id)
            items.append(declaration)

        return {
            "schema": self.SCHEMA,
            "studioId": studio_id,
            "items": items,
            "conflicts": sorted(conflicts),
        }
