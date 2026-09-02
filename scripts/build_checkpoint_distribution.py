#!/usr/bin/env python3
"""Build one Publisher-signed, byte-verified MS/HF distribution envelope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.checkpoint_publishing import (
    build_checkpoint_distribution,
    build_checkpoint_distribution_from_metadata,
    fetch_modelscope_file_metadata,
    verification_receipt_for_envelope,
    write_checkpoint_distribution,
)
from ai2apps.secrets.factory import create_secret_backend


def _private_key(args: argparse.Namespace) -> Ed25519PrivateKey:
    if args.private_key is not None:
        value = serialization.load_pem_private_key(
            args.private_key.read_bytes(), password=None
        )
    else:
        backend = create_secret_backend(
            Path.home() / ".omlx" / "platform" / "secrets",
            namespace=args.keychain_namespace,
        )
        value = serialization.load_pem_private_key(
            backend.load(args.keychain_secret).encode("ascii"), password=None
        )
    if not isinstance(value, Ed25519PrivateKey):
        raise TypeError("Publisher key must be Ed25519")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--huggingface-root", type=Path, required=True)
    parser.add_argument("--modelscope-root", type=Path)
    parser.add_argument(
        "--verification-mode",
        choices=("metadata_verified", "full_dual_download"),
        default="metadata_verified",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publisher-id", required=True)
    parser.add_argument("--publisher-key-id", required=True)
    key = parser.add_mutually_exclusive_group(required=True)
    key.add_argument("--private-key", type=Path)
    key.add_argument("--keychain-secret")
    parser.add_argument("--keychain-namespace")
    args = parser.parse_args()
    if args.keychain_secret and not args.keychain_namespace:
        parser.error("--keychain-namespace is required with --keychain-secret")
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    private_key = _private_key(args)
    if args.verification_mode == "full_dual_download":
        if args.modelscope_root is None:
            parser.error("--modelscope-root is required for full_dual_download")
        built = build_checkpoint_distribution(
            spec,
            source_roots={
                "huggingface": args.huggingface_root,
                "modelscope": args.modelscope_root,
            },
            private_key=private_key,
            publisher_id=args.publisher_id,
            publisher_key_id=args.publisher_key_id,
        )
    else:
        source = next(
            item
            for item in spec["sourceRepositories"]
            if item["type"] == "modelscope"
        )
        built = build_checkpoint_distribution_from_metadata(
            spec,
            huggingface_root=args.huggingface_root,
            modelscope_files=fetch_modelscope_file_metadata(
                source["repoId"],
                source["revision"],
                include_patterns=tuple(spec["includePatterns"]),
            ),
            private_key=private_key,
            publisher_id=args.publisher_id,
            publisher_key_id=args.publisher_key_id,
        )
    result = write_checkpoint_distribution(built, args.output)
    result["verificationReceiptValue"] = verification_receipt_for_envelope(
        built.envelope, builder=built.verification_builder
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
