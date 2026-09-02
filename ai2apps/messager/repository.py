"""Principal-isolated local conversation history for Messager."""

from __future__ import annotations

import time
import uuid
from typing import Any

from ai2apps.core import utc_now_text
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase


class MessagerIdempotencyConflictError(ValueError):
    """A logical message ID was reused for different message content."""


class MessagerRepository:
    def __init__(
        self,
        database: PlatformDatabase,
        events: EventStore | None = None,
    ) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _conversation_id() -> str:
        return f"mc_{uuid.uuid4().hex}"

    @staticmethod
    def _message_id() -> str:
        return f"mm_{uuid.uuid4().hex}"

    @staticmethod
    def _attachment_values(message: dict[str, Any]) -> tuple[Any, ...]:
        attachment = message.get("attachment")
        if not isinstance(attachment, dict):
            return (None, None, None, None, None, None)
        attachment_id = attachment.get("id")
        media_type = attachment.get("mediaType")
        content_path = attachment.get("contentPath")
        if not all(
            isinstance(value, str) and value
            for value in (attachment_id, media_type, content_path)
        ):
            return (None, None, None, None, None, None)
        return (
            attachment_id,
            media_type,
            attachment.get("byteSize"),
            attachment.get("width"),
            attachment.get("height"),
            content_path,
        )

    def _conversation(
        self,
        connection,
        *,
        owner_user_id: str,
        peer_user_id: str,
        occurred_at: str,
    ) -> str:
        row = connection.execute(
            "SELECT id FROM messager_conversations WHERE owner_user_id=? AND peer_user_id=?",
            (owner_user_id, peer_user_id),
        ).fetchone()
        if row is not None:
            connection.execute(
                "UPDATE messager_conversations SET updated_at=? WHERE id=?",
                (occurred_at, row["id"]),
            )
            return str(row["id"])
        conversation_id = self._conversation_id()
        connection.execute(
            "INSERT INTO messager_conversations(id,owner_user_id,peer_user_id,created_at,updated_at) VALUES (?,?,?,?,?)",
            (conversation_id, owner_user_id, peer_user_id, occurred_at, occurred_at),
        )
        return conversation_id

    def ingest_cloud_message(
        self,
        owner_user_id: str,
        message: dict[str, Any],
    ) -> dict[str, Any] | None:
        if message.get("kind") != "user.offline_message":
            return None
        remote_message_id = str(message.get("id") or "")
        data = message.get("data")
        peer_user_id = str(
            message.get("senderUserId")
            or (data.get("senderUserId") if isinstance(data, dict) else "")
            or ""
        )
        body = str(message.get("body") or "")
        attachment_values = self._attachment_values(message)
        if (
            not remote_message_id
            or not peer_user_id
            or (not body and attachment_values[0] is None)
            or peer_user_id == owner_user_id
        ):
            return None
        created_at = str(message.get("createdAt") or utc_now_text())
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM messager_messages WHERE owner_user_id=? AND remote_message_id=?",
                (owner_user_id, remote_message_id),
            ).fetchone()
            if existing is not None:
                return dict(existing)
            conversation_id = self._conversation(
                connection,
                owner_user_id=owner_user_id,
                peer_user_id=peer_user_id,
                occurred_at=created_at,
            )
            message_id = self._message_id()
            connection.execute(
                """
                INSERT INTO messager_messages(
                    id,conversation_id,owner_user_id,peer_user_id,direction,transport,status,
                    body,client_message_id,remote_message_id,created_at,updated_at
                    ,attachment_id,attachment_media_type,attachment_byte_size,
                    attachment_width,attachment_height,attachment_content_path
                ) VALUES (?,?,?,?,?,'cloud_offline','received',?,NULL,?,?,?, ?,?,?,?,?,?)
                """,
                (
                    message_id,
                    conversation_id,
                    owner_user_id,
                    peer_user_id,
                    "incoming",
                    body,
                    remote_message_id,
                    created_at,
                    created_at,
                    *attachment_values,
                ),
            )
            if self.events is not None:
                self.events.append_in_transaction(
                    connection,
                    event_type="messager.message.received",
                    subject_id=message_id,
                    trace_id=remote_message_id,
                    payload={
                        "owner_user_id": owner_user_id,
                        "peer_user_id": peer_user_id,
                        "transport": "cloud_offline",
                        "remote_message_id": remote_message_id,
                    },
                )
            row = connection.execute(
                "SELECT * FROM messager_messages WHERE id=?", (message_id,)
            ).fetchone()
            assert row is not None
            return dict(row)

    def record_cloud_outgoing(
        self,
        *,
        owner_user_id: str,
        peer_user_id: str,
        client_message_id: str,
        body: str,
        remote_message_id: str | None,
        attachment: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        occurred_at = created_at or utc_now_text()
        attachment_values = self._attachment_values(
            {"attachment": attachment} if attachment is not None else {}
        )
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM messager_messages WHERE owner_user_id=? AND client_message_id=?",
                (owner_user_id, client_message_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["peer_user_id"] != peer_user_id
                    or existing["body"] != body
                    or existing["attachment_id"] != attachment_values[0]
                ):
                    raise MessagerIdempotencyConflictError(
                        "clientMessageId is already bound to another logical message"
                    )
                return dict(existing)
            conversation_id = self._conversation(
                connection,
                owner_user_id=owner_user_id,
                peer_user_id=peer_user_id,
                occurred_at=occurred_at,
            )
            message_id = self._message_id()
            connection.execute(
                """
                INSERT INTO messager_messages(
                    id,conversation_id,owner_user_id,peer_user_id,direction,transport,status,
                    body,client_message_id,remote_message_id,created_at,updated_at
                    ,attachment_id,attachment_media_type,attachment_byte_size,
                    attachment_width,attachment_height,attachment_content_path
                ) VALUES (?,?,?,?,?,'cloud_offline','sent',?,?,?,?,?, ?,?,?,?,?,?)
                """,
                (
                    message_id,
                    conversation_id,
                    owner_user_id,
                    peer_user_id,
                    "outgoing",
                    body,
                    client_message_id,
                    remote_message_id,
                    occurred_at,
                    occurred_at,
                    *attachment_values,
                ),
            )
            row = connection.execute(
                "SELECT * FROM messager_messages WHERE id=?", (message_id,)
            ).fetchone()
            assert row is not None
            return dict(row)

    def accept_peer_handshake(
        self,
        *,
        assertion_jti: str,
        handshake_id: str,
        initiator_user_id: str,
        initiator_device_id: str,
        expires_at: int,
    ) -> bool:
        """Atomically consume a Cloud assertion and handshake ID once."""

        now_epoch = int(time.time())
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "DELETE FROM messager_peer_handshake_replays WHERE expires_at < ?",
                (now_epoch - 30,),
            )
            existing = connection.execute(
                "SELECT 1 FROM messager_peer_handshake_replays "
                "WHERE assertion_jti=? OR handshake_id=?",
                (assertion_jti, handshake_id),
            ).fetchone()
            if existing is not None:
                return False
            connection.execute(
                """
                INSERT INTO messager_peer_handshake_replays(
                    assertion_jti,handshake_id,initiator_user_id,
                    initiator_device_id,expires_at,accepted_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (
                    assertion_jti,
                    handshake_id,
                    initiator_user_id,
                    initiator_device_id,
                    expires_at,
                    utc_now_text(),
                ),
            )
        return True

    def record_local_incoming(
        self,
        *,
        owner_user_id: str,
        peer_user_id: str,
        remote_message_id: str,
        body: str,
        created_at: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        occurred_at = created_at or utc_now_text()
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM messager_messages WHERE owner_user_id=? "
                "AND peer_user_id=? AND remote_message_id=?",
                (owner_user_id, peer_user_id, remote_message_id),
            ).fetchone()
            if existing is not None:
                if existing["body"] != body:
                    raise MessagerIdempotencyConflictError(
                        "remote message ID is bound to different content"
                    )
                return dict(existing), False
            conversation_id = self._conversation(
                connection,
                owner_user_id=owner_user_id,
                peer_user_id=peer_user_id,
                occurred_at=occurred_at,
            )
            message_id = self._message_id()
            connection.execute(
                """
                INSERT INTO messager_messages(
                    id,conversation_id,owner_user_id,peer_user_id,direction,
                    transport,status,body,client_message_id,remote_message_id,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,'local_e2ee','received',?,NULL,?,?,?)
                """,
                (
                    message_id,
                    conversation_id,
                    owner_user_id,
                    peer_user_id,
                    "incoming",
                    body,
                    remote_message_id,
                    occurred_at,
                    occurred_at,
                ),
            )
            if self.events is not None:
                self.events.append_in_transaction(
                    connection,
                    event_type="messager.message.received",
                    subject_id=message_id,
                    trace_id=remote_message_id,
                    payload={
                        "owner_user_id": owner_user_id,
                        "peer_user_id": peer_user_id,
                        "transport": "local_e2ee",
                        "remote_message_id": remote_message_id,
                    },
                )
            row = connection.execute(
                "SELECT * FROM messager_messages WHERE id=?", (message_id,)
            ).fetchone()
            assert row is not None
            return dict(row), True

    def record_local_outgoing(
        self,
        *,
        owner_user_id: str,
        peer_user_id: str,
        client_message_id: str,
        body: str,
        status: str = "sent",
        created_at: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"sent", "result_unknown", "failed"}:
            raise ValueError("local outgoing status is invalid")
        occurred_at = created_at or utc_now_text()
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM messager_messages WHERE owner_user_id=? AND client_message_id=?",
                (owner_user_id, client_message_id),
            ).fetchone()
            if existing is not None:
                if existing["peer_user_id"] != peer_user_id or existing["body"] != body:
                    raise MessagerIdempotencyConflictError(
                        "clientMessageId is already bound to another logical message"
                    )
                if status == "sent" and existing["status"] == "result_unknown":
                    connection.execute(
                        "UPDATE messager_messages SET status='sent',updated_at=? WHERE id=?",
                        (occurred_at, existing["id"]),
                    )
                    existing = connection.execute(
                        "SELECT * FROM messager_messages WHERE id=?", (existing["id"],)
                    ).fetchone()
                    assert existing is not None
                return dict(existing)
            conversation_id = self._conversation(
                connection,
                owner_user_id=owner_user_id,
                peer_user_id=peer_user_id,
                occurred_at=occurred_at,
            )
            message_id = self._message_id()
            connection.execute(
                """
                INSERT INTO messager_messages(
                    id,conversation_id,owner_user_id,peer_user_id,direction,
                    transport,status,body,client_message_id,remote_message_id,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,'local_e2ee',?,?,?,NULL,?,?)
                """,
                (
                    message_id,
                    conversation_id,
                    owner_user_id,
                    peer_user_id,
                    "outgoing",
                    status,
                    body,
                    client_message_id,
                    occurred_at,
                    occurred_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM messager_messages WHERE id=?", (message_id,)
            ).fetchone()
            assert row is not None
            return dict(row)

    def validate_cloud_outgoing(
        self,
        *,
        owner_user_id: str,
        peer_user_id: str,
        client_message_id: str,
        body: str,
        attachment_id: str | None = None,
    ) -> None:
        """Reject conflicting retries before a request can reach Cloud."""

        with self.database.transaction() as connection:
            existing = connection.execute(
                "SELECT peer_user_id,body,attachment_id FROM messager_messages "
                "WHERE owner_user_id=? AND client_message_id=?",
                (owner_user_id, client_message_id),
            ).fetchone()
        if existing is not None and (
            existing["peer_user_id"] != peer_user_id
            or existing["body"] != body
            or existing["attachment_id"] != attachment_id
        ):
            raise MessagerIdempotencyConflictError(
                "clientMessageId is already bound to another logical message"
            )

    def list_messages(
        self,
        owner_user_id: str,
        peer_user_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM messager_messages
                WHERE owner_user_id=? AND peer_user_id=?
                ORDER BY created_at, id LIMIT ?
                """,
                (owner_user_id, peer_user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_conversations(
        self,
        owner_user_id: str,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.*,
                    (SELECT body FROM messager_messages m WHERE m.conversation_id=c.id ORDER BY m.created_at DESC,m.id DESC LIMIT 1) AS last_body,
                    (SELECT status FROM messager_messages m WHERE m.conversation_id=c.id ORDER BY m.created_at DESC,m.id DESC LIMIT 1) AS last_status
                FROM messager_conversations c
                WHERE c.owner_user_id=? ORDER BY c.updated_at DESC LIMIT ?
                """,
                (owner_user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
