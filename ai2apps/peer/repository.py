"""Metadata-only durable Peer Session and replay records."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from ai2apps.core import parse_utc, utc_now_text
from ai2apps.storage import PlatformDatabase

from .identity import PeerProtocol
from .session import PeerEndpoint, PeerSession, PeerTransportPolicy


@dataclass(frozen=True, slots=True)
class PeerSessionRecord:
    session: PeerSession
    owner_user_id: str


class PeerSessionRepository:
    """Never persists compact Grants, candidates, public keys, or payload bytes."""

    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    def upsert(self, session: PeerSession, owner_user_id: str) -> None:
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM peer_sessions WHERE session_id=?", (session.session_id,)
            ).fetchone()
            if existing is not None and any((
                existing["owner_user_id"] != owner_user_id,
                existing["protocol"] != session.protocol.value,
                existing["purpose_type"] != session.purpose_type,
                existing["purpose_id"] != session.purpose_id,
                existing["self_user_id"] != session.self_endpoint.user_id,
                existing["self_device_id"] != session.self_endpoint.device_id,
                existing["self_installation_id"] != session.self_endpoint.installation_id,
                existing["peer_user_id"] != session.peer_endpoint.user_id,
                existing["peer_device_id"] != session.peer_endpoint.device_id,
                existing["peer_installation_id"] != session.peer_endpoint.installation_id,
            )):
                raise ValueError("Peer Session immutable authority changed")
            connection.execute(
                """
                INSERT INTO peer_sessions(
                    session_id,owner_user_id,protocol,purpose_type,purpose_id,status,
                    expires_at,self_user_id,self_device_id,self_installation_id,
                    self_access_epoch,self_key_id,self_key_epoch,peer_user_id,
                    peer_device_id,peer_installation_id,peer_access_epoch,peer_key_id,
                    peer_key_epoch,allowed_transports,max_bytes,max_streams,
                    policy_version,fallback_policy,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(session_id) DO UPDATE SET
                    status=excluded.status,expires_at=excluded.expires_at,
                    self_access_epoch=excluded.self_access_epoch,
                    self_key_id=excluded.self_key_id,self_key_epoch=excluded.self_key_epoch,
                    peer_access_epoch=excluded.peer_access_epoch,
                    peer_key_id=excluded.peer_key_id,peer_key_epoch=excluded.peer_key_epoch,
                    allowed_transports=excluded.allowed_transports,max_bytes=excluded.max_bytes,
                    max_streams=excluded.max_streams,policy_version=excluded.policy_version,
                    fallback_policy=excluded.fallback_policy,updated_at=excluded.updated_at
                """,
                (
                    session.session_id, owner_user_id, session.protocol.value,
                    session.purpose_type, session.purpose_id, session.status,
                    session.expires_at.isoformat(), session.self_endpoint.user_id,
                    session.self_endpoint.device_id, session.self_endpoint.installation_id,
                    session.self_endpoint.access_epoch, session.self_endpoint.key_id,
                    session.self_endpoint.key_epoch, session.peer_endpoint.user_id,
                    session.peer_endpoint.device_id, session.peer_endpoint.installation_id,
                    session.peer_endpoint.access_epoch, session.peer_endpoint.key_id,
                    session.peer_endpoint.key_epoch,
                    ",".join(session.transport_policy.allowed_transports),
                    str(session.transport_policy.max_bytes), session.transport_policy.max_streams,
                    session.transport_policy.policy_version,
                    session.transport_policy.fallback_policy, utc_now_text(),
                ),
            )

    @staticmethod
    def _endpoint(row: sqlite3.Row, prefix: str) -> PeerEndpoint:
        return PeerEndpoint(
            user_id=row[f"{prefix}_user_id"], device_id=row[f"{prefix}_device_id"],
            installation_id=row[f"{prefix}_installation_id"],
            access_epoch=int(row[f"{prefix}_access_epoch"]), key_id=row[f"{prefix}_key_id"],
            key_epoch=int(row[f"{prefix}_key_epoch"]),
            identity_signing_public_key="", static_dh_public_key="",
        )

    @classmethod
    def _record(cls, row: sqlite3.Row) -> PeerSessionRecord:
        policy = PeerTransportPolicy(
            allowed_transports=tuple(row["allowed_transports"].split(",")),
            max_bytes=int(row["max_bytes"]), max_streams=int(row["max_streams"]),
            policy_version=int(row["policy_version"]), fallback_policy=row["fallback_policy"],
        )
        return PeerSessionRecord(
            PeerSession(
                session_id=row["session_id"], protocol=PeerProtocol(row["protocol"]),
                purpose_type=row["purpose_type"], purpose_id=row["purpose_id"],
                status=row["status"], expires_at=parse_utc(row["expires_at"]),
                transport_policy=policy, self_endpoint=cls._endpoint(row, "self"),
                peer_endpoint=cls._endpoint(row, "peer"), grant=None,
            ),
            row["owner_user_id"],
        )

    def get(self, session_id: str) -> PeerSessionRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM peer_sessions WHERE session_id=?", (session_id,)).fetchone()
        return None if row is None else self._record(row)

    def mark_closed(self, session_id: str) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE peer_sessions SET status='closed',updated_at=? WHERE session_id=?",
                (utc_now_text(), session_id),
            )

    def consume_grant_jti(self, *, jti: str, session_id: str, expires_at: datetime) -> bool:
        digest = hashlib.sha256(jti.encode("ascii")).hexdigest()
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute("DELETE FROM peer_replay_tokens WHERE expires_at < ?", (now,))
            try:
                connection.execute(
                    "INSERT INTO peer_replay_tokens(jti_digest,session_id,expires_at,consumed_at) VALUES (?,?,?,?)",
                    (digest, session_id, expires_at.isoformat(), now),
                )
            except sqlite3.IntegrityError:
                return False
        return True
