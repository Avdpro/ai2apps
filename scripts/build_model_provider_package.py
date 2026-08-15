#!/usr/bin/env python3
"""Build a signed local-development `.ai2service` model provider archive."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.packages import PackageFile, package_digest
from ai2apps.packages.archive import ServicePackageArchive

EXCLUDED = {
    "META/files.json",
    "attestations/publisher.json",
    "signatures/publisher.sig",
}


def _private_key(path: Path | None) -> tuple[Ed25519PrivateKey, bool]:
    if path is None:
        return Ed25519PrivateKey.generate(), True
    value = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(value, Ed25519PrivateKey):
        raise TypeError("Publisher key must be Ed25519")
    return value, False


def _write_zip_file(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)


def build(source: Path, output: Path, key_path: Path | None) -> dict:
    source = source.resolve(strict=True)
    manifest_path = source / "service.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing {manifest_path}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    parsed = ServicePackageArchive._manifest(manifest)
    private, ephemeral = _private_key(key_path)

    immutable: dict[str, bytes] = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(source).as_posix()
        if relative in EXCLUDED or relative.startswith("dist/") or relative == "README.md":
            continue
        immutable[relative] = path.read_bytes()
    files = tuple(
        PackageFile(
            path=name,
            content_hash="sha256:" + hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )
        for name, content in immutable.items()
    )
    digest = package_digest(manifest, files)
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    key_id = f"{parsed.publisher_key}:local"
    publisher = {
        "publisher_id": parsed.publisher_key,
        "key_id": key_id,
        "algorithm": "ed25519",
        "package_digest": digest,
    }
    signature = {
        "algorithm": "ed25519",
        "key_id": key_id,
        "signature": base64.b64encode(private.sign(digest.encode("ascii"))).decode(),
    }
    index = {
        "files": [
            {"path": item.path, "sha256": item.content_hash, "size": item.size_bytes}
            for item in files
        ]
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, content in immutable.items():
                _write_zip_file(archive, name, content)
            _write_zip_file(
                archive,
                "META/files.json",
                json.dumps(index, sort_keys=True, indent=2).encode(),
            )
            _write_zip_file(
                archive,
                "attestations/publisher.json",
                json.dumps(publisher, sort_keys=True, indent=2).encode(),
            )
            _write_zip_file(
                archive,
                "signatures/publisher.sig",
                json.dumps(signature, sort_keys=True, indent=2).encode(),
            )
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)

    inspected = ServicePackageArchive.inspect(output)
    sidecar = {
        "publisher_key": parsed.publisher_key,
        "display_name": "AI2Apps Local Model Providers",
        "key_id": key_id,
        "algorithm": "ed25519",
        "public_key": base64.b64encode(public).decode(),
        "package_digest": inspected.digest,
        "ephemeral": ephemeral,
    }
    sidecar_path = output.with_suffix(output.suffix + ".publisher.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    if ephemeral:
        private_path = output.with_suffix(output.suffix + ".private.pem")
        private_path.write_bytes(
            private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        private_path.chmod(0o600)
    return {
        "artifact": str(output),
        "publisher": str(sidecar_path),
        "digest": inspected.digest,
        "models": [item["id"] for item in inspected.manifest.models],
        "ephemeral_key": ephemeral,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--private-key", type=Path)
    args = parser.parse_args()
    manifest = yaml.safe_load((args.source / "service.yaml").read_text(encoding="utf-8"))
    output = args.output or (
        args.source / "dist" / f"{manifest['id']}-{manifest['version']}.ai2service"
    )
    report = build(args.source, output.resolve(), args.private_key)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
