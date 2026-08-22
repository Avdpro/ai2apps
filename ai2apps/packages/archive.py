"""Safe `.ai2service` archive parsing and canonical package digesting."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from ai2apps.model_providers import (
    ModelProviderContractError,
    validate_package_models,
)
from ai2apps.services import ServiceDependency, ServiceRuntimeMode

from .models import (
    InspectedServicePackage,
    PackageError,
    PackageFile,
    ServicePackageManifest,
)

MAX_PACKAGE_FILES = 10_000
MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_METADATA_BYTES = 4 * 1024 * 1024
_SERVICE_KEY = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?$")
_INDEX_EXCLUSIONS = frozenset({"META/files.json"})
_UNINDEXED_PREFIXES = ("signatures/", "attestations/")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _validate_external_endpoint(value: Any) -> str:
    """Accept only a local HTTP endpoint for an installed external Service.

    A Package Tool may receive explicitly granted Secret values. Allowing its
    endpoint to name an arbitrary remote host would turn that grant into an
    implicit data-egress permission and make DNS rebinding relevant. Remote AI
    providers use the separate Host-controlled Provider/Cloud integrations.
    """

    if not isinstance(value, str):
        raise PackageError(
            "missing_endpoint", "External Service requires runtime.endpoint"
        )
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise PackageError(
            "invalid_external_endpoint", "External Service endpoint is invalid"
        ) from error
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port is None
        or parsed.query
        or parsed.fragment
    ):
        raise PackageError(
            "external_endpoint_not_local",
            "Installed external Services must use an explicit loopback HTTP port",
        )
    return value


def _validate_managed_endpoint(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value.count("{port}") > 1:
        raise PackageError(
            "invalid_managed_endpoint", "Managed Service endpoint is invalid"
        )
    probe = value.replace("{port}", "1")
    try:
        _validate_external_endpoint(probe)
    except PackageError as error:
        raise PackageError(
            "managed_endpoint_not_local",
            "Managed Services must use a loopback HTTP endpoint",
        ) from error
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def package_digest(manifest: dict[str, Any], files: tuple[PackageFile, ...]) -> str:
    index = [
        {"path": item.path, "sha256": item.content_hash, "size": item.size_bytes}
        for item in sorted(files, key=lambda item: item.path)
    ]
    value = (
        b"ai2apps.service/v1\n"
        + canonical_json(manifest)
        + b"\n"
        + canonical_json(index)
    )
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


class ServicePackageArchive:
    @classmethod
    def inspect(cls, archive_path: str | Path) -> InspectedServicePackage:
        path = Path(archive_path).expanduser().resolve(strict=True)
        if not path.is_file():
            raise PackageError(
                "archive_not_found", f"Package archive not found: {path}"
            )
        try:
            with zipfile.ZipFile(path) as archive:
                entries = cls._entries(archive)
                manifest_raw = cls._metadata(
                    archive, entries, "service.yaml", yaml.safe_load
                )
                manifest = cls._manifest(manifest_raw)
                index_raw = cls._metadata(
                    archive, entries, "META/files.json", json.loads
                )
                files = cls._verify_index(archive, entries, index_raw)
                sbom = cls._metadata(
                    archive, entries, "META/sbom.spdx.json", json.loads
                )
                cls._validate_sbom(sbom, manifest)
                cls._validate_native_artifacts(archive, manifest, files, sbom)
                digest = package_digest(manifest.raw, files)
                publisher = cls._metadata(
                    archive, entries, "attestations/publisher.json", json.loads
                )
                signature = cls._signature(archive, entries)
                bundled = []
                for name in sorted(entries):
                    if (
                        name.startswith("attestations/")
                        and name.endswith(".json")
                        and name != "attestations/publisher.json"
                    ):
                        bundled.append(
                            cls._metadata(archive, entries, name, json.loads)
                        )
                if publisher.get("package_digest") != digest:
                    raise PackageError(
                        "publisher_digest_mismatch",
                        "Publisher attestation does not reference the canonical package digest",
                    )
                if publisher.get("publisher_id") != manifest.publisher_key:
                    raise PackageError(
                        "publisher_mismatch",
                        "Manifest and publisher attestation disagree",
                    )
                return InspectedServicePackage(
                    archive_path=path,
                    digest=digest,
                    manifest=manifest,
                    files=files,
                    sbom=sbom,
                    publisher_attestation=publisher,
                    signature=signature,
                    bundled_attestations=tuple(bundled),
                    total_size_bytes=sum(item.file_size for item in entries.values()),
                )
        except zipfile.BadZipFile as error:
            raise PackageError(
                "invalid_archive", "Package is not a valid ZIP archive"
            ) from error

    @staticmethod
    def _entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
        entries: dict[str, zipfile.ZipInfo] = {}
        total = 0
        for item in archive.infolist():
            if item.is_dir():
                continue
            path = PurePosixPath(item.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in item.filename
                or "\x00" in item.filename
                or item.filename != path.as_posix()
            ):
                raise PackageError(
                    "unsafe_archive_path", f"Unsafe package path: {item.filename}"
                )
            if item.filename in entries:
                raise PackageError(
                    "duplicate_archive_path", f"Duplicate package path: {item.filename}"
                )
            # ZIP external mode identifies symlinks on Unix.
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise PackageError(
                    "archive_symlink_denied", f"Package symlink denied: {item.filename}"
                )
            if item.file_size < 0 or item.file_size > MAX_PACKAGE_BYTES:
                raise PackageError(
                    "package_size_limit", "Package entry exceeds size limit"
                )
            total += item.file_size
            entries[item.filename] = item
        if len(entries) > MAX_PACKAGE_FILES or total > MAX_PACKAGE_BYTES:
            raise PackageError(
                "package_size_limit", "Package exceeds bounded file or byte limit"
            )
        return entries

    @staticmethod
    def _metadata(archive, entries, name: str, parser):
        item = entries.get(name)
        if item is None:
            raise PackageError(
                "missing_package_file", f"Required package file missing: {name}"
            )
        if item.file_size > MAX_METADATA_BYTES:
            raise PackageError(
                "metadata_size_limit", f"Package metadata is too large: {name}"
            )
        try:
            text = archive.read(item).decode("utf-8")
            value = parser(text)
        except Exception as error:
            raise PackageError(
                "invalid_package_metadata", f"Invalid package metadata: {name}"
            ) from error
        if not isinstance(value, dict):
            raise PackageError(
                "invalid_package_metadata", f"{name} must contain an object"
            )
        return value

    @classmethod
    def _manifest(cls, raw: dict[str, Any]) -> ServicePackageManifest:
        if raw.get("schema") != "ai2apps.service/v1":
            raise PackageError(
                "unsupported_package_schema", "Expected ai2apps.service/v1"
            )
        service_key = raw.get("id")
        name = raw.get("name")
        version = raw.get("version")
        publisher = raw.get("publisher", {})
        runtime = raw.get("runtime", {})
        if not isinstance(service_key, str) or not _SERVICE_KEY.fullmatch(service_key):
            raise PackageError("invalid_service_id", "Manifest Service id is invalid")
        if not isinstance(name, str) or not name.strip():
            raise PackageError("invalid_manifest", "Manifest name is required")
        try:
            Version(str(version))
        except InvalidVersion as error:
            raise PackageError(
                "invalid_version", "Manifest version is not PEP 440 compatible"
            ) from error
        publisher_key = publisher.get("id") if isinstance(publisher, dict) else None
        if not isinstance(publisher_key, str) or not _SERVICE_KEY.fullmatch(
            publisher_key
        ):
            raise PackageError("invalid_publisher", "Manifest publisher.id is invalid")
        mode_value = runtime.get("mode") if isinstance(runtime, dict) else None
        aliases = {"embedded": "in_process", "process": "managed_process"}
        try:
            mode = ServiceRuntimeMode(aliases.get(mode_value, mode_value))
        except ValueError as error:
            raise PackageError(
                "invalid_runtime", "Unsupported Service runtime mode"
            ) from error
        protocol = runtime.get("protocol", "http-json")
        if protocol not in {
            "http-json",
            "mcp",
            "openai-compatible",
            "internal-asgi",
            "ai2apps-model-worker/v1",
            "ai2apps-inference-runtime/v1",
        }:
            raise PackageError("invalid_protocol", "Unsupported Service protocol")
        command = runtime.get("command", [])
        if not isinstance(command, list) or not all(
            isinstance(x, str) and x for x in command
        ):
            raise PackageError(
                "invalid_entrypoint", "runtime.command must be a string array"
            )
        entrypoint = runtime.get("entrypoint")
        endpoint = runtime.get("endpoint")
        model_worker = protocol == "ai2apps-model-worker/v1"
        inference_runtime = protocol == "ai2apps-inference-runtime/v1"
        if mode is ServiceRuntimeMode.MANAGED_PROCESS and not command and not (
            model_worker or inference_runtime
        ):
            raise PackageError(
                "missing_entrypoint", "Managed Service requires runtime.command"
            )
        if model_worker:
            adapter = runtime.get("adapter")
            if mode is not ServiceRuntimeMode.MANAGED_PROCESS:
                raise PackageError(
                    "invalid_model_worker",
                    "Model Worker Packages must use runtime.mode: process",
                )
            if command:
                raise PackageError(
                    "invalid_model_worker",
                    "Model Worker startup is system-owned; runtime.command is not allowed",
                )
            if (
                not isinstance(adapter, str)
                or not adapter
                or adapter.startswith("/")
                or ".." in adapter.partition(":")[0].split("/")
                or ":" not in adapter
            ):
                raise PackageError(
                    "invalid_model_worker",
                    "runtime.adapter must be a package-relative path and factory, for example src/adapter.py:create_adapter",
                )
        if inference_runtime:
            from .inference_runtime import validate_inference_runtime_manifest

            validate_inference_runtime_manifest(raw)
        if mode is ServiceRuntimeMode.MANAGED_PROCESS:
            endpoint = _validate_managed_endpoint(endpoint)
        if mode is ServiceRuntimeMode.EXTERNAL:
            endpoint = _validate_external_endpoint(endpoint)
        dependencies = []
        requires = raw.get("requires", {})
        service_requires = (
            requires.get("services", []) if isinstance(requires, dict) else []
        )
        if not isinstance(service_requires, list):
            raise PackageError(
                "invalid_dependencies", "requires.services must be an array"
            )
        for dependency in service_requires:
            if not isinstance(dependency, dict) or not isinstance(
                dependency.get("id"), str
            ):
                raise PackageError(
                    "invalid_dependencies", "Service dependency is invalid"
                )
            spec = str(dependency.get("version", "*"))
            try:
                SpecifierSet("" if spec == "*" else spec)
            except InvalidSpecifier as error:
                raise PackageError(
                    "invalid_dependencies", f"Invalid dependency range: {spec}"
                ) from error
            dependencies.append(
                ServiceDependency(
                    dependency["id"], spec, bool(dependency.get("optional", False))
                )
            )
            required_capabilities = dependency.get("capabilities", [])
            if not isinstance(required_capabilities, list) or not all(
                isinstance(item, str) and item for item in required_capabilities
            ):
                raise PackageError(
                    "invalid_dependencies",
                    "Service dependency capabilities must be an array of strings",
                )
        permissions = raw.get("permissions", {})
        compatibility = raw.get("compatibility", {})
        health = raw.get("health", {})
        restart = raw.get("restart", {})
        tools = raw.get("tools", [])
        try:
            models = validate_package_models(
                service_key,
                raw.get("models", []),
                runtime_mode=str(mode_value),
                protocol=str(protocol),
            )
        except ModelProviderContractError as error:
            raise PackageError("invalid_models", str(error)) from error
        capabilities = raw.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) and item for item in capabilities
        ):
            raise PackageError(
                "invalid_manifest", "Manifest capabilities must be strings"
            )
        if not all(
            isinstance(value, dict)
            for value in (permissions, compatibility, health, restart)
        ):
            raise PackageError(
                "invalid_manifest", "Manifest policy sections must be objects"
            )
        if not isinstance(tools, list) or not all(
            isinstance(item, dict) for item in tools
        ):
            raise PackageError(
                "invalid_manifest", "Manifest tools must be an array of objects"
            )
        return ServicePackageManifest(
            service_key=service_key,
            name=name.strip(),
            version=str(version),
            publisher_key=publisher_key,
            runtime_mode=mode,
            protocol=protocol,
            entrypoint=entrypoint if isinstance(entrypoint, str) else None,
            command=tuple(command),
            endpoint=endpoint if isinstance(endpoint, str) else None,
            contract=runtime.get("contract")
            if isinstance(runtime.get("contract"), str)
            else None,
            capabilities=tuple(sorted(set(capabilities))),
            dependencies=tuple(dependencies),
            permissions=permissions,
            compatibility=compatibility,
            health=health,
            restart=restart,
            tools=tuple(tools),
            models=models,
            raw=raw,
        )

    @staticmethod
    def _verify_index(archive, entries, raw: dict[str, Any]) -> tuple[PackageFile, ...]:
        values = raw.get("files")
        if not isinstance(values, list):
            raise PackageError(
                "invalid_file_index", "META/files.json needs a files array"
            )
        indexed: dict[str, PackageFile] = {}
        for value in values:
            if not isinstance(value, dict):
                raise PackageError(
                    "invalid_file_index", "File index entry must be an object"
                )
            path = value.get("path")
            digest = value.get("sha256")
            size = value.get("size")
            if (
                not isinstance(path, str)
                or path in indexed
                or not isinstance(digest, str)
                or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", digest)
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
            ):
                raise PackageError(
                    "invalid_file_index", f"Invalid file index entry: {path!r}"
                )
            item = entries.get(path)
            if item is None or item.file_size != size:
                raise PackageError("file_index_mismatch", f"File size mismatch: {path}")
            content = archive.read(item)
            actual = hashlib.sha256(content).hexdigest()
            expected = digest.removeprefix("sha256:")
            if actual != expected:
                raise PackageError("file_hash_mismatch", f"File hash mismatch: {path}")
            indexed[path] = PackageFile(
                path, f"sha256:{actual}", size, mimetypes.guess_type(path)[0]
            )
        expected_paths = {
            name
            for name in entries
            if name not in _INDEX_EXCLUSIONS
            and not name.startswith(_UNINDEXED_PREFIXES)
        }
        if set(indexed) != expected_paths:
            raise PackageError(
                "incomplete_file_index",
                "File index does not exactly cover immutable package content",
                details={
                    "missing": sorted(expected_paths - set(indexed)),
                    "unexpected": sorted(set(indexed) - expected_paths),
                },
            )
        return tuple(sorted(indexed.values(), key=lambda item: item.path))

    @staticmethod
    def _validate_sbom(sbom: dict[str, Any], manifest: ServicePackageManifest) -> None:
        if sbom.get("spdxVersion") not in {"SPDX-2.2", "SPDX-2.3"}:
            raise PackageError("invalid_sbom", "SBOM must be SPDX 2.2 or 2.3 JSON")
        if not isinstance(sbom.get("SPDXID"), str):
            raise PackageError("invalid_sbom", "SBOM requires SPDXID")
        name = sbom.get("name")
        if not isinstance(name, str) or not name:
            raise PackageError("invalid_sbom", "SBOM requires a document name")

    @staticmethod
    def _validate_native_artifacts(
        archive,
        manifest: ServicePackageManifest,
        files: tuple[PackageFile, ...],
        sbom: dict[str, Any],
    ) -> None:
        indexed = {item.path: item for item in files}
        declarations = manifest.raw.get("native_artifacts", [])
        if not isinstance(declarations, list) or not all(
            isinstance(item, dict) and isinstance(item.get("path"), str)
            for item in declarations
        ):
            raise PackageError(
                "invalid_native_artifacts", "Native artifact declarations are invalid"
            )
        declared = {item["path"]: item for item in declarations}
        sbom_files = {
            item.get("fileName"): item
            for item in sbom.get("files", [])
            if isinstance(item, dict)
        }
        native_paths = set()
        for path, item in indexed.items():
            header = archive.read(path)[:4]
            if (
                header == b"\x7fELF"
                or header[:2] == b"MZ"
                or header
                in {
                    b"\xfe\xed\xfa\xce",
                    b"\xfe\xed\xfa\xcf",
                    b"\xce\xfa\xed\xfe",
                    b"\xcf\xfa\xed\xfe",
                    b"\xca\xfe\xba\xbe",
                }
            ):
                native_paths.add(path)
                declaration = declared.get(path)
                if declaration is None:
                    raise PackageError(
                        "undeclared_native_artifact",
                        f"Native executable is not declared: {path}",
                    )
                if declaration.get("sha256", "").removeprefix(
                    "sha256:"
                ) != item.content_hash.removeprefix("sha256:"):
                    raise PackageError(
                        "native_artifact_hash_mismatch",
                        f"Native artifact declaration hash differs: {path}",
                    )
                if not declaration.get("architectures"):
                    raise PackageError(
                        "native_artifact_platform_missing",
                        f"Native artifact lacks architecture selection: {path}",
                    )
                if path not in sbom_files:
                    raise PackageError(
                        "native_artifact_missing_from_sbom",
                        f"Native artifact is absent from the SPDX SBOM: {path}",
                    )
        unexpected = set(declared) - native_paths
        if unexpected:
            raise PackageError(
                "native_artifact_declaration_invalid",
                "Native artifact declaration references a non-native or absent file",
                details={"paths": sorted(unexpected)},
            )

    @staticmethod
    def _signature(archive, entries) -> dict[str, Any]:
        item = entries.get("signatures/publisher.sig")
        if item is None or item.file_size > 64 * 1024:
            raise PackageError("missing_signature", "Publisher signature is required")
        text = archive.read(item).decode("utf-8").strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            value = {"algorithm": "ed25519", "signature": text}
        if (
            not isinstance(value, dict)
            or value.get("algorithm") != "ed25519"
            or not isinstance(value.get("signature"), str)
        ):
            raise PackageError(
                "invalid_signature", "Publisher signature metadata is invalid"
            )
        try:
            base64.b64decode(value["signature"], validate=True)
        except ValueError as error:
            raise PackageError(
                "invalid_signature", "Publisher signature is not base64"
            ) from error
        return value

    @staticmethod
    def extract(inspected: InspectedServicePackage, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        try:
            with zipfile.ZipFile(inspected.archive_path) as archive:
                entries = ServicePackageArchive._entries(archive)
                for name, item in entries.items():
                    target = destination.joinpath(*PurePosixPath(name).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(item))
        except BaseException:
            import shutil

            shutil.rmtree(destination, ignore_errors=True)
            raise
