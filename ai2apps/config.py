"""Configuration paths owned by the AI2Apps platform layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PLATFORM_DATABASE_FILENAME = "ai2apps-platform.sqlite3"
PLATFORM_DATABASE_SCHEMA_VERSION = 22
DEFAULT_SESSION_WORKSPACE_QUOTA_BYTES = 512 * 1024 * 1024
DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES = 64 * 1024 * 1024
DEFAULT_WORKSPACE_READ_LIMIT_BYTES = 1024 * 1024
DEFAULT_SESSION_PROCESS_LIMIT = 4
DEFAULT_PROCESS_OUTPUT_LIMIT_BYTES = 4 * 1024 * 1024
DEFAULT_PROCESS_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024
DEFAULT_PROCESS_WALL_TIME_SECONDS = 300
DEFAULT_PROCESS_IDLE_TIME_SECONDS = 60
DEFAULT_PROCESS_CPU_TIME_SECONDS = 120
DEFAULT_TEMPORARY_SESSION_TTL_SECONDS = 24 * 60 * 60
DEFAULT_SESSION_RETENTION_INTERVAL_SECONDS = 60.0
BUILTIN_CHAT_PACKAGE_ID = "ai2apps.general-chat"
BUILTIN_CHAT_PACKAGE_VERSION = "1.0.0"
BUILTIN_CHAT_SINGLETON_KEY = "ai2apps.general-chat:user:local"


def resolve_projects_path(base_path: str | Path) -> Path:
    """Return the AI2Apps-owned source-project root.

    The server still accepts ``~/.omlx`` as a compatibility data root, but new
    Coder source projects must not inherit that legacy product namespace.
    Explicit non-legacy base paths remain self-contained.
    """

    override = os.environ.get("AI2APPS_PROJECTS_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    resolved = Path(base_path).expanduser().resolve()
    legacy_default = (Path.home() / ".omlx").resolve()
    if resolved == legacy_default:
        return (Path.home() / ".ai2apps" / "projects").resolve()
    return resolved / "projects"


@dataclass(frozen=True, slots=True)
class PlatformPaths:
    """Managed paths derived from the installation's existing data root."""

    base_path: Path
    database_path: Path
    artifacts_path: Path
    sandboxes_path: Path
    packages_path: Path
    projects_path: Path
    documents_path: Path
    browsers_path: Path
    secrets_path: Path

    @classmethod
    def from_base_path(cls, base_path: str | Path) -> PlatformPaths:
        """Resolve paths without creating or mutating the filesystem."""

        resolved = Path(base_path).expanduser().resolve()
        platform_root = resolved / "platform"
        return cls(
            base_path=resolved,
            database_path=platform_root / PLATFORM_DATABASE_FILENAME,
            artifacts_path=platform_root / "artifacts",
            sandboxes_path=platform_root / "sandboxes",
            packages_path=platform_root / "packages",
            projects_path=resolve_projects_path(resolved),
            documents_path=platform_root / "documents",
            browsers_path=platform_root / "browsers",
            secrets_path=platform_root / "secrets",
        )


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Bootstrap configuration before the platform database is opened."""

    paths: PlatformPaths | None
    database_schema_version: int = PLATFORM_DATABASE_SCHEMA_VERSION
    secret_backend: str = "auto"

    @property
    def database_filename(self) -> str:
        if self.paths is None:
            return PLATFORM_DATABASE_FILENAME
        return self.paths.database_path.name

    @classmethod
    def from_base_path(
        cls, base_path: str | Path, *, secret_backend: str = "auto"
    ) -> PlatformConfig:
        return cls(
            paths=PlatformPaths.from_base_path(base_path),
            secret_backend=secret_backend,
        )

    @classmethod
    def unconfigured(cls) -> PlatformConfig:
        return cls(paths=None)
