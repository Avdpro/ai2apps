"""Mail owner fixtures exercise the real API, storage and credential boundaries."""

from dataclasses import replace
import base64
import hashlib
import json
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from ai2apps.api.mail import create_mail_router
from ai2apps.apps import SYSTEM_APP_MANIFESTS
from ai2apps.identity import RequestPrincipal
from ai2apps.mail import imap
from ai2apps.mail import gmail_oauth
from ai2apps.mail import service as mail
from ai2apps.secrets.backends import MemorySecretBackend
from ai2apps.storage import PlatformDatabase


@pytest.fixture
def mail_fixture(tmp_path, monkeypatch):
    db = PlatformDatabase(tmp_path / "mail-test.sqlite")
    db.initialize()
    secret = MemorySecretBackend()
    service = mail.MailService(db, secret)
    principal = RequestPrincipal.legacy_local()
    caller = [principal]
    app = FastAPI()
    app.include_router(create_mail_router(lambda: SimpleNamespace(mail=service), lambda: caller[0]))

    def verify(account, password):
        if password == "rejected":
            raise imap.MailError("authentication_failed")

    monkeypatch.setattr(imap, "verify", verify)
    monkeypatch.setattr(mail, "probe_smtp", lambda account, password: "authenticated" if account["smtp_host"] else "not_configured")
    monkeypatch.setattr(imap, "snapshot", lambda account, password: (
        35, [(10, "Subject " + account["provider"], "sender@example.test", "2026-11-12T10:00:00+00:00", 0, 0)], True,
    ))
    monkeypatch.setattr(imap, "read_preview", lambda *args: {"text": "<script>mail data</script>", "preview_status": "complete"})
    with TestClient(app) as client:
        yield client, service, secret, caller


def test_builtin_and_three_providers_unified_inbox(mail_fixture):
    client, _, _, _ = mail_fixture
    manifest = next(app for app in SYSTEM_APP_MANIFESTS if app["id"] == "ai2apps.mail")
    assert manifest["entry"] == {"kind": "host", "resource": "ai2apps:system/mail"}
    cases = (
        ({"provider": "icloud", "address": "test@icloud.com", "password": "icloud-fixture-secret"}, "imap.mail.me.com", "test"),
        ({"provider": "gmail", "address": "test@gmail.com", "password": "abcd efgh ijkl mnop"}, "imap.gmail.com", "test@gmail.com"),
        ({"provider": "imap", "address": "test@example.test", "host": "imap.example.test", "password": "generic-fixture-secret"}, "imap.example.test", "test@example.test"),
    )
    ids = []
    for payload, host, username in cases:
        response = client.post("/mail/accounts", json=payload)
        assert response.status_code == 201
        record = response.json()
        assert record["host"] == host and record["username"] == username
        assert record["smtp_tls"] == "starttls"
        assert "secret_key" not in record and payload["password"] not in response.text
        ids.append(record["id"])
        assert client.post(f"/mail/accounts/{record['id']}/sync").json()["count"] == 1
    items = client.get("/mail/messages?limit=2").json()
    assert items["has_more"] and len(items["items"]) == 2
    assert len(client.get("/mail/messages?limit=2&offset=2").json()["items"]) == 1
    assert len(client.get("/mail/messages?q=GMAIL").json()["items"]) == 1
    path = f"/mail/accounts/{ids[0]}/messages/35/10"
    assert client.get(path).json()["text"] == "<script>mail data</script>"
    assert client.get(path.replace("/35/", "/36/")).status_code == 404


@pytest.mark.asyncio
async def test_mobile_mail_mount_reuses_owner_data_and_denies_desktop_routes(mail_fixture):
    from fastapi import HTTPException

    from ai2apps.identity import MemberRole
    from ai2apps.web.mobile_app_gateway import api_response

    client, service, _, caller = mail_fixture
    desktop = caller[0]
    owner = replace(desktop, client_scope="owner-home", authentication_type="owner_home_lease")
    account = client.post("/mail/accounts", json={
        "provider": "icloud", "address": "mail@example.test", "password": "fixture",
    }).json()
    account_path = f"/accounts/{account['id']}"
    assert client.post(f"/mail{account_path}/sync").status_code == 200
    spec = next(app["mobile"]["gateway"] for app in SYSTEM_APP_MANIFESTS if app["id"] == "ai2apps.mail")
    runtime = SimpleNamespace(mail=service)

    async def mounted(path, verb="GET", payload=None, principal=owner):
        return await api_response(runtime, principal, spec, {
            "verb": verb, "path": spec["api"]["prefix"] + path,
            "headers": {"content-type": "application/json"},
            "body": base64.b64encode(json.dumps(payload).encode()).decode() if payload is not None else "",
        })

    assert (await mounted("/accounts")).json()[0]["id"] == account["id"]
    assert len((await mounted("/messages")).json()["items"]) == 1
    message = account_path + "/messages/35/10"
    assert (await mounted(message)).json()["text"] == "<script>mail data</script>"
    assert (await mounted(message + "/read", "POST", {})).status_code == 204
    assert client.get("/mail/messages").json()["items"][0]["seen"]
    draft = await mounted("/drafts", "POST", {
        "account_id": account["id"], "recipients": [], "subject": "Mobile draft", "body": "Saved on the phone",
        "attachments": [{"name": "fixture.txt", "data": "dGVzdA=="}],
    })
    assert draft.status_code == 201
    assert client.get("/mail/drafts/" + draft.json()["id"]).json()["attachments"][0]["name"] == "fixture.txt"
    for principal in (desktop, replace(owner, role=MemberRole.MEMBER),
                      replace(owner, authentication_type="remote_session")):
        assert (await mounted("/accounts", principal=principal)).status_code == 403
    assert (await mounted("/accounts", principal=replace(owner, actor_user_id="other"))).json() == []
    assert (await mounted(message, principal=replace(owner, installation_id="other"))).status_code == 404
    caller[0] = owner
    assert client.get("/mail/accounts").status_code == 403
    for verb, path in (("POST", "/accounts"), ("POST", account_path + "/reconnect"),
                       ("DELETE", account_path), ("POST", "/gmail/oauth")):
        assert (await mounted(path, verb, {})).status_code in {404, 405}
    with pytest.raises(HTTPException) as denied:
        await api_response(runtime, owner, spec, {"path": "/v1/platform/client/browser-profiles/default/launch"})
    assert denied.value.status_code == 403


def test_gmail_connect_and_reconnect_normalize_credentials_for_both_protocols(mail_fixture, monkeypatch):
    client, _, _, _ = mail_fixture
    address = "mailbox@gmail.com"
    attempts = []

    def verify(account, password):
        attempts.append(("imap", password))
        assert (account["host"], account["port"], account["username"]) == ("imap.gmail.com", 993, address)

    def probe(account, password):
        attempts.append(("smtp", password))
        assert (account["smtp_host"], account["smtp_port"], account["smtp_tls"], account["smtp_username"]) == (
            "smtp.gmail.com", 587, "starttls", address,
        )
        return "authenticated"

    monkeypatch.setattr(imap, "verify", verify)
    monkeypatch.setattr(mail, "probe_smtp", probe)
    response = client.post("/mail/accounts", json={
        "provider": "gmail", "address": address, "password": "abcd efgh ijkl mnop",
    })
    assert response.status_code == 201
    account = response.json()
    assert account["smtp_status"] == "authenticated"
    path = f"/mail/accounts/{account['id']}/reconnect"
    assert client.post(path, json={"password": "invalid"}).status_code == 422
    response = client.post(path, json={"password": "qrst uvwx yzab cdef"})
    assert response.status_code == 200
    assert response.json()["id"] == account["id"]
    assert attempts == [
        ("imap", "abcdefghijklmnop"), ("smtp", "abcdefghijklmnop"),
        ("imap", "qrstuvwxyzabcdef"), ("smtp", "qrstuvwxyzabcdef"),
    ]


