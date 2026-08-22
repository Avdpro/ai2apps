#!/usr/bin/env python3
"""Generate bounded, machine-readable metadata for one signed AI2Apps release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"generate-release-metadata: {message}")


def run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        details = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
        detail = details[-1][:256] if details else f"exit status {completed.returncode}"
        fail(f"{Path(arguments[0]).name} failed: {detail}")
    return completed


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_size(path: Path) -> int:
    total = 0
    for root, _directories, files in os.walk(path, followlinks=False):
        for filename in files:
            candidate = Path(root) / filename
            if not candidate.is_symlink():
                total += candidate.stat().st_size
    return total


def signing_metadata(app: Path) -> dict[str, object]:
    result = run("codesign", "-dvvv", str(app))
    output = result.stderr

    def value(name: str) -> str:
        match = re.search(rf"^{re.escape(name)}=(.+)$", output, re.MULTILINE)
        if match is None:
            fail(f"signed App is missing {name}")
        return match.group(1).strip()

    flags = value("CodeDirectory v") if "CodeDirectory v=" in output else ""
    return {
        "cdhash": value("CDHash"),
        "identifier": value("Identifier"),
        "team_identifier": value("TeamIdentifier"),
        "hardened_runtime": "runtime" in flags or "flags=0x10000" in output,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--dmg", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    app = args.app.resolve()
    dmg = args.dmg.resolve()
    output = args.output.resolve()
    if not app.is_dir() or app.suffix != ".app":
        fail("--app must be an existing .app bundle")
    if not dmg.is_file() or dmg.suffix != ".dmg":
        fail("--dmg must be an existing .dmg")
    if output.exists():
        fail("refusing to overwrite output")

    run("codesign", "--verify", "--deep", "--strict", str(app))
    run("codesign", "--verify", str(dmg))
    dmg_verifier = Path(__file__).with_name("verify-dmg-contents.sh")
    if not dmg_verifier.is_file():
        fail("DMG content verifier is missing")
    run(str(dmg_verifier), str(app), str(dmg))
    info_path = app / "Contents" / "Info.plist"
    runtime_manifest_path = (
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
    if not runtime_manifest_path.is_file():
        fail("embedded Runtime manifest is missing")
    with info_path.open("rb") as handle:
        info = plistlib.load(handle)
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    signing = signing_metadata(app)

    required_info = (
        "CFBundleIdentifier",
        "CFBundleShortVersionString",
        "CFBundleVersion",
        "AI2AppsInstanceID",
    )
    if any(not isinstance(info.get(key), str) or not info[key] for key in required_info):
        fail("App Info.plist is missing release identity fields")
    if signing["identifier"] != info["CFBundleIdentifier"]:
        fail("code signature identifier does not match Info.plist")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?", info["AI2AppsInstanceID"]):
        fail("invalid AI2AppsInstanceID")

    executable = app / "Contents" / "MacOS" / "AI2Apps"
    architectures = run("lipo", "-archs", str(executable)).stdout.split()
    stapled = run("xcrun", "stapler", "validate", str(dmg), check=False).returncode == 0
    metadata = {
        "schema_version": 1,
        "product": "AI2Apps",
        "installed_app_name": "AI2Apps.app",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "bundle_identifier": info["CFBundleIdentifier"],
        "product_version": info["CFBundleShortVersionString"],
        "bundle_version": info["CFBundleVersion"],
        "instance_id": info["AI2AppsInstanceID"],
        "architectures": sorted(architectures),
        "minimum_system_version": info.get("LSMinimumSystemVersion"),
        "runtime": {
            "version": runtime_manifest.get("runtime_version"),
            "manifest_sha256": sha256_file(runtime_manifest_path),
        },
        "signing": signing,
        "notarization": {"status": "stapled" if stapled else "not_stapled"},
        "artifacts": {
            "app": {
                "filename": app.name,
                "size_bytes": bundle_size(app),
            },
            "dmg": {
                "filename": dmg.name,
                "size_bytes": dmg.stat().st_size,
                "sha256": sha256_file(dmg),
            },
        },
    }
    if not metadata["runtime"]["version"]:
        fail("runtime manifest is missing runtime_version")

    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        dir=output.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # This manifest contains no secrets and is published beside the DMG.
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, output)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    print(f"Generated release metadata {output}")


if __name__ == "__main__":
    main()
