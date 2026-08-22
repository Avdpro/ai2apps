#!/usr/bin/env python3
"""Verify and stage one immutable AI2Apps update from a signed DMG."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"stage-update-candidate: {message}")


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(arguments, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        details = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
        detail = details[-1][:256] if details else f"exit status {completed.returncode}"
        fail(f"{Path(arguments[0]).name} failed: {detail}")
    return completed


def cdhash(app: Path) -> str:
    output = run("codesign", "-dvvv", str(app)).stderr
    match = re.search(r"^CDHash=(.+)$", output, re.MULTILINE)
    if match is None:
        fail("signed App is missing CDHash")
    return match.group(1).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed-app", required=True, type=Path)
    parser.add_argument("--dmg", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--output-app", required=True, type=Path)
    parser.add_argument("--internal-candidate", action="store_true")
    args = parser.parse_args()

    raw_installed = args.installed_app.absolute()
    raw_dmg = args.dmg.absolute()
    raw_metadata = args.metadata.absolute()
    raw_output = args.output_app.absolute()
    if raw_installed.is_symlink() or raw_dmg.is_symlink() or raw_metadata.is_symlink():
        fail("installed App, DMG, and metadata roots must not be symbolic links")
    if raw_output.is_symlink() or raw_output.parent.is_symlink():
        fail("output App and parent must not be symbolic links")
    installed = raw_installed.resolve()
    dmg = raw_dmg.resolve()
    metadata = raw_metadata.resolve()
    output = raw_output.resolve()
    if not installed.is_dir() or installed.suffix != ".app":
        fail("--installed-app must be an existing .app")
    if not dmg.is_file() or dmg.suffix != ".dmg":
        fail("--dmg must be a real .dmg file")
    if not metadata.is_file():
        fail("--metadata must be a real file")
    if metadata.stat().st_size > 64 * 1024:
        fail("--metadata exceeds 64 KiB")
    try:
        record = json.loads(metadata.read_text(encoding="utf-8"))
        candidate_filename = record["artifacts"]["app"]["filename"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        fail("--metadata does not contain an App artifact filename")
    expected_status = "not_stapled" if args.internal_candidate else "stapled"
    if record.get("schema_version") != 1:
        fail("unsupported metadata schema")
    if record.get("notarization", {}).get("status") != expected_status:
        fail(f"candidate notarization status must be {expected_status}")
    if (
        not isinstance(candidate_filename, str)
        or Path(candidate_filename).name != candidate_filename
        or not candidate_filename.endswith(".app")
    ):
        fail("metadata App filename must be a plain .app name")
    if output.suffix != ".app" or output.exists() or output.is_symlink():
        fail("--output-app must be a new .app path")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output.parent, 0o700)

    verifier = Path(__file__).with_name("verify-update-candidate.py")
    if not verifier.is_file():
        fail("update verifier is missing")

    mount_point = Path(tempfile.mkdtemp(prefix="ai2apps-update-mount."))
    mounted = False
    staging_root = output.parent / f".ai2apps-update-{os.getpid()}.staging"
    if staging_root.exists():
        fail("staging collision")
    staging_root.mkdir(mode=0o700)
    staged = staging_root / candidate_filename
    try:
        try:
            run(
                "hdiutil",
                "attach",
                "-readonly",
                "-nobrowse",
                "-mountpoint",
                str(mount_point),
                str(dmg),
            )
            mounted = True
            apps = [
                item for item in mount_point.iterdir()
                if item.suffix == ".app" and item.is_dir()
            ]
            if len(apps) != 1 or apps[0].name != "AI2Apps.app" or apps[0].is_symlink():
                fail("DMG must contain exactly one real top-level AI2Apps.app")
            embedded = apps[0]
            if staged.exists():
                fail("staging collision")
            embedded_hash = cdhash(embedded)
            run("/usr/bin/ditto", str(embedded), str(staged))
            run("codesign", "--verify", "--deep", "--strict", str(staged))
            if cdhash(staged) != embedded_hash:
                fail("staged App CDHash changed after copy")
        finally:
            if mounted:
                detached = subprocess.run(
                    ["hdiutil", "detach", str(mount_point)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if detached.returncode != 0:
                    subprocess.run(
                        ["hdiutil", "detach", "-force", str(mount_point)],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                mounted = False
            try:
                mount_point.rmdir()
            except OSError:
                pass

        command = [
            sys.executable,
            "-I",
            "-B",
            str(verifier),
            "--installed-app",
            str(installed),
            "--candidate-app",
            str(staged),
            "--candidate-dmg",
            str(dmg),
            "--candidate-metadata",
            str(metadata),
        ]
        if args.internal_candidate:
            command.append("--internal-candidate")
        run(*command)
        os.replace(staged, output)
        print(f"Staged verified update {output}")
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        try:
            mount_point.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    main()
