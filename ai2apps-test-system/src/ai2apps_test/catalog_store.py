from __future__ import annotations

import base64
import binascii
import difflib
import hashlib
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .catalog_validation import (
    ID_PATTERN,
    require_valid,
    validate_case,
    validate_group,
    validate_pipeline,
)


class CatalogConflictError(RuntimeError):
    pass


FIXTURE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_FIXTURE_BYTES = 10 * 1024 * 1024


class CatalogStore:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        configured = self.repo_root / "tests" / "ats" / "catalog"
        if configured.is_symlink():
            raise ValueError("catalog root cannot be a symbolic link")
        self.root = configured.resolve()

    def _directory(self, kind: str, archived: bool = False) -> Path:
        if kind not in {"groups", "cases", "pipelines", "case-content"}:
            raise ValueError("invalid catalog object kind")
        return self.root / ("archived" if archived else "") / kind

    def _path(self, kind: str, object_id: str, archived: bool = False) -> Path:
        if not ID_PATTERN.fullmatch(object_id):
            raise ValueError("invalid catalog object ID")
        path = self._directory(kind, archived) / f"{object_id}.yaml"
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        if parent.is_symlink() or self.root not in path.resolve(strict=False).parents:
            raise ValueError("catalog path escapes the configured root")
        return path

    @staticmethod
    def revision_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def read_path(self, path: Path) -> dict[str, Any]:
        raw = path.read_bytes()
        value = yaml.safe_load(raw)
        if not isinstance(value, dict):
            raise ValueError(f"catalog object must be a mapping: {path}")
        value = dict(value)
        value["revision"] = self.revision_bytes(raw)
        value["sourcePath"] = str(path.relative_to(self.root.parent.parent.parent))
        return value

    def list_objects(self, kind: str, archived: bool = False) -> list[dict[str, Any]]:
        directory = self._directory(kind, archived)
        if not directory.is_dir() or directory.is_symlink():
            return []
        return [
            self.read_path(path)
            for path in sorted(directory.glob("*.yaml"))
            if not path.is_symlink()
        ]

    def get(self, kind: str, object_id: str, archived: bool = False) -> dict[str, Any]:
        return self.read_path(self._path(kind, object_id, archived))

    def _groups_for_validation(self) -> dict[str, dict[str, Any]]:
        return {item["id"]: item for item in self.list_objects("groups")}

    def fixture_errors(self, value: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        case_id = str(value.get("id", ""))
        prefix = f"tests/ats/fixtures/{case_id}/"
        fixture_root = (self.root.parent / "fixtures").resolve()
        fixtures = value.get("fixtures", [])
        if not isinstance(fixtures, list):
            return errors
        for fixture in fixtures:
            if not isinstance(fixture, str) or not fixture.startswith(prefix):
                errors.append(f"fixture must be inside {prefix}")
                continue
            path = (self.repo_root / fixture).resolve()
            if (
                fixture_root not in path.parents
                or not path.is_file()
                or path.is_symlink()
            ):
                errors.append(f"fixture does not exist or is unsafe: {fixture}")
        return errors

    def store_image_fixture(
        self, case_id: str, filename: str, encoded_content: str
    ) -> dict[str, Any]:
        self.get("cases", case_id)
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if safe_name != filename or suffix not in FIXTURE_SUFFIXES:
            raise ValueError("fixture must be a PNG, JPEG, WebP, or GIF image")
        try:
            content = base64.b64decode(encoded_content, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("fixture content is not valid base64") from error
        if not content or len(content) > MAX_FIXTURE_BYTES:
            raise ValueError("fixture image must be between 1 byte and 10 MB")
        signatures = {
            ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            ".jpg": content.startswith(b"\xff\xd8\xff"),
            ".jpeg": content.startswith(b"\xff\xd8\xff"),
            ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
            ".gif": content.startswith((b"GIF87a", b"GIF89a")),
        }
        if not signatures[suffix]:
            raise ValueError("fixture content does not match its image extension")
        slug = re.sub(r"[^a-z0-9-]+", "-", Path(safe_name).stem.lower()).strip("-")
        slug = (slug or "image")[:48]
        digest = hashlib.sha256(content).hexdigest()
        directory = self.root.parent / "fixtures" / case_id
        directory.mkdir(parents=True, exist_ok=True)
        if (
            directory.is_symlink()
            or self.root.parent.resolve() not in directory.resolve().parents
        ):
            raise ValueError("fixture path escapes the configured root")
        path = directory / f"{digest[:12]}-{slug}{suffix}"
        if not path.exists():
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temporary.write_bytes(content)
            os.replace(temporary, path)
        relative = str(path.relative_to(self.repo_root))
        return {"path": relative, "size": len(content), "sha256": digest}

    def save(
        self, kind: str, value: dict[str, Any], expected_revision: str | None = None
    ) -> dict[str, Any]:
        clean = {
            key: item
            for key, item in value.items()
            if key not in {"revision", "sourcePath", "sourceType", "editable"}
        }
        if kind == "groups":
            require_valid(validate_group(clean))
        elif kind == "cases":
            require_valid(
                validate_case(clean, self._groups_for_validation())
                + self.fixture_errors(clean)
            )
        elif kind == "pipelines":
            require_valid(validate_pipeline(clean))
        else:
            raise ValueError("invalid catalog object kind")
        path = self._path(kind, str(clean["id"]))
        if path.exists():
            previous = self.read_path(path)
            current = self.revision_bytes(path.read_bytes())
            if expected_revision is None or current != expected_revision:
                raise CatalogConflictError("catalog object changed on disk")
            if kind == "cases" and any(
                previous.get(field) != clean.get(field)
                for field in (
                    "executor",
                    "requires",
                    "instructions",
                    "expectations",
                    "cleanup",
                    "fixtures",
                )
            ):
                clean["enabled"] = False
                clean["lifecycle"] = "valid"
        elif expected_revision:
            raise CatalogConflictError("catalog object no longer exists")
        data = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False).encode(
            "utf-8"
        )
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)
        return self.get(kind, str(clean["id"]))

    def preview(self, kind: str, value: dict[str, Any]) -> str:
        clean = {
            key: item
            for key, item in value.items()
            if key not in {"revision", "sourcePath", "sourceType", "editable"}
        }
        path = self._path(kind, str(clean.get("id", "")))
        before = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        after = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False).splitlines()
        return "\n".join(
            difflib.unified_diff(
                before, after, fromfile=str(path), tofile=str(path), lineterm=""
            )
        )

    def archive(
        self, kind: str, object_id: str, expected_revision: str
    ) -> dict[str, Any]:
        source = self._path(kind, object_id)
        current = self.revision_bytes(source.read_bytes())
        if current != expected_revision:
            raise CatalogConflictError("catalog object changed on disk")
        destination = self._path(kind, object_id, archived=True)
        if destination.exists():
            raise CatalogConflictError("archived object already exists")
        os.replace(source, destination)
        return self.get(kind, object_id, archived=True)

    def restore(
        self, kind: str, object_id: str, expected_revision: str
    ) -> dict[str, Any]:
        source = self._path(kind, object_id, archived=True)
        current = self.revision_bytes(source.read_bytes())
        if current != expected_revision:
            raise CatalogConflictError("catalog object changed on disk")
        destination = self._path(kind, object_id)
        if destination.exists():
            raise CatalogConflictError("active object already exists")
        os.replace(source, destination)
        return self.get(kind, object_id)
