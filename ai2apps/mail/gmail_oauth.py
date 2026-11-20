"""Google desktop authorization for the Mail-owned Gmail transport."""

import base64
from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import sys
from threading import Event, Lock, Thread
from time import monotonic
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser

import httpx

from .imap import MailError

MAIL_SCOPE = "https://mail.google.com/"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
CALLBACK_PATH = "/gmail-oauth"
FLOW_SECONDS = 300


def _open_browser(url):
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", url], check=True, timeout=8, capture_output=True)
    elif not webbrowser.open(url):
        raise OSError("System browser unavailable")


@dataclass(frozen=True)
class _Client:
    client_id: str
    client_secret: str = field(repr=False)


@dataclass
class _Flow:
    owner: tuple
    account_id: str | None
    credential_key: str = field(repr=False)
    client: _Client
    state: str = field(repr=False)
    verifier: str = field(repr=False)
    deadline: float
    redirect: str = ""
    callback: Event = field(default_factory=Event, repr=False)
    stop: Event = field(default_factory=Event, repr=False)
    code: str = field(default="", repr=False)
    error: str = ""


class _Callback(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(2)
        super().setup()

    def log_message(self, *args):
        # The callback URL contains an authorization code.
        pass

    def do_GET(self):
        flow = self.server.flow
        try:
            url = urlsplit(self.path)
            params = parse_qs(url.query, max_num_fields=20)
        except ValueError:
            self._reply(400, "Invalid authorization response.")
            return
        if (self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}"
                or url.path != CALLBACK_PATH or flow.stop.is_set()
                or monotonic() >= flow.deadline or flow.callback.is_set()
                or not secrets.compare_digest(params.get("state", [""])[0].encode(), flow.state.encode())):
            self._reply(400, "Invalid or expired authorization response.")
            return
        code = params.get("code", [""])[0]
        if params.get("error"):
            flow.error = "gmail_oauth_denied"
        elif 0 < len(code) <= 2048 and code.isascii():
            flow.code = code
        else:
            self._reply(400, "Invalid authorization response.")
            return
        flow.callback.set()
        self._reply(200, "Return to AI2Apps Mail to finish connecting your Gmail account.")

    def _reply(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(message.encode())


class GmailOAuth:
    def __init__(self, client_path: Path):
        self.client_path = client_path
        self._flows = {}
        self._lock = Lock()

    def _client(self):
        try:
            with self.client_path.open("rb") as stream:
                data = stream.read(8193)
            if len(data) > 8192:
                raise ValueError
            installed = json.loads(data)["installed"]
            client = _Client(installed["client_id"], installed.get("client_secret", ""))
            if (not isinstance(client.client_id, str)
                    or not client.client_id.endswith(".apps.googleusercontent.com")
                    or not isinstance(client.client_secret, str)):
                raise ValueError
            return client
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise MailError("gmail_oauth_unconfigured") from None

    @staticmethod
    def _listen(server, flow):
        with server:
            while not flow.stop.is_set() and not flow.callback.is_set() and monotonic() < flow.deadline:
                server.handle_request()

    def start(self, owner, account_id=None, credential_key=""):
        client = self._client()
        flow_id = secrets.token_urlsafe(24)
        flow = _Flow(owner, account_id, credential_key, client, secrets.token_urlsafe(32),
                     secrets.token_urlsafe(48), monotonic() + FLOW_SECONDS)
        with self._lock:
            for key, pending in list(self._flows.items()):
                if monotonic() >= pending.deadline or pending.owner == owner:
                    pending.stop.set()
                    del self._flows[key]
            if len(self._flows) >= 8:
                raise MailError("mail_busy")
            try:
                server = HTTPServer(("127.0.0.1", 0), _Callback)
            except OSError:
                raise MailError("gmail_oauth_browser_failed") from None
            server.timeout = 0.5
            server.flow = flow
            flow.redirect = f"http://127.0.0.1:{server.server_port}{CALLBACK_PATH}"
            self._flows[flow_id] = flow
        challenge = base64.urlsafe_b64encode(hashlib.sha256(flow.verifier.encode()).digest()).decode().rstrip("=")
        url = AUTH_URL + "?" + urlencode({
            "client_id": client.client_id, "redirect_uri": flow.redirect,
            "response_type": "code", "scope": f"openid email {MAIL_SCOPE}",
            "state": flow.state, "code_challenge": challenge, "code_challenge_method": "S256",
            "access_type": "offline", "prompt": "consent select_account",
        })
        Thread(target=self._listen, args=(server, flow), daemon=True).start()
        try:
            _open_browser(url)
        except (OSError, subprocess.SubprocessError):
            self.cancel(owner, flow_id)
            raise MailError("gmail_oauth_browser_failed") from None
        return {"flow_id": flow_id}

    def cancel(self, owner, flow_id):
        with self._lock:
            flow = self._flows.get(flow_id)
            if flow is not None and flow.owner == owner:
                flow.stop.set()
                del self._flows[flow_id]

    def claim(self, owner, flow_id):
        with self._lock:
            flow = self._flows.get(flow_id)
            if flow is None or flow.owner != owner:
                raise KeyError(flow_id)
            expired = monotonic() >= flow.deadline
            if not expired and not flow.callback.is_set():
                return None
            del self._flows[flow_id]
            flow.stop.set()
        if expired:
            raise MailError("gmail_oauth_expired")
        if flow.error:
            raise MailError(flow.error)
        return flow

    @staticmethod
    def _request(method, url, **kwargs):
        try:
            with httpx.Client(timeout=8, follow_redirects=False) as http:
                response = http.request(method, url, **kwargs)
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise MailError("gmail_oauth_unavailable") from None
        if not isinstance(data, dict):
            raise MailError("gmail_oauth_unavailable")
        if response.status_code == 400 and data.get("error") == "invalid_grant":
            raise MailError("authentication_failed")
        if response.status_code != 200:
            raise MailError("gmail_oauth_unavailable")
        return data

    def _token(self, client, **grant):
        payload = {"client_id": client.client_id, **grant}
        if client.client_secret:
            payload["client_secret"] = client.client_secret
        token = self._request("POST", TOKEN_URL, data=payload)
        if "scope" in token and MAIL_SCOPE not in str(token["scope"]).split():
            raise MailError("gmail_oauth_scope_missing")
        access = token.get("access_token")
        if (not isinstance(access, str) or not access or not all(33 <= ord(c) <= 126 for c in access)
                or str(token.get("token_type")).lower() != "bearer"):
            raise MailError("gmail_oauth_unavailable")
        return token

    def exchange(self, flow):
        token = self._token(flow.client, grant_type="authorization_code", code=flow.code,
                            redirect_uri=flow.redirect, code_verifier=flow.verifier)
        if MAIL_SCOPE not in str(token.get("scope", "")).split():
            raise MailError("gmail_oauth_scope_missing")
        refresh = token.get("refresh_token")
        if not isinstance(refresh, str) or not refresh:
            raise MailError("gmail_oauth_unavailable")
        profile = self._request("GET", USERINFO_URL, headers={"Authorization": "Bearer " + token["access_token"]})
        address = profile.get("email")
        if profile.get("email_verified") is not True or not isinstance(address, str):
            raise MailError("gmail_oauth_unavailable")
        return address, refresh, token["access_token"]

    def refresh(self, credential):
        return self._token(self._client(), grant_type="refresh_token", refresh_token=credential)["access_token"]
