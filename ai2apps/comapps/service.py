"""Instance-local WeChat binding state and connector operations."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from unicodedata import normalize

from . import cli, proxy_workers
from .weixin import BASE, ConnectorError, ILink, qr_png, trusted_base


def record_activity(config, direction, text, *, delivery=None):
    """Store bounded display data alongside the owning iLink binding."""
    entry = {"direction": direction, "text": text[:500], "at": int(time.time())}
    if delivery:
        entry["delivery"] = delivery
    config["activity"] = [*config.get("activity", [])[-11:], entry]


def delivery_status(error):
    return {
        "ilink_reconnect_required": "reconnect",
        "ilink_request_rejected": "rejected",
    }.get(str(error), "unknown")


@dataclass
class Login:
    id: str
    code: str
    deadline: float
    base: str = BASE


class ComApps:
    def __init__(self, vault, ilink=None):
        self.vault = vault
        self.ilink = ilink or ILink()
        self._logins = {}
        self._running = set()
        self._lock = Lock()
        self.bot_channel = None
        self.proxy_monitor = None
        self.recall_monitor = None

    @staticmethod
    def owner_scope(principal):
        return hashlib.sha256(
            json.dumps([principal.installation_id, principal.actor_user_id]).encode()
        ).hexdigest()

    def invoke(self, principal, operation, **arguments):
        scope = self.owner_scope(principal)
        # The app opens from saved snapshots and must not wait for a connector poll.
        if operation in {"state", "cli-workers"}:
            return self._invoke(scope, operation, arguments)
        if operation == "cli-recall-status":
            if self.recall_monitor is None:
                raise ConnectorError("comapps_recall_work_unavailable")
            return self.recall_monitor.status(scope, arguments)
        if operation in {"cli-image-monitor-status", "cli-image-monitor-stop"}:
            if self.proxy_monitor is None:
                raise ConnectorError("comapps_image_monitor_unavailable")
            return self.proxy_monitor.control(scope, principal, operation, arguments)
        with self.claim(scope):
            if operation == "cli-image-monitor-start":
                if self.proxy_monitor is None:
                    raise ConnectorError("comapps_image_monitor_unavailable")
                return self.proxy_monitor.control(
                    scope, principal, operation, arguments
                )
            if operation in {"ilink-auto-enable", "ilink-auto-disable"}:
                if self.bot_channel is None:
                    raise ConnectorError("ilink_auto_unavailable")
                config = self._load(scope, "ilink")
                if not config:
                    raise ConnectorError("ilink_not_bound")
                if operation == "ilink-auto-enable":
                    if not config.get("auto_generation"):
                        self.bot_channel.enable(
                            scope, principal, arguments["instance_id"], config
                        )
                else:
                    self.bot_channel.disable(scope)
                    config.pop("auto_generation", None)
                    config.pop("pending", None)
                    config.pop("access_jobs", None)
                    config.pop("flash_jobs", None)
                    config.pop("staged_media", None)
                    config.pop("bot_menu_choices", None)
                    config.pop("conversation_bot", None)
                    self._store(scope, "ilink", config)
                return self._invoke(scope, "state", {})
            result = self._invoke(scope, operation, arguments)
            if (self.recall_monitor is not None
                    and operation in {"cli-worker-save", "cli-worker-delete"}
                    and "instance_id" in arguments):
                self.recall_monitor.sync(scope, principal, arguments, result["entries"])
            return result

    @contextmanager
    def claim(self, scope):
        with self._lock:
            if scope in self._running:
                raise ConnectorError("comapps_busy")
            self._running.add(scope)
        try:
            yield
        finally:
            with self._lock:
                self._running.remove(scope)

    def _load(self, scope, kind):
        try:
            return json.loads(self.vault.load(f"comapps-v1/{scope}/{kind}"))
        except KeyError:
            return None

    def _store(self, scope, kind, config):
        self.vault.store(f"comapps-v1/{scope}/{kind}", json.dumps(config))

    @staticmethod
    def proxy_account_key(config):
        identity = [config["profile"], config["namespace"]]
        return hashlib.sha256(json.dumps(identity).encode()).hexdigest()

    def _invoke(self, scope, operation, args):
        if operation in {
            "cli-workers",
            "cli-worker-save",
            "cli-worker-delete",
            "cli-worker-image-test",
        }:
            return proxy_workers.workspace(self, scope, operation, args)
        if operation == "state":
            ilink = self._load(scope, "ilink")
            config = self._load(scope, "cli")
            return {
                "ilink_bound": ilink is not None,
                "ilink_signed_out": ilink is None
                and self._load(scope, "ilink-avatar") is not None,
                "ilink_auto": bool(ilink and ilink.get("auto_generation")),
                "ilink_delivery": ilink.get("delivery") if ilink else None,
                "ilink_checked_at": ilink.get("checked_at") if ilink else None,
                "ilink_activity": ilink.get("activity", []) if ilink else [],
                "cli_path": config["path"] if config else None,
                "cli_profile": config.get("profile") if config else None,
                "cli_workspace": self.proxy_account_key(config)
                if config and config.get("profile") and config.get("namespace")
                else None,
            }
        if operation in {"ilink-start", "ilink-poll", "ilink-inbox", "ilink-reply"}:
            config = self._load(scope, "ilink")
            if config and config.get("auto_generation"):
                raise ConnectorError("ilink_auto_active")
        if operation == "ilink-start":
            result = self.ilink.request(
                "get_bot_qrcode", query={"bot_type": "3"}, data={"local_token_list": []}
            )
            code = result.get("qrcode")
            if not isinstance(code, str) or not 1 <= len(code) <= 2048:
                raise ConnectorError("ilink_invalid_qr")
            png = qr_png(result.get("qrcode_img_content"))
            login = Login(secrets.token_urlsafe(18), code, time.monotonic() + 300)
            with self._lock:
                self._logins = {
                    k: v
                    for k, v in self._logins.items()
                    if v.deadline > time.monotonic()
                }
                self._logins[scope] = login
            return {"login_id": login.id, "qr": png}
        if operation == "ilink-poll":
            login = self._logins.get(scope)
            if (
                login is None
                or args["login_id"] != login.id
                or time.monotonic() >= login.deadline
            ):
                raise ConnectorError("ilink_qr_expired")
            query = {"qrcode": login.code}
            if args.get("verify_code"):
                query["verify_code"] = args["verify_code"]
            result = self.ilink.request(
                "get_qrcode_status", base=login.base, query=query, timeout=38
            )
            status = result.get("status")
            if status == "scaned_but_redirect":
                login.base = trusted_base(
                    "https://" + str(result.get("redirect_host", ""))
                )
                status = "scaned"
            if status == "confirmed":
                fields = [
                    result.get(name)
                    for name in ("bot_token", "ilink_bot_id", "ilink_user_id")
                ]
                if any(
                    not isinstance(item, str)
                    or not 1 <= len(item) <= 1024
                    or any(char.isspace() for char in item)
                    or not item.isascii()
                    for item in fields
                ):
                    raise ConnectorError("ilink_incomplete_binding")
                token, bot, user = fields
                self._store(
                    scope,
                    "ilink",
                    {
                        "token": token,
                        "bot": bot,
                        "user": user,
                        "base": trusted_base(result.get("baseurl") or BASE),
                        "cursor": "",
                        "message": None,
                        "reply": None,
                        "seen": [],
                        "checked_at": int(time.time()),
                    },
                )
                if self._load(scope, "ilink-avatar") is not None:
                    self.vault.delete(f"comapps-v1/{scope}/ilink-avatar")
                self._logins.pop(scope, None)
            elif status in ("expired", "verify_code_blocked", "binded_redirect"):
                self._logins.pop(scope, None)
            elif status not in (
                "wait",
                "scaned",
                "need_verifycode",
                "confirmed_but_need_verifycode",
            ):
                raise ConnectorError("ilink_invalid_response")
            return {"status": status}
        if operation in {"ilink-logoff", "ilink-disconnect"}:
            bound = self._load(scope, "ilink") is not None
            if operation == "ilink-logoff" and bound:
                self._store(scope, "ilink-avatar", {})
            if self.bot_channel is not None:
                self.bot_channel.disable(scope)
            self._logins.pop(scope, None)
            if bound:
                self.vault.delete(f"comapps-v1/{scope}/ilink")
            if (
                operation == "ilink-disconnect"
                and self._load(scope, "ilink-avatar") is not None
            ):
                self.vault.delete(f"comapps-v1/{scope}/ilink-avatar")
            return {}
        if operation == "ilink-reply":
            config = self._load(scope, "ilink")
            reply = config.get("reply") if config else None
            if not reply or args["reply_id"] != reply["id"] or not args["text"].strip():
                raise ConnectorError("ilink_reply_unavailable")
            # Claim before contacting WeChat. Unknown outcomes must never retry.
            config["reply"] = None
            self._store(scope, "ilink", config)
            delivery = "submitted"
            try:
                self.send_reply(config, self.reply_payload(config, reply, args["text"]))
            except ConnectorError as error:
                delivery = delivery_status(error)
                raise
            finally:
                config["delivery"] = delivery
                record_activity(config, "out", args["text"], delivery=delivery)
                self._store(scope, "ilink", config)
            return {"status": "submitted"}
        if operation == "ilink-inbox":
            config = self._load(scope, "ilink")
            if config is None:
                raise ConnectorError("ilink_not_bound")
            try:
                result = self.ilink.request(
                    "getupdates",
                    base=config["base"],
                    token=config["token"],
                    data={"get_updates_buf": config["cursor"]},
                    timeout=48,
                )
            except ConnectorError as error:
                if str(error) == "ilink_reconnect_required":
                    config["delivery"] = "reconnect"
                    self._store(scope, "ilink", config)
                raise
            batch = result.get("msgs", [])
            if not isinstance(batch, list):
                raise ConnectorError("ilink_invalid_response")
            for message in batch:
                if not isinstance(message, dict):
                    continue
                if (
                    message.get("message_type") != 1
                    or message.get("from_user_id") != config["user"]
                    or message.get("to_user_id") not in (None, "", config["bot"])
                    or message.get("group_id")
                ):
                    continue
                items = message.get("item_list")
                if not isinstance(items, list):
                    continue
                lines = []
                for item in items[:16]:
                    if not isinstance(item, dict) or item.get("type") != 1:
                        continue
                    text = item.get("text_item")
                    if isinstance(text, dict) and isinstance(text.get("text"), str):
                        lines.append(text["text"][:2000])
                if lines:
                    message_id = message.get("message_id")
                    if (
                        type(message_id) not in (int, str)
                        or not 1 <= len(str(message_id)) <= 20
                        or not str(message_id).isdigit()
                    ):
                        continue
                    message_id = str(message_id)
                    if message_id in config["seen"]:
                        continue
                    config["seen"] = [*config["seen"][-127:], message_id]
                    config["message"] = "\n".join(lines)[:2000]
                    record_activity(config, "in", config["message"])
                    token = message.get("context_token")
                    config["reply"] = (
                        {"id": secrets.token_urlsafe(18), "token": token}
                        if isinstance(token, str) and 0 < len(token) <= 4096
                        else None
                    )
            cursor = result.get("get_updates_buf")
            if isinstance(cursor, str) and cursor:
                if len(cursor) > 8192:
                    raise ConnectorError("ilink_invalid_response")
                config["cursor"] = cursor
            config["checked_at"] = int(time.time())
            self._store(scope, "ilink", config)
            return {
                "message": config["message"],
                "reply_id": config["reply"]["id"] if config["reply"] else None,
            }
        if operation == "cli-configure":
            path, digest = cli.executable(args["path"])
            config = {"path": str(path), "sha256": digest}
            if args["path"] != str(path):
                raise ConnectorError("wechat_cli_enter_resolved_path")
            profiles = self._profiles(config)
            self._store(scope, "cli", config)
            return {"profiles": profiles}
        config = self._load(scope, "cli")
        if config is None:
            raise ConnectorError("wechat_cli_not_configured")
        if operation == "cli-profiles":
            return {"profiles": self._profiles(config)}
        if operation == "cli-profile-create":
            profile = args["profile"]
            result = cli.run(config, "profile-create", profile)
            return {"profile": profile, "created": result["created"]}
        if operation == "cli-profile-launch":
            result = cli.run(config, "launch", args["profile"])
            if result.get("started") is not True and result.get("running") is not True:
                raise ConnectorError("wechat_cli_invalid_response")
            return {"profile": args["profile"]}
        if operation == "cli-disconnect":
            self.vault.delete(f"comapps-v1/{scope}/cli")
            return {}
        if operation == "cli-bind":
            profile = args["profile"]
            identity = cli.run(config, "identity", profile)
            self._store(
                scope,
                "cli",
                {**config, "profile": profile, "namespace": identity["namespace"]},
            )
            return {"profile": profile}
        profile = config.get("profile")
        if not profile:
            raise ConnectorError("wechat_cli_not_bound")
        name = operation.removeprefix("cli-")
        if name == "search" and args["workspace"] != self.proxy_account_key(config):
            raise ConnectorError("wechat_cli_account_changed")
        observed = cli.run(config, "identity", profile)
        if observed["namespace"] != config["namespace"]:
            raise ConnectorError("wechat_cli_account_changed")
        if name == "search":
            result = self._search_cli(config, profile, observed["pid"], args)
        else:
            result = cli.run(
                config, name, profile, args.get("chat"), pid=observed["pid"]
            )
        if cli.run(config, "identity", profile) != observed:
            raise ConnectorError("wechat_cli_account_changed")
        if name == "search":
            return result
        fields = {
            "friends": ("user_name", "nickname", "remark"),
            "groups": ("user_name", "nickname", "remark"),
            "conversations": ("user_name", "unread_count", "summary"),
            "messages": ("from_user", "raw_content", "created_at"),
        }
        rows = result.get(name)
        if not isinstance(rows, list):
            raise ConnectorError("wechat_cli_invalid_response")
        return {
            "items": [
                self._project(row, fields[name])
                for row in rows[:100]
                if isinstance(row, dict)
            ],
            "partial": bool(
                result.get("truncated")
                or result.get("possibly_more")
                or len(rows) > 100
            ),
        }

    @staticmethod
    def _search_cli(config, profile, pid, args):
        directory = args["directory"]
        sources = ("conversations", "friends", "groups")
        if directory != "all":
            sources = (directory,)
        query = normalize("NFKC", args["query"]).strip().casefold()
        found = {}
        incomplete = False
        for source in sources:
            result = cli.run(config, source, profile, pid=pid, full_directory=True)
            rows = result.get(source)
            if not isinstance(rows, list):
                raise ConnectorError("wechat_cli_invalid_response")
            incomplete |= bool(result.get("truncated") or result.get("possibly_more"))
            for row in rows:
                if not isinstance(row, dict):
                    continue
                user = row.get("user_name")
                if not isinstance(user, str) or not cli.TARGET.fullmatch(user):
                    continue
                entry = found.setdefault(user, {})
                for key in ("remark", "nickname", "alias"):
                    value = row.get(key)
                    if isinstance(value, str) and (value := value.strip()[:180]):
                        entry.setdefault(key, value)

        matches = []
        for user, names in found.items():
            label = (
                names.get("remark")
                or names.get("nickname")
                or names.get("alias")
                or user
            )
            values = [
                normalize("NFKC", term).casefold() for term in (user, *names.values())
            ]
            if not query or query in values:
                rank = 0
            elif any(value.startswith(query) for value in values):
                rank = 1
            elif any(query in value for value in values):
                rank = 2
            else:
                continue
            matches.append((rank, {"id": user, "label": label}))
        matches.sort(key=lambda match: match[0])
        return {
            "items": [item for _, item in matches[:100]],
            "more": len(matches) > 100,
            "incomplete": incomplete,
        }

    @staticmethod
    def reply_payload(config, reply, text):
        return {
            "msg": {
                "from_user_id": "",
                "to_user_id": config["user"],
                "client_id": reply["id"],
                "message_type": 2,
                "message_state": 2,
                "context_token": reply["token"],
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            }
        }

    def send_reply(self, config, payload):
        try:
            result = self.ilink.request(
                "sendmessage", base=config["base"], token=config["token"], data=payload
            )
            if result.get("ret") != 0 and not result.get("message_id"):
                raise ConnectorError("ilink_invalid_response")
        except ConnectorError as error:
            if str(error) not in {"ilink_request_rejected", "ilink_reconnect_required"}:
                raise ConnectorError("ilink_send_unknown") from None
            raise

    @staticmethod
    def _project(row, fields):
        return {
            k: v[:2000] if isinstance(v, str) else v
            for k in fields
            if isinstance(v := row.get(k), (str, int))
        }

    @classmethod
    def _profiles(cls, config):
        values = cli.run(config, "profiles").get("profiles")
        if not isinstance(values, list):
            raise ConnectorError("wechat_cli_invalid_response")
        return [
            cls._project(row, ("name", "display_name"))
            for row in values[:50]
            if isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and cli.PROFILE.fullmatch(row["name"])
        ]
