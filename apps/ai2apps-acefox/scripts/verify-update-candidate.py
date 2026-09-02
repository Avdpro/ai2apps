#!/usr/bin/env python3
"""Verify that one signed AI2Apps release is a safe update for an installed App."""

from __future__ import annotations

import argparse
import json
import platform
import plistlib
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


MAX_METADATA_BYTES = 64 * 1024


def fail(message: str) -> None:
    raise SystemExit(f"verify-update-candidate: {message}")


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        details = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
        detail = details[-1][:256] if details else f"exit status {completed.returncode}"
        fail(f"{Path(arguments[0]).name} failed: {detail}")
    return completed


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_METADATA_BYTES:
        fail("candidate metadata is missing or exceeds 64 KiB")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"cannot read candidate metadata: {error}")
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        fail("unsupported candidate metadata schema")
    return value


def load_info(app: Path) -> dict[str, Any]:
    try:
        with (app / "Contents" / "Info.plist").open("rb") as handle:
            value = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException) as error:
        fail(f"cannot read installed App identity: {error}")
    if not isinstance(value, dict):
        fail("installed App Info.plist is invalid")
    return value


def signing_value(app: Path, name: str) -> str:
    output = run("codesign", "-dvvv", str(app)).stderr
    match = re.search(rf"^{re.escape(name)}=(.+)$", output, re.MULTILINE)
    if match is None:
        fail(f"installed App signature is missing {name}")
    return match.group(1).strip()


def positive_build(value: Any, field: str) -> int:
    if not isinstance(value, str) or not value.isascii() or not value.isdigit():
        fail(f"{field} must be a positive integer string")
    number = int(value)
    if number < 1:
        fail(f"{field} must be positive")
    return number


def version_tuple(value: str, field: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+)*", value):
        fail(f"{field} is not a numeric dotted version")
    return tuple(int(component) for component in value.split("."))


def current_macos_version() -> str:
    value = platform.mac_ver()[0]
    if value:
        return value
    return run("sw_vers", "-productVersion").stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-app", required=True, type=Path)
    parser.add_argument("--candidate-app", required=True, type=Path)
    parser.add_argument("--candidate-dmg", required=True, type=Path)
    parser.add_argument("--candidate-metadata", required=True, type=Path)
    parser.add_argument(
        "--internal-candidate",
        action="store_true",
        help="permit a valid not_stapled developer candidate",
    )
    args = parser.parse_args()

    installed = args.installed_app.resolve()
    candidate_app = args.candidate_app.resolve()
    candidate_dmg = args.candidate_dmg.resolve()
    candidate_metadata = args.candidate_metadata.resolve()
    if not installed.is_dir() or installed.suffix != ".app":
        fail("--installed-app must be an existing .app")

    verifier = Path(__file__).with_name("verify-release-metadata.py")
    if not verifier.is_file():
        fail("release metadata verifier is missing")
    run(
        sys.executable,
        "-I",
        "-B",
        str(verifier),
        "--metadata",
        str(candidate_metadata),
        "--app",
        str(candidate_app),
        "--dmg",
        str(candidate_dmg),
        "--client-runtime",
    )
    run("codesign", "--verify", "--deep", "--strict", str(installed))

    info = load_info(installed)
    metadata = load_json(candidate_metadata)
    required_installed = (
        "CFBundleIdentifier",
        "CFBundleVersion",
        "AI2AppsInstanceID",
    )
    if any(not isinstance(info.get(key), str) or not info[key] for key in required_installed):
        fail("installed App is missing update identity fields")
    installed_identifier = signing_value(installed, "Identifier")
    installed_team = signing_value(installed, "TeamIdentifier")
    if installed_identifier != info["CFBundleIdentifier"]:
        fail("installed App signature identifier does not match Info.plist")
    if installed_team in {"", "not set", "-"}:
        fail("installed App must have a Developer ID team")

    checks = {
        "product": "AI2Apps",
        "bundle_identifier": info["CFBundleIdentifier"],
        "instance_id": info["AI2AppsInstanceID"],
    }
    for field, expected in checks.items():
        if metadata.get(field) != expected:
            fail(f"candidate {field} does not match installed App")
    signing = metadata.get("signing")
    if not isinstance(signing, dict) or signing.get("team_identifier") != installed_team:
        fail("candidate signing team does not match installed App")
    if signing.get("identifier") != info["CFBundleIdentifier"]:
        fail("candidate signature identifier does not match installed App")
    if signing.get("hardened_runtime") is not True:
        fail("candidate must enable Hardened Runtime")

    installed_build = positive_build(info["CFBundleVersion"], "installed build")
    candidate_build = positive_build(metadata.get("bundle_version"), "candidate build")
    if candidate_build <= installed_build:
        fail("candidate build must be newer than installed build")

    notarization = metadata.get("notarization")
    status = notarization.get("status") if isinstance(notarization, dict) else None
    allowed_status = "not_stapled" if args.internal_candidate else "stapled"
    if status != allowed_status:
        fail(f"candidate notarization status must be {allowed_status}")

    architectures = metadata.get("architectures")
    machine = platform.machine()
    if not isinstance(architectures, list) or machine not in architectures:
        fail(f"candidate does not support this Mac architecture ({machine})")
    minimum = metadata.get("minimum_system_version")
    if not isinstance(minimum, str):
        fail("candidate is missing minimum_system_version")
    current_system = current_macos_version()
    if version_tuple(minimum, "minimum_system_version") > version_tuple(
        current_system, "current macOS version"
    ):
        fail(f"candidate requires macOS {minimum}, current system is {current_system}")

    result = {
        "bundle_identifier": info["CFBundleIdentifier"],
        "from_build": str(installed_build),
        "instance_id": info["AI2AppsInstanceID"],
        "status": "eligible",
        "to_build": str(candidate_build),
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
