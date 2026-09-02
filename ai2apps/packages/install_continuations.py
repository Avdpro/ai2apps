"""Durable continuation state for Registry installs interrupted by restart."""

from __future__ import annotations

import json
from typing import Any

from ai2apps.core import utc_now_text
from ai2apps.storage.database import PlatformDatabase


class RegistryInstallContinuationRepository:
    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _record(row) -> dict[str, Any]:
        return {
            "packageId": row["package_id"],
            "version": row["package_version"],
            "approveReview": bool(row["approve_review"]),
            "dependency": json.loads(row["dependency_json"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def get(self, actor_id: str, installation_id: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM registry_install_continuations
                   WHERE actor_id=? AND installation_id=?""",
                (actor_id, installation_id),
            ).fetchone()
        return None if row is None else self._record(row)

    def save(
        self,
        *,
        actor_id: str,
        installation_id: str,
        package_id: str,
        version: str | None,
        approve_review: bool,
        dependency: dict[str, Any],
    ) -> dict[str, Any]:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO registry_install_continuations(
                       actor_id,installation_id,package_id,package_version,
                       approve_review,dependency_json,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(actor_id,installation_id) DO UPDATE SET
                       package_id=excluded.package_id,
                       package_version=excluded.package_version,
                       approve_review=excluded.approve_review,
                       dependency_json=excluded.dependency_json,
                       updated_at=excluded.updated_at""",
                (
                    actor_id,
                    installation_id,
                    package_id,
                    version,
                    int(approve_review),
                    json.dumps(dependency, separators=(",", ":"), sort_keys=True),
                    now,
                    now,
                ),
            )
        record = self.get(actor_id, installation_id)
        assert record is not None
        return record

    def delete(
        self,
        actor_id: str,
        installation_id: str,
        *,
        package_id: str | None = None,
    ) -> bool:
        query = (
            "DELETE FROM registry_install_continuations "
            "WHERE actor_id=? AND installation_id=?"
        )
        params: tuple[str, ...] = (actor_id, installation_id)
        if package_id is not None:
            query += " AND package_id=?"
            params = (*params, package_id)
        with self.database.transaction(write=True) as connection:
            result = connection.execute(query, params)
        return result.rowcount > 0
