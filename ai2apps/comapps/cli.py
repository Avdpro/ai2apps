"""Fixed read-only commands against an explicitly configured local wechat-agent."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path

from .weixin import ConnectorError

PROFILE = re.compile(r"[a-z][a-z0-9-]{0,31}")
TARGET_PATTERN = r"[A-Za-z0-9_@.][A-Za-z0-9_@.\-]{0,179}"
TARGET = re.compile(TARGET_PATTERN)
OUTPUT_LIMIT = 2 * 1024 * 1024
DIRECTORY_OUTPUT_LIMIT = 16 * 1024 * 1024


def executable(path):
    try:
        selected = Path(path)
        if not selected.is_absolute() or selected.name != "wechat-agent":
            raise ValueError
        resolved = selected.resolve(strict=True)
        metadata = resolved.stat()
        if (
            resolved.name != "wechat-agent"
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_mode & 0o022
            or not os.access(resolved, os.X_OK)
            or metadata.st_size > 32 * 1024 * 1024
        ):
            raise ValueError
        return resolved, hashlib.sha256(resolved.read_bytes()).hexdigest()
    except (OSError, ValueError, RuntimeError) as error:
        raise ConnectorError("wechat_cli_invalid_path") from error


def run(
    config,
    operation,
    profile=None,
    chat=None,
    pid=None,
    *,
    full_directory=False,
    image_identity=None,
    image_variant="thumbnail",
    destination=None,
    message_window=None,
    reply=None,
    event_state=None,
    after_event=0,
    latest=False,
):
    path, digest = executable(config["path"])
    if digest != config["sha256"]:
        raise ConnectorError("wechat_cli_changed_reconfigure")
    if operation == "profiles":
        args = ["profile", "list"]
    elif operation == "profile-create":
        if (
            not isinstance(profile, str)
            or not PROFILE.fullmatch(profile)
            or profile == "default"
        ):
            raise ConnectorError("wechat_cli_invalid_profile")
        args = ["profile", "create", profile]
    else:
        if not isinstance(profile, str) or not PROFILE.fullmatch(profile):
            raise ConnectorError("wechat_cli_invalid_profile")
        args = ["--profile", profile, "--timeout", "12"]
        if pid is not None:
            args.extend(["--pid", str(pid)])
        if operation == "identity":
            args.extend(["queue", "identity"])
        elif operation in {"message-events", "message-original"}:
            args.extend([
                operation, "--chat", chat, "--namespace", config["namespace"],
                "--database", image_identity["database"], "--state", str(event_state),
            ])
            if operation == "message-events":
                args.extend(["--cache-originals", "--after-event", str(after_event), "--limit", "20"])
            else:
                args.extend(["--local-id", str(image_identity["local_id"]),
                             "--server-id=" + image_identity["server_id"]])
        elif operation == "image-read":
            args.extend(
                [
                    operation,
                    "--namespace",
                    config["namespace"],
                    "--chat",
                    chat,
                    "--database",
                    image_identity["database"],
                    "--local-id",
                    str(image_identity["local_id"]),
                    "--server-id=" + image_identity["server_id"],
                    "--variant",
                    image_variant,
                    "--file",
                    str(destination),
                ]
            )
        elif operation == "reply-enqueue":
            request_id, answer = reply
            if answer not in {"是", "否"} or not TARGET.fullmatch(chat):
                raise ConnectorError("wechat_cli_operation_unavailable")
            args.extend(
                [
                    "send",
                    "--to",
                    chat,
                    "--text",
                    answer,
                    "--request-id",
                    request_id,
                    "--ttl",
                    "60",
                    "--execute",
                ]
            )
        elif operation == "reply-dispatch":
            args.extend(["queue", "run", "--request-id", reply, "--execute"])
        elif operation in {
            "launch",
            "status",
            "friends",
            "groups",
            "conversations",
            "databases",
        }:
            args.append(operation)
        elif (
            operation == "messages"
            and isinstance(chat, str)
            and re.fullmatch(r"[A-Za-z0-9_@.\-]{1,180}", chat)
            and not chat.startswith("-")
        ):
            args.extend(["messages", "--chat", chat, "--limit", "30"])
            if latest:
                args.append("--latest")
            if message_window:
                database, cursor = message_window
                args.extend(["--database", database, "--cursor", str(cursor)])
        else:
            raise ConnectorError("wechat_cli_operation_unavailable")
    limit = DIRECTORY_OUTPUT_LIMIT if full_directory else OUTPUT_LIMIT
    command_path = "/usr/bin:/bin:/usr/sbin:/sbin"
    if operation == "image-read" and image_variant == "large":
        command_path += ":/opt/homebrew/bin:/usr/local/bin"
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                [str(path), *args],
                cwd=path.parent,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.DEVNULL,
                timeout={"profile-create": 180, "image-read": 60}.get(operation, 16),
                check=False,
                env={
                    "HOME": str(Path.home()),
                    "PATH": command_path,
                    "LANG": "en_US.UTF-8",
                },
            )
            output.seek(0)
            raw = output.read(limit + 1)
        if len(raw) > limit:
            raise ConnectorError("wechat_cli_response_too_large")
        value = json.loads(raw)
    except subprocess.TimeoutExpired as error:
        raise ConnectorError("wechat_cli_timeout") from error
    except (OSError, ValueError) as error:
        raise ConnectorError("wechat_cli_request_failed") from error
    if not isinstance(value, dict) or result.returncode or value.get("ok") is not True:
        code = value.get("error") if isinstance(value, dict) else None
        code = code.get("code") if isinstance(code, dict) else None
        allowed = {
            "profile_not_found",
            "profile_mismatch",
            "profile_busy",
            "source_changed",
            "copy_changed",
            "core_changed",
            "attach_denied",
            "request_timeout",
            "account_unbound",
            "account_mismatch",
            "cache_missing",
            "decoder_unavailable",
            "decode_failed",
            "unsupported_wxgf",
            "image_too_large",
            "invalid_image",
            "message_mismatch",
            "unsupported_build",
            "unsupported_profile",
            "launch_failed",
            "other_wechat_running",
        }
        raise ConnectorError(
            f"wechat_cli_{code}" if code in allowed else "wechat_cli_request_failed"
        )
    body = value.get("result")
    if not isinstance(body, dict):
        raise ConnectorError("wechat_cli_invalid_response")
    if operation == "identity":
        if (
            body.get("profile") != profile
            or not isinstance(body.get("namespace"), str)
            or type(body.get("pid")) is not int
            or body["pid"] < 1
        ):
            raise ConnectorError("wechat_cli_identity_unavailable")
    elif operation == "profile-create":
        if body.get("name") != profile or type(body.get("created")) is not bool:
            raise ConnectorError("wechat_cli_invalid_response")
    elif operation not in {"profiles", "reply-dispatch"}:
        target = body.get("target_profile")
        if not isinstance(target, dict) or target.get("name") != profile:
            raise ConnectorError("wechat_cli_profile_mismatch")
    return body
