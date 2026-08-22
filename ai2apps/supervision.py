"""Helper-supervised Local startup contract."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

_INSTANCE_ID = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?$")
_PROCESS_BOOT_ID = uuid4()


class SupervisionContractError(RuntimeError):
    pass


def current_supervision_boot_id(environ: dict[str, str] | None = None) -> UUID:
    environment = os.environ if environ is None else environ
    value = environment.get("AI2APPS_BOOT_ID")
    if value is None:
        return _PROCESS_BOOT_ID
    try:
        return UUID(value)
    except ValueError as error:
        raise SupervisionContractError("Invalid AI2APPS_BOOT_ID") from error


def current_supervised_instance_id(
    *,
    fallback: str,
    environ: dict[str, str] | None = None,
) -> str:
    environment = os.environ if environ is None else environ
    value = environment.get("AI2APPS_INSTANCE_ID", fallback)
    if not _INSTANCE_ID.fullmatch(value) or ".." in value:
        raise SupervisionContractError("Invalid AI2APPS_INSTANCE_ID")
    return value


def write_supervised_run_descriptor(
    *,
    actual_port: int,
    configured_port: int | None,
    runtime_version: str,
    base_path: str | Path,
    environ: dict[str, str] | None = None,
) -> Path | None:
    environment = os.environ if environ is None else environ
    if environment.get("AI2APPS_SUPERVISED") != "helper":
        return None

    instance_id = current_supervised_instance_id(fallback="", environ=environment)
    boot_id = str(current_supervision_boot_id(environment))
    if not 1024 <= actual_port <= 65535:
        raise SupervisionContractError("Actual port must be between 1024 and 65535")
    if configured_port is not None and not 1024 <= configured_port <= 65535:
        raise SupervisionContractError("Configured port must be between 1024 and 65535")
    if not runtime_version.strip():
        raise SupervisionContractError("Runtime version is required")

    instance_root = Path(base_path).expanduser().resolve().parent
    expected_path = (instance_root / "run" / "local.json").resolve()
    supplied_path = Path(environment.get("AI2APPS_RUN_DESCRIPTOR_PATH", "")).expanduser().resolve()
    if supplied_path != expected_path:
        raise SupervisionContractError("Run descriptor path does not match the instance root")

    payload = {
        "schema_version": 1,
        "instance_id": instance_id,
        "pid": os.getpid(),
        "configured_port": configured_port,
        "actual_port": actual_port,
        "boot_id": boot_id,
        "runtime_version": runtime_version,
        "started_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    expected_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(expected_path.parent, 0o700)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=expected_path.parent,
            prefix=".local.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            os.fchmod(temporary.fileno(), 0o600)
            json.dump(payload, temporary, separators=(",", ":"), sort_keys=True)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, expected_path)
        temporary_path = None
        directory_fd = os.open(expected_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            Path(temporary_path).unlink(missing_ok=True)
    return expected_path
