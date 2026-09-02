"""Regression tests for Desktop update verification on an end-user Mac."""

from __future__ import annotations

import importlib.util
import json
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "apps" / "ai2apps-acefox" / "scripts"


def _load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_client_release_inspection_uses_no_xcode_tools(tmp_path, monkeypatch):
    module = _load_script("generate-release-metadata.py")
    app = tmp_path / "AI2Apps.app"
    executable = app / "Contents" / "MacOS" / "AI2Apps"
    runtime_manifest = (
        app
        / "Contents"
        / "Library"
        / "LoginItems"
        / "AI2AppsHelper.app"
        / "Contents"
        / "Resources"
        / "AI2AppsLocal"
        / "runtime-manifest.json"
    )
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"signed executable placeholder")
    runtime_manifest.parent.mkdir(parents=True)
    runtime_manifest.write_text(json.dumps({"runtime_version": "0.1.0"}))
    with (app / "Contents" / "Info.plist").open("wb") as handle:
        plistlib.dump(
            {
                "CFBundleIdentifier": "com.ai2apps.desktop",
                "CFBundleShortVersionString": "0.1.0",
                "CFBundleVersion": "2245",
                "AI2AppsInstanceID": "default",
                "LSMinimumSystemVersion": "13.0",
            },
            handle,
        )
    dmg = tmp_path / "AI2Apps.dmg"
    dmg.write_bytes(b"signed dmg placeholder")
    output = tmp_path / "release.json"
    calls: list[tuple[str, ...]] = []

    def fake_run(*arguments: str, check: bool = True):
        calls.append(arguments)
        stderr = ""
        if arguments[:2] == ("codesign", "-dvvv"):
            stderr = "\n".join(
                [
                    "Identifier=com.ai2apps.desktop",
                    "TeamIdentifier=84XL5V265N",
                    "CDHash=0123456789abcdef",
                    "CodeDirectory v=20500 size=1 flags=0x10000(runtime)",
                ]
            )
        return subprocess.CompletedProcess(arguments, 0, "", stderr)

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate-release-metadata.py",
            "--app",
            str(app),
            "--dmg",
            str(dmg),
            "--output",
            str(output),
            "--client-verification",
        ],
    )
    module.main()

    metadata = json.loads(output.read_text())
    assert metadata["architectures"] == ["arm64"]
    assert metadata["notarization"] == {"status": "stapled"}
    assert any(call[0] == "/usr/sbin/spctl" for call in calls)
    assert all(call[0] not in {"lipo", "xcrun"} for call in calls)


def test_update_candidate_requests_end_user_verification_mode():
    source = (SCRIPTS / "verify-update-candidate.py").read_text()
    assert '"--client-runtime"' in source
