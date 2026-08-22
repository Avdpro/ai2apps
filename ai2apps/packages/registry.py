"""Public Registry discovery, authenticated download, and local installation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import tempfile
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.extensions import ExtensionError, UnitKind
from ai2apps.extensions.models import BundleFile, InspectedBundle
from ai2apps.localization import (
    localized_package_metadata,
    package_localizations_for_manifest,
)
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.models import (
    InspectedServicePackage,
    PackageFile,
    PackageStatus,
    TrustStatus,
)
from ai2apps.secrets import SecretRepository

from .contract_v1 import (
    MAX_ARTIFACT_BYTES,
    PackageContractError,
    build_package,
    create_key_proof,
    create_signature_envelope,
    generate_publisher_key,
    inspect_package,
    public_key_fingerprint,
    verify_repository_snapshot,
    verify_signed_package,
)
from .repository_config import AI2APPS_REPOSITORY_FINGERPRINT

# Backwards-compatible public name; the authoritative value lives in the
# lightweight repository_config module shared by Registry and model adapters.
DEFAULT_REPOSITORY_FINGERPRINT = AI2APPS_REPOSITORY_FINGERPRINT
MAX_SUBMISSION_BYTES = 25 * 1024 * 1024
MAX_PLATFORM_RUNTIME_SUBMISSION_BYTES = 512 * 1024 * 1024
PLATFORM_RUNTIME_PACKAGE_ID = "ai2apps/runtime-omlx"


class RegistryError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise RegistryError("repository_metadata_invalid", "Repository timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise RegistryError("repository_metadata_invalid", "Repository timestamp requires a timezone")
    return parsed.astimezone(UTC)


class RegistryPackageManager:
    def __init__(
        self,
        *,
        cloud: AI2AppsCloudClient,
        root: Path,
        secrets: SecretRepository,
        extension_manager,
        service_manager,
        repository_fingerprint: str | None = None,
    ) -> None:
        self.cloud = cloud
        self.root = root / "registry-v1"
        self.secrets = secrets
        self.extension_manager = extension_manager
        self.service_manager = service_manager
        self.repository_fingerprint = (
            repository_fingerprint
            or os.environ.get("AI2APPS_REPOSITORY_KEY_FINGERPRINT")
            or DEFAULT_REPOSITORY_FINGERPRINT
        ).removeprefix("sha256:")
        self.state_path = self.root / "state.json"

    def for_cloud(self, cloud: AI2AppsCloudClient) -> RegistryPackageManager:
        """Bind shared local package state to one request-scoped Cloud session."""

        return type(self)(
            cloud=cloud,
            root=self.root.parent,
            secrets=self.secrets,
            extension_manager=self.extension_manager,
            service_manager=self.service_manager,
            repository_fingerprint=self.repository_fingerprint,
        )

    async def _json(self, method: str, path: str, **kwargs) -> Any:
        response = await self.cloud.request(method, path, **kwargs)
        try:
            if response.status_code >= 400:
                try:
                    data = response.json()
                except ValueError:
                    data = {}
                error = data.get("error", {}) if isinstance(data, dict) else {}
                raise RegistryError(
                    str(error.get("code") or "registry_request_failed").lower(),
                    str(error.get("message") or f"Registry request failed ({response.status_code})"),
                    details={"status": response.status_code},
                )
            return response.json()
        finally:
            await response.aclose()

    async def search(self, **params) -> Any:
        value = await self._json("GET", "/v1/registry/search", params={key: value for key, value in params.items() if value is not None and value != ""})
        return self._decorate_catalog_compatibility(value)

    async def recommendations(self, **params) -> Any:
        value = await self._json("GET", "/v1/registry/recommendations", params={key: value for key, value in params.items() if value is not None and value != ""})
        return self._decorate_catalog_compatibility(value)

    async def catalog(self, namespace: str, name: str) -> Any:
        value = await self._json("GET", f"/v1/registry/packages/{namespace}/{name}/catalog")
        return self._decorate_catalog_compatibility(value)

    async def package(self, namespace: str, name: str) -> Any:
        return await self._json("GET", f"/v1/registry/packages/{namespace}/{name}")

    def _load_state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {"metadataVersion": 0, "installed": {}}
        return value if isinstance(value, dict) else {"metadataVersion": 0, "installed": {}}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(f".{self.state_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_path)

    async def trusted_snapshot(self) -> dict[str, Any]:
        key_info = await self._json("GET", "/v1/registry/repository-key")
        public_key_pem = key_info.get("publicKeyPem") if isinstance(key_info, dict) else None
        if not isinstance(public_key_pem, str):
            raise RegistryError("repository_key_invalid", "Registry did not return a public key")
        envelope = await self._json("GET", "/v1/registry/metadata/latest")
        try:
            payload = verify_repository_snapshot(
                envelope,
                public_key_pem,
                pinned_fingerprint=self.repository_fingerprint,
            )
        except PackageContractError as error:
            raise RegistryError(error.code, str(error), details=error.details) from error
        now = datetime.now(UTC)
        if _utc(payload["expiresAt"]) <= now:
            raise RegistryError("repository_metadata_expired", "Repository snapshot has expired")
        if _utc(payload["generatedAt"]) > now.replace(microsecond=now.microsecond) and (_utc(payload["generatedAt"]) - now).total_seconds() > 300:
            raise RegistryError("repository_metadata_future", "Repository snapshot is dated in the future")
        state = self._load_state()
        previous = int(state.get("metadataVersion", 0))
        version = int(payload["version"])
        if version < previous:
            raise RegistryError(
                "repository_metadata_rollback",
                "Repository snapshot version moved backwards",
                details={"previous": previous, "received": version},
            )
        if version > previous:
            state["metadataVersion"] = version
            self._save_state(state)
        return payload

    @staticmethod
    def _release(snapshot: dict[str, Any], package_id: str, version: str | None):
        matches = [
            item for item in snapshot.get("releases", [])
            if isinstance(item, dict)
            and item.get("packageId") == package_id
            and (version is None or item.get("version") == version)
        ]
        if not matches:
            raise RegistryError("release_not_found", "Package release is absent from trusted repository metadata")
        if version is None:
            matches.sort(key=lambda item: Version(str(item["version"])), reverse=True)
        release = matches[0]
        if release.get("status") != "published":
            raise RegistryError(
                "release_unavailable",
                f"Release is {release.get('status', 'unavailable')}",
                details={"reason": release.get("statusReason")},
            )
        return release

    @staticmethod
    def _dependency_release(
        snapshot: dict[str, Any], package_id: str, version_spec: str
    ) -> dict[str, Any]:
        try:
            specifier = SpecifierSet(
                "" if version_spec == "*" else version_spec.replace(" ", ",")
            )
        except Exception as error:
            raise RegistryError(
                "dependency_version_invalid",
                f"Dependency version range is invalid: {version_spec}",
            ) from error
        matches = [
            item
            for item in snapshot.get("releases", [])
            if isinstance(item, dict)
            and item.get("packageId") == package_id
            and item.get("status") == "published"
            and Version(str(item.get("version"))) in specifier
        ]
        if not matches:
            raise RegistryError(
                "dependency_unresolved",
                f"No published release satisfies {package_id} {version_spec}",
            )
        return max(matches, key=lambda item: Version(str(item["version"])))

    @staticmethod
    def _dependency_restart_scope(
        package_id: str, release: dict[str, Any]
    ) -> str | None:
        activation = release.get("activation", {})
        scope = (
            activation.get("restartScope")
            if isinstance(activation, dict)
            else None
        )
        if scope in {"local", "app"}:
            return str(scope)
        # The official inference Runtime predates activation metadata in the
        # public Registry contract. Keep its restart behavior stable while
        # newer Runtime-class packages declare it in release metadata.
        if package_id == PLATFORM_RUNTIME_PACKAGE_ID:
            return "local"
        return None

    def _installed_dependency_status(
        self, dependency_id: str, raw_spec: str
    ) -> tuple[bool, dict[str, Any] | None, str | None]:
        stored = self._load_state().get("installed", {}).get(dependency_id)
        specifier = SpecifierSet(
            "" if raw_spec == "*" else raw_spec.replace(" ", ",")
        )
        if not isinstance(stored, dict):
            return False, None, None
        if stored.get("packageType") != "service":
            satisfies = Version(str(stored["version"])) in specifier
            return satisfies, stored, str(stored["version"])
        runtime_key = stored.get("runtimeKey")
        active = (
            self.service_manager.packages.active(runtime_key)
            if isinstance(runtime_key, str) and runtime_key
            else None
        )
        active_version = None if active is None else active.package_version
        satisfies = bool(
            active_version is not None and Version(str(active_version)) in specifier
        )
        return satisfies, stored, active_version

    async def _preflight_restart_dependencies(
        self,
        inspected,
        *,
        stack: tuple[str, ...],
        progress: Callable[[dict[str, Any]], None] | None,
    ) -> None:
        package_id = inspected.manifest["package"]["id"]
        if package_id in stack:
            raise RegistryError(
                "dependency_cycle",
                "Registry Package dependency cycle detected",
                details={"cycle": [*stack, package_id]},
            )
        snapshot: dict[str, Any] | None = None
        for dependency in inspected.manifest["dependencies"]:
            if dependency["optional"]:
                continue
            dependency_id = dependency["packageId"]
            raw_spec = dependency["version"]
            satisfies, stored, active_version = self._installed_dependency_status(
                dependency_id, raw_spec
            )
            if satisfies:
                continue
            if snapshot is None:
                snapshot = await self.trusted_snapshot()
            release = self._dependency_release(snapshot, dependency_id, raw_spec)
            restart_scope = self._dependency_restart_scope(dependency_id, release)
            if restart_scope is not None:
                stored_version = (
                    None if stored is None else str(stored.get("version") or "") or None
                )
                pending_restart = bool(
                    stored_version
                    and Version(stored_version)
                    in SpecifierSet(
                        "" if raw_spec == "*" else raw_spec.replace(" ", ",")
                    )
                    and active_version != stored_version
                )
                release_package = release.get("package")
                release_display_name = (
                    release_package.get("displayName")
                    if isinstance(release_package, dict)
                    else None
                )
                raise RegistryError(
                    "dependency_restart_required",
                    (
                        f"Restart {restart_scope} to activate {dependency_id}"
                        if pending_restart
                        else f"Install or upgrade {dependency_id} before {package_id}"
                    ),
                    details={
                        "targetPackageId": package_id,
                        "dependency": {
                            "packageId": dependency_id,
                            "displayName": release.get("displayName")
                            or release_display_name
                            or dependency_id,
                            "packageType": release.get("packageType", "service"),
                            "requiredVersion": raw_spec,
                            "installedVersion": stored_version,
                            "activeVersion": active_version,
                            "availableVersion": str(release["version"]),
                            "restartScope": restart_scope,
                            "pendingRestart": pending_restart,
                        },
                    },
                )
            dependency_namespace, dependency_name = dependency_id.split("/", 1)
            if progress is None:
                child, _envelope, _release, _metadata = await self.download_verified(
                    dependency_namespace,
                    dependency_name,
                    str(release["version"]),
                )
            else:
                child, _envelope, _release, _metadata = await self.download_verified(
                    dependency_namespace,
                    dependency_name,
                    str(release["version"]),
                    progress=progress,
                    progress_step=1,
                    dependency=True,
                )
            await self._preflight_restart_dependencies(
                child,
                stack=(*stack, package_id),
                progress=progress,
            )

    def _registry_path(self, url: str, fallback: str) -> str:
        parsed = urlparse(url)
        cloud = urlparse(self.cloud.base_url)
        if parsed.scheme and (parsed.scheme, parsed.netloc) != (cloud.scheme, cloud.netloc):
            raise RegistryError("repository_url_invalid", "Repository metadata points outside the configured Cloud origin")
        path = parsed.path if parsed.scheme else url
        if not path.startswith("/v1/registry/"):
            raise RegistryError("repository_url_invalid", "Repository download URL is outside the public Registry")
        return path or fallback

    @staticmethod
    def _report_install_progress(
        progress: Callable[[dict[str, Any]], None] | None,
        **values: Any,
    ) -> None:
        if progress is not None:
            progress(values)

    async def download_verified(
        self,
        namespace: str,
        name: str,
        version: str | None = None,
        *,
        progress: Callable[[dict[str, Any]], None] | None = None,
        progress_step: int = 2,
        dependency: bool = False,
    ):
        package_id = f"{namespace}/{name}"
        snapshot = await self.trusted_snapshot()
        release = self._release(snapshot, package_id, version)
        release_compatibility = release.get("compatibility")
        if isinstance(release_compatibility, dict):
            self._check_compatibility(release_compatibility)
        version = str(release["version"])
        artifact = release["artifact"]
        envelope_path = self._registry_path(
            str(release["envelopeUrl"]),
            f"/v1/registry/packages/{namespace}/{name}/versions/{version}/envelope",
        )
        envelope = await self._json("GET", envelope_path)
        expected_size = int(artifact["size"])
        if not 1 <= expected_size <= MAX_ARTIFACT_BYTES:
            raise RegistryError("artifact_size_limit", "Repository artifact exceeds local limits")
        artifact_path = self._registry_path(
            str(artifact["url"]),
            f"/v1/registry/packages/{namespace}/{name}/versions/{version}/artifact",
        )
        suffix = {"app": ".ai2app", "agent": ".ai2agent", "service": ".ai2service"}[release["packageType"]]
        publisher = release["publisher"]
        key = publisher["key"]
        if public_key_fingerprint(key["publicKeyPem"]) != key["fingerprintSha256"]:
            raise RegistryError("publisher_key_invalid", "Publisher key fingerprint is invalid")
        if envelope.get("payload", {}).get("publisherId") != publisher["id"] or envelope.get("payload", {}).get("publisherKeyId") != key["id"]:
            raise RegistryError("publisher_identity_mismatch", "Envelope publisher is not bound by repository metadata")
        final = self.root / "downloads" / namespace / name / version / f"{artifact['sha256']}{suffix}"
        if final.is_symlink():
            final.unlink(missing_ok=True)
        elif final.exists() and not final.is_file():
            raise RegistryError(
                "artifact_cache_invalid",
                "Registry artifact cache path is not a regular file",
            )
        if final.is_file():
            self._report_install_progress(
                progress,
                currentStep=progress_step,
                stage="verifying_dependency" if dependency else "verifying_package",
                packageId=package_id,
                bytesCompleted=expected_size,
                bytesTotal=expected_size,
            )

            def verify_cached_artifact():
                digest = hashlib.sha256()
                size = 0
                with final.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        size += len(chunk)
                        digest.update(chunk)
                if size != expected_size or digest.hexdigest() != artifact["sha256"]:
                    raise RegistryError(
                        "artifact_digest_mismatch",
                        "Cached artifact bytes do not match trusted repository metadata",
                    )
                try:
                    return verify_signed_package(
                        final,
                        envelope,
                        key["publicKeyPem"],
                        precomputed_hash=(digest.hexdigest(), size),
                    )
                except PackageContractError as error:
                    raise RegistryError(
                        error.code, str(error), details=error.details
                    ) from error

            try:
                inspected = await asyncio.to_thread(verify_cached_artifact)
            except RegistryError:
                final.unlink(missing_ok=True)
            else:
                return inspected, envelope, release, snapshot["version"]
        quarantine = self.root / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix="download-", suffix=suffix, dir=quarantine)
        os.close(handle)
        temporary = Path(temporary_name)
        digest = hashlib.sha256()
        size = 0
        download_stage = "downloading_dependency" if dependency else "downloading_package"
        verify_stage = "verifying_dependency" if dependency else "verifying_package"
        self._report_install_progress(
            progress,
            currentStep=progress_step,
            stage=download_stage,
            packageId=package_id,
            bytesCompleted=0,
            bytesTotal=expected_size,
        )
        response = await self.cloud.request("GET", artifact_path, stream=True, headers={"Accept": str(artifact["mediaType"])})
        try:
            if response.status_code >= 400:
                raise RegistryError("artifact_download_failed", f"Artifact download failed ({response.status_code})")
            with temporary.open("wb") as output:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    size += len(chunk)
                    if size > expected_size or size > MAX_ARTIFACT_BYTES:
                        raise RegistryError("artifact_size_mismatch", "Artifact exceeded its signed size")
                    digest.update(chunk)
                    output.write(chunk)
                    self._report_install_progress(
                        progress,
                        currentStep=progress_step,
                        stage=download_stage,
                        packageId=package_id,
                        bytesCompleted=size,
                        bytesTotal=expected_size,
                    )
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await response.aclose()
        actual_sha256 = digest.hexdigest()
        self._report_install_progress(
            progress,
            currentStep=progress_step,
            stage=verify_stage,
            packageId=package_id,
            bytesCompleted=size,
            bytesTotal=expected_size,
        )
        if size != expected_size or actual_sha256 != artifact["sha256"]:
            temporary.unlink(missing_ok=True)
            raise RegistryError("artifact_digest_mismatch", "Artifact bytes do not match trusted repository metadata")
        try:
            inspected = verify_signed_package(
                temporary,
                envelope,
                key["publicKeyPem"],
                precomputed_hash=(actual_sha256, size),
            )
        except PackageContractError as error:
            temporary.unlink(missing_ok=True)
            raise RegistryError(error.code, str(error), details=error.details) from error
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            temporary.unlink(missing_ok=True)
        else:
            os.replace(temporary, final)
        return inspected.__class__(
            final,
            inspected.sha256,
            inspected.size,
            inspected.media_type,
            inspected.manifest_sha256,
            inspected.manifest,
            inspected.files,
        ), envelope, release, snapshot["version"]

    @staticmethod
    def _local_os_version(local_platform: str) -> str:
        if local_platform == "darwin":
            return platform.mac_ver()[0]
        return platform.release()

    @classmethod
    def _check_compatibility(cls, compatibility: dict[str, Any]) -> None:
        platforms = compatibility.get("platforms", [])
        local_platform = {"Darwin": "darwin", "Linux": "linux", "Windows": "win32"}.get(platform.system(), platform.system().lower())
        if platforms and local_platform not in platforms:
            raise RegistryError(
                "platform_incompatible",
                f"Package does not support {local_platform}",
                details={"current": local_platform, "supported": platforms},
            )
        architectures = compatibility.get("architectures", [])
        local_arch = {"aarch64": "arm64", "AMD64": "x64", "x86_64": "x64"}.get(platform.machine(), platform.machine())
        if architectures and local_arch not in architectures:
            raise RegistryError(
                "architecture_incompatible",
                f"Package does not support {local_arch}",
                details={"current": local_arch, "supported": architectures},
            )
        minimum_os = compatibility.get("minimumOsVersion")
        maximum_os = compatibility.get("maximumOsVersionExclusive")
        if minimum_os or maximum_os:
            current_raw = cls._local_os_version(local_platform)
            try:
                current_os = Version(current_raw)
            except Exception as error:
                raise RegistryError(
                    "os_version_unknown",
                    "The current OS version could not be determined",
                    details={"current": current_raw},
                ) from error
            if minimum_os and current_os < Version(str(minimum_os)):
                raise RegistryError(
                    "os_version_too_old",
                    f"Package requires macOS {minimum_os} or later; this device runs {current_raw}",
                    details={"current": current_raw, "minimum": str(minimum_os)},
                )
            if maximum_os and current_os >= Version(str(maximum_os)):
                raise RegistryError(
                    "os_version_too_new",
                    f"Package requires an OS earlier than {maximum_os}; this device runs {current_raw}",
                    details={
                        "current": current_raw,
                        "maximumExclusive": str(maximum_os),
                    },
                )
        raw_range = compatibility["ai2apps"].strip()
        try:
            specifier = SpecifierSet("" if raw_range == "*" else raw_range.replace(" ", ","))
        except Exception as error:
            raise RegistryError("compatibility_invalid", "Package AI2Apps version range is invalid") from error
        # The local package contract started at 0.1.0. Keep this explicit until
        # the runtime exposes a single product version constant.
        if Version("0.1.0") not in specifier:
            raise RegistryError("ai2apps_incompatible", "Package does not support this AI2Apps contract version")

    @classmethod
    def _compatibility(cls, manifest: dict[str, Any]) -> None:
        cls._check_compatibility(manifest["compatibility"])

    @classmethod
    def _compatibility_status(cls, compatibility: Any) -> dict[str, Any]:
        if not isinstance(compatibility, dict):
            return {"installable": True, "blockers": []}
        try:
            cls._check_compatibility(compatibility)
        except RegistryError as error:
            return {
                "installable": False,
                "blockers": [
                    {
                        "code": error.code,
                        "message": str(error),
                        "details": error.details,
                    }
                ],
            }
        return {"installable": True, "blockers": []}

    @classmethod
    def _decorate_catalog_compatibility(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._decorate_catalog_compatibility(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {
            key: cls._decorate_catalog_compatibility(item)
            for key, item in value.items()
        }
        compatibility = result.get("compatibility")
        if isinstance(compatibility, dict):
            result["installability"] = cls._compatibility_status(compatibility)
        return result

    def _interactive_bundle(self, inspected, envelope) -> InspectedBundle:
        manifest = inspected.manifest
        package = manifest["package"]
        runtime_key = package["id"].replace("/", ".")
        entrypoint = manifest["entrypoints"][0]
        kind = UnitKind(package["type"])
        with zipfile.ZipFile(inspected.archive_path) as archive:
            if kind is UnitKind.APP:
                indexed = {item.path for item in inspected.files}
                if "app.yaml" in indexed:
                    try:
                        app_manifest = yaml.safe_load(
                            archive.read("app.yaml").decode("utf-8", "strict")
                        )
                    except Exception as error:
                        raise RegistryError(
                            "app_definition_invalid",
                            "app.yaml must contain a valid App definition",
                        ) from error
                    if (
                        not isinstance(app_manifest, dict)
                        or app_manifest.get("schema") != "ai2apps.app/v1"
                    ):
                        raise RegistryError(
                            "app_definition_invalid",
                            "app.yaml must use ai2apps.app/v1",
                        )
                    app_manifest = dict(app_manifest)
                    runtime_localizations = package_localizations_for_manifest(
                        package.get("localizations"),
                        app_manifest.get("localizations"),
                    )
                    app_manifest.update(
                        {
                            "id": runtime_key,
                            "name": package["displayName"],
                            "description": package.get("description", ""),
                            "version": package["version"],
                            "publisher": {
                                "id": envelope["payload"]["publisherId"]
                            },
                        }
                    )
                    if runtime_localizations:
                        app_manifest["localizations"] = runtime_localizations
                    entry = app_manifest.get("entry", {})
                    if (
                        not isinstance(entry, dict)
                        or entry.get("resource") != entrypoint["path"]
                    ):
                        raise RegistryError(
                            "app_entrypoint_mismatch",
                            "app.yaml entry must match the signed Package entrypoint",
                        )
                else:
                    suffix = Path(entrypoint["path"]).suffix.lower()
                    app_manifest = {
                        "schema": "ai2apps.app/v1",
                        "id": runtime_key,
                        "name": package["displayName"],
                        "description": package.get("description", ""),
                        "version": package["version"],
                        "publisher": {
                            "id": envelope["payload"]["publisherId"]
                        },
                        "instances": {"mode": "multiple"},
                        "entry": {
                            "kind": "safe-html"
                            if suffix in {".html", ".htm"}
                            else "sandbox",
                            "resource": entrypoint["path"],
                        },
                        "navigation": {
                            "category": "Installed",
                            "icon": "package",
                            "order": 100,
                        },
                        "state": {"version": 1, "defaults": {}},
                    }
                    runtime_localizations = package_localizations_for_manifest(
                        package.get("localizations")
                    )
                    if runtime_localizations:
                        app_manifest["localizations"] = runtime_localizations
            else:
                try:
                    raw = archive.read(entrypoint["path"]).decode("utf-8", "strict")
                    app_manifest = json.loads(raw) if entrypoint["path"].endswith(".json") else yaml.safe_load(raw)
                except Exception as error:
                    raise RegistryError("agent_entrypoint_invalid", "Agent entrypoint must be a JSON/YAML Agent definition") from error
                if not isinstance(app_manifest, dict) or app_manifest.get("schema") != "ai2apps.agent/v1":
                    raise RegistryError("agent_entrypoint_invalid", "Agent entrypoint must use ai2apps.agent/v1")
                app_manifest = dict(app_manifest)
                runtime_localizations = package_localizations_for_manifest(
                    package.get("localizations"),
                    app_manifest.get("localizations"),
                )
                app_manifest.update({
                    "id": runtime_key,
                    "name": package["displayName"],
                    "description": package.get("description", ""),
                    "version": package["version"],
                    "publisher": {"id": envelope["payload"]["publisherId"]},
                })
                if runtime_localizations:
                    app_manifest["localizations"] = runtime_localizations
        sbom = {}
        if manifest.get("sbom"):
            with zipfile.ZipFile(inspected.archive_path) as archive:
                try:
                    sbom = json.loads(archive.read(manifest["sbom"]["path"]))
                except (KeyError, json.JSONDecodeError):
                    sbom = {}
        return InspectedBundle(
            kind,
            runtime_key,
            package["version"],
            f"sha256:{inspected.sha256}",
            app_manifest,
            tuple(BundleFile(item.path, f"sha256:{item.sha256}", item.size) for item in inspected.files),
            sbom,
            envelope["signature"],
            {"package_digest": f"sha256:{inspected.sha256}", "contract": "ai2apps.package-release.v1"},
            inspected.archive_path,
        )

    @staticmethod
    def _service_publisher_key(publisher_id: str, publisher_key_id: str) -> str:
        """Return the key-scoped publisher identity used by Service storage.

        Cloud Publisher IDs are stable while their Ed25519 keys are expected to
        rotate.  The legacy Service trust table stores one key per
        ``publisher_key``, so using only the Publisher ID makes a legitimate
        rotation collide with the previously installed key.  Scope the local
        identity to both immutable Cloud identifiers; the original Publisher
        and key IDs remain in Registry verification metadata.
        """

        return f"registry.{publisher_id}.{publisher_key_id}"

    def _service_bundle(self, inspected, envelope) -> InspectedServicePackage:
        manifest = inspected.manifest
        package = manifest["package"]
        entrypoint = manifest["entrypoints"][0]
        with zipfile.ZipFile(inspected.archive_path) as archive:
            try:
                raw_text = archive.read(entrypoint["path"]).decode("utf-8", "strict")
                raw = (
                    json.loads(raw_text)
                    if entrypoint["path"].endswith(".json")
                    else yaml.safe_load(raw_text)
                )
            except Exception as error:
                raise RegistryError(
                    "service_entrypoint_invalid",
                    "Service entrypoint must be a JSON/YAML Service definition",
                ) from error
            if not isinstance(raw, dict) or raw.get("schema") != "ai2apps.service/v1":
                raise RegistryError(
                    "service_entrypoint_invalid",
                    "Service entrypoint must use ai2apps.service/v1",
                )
            raw = dict(raw)
            runtime = raw.get("runtime", {})
            if (
                isinstance(runtime, dict)
                and runtime.get("role") == "inference_provider"
                and package["id"] != "ai2apps/runtime-omlx"
            ):
                raise RegistryError(
                    "runtime_publisher_denied",
                    "Inference Runtime Providers must use the reserved official Package ID",
                )
            runtime_localizations = package_localizations_for_manifest(
                package.get("localizations"), raw.get("localizations")
            )
            service_publisher_key = self._service_publisher_key(
                envelope["payload"]["publisherId"],
                envelope["payload"]["publisherKeyId"],
            )
            raw.update(
                {
                    "name": package["displayName"],
                    "description": package.get("description", ""),
                    "version": package["version"],
                    "publisher": {"id": service_publisher_key},
                }
            )
            if runtime_localizations:
                raw["localizations"] = runtime_localizations
            compatibility = dict(raw.get("compatibility", {}))
            platforms = manifest["compatibility"].get("platforms")
            if platforms is not None:
                platform_aliases = {"darwin": "macos", "win32": "windows"}
                compatibility["os"] = [
                    platform_aliases.get(item, item) for item in platforms
                ]
            architectures = manifest["compatibility"].get("architectures")
            if architectures is not None:
                compatibility["architectures"] = architectures
            minimum_os = manifest["compatibility"].get("minimumOsVersion")
            if minimum_os is not None:
                compatibility["minimum_os_version"] = minimum_os
            maximum_os = manifest["compatibility"].get(
                "maximumOsVersionExclusive"
            )
            if maximum_os is not None:
                compatibility["maximum_os_version_exclusive"] = maximum_os
            raw["compatibility"] = compatibility
            # service.yaml carries the sandbox's exact structured policy
            # (for example read-only HF cache and Metal access). Both it and
            # the outer permission summary are covered by the same detached
            # Package signature, so preserve the exact Service policy here.
            raw["permissions"] = dict(raw.get("permissions", {}))
            requires = dict(raw.get("requires", {}))
            declared_requirements = {
                item.get("id"): item
                for item in requires.get("services", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            dependencies = []
            for item in manifest["dependencies"]:
                service_id = self._service_dependency_key(item["packageId"])
                raw_version = item["version"]
                dependency = {
                    "id": service_id,
                    # Cloud v1 uses whitespace as the AND separator because
                    # commas are not part of its dependency-range grammar.
                    # The local Service layer delegates to PEP 440's
                    # SpecifierSet, which requires comma-separated clauses.
                    "version": (
                        raw_version
                        if raw_version == "*"
                        else ",".join(raw_version.split())
                    ),
                    "optional": item["optional"],
                }
                # The outer Cloud dependency remains authoritative for package
                # identity/version/optionality. Capability constraints are a
                # Service-runtime concern and are preserved from the equally
                # signed service.yaml only for the matching dependency.
                capabilities = declared_requirements.get(service_id, {}).get(
                    "capabilities", []
                )
                if capabilities:
                    dependency["capabilities"] = capabilities
                dependencies.append(dependency)
            requires["services"] = dependencies
            raw["requires"] = requires
            try:
                service_manifest = ServicePackageArchive._manifest(raw)
            except Exception as error:
                raise RegistryError(
                    getattr(error, "code", "service_entrypoint_invalid"), str(error)
                ) from error
            sbom = {}
            if manifest.get("sbom"):
                try:
                    sbom = json.loads(archive.read(manifest["sbom"]["path"]))
                except (KeyError, json.JSONDecodeError):
                    sbom = {}
        return InspectedServicePackage(
            archive_path=inspected.archive_path,
            digest=f"sha256:{inspected.sha256}",
            manifest=service_manifest,
            files=tuple(
                PackageFile(item.path, f"sha256:{item.sha256}", item.size)
                for item in inspected.files
            ),
            sbom=sbom,
            publisher_attestation={
                "publisher_id": service_publisher_key,
                "cloud_publisher_id": envelope["payload"]["publisherId"],
                "key_id": envelope["payload"]["publisherKeyId"],
                "package_digest": f"sha256:{inspected.sha256}",
            },
            signature=envelope["signature"],
            bundled_attestations=(),
            total_size_bytes=sum(item.size for item in inspected.files),
        )

    @staticmethod
    def _service_dependency_key(package_id: str) -> str:
        """Map signed Registry Package identity to its stable Service identity.

        Official model/runtime packages predate a general Service-ID field in
        the Cloud v1 dependency object. Keep their public Service API stable
        while the outer Package ID remains within the Cloud slug grammar.
        """

        # Some official Service identities intentionally keep the model
        # namespace even though their public Registry slug predates the
        # ``model-`` naming convention.  Keep these aliases explicit: the
        # generic slash-to-dot fallback would otherwise make an installed
        # dependency invisible to the Service package manager.
        official_aliases = {
            "ai2apps/punctuation-restorer": "ai2apps.model.punctuation-restorer",
        }
        if package_id in official_aliases:
            return official_aliases[package_id]

        official_prefixes = {
            "ai2apps/runtime-": "ai2apps.runtime.",
            "ai2apps/model-": "ai2apps.model.",
        }
        for prefix, service_prefix in official_prefixes.items():
            if package_id.startswith(prefix):
                return service_prefix + package_id.removeprefix(prefix)
        return package_id.replace("/", ".")

    def _register_service_publisher(self, release: dict[str, Any]) -> None:
        """Materialize the Registry-authenticated publisher for Service storage.

        ``service_packages.publisher_key`` is deliberately constrained to the
        local publisher trust table. Public Registry verification authenticates
        this same publisher and key before this method is reached, so persist
        that verified identity before the Service install transaction starts.
        """

        publisher = release["publisher"]
        key = publisher["key"]
        service_publisher_key = self._service_publisher_key(
            publisher["id"], key["id"]
        )
        self.service_manager.packages.upsert_publisher(
            publisher_key=service_publisher_key,
            display_name=publisher["displayName"],
            key_id=key["id"],
            public_key=key["publicKeyPem"],
            trust_status=TrustStatus.TRUSTED,
            source="organization",
            metadata={
                "trust": "ai2apps-cloud-registry-v1",
                "cloud_publisher_id": publisher["id"],
                "cloud_publisher_key_id": key["id"],
                "fingerprint_sha256": key["fingerprintSha256"],
            },
        )

    async def install(
        self,
        namespace: str,
        name: str,
        version: str | None = None,
        *,
        approve_review: bool = False,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._report_install_progress(
            progress,
            currentStep=1,
            stage="preparing",
            packageId=f"{namespace}/{name}",
            bytesCompleted=None,
            bytesTotal=None,
        )
        if progress is None:
            downloaded = await self.download_verified(namespace, name, version)
        else:
            downloaded = await self.download_verified(
                namespace,
                name,
                version,
                progress=progress,
                progress_step=1,
                dependency=False,
            )
        await self._preflight_restart_dependencies(
            downloaded[0], stack=(), progress=progress
        )
        return await self._install_with_dependencies(
            namespace,
            name,
            version,
            approve_review=approve_review,
            stack=(),
            progress=progress,
            downloaded=downloaded,
        )

    async def _install_with_dependencies(
        self,
        namespace: str,
        name: str,
        version: str | None,
        *,
        approve_review: bool,
        stack: tuple[str, ...],
        progress: Callable[[dict[str, Any]], None] | None,
        downloaded=None,
    ):
        package_id = f"{namespace}/{name}"
        if package_id in stack:
            raise RegistryError(
                "dependency_cycle",
                "Registry Package dependency cycle detected",
                details={"cycle": [*stack, package_id]},
            )
        is_dependency = bool(stack)
        progress_step = 3 if is_dependency else 2
        if downloaded is not None:
            inspected, envelope, release, metadata_version = downloaded
        elif progress is None:
            # Preserve the legacy call shape for embedders and test doubles
            # that override download_verified without progress support.
            inspected, envelope, release, metadata_version = (
                await self.download_verified(namespace, name, version)
            )
        else:
            inspected, envelope, release, metadata_version = await self.download_verified(
                namespace,
                name,
                version,
                progress=progress,
                progress_step=progress_step,
                dependency=is_dependency,
            )
        self._compatibility(inspected.manifest)
        kind = inspected.manifest["package"]["type"]
        verification = {
            "trust": "ai2apps-cloud-registry-v1",
            "repository_metadata_version": metadata_version,
            "publisher_id": release["publisher"]["id"],
            "publisher_key_id": release["publisher"]["key"]["id"],
            "publisher_key_fingerprint": release["publisher"]["key"]["fingerprintSha256"],
            "envelope": envelope,
        }
        try:
            snapshot: dict[str, Any] | None = None
            for dependency in inspected.manifest["dependencies"]:
                if dependency["optional"]:
                    continue
                dependency_id = dependency["packageId"]
                installed_dependency = self._load_state().get("installed", {}).get(
                    dependency_id
                )
                raw_spec = dependency["version"]
                specifier = SpecifierSet(
                    "" if raw_spec == "*" else raw_spec.replace(" ", ",")
                )
                installed_satisfies = (
                    installed_dependency is not None
                    and Version(str(installed_dependency["version"])) in specifier
                )
                if (
                    installed_satisfies
                    and installed_dependency.get("packageType") == "service"
                ):
                    runtime_key = installed_dependency.get("runtimeKey")
                    installed_satisfies = bool(
                        isinstance(runtime_key, str)
                        and self.service_manager.packages.active(runtime_key) is not None
                    )
                if installed_satisfies:
                    continue
                if snapshot is None:
                    snapshot = await self.trusted_snapshot()
                dependency_release = self._dependency_release(
                    snapshot, dependency_id, raw_spec
                )
                dependency_namespace, dependency_name = dependency_id.split("/", 1)
                await self._install_with_dependencies(
                    dependency_namespace,
                    dependency_name,
                    str(dependency_release["version"]),
                    approve_review=approve_review,
                    stack=(*stack, package_id),
                    progress=progress,
                )
            self._report_install_progress(
                progress,
                currentStep=3 if is_dependency else 4,
                stage="installing_dependency" if is_dependency else "installing_package",
                packageId=package_id,
                bytesCompleted=None,
                bytesTotal=None,
            )
            if kind == "service":
                service_bundle = self._service_bundle(inspected, envelope)
                self._register_service_publisher(release)
                record = await self.service_manager.install_verified_package(
                    service_bundle,
                    verification,
                    approve_audit_review=approve_review,
                )
                runtime_key = service_bundle.manifest.service_key
            else:
                bundle = self._interactive_bundle(inspected, envelope)
                record = await self.extension_manager.install_verified_bundle(
                    bundle,
                    verification,
                    approve_review=approve_review,
                )
                runtime_key = bundle.key
        except (ExtensionError, Exception) as error:
            if isinstance(error, RegistryError):
                raise
            if hasattr(error, "code"):
                raise RegistryError(error.code, str(error), details=getattr(error, "details", {})) from error
            raise
        state = self._load_state()
        installed = state.setdefault("installed", {})
        installed[inspected.manifest["package"]["id"]] = {
            "packageId": inspected.manifest["package"]["id"],
            "packageType": kind,
            "displayName": inspected.manifest["package"]["displayName"],
            "description": inspected.manifest["package"].get("description", ""),
            "localizations": inspected.manifest["package"].get("localizations", {}),
            "version": inspected.manifest["package"]["version"],
            "sha256": inspected.sha256,
            "runtimeKey": runtime_key,
            "activationStatus": (
                "pending_restart"
                if kind == "service"
                and getattr(record, "status", None) is PackageStatus.INSTALLED
                and runtime_key == "ai2apps.runtime.omlx"
                else "active"
            ),
            "restartScope": (
                "local"
                if kind == "service"
                and getattr(record, "status", None) is PackageStatus.INSTALLED
                and runtime_key == "ai2apps.runtime.omlx"
                else None
            ),
            "installedAt": datetime.now(UTC).isoformat(),
        }
        self._save_state(state)
        self._report_install_progress(
            progress,
            currentStep=3 if is_dependency else 5,
            stage="dependency_ready" if is_dependency else "finalizing",
            packageId=package_id,
            bytesCompleted=None,
            bytesTotal=None,
        )
        return record

    def installed(self, *, locale: str | None = None) -> list[dict[str, Any]]:
        items = []
        for stored in self._load_state().get("installed", {}).values():
            item = dict(stored)
            if item.get("packageType") == "service":
                runtime_key = item.get("runtimeKey")
                active = (
                    self.service_manager.packages.active(runtime_key)
                    if isinstance(runtime_key, str) and runtime_key
                    else None
                )
                expected_digest = f"sha256:{item.get('sha256')}"
                if active is not None and active.package_digest == expected_digest:
                    item["activationStatus"] = "active"
                    item["restartScope"] = None
            if locale:
                metadata = localized_package_metadata(item, locale)
                item.update(metadata)
            items.append(item)
        return sorted(items, key=lambda item: item["packageId"])

    async def uninstall(self, package_id: str, *, force: bool = False) -> None:
        state = self._load_state()
        item = state.get("installed", {}).get(package_id)
        if not item:
            raise RegistryError("package_not_installed", "Package is not installed")
        kind = item["packageType"]
        if kind in {"app", "agent"}:
            try:
                self.extension_manager.uninstall(
                    UnitKind(kind),
                    item.get("runtimeKey", package_id.replace("/", ".")),
                    force=force,
                )
            except ExtensionError as error:
                raise RegistryError(error.code, str(error), details=error.details) from error
        else:
            await self.service_manager.uninstall(item.get("runtimeKey", package_id.replace("/", ".")))
        state["installed"].pop(package_id, None)
        self._save_state(state)

    def build(self, source_path: str, output_path: str):
        return build_package(source_path, output_path)

    def create_key(self, name: str) -> dict[str, str]:
        private_pem, public_pem, fingerprint = generate_publisher_key()
        record = self.secrets.create(
            name=f"Publisher key: {name}",
            value=private_pem,
            purpose="AI2Apps package signing",
            metadata={"algorithm": "Ed25519", "fingerprintSha256": fingerprint, "publicKeyPem": public_pem},
        )
        return {"keyRef": record.id, "algorithm": "Ed25519", "fingerprintSha256": fingerprint, "publicKeyPem": public_pem}

    def keys(self) -> dict[str, list[dict[str, Any]]]:
        items = []
        for record in self.secrets.list():
            if record.purpose != "AI2Apps package signing":
                continue
            metadata = record.metadata if isinstance(record.metadata, dict) else {}
            if metadata.get("algorithm") != "Ed25519":
                continue
            items.append(
                {
                    "keyRef": record.id,
                    "name": record.name.removeprefix("Publisher key: "),
                    "algorithm": "Ed25519",
                    "fingerprintSha256": metadata.get("fingerprintSha256", ""),
                    "publicKeyPem": metadata.get("publicKeyPem", ""),
                    "status": record.status,
                    "createdAt": record.created_at.isoformat(),
                }
            )
        return {"items": items}

    def _private_key(self, key_ref: str) -> str:
        record = self.secrets.get(key_ref)
        if record.status != "active" or record.metadata.get("algorithm") != "Ed25519":
            raise RegistryError("publisher_key_invalid", "Publisher signing key is unavailable")
        try:
            return self.secrets.backend.load(key_ref)
        except KeyError as error:
            raise RegistryError("publisher_key_invalid", "Publisher private key is unavailable") from error

    def sign(self, archive_path: str, key_ref: str, publisher_id: str, publisher_key_id: str) -> dict[str, Any]:
        inspected = inspect_package(archive_path)
        return create_signature_envelope(
            inspected,
            self._private_key(key_ref),
            publisher_id=publisher_id,
            publisher_key_id=publisher_key_id,
        )

    def key_proof(self, payload: dict[str, Any], key_ref: str) -> str:
        return create_key_proof(payload, self._private_key(key_ref))

    async def create_publisher(self, display_name: str, namespace: str, kind: str = "personal"):
        return await self._json(
            "POST",
            "/v1/prototype/publishers",
            json={"displayName": display_name, "namespace": namespace, "kind": kind},
        )

    async def publishers(self):
        return await self._json("GET", "/v1/prototype/publishers")

    async def create_key_challenge(self, publisher_id: str, key_ref: str):
        record = self.secrets.get(key_ref)
        public_key = record.metadata.get("publicKeyPem")
        if not isinstance(public_key, str):
            raise RegistryError("publisher_key_invalid", "Publisher public key is unavailable")
        return await self._json(
            "POST",
            f"/v1/prototype/publishers/{publisher_id}/key-challenges",
            json={"publicKeyPem": public_key},
        )

    async def register_key(self, publisher_id: str, challenge_id: str, signature: str):
        return await self._json(
            "POST",
            f"/v1/prototype/publishers/{publisher_id}/keys",
            json={"challengeId": challenge_id, "signature": signature},
        )

    async def submit(self, archive_path: str, envelope: dict[str, Any]):
        inspected = inspect_package(archive_path)
        envelope_text = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        if len(envelope_text.encode("utf-8")) > 65_536:
            raise RegistryError("envelope_size_limit", "Signature envelope exceeds 64 KiB")
        package_id = inspected.manifest.get("package", {}).get("id")
        size_limit = (
            MAX_PLATFORM_RUNTIME_SUBMISSION_BYTES
            if package_id == PLATFORM_RUNTIME_PACKAGE_ID
            else MAX_SUBMISSION_BYTES
        )
        if inspected.size > size_limit:
            limit_mib = size_limit // (1024 * 1024)
            raise RegistryError(
                "artifact_size_limit",
                f"Package submissions are limited to {limit_mib} MiB",
            )
        submission_path = (
            "/v1/platform-runtime-submissions"
            if package_id == PLATFORM_RUNTIME_PACKAGE_ID
            else "/v1/submissions"
        )
        with inspected.archive_path.open("rb") as artifact:
            response = await self.cloud.request(
                "POST",
                submission_path,
                data={"envelope": envelope_text},
                files={"artifact": (inspected.archive_path.name, artifact, inspected.media_type)},
            )
        try:
            if response.status_code >= 400:
                try:
                    value = response.json()
                except ValueError:
                    value = {}
                error = value.get("error", {}) if isinstance(value, dict) else {}
                raise RegistryError(
                    str(error.get("code") or "submission_failed").lower(),
                    str(error.get("message") or f"Submission failed ({response.status_code})"),
                    details={"status": response.status_code},
                )
            return response.json()
        finally:
            await response.aclose()

    async def publishing_context(self):
        return await self._json("GET", "/v1/auth/me")

    async def reauthenticate_admin(self, password: str):
        return await self._json(
            "POST", "/v1/admin/reauth", json={"password": password}
        )

    async def publisher_submissions(self, *, status: str | None = None, limit: int = 50):
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return await self._json("GET", "/v1/publisher-submissions", params=params)

    async def review_submissions(self, *, status: str | None = None, limit: int = 50):
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return await self._json("GET", "/v1/prototype/submissions", params=params)

    async def submissions(self, *, status: str | None = None, limit: int = 50):
        """Compatibility alias for the reviewer queue."""

        return await self.review_submissions(status=status, limit=limit)

    async def submission(self, submission_id: str):
        return await self._json("GET", f"/v1/submissions/{submission_id}")

    async def submission_details(self, submission_id: str):
        return await self._json(
            "GET", f"/v1/prototype/submissions/{submission_id}/details"
        )

    async def request_review(self, submission_id: str):
        return await self._json(
            "POST", f"/v1/prototype/submissions/{submission_id}/review-request"
        )

    async def review_submission(self, submission_id: str, decision: str, note: str):
        return await self._json(
            "POST",
            f"/v1/prototype/submissions/{submission_id}/reviews",
            json={"decision": decision, "note": note},
        )

    async def publish_submission(self, submission_id: str):
        return await self._json(
            "POST", f"/v1/prototype/submissions/{submission_id}/publication"
        )
