from __future__ import annotations

import pytest

from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.localization import (
    localized_app_metadata,
    localized_package_metadata,
    normalize_locale,
    package_localizations_for_manifest,
    validate_app_localizations,
)


def test_locale_normalization_and_app_fallbacks():
    manifest = {
        "id": "example.notes",
        "name": "Notes",
        "description": "Base description",
        "navigation": {"category": "Tools"},
        "localizations": {
            "zh": {
                "name": "笔记",
                "description": "基础说明",
                "navigation": {"category": "工具"},
            },
            "zh-TW": {
                "name": "筆記",
                "description": "繁體說明",
                "navigation": {"category": "工具"},
            },
        },
    }

    assert normalize_locale("zh_cn") == "zh-CN"
    assert localized_app_metadata(manifest, "zh-CN")["name"] == "笔记"
    assert localized_app_metadata(manifest, "zh-HK")["name"] == "筆記"
    assert localized_app_metadata(manifest, "fr")["name"] == "Notes"


def test_package_metadata_and_runtime_manifest_conversion():
    package = {
        "id": "example/notes",
        "displayName": "Notes",
        "description": "Base description",
        "localizations": {
            "zh-CN": {"displayName": "笔记", "description": "中文说明"}
        },
    }

    assert localized_package_metadata(package, "zh-CN") == {
        "displayName": "笔记",
        "description": "中文说明",
    }
    converted = package_localizations_for_manifest(
        package["localizations"],
        {"zh-CN": {"navigation": {"category": "效率"}}},
    )
    assert converted["zh-CN"] == {
        "name": "笔记",
        "description": "中文说明",
        "navigation": {"category": "效率"},
    }
    assert package_localizations_for_manifest(None) == {}


def test_builtin_app_localizations_follow_manifest_contract():
    for manifest in SYSTEM_APP_MANIFESTS:
        validate_app_localizations(manifest["localizations"])

    account = next(
        manifest
        for manifest in SYSTEM_APP_MANIFESTS
        if manifest["id"] == "ai2apps.account"
    )
    assert localized_app_metadata(account, "zh-CN")["name"] == "账户"


def test_app_localization_rejects_unknown_fields():
    with pytest.raises(ValueError, match="unsupported fields"):
        validate_app_localizations({"zh": {"name": "笔记", "icon": "note"}})
