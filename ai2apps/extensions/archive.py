"""Fail-closed parser for `.ai2agent`, `.ai2app`, and `.ai2patch` archives."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ai2apps.packages.archive import package_digest
from ai2apps.packages.models import PackageFile

from .models import BundleFile, ExtensionError, InspectedBundle, UnitKind

MAX_FILES = 4096
MAX_BYTES = 128 * 1024 * 1024


class InteractiveArchive:
    @staticmethod
    def _safe(name: str) -> str:
        path = PurePosixPath(name)
        if not name or name.startswith("/") or "\\" in name or ".." in path.parts:
            raise ExtensionError(
                "unsafe_archive_path", f"Unsafe archive path: {name!r}"
            )
        value = path.as_posix()
        if value in {".", ""}:
            raise ExtensionError("unsafe_archive_path", "Empty archive path")
        return value

    @classmethod
    def inspect(cls, archive_path: str | Path) -> InspectedBundle:
        path = Path(archive_path).resolve(strict=True)
        suffixes = {
            ".ai2agent": (UnitKind.AGENT, "agent.yaml"),
            ".ai2app": (UnitKind.APP, "app.yaml"),
            ".ai2patch": ("patch", "patch.yaml"),
        }
        if path.suffix not in suffixes:
            raise ExtensionError(
                "unsupported_package", "Expected .ai2agent, .ai2app, or .ai2patch"
            )
        kind, manifest_name = suffixes[path.suffix]
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_FILES:
                    raise ExtensionError(
                        "package_file_limit", "Package has too many files"
                    )
                names: set[str] = set()
                total = 0
                for info in infos:
                    name = cls._safe(info.filename)
                    if name in names:
                        raise ExtensionError(
                            "duplicate_archive_path", f"Duplicate archive path: {name}"
                        )
                    names.add(name)
                    total += info.file_size
                    mode = info.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise ExtensionError(
                            "archive_link_denied", "Archive links are forbidden"
                        )
                if total > MAX_BYTES:
                    raise ExtensionError("package_size_limit", "Package is too large")
                required = {manifest_name, "META/files.json", "META/sbom.spdx.json"}
                if not required.issubset(names):
                    raise ExtensionError(
                        "package_file_missing", "Required package metadata is missing"
                    )
                manifest = yaml.safe_load(archive.read(manifest_name))
                index = json.loads(archive.read("META/files.json"))
                sbom = json.loads(archive.read("META/sbom.spdx.json"))
                signature_name = (
                    "signatures/device.sig"
                    if kind == "patch"
                    else "signatures/publisher.sig"
                )
                attestation_name = (
                    "attestations/device.json"
                    if kind == "patch"
                    else "attestations/publisher.json"
                )
                signature = json.loads(archive.read(signature_name))
                attestation = json.loads(archive.read(attestation_name))
                files = cls._validate_files(archive, index, names)
        except (
            zipfile.BadZipFile,
            KeyError,
            json.JSONDecodeError,
            yaml.YAMLError,
        ) as error:
            raise ExtensionError(
                "invalid_package", "Package metadata is invalid"
            ) from error
        cls._validate_manifest(kind, manifest, {item.path for item in files})
        if sbom.get("spdxVersion") not in {"SPDX-2.2", "SPDX-2.3"}:
            raise ExtensionError("invalid_sbom", "An SPDX 2.2/2.3 SBOM is required")
        digest = package_digest(
            manifest,
            tuple(
                PackageFile(item.path, item.content_hash, item.size_bytes)
                for item in files
            ),
        )
        if attestation.get("package_digest") != digest:
            raise ExtensionError(
                "attestation_digest_mismatch", "Attestation does not cover this package"
            )
        key = manifest["target"]["id"] if kind == "patch" else manifest["id"]
        return InspectedBundle(
            kind,
            key,
            str(manifest["version"]),
            digest,
            manifest,
            files,
            sbom,
            signature,
            attestation,
            path,
        )

    @classmethod
    def _validate_files(cls, archive, index, names) -> tuple[BundleFile, ...]:
        rows = index.get("files") if isinstance(index, dict) else None
        if not isinstance(rows, list):
            raise ExtensionError("invalid_file_index", "files.json must contain files")
        excluded = {
            "META/files.json",
            "signatures/publisher.sig",
            "signatures/device.sig",
            "attestations/publisher.json",
            "attestations/device.json",
        }
        expected = names - excluded
        result = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ExtensionError("invalid_file_index", "Invalid file entry")
            name = cls._safe(str(row.get("path", "")))
            if name in seen or name not in expected:
                raise ExtensionError(
                    "invalid_file_index", f"Unexpected indexed file: {name}"
                )
            content = archive.read(name)
            digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
            if row.get("sha256") != digest or row.get("size") != len(content):
                raise ExtensionError(
                    "package_hash_mismatch", f"Hash/size mismatch: {name}"
                )
            seen.add(name)
            result.append(BundleFile(name, digest, len(content)))
        if seen != expected:
            raise ExtensionError(
                "incomplete_file_index", "File index coverage is incomplete"
            )
        return tuple(sorted(result, key=lambda item: item.path))

    @staticmethod
    def _validate_manifest(kind, manifest, files: set[str]) -> None:
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("version"), str
        ):
            raise ExtensionError("invalid_manifest", "Manifest/version is invalid")
        if kind == "patch":
            if manifest.get("schema") != "ai2apps.patch/v1" or not isinstance(
                manifest.get("target"), dict
            ):
                raise ExtensionError(
                    "invalid_patch_manifest", "Patch target is invalid"
                )
            if manifest["target"].get("kind") not in {"agent", "app"} or not manifest[
                "target"
            ].get("id"):
                raise ExtensionError("invalid_patch_target", "Patch target is invalid")
            if not isinstance(manifest.get("base_digest"), str) or not isinstance(
                manifest.get("operations"), list
            ):
                raise ExtensionError(
                    "invalid_patch_manifest", "Patch base/operations are required"
                )
            return
        schema = f"ai2apps.{kind.value}/v1"
        if manifest.get("schema") != schema or not isinstance(manifest.get("id"), str):
            raise ExtensionError("invalid_manifest", f"Expected {schema}")
        if not isinstance(manifest.get("publisher"), dict) or not manifest[
            "publisher"
        ].get("id"):
            raise ExtensionError("invalid_publisher", "Publisher identity is required")
        if kind is UnitKind.AGENT:
            if not isinstance(manifest.get("executor", {}).get("key"), str):
                raise ExtensionError(
                    "invalid_agent_executor", "Agent executor key is required"
                )
            invocation_schema = manifest.get(
                "invocation_schema", {"type": "object", "properties": {}}
            )
            if not isinstance(invocation_schema, dict):
                raise ExtensionError(
                    "invalid_agent_invocation", "invocation_schema must be an object"
                )
            try:
                Draft202012Validator.check_schema(invocation_schema)
            except SchemaError as error:
                raise ExtensionError(
                    "invalid_agent_invocation", f"Invalid invocation_schema: {error.message}"
                ) from error
            if invocation_schema.get("type", "object") != "object":
                raise ExtensionError(
                    "invalid_agent_invocation",
                    "invocation_schema must describe an object",
                )
            if "discoverable" in manifest and not isinstance(
                manifest["discoverable"], bool
            ):
                raise ExtensionError(
                    "invalid_agent_invocation", "discoverable must be boolean"
                )
            if "aliases" in manifest and (
                not isinstance(manifest["aliases"], list)
                or not all(isinstance(item, str) and item for item in manifest["aliases"])
            ):
                raise ExtensionError(
                    "invalid_agent_invocation", "aliases must be non-empty strings"
                )
            if "invocation_ui" in manifest and not isinstance(
                manifest["invocation_ui"], dict
            ):
                raise ExtensionError(
                    "invalid_agent_invocation", "invocation_ui must be an object"
                )
        else:
            entry = manifest.get("entry")
            if not isinstance(entry, dict) or entry.get("kind") not in {
                "host",
                "schema",
                "safe-html",
                "sandbox",
            }:
                raise ExtensionError(
                    "invalid_app_entry", "Every App requires a valid Entry"
                )
            resource = entry.get("resource")
            if resource and resource not in files:
                raise ExtensionError(
                    "entry_resource_missing", "Entry resource is not indexed"
                )
            mini = manifest.get("mini_entry")
            if mini is not None:
                if not isinstance(mini, dict) or mini.get("kind") not in {
                    "schema",
                    "safe-html",
                    "sandbox",
                }:
                    raise ExtensionError(
                        "invalid_mini_entry", "Mini-Entry renderer is invalid"
                    )
                if mini.get("resource") not in files:
                    raise ExtensionError(
                        "mini_entry_resource_missing",
                        "Mini-Entry resource is not indexed",
                    )
            mobile = manifest.get("mobile")
            if mobile is not None and (
                not isinstance(mobile, dict)
                or not isinstance(mobile.get("ready"), bool)
            ):
                raise ExtensionError(
                    "invalid_mobile_declaration",
                    "mobile.ready must be a boolean",
                )
            mobile_entry = manifest.get("mobile_entry")
            if mobile_entry is not None:
                if not isinstance(mobile_entry, dict) or mobile_entry.get(
                    "kind"
                ) not in {"schema", "safe-html", "sandbox"}:
                    raise ExtensionError(
                        "invalid_mobile_entry", "Mobile-Entry renderer is invalid"
                    )
                if mobile_entry.get("resource") not in files:
                    raise ExtensionError(
                        "mobile_entry_resource_missing",
                        "Mobile-Entry resource is not indexed",
                    )
            if isinstance(mobile, dict) and mobile.get("ready") is True:
                selected = mobile_entry or mini or entry
                if not isinstance(selected, dict):
                    raise ExtensionError(
                        "mobile_entry_missing",
                        "Mobile Ready App has no usable Entry",
                    )
                if selected.get("kind") == "host":
                    raise ExtensionError(
                        "mobile_host_renderer_denied",
                        "Third-party Mobile Apps cannot use a host renderer",
                    )
