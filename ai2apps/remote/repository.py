"""Durable non-secret Remote Access client state."""

from __future__ import annotations

from typing import Any

from ai2apps.core import parse_utc, utc_now_text
from ai2apps.storage import PlatformDatabase

from .models import RemoteDeviceRecord


class RemoteDeviceRepository:
    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _record(row) -> RemoteDeviceRecord:
        return RemoteDeviceRecord(
            device_id=row["device_id"], display_name=row["display_name"],
            platform=row["platform"], client_version=row["client_version"],
            status=row["status"], suspension_reason=row["suspension_reason"],
            access_epoch=int(row["access_epoch"]), public_origin=row["public_origin"],
            credential_version=int(row["credential_version"]),
            credential_expires_at=parse_utc(row["credential_expires_at"]),
            server_addr=row["server_addr"], server_port=int(row["server_port"]),
            proxy_name=row["proxy_name"], subdomain=row["subdomain"],
            secret_backend_key=row["secret_backend_key"], enabled=bool(row["enabled"]),
            online=bool(row["online"]), proxy_connected=bool(row["proxy_connected"]),
            last_seen_at=None if row["last_seen_at"] is None else parse_utc(row["last_seen_at"]),
            created_at=parse_utc(row["created_at"]), updated_at=parse_utc(row["updated_at"]),
        )

    def list(self) -> tuple[RemoteDeviceRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM remote_client_devices ORDER BY updated_at DESC"
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def get(self, device_id: str) -> RemoteDeviceRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM remote_client_devices WHERE device_id = ?", (device_id,)
            ).fetchone()
        return None if row is None else self._record(row)

    def upsert(self, device: dict[str, Any], connector: dict[str, Any], *, secret_backend_key: str) -> RemoteDeviceRecord:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO remote_client_devices(
                   device_id,display_name,platform,client_version,status,suspension_reason,
                   access_epoch,public_origin,credential_version,credential_expires_at,
                   server_addr,server_port,proxy_name,subdomain,secret_backend_key,
                   online,proxy_connected,last_seen_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(device_id) DO UPDATE SET
                   display_name=excluded.display_name,platform=excluded.platform,
                   client_version=excluded.client_version,status=excluded.status,
                   suspension_reason=excluded.suspension_reason,access_epoch=excluded.access_epoch,
                   public_origin=excluded.public_origin,credential_version=excluded.credential_version,
                   credential_expires_at=excluded.credential_expires_at,
                   server_addr=excluded.server_addr,server_port=excluded.server_port,
                   proxy_name=excluded.proxy_name,subdomain=excluded.subdomain,
                   secret_backend_key=excluded.secret_backend_key,online=excluded.online,
                   proxy_connected=excluded.proxy_connected,last_seen_at=excluded.last_seen_at,
                   updated_at=excluded.updated_at""",
                (
                    device["id"], device["displayName"], device["platform"],
                    device["clientVersion"], device["status"], device.get("suspensionReason"),
                    int(device["accessEpoch"]), device["publicOrigin"],
                    int(connector["credentialVersion"]), connector["credentialExpiresAt"],
                    connector["serverAddr"], int(connector["serverPort"]),
                    connector["proxyName"], connector["subdomain"], secret_backend_key,
                    int(bool(device.get("online"))), int(bool(device.get("proxyConnected"))),
                    device.get("lastSeenAt"), device.get("createdAt") or now, now,
                ),
            )
        record = self.get(device["id"])
        assert record is not None
        return record

    def update_cloud_state(self, device: dict[str, Any]) -> RemoteDeviceRecord | None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE remote_client_devices SET display_name=?,status=?,suspension_reason=?,
                   access_epoch=?,public_origin=?,credential_expires_at=?,online=?,
                   proxy_connected=?,last_seen_at=?,updated_at=? WHERE device_id=?""",
                (device["displayName"], device["status"], device.get("suspensionReason"),
                 int(device["accessEpoch"]), device["publicOrigin"],
                 device["credentialExpiresAt"], int(bool(device.get("online"))),
                 int(bool(device.get("proxyConnected"))), device.get("lastSeenAt"), now,
                 device["id"]),
            )
        return self.get(device["id"])

    def update_credential(self, device_id: str, credential: dict[str, Any]) -> RemoteDeviceRecord | None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE remote_client_devices SET credential_version=?,
                   credential_expires_at=?,updated_at=? WHERE device_id=?""",
                (int(credential["credentialVersion"]), credential["credentialExpiresAt"],
                 utc_now_text(), device_id),
            )
        return self.get(device_id)

    def set_enabled(self, device_id: str, enabled: bool) -> RemoteDeviceRecord | None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE remote_client_devices SET enabled=?,updated_at=? WHERE device_id=?",
                (int(enabled), utc_now_text(), device_id),
            )
        return self.get(device_id)

    def delete(self, device_id: str) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute("DELETE FROM remote_client_devices WHERE device_id=?", (device_id,))
