"""Bounded, read-only inbox access over certificate-verified IMAP TLS."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import imaplib
import re
import ssl

from .html_preview import formatted_html
from .remote_images import RemoteImages

MAX_INBOX = 200
MAX_BODY = 192 * 1024
WINDOW_DAYS = 30
MAX_PREVIEW_TEXT = 16000


class _HTMLPreview(HTMLParser):
    """Extract text nodes only; attributes and URLs never become markup."""

    _SKIP = frozenset({"head", "script", "style", "template", "noscript", "iframe", "svg", "object"})
    _BREAK = frozenset({
        "address", "article", "blockquote", "br", "div", "h1", "h2", "h3", "h4",
        "h5", "h6", "hr", "li", "p", "pre", "section", "table", "tr",
    })

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skipped = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self.skipped.append(tag)
        elif not self.skipped:
            self._boundary(tag)

    def handle_endtag(self, tag):
        if self.skipped:
            if tag == self.skipped[-1]:
                self.skipped.pop()
        else:
            self._boundary(tag)

    def handle_startendtag(self, tag, attrs):
        if not self.skipped:
            self._boundary(tag)

    def handle_data(self, data):
        if not self.skipped:
            self.parts.append(re.sub(r"\s+", " ", data))

    def _boundary(self, tag):
        if tag in self._BREAK:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" ")

    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines()
                         if line.strip())


def _preview_text(message):
    for subtype in ("plain", "html"):
        part = message.get_body(preferencelist=(subtype,))
        if part is None:
            continue
        try:
            body = part.get_content(errors="replace")
            if subtype == "html":
                parser = _HTMLPreview()
                parser.feed(body)
                parser.close()
                body = parser.text()
        except (LookupError, ValueError):
            continue
        if body.strip():
            return {
                "text": body[:MAX_PREVIEW_TEXT],
                "preview_status": "truncated" if len(body) > MAX_PREVIEW_TEXT else "complete",
            }
    return {"text": "", "preview_status": "no_plain_text"}


class MailError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class BoundedIMAP(imaplib.IMAP4_SSL):
    def read(self, size):
        if size > MAX_BODY:
            raise self.abort("Oversized IMAP response")
        return super().read(size)


def xoauth2_payload(username, access_token):
    return f"user={username}\x01auth=Bearer {access_token}\x01\x01"


@contextmanager
def inbox(account, password):
    try:
        client = BoundedIMAP(account["host"], account["port"],
                             ssl_context=ssl.create_default_context(), timeout=8)
        client.sock.settimeout(8)
    except (OSError, imaplib.IMAP4.error):
        raise MailError("connection_failed") from None
    try:
        try:
            if account.get("auth_mode") == "xoauth2":
                payload = xoauth2_payload(account["username"], password).encode("ascii")
                responses = iter((payload, b""))
                client.authenticate("XOAUTH2", lambda _: next(responses, None))
            else:
                # imaplib quotes the password, but passes the username as an IMAP argument.
                username = account["username"].replace("\\", "\\\\").replace('"', '\\"')
                client.login(f'"{username}"', password)
        except imaplib.IMAP4.abort:
            raise MailError("connection_failed") from None
        except imaplib.IMAP4.error:
            raise MailError("authentication_failed") from None
        state, data = client.select("INBOX", readonly=True)
        validity = (client.response("UIDVALIDITY")[1] or [None])[0]
        if state != "OK" or not validity or not validity.isdigit():
            raise MailError("inbox_unavailable")
        yield client, int(data[0]), int(validity)
    except (OSError, ValueError, IndexError, imaplib.IMAP4.error):
        raise MailError("connection_failed") from None
    finally:
        # Close the transport directly: no CLOSE/EXPUNGE and no extra network wait.
        try:
            client.shutdown()
        except OSError:
            pass


def verify(account, password):
    with inbox(account, password):
        pass


def _literal(response):
    for item in response or []:
        if isinstance(item, tuple) and isinstance(item[1], bytes):
            yield item


def _text(message, field, limit):
    return " ".join(str(message.get(field, "")).split())[:limit]


def snapshot(account, password):
    """Replace one bounded snapshot, never claim coverage beyond its window."""
    with inbox(account, password) as (client, count, validity):
        if not count:
            return validity, [], False
        cutoff = datetime.now(UTC) - timedelta(days=WINDOW_DAYS)
        months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        since = f"{cutoff.day:02d}-{months[cutoff.month - 1]}-{cutoff.year}"
        # Bound the sequence range, then address each result by stable UID.
        start = max(1, count - MAX_INBOX + 1)
        state, data = client.uid("SEARCH", None, f"{start}:{count}", "SINCE", since)
        if state != "OK":
            raise MailError("inbox_unavailable")
        uids = sorted({int(x) for x in (data[0] or b"").split() if x.isdigit()}, reverse=True)
        if len(uids) > MAX_INBOX:
            raise MailError("inbox_unavailable")
        rows = []
        for offset in range(0, len(uids), 50):
            batch = uids[offset:offset + 50]
            state, data = client.uid(
                "FETCH", ",".join(map(str, batch)),
                "(UID FLAGS INTERNALDATE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)]<0.8192>)",
            )
            if state != "OK":
                raise MailError("inbox_unavailable")
            for metadata, content in _literal(data):
                uid = re.search(rb"\bUID (\d+)\b", metadata)
                internal = re.search(rb'\bINTERNALDATE "([^"]+)"', metadata)
                flags = re.search(rb"\bFLAGS \(([^)]*)\)", metadata)
                if not uid or int(uid[1]) not in batch or not internal or not flags:
                    raise MailError("inbox_unavailable")
                message = BytesParser(policy=policy.default).parsebytes(content, headersonly=True)
                received = parsedate_to_datetime(internal[1].decode("ascii")).astimezone(UTC)
                message_flags = flags[1].lower().split()
                rows.append((int(uid[1]), _text(message, "Subject", 500), _text(message, "From", 500),
                             received.isoformat(), int(b"\\seen" in message_flags),
                             int(b"\\answered" in message_flags)))
        if {r[0] for r in rows} != set(uids) or len(rows) != len(uids):
            raise MailError("inbox_changed")
        return validity, rows, count > MAX_INBOX


def analysis_texts(account, password, validity, uids):
    """Read bounded MIME text without loading resources or setting Seen."""
    bodies = {}
    with inbox(account, password) as (client, _, current):
        if current != validity:
            raise MailError("inbox_changed")
        requested = set(uids)
        state, data = client.uid("FETCH", ",".join(map(str, uids)), "(UID BODY.PEEK[]<0.49152>)")
        if state != "OK":
            raise MailError("inbox_unavailable")
        for metadata, content in _literal(data):
            identity = re.search(rb"\bUID (\d+)\b", metadata)
            if identity and (uid := int(identity[1])) in requested:
                message = BytesParser(policy=policy.default).parsebytes(content)
                bodies[uid] = " ".join(_preview_text(message)["text"].split())[:850]
    return bodies


def reply_headers(account, password, validity, uid):
    with inbox(account, password) as (client, _, current):
        if current != validity:
            raise MailError("inbox_changed")
        state, data = client.uid("FETCH", str(uid),
            "(UID BODY.PEEK[HEADER.FIELDS (FROM REPLY-TO SUBJECT MESSAGE-ID REFERENCES)]<0.8192>)")
        if state == "OK":
            for metadata, content in _literal(data):
                identity = re.search(rb"\bUID (\d+)\b", metadata)
                if identity and int(identity[1]) == uid and len(content) < 8192:
                    return BytesParser(policy=policy.default).parsebytes(content, headersonly=True)
        raise MailError("mail_reply_unavailable")


def read_preview(account, password, validity, uid, *, load_images=False):
    with inbox(account, password) as (client, _, current):
        if current != validity:
            raise MailError("inbox_changed")
        state, data = client.uid("FETCH", str(uid), f"(UID RFC822.SIZE BODY.PEEK[]<0.{MAX_BODY}>)")
        if state != "OK":
            raise MailError("inbox_unavailable")
        for metadata, content in _literal(data):
            identity = re.search(rb"\bUID (\d+)\b", metadata)
            size = re.search(rb"\bRFC822.SIZE (\d+)\b", metadata)
            if not identity or int(identity[1]) != uid or not size:
                raise MailError("inbox_unavailable")
            if int(size[1]) != len(content) or len(content) >= MAX_BODY:
                return {"text": "", "preview_status": "too_large"}
            break
        else:
            raise MailError("inbox_changed")
    message = BytesParser(policy=policy.default).parsebytes(content)
    preview = _preview_text(message)
    part = message.get_body(preferencelist=("html",))
    if part is not None:
        try:
            markup, total, loaded = formatted_html(
                part.get_content(errors="replace"), RemoteImages() if load_images else None,
            )
            if markup and len(markup) <= MAX_BODY + (3 * 1024 * 1024 if load_images else 0):
                preview["html"] = markup
                preview["html_links"] = True
                if total:
                    preview.update(remote_images=total, loaded_images=loaded)
        except (LookupError, ValueError):
            pass
    return preview
