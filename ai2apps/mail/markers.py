"""Local Mail markers and the owner-scoped link to Todo."""

from datetime import UTC, datetime
import json

from .imap import MailError


BUILTIN_VIEWS = ("top5", "flagged", "todo", "answered")
TOP_LIMIT = 5


class MessageMarkers:
    def __init__(self, mail, todo_store):
        self.mail = mail
        self.todo_store = todo_store

    def records(self, db, principal, account_id=None):
        return db.execute("""SELECT m.account_id,m.uidvalidity,m.uid,m.subject,m.sender,m.received_at,
            m.seen,m.answered,m.pinned_at,m.flagged,m.todo_id,m.preview!='{}' AS has_preview,a.address,a.display_name,
            r.uid IS NOT NULL AS read_here FROM mail_message_markers m JOIN mail_accounts a ON a.id=m.account_id
            LEFT JOIN mail_local_reads r ON r.account_id=m.account_id AND r.uidvalidity=m.uidvalidity AND r.uid=m.uid
            WHERE a.owner=? AND a.installation=? AND a.status!='removing'
            AND (? IS NULL OR a.id=?)""", (*self.mail._scope(principal), account_id, account_id)).fetchall()

    @staticmethod
    def key(row):
        return row["account_id"], row["uidvalidity"], row["uid"]

    def open_todos(self, principal, records):
        ids = {row["todo_id"] for row in records if row["todo_id"] and
               ("has_preview" not in row.keys() or row["has_preview"])}
        store = self.todo_store()
        return store.open_task_ids(principal.actor_user_id, ids) if store else ids

    def todo_state(self, principal):
        with self.mail.database.transaction() as db:
            records = self.records(db, principal)
        return sorted(self.open_todos(principal, records))

    def list_fields(self, marker, active, answered):
        return {
            "pinned": bool(marker and marker["pinned_at"]),
            "flagged": bool(marker and marker["flagged"]),
            "todo": bool(marker and marker["todo_id"] in active),
            "answered": bool(answered),
        }

    def lookup(self, db, account, validity, uid):
        if account["status"] == "removing":
            raise KeyError(uid)
        key = (account["id"], validity, uid)
        marker = db.execute("""SELECT * FROM mail_message_markers
            WHERE account_id=? AND uidvalidity=? AND uid=?""", key).fetchone()
        recent = None
        if account["uidvalidity"] == validity:
            recent = db.execute("SELECT * FROM mail_messages WHERE account_id=? AND uid=?",
                                (account["id"], uid)).fetchone()
        return recent, marker

    def retained(self, principal, marker):
        return marker and marker["preview"] != "{}" and (
            marker["flagged"] or marker["pinned_at"] or marker["todo_id"] in self.open_todos(principal, [marker]))

    def set(self, principal, account_id, validity, uid, kind, enabled, language):
        with self.mail.database.transaction() as db:
            account = self.mail._account(db, principal, account_id)
            recent, marker = self.lookup(db, account, validity, uid)
            if recent is None and not self.retained(principal, marker):
                if marker and not enabled:
                    return
                raise KeyError(uid)
            snapshot_needed = enabled and (marker is None or marker["preview"] == "{}")
        body = self.mail.preview(principal, account_id, validity, uid) if snapshot_needed else None
        owner = principal.actor_user_id
        key = (account_id, validity, uid)
        with self.mail.database.transaction(write=True) as db:
            account = self.mail._account(db, principal, account_id)
            recent, marker = self.lookup(db, account, validity, uid)
            if recent is None and not self.retained(principal, marker):
                if marker and not enabled:
                    return
                raise KeyError(uid)
            if kind == "pin" and enabled and not (marker and marker["pinned_at"]):
                if sum(bool(row["pinned_at"]) for row in self.records(db, principal)) >= TOP_LIMIT:
                    raise MailError("mail_pin_limit")
                db.execute("DELETE FROM mail_priority_dismissals WHERE account_id=? AND uidvalidity=? AND uid=?", key)
            if enabled and (marker is None or marker["preview"] == "{}"):
                if body is None:
                    raise MailError("account_changed")
                preview = {field: body[field] for field in ("text", "html", "html_links", "preview_status", "remote_images")
                           if field in body}
                preview.setdefault("preview_status", "complete")
                item = recent or marker
                read_here = db.execute("""SELECT 1 FROM mail_local_reads
                    WHERE account_id=? AND uidvalidity=? AND uid=?""", key).fetchone()
                db.execute("""INSERT INTO mail_message_markers
                    (account_id,uidvalidity,uid,subject,sender,received_at,seen,answered,preview)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(account_id,uidvalidity,uid) DO UPDATE SET
                    preview=excluded.preview,seen=excluded.seen,answered=excluded.answered""",
                    (*key, item["subject"], item["sender"], item["received_at"], int(bool(item["seen"] or read_here)),
                     item["answered"], json.dumps(preview, ensure_ascii=False)))
                recent, marker = self.lookup(db, account, validity, uid)
            if marker is None:
                return
            if kind == "pin":
                pin = (marker["pinned_at"] or datetime.now(UTC).isoformat()) if enabled else None
                db.execute("UPDATE mail_message_markers SET pinned_at=? WHERE account_id=? AND uidvalidity=? AND uid=?",
                           (pin, *key))
            elif kind == "flag":
                db.execute("UPDATE mail_message_markers SET flagged=? WHERE account_id=? AND uidvalidity=? AND uid=?",
                           (int(enabled), *key))
            else:
                self._set_todo(db, owner, key, marker, enabled, language)
            self.prune(db, principal, account_id)

    def _set_todo(self, db, owner, key, marker, enabled, language):
        store = self.todo_store()
        if store is None:
            raise MailError("mail_todo_unavailable")
        task_id = marker["todo_id"]
        active = store.open_task_ids(owner, [task_id]) if task_id else set()
        if enabled and not active:
            directory = store.linked_directory(owner, "mail", "邮件" if language == "zh" else "Mail",
                                               ("邮件", "Mail", "邮件 / Mail"))
            request_key = "mail:" + ":".join(map(str, (*key, task_id or "first")))
            task = store.linked_task(owner, request_key, {
                "title": marker["subject"].strip() or ("无主题" if language == "zh" else "No subject"),
                "description": marker["sender"] + "\n" + marker["received_at"],
                "directory_id": directory,
            })
            db.execute("UPDATE mail_message_markers SET todo_id=? WHERE account_id=? AND uidvalidity=? AND uid=?",
                       (task["id"], *key))
        if not enabled and active:
            try:
                task = store.get(owner, task_id)
                if not task["completed"]:
                    store.complete_linked_task(owner, task)
            except ValueError as error:
                raise MailError("account_changed") from error

    def prune(self, db, principal, account_id):
        records = self.records(db, principal, account_id)
        active = self.open_todos(principal, records)
        db.executemany("""UPDATE mail_message_markers SET preview='{}'
            WHERE account_id=? AND uidvalidity=? AND uid=? AND preview!='{}'""",
            (self.key(row) for row in records
             if not (row["pinned_at"] or row["flagged"] or row["todo_id"] in active)))
        db.execute("""DELETE FROM mail_message_markers WHERE account_id=? AND preview='{}'
            AND todo_id IS NULL""", (account_id,))