def test_gmail_google_authorization_uses_loopback_pkce_and_refresh(mail_fixture, monkeypatch):
    client, service, secret, caller = mail_fixture
    assert client.post("/mail/gmail/oauth", json={}).json()["detail"] == "gmail_oauth_unconfigured"
    service.gmail.client_path.write_text(json.dumps({
        "installed": {"client_id": "fixture.apps.googleusercontent.com", "client_secret": "fixture-secret"},
    }))
    browser = []
    monkeypatch.setattr(gmail_oauth, "_open_browser", browser.append)
    checked = []
    monkeypatch.setattr(imap, "verify", lambda account, token: checked.append((account["auth_mode"], token)))

    def request(method, url, **kwargs):
        if url == gmail_oauth.USERINFO_URL:
            assert kwargs["headers"] == {"Authorization": "Bearer access-first"}
            return {"email": "mailbox@gmail.com", "email_verified": True}
        grant = kwargs["data"]
        assert grant["client_secret"] == "fixture-secret"
        if grant["grant_type"] == "refresh_token":
            assert grant["refresh_token"] == "stored-refresh"
            return {"access_token": "access-refreshed", "token_type": "Bearer"}
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(grant["code_verifier"].encode()).digest(),
        ).decode().rstrip("=")
        assert challenge == params["code_challenge"][0]
        assert grant["redirect_uri"] == redirect and grant["code"] == "fixture-code"
        return {"access_token": "access-first", "refresh_token": "stored-refresh",
                "token_type": "Bearer", "scope": gmail_oauth.MAIL_SCOPE}

    monkeypatch.setattr(service.gmail, "_request", request)
    flow_id = client.post("/mail/gmail/oauth", json={}).json()["flow_id"]
    endpoint = "/mail/gmail/oauth/" + flow_id
    assert client.post(endpoint, json={}).json() == {"status": "pending"}
    original = caller[0]
    caller[0] = replace(original, installation_id="different")
    assert client.post(endpoint, json={}).status_code == 404
    assert client.delete(endpoint).status_code == 204
    caller[0] = original
    params = parse_qs(urlsplit(browser[0]).query)
    redirect = params["redirect_uri"][0]
    assert urlsplit(redirect).hostname == "127.0.0.1"
    assert params["code_challenge_method"] == ["S256"]
    assert gmail_oauth.MAIL_SCOPE in params["scope"][0].split()
    with pytest.raises(HTTPError) as wrong_state:
        urlopen(redirect + "?state=wrong&code=fixture-code", timeout=2)
    assert wrong_state.value.code == 400
    assert client.post(endpoint, json={}).json() == {"status": "pending"}
    with urlopen(redirect + "?" + urlencode({"state": params["state"][0], "code": "fixture-code"}), timeout=2) as callback:
        assert callback.status == 200
        assert b"fixture-code" not in callback.read()
    response = client.post(endpoint, json={})
    assert response.status_code == 200
    assert "stored-refresh" not in response.text and "access-first" not in response.text
    account = response.json()["account"]
    assert account["auth_mode"] == "xoauth2" and account["address"] == "mailbox@gmail.com"
    assert checked == [("xoauth2", "access-first")]
    assert client.post(endpoint, json={}).status_code == 404
    with service.database.transaction() as db:
        key = db.execute("SELECT secret_key FROM mail_accounts").fetchone()[0]
    assert secret.load(key) == "stored-refresh"
    path = f"/mail/accounts/{account['id']}"
    assert client.post(path + "/reconnect", json={"password": "invalid"}).json()["detail"] == "gmail_oauth_required"

    def snapshot(account, token):
        assert account["auth_mode"] == "xoauth2"
        assert token == "access-refreshed"
        return 35, [(10, "Fixture", "sender@example.test", "2026-11-12T10:00:00+00:00", 0, 0)], False

    monkeypatch.setattr(imap, "snapshot", snapshot)
    assert client.post(path + "/sync").json()["count"] == 1

    def revoked(_):
        raise imap.MailError("authentication_failed")

    monkeypatch.setattr(service.gmail, "refresh", revoked)
    assert client.post(path + "/sync").json()["detail"] == "gmail_oauth_required"
    assert client.get("/mail/accounts").json()[0]["status"] == "reconnect_required"
    assert len(client.get("/mail/messages").json()["items"]) == 1


def test_gmail_uses_xoauth2_on_both_mail_transports(monkeypatch):
    calls = []

    class IMAP:
        sock = SimpleNamespace(settimeout=lambda timeout: None)

        def __init__(self, *args, **kwargs):
            pass

        def authenticate(self, mechanism, respond):
            calls.append(("imap", mechanism, respond(b"")))
            assert respond(b"denied") == b""

        def select(self, mailbox, *, readonly):
            assert mailbox == "INBOX" and readonly
            return "OK", [b"0"]

        def response(self, _):
            return "UIDVALIDITY", [b"35"]

        def shutdown(self):
            pass

    class SMTP:
        def __init__(self, *args, **kwargs):
            self.tls = False

        def starttls(self, *, context):
            assert context.check_hostname
            self.tls = True

        def ehlo(self):
            assert self.tls

        def auth(self, mechanism, respond):
            assert self.tls and respond(b"denied") == ""
            calls.append(("smtp", mechanism, respond().encode()))

        def close(self):
            pass

    monkeypatch.setattr(imap, "BoundedIMAP", IMAP)
    monkeypatch.setattr(mail.smtplib, "SMTP", SMTP)
    account, _ = mail.account_settings({
        "provider": "gmail", "address": "mailbox@gmail.com", "display_name": "",
        "password": "abcdefghijklmnop",
    })
    account["auth_mode"] = "xoauth2"
    imap.verify(account, "access-token")
    assert mail.probe_smtp(account, "access-token") == "authenticated"
    payload = b"user=mailbox@gmail.com\x01auth=Bearer access-token\x01\x01"
    assert calls == [("imap", "XOAUTH2", payload), ("smtp", "XOAUTH2", payload)]


def test_scope_reconnect_and_remove(mail_fixture, monkeypatch):
    client, service, secret, caller = mail_fixture
    password = "fixture-old-password"
    account = client.post("/mail/accounts", json={"provider": "imap", "host": "imap.example.test",
                                                    "address": "a@example.test", "password": password}).json()
    path = f"/mail/accounts/{account['id']}"
    with service.database.transaction() as db:
        old_key = db.execute("SELECT secret_key FROM mail_accounts").fetchone()[0]
    assert secret.load(old_key) == password
    assert client.post(path + "/sync").status_code == 200
    original = caller[0]
    for other in (replace(original, actor_user_id="other"), replace(original, installation_id="other")):
        caller[0] = other
        assert client.get("/mail/accounts").json() == []
        assert client.get("/mail/messages").json()["items"] == []
        assert client.get(path + "/messages/35/10").status_code == 404
        assert client.delete(path).status_code == 404
    caller[0] = replace(original, client_scope="mobile")
    assert client.get("/mail/accounts").status_code == 403
    caller[0] = original
    monkeypatch.setattr(imap, "snapshot", lambda *args: (_ for _ in ()).throw(imap.MailError("authentication_failed")))
    assert client.post(path + "/sync").status_code == 409
    assert client.get("/mail/accounts").json()[0]["status"] == "reconnect_required"
    assert len(client.get("/mail/messages").json()["items"]) == 1
    assert client.post(path + "/reconnect", json={"password": "fixture-new-password"}).status_code == 200
    with pytest.raises(KeyError):
        secret.load(old_key)
    with service.database.transaction() as db:
        new_key = db.execute("SELECT secret_key FROM mail_accounts").fetchone()[0]
    assert secret.load(new_key) == "fixture-new-password"
    assert client.delete(path).status_code == 204
    assert client.get("/mail/messages").json()["items"] == []
    with pytest.raises(KeyError):
        secret.load(new_key)


