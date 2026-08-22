#!/usr/bin/env python3
"""Build a Package Contract v1 artifact and sign its detached Cloud envelope."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ai2apps.packages.contract_v1 import build_package, create_signature_envelope, inspect_package
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
    args = parser.parse_args()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.artifact is not None:
        artifact = args.artifact.resolve(strict=True)
        if artifact != output:
            raise SystemExit("--artifact must refer to the same path as --output")
        inspected = inspect_package(artifact)
    else:
        inspected = build_package(args.source.resolve(strict=True), output)
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
