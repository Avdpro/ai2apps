#!/usr/bin/env python3
"""Independently verify signed AI2Apps artifacts against a release record."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


MAX_METADATA_BYTES = 64 * 1024


def fail(message: str) -> None:
    raise SystemExit(f"verify-release-metadata: {message}")


def load_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail("--metadata must be an existing file")
    if path.stat().st_size > MAX_METADATA_BYTES:
        fail("metadata exceeds 64 KiB")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"cannot read metadata: {error}")
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        fail("unsupported metadata schema")
    generated_at = value.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.endswith("Z"):
        fail("generated_at must be a UTC timestamp")
    try:
        datetime.fromisoformat(generated_at[:-1] + "+00:00")
    except ValueError:
        fail("generated_at is not a valid timestamp")
    return value


def first_difference(expected: Any, actual: Any, path: str = "$") -> str:
    if type(expected) is not type(actual):
        return path
    if isinstance(expected, dict):
        if set(expected) != set(actual):
            return path
        for key in sorted(expected):
            difference = first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
        return ""
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return path
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            difference = first_difference(
                expected_item, actual_item, f"{path}[{index}]"
            )
            if difference:
                return difference
        return ""
    return "" if expected == actual else path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--dmg", required=True, type=Path)
    args = parser.parse_args()

    metadata = args.metadata.resolve()
    app = args.app.resolve()
    dmg = args.dmg.resolve()
    expected = load_record(metadata)
    generator = Path(__file__).with_name("generate-release-metadata.py")
    if not generator.is_file():
        fail("release metadata generator is missing")

    with tempfile.TemporaryDirectory(prefix="ai2apps-release-verify.") as directory:
        actual_path = Path(directory) / "actual.release.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(generator),
                "--app",
                str(app),
                "--dmg",
                str(dmg),
                "--output",
                str(actual_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            details = [
                line.strip()
                for line in completed.stderr.splitlines()
                if line.strip()
            ]
            detail = details[-1][:256] if details else "artifact inspection failed"
            fail(detail)
        actual = load_record(actual_path)

    # The record creation time describes publication, not current verification.
    expected.pop("generated_at")
    actual.pop("generated_at")
    difference = first_difference(expected, actual)
    if difference:
        fail(f"artifact metadata mismatch at {difference}")
    print(f"Verified release metadata {metadata}")


if __name__ == "__main__":
    main()
