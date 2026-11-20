"""Saved settings for the ComApps proxy workspace."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal
from urllib.parse import urlsplit

from PIL import Image
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from . import cli
from .cli import TARGET_PATTERN
from .media import IMAGE_LIMIT, validate
from .weixin import ConnectorError

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
Key = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]


class Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Target(Settings):
    id: str = Field(pattern=f"^{TARGET_PATTERN}$")
    label: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)
    ]


class Work(Settings):
    id: Key
    trigger: Literal["all", "image", "mention", "prefix", "schedule", "request", "recall"]
    match: str = Field(max_length=120)
    response: Literal["warn", "moderate", "answer", "publish", "recall"]
    instruction: str = Field(max_length=1000)
    enabled: bool

    @model_validator(mode="after")
    def check_match(self):
        if self.trigger in {"prefix", "schedule"} and not self.match.strip():
            raise ValueError("trigger needs a value")
        if (self.trigger == "recall") != (self.response == "recall"):
            raise ValueError("invalid recall monitor")
        return self


class Monitor(Settings):
    id: Key
    kind: Literal["monitor"]
    name: Title
    source: Literal["session", "requests"]
    target: Target | None
    works: list[Work] = Field(max_length=8)

    @model_validator(mode="after")
    def check_source(self):
        if (self.source == "session") != (self.target is not None):
            raise ValueError("invalid work target")
        if len({work.id for work in self.works}) != len(self.works):
            raise ValueError("duplicate work")
        if any(
            (work.trigger == "request") != (self.source == "requests")
            and work.trigger != "schedule"
            for work in self.works
        ):
            raise ValueError("trigger does not match work target")
        return self


class Content(Settings):
    kind: Literal["text", "image", "video", "link"]
    value: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1800)
    ]

    @field_validator("value")
    @classmethod
    def no_control_characters(cls, value):
        if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("invalid content")
        return value

    @model_validator(mode="after")
    def check_media(self):
        if self.kind != "text":
            url = urlsplit(self.value)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username is not None
            ):
                raise ValueError("media must be an HTTP or HTTPS URL")
            if any(char.isspace() for char in self.value):
                raise ValueError("invalid URL")
        return self


class Audience(Settings):
    id: Key
    kind: Literal["audience"]
    name: Title
    targets: list[Target] = Field(max_length=30)

    @field_validator("targets")
    @classmethod
    def unique_targets(cls, targets):
        if len({target.id for target in targets}) != len(targets):
            raise ValueError("duplicate target")
        return targets


class Broadcast(Audience):
    kind: Literal["broadcast"]
    content: list[Content] = Field(max_length=4)
    interval: int = Field(ge=5, le=3600)


Entry = Annotated[Monitor | Broadcast | Audience, Field(discriminator="kind")]


def workspace(service, scope, operation, args):
    config = service._load(scope, "cli")
    if not config or not config.get("profile") or not config.get("namespace"):
        raise ConnectorError("wechat_cli_not_bound")
    account = service.proxy_account_key(config)
    key = "proxy-workers-" + account
    data = service._load(scope, key) or {"revision": 0, "entries": []}
    if operation == "cli-workers":
        return {**data, "workspace": account}
    if args["workspace"] != account:
        raise ConnectorError("comapps_workers_conflict")
    if operation == "cli-worker-image-test":
        return test_image(service, scope, key, data, config, args)
    if data["revision"] != args["revision"]:
        raise ConnectorError("comapps_workers_conflict")

    entries = data["entries"]
    if operation == "cli-worker-save":
        entry = args["worker"]
        previous = next((row for row in entries if row["id"] == entry["id"]), None)
        if previous and previous["kind"] != entry["kind"]:
            raise ConnectorError("comapps_worker_kind_changed")
        if previous is None and len(entries) >= 24:
            raise ConnectorError("comapps_workers_limit")
        entry["updated_at"] = datetime.now(UTC).isoformat()
        if previous is None:
            entries.append(entry)
        else:
            entries[entries.index(previous)] = entry
    else:
        data["entries"] = [row for row in entries if row["id"] != args["worker_id"]]
    work_keys = {
        row["id"] + ":" + work["id"]
        for row in data["entries"]
        if row["kind"] == "monitor"
        for work in row["works"]
    }
    if "image_test_logs" in data:
        data["image_test_logs"] = {
            key: logs
            for key, logs in data["image_test_logs"].items()
            if key in work_keys
        }
    data["revision"] += 1
    service._store(scope, key, data)
    return {**data, "workspace": account}


def test_image(service, scope, key, data, config, args):
    worker = next(
        (row for row in data["entries"] if row["id"] == args["worker_id"]), None
    )
    if not worker or worker["kind"] != "monitor" or worker["source"] != "session":
        raise ConnectorError("comapps_image_work_unavailable")
    work = next((row for row in worker["works"] if row["id"] == args["work_id"]), None)
    target = worker["target"]["id"]
    if (
        not work
        or work["trigger"] != "image"
        or config["profile"] != "default"
        or not target.startswith("wxid_")
    ):
        raise ConnectorError("comapps_image_work_unavailable")
    if args.get("watch"):
        if not work["enabled"] or not args.get("judge"):
            raise ConnectorError("comapps_image_work_unavailable")
        args = {
            **args,
            **wait_for_image(
                config,
                target,
                args["database"],
                args.get("local_id"),
                args.get("server_id"),
            ),
            "variant": "large",
        }
    identity = {name: args[name] for name in ("database", "local_id", "server_id")}
    if not -(2**63) <= int(identity["server_id"]) < 2**63:
        raise ConnectorError("comapps_image_message_invalid")
    judge = args.get("judge")
    if judge and (work["response"] != "answer" or not work["instruction"].strip()):
        raise ConnectorError("comapps_image_work_unavailable")
    work_key = worker["id"] + ":" + work["id"]
    variant = args.get("variant", "thumbnail")
    entry = {
        "at": datetime.now(UTC).isoformat(),
        **identity,
        "variant": variant,
        "state": "unread",
    }
    try:
        observed = cli.run(config, "identity", config["profile"])
        if observed["namespace"] != config["namespace"]:
            raise ConnectorError("wechat_cli_account_changed")
        with TemporaryDirectory(prefix="comapps-image-test-") as folder:
            output = Path(folder) / "image"
            receipt = cli.run(
                config,
                "image-read",
                config["profile"],
                chat=target,
                pid=observed["pid"],
                image_identity=identity,
                image_variant=variant,
                destination=output,
            )
            expected = {
                **identity,
                "namespace": config["namespace"],
                "chat": target,
                "file": str(output),
                "variant": variant,
            }
            if any(receipt.get(name) != value for name, value in expected.items()):
                raise ConnectorError("comapps_image_receipt_mismatch")
            if output.is_symlink() or not output.is_file():
                raise ConnectorError("comapps_image_receipt_mismatch")
            with output.open("rb") as stream:
                content = stream.read(IMAGE_LIMIT + 1)
            _, mime = validate(content, "image")
            with Image.open(BytesIO(content), formats=("JPEG", "PNG")) as image:
                image.load()
                width, height = image.size
            if (width, height, len(content), hashlib.sha256(content).hexdigest()) != (
                receipt.get("width"),
                receipt.get("height"),
                receipt.get("bytes"),
                receipt.get("sha256"),
            ) or mime != "image/" + str(receipt.get("format")):
                raise ConnectorError("comapps_image_receipt_mismatch")
        if cli.run(config, "identity", config["profile"]) != observed:
            raise ConnectorError("wechat_cli_account_changed")
    except ConnectorError as error:
        entry["error"] = str(error)
    except (OSError, ValueError):
        entry["error"] = "comapps_image_invalid"
    else:
        entry.update(
            state=f"{variant}_read",
            format=receipt["format"],
            width=width,
            height=height,
            bytes=len(content),
        )

    if judge and entry["state"] != "unread":
        try:
            answer, model = judge(content, mime, work["instruction"])
        except ConnectorError as error:
            entry["judgment_error"] = str(error)
        except Exception:
            entry["judgment_error"] = "comapps_image_model_failed"
        else:
            entry.update(judgment=answer, model=model)

    if args.get("watch"):
        previous = next(
            (
                row
                for row in data.get("image_test_logs", {}).get(work_key, [])
                if row["server_id"] == identity["server_id"] and row.get("delivery")
            ),
            None,
        )
        if previous:
            return {"entry": previous}

    logs = data.setdefault("image_test_logs", {})
    logs[work_key] = [entry, *logs.get(work_key, [])][:5]
    service._store(scope, key, data)
    if (args.get("watch") or args.get("auto")) and entry.get("judgment"):
        request_id = (
            "comapps-"
            + hashlib.sha256(
                f"{scope}:{key}:{work_key}:{identity['server_id']}".encode()
            ).hexdigest()[:48]
        )
        entry["delivery"] = "unknown"
        service._store(scope, key, data)
        try:
            if args.get("before_send"):
                args["before_send"]()
            entry["delivery"] = send_judgment(
                config, target, request_id, entry["judgment"]
            )
        except ConnectorError as error:
            entry["delivery_error"] = str(error)
        service._store(scope, key, data)
    return {"entry": entry}


def wait_for_image(config, target, database, local_id=None, server_id=None):
    profile = config["profile"]
    observed = cli.run(config, "identity", profile)
    if observed["namespace"] != config["namespace"]:
        raise ConnectorError("wechat_cli_account_changed")

    def read(cursor):
        result = cli.run(
            config,
            "messages",
            profile,
            chat=target,
            pid=observed["pid"],
            message_window=(database, cursor),
        )
        if result.get("user_name") != target or result.get("table_found") is not True:
            raise ConnectorError("comapps_image_shard_unavailable")
        rows = result.get("messages")
        if not isinstance(rows, list):
            raise ConnectorError("wechat_cli_invalid_response")
        seen = set()
        for row in rows:
            local_id = row.get("local_id")
            if (
                type(local_id) is not int
                or local_id < cursor
                or local_id in seen
                or row.get("database_name") != database
            ):
                raise ConnectorError("wechat_cli_invalid_response")
            seen.add(local_id)
        return sorted(rows, key=lambda row: row["local_id"])

    if local_id is not None:
        rows = read(local_id)
        if not rows or (rows[0]["local_id"], rows[0]["server_id"]) != (
            local_id,
            server_id,
        ):
            raise ConnectorError("comapps_image_shard_changed")
        anchor = rows[0]
    else:
        cursor = 0
        anchor = None
        for _ in range(40):
            rows = read(cursor)
            if rows:
                anchor = rows[-1]
                cursor = anchor["local_id"] + 1
            if len(rows) < 30:
                break
        else:
            raise ConnectorError("comapps_image_history_too_long")
    if anchor is None or not anchor.get("server_id") or anchor["server_id"] == "0":
        raise ConnectorError("comapps_image_shard_unavailable")
    logging.getLogger(__name__).info(
        "ComApps single-image test waiting at current shard tail"
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        rows = read(anchor["local_id"])
        if (
            not rows
            or rows[0]["local_id"] != anchor["local_id"]
            or rows[0]["server_id"] != anchor["server_id"]
        ):
            raise ConnectorError("comapps_image_shard_changed")
        for row in rows[1:]:
            if row.get("type") == 3 and row.get("from_user") == target:
                if cli.run(config, "identity", profile) != observed:
                    raise ConnectorError("wechat_cli_account_changed")
                server_id = row.get("server_id")
                if (
                    not isinstance(server_id, str)
                    or not server_id.lstrip("-").isdigit()
                    or server_id == "0"
                ):
                    raise ConnectorError("comapps_image_message_invalid")
                return {
                    "database": database,
                    "local_id": row["local_id"],
                    "server_id": server_id,
                }
        anchor = rows[-1]
        time.sleep(3)
    raise ConnectorError("comapps_image_watch_timeout")


def send_judgment(config, target, request_id, answer):
    profile = config["profile"]
    observed = cli.run(config, "identity", profile)
    if observed["namespace"] != config["namespace"]:
        raise ConnectorError("wechat_cli_account_changed")
    pending = cli.run(
        config, "reply-enqueue", profile, chat=target, reply=(request_id, answer)
    )
    if pending.get("id") != request_id or pending.get("recipient") != target:
        raise ConnectorError("wechat_cli_invalid_response")
    result = cli.run(config, "reply-dispatch", profile, reply=request_id)
    request = result.get("request") or {}
    if request.get("id") != request_id or request.get("recipient") != target:
        raise ConnectorError("wechat_cli_invalid_response")
    state = request.get("state")
    if state == "sent":
        receipt = request.get("receipt") or {}
        if (
            receipt.get("outcome") != "native_result_success"
            or receipt.get("native_state_retired") is not True
        ):
            return "unknown"
    return (
        state
        if state in {"queued", "sent", "failed", "rejected", "expired", "cancelled"}
        else "unknown"
    )
