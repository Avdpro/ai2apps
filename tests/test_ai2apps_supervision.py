from __future__ import annotations

import json
import os
from argparse import Namespace
from pathlib import Path
from uuid import uuid4

import pytest

from ai2apps.supervision import SupervisionContractError, write_supervised_run_descriptor
from omlx.settings import GlobalSettings


def supervision_environment(instance_root: Path) -> dict[str, str]:
    return {
        "AI2APPS_SUPERVISED": "helper",
        "AI2APPS_INSTANCE_ID": "customer-a",
        "AI2APPS_BOOT_ID": str(uuid4()),
        "AI2APPS_RUN_DESCRIPTOR_PATH": str(instance_root / "run" / "local.json"),
    }


def test_writer_emits_owner_only_atomic_descriptor(tmp_path: Path) -> None:
    base_path = tmp_path / "customer-a" / "data"
    environment = supervision_environment(base_path.parent)
    path = write_supervised_run_descriptor(
        actual_port=49_152,
        configured_port=None,
        runtime_version="1.0.0",
        base_path=base_path,
        environ=environment,
    )

    assert path == base_path.parent / "run" / "local.json"
    assert path is not None
    payload = json.loads(path.read_text())
    assert payload["instance_id"] == "customer-a"
    assert payload["actual_port"] == 49_152
    assert payload["configured_port"] is None
    assert payload["pid"] == os.getpid()
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_writer_rejects_descriptor_outside_instance_root(tmp_path: Path) -> None:
    base_path = tmp_path / "customer-a" / "data"
    environment = supervision_environment(base_path.parent)
    environment["AI2APPS_RUN_DESCRIPTOR_PATH"] = str(tmp_path / "customer-b" / "run" / "local.json")

    with pytest.raises(SupervisionContractError, match="instance root"):
        write_supervised_run_descriptor(
            actual_port=49_152,
            configured_port=None,
            runtime_version="1.0.0",
            base_path=base_path,
            environ=environment,
        )


def test_writer_is_noop_without_helper_supervision(tmp_path: Path) -> None:
    result = write_supervised_run_descriptor(
        actual_port=49_152,
        configured_port=None,
        runtime_version="1.0.0",
        base_path=tmp_path / "data",
        environ={},
    )
    assert result is None


def test_writer_rejects_invalid_instance_identity(tmp_path: Path) -> None:
    base_path = tmp_path / "customer-a" / "data"
    environment = supervision_environment(base_path.parent)
    environment["AI2APPS_INSTANCE_ID"] = "../customer-b"
    with pytest.raises(SupervisionContractError, match="INSTANCE_ID"):
        write_supervised_run_descriptor(
            actual_port=49_152,
            configured_port=None,
            runtime_version="1.0.0",
            base_path=base_path,
            environ=environment,
        )


def test_port_zero_is_only_valid_for_loopback_helper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = GlobalSettings(base_path=tmp_path)
    settings.server.port = 0
    assert any("Invalid port" in error for error in settings.validate())

    monkeypatch.setenv("AI2APPS_SUPERVISED", "helper")
    assert not any("port" in error.lower() for error in settings.validate())

    settings.server.host = "0.0.0.0"
    assert any("Automatic port" in error for error in settings.validate())


def test_transient_port_zero_is_not_persisted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI2APPS_SUPERVISED", "helper")
    monkeypatch.setattr(
        GlobalSettings,
        "ensure_directories",
        lambda settings: settings.base_path.mkdir(parents=True, exist_ok=True),
    )
    settings = GlobalSettings(base_path=tmp_path)
    arguments = Namespace(port=0)
    settings._apply_cli_overrides(arguments)
    assert settings.server.port == 0

    settings.save_cli_overrides(arguments)
    persisted = GlobalSettings.load(base_path=tmp_path)
    assert persisted.server.port == 8000
