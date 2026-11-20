"""Account-scoped Mail service shared by all local Mail surfaces."""

from datetime import UTC, datetime
from contextlib import contextmanager
from email import policy
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
import json
import logging
import re
import smtplib
import sqlite3
import ssl
from threading import BoundedSemaphore
from uuid import uuid4

from . import imap
from .drafts import Drafts, decode_attachments
from .gmail_oauth import GmailOAuth
from .markers import MessageMarkers
from .smart_folders import SmartFolders

PRESETS = {
    "icloud": ("imap.mail.me.com", "smtp.mail.me.com", 587),
    "gmail": ("imap.gmail.com", "smtp.gmail.com", 587),
}
logger = logging.getLogger(__name__)


def _host(value):
    # Host only. The owner explicitly configures this endpoint; never accept a URL.
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", value):
        raise imap.MailError("invalid_host")
    return value.lower()


def _address(value):
    address = value.strip()
    if not re.fullmatch(r"[!-~]+", address) or not re.fullmatch(r"[^@<>]+@[^@<>]+", address):
        raise imap.MailError("invalid_address")
    return address


def _settings(payload):
    address = _address(payload["address"])
    provider = payload["provider"]
    if provider in PRESETS:
        host, smtp_host, smtp_port = PRESETS[provider]
        port = 993
        username = (payload["username"] or address.split("@")[0]) if provider == "icloud" else address
        smtp_username = address
        smtp_tls = "starttls"
    else:
        host, port = _host(payload["host"]), payload["port"]
        smtp_host, smtp_port = (_host(payload["smtp_host"]) if payload["smtp_host"] else ""), payload["smtp_port"]
        username, smtp_username = payload["username"] or address, payload["smtp_username"] or address
        smtp_tls = payload["smtp_tls"]
    return {
        "provider": provider, "address": address, "display_name": payload["display_name"].strip() or address,
        "host": host, "port": port, "username": username,
        "smtp_host": smtp_host, "smtp_port": smtp_port, "smtp_username": smtp_username, "smtp_tls": smtp_tls,
    }


def account_settings(payload):
    settings = _settings(payload)
    password = payload["password"]
    if settings["provider"] == "gmail":
        password = password.replace(" ", "")
        if not re.fullmatch(r"[A-Za-z0-9]{16}", password):
            raise imap.MailError("gmail_app_password_required")
    if not all(v and all(32 <= ord(c) < 127 for c in v)
               for v in (settings["username"], settings["smtp_username"], password)):
        raise imap.MailError("invalid_credentials_format")
    return settings, password


@contextmanager
def smtp_session(account, password):
    client = None
    try:
        context = ssl.create_default_context()
        host, port = account["smtp_host"], account["smtp_port"]
        if account["smtp_tls"] == "implicit":
            client = smtplib.SMTP_SSL(host, port, timeout=8, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=8)
            client.starttls(context=context)
        if account.get("auth_mode") == "xoauth2":
            client.ehlo()
            payload = imap.xoauth2_payload(account["smtp_username"], password)
            client.auth("XOAUTH2", lambda challenge=None: payload if challenge is None else "")
        else:
            client.login(account["smtp_username"], password)
        yield client
    finally:
        if client is not None:
            try:
                client.close()
            except OSError:
                pass


def probe_smtp(account, password):
    if not account["smtp_host"]:
        return "not_configured"
    try:
        with smtp_session(account, password):
            return "authenticated"
    except smtplib.SMTPAuthenticationError:
        return "authentication_failed"
    except (OSError, smtplib.SMTPException):
        return "connection_failed"


def recipient_address(value):
    value = value.strip()
    try:
        if not re.fullmatch(r"[!-~]{3,254}", value):
            raise ValueError
        address = Address(addr_spec=value)
        if not (address.username and address.domain) or address.addr_spec != value:
            raise ValueError
    except (ValueError, IndexError, HeaderParseError) as error:
        raise imap.MailError("mail_invalid_recipient") from error
    return address


