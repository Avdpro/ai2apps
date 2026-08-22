"""Persistence for trusted publishers, immutable packages, locks, and operations."""

from __future__ import annotations

import json
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .models import (
    AttestationRecord,
    AuditDecision,
    AuditRisk,
    DependencyLock,
    InspectedServicePackage,
    InstalledPackageRecord,
    PackageStatus,
    PublisherRecord,
    TrustStatus,
)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _time(value: str | None):
    return None if value is None else parse_utc(value)


class PackageRepository:
    def __init__(self, database: PlatformDatabase, events: EventStore) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _publisher(row) -> PublisherRecord:
        return PublisherRecord(
            id=row["id"],
            publisher_key=row["publisher_key"],
            display_name=row["display_name"],
            key_id=row["key_id"],
            algorithm=row["algorithm"],
            public_key=row["public_key"],
            trust_status=TrustStatus(row["trust_status"]),
            source=row["source"],
            metadata=json.loads(row["metadata_json"]),
            revision=row["revision"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            revoked_at=_time(row["revoked_at"]),
        )

    @staticmethod
    def _package(row) -> InstalledPackageRecord:
        from ai2apps.services import ServiceRuntimeMode

        return InstalledPackageRecord(
            id=row["id"],
            service_key=row["service_key"],
            package_version=row["package_version"],
            package_digest=row["package_digest"],
            publisher_key=row["publisher_key"],
            runtime_mode=ServiceRuntimeMode(row["runtime_mode"]),
            protocol=row["protocol"],
            entrypoint=row["entrypoint"],
            archive_path=row["archive_path"],
            store_path=row["store_path"],
            manifest=json.loads(row["manifest_json"]),
            permissions=json.loads(row["permissions_json"]),
            compatibility=json.loads(row["compatibility_json"]),
            sbom=json.loads(row["sbom_json"]),
            verification=json.loads(row["verification_json"]),
            status=PackageStatus(row["status"]),
            installed_at=parse_utc(row["installed_at"]),
            activated_at=_time(row["activated_at"]),
            retired_at=_time(row["retired_at"]),
        )

    def upsert_publisher(
        self,
        *,
        publisher_key: str,
        display_name: str,
        key_id: str,
        public_key: str,
        trust_status: TrustStatus,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> PublisherRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM publisher_trust WHERE publisher_key = ?",
                (publisher_key,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """INSERT INTO publisher_trust(
                        id, publisher_key, display_name, key_id, algorithm, public_key,
                        trust_status, source, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'ed25519', ?, ?, ?, ?, ?, ?)""",
                    (
                        new_entity_id(EntityIdKind.PUBLISHER),
                        publisher_key,
                        display_name,
                        key_id,
                        public_key,
                        trust_status.value,
                        source,
                        _json(metadata or {}),
                        now,
                        now,
                    ),
                )
            else:
                if row["key_id"] != key_id or row["public_key"] != public_key:
                    raise ResourceConflictError(
                        "Publisher key rotation requires a distinct publisher/key identity"
                    )
                connection.execute(
                    """UPDATE publisher_trust SET display_name = ?, trust_status = ?,
                       source = ?, metadata_json = ?, revision = revision + 1,
                       revoked_at = ?, updated_at = ? WHERE publisher_key = ?""",
                    (
                        display_name,
                        trust_status.value,
                        source,
                        _json(metadata or {}),
                        now if trust_status is TrustStatus.REVOKED else None,
                        now,
                        publisher_key,
                    ),
                )
            row = connection.execute(
                "SELECT * FROM publisher_trust WHERE publisher_key = ?",
                (publisher_key,),
            ).fetchone()
            assert row is not None
            self.events.append_in_transaction(
                connection,
                event_type="publisher.trust.updated",
                subject_id=row["id"],
                payload={
                    "publisher_key": publisher_key,
                    "trust_status": trust_status.value,
                    "key_id": key_id,
                },
            )
            return self._publisher(row)

    def get_publisher(self, publisher_key: str) -> PublisherRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM publisher_trust WHERE publisher_key = ?",
                (publisher_key,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("publisher", publisher_key)
        return self._publisher(row)

    def list_publishers(self) -> tuple[PublisherRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM publisher_trust ORDER BY publisher_key"
            ).fetchall()
        return tuple(self._publisher(row) for row in rows)

    def get_by_digest(self, digest: str) -> InstalledPackageRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM service_packages WHERE package_digest = ?", (digest,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("service_package", digest)
        return self._package(row)

    def active(self, service_key: str) -> InstalledPackageRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM service_packages WHERE service_key = ? AND status = 'active'",
                (service_key,),
            ).fetchone()
        return None if row is None else self._package(row)

    def installed(
        self, service_key: str | None = None
    ) -> tuple[InstalledPackageRecord, ...]:
        query = "SELECT * FROM service_packages WHERE status != 'uninstalled'"
        params: tuple[Any, ...] = ()
        if service_key is not None:
            query += " AND service_key = ?"
            params = (service_key,)
        query += " ORDER BY service_key, installed_at DESC"
        with self.database.transaction() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(self._package(row) for row in rows)

    def record_install(
        self,
        inspected: InspectedServicePackage,
        *,
        store_path: str,
        verification: dict[str, Any],
        status: PackageStatus = PackageStatus.INSTALLED,
    ) -> InstalledPackageRecord:
        now = utc_now_text()
        package_id = new_entity_id(EntityIdKind.SERVICE_PACKAGE)
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM service_packages WHERE package_digest = ?",
                (inspected.digest,),
            ).fetchone()
            if existing is not None:
                if existing["status"] != PackageStatus.UNINSTALLED.value:
                    return self._package(existing)
                # A failed first activation intentionally keeps an
                # ``uninstalled`` history row. Reinstalling the same verified
                # digest must revive that row; returning it unchanged makes
                # ``activate`` reject the package moments later.
                package_id = existing["id"]
                connection.execute(
                    """UPDATE service_packages SET
                        service_key = ?, package_version = ?, publisher_key = ?,
                        runtime_mode = ?, protocol = ?, entrypoint = ?,
                        archive_path = ?, store_path = ?, manifest_json = ?,
                        permissions_json = ?, compatibility_json = ?, sbom_json = ?,
                        verification_json = ?, status = ?, installed_at = ?,
                        activated_at = NULL, retired_at = NULL
                       WHERE id = ?""",
                    (
                        inspected.manifest.service_key,
                        inspected.manifest.version,
                        inspected.manifest.publisher_key,
                        inspected.manifest.runtime_mode.value,
                        inspected.manifest.protocol,
                        inspected.manifest.entrypoint,
                        str(inspected.archive_path),
                        store_path,
                        _json(inspected.manifest.raw),
                        _json(inspected.manifest.permissions),
                        _json(inspected.manifest.compatibility),
                        _json(inspected.sbom),
                        _json(verification),
                        status.value,
                        now,
                        package_id,
                    ),
                )
                connection.execute(
                    "DELETE FROM service_package_files WHERE package_id = ?",
                    (package_id,),
                )
            else:
                connection.execute(
                    """INSERT INTO service_packages(
                        id, service_key, package_version, package_digest, publisher_key,
                        runtime_mode, protocol, entrypoint, archive_path, store_path,
                        manifest_json, permissions_json, compatibility_json, sbom_json,
                        verification_json, status, installed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        package_id,
                        inspected.manifest.service_key,
                        inspected.manifest.version,
                        inspected.digest,
                        inspected.manifest.publisher_key,
                        inspected.manifest.runtime_mode.value,
                        inspected.manifest.protocol,
                        inspected.manifest.entrypoint,
                        str(inspected.archive_path),
                        store_path,
                        _json(inspected.manifest.raw),
                        _json(inspected.manifest.permissions),
                        _json(inspected.manifest.compatibility),
                        _json(inspected.sbom),
                        _json(verification),
                        status.value,
                        now,
                    ),
                )
            for item in inspected.files:
                connection.execute(
                    """INSERT INTO service_package_files(
                        package_id, path, content_hash, size_bytes, media_type
                    ) VALUES (?, ?, ?, ?, ?)""",
                    (
                        package_id,
                        item.path,
                        item.content_hash,
                        item.size_bytes,
                        item.media_type,
                    ),
                )
            self.events.append_in_transaction(
                connection,
                event_type="service.package.installed",
                subject_id=package_id,
                payload={
                    "service_key": inspected.manifest.service_key,
                    "version": inspected.manifest.version,
                    "digest": inspected.digest,
                    "status": status.value,
                },
            )
            row = connection.execute(
                "SELECT * FROM service_packages WHERE id = ?", (package_id,)
            ).fetchone()
            assert row is not None
            return self._package(row)

    def activate(self, service_key: str, digest: str) -> InstalledPackageRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            target = connection.execute(
                """SELECT * FROM service_packages WHERE service_key = ?
                   AND package_digest = ? AND status != 'uninstalled'""",
                (service_key, digest),
            ).fetchone()
            if target is None:
                raise ResourceNotFoundError("service_package", digest)
            connection.execute(
                """UPDATE service_packages SET status = 'retained', retired_at = ?
                   WHERE service_key = ? AND status = 'active' AND package_digest != ?""",
                (now, service_key, digest),
            )
            connection.execute(
                """UPDATE service_packages SET status = 'active', activated_at = ?,
                   retired_at = NULL WHERE package_digest = ?""",
                (now, digest),
            )
            self.events.append_in_transaction(
                connection,
                event_type="service.package.activated",
                subject_id=target["id"],
                payload={
                    "service_key": service_key,
                    "digest": digest,
                    "version": target["package_version"],
                },
            )
            row = connection.execute(
                "SELECT * FROM service_packages WHERE package_digest = ?", (digest,)
            ).fetchone()
            assert row is not None
            return self._package(row)

    def activate_with_relocked_dependents(
        self,
        service_key: str,
        digest: str,
        dependent_digests: tuple[str, ...],
    ) -> InstalledPackageRecord:
        """Atomically activate a provider and move compatible active locks to it."""

        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            target = connection.execute(
                """SELECT * FROM service_packages WHERE service_key = ?
                   AND package_digest = ? AND status != 'uninstalled'""",
                (service_key, digest),
            ).fetchone()
            if target is None:
                raise ResourceNotFoundError("service_package", digest)
            for dependent_digest in dependent_digests:
                cursor = connection.execute(
                    """UPDATE service_dependency_locks
                       SET dependency_version = ?, dependency_digest = ?, created_at = ?
                       WHERE package_digest = ? AND dependency_key = ? AND optional = 0""",
                    (
                        target["package_version"],
                        digest,
                        now,
                        dependent_digest,
                        service_key,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ResourceNotFoundError(
                        "service_dependency_lock",
                        f"{dependent_digest}:{service_key}",
                    )
            connection.execute(
                """UPDATE service_packages SET status = 'retained', retired_at = ?
                   WHERE service_key = ? AND status = 'active' AND package_digest != ?""",
                (now, service_key, digest),
            )
            connection.execute(
                """UPDATE service_packages SET status = 'active', activated_at = ?,
                   retired_at = NULL WHERE package_digest = ?""",
                (now, digest),
            )
            self.events.append_in_transaction(
                connection,
                event_type="service.package.activated",
                subject_id=target["id"],
                payload={
                    "service_key": service_key,
                    "digest": digest,
                    "version": target["package_version"],
                    "relocked_dependents": list(dependent_digests),
                },
            )
            row = connection.execute(
                "SELECT * FROM service_packages WHERE package_digest = ?", (digest,)
            ).fetchone()
            assert row is not None
            return self._package(row)

    def set_package_status(self, digest: str, status: PackageStatus) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            cursor = connection.execute(
                """UPDATE service_packages SET status = ?,
                   retired_at = CASE WHEN ? IN ('retained', 'uninstalled')
                                     THEN ? ELSE retired_at END
                   WHERE package_digest = ?""",
                (status.value, status.value, now, digest),
            )
            if cursor.rowcount == 0:
                raise ResourceNotFoundError("service_package", digest)

    def store_locks(
        self, service_key: str, digest: str, locks: tuple[DependencyLock, ...]
    ) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "DELETE FROM service_dependency_locks WHERE service_key = ? AND package_digest = ?",
                (service_key, digest),
            )
            for lock in locks:
                connection.execute(
                    """INSERT INTO service_dependency_locks(
                        service_key, package_digest, dependency_key, dependency_version,
                        dependency_digest, optional, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        service_key,
                        digest,
                        lock.dependency_key,
                        lock.dependency_version,
                        lock.dependency_digest,
                        int(lock.optional),
                        now,
                    ),
                )

    def locks(self, digest: str) -> tuple[DependencyLock, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM service_dependency_locks WHERE package_digest = ? ORDER BY dependency_key",
                (digest,),
            ).fetchall()
        return tuple(
            DependencyLock(
                row["service_key"],
                row["package_digest"],
                row["dependency_key"],
                row["dependency_version"],
                row["dependency_digest"],
                bool(row["optional"]),
            )
            for row in rows
        )

    def files(self, digest: str) -> tuple[dict[str, Any], ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT f.* FROM service_package_files f
                   JOIN service_packages p ON p.id = f.package_id
                   WHERE p.package_digest = ? ORDER BY f.path""",
                (digest,),
            ).fetchall()
        return tuple(
            {
                "path": row["path"],
                "content_hash": row["content_hash"],
                "size_bytes": row["size_bytes"],
                "media_type": row["media_type"],
            }
            for row in rows
        )

    def attestations(self, digest: str) -> tuple[AttestationRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM package_attestations WHERE package_digest = ?
                   ORDER BY created_at""",
                (digest,),
            ).fetchall()
        return tuple(
            AttestationRecord(
                id=row["id"],
                package_digest=row["package_digest"],
                kind=row["kind"],
                issuer=row["issuer"],
                decision=AuditDecision(row["decision"]),
                risk=AuditRisk(row["risk"]),
                model=row["model"],
                policy_version=row["policy_version"],
                evidence=json.loads(row["evidence_json"]),
                signature=json.loads(row["signature_json"]),
                created_at=parse_utc(row["created_at"]),
            )
            for row in rows
        )

    def dependents(self, service_key: str) -> tuple[str, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT DISTINCT p.service_key FROM service_dependency_locks l
                   JOIN service_packages p ON p.package_digest = l.package_digest
                   WHERE l.dependency_key = ? AND l.optional = 0 AND p.status = 'active'
                   ORDER BY p.service_key""",
                (service_key,),
            ).fetchall()
        return tuple(row[0] for row in rows)

    def add_attestation(
        self,
        *,
        package_digest: str,
        kind: str,
        issuer: str,
        decision: AuditDecision,
        risk: AuditRisk,
        evidence: dict[str, Any],
        model: str | None = None,
        policy_version: str | None = None,
        signature: dict[str, Any] | None = None,
    ) -> AttestationRecord:
        attestation_id = new_entity_id(EntityIdKind.PACKAGE_ATTESTATION)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO package_attestations(
                    id, package_digest, kind, issuer, decision, risk, model,
                    policy_version, evidence_json, signature_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    attestation_id,
                    package_digest,
                    kind,
                    issuer,
                    decision.value,
                    risk.value,
                    model,
                    policy_version,
                    _json(evidence),
                    _json(signature or {}),
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM package_attestations WHERE id = ?", (attestation_id,)
            ).fetchone()
            assert row is not None
        return AttestationRecord(
            id=row["id"],
            package_digest=row["package_digest"],
            kind=row["kind"],
            issuer=row["issuer"],
            decision=AuditDecision(row["decision"]),
            risk=AuditRisk(row["risk"]),
            model=row["model"],
            policy_version=row["policy_version"],
            evidence=json.loads(row["evidence_json"]),
            signature=json.loads(row["signature_json"]),
            created_at=parse_utc(row["created_at"]),
        )

    def begin_operation(
        self,
        service_key: str,
        operation: str,
        *,
        from_digest: str | None,
        to_digest: str | None,
        plan: dict[str, Any],
    ) -> str:
        operation_id = new_entity_id(EntityIdKind.SERVICE_OPERATION)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO service_operations(
                    id, service_key, operation, status, from_digest, to_digest,
                    plan_json, created_at, updated_at
                ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)""",
                (
                    operation_id,
                    service_key,
                    operation,
                    from_digest,
                    to_digest,
                    _json(plan),
                    now,
                    now,
                ),
            )
        return operation_id

    def settle_operation(
        self, operation_id: str, status: str, error: dict[str, Any] | None = None
    ) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE service_operations SET status = ?, error_json = ?,
                   updated_at = ?, completed_at = ? WHERE id = ?""",
                (
                    status,
                    None if error is None else _json(error),
                    now,
                    now,
                    operation_id,
                ),
            )

    def append_log(
        self,
        service_key: str,
        level: str,
        stream: str,
        message: str,
        *,
        process_id: str | None = None,
        fields: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM service_logs WHERE service_key = ?",
                (service_key,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO service_logs(
                    id, service_key, process_id, sequence, level, stream,
                    message, fields_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_entity_id(EntityIdKind.SERVICE_LOG),
                    service_key,
                    process_id,
                    sequence,
                    level,
                    stream,
                    message[:65536],
                    _json(fields or {}),
                    now,
                ),
            )
            connection.execute(
                """DELETE FROM service_logs WHERE service_key = ? AND sequence <= ?""",
                (service_key, max(0, int(sequence) - 10_000)),
            )

    def logs(
        self, service_key: str, *, after: int = 0, limit: int = 200
    ) -> tuple[dict[str, Any], ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM service_logs WHERE service_key = ? AND sequence > ?
                   ORDER BY sequence LIMIT ?""",
                (service_key, after, min(limit, 1000)),
            ).fetchall()
        return tuple(
            {
                "sequence": row["sequence"],
                "level": row["level"],
                "stream": row["stream"],
                "message": row["message"],
                "fields": json.loads(row["fields_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        )
