"""Local, account-scoped drafts and bounded outgoing attachments."""

import base64
from datetime import UTC, datetime
import json
import re
import sqlite3
from uuid import uuid4

from ai2apps.secrets.backends import SecretBackendError

from .imap import MailError


MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENT_REQUEST = 15 * 1024 * 1024


def decode_attachments(attachments):
    if len(attachments) > MAX_ATTACHMENTS:
        raise MailError("mail_attachments_too_large")
    total = 0
    files = []
    for attachment in attachments:
        name = attachment["name"]
        if not name.strip() or re.search(r"[\x00-\x1f\x7f/\\]", name) or len(name) > 255:
            raise MailError("mail_invalid_attachment")
        try:
            content = base64.b64decode(attachment["data"], validate=True)
        except ValueError:
            raise MailError("mail_invalid_attachment") from None
        total += len(content)
        if total > MAX_ATTACHMENT_BYTES:
            raise MailError("mail_attachments_too_large")
        files.append((name, content))
    return files


class Drafts:
    def __init__(self, mail):
        self.mail = mail

    def _row(self, db, principal, draft_id):
        row = db.execute("""SELECT d.* FROM mail_drafts d JOIN mail_accounts a ON a.id=d.account_id
            WHERE d.id=? AND a.owner=? AND a.installation=? AND a.status!='removing'""",
            (draft_id, *self.mail._scope(principal))).fetchone()
        if row is None:
            raise KeyError(draft_id)
        return row

    def list(self, principal, account_id):
        with self.mail.database.transaction() as db:
            if account_id is not None:
                self.mail._account(db, principal, account_id)
            rows = db.execute("""SELECT d.id,d.account_id,d.updated_at,d.status,
                json_extract(d.data,'$.subject') AS subject,
                json_extract(d.data,'$.recipients') AS recipients,
                json_array_length(d.data,'$.attachments') AS attachment_count,a.address
                FROM mail_drafts d JOIN mail_accounts a ON a.id=d.account_id
                WHERE a.owner=? AND a.installation=? AND a.status!='removing'
                AND (? IS NULL OR a.id=?) ORDER BY d.updated_at DESC,d.id""",
                (*self.mail._scope(principal), account_id, account_id)).fetchall()
        return [{**dict(row), "recipients": json.loads(row["recipients"])} for row in rows]

    def get(self, principal, draft_id):
        with self.mail.database.transaction() as db:
            row = self._row(db, principal, draft_id)
            return self._data(row)

    @staticmethod
    def _data(row):
        return {**json.loads(row["data"]), "id": row["id"], "account_id": row["account_id"],
                "revision": row["revision"], "status": row["status"]}

    def save_agent_reply(self, principal, draft_id, origin, details, body):
        account_id = origin["account_id"]
        data = {"recipients": [details["recipient"]], "subject": details["subject"], "body": body,
                "reply": {"validity": origin["uidvalidity"], "uid": origin["uid"]},
                "attachments": [], "agent_origin": origin}
        with self.mail.database.transaction(write=True) as db:
            account = self.mail._account(db, principal, account_id)
            if account["status"] != "connected":
                raise MailError("reconnect_required")
            db.execute("""INSERT INTO mail_drafts(id,account_id,data,updated_at,revision)
                VALUES(?,?,?,?,1) ON CONFLICT(id) DO NOTHING""",
                (draft_id, account_id, json.dumps(data), datetime.now(UTC).isoformat()))
            return self._data(self._row(db, principal, draft_id))

    @staticmethod
    def _check_editable(row, revision):
        if row["status"] != "draft" or row["revision"] != revision:
            raise MailError("mail_draft_changed")

    def save(self, principal, account_id, data, draft_id=None, revision=None):
        decode_attachments(data["attachments"])
        with self.mail.database.transaction(write=True) as db:
            account = self.mail._account(db, principal, account_id)
            if account["status"] == "removing":
                raise KeyError(account_id)
            if draft_id:
                row = self._row(db, principal, draft_id)
                self._check_editable(row, revision)
                previous = json.loads(row["data"])
                if previous["reply"] != data["reply"] or (data["reply"] and row["account_id"] != account_id):
                    raise MailError("mail_draft_changed")
                if "agent_origin" in previous:
                    data = {**data, "agent_origin": previous["agent_origin"]}
            draft_id = draft_id or uuid4().hex
            revision = (revision or 0) + 1
            db.execute("""INSERT INTO mail_drafts(id,account_id,data,updated_at,revision)
                VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET account_id=excluded.account_id,
                data=excluded.data,updated_at=excluded.updated_at,revision=excluded.revision""",
                (draft_id, account_id, json.dumps(data), datetime.now(UTC).isoformat(), revision))
        return {"id": draft_id, "revision": revision}

    def delete(self, principal, draft_id, revision):
        with self.mail.database.transaction(write=True) as db:
            row = self._row(db, principal, draft_id)
            if row["revision"] != revision or row["status"] == "sending":
                raise MailError("mail_draft_changed")
            db.execute("DELETE FROM mail_drafts WHERE id=?", (draft_id,))

    def send(self, principal, draft_id, revision):
        with self.mail.database.transaction(write=True) as db:
            row = self._row(db, principal, draft_id)
            self._check_editable(row, revision)
            db.execute("UPDATE mail_drafts SET status='sending' WHERE id=?", (draft_id,))
        data = json.loads(row["data"])
        reply = data["reply"]
        try:
            result = self.mail.send(principal, row["account_id"], data["recipients"], data["subject"], data["body"],
                                    (reply["validity"], reply["uid"]) if reply else None, data["attachments"])
        except (MailError, KeyError, SecretBackendError) as error:
            status = "uncertain" if getattr(error, "code", None) == "mail_send_uncertain" else "draft"
            with self.mail.database.transaction(write=True) as db:
                db.execute("UPDATE mail_drafts SET status=? WHERE id=?", (status, draft_id))
            raise
        except Exception:
            # Preserve the in-flight state when acceptance cannot be established.
            raise MailError("mail_send_uncertain") from None
        try:
            with self.mail.database.transaction(write=True) as db:
                db.execute("DELETE FROM mail_drafts WHERE id=?", (draft_id,))
        except sqlite3.Error:
            # A confirmed send must never appear retryable because cleanup failed.
            result["draft_cleanup_failed"] = True
        return result
