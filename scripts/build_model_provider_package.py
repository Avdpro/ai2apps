#!/usr/bin/env python3
"""Build a signed local-development `.ai2service` model provider archive."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ai2apps.checkpoint_package_policy import require_checkpoint_distributions
from ai2apps.packages import PackageFile, package_digest
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.secrets.factory import create_secret_backend

EXCLUDED = {
    "META/files.json",
    "attestations/publisher.json",
    "signatures/publisher.sig",
}


def _private_key(
    path: Path | None,
    *,
    keychain_secret: str | None = None,
    keychain_namespace: str | None = None,
) -> tuple[Ed25519PrivateKey, bool]:
    if path is not None and keychain_secret is not None:
        raise ValueError("Choose either --private-key or --keychain-secret")
    if keychain_secret is not None:
        if not keychain_namespace:
            raise ValueError("--keychain-namespace is required with --keychain-secret")
        backend = create_secret_backend(
            Path.home() / ".omlx" / "platform" / "secrets",
            namespace=keychain_namespace,
        )
        encoded = backend.load(keychain_secret).encode("ascii")
        value = serialization.load_pem_private_key(encoded, password=None)
        if not isinstance(value, Ed25519PrivateKey):
            raise TypeError("Publisher key must be Ed25519")
        return value, False
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
    compression = (
        zipfile.ZIP_STORED
        if name.endswith((".dmg", ".tar.gz"))
        else zipfile.ZIP_DEFLATED
    )
    archive.writestr(info, content, compress_type=compression)


def _write_zip_path(archive: zipfile.ZipFile, name: str, source: Path) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.compress_type = (
        zipfile.ZIP_STORED
        if name.endswith((".dmg", ".tar.gz"))
        else zipfile.ZIP_DEFLATED
    )
    info.file_size = source.stat().st_size
    with source.open("rb") as input_file, archive.open(
        info, "w", force_zip64=True
    ) as output_file:
        shutil.copyfileobj(input_file, output_file, length=1024 * 1024)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build(
    source: Path,
    output: Path,
    key_path: Path | None,
    *,
    keychain_secret: str | None = None,
    keychain_namespace: str | None = None,
    key_id: str | None = None,
) -> dict:
    source = source.resolve(strict=True)
    manifest_path = source / "service.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing {manifest_path}")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    require_checkpoint_distributions(manifest)
    parsed = ServicePackageArchive._manifest(manifest)
    private, ephemeral = _private_key(
        key_path,
        keychain_secret=keychain_secret,
        keychain_namespace=keychain_namespace,
    )

    immutable: dict[str, Path] = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(source).as_posix()
        if (
            relative in EXCLUDED
            or relative.startswith("dist/")
            or relative == "README.md"
            or "__pycache__" in path.parts
            or path.suffix in {".pyc", ".pyo"}
        ):
            continue
        immutable[relative] = path
    files = tuple(
        PackageFile(
            path=name,
            content_hash="sha256:" + _file_sha256(path),
            size_bytes=path.stat().st_size,
        )
        for name, path in immutable.items()
    )
    digest = package_digest(manifest, files)
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    key_id = key_id or f"{parsed.publisher_key}:local"
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
            for name, path in immutable.items():
                _write_zip_path(archive, name, path)
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
    parser.add_argument("--keychain-secret")
    parser.add_argument("--keychain-namespace")
    parser.add_argument("--key-id")
    args = parser.parse_args()
    manifest = yaml.safe_load((args.source / "service.yaml").read_text(encoding="utf-8"))
    output = args.output or (
        args.source / "dist" / f"{manifest['id']}-{manifest['version']}.ai2service"
    )
    report = build(
        args.source,
        output.resolve(),
        args.private_key,
        keychain_secret=args.keychain_secret,
        keychain_namespace=args.keychain_namespace,
        key_id=args.key_id,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
