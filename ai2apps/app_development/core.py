"""Standard-library-only source draft, observed edits and reviewed write-back.

Inspired by DeepSeek Harness fs observation/edit and bounded read semantics.
Host identity, model execution, process confinement and preview remain adapters.
"""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from threading import RLock

MAX_FILES = 512
MAX_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TEXT_BYTES = 2 * 1024 * 1024
IGNORED = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "dist",
        ".build",
        ".DS_Store",
    }
)
SECRET_NAMES = (".env*", "*.pem", "*.key", ".npmrc", ".pypirc", "credentials*")


class DraftError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if (
        not relative
        or pure.is_absolute()
        or ".." in pure.parts
        or "\\" in relative
        or "\x00" in relative
    ):
        raise DraftError(
            "unsafe_path", "Use a relative path inside the development project."
        )
    if any(
        p in IGNORED or any(fnmatch.fnmatch(p, pattern) for pattern in SECRET_NAMES)
        for p in pure.parts
    ):
        raise DraftError(
            "excluded_path", "Dependency, generated and credential paths are excluded."
        )
    candidate = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise DraftError("symlink_path", "Symlink paths are not editable.")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise DraftError("unsafe_path", "Path leaves the development project.")
    return candidate


def atomic_write(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".appdev-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def files(root: Path):
    result, excluded, total = {}, [], 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        relative_dir = Path(directory).relative_to(root)
        for name in list(dirs):
            try:
                safe_path(root, (relative_dir / name).as_posix())
            except DraftError:
                dirs.remove(name)
                excluded.append((relative_dir / name).as_posix())
        for name in sorted(names):
            relative = (relative_dir / name).as_posix()
            try:
                path = safe_path(root, relative)
            except DraftError:
                excluded.append(relative)
                continue
            if not path.is_file():
                raise DraftError(
                    "unsupported_file",
                    "Only regular files can enter a development draft.",
                )
            size = path.stat().st_size
            total += size
            if size > MAX_FILE_BYTES or total > MAX_BYTES or len(result) >= MAX_FILES:
                raise DraftError(
                    "project_too_large",
                    "App development drafts allow 512 files, 8 MiB per file and 32 MiB total.",
                )
            content = path.read_bytes()
            result[relative] = {"sha256": digest(content), "bytes": len(content)}
    return result, excluded


class Draft:
    def __init__(self, source: Path, workspace: Path, state: Path):
        self.source, self.workspace, self.state = (
            source.resolve(),
            workspace.resolve(),
            state.resolve(),
        )
        self.lock = RLock()

    def create(self):
        with self.lock:
            if self.state.exists():
                raise DraftError("draft_exists", "Development draft already exists.")
            if (
                self.source == self.workspace
                or self.workspace.is_relative_to(self.source)
                or self.source.is_relative_to(self.workspace)
            ):
                raise DraftError(
                    "overlapping_roots",
                    "Project and draft directories must be independent.",
                )
            baseline, excluded = files(self.source)
            self.workspace.mkdir(parents=True, exist_ok=True)
            if any(self.workspace.iterdir()):
                raise DraftError(
                    "workspace_not_empty",
                    "A new development draft requires an empty workspace.",
                )
            for relative, meta in baseline.items():
                content = safe_path(self.source, relative).read_bytes()
                if digest(content) != meta["sha256"]:
                    raise DraftError(
                        "source_changed",
                        "Project changed during draft creation; start again.",
                    )
                atomic_write(safe_path(self.workspace, relative), content)
            self._save(
                {
                    "baseline": baseline,
                    "observed": {},
                    "excluded": excluded[:64],
                    "applied": False,
                }
            )
            return {"files": len(baseline), "excluded": excluded[:64]}

    def _load(self):
        value = json.loads(self.state.read_text())
        if value.get("source") != str(self.source) or value.get("workspace") != str(
            self.workspace
        ):
            raise DraftError(
                "draft_binding_changed", "Development draft binding changed."
            )
        return value

    def _save(self, value):
        value.update(source=str(self.source), workspace=str(self.workspace))
        atomic_write(self.state, json.dumps(value, sort_keys=True).encode())

    def read(self, relative, offset=1, limit=200):
        with self.lock:
            path = safe_path(self.workspace, relative)
            if not path.is_file():
                raise DraftError("file_not_found", "Draft file does not exist.")
            content = path.read_bytes()
            if len(content) > MAX_TEXT_BYTES:
                raise DraftError(
                    "file_too_large", "Text editing is limited to 2 MiB per file."
                )
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise DraftError(
                    "binary_file", "Use text tools only for UTF-8 source files."
                ) from exc
            lines = text.splitlines()
            if offset < 1 or not 1 <= limit <= 500:
                raise DraftError(
                    "invalid_window", "Use a positive line offset and 1–500 lines."
                )
            selected, used = [], 0
            for number, line in enumerate(
                lines[offset - 1 : offset - 1 + limit], start=offset
            ):
                rendered = f"{number}: {line[:2000]}"
                if used + len(rendered.encode()) > 16000:
                    break
                selected.append(rendered)
                used += len(rendered.encode())
            value = self._load()
            value["observed"][relative] = digest(content)
            self._save(value)
            return {
                "path": relative,
                "sha256": digest(content),
                "content": "\n".join(selected),
                "total_lines": len(lines),
                "next_offset": offset + len(selected)
                if offset + len(selected) <= len(lines)
                else None,
                "line_truncated": any(
                    len(line) > 2000
                    for line in lines[offset - 1 : offset - 1 + len(selected)]
                ),
            }

    def write(self, relative, content, expected_sha256=None):
        with self.lock:
            path = safe_path(self.workspace, relative)
            value = self._load()
            if value["applied"]:
                raise DraftError(
                    "draft_applied", "Start a new draft after applying changes."
                )
            if path.exists():
                current = digest(path.read_bytes())
                if (
                    not expected_sha256
                    or value["observed"].get(relative) != expected_sha256
                    or current != expected_sha256
                ):
                    raise DraftError(
                        "unobserved_or_changed",
                        "Read the current file and supply its sha256 before editing.",
                    )
            elif expected_sha256 is not None:
                raise DraftError("file_not_found", "Expected existing file is missing.")
            data = content.encode("utf-8")
            if len(data) > MAX_TEXT_BYTES:
                raise DraftError(
                    "file_too_large", "Text editing is limited to 2 MiB per file."
                )
            inventory, _ = files(self.workspace)
            total = (
                sum(item["bytes"] for item in inventory.values())
                - inventory.get(relative, {}).get("bytes", 0)
                + len(data)
            )
            if total > MAX_BYTES or (
                relative not in inventory and len(inventory) >= MAX_FILES
            ):
                raise DraftError(
                    "project_too_large", "Development draft quota exceeded."
                )
            atomic_write(path, data)
            value["observed"][relative] = digest(data)
            self._save(value)
            return {"ok": True, "path": relative, "sha256": digest(data)}

    def edit(self, relative, old, new, expected_sha256, replace_all=False):
        with self.lock:
            path = safe_path(self.workspace, relative)
            if not old or old == new:
                raise DraftError(
                    "invalid_edit",
                    "Provide non-empty old text and a different replacement.",
                )
            text = path.read_text(encoding="utf-8")
            count = text.count(old)
            if count == 0 or (not replace_all and count != 1):
                raise DraftError(
                    "ambiguous_edit",
                    "Old text must match exactly once, or explicitly use replace_all.",
                )
            return self.write(relative, text.replace(old, new), expected_sha256)

    def review(self):
        with self.lock:
            value = self._load()
            current, _ = files(self.workspace)
            changes = []
            for relative in sorted(set(value["baseline"]) | set(current)):
                before, after = value["baseline"].get(relative), current.get(relative)
                if before == after:
                    continue
                source = safe_path(self.source, relative)
                source_hash = digest(source.read_bytes()) if source.is_file() else None
                conflict = source_hash != (before or {}).get("sha256")
                change = {
                    "path": relative,
                    "before": before,
                    "after": after,
                    "conflict": conflict,
                    "kind": "deleted"
                    if after is None
                    else "new"
                    if before is None
                    else "modified",
                }
                if after is not None and not conflict:
                    try:
                        old = source.read_text(encoding="utf-8") if before else ""
                        new = safe_path(self.workspace, relative).read_text(
                            encoding="utf-8"
                        )
                        difference = "".join(
                            difflib.unified_diff(
                                old.splitlines(True),
                                new.splitlines(True),
                                fromfile=relative,
                                tofile=relative,
                            )
                        )
                        change["diff"] = difference[:16000]
                        change["diff_truncated"] = len(difference) > 16000
                    except UnicodeDecodeError:
                        change["binary"] = True
                changes.append(change)
            revision = digest(json.dumps(changes, sort_keys=True).encode())
            return {
                "revision": revision,
                "changes": changes,
                "applied": value["applied"],
                "excluded": value["excluded"],
            }

    def apply(self, revision):
        with self.lock:
            report = self.review()
            if report["applied"]:
                raise DraftError("draft_applied", "This draft was already applied.")
            if report["revision"] != revision:
                raise DraftError(
                    "review_changed", "Draft changed since review; review it again."
                )
            if any(change["conflict"] for change in report["changes"]):
                raise DraftError(
                    "source_conflict",
                    "Project changed outside the draft; do not overwrite it.",
                )
            if any(change["kind"] == "deleted" for change in report["changes"]):
                raise DraftError(
                    "deletion_not_supported",
                    "This version does not delete source files.",
                )
            value = self._load()
            # Retain original bytes outside the command-writable workspace.
            backup = self.state.parent / "backup"
            for change in report["changes"]:
                source = safe_path(self.source, change["path"])
                if source.is_file():
                    atomic_write(backup / change["path"], source.read_bytes())
            value["applying"] = {
                "revision": revision,
                "changes": report["changes"],
                "completed": [],
            }
            self._save(value)
            for change in report["changes"]:
                relative = change["path"]
                source = safe_path(self.source, relative)
                actual = digest(source.read_bytes()) if source.is_file() else None
                if actual != (change["before"] or {}).get("sha256"):
                    raise DraftError(
                        "source_conflict",
                        "Source changed during apply; partial receipt is retained.",
                    )
                content = safe_path(self.workspace, relative).read_bytes()
                if digest(content) != change["after"]["sha256"]:
                    raise DraftError(
                        "review_changed",
                        "Draft changed during apply; partial receipt is retained.",
                    )
                atomic_write(source, content)
                value["applying"]["completed"].append(relative)
                self._save(value)
            value["applied"] = True
            self._save(value)
            return {
                "ok": True,
                "applied": value["applying"]["completed"],
                "revision": revision,
            }
