"""Validate Skill snapshots and commit their lifecycle atomically."""

import base64
import hashlib
import io
import json
import re
import sqlite3
import stat
import time
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath
from uuid import uuid4

import yaml

MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 256
MAX_PREVIEWS = 8
MAX_LIBRARY_BYTES = 128 * 1024 * 1024
PREVIEW_SECONDS = 1800
MAX_BOT_SKILLS = 12
MAX_REFERENCE_BYTES = 8 * 1024
MAX_REFERENCES_PER_RUN = 4
REFERENCE_SUFFIXES = frozenset({".md", ".txt", ".rst", ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml"})


def principal_owner(principal):
    return json.dumps([principal.installation_id, principal.organization_id, principal.actor_user_id])


def skill_path(value: str) -> str:
    parts = value.split("/")
    if len(value) > 512 or len(parts) > 16 or any(
        not part or part in {".", ".."} or "\\" in part or ":" in part
        or any(ord(char) < 32 for char in part) for part in parts
    ):
        raise ValueError("Invalid path in Skill folder")
    return value


def is_text_reference(path: str) -> bool:
    try:
        return (skill_path(path).startswith("references/")
                and PurePosixPath(path).suffix.lower() in REFERENCE_SUFFIXES)
    except ValueError:
        return False


def validate_skill(folder: str, files: dict[str, bytes]) -> dict:
    if not 1 <= len(files) <= MAX_FILES or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError("Skill exceeds the file count or size limit")
    # Check each path prefix to catch file/directory and case-folding collisions.
    prefixes = {}
    for path in files:
        skill_path(path)
        for prefix in (PurePosixPath(path), *PurePosixPath(path).parents):
            label = str(prefix)
            key = label.casefold()
            if prefixes.setdefault(key, label) != label:
                raise ValueError("Skill includes conflicting paths")
            if label != path and label in files:
                raise ValueError("Skill includes a file where a directory is needed")
    entry = files.get("SKILL.md")
    if not entry or len(entry) > 64 * 1024:
        raise ValueError("SKILL.md is missing or exceeds 64 KiB")
    markdown = entry.decode("utf-8-sig")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", markdown, re.S)
    if not match or len(match[1]) > 8192:
        raise ValueError("SKILL.md requires YAML front matter")
    try:
        header = yaml.safe_load(match[1])
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValueError("Invalid SKILL.md front matter") from exc
    if not isinstance(header, dict):
        raise ValueError("Invalid SKILL.md front matter")
    name, description = header.get("name"), header.get("description")
    if not isinstance(name, str) or name != folder or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        raise ValueError("Skill name must match its folder and use lowercase letters, numbers and hyphens")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ValueError("Skill requires a description of up to 1024 characters")
    metadata = header.get("metadata")
    return {
        "name": name,
        "description": description,
        "license": header.get("license") if isinstance(header.get("license"), str) else None,
        "requirements": header.get("compatibility") if isinstance(header.get("compatibility"), str) else None,
        "tools": header.get("allowed-tools") if isinstance(header.get("allowed-tools"), str) else None,
        "files": sorted(files),
        "scripts": sorted(path for path in files if path.startswith("scripts/")),
        "manual_only": header.get("disable-model-invocation") is True or (
            isinstance(metadata, dict) and metadata.get("opencode/autoinvoke") in (False, "false")
        ),
        "user_invocable": header.get("user-invocable") is not False,
        "unsupported": sorted(
            field for field in ("context", "hooks", "model", "agent", "effort", "background")
            if field in header
        ) + (["dynamic commands"] if re.search(r"(?:!\x60|^\s*!\s*\x60\x60\x60)", markdown[match.end():], re.M) else []),
    }


def folder_upload(entries: list[dict]) -> tuple[str, dict[str, bytes]]:
    if not 1 <= len(entries) <= MAX_FILES:
        raise ValueError("Select one Skill folder containing up to 256 files")
    folder = None
    files = {}
    size = 0
    for item in entries:
        root, sep, path = skill_path(item["path"]).partition("/")
        if not sep or (folder is not None and folder != root) or path in files:
            raise ValueError("Select one Skill folder with unique file paths")
        folder = root
        data = base64.b64decode(item["content"], validate=True)
        size += len(data)
        if size > MAX_BYTES:
            raise ValueError("Skill exceeds the size limit")
        files[path] = data
    return folder, files


def archive_skill(name: str, files: dict[str, bytes]) -> tuple[str, bytes]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(f"{name}/{path}")
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
    payload = buffer.getvalue()
    return hashlib.sha256(payload).hexdigest(), payload


class SkillLibrary:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "skills.sqlite3"

    def connect(self):
        return closing(self._connect())

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS skill_previews (
                owner TEXT, id TEXT, expires REAL, target TEXT, base_revision TEXT,
                source TEXT, source_key TEXT, revision TEXT, metadata TEXT, archive BLOB,
                result_id TEXT,
                PRIMARY KEY(owner, id)
            );
            CREATE TABLE IF NOT EXISTS skill_revisions (
                owner TEXT, revision TEXT, archive BLOB,
                PRIMARY KEY(owner, revision)
            );
            CREATE TABLE IF NOT EXISTS installed_skills (
                owner TEXT, id TEXT, source TEXT, source_key TEXT, revision TEXT, metadata TEXT,
                PRIMARY KEY(owner, id), UNIQUE(owner, source_key, revision)
            );
            CREATE TABLE IF NOT EXISTS skill_mini_apps (
                owner TEXT NOT NULL, id TEXT NOT NULL, skill TEXT NOT NULL,
                revision TEXT NOT NULL, studio TEXT NOT NULL, config TEXT NOT NULL,
                PRIMARY KEY(owner, id)
            );
            CREATE TABLE IF NOT EXISTS bot_skills (
                owner TEXT, bot TEXT, skill TEXT, grant_id TEXT NOT NULL,
                PRIMARY KEY(owner,bot,skill)
            );
            CREATE TABLE IF NOT EXISTS bot_skill_revisions (
                owner TEXT, grant_id TEXT, revision TEXT,
                PRIMARY KEY(owner,grant_id,revision)
            );
            CREATE TABLE IF NOT EXISTS bot_disabled_skills (
                owner TEXT NOT NULL, bot TEXT NOT NULL, skill TEXT NOT NULL,
                PRIMARY KEY(owner,bot,skill)
            );
        """)
        return connection

    @staticmethod
    def summary(row):
        return {"id": row["id"], "source": json.loads(row["source"]),
                "revision": row["revision"], **json.loads(row["metadata"])}

    def list(self, owner: str) -> list[dict]:
        with self.connect() as db:
            return [self.summary(row) for row in db.execute(
                "SELECT * FROM installed_skills WHERE owner=? ORDER BY rowid", (owner,)
            )]

    def preview(self, owner, folder, files, source, source_key, target=None, expected_revision=None):
        metadata = validate_skill(folder, files)
        revision, archive = archive_skill(folder, files)
        now, preview_id = time.time(), uuid4().hex
        changes = None
        with self.connect() as db, db:
            db.execute("DELETE FROM skill_previews WHERE expires<=?", (now,))
            if target:
                current = self._installed(db, owner, target)
                if source_key != current["source_key"]:
                    raise ValueError("Choose the original Skill source to update this installation")
                if current["revision"] != expected_revision:
                    raise ValueError("Installed Skill changed. Reopen it before updating")
                old_archive = db.execute(
                    "SELECT archive FROM skill_revisions WHERE owner=? AND revision=?",
                    (owner, expected_revision),
                ).fetchone()[0]
                with zipfile.ZipFile(io.BytesIO(old_archive)) as previous:
                    old_paths = {path.split("/", 1)[1] for path in previous.namelist()}
                    changes = {
                        "added": sorted(files.keys() - old_paths),
                        "removed": sorted(old_paths - files.keys()),
                        "modified": sorted(
                            path for path in old_paths & files.keys()
                            if previous.read(f"{folder}/{path}") != files[path]
                        ),
                    }
            db.execute(
                """DELETE FROM skill_previews WHERE owner=? AND id IN (
                   SELECT id FROM skill_previews WHERE owner=? ORDER BY expires DESC LIMIT -1 OFFSET ?
                )""", (owner, owner, MAX_PREVIEWS - 1)
            )
            db.execute("""INSERT INTO skill_previews
                       (owner,id,expires,target,base_revision,source,source_key,revision,metadata,archive)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                       (owner, preview_id, now + PREVIEW_SECONDS, target, expected_revision,
                        json.dumps(source), source_key, revision, json.dumps(metadata), archive))
        return {"id": preview_id, "revision": revision, "source": source, "changes": changes, **metadata,
                "markdown": files["SKILL.md"].decode("utf-8-sig")}

    def review_snapshot(self, owner, preview_id):
        with self.connect() as db:
            row = db.execute(
                """SELECT revision,source,archive FROM skill_previews
                   WHERE owner=? AND id=? AND expires>? AND result_id IS NULL""",
                (owner, preview_id, time.time()),
            ).fetchone()
        if row is None:
            raise LookupError("Skill preview expired. Preview the import again")
        return row["revision"], json.loads(row["source"]), row["archive"]

    @staticmethod
    def _installed(db, owner, skill_id):
        row = db.execute("SELECT * FROM installed_skills WHERE owner=? AND id=?", (owner, skill_id)).fetchone()
        if row is None:
            raise LookupError("Skill installation not found")
        return row

    def install(self, owner, preview_id):
        with self.connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            preview = db.execute(
                "SELECT * FROM skill_previews WHERE owner=? AND id=? AND expires>?",
                (owner, preview_id, time.time()),
            ).fetchone()
            if preview is None:
                raise LookupError("Skill preview expired. Preview the import again")
            target = preview["target"]
            revision = preview["revision"]
            if preview["result_id"]:
                current = self._installed(db, owner, preview["result_id"])
                if current["revision"] != revision:
                    raise ValueError("Installed Skill changed. Preview the import again")
                return self.summary(current)
            existing = db.execute(
                "SELECT * FROM installed_skills WHERE owner=? AND source_key=? AND revision=?",
                (owner, preview["source_key"], revision),
            ).fetchone()
            if target:
                current = self._installed(db, owner, target)
                if current["revision"] not in {preview["base_revision"], revision}:
                    raise ValueError("Installed Skill changed. Preview the update again")
                if existing and existing["id"] != target:
                    raise ValueError("That version is already installed separately")
            elif existing:
                target = existing["id"]
            else:
                target = uuid4().hex
            present = db.execute(
                "SELECT 1 FROM skill_revisions WHERE owner=? AND revision=?", (owner, revision)
            ).fetchone()
            if not present:
                total = db.execute(
                    "SELECT COALESCE(SUM(length(archive)),0) FROM skill_revisions WHERE owner=?", (owner,)
                ).fetchone()[0]
                if total + len(preview["archive"]) > MAX_LIBRARY_BYTES:
                    raise ValueError("Skill library storage limit reached")
            db.execute("INSERT OR IGNORE INTO skill_revisions VALUES (?,?,?)",
                       (owner, revision, preview["archive"]))
            db.execute("""INSERT INTO installed_skills VALUES (?,?,?,?,?,?)
                       ON CONFLICT(owner,id) DO UPDATE SET source=excluded.source,
                       revision=excluded.revision, metadata=excluded.metadata""",
                       (owner, target, preview["source"], preview["source_key"], revision, preview["metadata"]))
            db.execute("UPDATE skill_previews SET result_id=?, archive=NULL WHERE owner=? AND id=?",
                       (target, owner, preview_id))
            self._prune(db, owner)
            return self.summary(self._installed(db, owner, target))

    @staticmethod
    def _prune(db, owner):
        db.execute("""DELETE FROM skill_revisions WHERE owner=? AND revision NOT IN
                      (SELECT revision FROM installed_skills WHERE owner=?
                       UNION SELECT revision FROM bot_skill_revisions WHERE owner=?
                       UNION SELECT revision FROM skill_mini_apps WHERE owner=?)""", (owner, owner, owner, owner))

    def _revoke(self, db, owner, skill_id, bot_id=None):
        where = "owner=? AND skill=?"
        params = (owner, skill_id)
        if bot_id is not None:
            where += " AND bot=?"
            params += (bot_id,)
        db.execute("DELETE FROM bot_skill_revisions WHERE owner=? AND grant_id IN "
                   f"(SELECT grant_id FROM bot_skills WHERE {where})", (owner, *params))
        db.execute(f"DELETE FROM bot_skills WHERE {where}", params)

    def bot_items(self, owner, bot_id):
        with self.connect() as db:
            return [{**self.summary(row), "enabled": row["grant_id"] is not None,
                     "added": row["grant_id"] is not None or row["disabled"] is not None}
                    for row in db.execute("""
                SELECT s.*, b.grant_id, d.skill AS disabled FROM installed_skills s LEFT JOIN bot_skills b
                ON b.owner=s.owner AND b.skill=s.id AND b.bot=?
                LEFT JOIN bot_disabled_skills d ON d.owner=s.owner AND d.skill=s.id AND d.bot=?
                WHERE s.owner=? ORDER BY s.rowid
            """, (bot_id, bot_id, owner))]

    def set_bot_skill(self, owner, bot_id, skill_id, enabled):
        with self.connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            if enabled:
                item = self.summary(self._installed(db, owner, skill_id))
                if item["unsupported"]:
                    raise ValueError("This Skill requires features from another host")
                if db.execute("SELECT 1 FROM bot_skills WHERE owner=? AND bot=? AND skill=?",
                              (owner, bot_id, skill_id)).fetchone():
                    return
                count = db.execute("SELECT count(*) FROM bot_skills WHERE owner=? AND bot=?",
                                   (owner, bot_id)).fetchone()[0]
                if count >= MAX_BOT_SKILLS:
                    raise ValueError(f"A Bot can enable up to {MAX_BOT_SKILLS} Skills")
                db.execute("INSERT INTO bot_skills VALUES (?,?,?,?)",
                           (owner, bot_id, skill_id, uuid4().hex))
                db.execute("DELETE FROM bot_disabled_skills WHERE owner=? AND bot=? AND skill=?",
                           (owner, bot_id, skill_id))
            else:
                db.execute("""INSERT OR IGNORE INTO bot_disabled_skills
                              SELECT owner, bot, skill FROM bot_skills
                              WHERE owner=? AND bot=? AND skill=?""", (owner, bot_id, skill_id))
                self._revoke(db, owner, skill_id, bot_id)
                self._prune(db, owner)

    def remove_bot_skill(self, owner, bot_id, skill_id):
        with self.connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._revoke(db, owner, skill_id, bot_id)
            db.execute("DELETE FROM bot_disabled_skills WHERE owner=? AND bot=? AND skill=?",
                       (owner, bot_id, skill_id))
            self._prune(db, owner)

    def bot_snapshot(self, owner, bot_id):
        with self.connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("""
                SELECT s.*, b.grant_id FROM installed_skills s JOIN bot_skills b
                ON b.owner=s.owner AND b.skill=s.id WHERE s.owner=? AND b.bot=? ORDER BY s.rowid
            """, (owner, bot_id)).fetchall()
            snapshot = []
            for row in rows:
                item = self.summary(row)
                if item["unsupported"]:
                    continue
                db.execute("INSERT OR IGNORE INTO bot_skill_revisions VALUES (?,?,?)",
                           (owner, row["grant_id"], row["revision"]))
                snapshot.append({key: item[key] for key in (
                    "id", "revision", "name", "description", "manual_only", "user_invocable"
                )} | {"grant_id": row["grant_id"], "references": [
                    path for path in item["files"] if is_text_reference(path)
                ]})
        return snapshot

    def bot_entry(self, owner, bot_id, pin, *, read=True):
        content = self.bot_content(owner, bot_id, pin, read=read)
        return content[0] if content is not None else None

    def bot_content(self, owner, bot_id, pin, *, paths=(), read=True):
        allowed = set(pin.get("references", ()))
        if (len(paths) > MAX_REFERENCES_PER_RUN or len(set(paths)) != len(paths)
                or any(path not in allowed or not is_text_reference(path) for path in paths)):
            raise ValueError("Invalid Skill reference request")
        column = "r.archive" if read else "1"
        with self.connect() as db:
            row = db.execute(f"""
                SELECT {column} FROM bot_skills b JOIN bot_skill_revisions p USING(owner,grant_id)
                JOIN skill_revisions r USING(owner,revision)
                WHERE b.owner=? AND b.bot=? AND b.skill=? AND b.grant_id=? AND p.revision=?
            """, (owner, bot_id, pin["id"], pin["grant_id"], pin["revision"])).fetchone()
        if row is None:
            raise PermissionError("The selected Skill was disabled or uninstalled")
        if read:
            with zipfile.ZipFile(io.BytesIO(row["archive"])) as archive:
                root = pin["name"]
                entry = archive.read(f"{root}/SKILL.md").decode("utf-8-sig")
                sources = []
                for path in paths:
                    try:
                        file = archive.getinfo(f"{root}/{path}")
                        if file.file_size > MAX_REFERENCE_BYTES:
                            sources.append({"path": path, "unavailable": "File exceeds 8 KiB"})
                            continue
                        content = archive.read(file).decode("utf-8-sig")
                        if "\0" in content:
                            raise ValueError("Binary file")
                    except (KeyError, UnicodeError, ValueError):
                        sources.append({"path": path, "unavailable": "UTF-8 text is unavailable"})
                    else:
                        sources.append({"path": path, "text": content})
                return entry, sources

    def remove(self, owner, skill_id):
        with self.connect() as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._revoke(db, owner, skill_id)
            db.execute("DELETE FROM bot_disabled_skills WHERE owner=? AND skill=?", (owner, skill_id))
            db.execute("DELETE FROM skill_mini_apps WHERE owner=? AND skill=?", (owner, skill_id))
            db.execute("DELETE FROM installed_skills WHERE owner=? AND id=?", (owner, skill_id))
            self._prune(db, owner)

    def export(self, owner, skill_id):
        with self.connect() as db:
            row = db.execute(
                """SELECT installed_skills.*, archive FROM installed_skills
                   JOIN skill_revisions USING(owner,revision) WHERE owner=? AND id=?""",
                (owner, skill_id),
            ).fetchone()
            if row is None:
                raise LookupError("Skill installation not found")
            return self.summary(row), row["archive"]
