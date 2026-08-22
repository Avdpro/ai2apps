#!/usr/bin/env python3
"""Build and verify deployable oMLX model-adapter release directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai2apps.packages.repository_config import AI2APPS_REPOSITORY_FINGERPRINT
from omlx.model_adapters.publishing import (
    build_release_bundle,
    generate_repository_key,
    verify_release_bundle,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    keygen = commands.add_parser("generate-key", help="create a new offline trust root")
    keygen.add_argument("--private-key", type=Path, required=True)
    keygen.add_argument("--public-key", type=Path, required=True)

    build = commands.add_parser("build", help="build a signed static release directory")
    build.add_argument("--wheel", type=Path, action="append", required=True)
    build.add_argument("--private-key", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--metadata-version", type=int, required=True)
    build.add_argument("--artifact-url-prefix", default=".")
    build.add_argument("--expires-days", type=int, default=30)
    build.add_argument("--previous-catalog", type=Path)
    build.add_argument(
        "--checkpoint-manifest",
        type=Path,
        help="signed recommendation metadata keyed by package@version",
    )
    trust = build.add_mutually_exclusive_group()
    trust.add_argument(
        "--expected-fingerprint",
        default=AI2APPS_REPOSITORY_FINGERPRINT,
        help="required signing-key fingerprint (defaults to the AI2Apps trust root)",
    )
    trust.add_argument(
        "--allow-non-production-key",
        action="store_true",
        help="allow an ephemeral/local key; never use for production publication",
    )

    verify = commands.add_parser("verify", help="verify a completed release directory")
    verify.add_argument("--catalog", type=Path, required=True)
    verify.add_argument("--public-key", type=Path, required=True)
    verify.add_argument("--artifacts-dir", type=Path, required=True)
    verify.add_argument("--fingerprint")

    args = parser.parse_args()
    if args.command == "generate-key":
        report = generate_repository_key(args.private_key, args.public_key)
    elif args.command == "build":
        report = build_release_bundle(
            args.wheel,
            private_key_path=args.private_key,
            output_dir=args.output_dir,
            metadata_version=args.metadata_version,
            artifact_url_prefix=args.artifact_url_prefix,
            expires_days=args.expires_days,
            previous_catalog=args.previous_catalog,
            expected_fingerprint=(
                None if args.allow_non_production_key else args.expected_fingerprint
            ),
            checkpoint_manifest=args.checkpoint_manifest,
        )
    else:
        report = verify_release_bundle(
            args.catalog,
            args.public_key,
            args.artifacts_dir,
            pinned_fingerprint=args.fingerprint,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