def test_invalid_credentials_are_redacted_and_not_persisted(mail_fixture):
    client, _, _, _ = mail_fixture
    response = client.post("/mail/accounts", json={"password": "secret-must-not-echo"})
    assert response.status_code == 422 and "secret-must-not-echo" not in response.text
    response = client.post("/mail/accounts", json={"provider": "gmail", "address": "a@gmail.com", "password": "normal-password"})
    assert response.json()["detail"] == "gmail_app_password_required"
    response = client.post("/mail/accounts", json={"provider": "imap", "host": "imap.example.test",
                                                    "address": "a@example.test", "password": "rejected"})
    assert response.status_code == 409 and client.get("/mail/accounts").json() == []


@pytest.mark.parametrize(("raw", "expected"), [
    (b"Content-Type: text/plain; charset=utf-8\r\n\r\nHello.", "Hello."),
    (
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<head><title>Invisible title</title></head>"
        b"<h1>News &amp; updates</h1><p>Read <b>this</b><br>Next line</p>"
        b'<img src="https://tracker.invalid/pixel" alt="tracking image">'
        b"<script>never execute()</script><style>ignore styles</style>"
        b"<template>hidden template</template><!-- hidden comment -->",
        "News & updates\nRead this\nNext line",
    ),
])
def test_imap_snapshot_and_preview_use_read_only_uid_commands(monkeypatch, raw, expected):
    calls = []
    header = b"Subject: Sample\r\nFrom: sender@example.test\r\n\r\n"

    class ProtocolFixture:
        def __init__(self, host, port, *, ssl_context, timeout):
            self.sock = SimpleNamespace(settimeout=lambda value: None)
            assert ssl_context.check_hostname and timeout == 8

        def login(self, username, password):
            assert username == '"user with space"'
            assert password == "fixture"

        def select(self, mailbox, *, readonly):
            assert mailbox == "INBOX" and readonly
            return "OK", [b"230"]

        def response(self, name):
            assert name == "UIDVALIDITY"
            return name, [b"35"]

        def uid(self, command, *args):
            calls.append((command, *args))
            if command == "SEARCH":
                assert args[1:3] == ("31:230", "SINCE")
                return "OK", [b"10"]
            if "HEADER.FIELDS" in args[-1]:
                return "OK", [(b'22 (UID 10 FLAGS (\\Seen \\Answered) INTERNALDATE "12-Nov-2026 10:00:00 +0000"', header)]
            return "OK", [(f"22 (UID 10 RFC822.SIZE {len(raw)}".encode(), raw)]

        def shutdown(self):
            pass

    monkeypatch.setattr(imap, "BoundedIMAP", ProtocolFixture)
    account = {"host": "imap.example.test", "port": 993, "username": "user with space"}
    assert imap.snapshot(account, "fixture") == (
        35, [(10, "Sample", "sender@example.test", "2026-11-12T10:00:00+00:00", 1, 1)], True,
    )
    preview = imap.read_preview(account, "fixture", 35, 10)
    assert preview["text"] == expected and preview["preview_status"] == "complete"
    if b"Content-Type: text/html" in raw:
        assert preview["html"] == "<h1>News &amp; updates</h1><p>Read <b>this</b><br>Next line</p>"
    else:
        assert "html" not in preview
    assert [call[0] for call in calls] == ["SEARCH", "FETCH", "FETCH"]
    assert all("BODY.PEEK" in call[-1] for call in calls[1:])
    with pytest.raises(imap.MailError, match="inbox_changed"):
        imap.read_preview(account, "fixture", 34, 10)


@pytest.mark.parametrize(("plain", "expected"), [
    ("Plain text wins.", "Plain text wins.\n"),
    ("   ", "HTML fallback."),
])
def test_preview_selects_readable_mime_alternative(plain, expected):
    from email.message import EmailMessage

    message = EmailMessage()
    message.set_content(plain)
    message.add_alternative("<p>HTML fallback.</p>", subtype="html")
    assert imap._preview_text(message) == {"text": expected, "preview_status": "complete"}


def test_formatted_preview_keeps_links_as_inert_actions_without_external_resources():
    from ai2apps.mail.html_preview import passive_html

    assert passive_html(
        '<meta http-equiv="refresh" content="0;url=https://example.invalid">'
        '<style>@import "https://example.invalid/style";</style>'
        '<table width="600"><tr><td style="color:#d00; padding:12px; '
        'background-color:url(https://example.invalid/pixel)" onclick="doSomething()">'
        '<a href="https://example.invalid/link?a=1&amp;b=2" target="_top" ping="https://example.invalid/track">Read &amp; review</a>'
        '<a href="jav&#x61;script:alert(1)">Script</a><a href="file:///tmp/file">File</a>'
        '<a href="https://user:pass@example.invalid/">Credentials</a>'
        '<img src="https://example.invalid/pixel" srcset="https://example.invalid/b 2x">'
        '<script>skip()</script></td></tr></table>'
    ) == ('<table width="600"><tr><td style="color:#d00;padding:12px">'
          '<a href="#" data-mail-url="https://example.invalid/link?a=1&amp;b=2">Read &amp; review</a>'
          '<span>Script</span><span>File</span><span>Credentials</span></td></tr></table>')


def test_remote_images_are_opt_in_and_insert_only_local_raster_data():
    from ai2apps.mail.html_preview import formatted_html

    source = ('<p>Message</p><img src="https://images.example/logo.png" alt="Logo" '
              'srcset="https://other.example/tracker.png 2x" onload="run()" />'
              '<img src="http://images.example/cleartext.png">')
    assert formatted_html(source) == ("<p>Message</p>", 1, 0)
    requested = []

    def load(url):
        requested.append(url)
        return "data:image/png;base64,fixture"

    html, total, loaded = formatted_html(source, load)
    assert requested == ["https://images.example/logo.png"]
    assert (total, loaded) == (1, 1)
    assert html == '<p>Message</p><img src="data:image/png;base64,fixture" alt="Logo">'


def test_mail_preserves_safe_responsive_layout_and_image_styles():
    from ai2apps.mail.html_preview import formatted_html

    source = (
        '<head><style>@import "https://example.invalid/a";'
        '.app-icon { width: 64px; background-image: url(https://example.invalid/b) }'
        '@media only screen and (max-device-width: 600px) {'
        ' .app-icon {width:48px !important;height:auto} .footer {padding-bottom:16px} }'
        '@font-face { font-family: stolen; src:url(https://example.invalid/font) }'
        '</style></head><body class="message" style="margin:0">'
        '<div class="footer">Footer<img class="app-icon" '
        'style="width:64px;height:64px;border-radius:12px" src="https://example.invalid/icon"></div></body>'
    )
    html, total, loaded = formatted_html(source, lambda _: "data:image/png;base64,fixture")
    assert (total, loaded) == (1, 1)
    assert html == (
        '<style>.app-icon{width:64px}@media only screen and (max-width: 600px)'
        '{.app-icon{width:48px !important;height:auto}.footer{padding-bottom:16px}}</style>'
        '<body class="message" style="margin:0"><div class="footer">Footer'
        '<img src="data:image/png;base64,fixture" alt="" style="width:64px;height:64px;border-radius:12px"'
        ' class="app-icon"></div></body>'
    )


