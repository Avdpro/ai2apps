"""Canonical Site Agent identity and source-shape helpers."""

from __future__ import annotations

import re
import json
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit


def canonical_site_key(value: str) -> str:
    """Return a conservative, stable site identity without guessing public suffixes."""

    text = str(value or "").strip()
    if not text:
        return ""
    if re.match(r"^[a-z][a-z0-9+.-]*:", text, re.IGNORECASE) and not text.startswith(("http://", "https://")):
        return ""
    parsed = urlsplit(text if "://" in text else f"https://{text}")
    host = (parsed.hostname or "").rstrip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return ""
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    if port and host in {"localhost", "127.0.0.1", "::1"}:
        return f"{host}:{port}"
    return host


def site_key_from_source(source: dict[str, Any], site_scope: list[str] | tuple[str, ...] = ()) -> str:
    explicit = canonical_site_key(str(source.get("site_key") or ""))
    if explicit:
        return explicit
    scopes = source.get("site_scope") or site_scope
    if isinstance(scopes, list | tuple):
        for scope in scopes:
            key = canonical_site_key(str(scope).replace("/**", "/"))
            if key:
                return key
    return ""


def capability_slug(value: str, fallback: str = "run") -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return value[:80] or fallback


def capability_from_legacy(source: dict[str, Any], *, legacy_draft_id: str | None = None) -> dict[str, Any]:
    exports = source.get("capability_exports")
    export = exports[0] if isinstance(exports, list) and exports and isinstance(exports[0], dict) else {}
    title = str(source.get("name") or "Run")
    capability_id = capability_slug(str(export.get("name") or title))
    legacy_steps = deepcopy(source.get("steps") or [])
    item = {
        "id": capability_id,
        "name": str(export.get("name") or f"site.{capability_id}"),
        "title": title,
        "description": str(source.get("description") or export.get("description") or ""),
        "inputs": deepcopy(source.get("inputs") or export.get("input_schema") or {"type": "object", "properties": {}}),
        "outputs": deepcopy(source.get("outputs") or export.get("output_schema") or {"type": "object", "properties": {}}),
        "steps": legacy_steps,
        "fixtures": deepcopy(source.get("fixtures") or []),
        "validators": deepcopy(source.get("validators") or []),
    }
    if legacy_draft_id:
        item["provenance"] = {"legacy_draft_id": legacy_draft_id}
        if not legacy_steps:
            item["enabled"] = False
    return item


def normalize_site_agent_source(
    source: dict[str, Any], *, site_key: str = "", legacy_draft_id: str | None = None
) -> dict[str, Any]:
    """Upgrade a single-pipeline Agent Source to the P1.1 Site Agent shape."""

    if isinstance(source.get("capabilities"), list):
        result = deepcopy(source)
        result.setdefault("schema", "ai2apps.site-agent-source/v1")
        result["site_key"] = canonical_site_key(site_key or str(result.get("site_key") or ""))
        _dedupe_capabilities(result)
        return result
    result = {
        "schema": "ai2apps.site-agent-source/v1",
        "agent_type": str(source.get("agent_type") or "web"),
        "site_key": canonical_site_key(site_key) or site_key_from_source(source),
        "name": str(source.get("name") or "Untitled Site Agent"),
        "description": str(source.get("description") or ""),
        "site_scope": deepcopy(source.get("site_scope") or []),
        "capabilities": [capability_from_legacy(source, legacy_draft_id=legacy_draft_id)],
    }
    if source.get("provenance"):
        result["provenance"] = deepcopy(source["provenance"])
    return result


def _dedupe_capabilities(source: dict[str, Any]) -> None:
    capabilities = [
        item for item in source.get("capabilities", []) if isinstance(item, dict)
    ]
    retained: list[dict[str, Any]] = []
    semantic_signatures: dict[str, bool] = {}
    for item in capabilities:
        provenance = item.get("provenance")
        imported = isinstance(provenance, dict) and bool(
            provenance.get("legacy_draft_id")
        )
        title = str(item.get("title") or "").strip().casefold()
        description = str(item.get("description") or "").strip()
        steps = item.get("steps")
        if imported and not description and not steps and title in {
            "run", "new agent", "new site agent"
        }:
            continue
        semantic = {
            key: value for key, value in item.items()
            if key not in {"id", "name", "provenance", "enabled"}
        }
        signature = json.dumps(
            semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if signature in semantic_signatures and (
            imported or semantic_signatures[signature]
        ):
            continue
        semantic_signatures.setdefault(signature, imported)
        retained.append(item)
    source["capabilities"] = retained

    used_ids: set[str] = set()
    used_names: set[str] = set()
    for index, item in enumerate(source.get("capabilities", [])):
        if not isinstance(item, dict):
            continue
        base = capability_slug(str(item.get("id") or item.get("title") or f"capability-{index + 1}"))
        capability_id = base
        suffix = 2
        while capability_id in used_ids:
            capability_id = f"{base}-{suffix}"
            suffix += 1
        item["id"] = capability_id
        used_ids.add(capability_id)
        name = str(item.get("name") or f"site.{capability_id}")
        if name in used_names:
            name = f"site.{capability_id}"
        item["name"] = name
        used_names.add(name)
        provenance = item.get("provenance")
        if isinstance(provenance, dict) and provenance.get("legacy_draft_id") and not item.get("steps"):
            item.setdefault("enabled", False)


def unique_capability_id(source: dict[str, Any], desired: str) -> str:
    used = {
        str(item.get("id") or "")
        for item in source.get("capabilities", [])
        if isinstance(item, dict)
    }
    base = capability_slug(desired)
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