def deliver_smtp(account, password, message, recipients):
    try:
        with smtp_session(account, password) as client:
            if client.mail(account["address"])[0] != 250:
                raise imap.MailError("mail_send_rejected")
            for address in recipients:
                if client.rcpt(address.addr_spec)[0] not in (250, 251, 252):
                    raise imap.MailError("mail_recipient_rejected")
            try:
                code, _ = client.data(message.as_bytes(policy=policy.SMTP))
            except smtplib.SMTPDataError:
                raise imap.MailError("mail_send_rejected") from None
            except OSError:
                raise imap.MailError("mail_send_uncertain") from None
            if code != 250:
                raise imap.MailError("mail_send_rejected")
    except smtplib.SMTPAuthenticationError:
        raise imap.MailError("mail_smtp_auth_failed") from None
    except OSError:
        raise imap.MailError("mail_send_connection") from None


def reply_details(headers):
    field = "Reply-To" if "Reply-To" in headers else "From"
    values = headers.get_all(field, [])
    addresses = values[0].addresses if len(values) == 1 and not values[0].defects else ()
    if len(addresses) != 1:
        raise imap.MailError("mail_reply_unavailable")
    try:
        target = recipient_address(addresses[0].addr_spec).addr_spec
    except imap.MailError:
        raise imap.MailError("mail_reply_unavailable") from None
    subject = " ".join(str(headers.get("Subject", "")).split())
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject
    pattern = r"<[!-;=?-~]+@[!-;=?-~]+>"
    message_id = str(headers.get("Message-ID", "")).strip()
    if len(message_id) > 254 or not re.fullmatch(pattern, message_id):
        message_id = ""
    references = [value for value in re.findall(pattern, str(headers.get("References", "")))
                  if len(value) <= 254 and value != message_id][-10:]
    return target, subject[:500], message_id, references


def is_mobile_mail_owner(principal):
    return (principal.client_scope == "owner-home"
            and principal.authentication_type == "owner_home_lease"
            and principal.is_core)