def test_mail_preserves_solid_background_shorthand_without_loading_images():
    from ai2apps.mail.html_preview import passive_html

    markup = passive_html(
        '<style>.label{background:navy !important}</style>'
        '<table><tr><td style="background:#181818">'
        '<a class="label" href="https://example.invalid/" style="background:#76BBFF;'
        'background:url(https://example.invalid/track);color:#181818">Read more</a></td></tr></table>'
    )
    assert markup == (
        '<style>.label{background-color:navy !important}</style>'
        '<table><tr><td style="background-color:#181818">'
        '<a class="label" style="background-color:#76BBFF;color:#181818" href="#" '
        'data-mail-url="https://example.invalid/">Read more</a></td></tr></table>'
    )


def test_mail_keeps_spacer_dimensions_without_fetching_pixels():
    from ai2apps.mail.html_preview import formatted_html

    requested = []
    source = ('<table><tr><td><img src="https://example.invalid/pixel" width=1 height=30 '
              'style="display:block" class="footer-gap"></td></tr>'
              '<tr><td>Footer</td></tr></table>')
    html, total, loaded = formatted_html(source, requested.append)
    assert not requested
    assert (total, loaded) == (0, 0)
    assert '<span aria-hidden="true" class="footer-gap" style="display:inline-block;width:1px;height:30px;display:block"></span>' in html


def test_compose_and_reply_submit_only_after_all_recipients_are_accepted(mail_fixture, monkeypatch):
    from email import policy
    from email.parser import BytesParser

    client, _, _, caller = mail_fixture
    account = client.post("/mail/accounts", json={"provider": "icloud", "address": "test@icloud.com",
                                                 "password": "fixture"}).json()
    path = f"/mail/accounts/{account['id']}"
    assert client.post(path + "/sync").status_code == 200
    reply_path = path + "/messages/35/10/reply"
    original = BytesParser(policy=policy.default).parsebytes(
        b"From: sender@example.test\r\nReply-To: help@example.test\r\nSubject: Test\r\n"
        b"Message-ID: <original@example.test>\r\nReferences: <older@example.test>\r\n\r\n")
    monkeypatch.setattr(imap, "reply_headers", lambda *args: original)
    sent = []
    uncertain = False

    class SMTPFixture:
        def __init__(self, host, port, *, timeout):
            assert (host, port) == ("smtp.mail.me.com", 587)

        def starttls(self, *, context):
            assert context.check_hostname

        def login(self, username, password):
            assert (username, password) == ("test@icloud.com", "fixture")

        def mail(self, sender):
            assert sender == "test@icloud.com"
            return 250, b"OK"

        def rcpt(self, address):
            return (550 if address.startswith("rejected") else 250), b""

        def data(self, body):
            if uncertain:
                raise mail.smtplib.SMTPServerDisconnected()
            sent.append(BytesParser(policy=policy.default).parsebytes(body))
            return 250, b"OK"

        def close(self):
            pass

    monkeypatch.setattr(mail.smtplib, "SMTP", SMTPFixture)
    draft = {"recipients": ["first@example.test", "rejected@example.test"],
             "subject": "测试邮件", "body": "Hello\n测试"}
    assert client.post(path + "/send", json=draft).json()["detail"] == "mail_recipient_rejected"
    assert not sent
    draft["recipients"][1] = "second@example.test"
    assert client.post(path + "/send", json=draft).json()["sent"]
    assert str(sent[0]["Subject"]) == "测试邮件"
    assert sent[0].get_content().strip().splitlines() == ["Hello", "测试"]
    assert len(sent[0]["To"].addresses) == 2
    assert client.get(reply_path).json() == {"recipient": "help@example.test", "subject": "Re: Test"}
    draft["recipients"] = ["sender@example.test"]
    assert client.post(reply_path, json=draft).json()["detail"] == "mail_reply_target_changed"
    draft["recipients"] = ["help@example.test"]
    uncertain = True
    assert client.post(reply_path, json=draft).json()["detail"] == "mail_send_uncertain"
    assert not client.get("/mail/smart-folders/answered/messages").json()["items"]
    uncertain = False
    assert client.post(reply_path, json=draft).json() == {"sent": True, "reply_marked": True}
    assert sent[1]["In-Reply-To"] == "<original@example.test>"
    assert sent[1]["References"] == "<older@example.test> <original@example.test>"
    assert client.post(path + "/sync").status_code == 200
    assert client.get("/mail/smart-folders/answered/messages").json()["items"][0]["uid"] == 10
    caller[0] = replace(caller[0], actor_user_id="other")
    assert client.post(path + "/send", json=draft).status_code == 404
    assert len(sent) == 2


def test_local_reply_draft_retains_attachment_until_smtp_accepts(mail_fixture, monkeypatch):
    from email import policy
    from email.parser import BytesParser

    client, _, _, caller = mail_fixture
    account = client.post("/mail/accounts", json={"provider": "icloud", "address": "test@icloud.com",
                                                 "password": "fixture"}).json()
    account_id = account["id"]
    assert client.post(f"/mail/accounts/{account_id}/sync").status_code == 200
    original = BytesParser(policy=policy.default).parsebytes(
        b"From: sender@example.test\r\nSubject: Test\r\nMessage-ID: <original@example.test>\r\n\r\n")
    monkeypatch.setattr(imap, "reply_headers", lambda *args: original)
    contents = b"\x00\xff fixture"
    attachment = {"name": "报告.bin", "data": base64.b64encode(contents).decode("ascii")}
    payload = {"account_id": account_id, "subject": "Re: Test", "body": "", "recipients": [],
               "attachments": [attachment], "reply": {"validity": 35, "uid": 10}}
    sent = []
    failure = "mail_send_rejected"

    def deliver(account, password, message, addresses):
        if failure:
            raise imap.MailError(failure)
        sent.append(BytesParser(policy=policy.default).parsebytes(message.as_bytes()))

    monkeypatch.setattr(mail, "deliver_smtp", deliver)
    assert client.post("/mail/drafts", json={**payload, "attachments": [{**attachment, "data": "*"}]}).status_code == 422
    response = client.post("/mail/drafts", json=payload)
    assert response.status_code == 201
    path = "/mail/drafts/" + response.json()["id"]
    listing = client.get("/mail/drafts", params={"account_id": account_id}).json()
    assert listing[0]["attachment_count"] == 1 and "attachments" not in listing[0]
    assert client.get(path).json()["attachments"] == [attachment]
    principal = caller[0]
    caller[0] = replace(principal, actor_user_id="other")
    assert client.get(path).status_code == 404 and client.get("/mail/drafts").json() == []
    caller[0] = principal
    payload["recipients"] = ["sender@example.test"]
    assert client.put(path, json={**payload, "revision": 1}).json()["revision"] == 2
    assert client.put(path, json={**payload, "revision": 1}).status_code == 409
    assert not sent
    assert client.post(path + "/send", json={"revision": 2}).json()["detail"] == "mail_send_rejected"
    assert client.get(path).json()["status"] == "draft"
    failure = None
    assert client.post(path + "/send", json={"revision": 2}).json() == {"sent": True, "reply_marked": True}
    assert client.get(path).status_code == 404
    assert sent[0]["In-Reply-To"] == "<original@example.test>"
    part, = sent[0].iter_attachments()
    assert part.get_filename() == "报告.bin" and part.get_payload(decode=True) == contents
    draft_id = client.post("/mail/drafts", json=payload).json()["id"]
    uncertain_path = "/mail/drafts/" + draft_id
    failure = "mail_send_uncertain"
    assert client.post(uncertain_path + "/send", json={"revision": 1}).json()["detail"] == failure
    assert client.get(uncertain_path).json()["status"] == "uncertain"
    failure = None
    assert client.post(uncertain_path + "/send", json={"revision": 1}).status_code == 409
    assert len(sent) == 1
    assert client.delete(uncertain_path, params={"revision": 1}).status_code == 204


