# SPDX-License-Identifier: Apache-2.0
"""Development Bundle source-mounted Package acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ai2apps.config import PlatformConfig
from ai2apps.extensions import UnitKind
from ai2apps.platform_runtime import PlatformRuntime


def _write_source_repository(root: Path, *, mini_app_name: str = "Transcribe") -> Path:
    (root / "ai2apps").mkdir(parents=True)
    (root / "ai2apps" / "__init__.py").write_text("", encoding="utf-8")
    package = root / "packages" / "example-dev-app"
    (package / "web").mkdir(parents=True)
    (package / "ai2apps.json").write_text(
        json.dumps(
            {
                "schemaVersion": "ai2apps.package-manifest.v1",
                "package": {
                    "id": "example/dev-app",
                    "type": "app",
                    "version": "1.2.3",
                    "displayName": "Example Development App",
                },
                "compatibility": {"ai2apps": ">=0.1.0 <2.0.0"},
                "entrypoints": [
                    {"name": "main", "kind": "app", "path": "web/index.html"}
                ],
                "permissions": [],
                "dependencies": [],
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    (package / "app.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "ai2apps.app/v1",
                "id": "example.dev-app",
                "name": "Source name",
                "version": "1.2.3",
                "publisher": {"id": "example"},
                "instances": {"mode": "multiple"},
                "entry": {"kind": "sandbox", "resource": "web/index.html"},
                "mini_apps": [
                    {
                        "schema": "ai2apps.mini-app/v1",
                        "id": "example.dev.transcribe",
                        "name": mini_app_name,
                        "version": "1.0.0",
                        "kind": "project",
                        "entry": {
                            "kind": "sandbox",
                            "resource": "web/transcribe.html",
                            "placements": ["inline", "sidebar"],
                        },
                        "placements": [
                            {"studio": "ai2apps.video-studio", "order": 10}
                        ],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (package / "web" / "index.html").write_text("<main>index</main>", encoding="utf-8")
    (package / "web" / "transcribe.html").write_text(
        "<main>first</main>", encoding="utf-8"
    )
    return package


def test_development_bundle_mounts_package_source_and_hot_refreshes(
    tmp_path, monkeypatch
):
    source_root = tmp_path / "source"
    package = _write_source_repository(source_root)
    monkeypatch.setenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", "1")
    monkeypatch.setenv("AI2APPS_DEVELOPMENT_SOURCE_ROOT", str(source_root))
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()

    app = next(
        item
        for item in runtime.extension_manager.list_apps()
        if item["app_key"] == "example.dev-app"
    )
    mini_app = runtime.extension_manager.list_studio_mini_apps(
        "ai2apps.video-studio"
    )[0]
    instance, _home, _created = runtime.extension_manager.launch_app("example.dev-app")
    mount = runtime.extension_manager.mount_studio_mini_app(
        "ai2apps.video-studio", mini_app["id"]
    )

    assert app["source"] == "development"
    assert app["distribution"] == "development"
    assert mini_app["provider"]["distribution"] == "development"
    assert runtime.extension_manager.mount_entry(mount["id"])["source"] == "development"
    assert runtime.extension_repository.installed(UnitKind.APP, "example.dev-app") == ()
    with runtime.database.transaction() as connection:
        revision_before = connection.execute(
            "SELECT revision FROM app_definitions WHERE package_id='example.dev-app' "
            "AND status='enabled'"
        ).fetchone()["revision"]
    resource = runtime.extension_manager.resolve_app_resource(
        instance.id, "web/transcribe.html"
    )
    assert resource.read_text(encoding="utf-8") == "<main>first</main>"
    runtime.extension_manager.resolve_app_resource(instance.id, "web/transcribe.html")
    with runtime.database.transaction() as connection:
        revision_after = connection.execute(
            "SELECT revision FROM app_definitions WHERE package_id='example.dev-app' "
            "AND status='enabled'"
        ).fetchone()["revision"]
    assert revision_after == revision_before

    resource.write_text("<main>hot edit</main>", encoding="utf-8")
    assert runtime.extension_manager.resolve_app_resource(
        instance.id, "web/transcribe.html"
    ).read_text(encoding="utf-8") == "<main>hot edit</main>"

    app_manifest = yaml.safe_load((package / "app.yaml").read_text(encoding="utf-8"))
    app_manifest["mini_apps"][0]["name"] = "Renamed without restart"
    (package / "app.yaml").write_text(
        yaml.safe_dump(app_manifest, sort_keys=False), encoding="utf-8"
    )
    refreshed = runtime.extension_manager.list_studio_mini_apps(
        "ai2apps.video-studio"
    )[0]
    assert refreshed["name"] == "Renamed without restart"


def test_source_mount_is_disabled_without_development_runtime_marker(
    tmp_path, monkeypatch
):
    source_root = tmp_path / "source"
    _write_source_repository(source_root)
    monkeypatch.delenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", raising=False)
    monkeypatch.setenv("AI2APPS_DEVELOPMENT_SOURCE_ROOT", str(source_root))
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()

    assert all(
        item["app_key"] != "example.dev-app"
        for item in runtime.extension_manager.list_apps()
    )


def test_prior_source_definition_is_disabled_when_marker_is_removed(
    tmp_path, monkeypatch
):
    source_root = tmp_path / "source"
    _write_source_repository(source_root)
    data_root = tmp_path / "data"
    monkeypatch.setenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME", "1")
    monkeypatch.setenv("AI2APPS_DEVELOPMENT_SOURCE_ROOT", str(source_root))
    development_runtime = PlatformRuntime(PlatformConfig.from_base_path(data_root))
    development_runtime.start()
    assert any(
        item["app_key"] == "example.dev-app"
        for item in development_runtime.extension_manager.list_apps()
    )
    development_runtime.stop()

    monkeypatch.delenv("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME")
    without_marker = PlatformRuntime(PlatformConfig.from_base_path(data_root))
    without_marker.start()

    assert all(
        item["app_key"] != "example.dev-app"
        for item in without_marker.extension_manager.list_apps()
    )
