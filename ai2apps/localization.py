"""Locale-aware metadata resolution for Apps and distributable Packages."""

from __future__ import annotations

import re
from typing import Any, Mapping


_LOCALE_TAG = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


def normalize_locale(value: object) -> str:
    """Normalize a BCP-47-like locale tag without requiring external libraries."""

    raw = str(value or "en").strip().replace("_", "-")
    if not _LOCALE_TAG.fullmatch(raw):
        return "en"
    parts = raw.split("-")
    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 2 and part.isalpha():
            normalized.append(part.upper())
        elif len(part) == 4 and part.isalpha():
            normalized.append(part.title())
        else:
            normalized.append(part.lower())
    return "-".join(normalized)


def locale_candidates(locale: object) -> tuple[str, ...]:
    """Return most-specific to language-only candidates, excluding English fallback."""

    normalized = normalize_locale(locale)
    candidates = [normalized]
    language = normalized.split("-", 1)[0]
    if language == "zh" and normalized in {"zh-HK", "zh-MO", "zh-Hant"}:
        candidates.append("zh-TW")
    if language != normalized:
        candidates.append(language)
    return tuple(dict.fromkeys(candidates))


def localized_values(
    localizations: object,
    locale: object,
) -> Mapping[str, Any]:
    if not isinstance(localizations, Mapping):
        return {}
    by_normalized = {
        normalize_locale(key): value
        for key, value in localizations.items()
        if isinstance(key, str) and isinstance(value, Mapping)
    }
    for candidate in locale_candidates(locale):
        value = by_normalized.get(candidate)
        if isinstance(value, Mapping):
            return value
    return {}


def localized_app_metadata(manifest: Mapping[str, Any], locale: object) -> dict[str, str]:
    """Resolve user-visible App metadata with manifest defaults as fallback."""

    values = localized_values(manifest.get("localizations"), locale)
    navigation = manifest.get("navigation")
    navigation = navigation if isinstance(navigation, Mapping) else {}
    localized_navigation = values.get("navigation")
    localized_navigation = (
        localized_navigation if isinstance(localized_navigation, Mapping) else {}
    )
    return {
        "name": str(values.get("name") or manifest.get("name") or manifest.get("id") or "App"),
        "description": str(values.get("description") or manifest.get("description") or ""),
        "category": str(localized_navigation.get("category") or navigation.get("category") or "Third-party"),
    }


def localized_package_metadata(package: Mapping[str, Any], locale: object) -> dict[str, str]:
    """Resolve Package catalog metadata with signed base metadata as fallback."""

    values = localized_values(package.get("localizations"), locale)
    return {
        "displayName": str(values.get("displayName") or package.get("displayName") or package.get("id") or "Package"),
        "description": str(values.get("description") or package.get("description") or ""),
    }


def package_localizations_for_manifest(
    package_localizations: object,
    manifest_localizations: object = None,
) -> dict[str, dict[str, Any]]:
    """Convert signed Package display names to runtime Manifest names."""

    result: dict[str, dict[str, Any]] = {}
    if isinstance(manifest_localizations, Mapping):
        result = {
            str(locale): dict(translation)
            for locale, translation in manifest_localizations.items()
            if isinstance(locale, str) and isinstance(translation, Mapping)
        }
    if not isinstance(package_localizations, Mapping):
        return result
    for locale, translation in package_localizations.items():
        if not isinstance(locale, str) or not isinstance(translation, Mapping):
            continue
        merged = dict(result.get(locale, {}))
        merged["name"] = translation.get("displayName", merged.get("name", ""))
        if "description" in translation:
            merged["description"] = translation["description"]
        result[locale] = merged
    return result


def validate_app_localizations(value: object) -> None:
    """Validate the localized metadata surface shared by built-in and packaged Apps."""

    if not isinstance(value, Mapping) or not value or len(value) > 64:
        raise ValueError("localizations must be a non-empty locale map")
    normalized: set[str] = set()
    for locale, translation in value.items():
        if not isinstance(locale, str) or not _LOCALE_TAG.fullmatch(locale):
            raise ValueError("localization locale tag is invalid")
        locale_key = normalize_locale(locale).casefold()
        if locale_key in normalized:
            raise ValueError("localization locale tags must be unique")
        normalized.add(locale_key)
        if not isinstance(translation, Mapping):
            raise ValueError("localization entry must be an object")
        if not set(translation).issubset({"name", "description", "navigation"}):
            raise ValueError("localization entry contains unsupported fields")
        name = translation.get("name")
        description = translation.get("description")
        if not isinstance(name, str) or not 1 <= len(name) <= 160:
            raise ValueError("localized App name is invalid")
        if description is not None and (
            not isinstance(description, str) or len(description) > 2000
        ):
            raise ValueError("localized App description is invalid")
        navigation = translation.get("navigation")
        if navigation is not None:
            if (
                not isinstance(navigation, Mapping)
                or set(navigation) != {"category"}
                or not isinstance(navigation["category"], str)
                or not 1 <= len(navigation["category"]) <= 80
            ):
                raise ValueError("localized App navigation is invalid")
