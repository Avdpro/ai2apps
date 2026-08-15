"""Public Registry discovery, authenticated download, and local installation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from ai2apps.cloud_client import AI2AppsCloudClient
from ai2apps.extensions import ExtensionError, UnitKind
from ai2apps.extensions.models import BundleFile, InspectedBundle
from ai2apps.secrets import SecretRepository
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.models import InspectedServicePackage, PackageFile

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

DEFAULT_REPOSITORY_FINGERPRINT = (
    "c1664f2a8ab3206a207023791ca5260857c123aace542177e58f93141b574da2"
)


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
    return parsed.astimezone(timezone.utc)


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
        return await self._json("GET", "/v1/registry/search", params={key: value for key, value in params.items() if value is not None and value != ""})

    async def recommendations(self, **params) -> Any:
        return await self._json("GET", "/v1/registry/recommendations", params={key: value for key, value in params.items() if value is not None and value != ""})

    async def catalog(self, namespace: str, name: str) -> Any:
        return await self._json("GET", f"/v1/registry/packages/{namespace}/{name}/catalog")

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
        now = datetime.now(timezone.utc)
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

    def _registry_path(self, url: str, fallback: str) -> str:
        parsed = urlparse(url)
        cloud = urlparse(self.cloud.base_url)
        if parsed.scheme and (parsed.scheme, parsed.netloc) != (cloud.scheme, cloud.netloc):
            raise RegistryError("repository_url_invalid", "Repository metadata points outside the configured Cloud origin")
        path = parsed.path if parsed.scheme else url
        if not path.startswith("/v1/registry/"):
            raise RegistryError("repository_url_invalid", "Repository download URL is outside the public Registry")
        return path or fallback

    async def download_verified(self, namespace: str, name: str, version: str | None = None):
        package_id = f"{namespace}/{name}"
        snapshot = await self.trusted_snapshot()
        release = self._release(snapshot, package_id, version)
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
        quarantine = self.root / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix="download-", suffix=suffix, dir=quarantine)
        os.close(handle)
        temporary = Path(temporary_name)
        digest = hashlib.sha256()
        size = 0
        response = await self.cloud.request("GET", artifact_path, stream=True, headers={"Accept": str(artifact["mediaType"])})
        try:
            if response.status_code >= 400:
                raise RegistryError("artifact_download_failed", f"Artifact download failed ({response.status_code})")
            with temporary.open("wb") as output:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > expected_size or size > MAX_ARTIFACT_BYTES:
                        raise RegistryError("artifact_size_mismatch", "Artifact exceeded its signed size")
                    digest.update(chunk)
                    output.write(chunk)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await response.aclose()
        actual_sha256 = digest.hexdigest()
        if size != expected_size or actual_sha256 != artifact["sha256"]:
            temporary.unlink(missing_ok=True)
            raise RegistryError("artifact_digest_mismatch", "Artifact bytes do not match trusted repository metadata")
        publisher = release["publisher"]
        key = publisher["key"]
        if public_key_fingerprint(key["publicKeyPem"]) != key["fingerprintSha256"]:
            temporary.unlink(missing_ok=True)
            raise RegistryError("publisher_key_invalid", "Publisher key fingerprint is invalid")
        if envelope.get("payload", {}).get("publisherId") != publisher["id"] or envelope.get("payload", {}).get("publisherKeyId") != key["id"]:
            temporary.unlink(missing_ok=True)
            raise RegistryError("publisher_identity_mismatch", "Envelope publisher is not bound by repository metadata")
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
        final = self.root / "downloads" / namespace / name / version / f"{actual_sha256}{suffix}"
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
    def _compatibility(manifest: dict[str, Any]) -> None:
        compatibility = manifest["compatibility"]
        platforms = compatibility.get("platforms", [])
        local_platform = {"Darwin": "darwin", "Linux": "linux", "Windows": "win32"}.get(platform.system(), platform.system().lower())
        if platforms and local_platform not in platforms:
            raise RegistryError("platform_incompatible", f"Package does not support {local_platform}")
        architectures = compatibility.get("architectures", [])
        local_arch = {"aarch64": "arm64", "AMD64": "x64", "x86_64": "x64"}.get(platform.machine(), platform.machine())
        if architectures and local_arch not in architectures:
            raise RegistryError("architecture_incompatible", f"Package does not support {local_arch}")
        raw_range = compatibility["ai2apps"].strip()
        try:
            specifier = SpecifierSet("" if raw_range == "*" else raw_range.replace(" ", ","))
        except Exception as error:
            raise RegistryError("compatibility_invalid", "Package AI2Apps version range is invalid") from error
        # The local package contract started at 0.1.0. Keep this explicit until
        # the runtime exposes a single product version constant.
        if Version("0.1.0") not in specifier:
            raise RegistryError("ai2apps_incompatible", "Package does not support this AI2Apps contract version")

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
            else:
                try:
                    raw = archive.read(entrypoint["path"]).decode("utf-8", "strict")
                    app_manifest = json.loads(raw) if entrypoint["path"].endswith(".json") else yaml.safe_load(raw)
                except Exception as error:
                    raise RegistryError("agent_entrypoint_invalid", "Agent entrypoint must be a JSON/YAML Agent definition") from error
                if not isinstance(app_manifest, dict) or app_manifest.get("schema") != "ai2apps.agent/v1":
                    raise RegistryError("agent_entrypoint_invalid", "Agent entrypoint must use ai2apps.agent/v1")
                app_manifest = dict(app_manifest)
                app_manifest.update({
                    "id": runtime_key,
                    "name": package["displayName"],
                    "description": package.get("description", ""),
                    "version": package["version"],
                    "publisher": {"id": envelope["payload"]["publisherId"]},
                })
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
            runtime_key = package["id"].replace("/", ".")
            raw.update(
                {
                    "id": runtime_key,
                    "name": package["displayName"],
                    "description": package.get("description", ""),
                    "version": package["version"],
                    "publisher": {"id": envelope["payload"]["publisherId"]},
                }
            )
            raw["compatibility"] = {
                **raw.get("compatibility", {}),
                "os": manifest["compatibility"].get("platforms", []),
                "architectures": manifest["compatibility"].get("architectures", []),
            }
            raw["permissions"] = {
                item["capability"]: {
                    "reason": item["reason"], "required": item["required"]
                }
                for item in manifest["permissions"]
            }
            dependencies = [
                {
                    "id": item["packageId"].replace("/", "."),
                    "version": item["version"],
                    "optional": item["optional"],
                }
                for item in manifest["dependencies"]
            ]
            requires = dict(raw.get("requires", {}))
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
                "publisher_id": envelope["payload"]["publisherId"],
                "package_digest": f"sha256:{inspected.sha256}",
            },
            signature=envelope["signature"],
            bundled_attestations=(),
            total_size_bytes=sum(item.size for item in inspected.files),
        )

    async def install(self, namespace: str, name: str, version: str | None = None, *, approve_review: bool = False):
        inspected, envelope, release, metadata_version = await self.download_verified(namespace, name, version)
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
            if kind == "service":
                service_bundle = self._service_bundle(inspected, envelope)
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
            "version": inspected.manifest["package"]["version"],
            "sha256": inspected.sha256,
            "runtimeKey": runtime_key,
            "installedAt": datetime.now(timezone.utc).isoformat(),
        }
        self._save_state(state)
        return record

    def installed(self) -> list[dict[str, Any]]:
        return sorted(self._load_state().get("installed", {}).values(), key=lambda item: item["packageId"])

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
        if inspected.size > 25 * 1024 * 1024:
            raise RegistryError("artifact_size_limit", "Prototype submissions are limited to 25 MiB")
        with inspected.archive_path.open("rb") as artifact:
            response = await self.cloud.request(
                "POST",
                "/v1/submissions",
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

    async def submissions(self, *, status: str | None = None, limit: int = 50):
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        return await self._json("GET", "/v1/prototype/submissions", params=params)

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
