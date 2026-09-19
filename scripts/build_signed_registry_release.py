#!/usr/bin/env python3
"""Build a Package Contract v1 artifact and sign its detached Cloud envelope."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ai2apps.checkpoint_package_policy import (
    require_checkpoint_distributions_from_artifact,
    require_checkpoint_distributions_from_source,
)
from ai2apps.packages.contract_v1 import (
    build_package,
    create_signature_envelope,
    inspect_package,
)
from ai2apps.secrets.factory import create_secret_backend


def main() -> None:
    parser = argparse.ArgumentParser()
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--source", type=Path)
    input_group.add_argument(
        "--artifact",
        type=Path,
        help="Sign an already-built Package Contract v1 artifact without rebuilding it",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publisher-id", required=True)
    parser.add_argument("--publisher-key-id", required=True)
    parser.add_argument("--keychain-secret", required=True)
    parser.add_argument("--keychain-namespace", required=True)
    parser.add_argument(
        "--omit-mini-app-catalog",
        action="store_true",
        help=(
            "Keep Mini-App declarations only in the signed app.yaml for "
            "compatibility with Registry schemas predating top-level miniApps"
        ),
    )
    parser.add_argument(
        "--omit-model-install-catalog",
        action="store_true",
        help=(
            "Keep modelInstall in Package source but omit its top-level "
            "Registry projection for compatibility with older Cloud schemas"
        ),
    )
    args = parser.parse_args()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.artifact is not None:
        artifact = args.artifact.resolve(strict=True)
        if artifact != output:
            raise SystemExit("--artifact must refer to the same path as --output")
        inspected = inspect_package(artifact)
        require_checkpoint_distributions_from_artifact(artifact)
    else:
        source = args.source.resolve(strict=True)
        require_checkpoint_distributions_from_source(source)
        inspected = build_package(
            source,
            output,
            include_mini_app_catalog=not args.omit_mini_app_catalog,
            include_model_install_catalog=not args.omit_model_install_catalog,
        )
    backend = create_secret_backend(
        Path.home() / ".omlx" / "platform" / "secrets",
        namespace=args.keychain_namespace,
    )
    private_key = backend.load(args.keychain_secret)
    envelope = create_signature_envelope(
        inspected,
        private_key,
        publisher_id=args.publisher_id,
        publisher_key_id=args.publisher_key_id,
    )
    envelope_path = output.with_suffix(output.suffix + ".envelope.json")
    temporary = envelope_path.with_name(f".{envelope_path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, envelope_path)
    print(
        json.dumps(
            {
                "artifact": str(output),
                "envelope": str(envelope_path),
                "packageId": inspected.manifest["package"]["id"],
                "version": inspected.manifest["package"]["version"],
                "sha256": inspected.sha256,
                "size": inspected.size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
