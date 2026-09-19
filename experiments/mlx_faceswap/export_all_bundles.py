#!/usr/bin/env python3
"""Export all locked model files present in a development asset directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .export_bundle import export_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--assets-lock", type=Path, default=Path(__file__).with_name("assets.lock.json")
    )
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.assets_lock.read_text(encoding="utf-8"))
    exported: list[str] = []
    missing: list[str] = []
    for asset in manifest["models"].values():
        filename = asset["filename"]
        source = args.sources / filename
        if not source.is_file() and asset["role"].startswith("portrait_"):
            # The initial local experiment cache predates the lock and used a
            # disambiguating prefix. Published bundles use the canonical
            # upstream filename.
            source = args.sources / f"liveportrait_{filename}"
        if not source.is_file():
            missing.append(filename)
            continue
        destination = args.output / f"{Path(filename).stem}.omlx"
        export_model(source, destination, expected_sha256=asset["sha256"])
        exported.append(str(destination))
    print(json.dumps({"exported": exported, "missing": missing}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
