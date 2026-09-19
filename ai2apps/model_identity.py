"""Stable presentation identity for models exposed by AI2Apps.

Runtime model ids remain routing keys.  This module owns the user-facing
``(Source) Provider · Model`` label shared by Chat and every Studio.
"""

from __future__ import annotations

import re
from typing import Any

SOURCE_LABELS = {
    "cloud": "Cloud",
    "ai2apps_cloud": "Cloud",
    "local": "Local",
    "local_runtime": "Local",
    "package": "Local",
    "builtin": "Local",
    "fusion": "Local",
    "upstream_gateway": "Local",
    "byok": "BYOK",
    "local_byok": "BYOK",
}

PROVIDER_LABELS = {
    "ai2apps": "AI2Apps",
    "ai2apps-fusion": "AI2Apps-Fusion",
    "ai2apps.runtime.omlx": "AI2Apps-MLX",
    "ai2apps.runtime.cuda-torch": "AI2Apps-CUDA",
    "ai2apps.runtime.knowledge-rag": "AI2Apps-Knowledge",
    "omlx": "AI2Apps-MLX",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "openrouter": "OpenRouter",
}

MODEL_NAMES = {
    "gpt-5.6-luna": "ChatGPT 5.6 Luna",
    "gpt-5.6-sol": "ChatGPT 5.6 Sol",
    "gpt-5.6-terra": "ChatGPT 5.6 Terra",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def source_identity(source: str | None) -> tuple[str, str]:
    raw = _clean(source).lower().replace("-", "_")
    label = SOURCE_LABELS.get(raw, "Local")
    return label.lower(), label


def provider_label(provider_id: str | None, provider_name: str | None = None) -> str:
    key = _clean(provider_id).lower()
    if key in PROVIDER_LABELS:
        return PROVIDER_LABELS[key]
    name = _clean(provider_name)
    if name:
        return name.removesuffix(" Cloud")
    if not key:
        return "AI2Apps-MLX"
    return " ".join(part.capitalize() for part in re.split(r"[._-]+", key) if part)


def _humanize_model_id(model_id: str) -> str:
    value = model_id.rsplit("/", 1)[-1]
    known = MODEL_NAMES.get(value.lower())
    if known:
        return known
    value = re.sub(r"[_-]+", " ", value).strip()
    value = re.sub(r"(?i)\bqwen\s*(\d)", r"Qwen \1", value)
    value = re.sub(r"(?i)\b(\d+)b\b", lambda m: f"{m.group(1)}B", value)
    value = re.sub(r"(?i)\b(nvfp4|fp\d+|bf\d+|q\d+|int\d+)\b", lambda m: m.group(1).upper(), value)
    return value or model_id


def model_label(
    model_id: str,
    display_name: str | None = None,
    *,
    provider_id: str | None = None,
    provider_name: str | None = None,
) -> str:
    route_id = _clean(model_id)
    leaf_id = route_id.rsplit("/", 1)[-1]
    known = MODEL_NAMES.get(leaf_id.lower())
    if known:
        return known

    name = _clean(display_name)
    if not name or name in {route_id, leaf_id}:
        return _humanize_model_id(leaf_id)

    # Some managed catalogs historically included the inference provider in
    # displayName. Strip only providers whose brand differs from the model
    # family; "DeepSeek DeepSeek V4" is intentionally preserved as a model
    # name of "DeepSeek V4" rather than being handled generically.
    provider = _clean(provider_id).lower()
    removable_prefixes = {
        "anthropic": "Anthropic ",
        "google": "Google ",
        "openai": "OpenAI ",
        "openrouter": "OpenRouter ",
    }
    prefix = removable_prefixes.get(provider)
    if prefix and name.casefold().startswith(prefix.casefold()):
        name = name[len(prefix) :].strip()
    return name


def build_model_identity(
    *,
    source: str | None,
    provider_id: str | None,
    model_id: str,
    display_name: str | None = None,
    provider_name: str | None = None,
) -> dict[str, str]:
    source_id, source_name = source_identity(source)
    provider = provider_label(provider_id, provider_name)
    model = model_label(
        model_id,
        display_name,
        provider_id=provider_id,
        provider_name=provider_name,
    )
    return {
        "source": source_id,
        "sourceLabel": source_name,
        "providerId": _clean(provider_id).lower(),
        "providerName": provider,
        "modelId": _clean(model_id),
        "modelName": model,
        "displayName": f"({source_name}) {provider} · {model}",
    }


def with_model_identity(
    entry: dict[str, Any],
    *,
    source: str | None,
    provider_id: str | None,
    model_id: str | None = None,
    display_name: str | None = None,
    provider_name: str | None = None,
) -> dict[str, Any]:
    identity = build_model_identity(
        source=source,
        provider_id=provider_id,
        model_id=model_id or str(entry.get("id") or ""),
        display_name=display_name,
        provider_name=provider_name,
    )
    entry["identity"] = identity
    entry["display_name"] = identity["displayName"]
    entry["name"] = identity["displayName"]
    entry["model_name"] = identity["modelName"]
    return entry


def model_identity_fields(**kwargs: Any) -> dict[str, Any]:
    """Return fields suitable for an API model object or Pydantic model."""

    identity = build_model_identity(**kwargs)
    return {
        "identity": identity,
        "display_name": identity["displayName"],
        "name": identity["displayName"],
    }
