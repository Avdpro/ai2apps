#!/usr/bin/env python3
"""Build and sign the native oMLX Runtime DMG before Apple notarization."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from build_omlx_runtime_package import (
    create_bundle,
    create_knowledge_bundle,
    run,
    run_codesign,
    sign_runtime,
)


def _signing_image_size_kib(root: Path) -> int:
    payload_bytes = sum(
        path.stat().st_size
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    payload_kib = (payload_bytes + 1023) // 1024
    return payload_kib + 512 * 1024


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="1.1.0")
    parser.add_argument("--sign-identity", required=True)
    parser.add_argument(
        "--runtime-kind",
        choices=("omlx", "knowledge-rag"),
        default="omlx",
    )
    parser.add_argument(
        "--runtime-source-root",
        type=Path,
        help="Source root containing the ai2apps/ and omlx/ trees to embed",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai2apps-omlx-runtime-dmg-") as temporary:
        root = Path(temporary)
        image = root / "image"
        image.mkdir()
        if args.runtime_kind == "knowledge-rag":
            if args.runtime_source_root is not None:
                raise ValueError(
                    "--runtime-source-root is only valid for the oMLX Runtime"
                )
            bundle_name = "AI2AppsKnowledgeRagRuntime.bundle"
            create_knowledge_bundle(
                args.layers.resolve(strict=True), image, args.version
            )
        else:
            bundle_name = "AI2AppsOmlxRuntime.bundle"
            create_bundle(
                args.layers.resolve(strict=True),
                image,
                args.version,
                runtime_source_root=(
                    args.runtime_source_root.resolve(strict=True)
                    if args.runtime_source_root is not None
                    else Path(__file__).resolve().parents[1]
                ),
            )
        # hdiutil's srcfolder import mutates macOS provenance metadata on the
        # source bundle and invalidates a resource seal created beforehand.
        # Create a writable image first, then sign the bundle in place on the
        # destination filesystem before converting it to the final read-only
        # compressed image.
        writable = root / "AI2AppsOmlxRuntime-writable.dmg"
        run(
            "/usr/bin/hdiutil",
            "create",
            "-fs",
            "APFS",
            "-format",
            "UDRW",
            "-size",
            f"{_signing_image_size_kib(image)}k",
            "-srcfolder",
            str(image),
            str(writable),
        )
        mountpoint = root / "mounted"
        mountpoint.mkdir()
        run(
            "/usr/bin/hdiutil",
            "attach",
            "-readwrite",
            "-nobrowse",
            "-mountpoint",
            str(mountpoint),
            str(writable),
        )
        try:
            team_id = sign_runtime(mountpoint / bundle_name, args.sign_identity)
        finally:
            run("/usr/bin/hdiutil", "detach", str(mountpoint))
        candidate = root / output.name
        run(
            "/usr/bin/hdiutil",
            "convert",
            str(writable),
            "-format",
            "UDZO",
            "-imagekey",
            "zlib-level=9",
            "-o",
            str(candidate),
        )
        staged = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        shutil.copy2(candidate, staged)
        os.replace(staged, output)
    # Let the temporary APFS source and its clones be destroyed before the
    # final integrity check and signature. Otherwise cleanup can change clone
    # bookkeeping after codesign has sealed the output file.
    # Verify the disk image before signing it. hdiutil may attach/update image
    # checksum metadata, so running it after codesign can invalidate the outer
    # signature even though the image payload is unchanged.
    run("/usr/bin/hdiutil", "verify", str(output))
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