def test_remote_image_action_rechecks_message_scope_and_rejects_arbitrary_urls(mail_fixture, monkeypatch):
    client, _, _, caller = mail_fixture
    account = client.post("/mail/accounts", json={"provider": "imap", "host": "imap.example.test",
                                                 "address": "mail@example.test", "password": "fixture"}).json()
    path = f"/mail/accounts/{account['id']}"
    assert client.post(path + "/sync").status_code == 200
    requests = []
    images_available = False

    def preview(account, password, validity, uid, *, load_images=False):
        requests.append((validity, uid, load_images))
        return {"text": "Sample", "html": "<p>Sample</p>", "preview_status": "complete",
                "remote_images": 1, "loaded_images": int(load_images and images_available)}

    monkeypatch.setattr(imap, "read_preview", preview)
    endpoint = path + "/messages/35/10"
    assert client.get(endpoint).json()["auto_load_images"] is False
    assert client.post(endpoint + "/remote-images", json={"url": "https://example.invalid/"}).status_code == 422
    assert client.post(endpoint + "/remote-images", json={}).json()["auto_load_images"] is False
    images_available = True
    assert client.post(endpoint + "/remote-images", json={}).json()["auto_load_images"] is True
    restored = client.get(endpoint).json()
    assert restored["auto_load_images"] is True
    assert restored["loaded_images"] == 0
    caller[0] = replace(caller[0], actor_user_id="other")
    assert client.post(endpoint + "/remote-images", json={}).status_code == 404
    assert requests == [(35, 10, False), (35, 10, True), (35, 10, True), (35, 10, False)]


def test_remote_image_fetch_refuses_non_public_destination_and_reencodes():
    import time
    from io import BytesIO
    from PIL import Image
    from ai2apps.mail.remote_images import _download, _png

    with pytest.raises(ValueError, match="non-public"):
        _download("https://127.0.0.1/image", time.monotonic() + 1)
    original = BytesIO()
    Image.new("RGB", (20, 20), "red").save(original, format="JPEG", comment=b"metadata")
    clean = _png(original.getvalue())
    with Image.open(BytesIO(clean)) as image:
        assert image.format == "PNG" and image.size == (20, 20) and not image.info


def test_smtp_probes_only_after_tls_and_never_submits(monkeypatch):
    calls = []

    class SMTPFixture:
        def __init__(self, host, port, *, timeout):
            calls.append(("connect", host, port, timeout))

        def starttls(self, *, context):
            assert context.check_hostname
            calls.append("starttls")

        def login(self, username, password):
            calls.append(("authenticate", username))
            assert password == "fixture"

        def close(self):
            calls.append("close")

    monkeypatch.setattr(mail.smtplib, "SMTP", SMTPFixture)
    account = {"smtp_host": "smtp.mail.me.com", "smtp_port": 587,
               "smtp_tls": "starttls", "smtp_username": "test@icloud.com"}
    assert mail.probe_smtp(account, "fixture") == "authenticated"
    assert calls == [("connect", "smtp.mail.me.com", 587, 8), "starttls",
                     ("authenticate", "test@icloud.com"), "close"]

    def reject_tls(self, *, context):
        raise mail.smtplib.SMTPNotSupportedError

    monkeypatch.setattr(SMTPFixture, "starttls", reject_tls)
    calls.clear()
    assert mail.probe_smtp(account, "fixture") == "connection_failed"
    assert calls == [("connect", "smtp.mail.me.com", 587, 8), "close"]


def test_builtin_shell_renders_mail_without_native_launch():
    from starlette.requests import Request
    from omlx.admin import routes

    principal = RequestPrincipal.legacy_local()
    manager = SimpleNamespace(instance_entry=lambda *a, **k: {
        "renderer": "host", "resource": "ai2apps:system/mail",
    })
    url = routes._shell_entry_payload(manager, "mail", principal=principal)["content_url"]
    request = Request({"type": "http", "path": url, "headers": [], "query_string": b""})
    page = routes._system_app_content_response(request, "ai2apps.mail", include_api_key=False, principal=principal)
    assert page.status_code == 200
    assert b'id="mail-form" method="dialog"' in page.body
    assert b'/js/mail.js' in page.body and b'/css/mail.css' in page.body


def test_writing_assist_reads_owned_reply_and_returns_reviewable_text(mail_fixture, monkeypatch):
    client, service, _, caller = mail_fixture
    account = client.post("/mail/accounts", json={
        "provider": "icloud", "address": "writer@example.test", "password": "fixture-password",
    }).json()
    prefix = f"/mail/accounts/{account['id']}"
    assert client.post(prefix + "/sync").status_code == 200
    new_path = prefix + "/writing-assist"
    reply_path = prefix + "/messages/35/10/writing-assist"
    calls = []

    class Model:
        def model(self, model_id):
            assert model_id == "fixture-privacy-model"
            return None

        async def invoke_chat_json(self, request, *, context):
            system, user = request["messages"]
            payload = json.loads(user["content"])
            calls.append((payload, context.actor_user_id))
            assert "untrusted reference data" in system["content"]
            assert "tools" not in request
            answer = ({"summary": "The sender requests a meeting.", "directions": ["Accept", "Decline", "Reschedule"]}
                      if "user_instruction" not in payload else {"body": "Could we meet next week?"})
            return {"choices": [{"message": {"content": json.dumps(answer)}}]}

    def model_for(purpose, *, profile):
        assert (purpose, profile) == ("work_standard", "privacy")
        return "fixture-privacy-model"

    runtime = SimpleNamespace(mail=service, model_invocations=Model(),
                              model_manager=SimpleNamespace(resolve_default_model=model_for))
    api = FastAPI()
    api.include_router(create_mail_router(lambda: runtime, lambda: caller[0]))
    monkeypatch.setattr(mail, "deliver_smtp", lambda *args: pytest.fail("Writing must not send mail"))
    with TestClient(api) as writer:
        assert writer.post(new_path, json={"action": "directions"}).status_code == 422
        assert writer.post(new_path, json={"action": "write", "instruction": "Ask to meet"}).json() == {
            "body": "Could we meet next week?",
        }
        assert calls[-1][0]["original"] is None
        result = writer.post(reply_path, json={"action": "directions"})
        assert result.json()["directions"] == ["Accept", "Decline", "Reschedule"]
        assert calls[-1][0]["original"]["body"] == "<script>mail data</script>"
        assert writer.post(reply_path, json={"action": "write", "direction": "Reschedule"}).status_code == 200
        assert calls[-1][0]["chosen_direction"] == "Reschedule"
        assert writer.post(reply_path, json={
            "action": "write", "instruction": "Make it shorter", "body": "Previous draft",
        }).status_code == 200
        assert calls[-1][0]["draft"] == "Previous draft"
        principal = caller[0]
        caller[0] = replace(principal, installation_id="other")
        assert writer.post(reply_path, json={"action": "directions"}).status_code == 404
        assert len(calls) == 4 and all(actor == principal.actor_user_id for _, actor in calls)
        caller[0] = principal
    assert client.get("/mail/drafts").json() == []
    assert client.get("/mail/messages").json()["items"][0]["seen"] == 0


