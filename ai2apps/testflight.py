"""Local-only development distribution for unsigned AI2Apps App bundles."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from ai2apps.core import AppDefinitionStatus, AppInstanceMode, SingletonScope
from ai2apps.extensions import ExtensionError, UnitKind
from ai2apps.extensions.archive import InteractiveArchive
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import AppRepository

_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")


class TestFlightError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class TestFlightManager:
    """Submit development Bundles without granting formal installation trust."""

    def __init__(self, database: PlatformDatabase, root: str | Path) -> None:
        self.database = database
        self.root = Path(root).expanduser().resolve()
        self.apps = AppRepository(database)

    @staticmethod
    def _archive_name(value: str) -> str:
        pure = PurePosixPath(value)
        if not value or pure.is_absolute() or ".." in pure.parts or "\\" in value:
            raise TestFlightError("unsafe_bundle", "Unsafe development Bundle path")
        return pure.as_posix()

    @staticmethod
    def _read_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
        try:
            value = json.loads(archive.read(name))
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise TestFlightError("invalid_bundle", f"Invalid {name}") from error
        if not isinstance(value, dict):
            raise TestFlightError("invalid_bundle", f"Invalid {name}")
        return value

    def submit(self, bundle_path: str | Path) -> dict[str, Any]:
        path = Path(bundle_path).expanduser().resolve(strict=True)
        archive_digest = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        with zipfile.ZipFile(path) as archive:
            package = self._read_json(archive, "META/package.json")
            file_index = self._read_json(archive, "META/files.json").get("files")
            if (
                package.get("schema") != "ai2apps.package/v1"
                or package.get("development") is not True
                or package.get("installable") is not False
                or not isinstance(package.get("components"), list)
                or not isinstance(file_index, list)
            ):
                raise TestFlightError(
                    "not_development_bundle",
                    "TestFlight accepts AI2Apps development Bundles only",
                )
            entries = set(archive.namelist())
            indexed: dict[str, dict[str, Any]] = {}
            for item in file_index:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    raise TestFlightError("invalid_bundle", "Invalid development file index")
                name = self._archive_name(item["path"])
                if name not in entries or name in indexed:
                    raise TestFlightError("invalid_bundle", "Development file index mismatch")
                content = archive.read(name)
                digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
                if item.get("sha256") != digest or item.get("size") != len(content):
                    raise TestFlightError("bundle_integrity_failed", f"Bundle file changed: {name}")
                indexed[name] = item

            submitted = []
            for component in package["components"]:
                if not isinstance(component, dict) or component.get("type") != "app":
                    continue
                submitted.append(
                    self._submit_app(archive, indexed, component, archive_digest)
                )
        if not submitted:
            raise TestFlightError("app_missing", "Development Bundle contains no App")
        return {
            "ok": True,
            "channel": "testflight",
            "bundle": str(path),
            "bundle_digest": archive_digest,
            "apps": submitted,
        }

    def _submit_app(
        self,
        archive: zipfile.ZipFile,
        indexed: dict[str, dict[str, Any]],
        component: dict[str, Any],
        archive_digest: str,
    ) -> dict[str, Any]:
        root = self._archive_name(str(component.get("root", ""))).rstrip("/")
        manifest_name = self._archive_name(str(component.get("manifest", "")))
        prefix = root + "/"
        files = {
            name.removeprefix(prefix): item
            for name, item in indexed.items()
            if name.startswith(prefix)
        }
        if manifest_name not in indexed or not manifest_name.startswith(prefix):
            raise TestFlightError("app_manifest_missing", "TestFlight App manifest is missing")
        try:
            manifest = yaml.safe_load(archive.read(manifest_name))
        except yaml.YAMLError as error:
            raise TestFlightError("invalid_app_manifest", "Invalid TestFlight App manifest") from error
        if not isinstance(manifest, dict):
            raise TestFlightError("invalid_app_manifest", "Invalid TestFlight App manifest")
        try:
            InteractiveArchive._validate_manifest(UnitKind.APP, manifest, set(files))
        except ExtensionError as error:
            raise TestFlightError(error.code, str(error)) from error

        original_id = str(manifest.get("id", ""))
        if not _ID.fullmatch(original_id):
            raise TestFlightError("invalid_app_id", "TestFlight App id is invalid")
        digest_seed = json.dumps(
            [(name, item["sha256"]) for name, item in sorted(files.items())],
            separators=(",", ":"),
        ).encode()
        digest = f"sha256:{hashlib.sha256(digest_seed).hexdigest()}"
        suffix = digest.removeprefix("sha256:")[:12]
        app_key = f"testflight.{original_id}"
        if len(app_key) > 128:
            app_key = f"testflight.{original_id[:96]}.{suffix}"
        version = f"{manifest.get('version', '0.0.0')}+tf.{suffix}"
        store = self.root / original_id / suffix
        if not store.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix="testflight-", dir=self.root))
            try:
                for relative in files:
                    target = staging / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(prefix + relative))
                meta = staging / "META"
                meta.mkdir(exist_ok=True)
                meta.joinpath("files.json").write_text(
                    json.dumps(
                        {
                            "files": [
                                {**item, "path": name}
                                for name, item in sorted(files.items())
                            ]
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                store.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, store)
                for item in sorted(store.rglob("*"), reverse=True):
                    item.chmod(0o555 if item.is_dir() else 0o444)
                store.chmod(0o555)
            finally:
                shutil.rmtree(staging, ignore_errors=True)

        manifest = {
            **manifest,
            "id": app_key,
            "version": version,
            "navigation": {
                **(manifest.get("navigation") if isinstance(manifest.get("navigation"), dict) else {}),
                "category": "TestFlight",
                "pinned_default": False,
            },
            "testflight": {
                "original_id": original_id,
                "store_path": str(store),
                "digest": digest,
                "bundle_digest": archive_digest,
                "signed": False,
                "formal_installable": False,
            },
        }
        instances = manifest.get("instances", {})
        mode = AppInstanceMode(str(instances.get("mode", "multiple")))
        scope = (
            SingletonScope(str(instances.get("scope", "user")))
            if mode is AppInstanceMode.SINGLETON
            else None
        )
        with self.database.transaction(write=True) as connection:
            same = connection.execute(
                "SELECT id FROM app_definitions WHERE package_id=? "
                "AND package_version=? AND effective_digest=?",
                (app_key, version, digest),
            ).fetchone()
            old = connection.execute(
                "SELECT id FROM app_definitions WHERE package_id=? AND status='enabled'",
                (app_key,),
            ).fetchall()
            for row in old:
                connection.execute(
                    "UPDATE app_instances SET status='closed',closed_at=updated_at "
                    "WHERE app_definition_id=? AND status!='closed'",
                    (row["id"],),
                )
            connection.execute(
                "UPDATE app_definitions SET status='disabled' WHERE package_id=?",
                (app_key,),
            )
            if same is not None:
                connection.execute(
                    "UPDATE app_definitions SET status='enabled' WHERE id=?",
                    (same["id"],),
                )
                return {
                    "id": app_key,
                    "original_id": original_id,
                    "name": manifest.get("name") or original_id,
                    "version": version,
                    "digest": digest,
                    "entry_url": f"/apps/{app_key}",
                }
        record = self.apps.create_definition(
            package_id=app_key,
            package_version=version,
            display_name=str(manifest.get("name") or original_id),
            instance_mode=mode,
            singleton_scope=scope,
            source="local",
            status=AppDefinitionStatus.ENABLED,
            manifest=manifest,
        )
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE app_definitions SET upstream_digest=?,effective_digest=? WHERE id=?",
                (digest, digest, record.id),
            )
        return {
            "id": app_key,
            "original_id": original_id,
            "name": manifest.get("name") or original_id,
            "version": version,
            "digest": digest,
            "entry_url": f"/apps/{app_key}",
        }
