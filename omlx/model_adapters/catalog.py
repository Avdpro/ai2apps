# SPDX-License-Identifier: Apache-2.0
"""Authenticated remote catalog and downloads for model-adapter wheels."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from ai2apps.packages.contract_v1 import (
    PackageContractError,
    jcs_bytes,
    verify_repository_snapshot,
)
from ai2apps.packages.repository_config import AI2APPS_REPOSITORY_FINGERPRINT

from .packages import (
    MAX_WHEEL_BYTES,
    ModelAdapterPackageError,
    ModelAdapterPackageManager,
)

DEFAULT_CATALOG_URL = (
    "https://coder.ai2apps.com/assets/model-adapters/catalog.json"
)
DEFAULT_CATALOG_KEY_URL = (
    "https://coder.ai2apps.com/assets/model-adapters/repository-key.json"
)
DEFAULT_CATALOG_FINGERPRINT = AI2APPS_REPOSITORY_FINGERPRINT
MAX_CATALOG_BYTES = 2 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHECKPOINT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,159}$"
)
_STATE_LOCK = threading.RLock()


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Catalog timestamp is invalid"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Catalog timestamp is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Catalog timestamp requires a timezone"
        )
    return parsed.astimezone(UTC)


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment:
        raise ModelAdapterPackageError("catalog_url_invalid", "Catalog URL is unsafe")
    host = (parsed.hostname or "").lower()
    local = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise ModelAdapterPackageError(
            "catalog_url_invalid", "Catalog URLs must use HTTPS"
        )
    if not host:
        raise ModelAdapterPackageError("catalog_url_invalid", "Catalog URL has no host")
    return parsed.scheme, host, parsed.port


def validate_checkpoint_record(value: Any) -> dict[str, Any]:
    """Validate one signed, immutable checkpoint recommendation."""
    if not isinstance(value, dict):
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Checkpoint recommendation is invalid"
        )
    required = {"source", "repoId", "revision", "displayName"}
    optional = {"estimatedSizeBytes", "installMode", "recipeId"}
    if required - set(value) or set(value) - required - optional:
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Checkpoint recommendation schema is invalid"
        )
    if value["source"] != "huggingface":
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Checkpoint source is unsupported"
        )
    if not isinstance(value["repoId"], str) or not _REPOSITORY_ID.fullmatch(
        value["repoId"]
    ):
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Checkpoint repository ID is invalid"
        )
    if not isinstance(value["revision"], str) or not _CHECKPOINT_REVISION.fullmatch(
        value["revision"]
    ):
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid",
            "Checkpoint revision must be a pinned commit SHA",
        )
    if (
        not isinstance(value["displayName"], str)
        or not 1 <= len(value["displayName"]) <= 160
    ):
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Checkpoint display name is invalid"
        )
    estimated_size = value.get("estimatedSizeBytes")
    if estimated_size is not None and (
        not isinstance(estimated_size, int)
        or isinstance(estimated_size, bool)
        or estimated_size <= 0
    ):
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Checkpoint estimated size is invalid"
        )
    install_mode = value.get("installMode", "download")
    if install_mode not in {"download", "cache-moe"}:
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid", "Checkpoint install mode is invalid"
        )
    recipe_id = value.get("recipeId")
    if install_mode == "cache-moe":
        if not isinstance(recipe_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9._-]{0,127}", recipe_id
        ):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid",
                "Cached-MoE checkpoint requires a valid recipe ID",
            )
    elif recipe_id is not None:
        raise ModelAdapterPackageError(
            "catalog_metadata_invalid",
            "A direct checkpoint download cannot declare a recipe ID",
        )
    return {
        "source": value["source"],
        "repo_id": value["repoId"],
        "revision": value["revision"],
        "display_name": value["displayName"],
        "estimated_size_bytes": estimated_size,
        "install_mode": install_mode,
        "recipe_id": recipe_id,
    }


class ModelAdapterCatalog:
    """Verify a signed catalog before downloading any executable wheel bytes."""

    def __init__(
        self,
        manager: ModelAdapterPackageManager,
        *,
        catalog_url: str | None = None,
        key_url: str | None = None,
        repository_fingerprint: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.manager = manager
        self.catalog_url = catalog_url or os.environ.get(
            "OMLX_MODEL_ADAPTER_CATALOG_URL", DEFAULT_CATALOG_URL
        )
        self.key_url = key_url or os.environ.get(
            "OMLX_MODEL_ADAPTER_CATALOG_KEY_URL", DEFAULT_CATALOG_KEY_URL
        )
        self.repository_fingerprint = (
            repository_fingerprint
            or os.environ.get("OMLX_MODEL_ADAPTER_CATALOG_FINGERPRINT")
            or DEFAULT_CATALOG_FINGERPRINT
        ).removeprefix("sha256:")
        self.transport = transport
        self.state_path = manager.root / "catalog-state.json"
        self.catalog_origin = _origin(self.catalog_url)
        if _origin(self.key_url) != self.catalog_origin:
            raise ModelAdapterPackageError(
                "catalog_url_invalid", "Catalog key must use the catalog origin"
            )

    async def _json(self, client: httpx.AsyncClient, url: str) -> Any:
        try:
            response = await client.get(url, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise ModelAdapterPackageError(
                "catalog_unavailable", "Model adapter catalog is unavailable"
            ) from exc
        if response.status_code != 200:
            raise ModelAdapterPackageError(
                "catalog_unavailable",
                f"Model adapter catalog request failed ({response.status_code})",
            )
        if len(response.content) > MAX_CATALOG_BYTES:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog response is too large"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog response is not valid JSON"
            ) from exc

    def _load_state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"metadata_version": 0, "payload_sha256": None}
        if not isinstance(value, dict) or not isinstance(
            value.get("metadata_version"), int
        ):
            return {"metadata_version": 0, "payload_sha256": None}
        return value

    def _save_version(self, version: int, payload_sha256: str) -> None:
        with _STATE_LOCK:
            state = self._load_state()
            previous = state["metadata_version"]
            if version < previous:
                raise ModelAdapterPackageError(
                    "catalog_metadata_rollback",
                    "Model adapter catalog version moved backwards",
                    details={"previous": previous, "received": version},
                )
            previous_digest = state.get("payload_sha256")
            if version == previous and previous_digest not in {None, payload_sha256}:
                raise ModelAdapterPackageError(
                    "catalog_metadata_equivocation",
                    "Catalog content changed without advancing its version",
                    details={"version": version},
                )
            if version == previous and previous_digest == payload_sha256:
                return
            self.manager.root.mkdir(parents=True, exist_ok=True)
            fd, raw_path = tempfile.mkstemp(
                prefix="catalog-state-", suffix=".json", dir=self.manager.root
            )
            temporary = Path(raw_path)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "metadata_version": version,
                            "payload_sha256": payload_sha256,
                        },
                        handle,
                        sort_keys=True,
                    )
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.state_path)
            finally:
                temporary.unlink(missing_ok=True)

    def _validate_release(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog release is invalid"
            )
        required = {"packageId", "packageType", "version", "status", "artifact"}
        optional = {"displayName", "statusReason", "checkpoints"}
        if set(value) - required - optional or required - set(value):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog release schema is invalid"
            )
        package_id = value["packageId"]
        if (
            not isinstance(package_id, str)
            or not 1 <= len(package_id) <= 128
            or canonicalize_name(package_id) != package_id
        ):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog package ID is invalid"
            )
        if value["packageType"] != "model-adapter":
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog package type is invalid"
            )
        try:
            parsed_version = Version(value["version"])
        except (InvalidVersion, TypeError) as exc:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog package version is invalid"
            ) from exc
        if str(parsed_version) != value["version"]:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog package version is not canonical"
            )
        if value["status"] not in {"published", "yanked"}:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog release status is invalid"
            )
        artifact = value["artifact"]
        if not isinstance(artifact, dict) or set(artifact) != {"url", "sha256", "size"}:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog artifact is invalid"
            )
        if not isinstance(artifact["url"], str):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog artifact URL is invalid"
            )
        url = urljoin(self.catalog_url, artifact["url"])
        if _origin(url) != self.catalog_origin:
            raise ModelAdapterPackageError(
                "catalog_url_invalid",
                "Catalog artifact points outside its trusted origin",
            )
        filename = Path(unquote(urlsplit(url).path)).name
        if not filename.endswith(".whl"):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog artifact is not a wheel"
            )
        sha256 = artifact["sha256"]
        size = artifact["size"]
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog artifact digest is invalid"
            )
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or not 0 < size <= MAX_WHEEL_BYTES
        ):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog artifact size is invalid"
            )
        display_name = value.get("displayName", package_id)
        if not isinstance(display_name, str) or not 1 <= len(display_name) <= 160:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog display name is invalid"
            )
        status_reason = value.get("statusReason")
        if status_reason is not None and (
            not isinstance(status_reason, str) or len(status_reason) > 500
        ):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog status reason is invalid"
            )
        checkpoint_values = value.get("checkpoints", [])
        if not isinstance(checkpoint_values, list) or len(checkpoint_values) > 16:
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog checkpoints are invalid"
            )
        checkpoints = [
            {
                **validate_checkpoint_record(item),
                "package_id": package_id,
                "package_version": value["version"],
            }
            for item in checkpoint_values
        ]
        checkpoint_ids = {(item["source"], item["repo_id"]) for item in checkpoints}
        if len(checkpoint_ids) != len(checkpoints):
            raise ModelAdapterPackageError(
                "catalog_metadata_invalid", "Catalog checkpoints must be unique"
            )
        return {
            "package_id": package_id,
            "display_name": display_name,
            "version": value["version"],
            "status": value["status"],
            "status_reason": status_reason,
            "checkpoints": checkpoints,
            "artifact": {**artifact, "url": url, "filename": filename},
        }

    async def trusted_catalog(self) -> dict[str, Any]:
        async with httpx.AsyncClient(
            transport=self.transport,
            follow_redirects=False,
            trust_env=False,
            timeout=15,
        ) as client:
            key_info = await self._json(client, self.key_url)
            public_key = (
                key_info.get("publicKeyPem") if isinstance(key_info, dict) else None
            )
            if not isinstance(public_key, str):
                raise ModelAdapterPackageError(
                    "catalog_key_invalid", "Catalog did not return a public key"
                )
            envelope = await self._json(client, self.catalog_url)
        try:
            payload = verify_repository_snapshot(
                envelope,
                public_key,
                pinned_fingerprint=self.repository_fingerprint,
            )
        except PackageContractError as exc:
            raise ModelAdapterPackageError(
                exc.code, str(exc), details=exc.details
            ) from exc

        now = datetime.now(UTC)
        generated_at = _timestamp(payload["generatedAt"])
        expires_at = _timestamp(payload["expiresAt"])
        if expires_at <= now:
            raise ModelAdapterPackageError(
                "catalog_metadata_expired", "Model adapter catalog has expired"
            )
        if (generated_at - now).total_seconds() > 300:
            raise ModelAdapterPackageError(
                "catalog_metadata_future",
                "Model adapter catalog is dated in the future",
            )
        releases = [self._validate_release(item) for item in payload["releases"]]
        self._save_version(
            payload["version"], hashlib.sha256(jcs_bytes(payload)).hexdigest()
        )

        installed = {
            item["normalized_name"]: item["version"]
            for item in self.manager.installed()
        }
        items = []
        for release in releases:
            if release["status"] != "published":
                continue
            installed_version = installed.get(release["package_id"])
            items.append(
                {
                    **release,
                    "installed_version": installed_version,
                    "update_available": installed_version is not None
                    and Version(release["version"]) > Version(installed_version),
                }
            )
        items.sort(
            key=lambda item: (item["package_id"], Version(item["version"])),
            reverse=True,
        )
        return {
            "metadata_version": payload["version"],
            "generated_at": payload["generatedAt"],
            "expires_at": payload["expiresAt"],
            "items": items,
        }

    async def install(
        self, package_name: str, version: str | None = None
    ) -> dict[str, Any]:
        normalized = canonicalize_name(package_name)
        catalog = await self.trusted_catalog()
        matches = [
            item
            for item in catalog["items"]
            if item["package_id"] == normalized
            and (version is None or item["version"] == version)
        ]
        if not matches:
            raise ModelAdapterPackageError(
                "catalog_release_not_found",
                "Model adapter release is not in the trusted catalog",
            )
        release = max(matches, key=lambda item: Version(item["version"]))
        installed = {
            item["normalized_name"]: item["version"]
            for item in self.manager.installed()
        }.get(normalized)
        if installed is not None and Version(release["version"]) < Version(installed):
            raise ModelAdapterPackageError(
                "adapter_version_rollback",
                "Catalog install would downgrade the active model adapter",
                details={"installed": installed, "requested": release["version"]},
            )
        artifact = release["artifact"]
        self.manager.root.mkdir(parents=True, exist_ok=True)
        download_dir = Path(
            tempfile.mkdtemp(prefix="adapter-download-", dir=self.manager.root)
        )
        temporary = download_dir / artifact["filename"]
        digest = hashlib.sha256()
        size = 0
        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
                timeout=60,
            ) as client:
                try:
                    async with client.stream("GET", artifact["url"]) as response:
                        if response.status_code != 200:
                            raise ModelAdapterPackageError(
                                "artifact_download_failed",
                                f"Model adapter download failed ({response.status_code})",
                            )
                        with temporary.open("wb") as output:
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > artifact["size"]:
                                    raise ModelAdapterPackageError(
                                        "artifact_size_mismatch",
                                        "Downloaded wheel exceeded its signed size",
                                    )
                                digest.update(chunk)
                                output.write(chunk)
                except httpx.HTTPError as exc:
                    raise ModelAdapterPackageError(
                        "artifact_download_failed", "Model adapter download failed"
                    ) from exc
            if size != artifact["size"] or digest.hexdigest() != artifact["sha256"]:
                raise ModelAdapterPackageError(
                    "artifact_digest_mismatch",
                    "Downloaded wheel does not match the signed catalog",
                )
            inspected = await asyncio.to_thread(self.manager.inspect, temporary)
            if (
                inspected["normalized_name"] != release["package_id"]
                or inspected["version"] != release["version"]
            ):
                raise ModelAdapterPackageError(
                    "artifact_identity_mismatch",
                    "Wheel identity does not match the signed catalog release",
                )
            result = await asyncio.to_thread(self.manager.install, temporary)
            return {**result, "catalog_metadata_version": catalog["metadata_version"]}
        finally:
            shutil.rmtree(download_dir, ignore_errors=True)

    async def cached_moe_checkpoint(
        self, package_name: str, version: str, recipe_id: str
    ) -> dict[str, Any]:
        """Resolve a Cached-MoE recipe only through the signed active release."""
        normalized = canonicalize_name(package_name)
        catalog = await self.trusted_catalog()
        for release in catalog["items"]:
            if (
                release["package_id"] != normalized
                or release["version"] != version
                or release["installed_version"] != version
            ):
                continue
            for checkpoint in release["checkpoints"]:
                if (
                    checkpoint["install_mode"] == "cache-moe"
                    and checkpoint["recipe_id"] == recipe_id
                ):
                    return checkpoint
        raise ModelAdapterPackageError(
            "catalog_release_not_found",
            "Cached-MoE recipe is not recommended by the active signed adapter release",
        )