def test_smart_folders_classify_both_providers_and_keep_manual_overrides(mail_fixture, monkeypatch):
    from ai2apps.mail.smart_folders import SmartFolders

    client, service, _, caller = mail_fixture
    monkeypatch.setattr(imap, "analysis_texts", lambda account, password, validity, uids: {
        uid: "Order invoice. Payment is due tomorrow." for uid in uids
    })

    async def complete(self, runtime, principal, system, payload, max_tokens):
        if "existing" in payload:
            return {"folders": [{"name": "Orders", "rule": "Include invoices", "examples": [0]}]}
        return {"items": [{
            "index": message["index"],
            "matches": [{"id": folder["id"], "reason": "Order invoice"} for folder in payload["folders"]],
            "priority": 3, "reason": "Due tomorrow", "evidence": "Payment is due tomorrow.",
        } for message in payload["messages"]]}

    monkeypatch.setattr("ai2apps.mail.smart_folders.resolve_task_model", lambda *args: "fixture")
    monkeypatch.setattr(SmartFolders, "_model", complete)
    ids = []
    for provider, address, password in (
        ("gmail", "test@gmail.com", "abcd efgh ijkl mnop"),
        ("icloud", "test@icloud.com", "icloud-fixture"),
    ):
        account = client.post("/mail/accounts", json={"provider": provider, "address": address, "password": password})
        assert account.status_code == 201
        ids.append(account.json()["id"])
        assert client.post("/mail/accounts/" + ids[-1] + "/sync").status_code == 200

    suggestion = client.post("/mail/analysis/suggestions", json={}).json()[0]
    rule = {key: suggestion[key] for key in ("name", "rule")}
    assert client.post("/mail/analysis/preview", json=rule).json()["analyzed"] == 2
    rule["name"] = "Shopping"
    folder = client.post("/mail/smart-folders", json=rule).json()
    path = "/mail/smart-folders/" + folder["id"]
    assert client.post("/mail/analysis", json={}).json() == {"analyzed": 2, "remaining": 0}
    assert client.post("/mail/analysis", json={}).json()["analyzed"] == 0
    assert len(client.get(path + "/messages").json()["items"]) == 2

    top_path = "/mail/smart-folders/top5/messages"
    assert len(client.get(top_path).json()["items"]) == 2
    folders = client.get("/mail/smart-folders?language=zh").json()
    assert {item["name"] for item in folders} == {"Shopping", "疑似垃圾", "财务", "亲友"}
    assert next(item for item in folders if item["id"] == folder["id"])["rule"] == rule["rule"]
    assert len(client.get(top_path).json()["items"]) == 2
    assert len(client.get(path + "/messages").json()["items"]) == 2
    counts_path = "/mail/smart-folders/unread-counts"
    assert client.get(counts_path).json() == {
        "top5": 2, "flagged": 0, "todo": 0, "answered": 0, **{item["id"]: 2 if item["id"] == folder["id"] else 0 for item in folders},
    }
    read = "/mail/accounts/" + ids[0] + "/messages/35/10/read"
    assert client.post(read, json={}).status_code == 204
    assert client.post(read, json={}).status_code == 204
    assert client.post("/mail/accounts/" + ids[0] + "/sync").status_code == 200
    assert client.get(counts_path).json()[folder["id"]] == 1
    assert client.get(counts_path, params={"account_id": ids[0]}).json()["top5"] == 0
    assert client.get(counts_path, params={"account_id": ids[1]}).json()["top5"] == 1
    for listing in ("/mail/messages", path + "/messages"):
        visible = {item["account_id"]: item["seen"] for item in client.get(listing).json()["items"]}
        assert visible == {ids[0]: 1, ids[1]: 0}
    assert [item["account_id"] for item in client.get(top_path).json()["items"]] == [ids[1]]
    with service.database.transaction() as db:
        assert db.execute("SELECT seen FROM mail_messages WHERE account_id=?", (ids[0],)).fetchone()[0] == 0
    seeded = next(item for item in folders if item["preset"])
    assert client.get("/mail/smart-folders/" + seeded["id"] + "/messages").json()["analyzed"] == 0
    assert client.delete("/mail/smart-folders/" + seeded["id"], params={"revision": 1}).status_code == 204
    assert seeded["id"] not in {item["id"] for item in client.get("/mail/smart-folders").json()}
    feedback = "/mail/accounts/" + ids[0] + "/messages/35/10/classification"
    for target in ("top5", folder["id"]):
        assert client.post(feedback, json={"folder_id": target, "included": False}).status_code == 204
    edited = client.put(path, json={**rule, "rule": "Include invoices and refunds", "revision": 1})
    assert edited.status_code == 200
    assert client.post("/mail/analysis", json={}).json()["analyzed"] == 2
    assert client.get(path + "/messages").json()["items"][0]["account_id"] == ids[1]
    assert client.get(top_path).json()["items"][0]["account_id"] == ids[1]
    assert {item["account_id"]: item["seen"] for item in client.get("/mail/messages").json()["items"]} == {
        ids[0]: 1, ids[1]: 0,
    }
    caller[0] = replace(caller[0], installation_id="different-installation")
    assert client.get(path + "/messages").status_code == 404
    assert client.get(counts_path, params={"account_id": ids[0]}).status_code == 404
    assert client.post(feedback, json={"folder_id": "top5", "included": False}).status_code == 404
    assert client.post(read, json={}).status_code == 404
    other = client.get("/mail/smart-folders").json()
    assert {item["name"] for item in other} == {"Shopping", "Suspected junk", "Finance", "Friends & family"}
    assert not {item["id"] for item in other}.intersection(item["id"] for item in folders)


def test_top5_promotes_unread_candidates_without_reanalysis(mail_fixture, monkeypatch):
    from ai2apps.mail.smart_folders import SmartFolders

    client, _, _, _ = mail_fixture
    monkeypatch.setattr(imap, "snapshot", lambda *args: (
        35, [(uid, f"Message {uid}", "sender@example.test", f"2026-11-12T10:00:{uid}+00:00", int(uid == 17), 0)
             for uid in range(11, 18)], True,
    ))
    monkeypatch.setattr(imap, "analysis_texts", lambda *args: {})
    monkeypatch.setattr("ai2apps.mail.smart_folders.resolve_task_model", lambda *args: "fixture")

    async def complete(self, runtime, principal, system, payload, max_tokens):
        return {"items": [{
            "index": message["index"], "matches": [], "priority": 3, "reason": "Due tomorrow",
            "evidence": message["subject"],
        } for message in payload["messages"]]}

    monkeypatch.setattr(SmartFolders, "_model", complete)
    account = client.post("/mail/accounts", json={
        "provider": "icloud", "address": "test@icloud.com", "password": "icloud-fixture",
    }).json()
    account_path = f"/mail/accounts/{account['id']}"
    assert client.post(account_path + "/sync").status_code == 200
    assert client.post("/mail/analysis", json={}).json() == {"analyzed": 7, "remaining": 0}
    top = "/mail/smart-folders/top5/messages"
    assert [item["uid"] for item in client.get(top).json()["items"]] == [16, 15, 14, 13, 12]
    assert client.post(account_path + "/messages/35/16/read", json={}).status_code == 204
    result = client.post("/mail/analysis", json={}).json()
    assert (result["analyzed"], result["remaining"]) == (0, 0)
    assert [item["uid"] for item in client.get(top).json()["items"]] == [15, 14, 13, 12, 11]
    assert client.get("/mail/smart-folders/unread-counts").json()["top5"] == 5


