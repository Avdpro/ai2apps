#!/usr/bin/env python3
"""Build and sign the native oMLX Runtime DMG before Apple notarization."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from build_omlx_runtime_package import create_bundle, run, run_codesign, sign_runtime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="1.1.0")
    parser.add_argument("--sign-identity", required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai2apps-omlx-runtime-dmg-") as temporary:
        root = Path(temporary)
        image = root / "image"
        image.mkdir()
        bundle = create_bundle(args.layers.resolve(strict=True), image, args.version)
        team_id = sign_runtime(bundle, args.sign_identity)
        candidate = root / output.name
        run(
            "/usr/bin/hdiutil",
            "create",
            "-fs",
            "HFS+",
            "-format",
            "UDZO",
            "-imagekey",
            "zlib-level=9",
            "-srcfolder",
            str(image),
            str(candidate),
        )
        staged = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        shutil.copy2(candidate, staged)
        os.replace(staged, output)
        # Verify the disk image before signing it. hdiutil may attach/update
        # image checksum metadata, so running it after codesign can invalidate
        # the outer signature even though the image payload is unchanged.
        run("/usr/bin/hdiutil", "verify", str(output))
        # Sign the final file, not the temporary image. On macOS, copying a
        # signed disk image with metadata-preserving APIs can invalidate the
        # outer signature even though the image payload checksum remains valid.
        timestamp = [] if args.sign_identity == "-" else ["--timestamp"]
        run_codesign(
            "--force",
            *timestamp,
            "--sign",
            args.sign_identity,
            str(output),
        )
        run("/usr/bin/codesign", "--verify", "--strict", str(output))
    print(json.dumps({"dmg": str(output), "team_id": team_id}, indent=2))


if __name__ == "__main__":
    main()
