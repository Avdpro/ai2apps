"""Persistent image Work for explicitly armed private chats."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from pathlib import Path

from anyio import from_thread
from starlette.concurrency import run_in_threadpool

from ai2apps.identity import IdentityRepository

from . import APP_ID, cli, proxy_workers
from .image_judgment import classify
from .weixin import ConnectorError

LOG = logging.getLogger(__name__)
SHARD = re.compile(r"message_[0-9]{1,6}\.db")
SERVER_ID = re.compile(r"-?[1-9][0-9]{0,18}")


def discover_shards(config, observed):
    result = cli.run(config, "databases", config["profile"], pid=observed["pid"])
    records = result.get("databases")
    if not isinstance(records, list):
        raise ConnectorError("comapps_image_shards_unavailable")
    opened = set()
    directory = None
    for record in records:
        path = Path(record.get("path", ""))
        if not SHARD.fullmatch(path.name):
            continue
        if path.parts[-4:-1] != (config["namespace"], "db_storage", "message"):
            raise ConnectorError("comapps_image_shard_changed")
        if directory is not None and directory != path.parent:
            raise ConnectorError("comapps_image_shard_changed")
        directory = path.parent
        opened.add(path.name)
    if not opened:
        raise ConnectorError("comapps_image_shards_unavailable")

    on_disk = {}
    try:
        for path in directory.iterdir():
            if SHARD.fullmatch(path.name):
                meta = path.stat(follow_symlinks=False)
                if path.is_symlink() or not path.is_file():
                    raise ConnectorError("comapps_image_shard_changed")
                on_disk[path.name] = [meta.st_dev, meta.st_ino]
    except OSError as error:
        raise ConnectorError("comapps_image_shards_unavailable") from error
    if opened != on_disk.keys() or len(opened) > 32:
        raise ConnectorError("comapps_image_shards_incomplete")
    return on_disk


def read_window(config, observed, target, shard, cursor):
    result = cli.run(
        config,
        "messages",
        config["profile"],
        chat=target,
        pid=observed["pid"],
        message_window=(shard, cursor),
    )
    rows = result.get("messages")
    if (
        result.get("user_name") != target
        or not isinstance(rows, list)
        or len(rows) > 30
    ):
        raise ConnectorError("wechat_cli_invalid_response")
    if not result.get("table_found") and rows:
        raise ConnectorError("wechat_cli_invalid_response")
    ids = set()
    for row in rows:
        local_id = row.get("local_id")
        if (
            type(local_id) is not int
            or local_id < cursor
            or local_id in ids
            or row.get("database_name") != shard
        ):
            raise ConnectorError("wechat_cli_invalid_response")
        ids.add(local_id)
    return sorted(rows, key=lambda row: row["local_id"])


def snapshot(config, target, checkpoints, activated):
    profile = config["profile"]
    observed = cli.run(config, "identity", profile)
    if observed["namespace"] != config["namespace"]:
        raise ConnectorError("wechat_cli_account_changed")
    shards = discover_shards(config, observed)
    if checkpoints is not None and not checkpoints.keys() <= shards.keys():
        raise ConnectorError("comapps_image_shard_changed")
    updated = {}
    images = []
    for shard, identity in sorted(shards.items()):
        old = (checkpoints or {}).get(shard)
        if old and old["identity"] != identity:
            raise ConnectorError("comapps_image_shard_changed")
        anchor = old["anchor"] if old else None
        if checkpoints is None:
            for _ in range(40):
                rows = read_window(
                    config, observed, target, shard, anchor[0] + 1 if anchor else 0
                )
                if rows:
                    anchor = [rows[-1]["local_id"], rows[-1].get("server_id")]
                if len(rows) < 30:
                    break
            else:
                raise ConnectorError("comapps_image_history_too_long")
        else:
            rows = read_window(
                config, observed, target, shard, anchor[0] if anchor else 0
            )
            if anchor:
                if (
                    not rows
                    or [rows[0]["local_id"], rows[0].get("server_id")] != anchor
                ):
                    raise ConnectorError("comapps_image_shard_changed")
                rows = rows[1:]
            for row in rows:
                if row.get("type") != 3 or row.get("from_user") != target:
                    continue
                created = row.get("created_at")
                server_id = row.get("server_id")
                if (
                    type(created) is not int
                    or not isinstance(server_id, str)
                    or not SERVER_ID.fullmatch(server_id)
                ):
                    raise ConnectorError("comapps_image_message_invalid")
                if created >= activated:
                    images.append(
                        {
                            "database": shard,
                            "local_id": row["local_id"],
                            "server_id": server_id,
                        }
                    )
            if rows:
                anchor = [rows[-1]["local_id"], rows[-1].get("server_id")]
        updated[shard] = {"identity": identity, "anchor": anchor}
    if cli.run(config, "identity", profile) != observed:
        raise ConnectorError("wechat_cli_account_changed")
    return updated, images


class ImageMonitor:
    def __init__(self, runtime, service):
        self.runtime = runtime
        self.service = service
        self.db = runtime.database
        self.runner = None
        self.stopping = False
        with self.db.transaction(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS comapps_image_monitors (
                scope TEXT PRIMARY KEY, actor TEXT NOT NULL, instance_id TEXT NOT NULL,
                workspace TEXT NOT NULL, worker_id TEXT NOT NULL, work_id TEXT NOT NULL,
                signature TEXT NOT NULL, activated INTEGER NOT NULL, checkpoints TEXT,
                status TEXT NOT NULL, error TEXT
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS comapps_image_events (
                scope TEXT NOT NULL, workspace TEXT NOT NULL, target TEXT NOT NULL,
                server_id TEXT NOT NULL, state TEXT NOT NULL,
                PRIMARY KEY(scope, workspace, target, server_id)
            )""")
            db.execute(
                "UPDATE comapps_image_events SET state='interrupted' WHERE state='processing'"
            )

    def start(self):
        self.runner = asyncio.create_task(self._run())
        LOG.info("ComApps image monitor loaded; source=%s", __file__)

    async def stop(self):
        self.stopping = True
        if self.runner:
            await self.runner

    def _saved(self, scope, args):
        config = self.service._load(scope, "cli")
        if (
            not config
            or config.get("profile") != "default"
            or self.service.proxy_account_key(config) != args["workspace"]
        ):
            raise ConnectorError("wechat_cli_account_changed")
        key = "proxy-workers-" + args["workspace"]
        data = self.service._load(scope, key) or {"entries": []}
        worker = next(
            (row for row in data["entries"] if row["id"] == args["worker_id"]), None
        )
        if not worker or worker["kind"] != "monitor" or worker["source"] != "session":
            raise ConnectorError("comapps_image_work_unavailable")
        target = worker["target"]["id"]
        work = next(
            (row for row in worker["works"] if row["id"] == args["work_id"]), None
        )
        if (
            not target.startswith("wxid_")
            or not work
            or not work["enabled"]
            or work["trigger"] != "image"
            or work["response"] != "answer"
            or not work["instruction"].strip()
        ):
            raise ConnectorError("comapps_image_work_unavailable")
        return config, key, data, target, json.dumps([target, work], sort_keys=True)

    def control(self, scope, principal, operation, args):
        with self.db.transaction(write=True) as db:
            row = db.execute(
                "SELECT * FROM comapps_image_monitors WHERE scope=?", (scope,)
            ).fetchone()
            matches = row and all(
                row[k] == args[k]
                for k in ("workspace", "worker_id", "work_id", "instance_id")
            )
            if operation == "cli-image-monitor-stop":
                if matches:
                    db.execute(
                        "DELETE FROM comapps_image_monitors WHERE scope=?", (scope,)
                    )
                return {"status": "off"}
            if operation == "cli-image-monitor-status":
                if not matches:
                    return {"status": "off"}
                data = (
                    self.service._load(scope, "proxy-workers-" + args["workspace"])
                    or {}
                )
                key = args["worker_id"] + ":" + args["work_id"]
                return {
                    "status": row["status"],
                    "error": row["error"],
                    "entries": data.get("image_test_logs", {}).get(key, []),
                }
            _, _, data, _, signature = self._saved(scope, args)
            if data.get("revision") != args["revision"]:
                raise ConnectorError("comapps_workers_conflict")
            if row:
                raise ConnectorError("comapps_image_monitor_already_active")
            db.execute(
                """INSERT INTO comapps_image_monitors
                   VALUES(?,?,?,?,?,?,?,?,NULL,'starting',NULL)""",
                (
                    scope,
                    principal.actor_user_id,
                    args["instance_id"],
                    args["workspace"],
                    args["worker_id"],
                    args["work_id"],
                    json.dumps([signature, secrets.token_hex(16)]),
                    int(time.time()) + 1,
                ),
            )
            return {"status": "starting"}

    async def _run(self):
        while not self.stopping:
            try:
                with self.db.transaction() as db:
                    rows = db.execute(
                        "SELECT * FROM comapps_image_monitors WHERE status != 'blocked'"
                    ).fetchall()
                for row in rows:
                    if not self.stopping:
                        await run_in_threadpool(self._tick, dict(row))
            except Exception:
                LOG.exception("ComApps image monitor cycle failed")
            await asyncio.sleep(3)

    def _principal(self, row):
        principal = IdentityRepository(self.db).principal_for(row["actor"])
        entry = self.runtime.extension_manager.instance_entry(
            row["instance_id"], principal=principal
        )
        if (
            not principal.is_core
            or self.service.owner_scope(principal) != row["scope"]
            or entry["source"] != "builtin"
            or entry["app_key"] != APP_ID
        ):
            raise ConnectorError("comapps_image_work_unavailable")
        return principal

    def _tick(self, row):
        scope = row["scope"]
        try:
            with self.service.claim(scope):
                with self.db.transaction() as db:
                    current = db.execute(
                        "SELECT * FROM comapps_image_monitors WHERE scope=?", (scope,)
                    ).fetchone()
                if current is None or dict(current) != row:
                    return
                principal = self._principal(row)
                config, key, data, target, signature = self._saved(scope, row)
                if signature != json.loads(row["signature"])[0]:
                    raise ConnectorError("comapps_image_work_changed")
                previous = (
                    json.loads(row["checkpoints"]) if row["checkpoints"] else None
                )
                checkpoints, images = snapshot(
                    config, target, previous, row["activated"]
                )
                for image in images:
                    if self.stopping:
                        return
                    if not self._handle(
                        row, principal, config, key, data, target, image
                    ):
                        return
                self._status(row, "watching", checkpoints=json.dumps(checkpoints))
        except ConnectorError as error:
            reason = str(error)
            if reason == "comapps_busy":
                return
            status = (
                "blocked"
                if reason
                in {
                    "comapps_image_shard_changed",
                    "comapps_image_work_changed",
                    "comapps_image_work_unavailable",
                    "wechat_cli_account_changed",
                }
                else "waiting"
            )
            self._status(row, status, reason)
        except (PermissionError, RuntimeError, ValueError):
            self._status(row, "blocked", "comapps_image_work_unavailable")

    def _status(self, row, status, error=None, checkpoints=None):
        with self.db.transaction(write=True) as db:
            db.execute(
                """UPDATE comapps_image_monitors SET status=?,error=?,
                   checkpoints=COALESCE(?,checkpoints)
                   WHERE scope=? AND signature=? AND worker_id=? AND work_id=?""",
                (
                    status,
                    error,
                    checkpoints,
                    row["scope"],
                    row["signature"],
                    row["worker_id"],
                    row["work_id"],
                ),
            )

    def _check_active(self, row):
        self._principal(row)
        with self.db.transaction() as db:
            active = db.execute(
                "SELECT 1 FROM comapps_image_monitors WHERE scope=? AND signature=?",
                (row["scope"], row["signature"]),
            ).fetchone()
        if not active or self.stopping:
            raise ConnectorError("comapps_image_monitor_stopped")

    def _handle(self, row, principal, config, key, data, target, image):
        identity = (row["scope"], row["workspace"], target, image["server_id"])
        with self.db.transaction(write=True) as db:
            claimed = db.execute(
                "INSERT OR IGNORE INTO comapps_image_events VALUES(?,?,?,?,'processing')",
                identity,
            )
            if not claimed.rowcount:
                return True

        async def judge(content, mime, instruction):
            async with asyncio.timeout(90):
                return await classify(
                    self.runtime,
                    principal,
                    row["instance_id"],
                    row["worker_id"],
                    content,
                    mime,
                    instruction,
                )

        result = proxy_workers.test_image(
            self.service,
            row["scope"],
            key,
            data,
            config,
            {
                **image,
                "worker_id": row["worker_id"],
                "work_id": row["work_id"],
                "variant": "large",
                "auto": True,
                "judge": lambda content, mime, instruction: from_thread.run(
                    judge, content, mime, instruction
                ),
                "before_send": lambda: self._check_active(row),
            },
        )["entry"]
        retryable = result.get("error") in {
            "wechat_cli_cache_missing",
            "wechat_cli_profile_busy",
        }
        attempts = sum(
            entry["server_id"] == image["server_id"]
            and entry.get("error") == result.get("error")
            for entry in data["image_test_logs"][
                row["worker_id"] + ":" + row["work_id"]
            ]
        )
        if retryable and attempts < 3:
            with self.db.transaction(write=True) as db:
                db.execute(
                    "DELETE FROM comapps_image_events WHERE scope=? AND workspace=? AND target=? AND server_id=?",
                    identity,
                )
            return False
        with self.db.transaction(write=True) as db:
            db.execute(
                """UPDATE comapps_image_events SET state=? WHERE
                   scope=? AND workspace=? AND target=? AND server_id=?""",
                (
                    result.get("delivery")
                    or ("judged" if result.get("judgment") else "unprocessed"),
                    *identity,
                ),
            )
        return True