def test_markers_retain_local_previews_and_sync_completion_with_todo(mail_fixture, monkeypatch, tmp_path):
    from ai2apps.todo.store import TodoStore

    client, service, _, caller = mail_fixture
    owner = caller[0].actor_user_id
    todo = TodoStore(tmp_path / "todo")
    service.markers.todo_store = lambda: todo
    rows = [(uid, f"Message {uid}", "sender@example.test", f"2026-11-12T10:00:{uid}+00:00", 0, 1)
            for uid in range(10, 14)]
    monkeypatch.setattr(imap, "snapshot", lambda *args: (35, rows, False))
    account = client.post("/mail/accounts", json={
        "provider": "icloud", "address": "test@icloud.com", "password": "icloud-fixture",
    }).json()
    path = f"/mail/accounts/{account['id']}"
    assert client.post(path + "/sync").status_code == 200

    def message(uid):
        return path + f"/messages/35/{uid}"

    def mark(uid, kind, enabled=True, language="zh"):
        return client.put(message(uid) + "/marker", json={"kind": kind, "enabled": enabled, "language": language})

    def folder(name):
        return {row["uid"]: row for row in client.get(f"/mail/smart-folders/{name}/messages").json()["items"]}

    assert mark(10, "flag").status_code == 204
    assert mark(10, "pin").status_code == 204
    assert client.post(message(10) + "/read", json={}).status_code == 204
    assert folder("top5")[10]["seen"] == 1
    assert mark(11, "todo").status_code == 204
    assert mark(11, "todo").status_code == 204
    assert mark(12, "todo", language="en").status_code == 204
    snapshot = todo.snapshot(owner)
    assert [(item["title"], item["system_source"]) for item in snapshot["directories"]] == [("邮件", "mail")]
    tasks = {item["title"]: item for item in snapshot["tasks"]}
    assert set(tasks) == {"Message 11", "Message 12"}
    inbox = {item["uid"]: item for item in client.get("/mail/messages").json()["items"]}
    assert inbox[10]["flagged"] and inbox[11]["todo"] and inbox[13]["answered"]
    assert set(folder("answered")) == {10, 11, 12, 13}
    rows.clear()
    assert client.post(path + "/sync").status_code == 200
    monkeypatch.setattr(imap, "read_preview", lambda *args: pytest.fail("Retained messages should open offline"))
    assert set(folder("flagged")) == {10}
    assert set(folder("todo")) == {11, 12}
    assert set(folder("answered")) == {10, 11, 12}
    assert client.get(message(10)).json()["text"] == "<script>mail data</script>"
    assert client.get(message(11)).status_code == 200
    assert client.get(message(13)).status_code == 404
    caller[0] = replace(caller[0], installation_id="other")
    assert client.get(message(10)).status_code == 404
    assert folder("flagged") == {}
    caller[0] = replace(caller[0], installation_id=account.get("installation", RequestPrincipal.legacy_local().installation_id))
    todo.complete_linked_task(owner, tasks["Message 11"])
    assert set(folder("todo")) == {12}
    assert mark(12, "todo", False).status_code == 204
    assert todo.get(owner, tasks["Message 12"]["id"])["completed"]
    assert folder("todo") == {}
    assert set(folder("answered")) == {10}
    assert mark(10, "pin", False).status_code == 204
    assert folder("top5") == {}
    assert set(folder("flagged")) == {10}


def test_existing_retained_html_recovers_links_when_original_is_available(mail_fixture, monkeypatch):
    from ai2apps.mail.html_preview import passive_html

    client, _, _, _ = mail_fixture
    account = client.post("/mail/accounts", json={
        "provider": "icloud", "address": "test@icloud.com", "password": "fixture",
    }).json()
    path = f"/mail/accounts/{account['id']}"
    assert client.post(path + "/sync").status_code == 200
    message = path + "/messages/35/10"
    old = {"text": "Open", "html": "<span>Open</span>", "preview_status": "complete"}
    monkeypatch.setattr(imap, "read_preview", lambda *args: old)
    assert client.put(message + "/marker", json={"kind": "flag", "enabled": True}).status_code == 204

    def offline(*args):
        raise imap.MailError("connection_failed")

    monkeypatch.setattr(imap, "read_preview", offline)
    assert client.get(message).json()["html"] == old["html"]
    new = {**old, "html": passive_html('<a href="https://example.invalid/">Open</a>'), "html_links": True}
    monkeypatch.setattr(imap, "read_preview", lambda *args: new)
    assert client.get(message).json()["html"] == new["html"]
    monkeypatch.setattr(imap, "read_preview", lambda *args: pytest.fail("Updated snapshot should be reused"))
    assert client.get(message).json()["html"] == new["html"]


def test_analysis_reads_bounded_text_with_peek(monkeypatch):
    from contextlib import contextmanager

    class Client:
        def uid(self, command, uid, options):
            assert (command, uid, options) == ("FETCH", "10", "(UID BODY.PEEK[]<0.49152>)")
            content = b"Content-Type: text/plain; charset=utf-8\r\n\r\nInvoice is due tomorrow.\r\n"
            return "OK", [(b"1 (UID 10 BODY[]<0> {72}", content)]

    @contextmanager
    def inbox(account, credential):
        yield Client(), 1, 35

    monkeypatch.setattr(imap, "inbox", inbox)
    assert imap.analysis_texts({}, "fixture", 35, [10]) == {10: "Invoice is due tomorrow."}
    with pytest.raises(imap.MailError, match="inbox_changed"):
        imap.analysis_texts({}, "fixture", 36, [10])


def test_smart_folder_sender_filters_and_guidance(mail_fixture, monkeypatch):
    from ai2apps.mail.smart_folders import SmartFolders

    client, service, _, _ = mail_fixture
    account = client.post("/mail/accounts", json={
        "provider": "icloud", "address": "reader@icloud.com", "password": "fixture",
    }).json()
    monkeypatch.setattr(imap, "snapshot", lambda *args: (35, [
        (10, "Receipt", '"Familiar name" <blocked@shop.example>', "2026-11-13T10:00:00+00:00", 0, 0),
        (11, "Receipt", "sales@news.bulk.example", "2026-11-13T10:00:00+00:00", 0, 0),
        (12, "Receipt", '"bulk.example" <sales@notbulk.example>', "2026-11-13T10:00:00+00:00", 0, 0),
        (13, "Receipt", "sales@shop.example", "2026-11-13T10:00:00+00:00", 0, 0),
    ], False))
    assert client.post(f"/mail/accounts/{account['id']}/sync").status_code == 200
    monkeypatch.setattr("ai2apps.mail.smart_folders.resolve_task_model", lambda *args: "fixture")
    monkeypatch.setattr(SmartFolders, "_snippets", lambda *args: {})
    rule = {"name": "Receipts", "rule": "Include receipts", "guidance": "Count payment confirmations.",
            "excluded_senders": [" BLOCKED@shop.example ", "bulk.example"]}

    async def model(self, runtime, principal, system, payload, max_tokens):
        folder = next(folder for folder in payload["folders"] if folder["name"] == rule["name"])
        assert folder["guidance"] == rule["guidance"]
        assert "excluded_senders" not in folder
        if folder["id"] == "preview":
            assert {message["sender"] for message in payload["messages"]} == {
                '"bulk.example" <sales@notbulk.example>', "sales@shop.example",
            }
        # Deliberately return excluded matches to verify the backend drops them.
        return {"items": [{"index": message["index"], "matches": [{"id": folder["id"], "reason": "Receipt"}]}
                          for message in payload["messages"]]}

    monkeypatch.setattr(SmartFolders, "_model", model)
    preview = client.post("/mail/analysis/preview", json=rule).json()
    assert preview["analyzed"] == 4
    assert {item["uid"] for item in preview["items"]} == {12, 13}
    folder = client.post("/mail/smart-folders", json=rule).json()
    assert folder["excluded_senders"] == ["blocked@shop.example", "bulk.example"]
    path = f"/mail/smart-folders/{folder['id']}"
    assert client.post("/mail/analysis", json={}).status_code == 200
    assert {item["uid"] for item in client.get(path + "/messages").json()["items"]} == {12, 13}
    assert client.get("/mail/smart-folders/unread-counts").json()[folder["id"]] == 2
    assert len(client.get("/mail/messages").json()["items"]) == 4
    feedback = f"/mail/accounts/{account['id']}/messages/35/11/classification"
    assert client.post(feedback, json={"folder_id": folder["id"], "included": True}).status_code == 409
    assert client.put(path, json={**rule, "excluded_senders": ["https://bulk.example"], "revision": 1}).status_code == 422
    updated = client.put(path, json={"name": rule["name"], "rule": rule["rule"], "revision": 1}).json()
    assert updated["guidance"] == rule["guidance"]
    assert updated["excluded_senders"] == folder["excluded_senders"]


