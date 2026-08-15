"""Persistence for interactive packages, Patches, effective definitions, and mounts."""

from __future__ import annotations

import json
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    ResourceNotFoundError,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .models import (
    EffectiveDefinitionRecord,
    InteractivePackageRecord,
    InteractivePackageStatus,
    LocalPatchRecord,
    PatchStatus,
    RebasePolicy,
    UnitKind,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _time(value):
    return None if value is None else parse_utc(value)


class ExtensionRepository:
    def __init__(self, database: PlatformDatabase, events: EventStore) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _package(row) -> InteractivePackageRecord:
        return InteractivePackageRecord(
            row["id"],
            UnitKind(row["package_kind"]),
            row["unit_key"],
            row["package_version"],
            row["package_digest"],
            row["publisher_key"],
            row["archive_path"],
            row["store_path"],
            json.loads(row["manifest_json"]),
            tuple(json.loads(row["file_index_json"])),
            json.loads(row["sbom_json"]),
            json.loads(row["verification_json"]),
            InteractivePackageStatus(row["status"]),
            parse_utc(row["installed_at"]),
            _time(row["activated_at"]),
            _time(row["retired_at"]),
        )

    @staticmethod
    def _patch(row) -> LocalPatchRecord:
        return LocalPatchRecord(
            row["id"],
            UnitKind(row["target_kind"]),
            row["target_key"],
            row["patch_version"],
            row["patch_digest"],
            row["base_digest"],
            row["intent"],
            RebasePolicy(row["rebase_policy"]),
            tuple(json.loads(row["operations_json"])),
            json.loads(row["resources_json"]),
            tuple(json.loads(row["tests_json"])),
            json.loads(row["audit_json"]),
            json.loads(row["signature_json"]),
            row["stack_order"],
            PatchStatus(row["status"]),
            None if row["conflict_json"] is None else json.loads(row["conflict_json"]),
            row["archive_path"],
            row["store_path"],
            parse_utc(row["created_at"]),
            parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _effective(row) -> EffectiveDefinitionRecord:
        return EffectiveDefinitionRecord(
            row["id"],
            UnitKind(row["unit_kind"]),
            row["unit_key"],
            row["upstream_digest"],
            row["patch_set_digest"],
            row["effective_digest"],
            row["effective_version"],
            json.loads(row["manifest_json"]),
            json.loads(row["resources_json"]),
            json.loads(row["audit_json"]),
            row["status"],
            row["revision"],
            parse_utc(row["created_at"]),
            _time(row["activated_at"]),
            _time(row["retired_at"]),
        )

    def installed(self, kind: UnitKind | None = None, key: str | None = None):
        query = "SELECT * FROM interactive_packages WHERE status != 'uninstalled'"
        params = []
        if kind:
            query += " AND package_kind = ?"
            params.append(kind.value)
        if key:
            query += " AND unit_key = ?"
            params.append(key)
        query += " ORDER BY package_kind, unit_key, installed_at DESC"
        with self.database.transaction() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(self._package(row) for row in rows)

    def active_package(self, kind: UnitKind, key: str):
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM interactive_packages WHERE package_kind=? AND unit_key=? AND status='active'",
                (kind.value, key),
            ).fetchone()
        return None if row is None else self._package(row)

    def package(self, digest: str):
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM interactive_packages WHERE package_digest=?", (digest,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("interactive_package", digest)
        return self._package(row)

    def record_package(self, bundle, store: str, verification: dict):
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM interactive_packages WHERE package_digest=?",
                (bundle.digest,),
            ).fetchone()
            if row is not None and row["unit_key"] != bundle.key:
                legacy_key = str(row["unit_key"])
                if legacy_key.replace("/", ".") != bundle.key:
                    raise ValueError(
                        "Package digest is already bound to another runtime identity"
                    )
                # Registry v1 package IDs contain a namespace separator while
                # local App/Agent routes use a single dotted key. Early
                # prototypes stored the slash form directly. Migrate that
                # exact legacy identity in place so the immutable artifact
                # digest remains the package identity.
                connection.execute(
                    "UPDATE app_definitions SET status='disabled',updated_at=? "
                    "WHERE package_id=? AND status='enabled'",
                    (now, legacy_key),
                )
                connection.execute(
                    "UPDATE agent_definitions SET status='disabled',updated_at=? "
                    "WHERE agent_key=? AND status='enabled'",
                    (now, legacy_key),
                )
                connection.execute(
                    "UPDATE effective_definitions SET status='retained',retired_at=? "
                    "WHERE unit_kind=? AND unit_key=? AND status='active'",
                    (now, bundle.kind.value, legacy_key),
                )
                connection.execute(
                    """UPDATE interactive_packages
                    SET unit_key=?,manifest_json=?,archive_path=?,store_path=?,
                        verification_json=?,status='installed',retired_at=NULL
                    WHERE package_digest=?""",
                    (
                        bundle.key,
                        _json(bundle.manifest),
                        str(bundle.archive_path),
                        store,
                        _json(verification),
                        bundle.digest,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM interactive_packages WHERE package_digest=?",
                    (bundle.digest,),
                ).fetchone()
            if row is None:
                package_id = new_entity_id(EntityIdKind.INTERACTIVE_PACKAGE)
                connection.execute(
                    """INSERT INTO interactive_packages(id,package_kind,unit_key,package_version,
                    package_digest,publisher_key,archive_path,store_path,manifest_json,file_index_json,
                    sbom_json,verification_json,status,installed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        package_id,
                        bundle.kind.value,
                        bundle.key,
                        bundle.version,
                        bundle.digest,
                        bundle.manifest["publisher"]["id"],
                        str(bundle.archive_path),
                        store,
                        _json(bundle.manifest),
                        _json([vars_file(item) for item in bundle.files]),
                        _json(bundle.sbom),
                        _json(verification),
                        "installed",
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM interactive_packages WHERE id=?", (package_id,)
                ).fetchone()
            return self._package(row)

    def activate_package(self, record: InteractivePackageRecord):
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE interactive_packages SET status='retained',retired_at=? WHERE package_kind=? AND unit_key=? AND status='active'",
                (now, record.kind.value, record.unit_key),
            )
            connection.execute(
                "UPDATE interactive_packages SET status='active',activated_at=?,retired_at=NULL WHERE package_digest=?",
                (now, record.digest),
            )
        return self.package(record.digest)

    def set_package_status(
        self, digest: str, status: InteractivePackageStatus
    ) -> InteractivePackageRecord:
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                "UPDATE interactive_packages SET status=? WHERE package_digest=?",
                (status.value, digest),
            )
            if cursor.rowcount == 0:
                raise ResourceNotFoundError("interactive_package", digest)
        return self.package(digest)

    def patches(self, kind: UnitKind, key: str, *, enabled_only=False):
        query = "SELECT * FROM local_patches WHERE target_kind=? AND target_key=?"
        if enabled_only:
            query += " AND status NOT IN ('disabled','superseded')"
        query += " ORDER BY stack_order,id"
        with self.database.transaction() as connection:
            rows = connection.execute(query, (kind.value, key)).fetchall()
        return tuple(self._patch(row) for row in rows)

    def record_patch(self, bundle, store: str, verification: dict):
        manifest = bundle.manifest
        target = manifest["target"]
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM local_patches WHERE patch_digest=?", (bundle.digest,)
            ).fetchone()
            if row is None:
                order = connection.execute(
                    "SELECT COALESCE(MAX(stack_order),-1)+1 FROM local_patches WHERE target_kind=? AND target_key=?",
                    (target["kind"], target["id"]),
                ).fetchone()[0]
                patch_id = new_entity_id(EntityIdKind.LOCAL_PATCH)
                connection.execute(
                    """INSERT INTO local_patches(id,target_kind,target_key,patch_version,
                    patch_digest,base_digest,intent,rebase_policy,operations_json,resources_json,
                    tests_json,audit_json,signature_json,stack_order,status,archive_path,store_path,
                    created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        patch_id,
                        target["kind"],
                        target["id"],
                        bundle.version,
                        bundle.digest,
                        manifest["base_digest"],
                        str(manifest.get("intent", "")),
                        manifest.get("rebase_policy", "strict"),
                        _json(manifest["operations"]),
                        _json(manifest.get("resources", {})),
                        _json(manifest.get("tests", [])),
                        _json(manifest.get("audit", {})),
                        _json(verification),
                        order,
                        "clean",
                        str(bundle.archive_path),
                        store,
                        now,
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM local_patches WHERE id=?", (patch_id,)
                ).fetchone()
            return self._patch(row)

    def set_patch(
        self, patch_id: str, status: PatchStatus, *, conflict=None, base_digest=None
    ):
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE local_patches SET status=?, conflict_json=?, base_digest=COALESCE(?,base_digest), updated_at=? WHERE id=?",
                (
                    status.value,
                    None if conflict is None else _json(conflict),
                    base_digest,
                    now,
                    patch_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM local_patches WHERE id=?", (patch_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("local_patch", patch_id)
        return self._patch(row)

    def effective(self, kind: UnitKind, key: str):
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM effective_definitions WHERE unit_kind=? AND unit_key=? AND status='active'",
                (kind.value, key),
            ).fetchone()
        return None if row is None else self._effective(row)

    def activate_effective(
        self,
        *,
        kind,
        key,
        upstream,
        patch_set,
        digest,
        version,
        manifest,
        resources,
        audit,
    ):
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM effective_definitions WHERE effective_digest=?",
                (digest,),
            ).fetchone()
            if row is None:
                eid = new_entity_id(EntityIdKind.EFFECTIVE_DEFINITION)
                connection.execute(
                    """INSERT INTO effective_definitions(id,unit_kind,unit_key,
                    upstream_digest,patch_set_digest,effective_digest,effective_version,manifest_json,
                    resources_json,audit_json,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        eid,
                        kind.value,
                        key,
                        upstream,
                        patch_set,
                        digest,
                        version,
                        _json(manifest),
                        _json(resources),
                        _json(audit),
                        "candidate",
                        now,
                    ),
                )
            connection.execute(
                "UPDATE effective_definitions SET status='retained',retired_at=? WHERE unit_kind=? AND unit_key=? AND status='active'",
                (now, kind.value, key),
            )
            connection.execute(
                "UPDATE effective_definitions SET status='active',activated_at=?,retired_at=NULL WHERE effective_digest=?",
                (now, digest),
            )
            row = connection.execute(
                "SELECT * FROM effective_definitions WHERE effective_digest=?",
                (digest,),
            ).fetchone()
        return self._effective(row)

    def begin_operation(
        self, kind: UnitKind, key: str, operation: str, detail: dict[str, Any]
    ) -> str:
        operation_id = new_entity_id(EntityIdKind.INTERACTIVE_OPERATION)
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "INSERT INTO interactive_operations VALUES(?,?,?,?,?,?,?,NULL)",
                (
                    operation_id,
                    kind.value,
                    key,
                    operation,
                    "running",
                    _json(detail),
                    utc_now_text(),
                ),
            )
            self.events.append_in_transaction(
                connection,
                event_type="interactive.operation.started",
                subject_id=operation_id,
                payload={"kind": kind.value, "key": key, "operation": operation},
            )
        return operation_id

    def settle_operation(
        self, operation_id: str, status: str, detail: dict[str, Any] | None = None
    ) -> None:
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT detail_json FROM interactive_operations WHERE id=?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("interactive_operation", operation_id)
            value = json.loads(row["detail_json"])
            value.update(detail or {})
            connection.execute(
                "UPDATE interactive_operations SET status=?,detail_json=?,finished_at=? WHERE id=?",
                (status, _json(value), utc_now_text(), operation_id),
            )
            self.events.append_in_transaction(
                connection,
                event_type="interactive.operation.finished",
                subject_id=operation_id,
                payload={"status": status, "detail": value},
            )

    def operations(self, kind: UnitKind | None = None, key: str | None = None):
        query = "SELECT * FROM interactive_operations WHERE 1=1"
        params = []
        if kind is not None:
            query += " AND unit_kind=?"
            params.append(kind.value)
        if key is not None:
            query += " AND unit_key=?"
            params.append(key)
        query += " ORDER BY created_at DESC LIMIT 500"
        with self.database.transaction() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(
            {
                "id": row["id"],
                "kind": row["unit_kind"],
                "key": row["unit_key"],
                "operation": row["operation"],
                "status": row["status"],
                "detail": json.loads(row["detail_json"]),
                "created_at": row["created_at"],
                "finished_at": row["finished_at"],
            }
            for row in rows
        )


def vars_file(item) -> dict:
    return {
        "path": item.path,
        "content_hash": item.content_hash,
        "size_bytes": item.size_bytes,
    }
