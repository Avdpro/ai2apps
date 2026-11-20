"""Owner-scoped WeChat recall monitoring and local Work history."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import time
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from starlette.concurrency import run_in_threadpool

from ai2apps.identity import IdentityRepository

from . import APP_ID, cli
from .media import IMAGE_LIMIT
from .proxy_monitor import SERVER_ID, discover_shards
from .weixin import ConnectorError

LOG = logging.getLogger(__name__)


def preview(config, observed, target, identity):
    if config["profile"] != "default" or not target.startswith("wxid_"):
        return None
    try:
        with TemporaryDirectory(prefix="comapps-recall-") as folder:
            output = Path(folder) / "preview"
            receipt = cli.run(
                config, "image-read", config["profile"], chat=target,
                pid=observed["pid"], image_identity=identity, destination=output,
            )
            expected = {
                **identity, "namespace": config["namespace"], "chat": target,
                "file": str(output), "variant": "thumbnail",
            }
            if any(receipt.get(key) != value for key, value in expected.items()):
                return None
            if output.is_symlink() or not output.is_file():
                return None
            with output.open("rb") as stream:
                content = stream.read(IMAGE_LIMIT + 1)
            if len(content) > IMAGE_LIMIT:
                return None
            with Image.open(BytesIO(content), formats=("JPEG", "PNG")) as image:
                if image.width * image.height > 4_000_000:
                    return None
                image.thumbnail((256, 256))
                encoded = BytesIO()
                image.convert("RGB").save(encoded, format="JPEG", quality=75)
            return "data:image/jpeg;base64," + base64.b64encode(encoded.getvalue()).decode("ascii")
    except (ConnectorError, OSError, ValueError, Image.DecompressionBombError):
        return None


class RecallMonitor:
    def __init__(self, runtime, service):
        self.runtime = runtime
        self.service = service
        self.db = runtime.database
        self.root = self.db.path.parent / "comapps-recall"
        self.runner = None
        self.stopping = False
        with self.db.transaction(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS comapps_recall_monitors (
                scope TEXT NOT NULL, workspace TEXT NOT NULL, worker_id TEXT NOT NULL,
                work_id TEXT NOT NULL, actor TEXT NOT NULL, instance_id TEXT NOT NULL,
                target TEXT NOT NULL, generation TEXT NOT NULL, status TEXT NOT NULL,
                error TEXT, checkpoints TEXT NOT NULL DEFAULT '{}',
                previews TEXT NOT NULL DEFAULT '{}', entries TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY(scope, workspace, worker_id, work_id)
            )""")

    def start(self):
        self.runner = asyncio.create_task(self._run())
        LOG.info("ComApps recall monitor loaded; source=%s", __file__)

    async def stop(self):
        self.stopping = True
        if self.runner:
            await self.runner

    @staticmethod
    def _key(row):
        return tuple(row[field] for field in ("scope", "workspace", "worker_id", "work_id"))

    def sync(self, scope, principal, args, workers):
        """Reconcile monitors when the owner saves or removes a Worker."""
        workspace = args["workspace"]
        worker_id = args.get("worker_id") or args["worker"]["id"]
        worker = next((item for item in workers if item["id"] == worker_id), None)
        works = {}
        target = None
        if worker and worker["kind"] == "monitor" and worker["source"] == "session":
            target = worker["target"]["id"]
            works = {work["id"]: work["enabled"] for work in worker["works"]
                     if work["trigger"] == "recall"}
        retired = []
        with self.db.transaction(write=True) as db:
            existing = db.execute(
                "SELECT * FROM comapps_recall_monitors WHERE scope=? AND workspace=? AND worker_id=?",
                (scope, workspace, worker_id),
            ).fetchall()
            for row in existing:
                work_id = row["work_id"]
                if work_id not in works or row["target"] != target:
                    db.execute(
                        "DELETE FROM comapps_recall_monitors WHERE scope=? AND workspace=? AND worker_id=? AND work_id=?",
                        self._key(row),
                    )
                    retired.append(row["generation"])
                    continue
                enabled = works.pop(work_id)
                if (enabled and row["status"] in {"off", "blocked"}
                        or not enabled and row["status"] != "off"):
                    db.execute(
                        """UPDATE comapps_recall_monitors SET status=?, error=NULL,
                           generation=?, checkpoints='{}', previews='{}', instance_id=?
                           WHERE scope=? AND workspace=? AND worker_id=? AND work_id=?""",
                        ("starting" if enabled else "off", secrets.token_hex(16),
                         args["instance_id"], *self._key(row)),
                    )
                    retired.append(row["generation"])
            for work_id, enabled in works.items():
                db.execute(
                    """INSERT INTO comapps_recall_monitors
                       (scope,workspace,worker_id,work_id,actor,instance_id,target,generation,status)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (scope, workspace, worker_id, work_id, principal.actor_user_id,
                     args["instance_id"], target, secrets.token_hex(16),
                     "starting" if enabled else "off"),
                )
        for generation in retired:
            for suffix in ("", "-journal", "-wal", "-shm"):
                try:
                    (self.root / (generation + ".sqlite3" + suffix)).unlink(missing_ok=True)
                except OSError:
                    LOG.warning("Unable to remove retired ComApps recall state")

    def status(self, scope, args):
        config = self.service._load(scope, "cli")
        if (not config or not config.get("profile")
                or self.service.proxy_account_key(config) != args["workspace"]):
            raise ConnectorError("wechat_cli_account_changed")
        with self.db.transaction() as db:
            row = db.execute(
                """SELECT status,error,entries FROM comapps_recall_monitors WHERE
                   scope=? AND workspace=? AND worker_id=? AND work_id=? AND instance_id=?""",
                (*self._key({**args, "scope": scope}), args["instance_id"]),
            ).fetchone()
        if not row:
            return {"status": "off", "entries": []}
        return {"status": row["status"], "error": row["error"], "entries": json.loads(row["entries"])}

    async def _run(self):
        while not self.stopping:
            try:
                with self.db.transaction() as db:
                    rows = db.execute(
                        "SELECT * FROM comapps_recall_monitors WHERE status NOT IN ('off','blocked')"
                    ).fetchall()
                for row in rows:
                    if self.stopping:
                        break
                    await run_in_threadpool(self._tick, dict(row))
            except Exception:
                LOG.exception("ComApps recall monitor cycle failed")
            await asyncio.sleep(3)

    def _binding(self, row):
        principal = IdentityRepository(self.db).principal_for(row["actor"])
        entry = self.runtime.extension_manager.instance_entry(row["instance_id"], principal=principal)
        config = self.service._load(row["scope"], "cli")
        if (not principal.is_core or self.service.owner_scope(principal) != row["scope"]
                or entry["source"] != "builtin" or entry["app_key"] != APP_ID
                or not config or not config.get("profile")
                or self.service.proxy_account_key(config) != row["workspace"]):
            raise ConnectorError("wechat_cli_account_changed")
        data = self.service._load(row["scope"], "proxy-workers-" + row["workspace"]) or {}
        worker = next((w for w in data.get("entries", []) if w["id"] == row["worker_id"]), None)
        if (not worker or worker["kind"] != "monitor" or worker["source"] != "session"
                or worker["target"]["id"] != row["target"] or not any(
                    w["id"] == row["work_id"] and w["trigger"] == "recall" and w["enabled"]
                    for w in worker["works"])):
            raise ConnectorError("comapps_recall_work_changed")
        return config

    def _tick(self, row):
        try:
            with self.service.claim(row["scope"]):
                with self.db.transaction() as db:
                    current = db.execute(
                        """SELECT * FROM comapps_recall_monitors WHERE
                           scope=? AND workspace=? AND worker_id=? AND work_id=?""",
                        self._key(row),
                    ).fetchone()
                if not current or dict(current) != row:
                    return
                config = self._binding(row)
                self._poll(row, config)
        except ConnectorError as error:
            reason = str(error)
            if reason != "comapps_busy":
                status = "blocked" if reason in {
                    "wechat_cli_account_changed", "comapps_recall_work_changed",
                    "comapps_image_shard_changed", "comapps_recall_state_missing",
                } else "waiting"
                self._update(row, status, reason)
        except (PermissionError, RuntimeError, ValueError):
            self._update(row, "blocked", "comapps_recall_work_unavailable")

    def _update(self, row, status, error=None):
        with self.db.transaction(write=True) as db:
            db.execute(
                """UPDATE comapps_recall_monitors SET status=?,error=?,checkpoints=?,previews=?,entries=?
                   WHERE scope=? AND workspace=? AND worker_id=? AND work_id=? AND generation=?""",
                (status, error, row["checkpoints"], row["previews"], row["entries"],
                 *self._key(row), row["generation"]),
            )

    def _poll(self, row, config):
        profile = config["profile"]
        target = row["target"]
        observed = cli.run(config, "identity", profile)
        if observed["namespace"] != config["namespace"]:
            raise ConnectorError("wechat_cli_account_changed")
        shards = discover_shards(config, observed)
        checkpoints = json.loads(row["checkpoints"])
        previews = json.loads(row["previews"])
        entries = json.loads(row["entries"])
        if any(shards.get(shard) != record["identity"] for shard, record in checkpoints.items()):
            raise ConnectorError("comapps_image_shard_changed")
        self.root.mkdir(mode=0o700, exist_ok=True)
        if self.root.is_symlink() or self.root.stat().st_mode & 0o077:
            raise ConnectorError("comapps_recall_work_unavailable")
        state = self.root / (row["generation"] + ".sqlite3")
        if checkpoints and not state.is_file():
            raise ConnectorError("comapps_recall_state_missing")

        def call(operation, identity, **kwargs):
            return cli.run(config, operation, profile, chat=target, pid=observed["pid"],
                           image_identity=identity, event_state=state, **kwargs)

        names = None
        for shard, identity in sorted(shards.items()):
            if self.stopping:
                return
            previous = checkpoints.get(shard)
            if not previous:
                window = cli.run(config, "messages", profile, chat=target,
                                 pid=observed["pid"], message_window=(shard, 0))
                if window.get("user_name") != target or type(window.get("table_found")) is not bool:
                    raise ConnectorError("wechat_cli_invalid_response")
                if not window["table_found"]:
                    continue
            cursor = previous["cursor"] if previous else 0
            result = call("message-events", {"database": shard}, after_event=cursor)
            events = result.get("events")
            if not isinstance(events, list) or len(events) > 20:
                raise ConnectorError("wechat_cli_invalid_response")
            for event in events:
                event_id = event.get("event_id")
                if (type(event_id) is not int or not cursor < event_id < 2**63
                        or event.get("profile") != profile or event.get("namespace") != config["namespace"]
                        or event.get("chat") != target or event.get("database") != shard):
                    raise ConnectorError("wechat_cli_invalid_response")
                cursor = event_id
                local_id, server_id = event.get("local_id"), event.get("server_id")
                if (type(local_id) is not int or not 0 < local_id < 2**53
                        or not isinstance(server_id, str) or not SERVER_ID.fullmatch(server_id)):
                    continue
                message_id = {"database": shard, "local_id": local_id, "server_id": server_id}
                preview_key = shard + ":" + str(local_id) + ":" + server_id
                if event.get("event") == "message_new":
                    message = event.get("message") or {}
                    if message.get("type") == 3:
                        image = preview(config, observed, target, message_id)
                        if image:
                            previews[preview_key] = image
                            if len(previews) > 100:
                                previews.pop(next(iter(previews)))
                elif event.get("event") == "message_recalled":
                    image = previews.pop(preview_key, None)
                    original = call("message-original", message_id).get("original") if event.get("original_available") else None
                    if original and (original.get("local_id"), original.get("server_id"),
                                     original.get("database_name")) != (local_id, server_id, shard):
                        raise ConnectorError("wechat_cli_invalid_response")
                    record = self._record(event, message_id, original, image)
                    if target.endswith("@chatroom"):
                        member_ids = (record["revoker_id"], record["sender_id"])
                        if any(member_ids) and names is None:
                            names = self._contact_names(config, observed)
                        for field, member_id in zip(("revoker_name", "sender_name"), member_ids):
                            record[field] = (names or {}).get(member_id)
                    entries = sorted([record, *entries], key=lambda item: item["at"], reverse=True)[:20]
                else:
                    raise ConnectorError("wechat_cli_invalid_response")
            checkpoints[shard] = {"identity": identity, "cursor": cursor}
            if cli.run(config, "identity", profile) != observed:
                raise ConnectorError("wechat_cli_account_changed")
            row.update(checkpoints=json.dumps(checkpoints), previews=json.dumps(previews),
                       entries=json.dumps(entries, ensure_ascii=False))
            self._update(row, "watching")
        self._update(row, "watching" if checkpoints else "waiting")

    @staticmethod
    def _contact_names(config, observed):
        try:
            result = cli.run(config, "friends", config["profile"],
                             pid=observed["pid"], full_directory=True)
        except ConnectorError:
            return {}
        rows = result.get("friends")
        if not isinstance(rows, list):
            return {}
        names = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            user = member_id(row.get("user_name"))
            if not user:
                continue
            for key in ("remark", "nickname", "alias"):
                label = row.get(key)
                if isinstance(label, str) and label.strip():
                    names[user] = label.strip()[:180]
                    break
        return names

    @staticmethod
    def _record(event, identity, original, image):
        now = int(time.time())
        revoked = event.get("revoke_time")
        if type(revoked) is int and revoked >= 1_000_000_000_000:
            revoked //= 1000
        if type(revoked) is not int or not 0 < revoked <= now + 300:
            revoked = None
        original = original or {}
        kind = {1: "text", 3: "image"}.get(original.get("type"))
        text = original.get("raw_content")
        return {
            **identity, "at": revoked or now, "revoke_time": revoked,
            "revoker_id": member_id(event.get("revoker_id")),
            "sender_id": member_id(original.get("from_user")),
            "kind": "image" if image else kind,
            "text": text[:16000] if kind == "text" and isinstance(text, str) else None,
            "image": image,
        }


def member_id(value):
    if isinstance(value, str) and cli.TARGET.fullmatch(value) and not value.endswith("@chatroom"):
        return value
    return None
