"""Durable, user-scoped AceFox profile metadata."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from ai2apps.core import utc_now_text
from ai2apps.storage import PlatformDatabase

DEFAULT_BROWSER_PROFILE_KEY = "default"
_PROFILE_KEY = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class BrowserProfile:
    key: str
    name: str
    is_default: bool
    created_at: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "is_default": self.is_default,
            "created_at": self.created_at,
        }


class BrowserProfileRepository:
    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    def list_for_user(self, owner_user_id: str) -> list[BrowserProfile]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT profile_key,name,created_at FROM browser_profiles "
                "WHERE owner_user_id=? ORDER BY created_at,id",
                (owner_user_id,),
            ).fetchall()
        return [
            BrowserProfile(DEFAULT_BROWSER_PROFILE_KEY, "Default", True, None),
            *[
                BrowserProfile(
                    key=str(row["profile_key"]),
                    name=str(row["name"]),
                    is_default=False,
                    created_at=str(row["created_at"]),
                )
                for row in rows
            ],
        ]

    def create(self, owner_user_id: str, name: str) -> BrowserProfile:
        normalized = " ".join(name.split())
        if not 1 <= len(normalized) <= 80:
            raise ValueError("Profile name must contain 1 to 80 characters")
        now = utc_now_text()
        for _ in range(4):
            key = secrets.token_hex(16)
            try:
                with self.database.transaction(write=True) as connection:
                    connection.execute(
                        "INSERT INTO browser_profiles("
                        "id,owner_user_id,profile_key,name,created_at,updated_at"
                        ") VALUES(?,?,?,?,?,?)",
                        (f"bprof_{key}", owner_user_id, key, normalized, now, now),
                    )
                return BrowserProfile(key, normalized, False, now)
            except Exception as exc:
                if "UNIQUE constraint failed: browser_profiles" not in str(exc):
                    raise
        raise RuntimeError("Could not allocate a browser Profile ID")

    def require(self, owner_user_id: str, key: str) -> BrowserProfile:
        if key == DEFAULT_BROWSER_PROFILE_KEY:
            return BrowserProfile(key, "Default", True, None)
        if not _PROFILE_KEY.fullmatch(key):
            raise ValueError("Browser Profile ID is invalid")
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT profile_key,name,created_at FROM browser_profiles "
                "WHERE owner_user_id=? AND profile_key=?",
                (owner_user_id, key),
            ).fetchone()
        if row is None:
            raise KeyError("Browser Profile not found")
        return BrowserProfile(key, str(row["name"]), False, str(row["created_at"]))

    def delete(self, owner_user_id: str, key: str) -> None:
        if key == DEFAULT_BROWSER_PROFILE_KEY:
            raise ValueError("The default browser Profile cannot be deleted")
        self.require(owner_user_id, key)
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                "DELETE FROM browser_profiles WHERE owner_user_id=? AND profile_key=?",
                (owner_user_id, key),
            )
        if cursor.rowcount != 1:
            raise KeyError("Browser Profile not found")