def test_block_sender_from_details_is_folder_scoped_and_reuses_priority(mail_fixture, monkeypatch, tmp_path):
    from ai2apps.mail.smart_folders import SmartFolders
    from ai2apps.todo.store import TodoStore

    client, service, _, caller = mail_fixture
    todo = TodoStore(tmp_path / "todo")
    service.markers.todo_store = lambda: todo
    account = client.post("/mail/accounts", json={
        "provider": "icloud", "address": "reader@icloud.com", "password": "fixture",
    }).json()
    senders = ["News <news@shop.example>", "billing@shop.example", "receipts@eu.shop.example", "other@example.net"]
    rows = [(uid, "Receipt", sender, "2026-11-13T10:00:00+00:00", 0, 1)
            for uid, sender in enumerate(senders, 10)]
    monkeypatch.setattr(imap, "snapshot", lambda *args: (35, rows, False))
    monkeypatch.setattr(imap, "read_preview", lambda *args: {"text": "Receipt", "preview_status": "complete"})
    monkeypatch.setattr("ai2apps.mail.smart_folders.resolve_task_model", lambda *args: "fixture")
    monkeypatch.setattr(SmartFolders, "_snippets", lambda *args: {})

    async def model(self, runtime, principal, system, payload, max_tokens):
        return {"items": [{"index": msg["index"], "priority": 1, "reason": "Receipt", "evidence": "Receipt",
                           "matches": [{"id": folder["id"], "reason": "Receipt"} for folder in payload["folders"]]}
                          for msg in payload["messages"]]}

    monkeypatch.setattr(SmartFolders, "_model", model)
    account_path = f"/mail/accounts/{account['id']}"
    assert client.post(account_path + "/sync").status_code == 200
    folder = client.post("/mail/smart-folders", json={"name": "Receipts", "rule": "Include receipts"}).json()
    assert client.post("/mail/analysis", json={}).status_code == 200

    def visible(folder_id):
        return {row["uid"] for row in client.get(f"/mail/smart-folders/{folder_id}/messages").json()["items"]}

    def block(uid, folder_id, kind, **options):
        path = f"{account_path}/messages/35/{uid}/block-sender"
        rule = {"folder_id": folder_id, "kind": kind}
        if options:
            return client.post(path, json={**rule, **options})
        preview = client.post(path, json={**rule, "preview": True})
        if preview.status_code != 200:
            return preview
        return client.post(path, json={**rule, "expected_sender": preview.json()["excluded_sender"]})

    assert block(10, folder["id"], "address", preview=True).json() == {"excluded_sender": "news@shop.example"}
    assert block(10, folder["id"], "address", preview=False).status_code == 409
    assert block(10, folder["id"], "address", expected_sender="different@shop.example").status_code == 409
    assert visible(folder["id"]) == {10, 11, 12, 13}
    assert block(10, folder["id"], "address").json() == {"excluded_sender": "news@shop.example"}
    assert visible(folder["id"]) == {11, 12, 13}
    assert visible("top5") == {10, 11, 12, 13}
    for kind in ("flag", "pin", "todo"):
        assert client.put(account_path + "/messages/35/11/marker",
                          json={"kind": kind, "enabled": True}).status_code == 204
    assert block(11, "top5", "domain").json() == {"excluded_sender": "shop.example"}
    assert visible("top5") == {13}
    assert visible("answered") == {10, 11, 12, 13}
    assert visible("flagged") == visible("todo") == {11}
    for special in ("drafts", "flagged", "todo"):
        assert block(11, special, "address").status_code == 404
    assert client.get("/mail/smart-folders/unread-counts").json()["top5"] == 1
    assert len(client.get("/mail/messages").json()["items"]) == 4
    assert block(11, "answered", "address").status_code == 200
    assert visible("answered") == {10, 12, 13}
    assert visible("flagged") == visible("todo") == {11}

    filters_path = "/mail/smart-folders/top5/sender-filters"
    filters = client.get(filters_path).json()
    assert filters["excluded_senders"] == ["shop.example"]
    assert block(11, "top5", "domain").status_code == 200
    assert client.get(filters_path).json() == filters
    assert client.put(filters_path, json={"excluded_senders": [], "revision": filters["revision"] - 1}).status_code == 409
    assert client.put(filters_path, json={**filters, "excluded_senders": []}).status_code == 204
    assert visible("top5") == {10, 11, 12, 13}
    assert client.post("/mail/analysis", json={}).json()["analyzed"] == 0
    caller[0] = replace(caller[0], installation_id="different-installation")
    assert block(10, "top5", "address").status_code == 404


def test_finance_upgrade_preserves_custom_folders_and_previous_revisions():
    import sqlite3

    from ai2apps.mail.smart_folders import PRESET_FOLDERS
    from ai2apps.storage.migrations import MIGRATIONS, apply_migrations

    with sqlite3.connect(":memory:") as db:
        apply_migrations(db, MIGRATIONS[:113])
        db.executemany("INSERT INTO mail_smart_folder_presets VALUES (?,'desktop','{}')",
                       [("zh",), ("en",), ("conflict",)])
        db.executemany("INSERT INTO mail_smart_folders VALUES (?,?,'desktop',?,?,?)", [
            ("preset-zh", "zh", "投资", "Old default", 1),
            ("preset-edited", "zh", "Investing", "Edited by user", 2),
            ("custom", "zh", "投资", "User folder", 1),
            ("preset-en", "en", "Investing", "Old default", 1),
            ("preset-conflict", "conflict", "投资", "Old default", 1),
            ("custom-finance", "conflict", "Finance", "User finance rule", 1),
        ])
        db.commit()
        apply_migrations(db)
        folders = {row[0]: row[1:] for row in db.execute("SELECT id,name,rule,revision FROM mail_smart_folders")}
        zh, en, zh_rule, en_rule = next(preset for preset in PRESET_FOLDERS if preset[0] == "财务")
        assert folders["preset-zh"] == (zh, zh_rule, 2)
        assert folders["preset-en"] == (en, en_rule, 2)
        assert folders["preset-edited"] == ("Investing", "Edited by user", 2)
        assert folders["custom"] == ("投资", "User folder", 1)
        assert folders["preset-conflict"] == ("投资", "Old default", 1)
        assert folders["custom-finance"] == ("Finance", "User finance rule", 1)
        history, = db.execute("SELECT finance_previous_folders FROM mail_smart_folder_presets WHERE owner='zh'").fetchone()
        assert json.loads(history) == {"preset-zh": 1, "preset-edited": 2, "custom": 1}