class MailService:
    def __init__(self, database, secrets, todo_store=lambda: None):
        self.database = database
        self.secrets = secrets
        self.gmail = GmailOAuth(database.path.parent / "gmail-oauth-client.json")
        self._slots = BoundedSemaphore(4)
        self.smart = SmartFolders(self)
        self.markers = MessageMarkers(self, todo_store)
        self.drafts = Drafts(self)
        logger.info("Built-in Mail service loaded from %s; IMAP preview loaded from %s", __file__, imap.__file__)

    @staticmethod
    def _scope(principal):
        if principal.client_scope != "desktop" and not is_mobile_mail_owner(principal):
            raise PermissionError
        return principal.actor_user_id, principal.installation_id

    def _account(self, db, principal, account_id):
        row = db.execute("SELECT * FROM mail_accounts WHERE owner=? AND installation=? AND id=?",
                         (*self._scope(principal), account_id)).fetchone()
        if row is None:
            raise KeyError(account_id)
        return dict(row)

    @staticmethod
    def _public(row):
        return {k: v for k, v in dict(row).items() if k not in ("owner", "installation", "secret_key")}

    def accounts(self, principal):
        with self.database.transaction() as db:
            rows = db.execute("SELECT * FROM mail_accounts WHERE owner=? AND installation=? ORDER BY display_name,id",
                              self._scope(principal)).fetchall()
        return [self._public(row) for row in rows]

    def _network(self, function, *args):
        if not self._slots.acquire(blocking=False):
            raise imap.MailError("mail_busy")
        try:
            return function(*args)
        finally:
            self._slots.release()

    def _check(self, account, password):
        imap.verify(account, password)
        return probe_smtp(account, password)

    def connect(self, principal, payload):
        self._scope(principal)
        settings, password = account_settings(payload)
        smtp_status = self._network(self._check, settings, password)
        return self._save(principal, settings, password, smtp_status)

    def start_gmail(self, principal, account_id):
        scope = self._scope(principal)
        credential_key = ""
        if account_id:
            with self.database.transaction() as db:
                account = self._account(db, principal, account_id)
            if account["provider"] != "gmail" or account["status"] == "removing":
                raise imap.MailError("account_changed")
            credential_key = account["secret_key"]
        return self.gmail.start(scope, account_id, credential_key)

    def cancel_gmail(self, principal, flow_id):
        self.gmail.cancel(self._scope(principal), flow_id)

    def finish_gmail(self, principal, flow_id):
        scope = self._scope(principal)
        return self._network(self._finish_gmail, principal, scope, flow_id)

    def _finish_gmail(self, principal, scope, flow_id):
        flow = self.gmail.claim(scope, flow_id)
        if flow is None:
            return {"status": "pending"}
        address, refresh_token, access_token = self.gmail.exchange(flow)
        address = _address(address)
        account = None
        if flow.account_id:
            with self.database.transaction() as db:
                account = self._account(db, principal, flow.account_id)
            if account["status"] == "removing" or account["secret_key"] != flow.credential_key:
                raise imap.MailError("account_changed")
            if account["address"].lower() != address.lower():
                raise imap.MailError("gmail_oauth_account_mismatch")
        settings = _settings({"provider": "gmail", "address": address,
                              "display_name": "", "username": ""})
        smtp_status = self._check({**settings, "auth_mode": "xoauth2"}, access_token)
        if account:
            result = self._replace(principal, account, refresh_token, smtp_status, "xoauth2")
        else:
            result = self._save(principal, settings, refresh_token, smtp_status, "xoauth2")
        return {"status": "connected", "account": result}

    def _save(self, principal, settings, credential, smtp_status, mode="password"):
        scope = self._scope(principal)
        account_id = uuid4().hex
        key = "mail-account-" + account_id
        self.secrets.store(key, credential)
        try:
            with self.database.transaction(write=True) as db:
                if mode == "xoauth2" and db.execute(
                    """SELECT 1 FROM mail_accounts WHERE owner=? AND installation=? AND provider='gmail'
                       AND lower(address)=lower(?)""", (*scope, settings["address"]),
                ).fetchone():
                    raise imap.MailError("gmail_oauth_account_exists")
                db.execute("""INSERT INTO mail_accounts
                    (id,owner,installation,provider,address,display_name,host,port,username,
                     smtp_host,smtp_port,smtp_username,smtp_tls,smtp_status,secret_key,auth_mode)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (account_id, *scope, *settings.values(), smtp_status, key, mode))
                return self._public(self._account(db, principal, account_id))
        except BaseException:
            self.secrets.delete(key)
            raise

    def _credential(self, account):
        if account["status"] != "connected":
            raise imap.MailError("reconnect_required")
        try:
            credential = self.secrets.load(account["secret_key"])
        except KeyError:
            raise imap.MailError("authentication_failed") from None
        return self.gmail.refresh(credential) if account["auth_mode"] == "xoauth2" else credential

    def _with_credential(self, function, account, *args):
        try:
            return function(account, self._credential(account), *args)
        except imap.MailError as error:
            if error.code == "authentication_failed" and account["auth_mode"] == "xoauth2":
                raise imap.MailError("gmail_oauth_required") from None
            raise

    def _mark_auth_failure(self, principal, account):
        with self.database.transaction(write=True) as db:
            db.execute("""UPDATE mail_accounts SET status='reconnect_required',revision=revision+1
                          WHERE owner=? AND installation=? AND id=? AND revision=?""",
                       (*self._scope(principal), account["id"], account["revision"]))

    def reconnect(self, principal, account_id, password):
        with self.database.transaction() as db:
            account = self._account(db, principal, account_id)
        if account["status"] == "removing":
            raise imap.MailError("account_changed")
        if account["auth_mode"] == "xoauth2":
            raise imap.MailError("gmail_oauth_required")
        settings, password = account_settings({**account, "password": password})
        smtp_status = self._network(self._check, settings, password)
        return self._replace(principal, account, password, smtp_status, "password")

    def _replace(self, principal, account, credential, smtp_status, mode):
        account_id = account["id"]
        new_key = "mail-account-" + uuid4().hex
        self.secrets.store(new_key, credential)
        try:
            with self.database.transaction(write=True) as db:
                result = db.execute("""UPDATE mail_accounts SET secret_key=?,status='connected',
                    smtp_status=?,auth_mode=?,revision=revision+1
                    WHERE owner=? AND installation=? AND id=? AND revision=?""",
                    (new_key, smtp_status, mode, *self._scope(principal), account_id, account["revision"]))
                if result.rowcount != 1:
                    raise imap.MailError("account_changed")
                public = self._public(self._account(db, principal, account_id))
        except BaseException:
            self.secrets.delete(new_key)
            raise
        self.secrets.delete(account["secret_key"])
        return public

    def disconnect(self, principal, account_id):
        with self.database.transaction(write=True) as db:
            row = self._account(db, principal, account_id)
            db.execute("UPDATE mail_accounts SET status='removing',revision=revision+1 WHERE id=?", (account_id,))
        self.secrets.delete(row["secret_key"])
        with self.database.transaction(write=True) as db:
            db.execute("DELETE FROM mail_accounts WHERE id=? AND status='removing'", (account_id,))

    def sync(self, principal, account_id):
        with self.database.transaction() as db:
            account = self._account(db, principal, account_id)
        try:
            validity, rows, capped = self._network(self._with_credential, imap.snapshot, account)
        except imap.MailError as error:
            if error.code in ("authentication_failed", "gmail_oauth_required"):
                self._mark_auth_failure(principal, account)
            raise
        now = datetime.now(UTC).isoformat()
        with self.database.transaction(write=True) as db:
            result = db.execute("""UPDATE mail_accounts SET synced_at=?,uidvalidity=?,capped=?,revision=revision+1
                WHERE owner=? AND installation=? AND id=? AND revision=? AND status='connected'""",
                (now, validity, int(capped), *self._scope(principal), account_id, account["revision"]))
            if result.rowcount != 1:
                raise imap.MailError("account_changed")
            db.execute("DELETE FROM mail_messages WHERE account_id=?", (account_id,))
            db.executemany("INSERT INTO mail_messages VALUES (?,?,?,?,?,?,?)", ((account_id, *r) for r in rows))
            db.execute("""UPDATE mail_messages SET answered=1 WHERE account_id=? AND uid IN
                (SELECT uid FROM mail_local_replies WHERE account_id=? AND uidvalidity=?)""",
                (account_id, account_id, validity))
            db.execute("""UPDATE mail_message_markers AS m SET
                answered=(SELECT recent.answered FROM mail_messages recent WHERE recent.account_id=m.account_id AND recent.uid=m.uid),
                seen=max(m.seen,(SELECT recent.seen FROM mail_messages recent WHERE recent.account_id=m.account_id AND recent.uid=m.uid))
                WHERE m.account_id=? AND m.uidvalidity=?
                AND EXISTS(SELECT 1 FROM mail_messages recent WHERE recent.account_id=m.account_id AND recent.uid=m.uid)""",
                (account_id, validity))
            db.execute("""DELETE FROM mail_analysis WHERE account_id=?
                AND (uidvalidity!=? OR uid NOT IN (SELECT uid FROM mail_messages WHERE account_id=?))""",
                (account_id, validity, account_id))
            self.markers.prune(db, principal, account_id)
            db.execute("DELETE FROM mail_classification_overrides WHERE account_id=? AND uidvalidity!=?",
                       (account_id, validity))
            db.execute("DELETE FROM mail_priority_dismissals WHERE account_id=? AND uidvalidity!=?",
                       (account_id, validity))
            db.execute("""DELETE FROM mail_local_reads WHERE account_id=?
                AND (uidvalidity!=? OR uid NOT IN (SELECT uid FROM mail_messages WHERE account_id=?))""",
                (account_id, validity, account_id))
            db.execute("""DELETE FROM mail_local_replies AS r WHERE account_id=?
                AND NOT EXISTS(SELECT 1 FROM mail_messages m WHERE m.account_id=r.account_id AND m.uid=r.uid AND r.uidvalidity=?)
                AND NOT EXISTS(SELECT 1 FROM mail_message_markers m WHERE m.account_id=r.account_id
                    AND m.uid=r.uid AND m.uidvalidity=r.uidvalidity AND m.preview!='{}')""", (account_id, validity))
        return {"synced_at": now, "count": len(rows), "capped": capped, "window_days": imap.WINDOW_DAYS}

    def messages(self, principal, account_id, limit, offset, query=""):
        scope = self._scope(principal)
        with self.database.transaction() as db:
            if account_id is not None:
                self._account(db, principal, account_id)
            rows = db.execute("""SELECT m.*,a.address,a.display_name,a.uidvalidity,r.uid IS NOT NULL AS read_here
                FROM mail_messages m JOIN mail_accounts a ON a.id=m.account_id
                LEFT JOIN mail_local_reads r ON r.account_id=m.account_id AND r.uidvalidity=a.uidvalidity AND r.uid=m.uid
                WHERE a.owner=? AND a.installation=? AND a.status!='removing'
                AND (? IS NULL OR a.id=?) AND (?='' OR instr(lower(m.subject),lower(?))>0 OR instr(lower(m.sender),lower(?))>0)
                ORDER BY received_at DESC,m.account_id,m.uid DESC LIMIT ? OFFSET ?""",
                (*scope, account_id, account_id, query, query, query, limit + 1, offset)).fetchall()
            records = self.markers.records(db, principal, account_id)
        markers = {self.markers.key(row): row for row in records}
        active = self.markers.open_todos(principal, records)
        items = [self._list_item(row, markers.get(self.markers.key(row)), active) for row in rows[:limit]]
        return {"items": items, "has_more": len(rows) > limit,
                "window_days": imap.WINDOW_DAYS}

    def _list_item(self, row, marker=None, active=()):
        item = dict(row)
        read_here = item.pop("read_here")
        item["seen"] = int(bool(item["seen"] or read_here or (marker and marker["seen"])))
        item.update(self.markers.list_fields(marker, active, item["answered"]))
        item.pop("pinned_at", None)
        item.pop("todo_id", None)
        return item

    def mark_read(self, principal, account_id, validity, uid):
        with self.database.transaction(write=True) as db:
            account = self._account(db, principal, account_id)
            recent, marker = self.markers.lookup(db, account, validity, uid)
            if recent is None and not self.markers.retained(principal, marker):
                raise KeyError(uid)
            db.execute("INSERT OR IGNORE INTO mail_local_reads VALUES (?,?,?)", (account_id, validity, uid))
            db.execute("UPDATE mail_message_markers SET seen=1 WHERE account_id=? AND uidvalidity=? AND uid=?",
                       (account_id, validity, uid))

    def preview(self, principal, account_id, validity, uid, load_images=False):
        legacy_preview = None
        with self.database.transaction() as db:
            account = self._account(db, principal, account_id)
            item, marker = self.markers.lookup(db, account, validity, uid)
            if item is None and not self.markers.retained(principal, marker):
                raise KeyError(uid)
            auto_load_images = item is not None and db.execute("""SELECT 1 FROM mail_image_permissions
                WHERE account_id=? AND uidvalidity=? AND uid=?""", (account_id, validity, uid)).fetchone() is not None
            if marker and marker["preview"] != "{}" and (not load_images or item is None):
                cached = json.loads(marker["preview"])
                if item is None:
                    cached.pop("remote_images", None)
                source = item or marker
                result = {**{k: source[k] for k in ("uid", "subject", "sender", "received_at", "seen")},
                          **cached, "auto_load_images": auto_load_images}
                if item is None or not cached.get("html") or cached.get("html_links"):
                    return result
                legacy_preview = result
        try:
            reader = imap.read_preview
            if load_images:
                from functools import partial
                reader = partial(reader, load_images=True)
            body = self._network(self._with_credential, reader, account, validity, uid)
        except imap.MailError as error:
            if error.code in ("authentication_failed", "gmail_oauth_required"):
                self._mark_auth_failure(principal, account)
            if legacy_preview is not None:
                return legacy_preview
            raise
        remember = bool(load_images and body.get("html") and body.get("loaded_images"))
        upgrade = legacy_preview is not None and body.get("html_links")
        if legacy_preview is not None and not upgrade:
            return legacy_preview
        with self.database.transaction(write=bool(remember or upgrade)) as db:
            if self._account(db, principal, account_id)["revision"] != account["revision"]:
                raise imap.MailError("account_changed")
            if remember:
                db.execute("INSERT OR IGNORE INTO mail_image_permissions VALUES (?,?,?)",
                           (account_id, validity, uid))
            if upgrade:
                db.execute("""UPDATE mail_message_markers SET preview=?
                    WHERE account_id=? AND uidvalidity=? AND uid=? AND preview=?""",
                           (json.dumps(body, ensure_ascii=False), account_id, validity, uid, marker["preview"]))
        return {**dict(item), **body, "auto_load_images": auto_load_images or remember}

    def set_marker(self, principal, account_id, validity, uid, kind, enabled, language):
        return self.markers.set(principal, account_id, validity, uid, kind, enabled, language)

    def todo_state(self, principal):
        return self.markers.todo_state(principal)

    @staticmethod
    def _check_send_account(account):
        if account["status"] != "connected":
            raise imap.MailError("reconnect_required")
        if not account["smtp_host"]:
            raise imap.MailError("mail_smtp_unconfigured")

    def _reply(self, principal, account_id, validity, uid, *, require_smtp=True):
        with self.database.transaction() as db:
            account = self._account(db, principal, account_id)
            if require_smtp:
                self._check_send_account(account)
            elif account["status"] != "connected":
                raise imap.MailError("reconnect_required")
            item, marker = self.markers.lookup(db, account, validity, uid)
            if item is None and not self.markers.retained(principal, marker):
                raise KeyError(uid)
        headers = self._network(self._with_credential, imap.reply_headers, account, validity, uid)
        return account, reply_details(headers)

    def reply_info(self, principal, account_id, validity, uid, *, require_smtp=True):
        _, (target, subject, _, _) = self._reply(principal, account_id, validity, uid, require_smtp=require_smtp)
        return {"recipient": target, "subject": subject}

    def send(self, principal, account_id, recipients, subject, body, reply=None, attachments=()):
        addresses = [recipient_address(value) for value in dict.fromkeys(value.strip() for value in recipients)]
        files = decode_attachments(attachments)
        if not addresses or not (body.strip() or files) or re.search(r"[\x00-\x1f\x7f]", subject):
            raise imap.MailError("mail_invalid_draft")
        if reply:
            account, (target, _, message_id, references) = self._reply(principal, account_id, *reply)
            if len(addresses) != 1 or addresses[0].addr_spec != target:
                raise imap.MailError("mail_reply_target_changed")
        else:
            with self.database.transaction() as db:
                account = self._account(db, principal, account_id)
                self._check_send_account(account)
        message = EmailMessage(policy=policy.SMTP)
        message["From"] = recipient_address(account["address"])
        message["To"] = ", ".join(address.addr_spec for address in addresses)
        message["Subject"] = subject
        message["Date"] = format_datetime(datetime.now(UTC))
        message["Message-ID"] = make_msgid(domain=message["From"].addresses[0].domain)
        message.set_content(body, cte="quoted-printable")
        if reply and message_id:
            message["In-Reply-To"] = message_id
            message["References"] = " ".join([*references, message_id])
        for name, content in files:
            message.add_attachment(content, maintype="application", subtype="octet-stream", filename=name)
        with self.database.transaction() as db:
            if self._account(db, principal, account_id)["revision"] != account["revision"]:
                raise imap.MailError("account_changed")
        self._network(self._with_credential, deliver_smtp, account, message, addresses)
        reply_marked = False
        if reply:
            try:
                reply_marked = self._record_reply(principal, account_id, *reply)
            except sqlite3.Error:
                logger.warning("Could not record local replied status after SMTP acceptance")
        return {"sent": True, "reply_marked": reply_marked}

    def _record_reply(self, principal, account_id, validity, uid):
        with self.database.transaction(write=True) as db:
            try:
                account = self._account(db, principal, account_id)
                item, marker = self.markers.lookup(db, account, validity, uid)
            except KeyError:
                return False
            if item is None and marker is None:
                return False
            db.execute("INSERT OR IGNORE INTO mail_local_replies VALUES (?,?,?)", (account_id, validity, uid))
            if item is not None:
                db.execute("UPDATE mail_messages SET answered=1 WHERE account_id=? AND uid=?", (account_id, uid))
            db.execute("UPDATE mail_message_markers SET answered=1 WHERE account_id=? AND uidvalidity=? AND uid=?",
                       (account_id, validity, uid))
            return True
