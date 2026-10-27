from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_spark_staging_excludes_local_build_payloads(monkeypatch, tmp_path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "spark_builder", ROOT / "scripts" / "build_spark_pip_package.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source = tmp_path / "source"
    for package in ("ai2apps", "omlx"):
        directory = source / package
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text("")
        for excluded in (".build", ".cache", ".venv", ".git"):
            (directory / excluded).mkdir()
            (directory / excluded / "large-payload").write_bytes(b"not package data")
    (source / "ai2apps" / "web").mkdir()
    (source / "ai2apps" / "web" / "index.html").write_text("retained")
    for name in ("README.md", "LICENSE", "NOTICE"):
        (source / name).write_text(name)
    monkeypatch.setattr(builder, "ROOT", source)
    staging = tmp_path / "staging"
    builder._copy_sources(staging)
    assert (staging / "ai2apps/web/index.html").read_text() == "retained"
    assert not list(staging.rglob("large-payload"))
    assert (staging / "omlx/__init__.py").is_file()


def test_spark_profile_imports_server_without_mlx():
    script = r'''
import importlib.abc
import os
import sys

class BlockMLX(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mlx" or fullname.startswith("mlx.") or fullname.startswith("mlx_"):
            raise ModuleNotFoundError(f"blocked {fullname}", name=fullname)

sys.meta_path.insert(0, BlockMLX())
from ai2apps.spark_cli import _configure_spark_profile
_configure_spark_profile()
import omlx.server
assert os.environ["AI2APPS_RUNTIME_PROFILE"] == "cloud"
'''
    environment = os.environ.copy()
    environment.pop("AI2APPS_RUNTIME_PROFILE", None)
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_spark_build_configuration_has_no_mlx_dependency():
    import tomllib

    source = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = source["project"]["optional-dependencies"]["control-plane"]
    assert not any(item.split("[", 1)[0].startswith("mlx") for item in dependencies)
    assert any(item.startswith("noiseprotocol") for item in dependencies)


def test_spark_serve_defaults_to_loopback_and_local_data(monkeypatch, tmp_path: Path):
    from ai2apps.spark_cli import _prepare_serve_arguments

    monkeypatch.setenv("AI2APPS_HOME", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["ai2apps", "serve"])
    _prepare_serve_arguments()
    assert sys.argv == [
        "ai2apps",
        "serve",
        "--base-path",
        str(tmp_path),
        "--host",
        "127.0.0.1",
    ]


def test_systemd_argument_is_quoted_and_rejects_newlines():
    import pytest

    from ai2apps.spark_cli import _systemd_argument

    assert _systemd_argument('/path with "quote"') == '"/path with \\"quote\\""'
    with pytest.raises(ValueError):
        _systemd_argument("bad\nvalue")


def test_docker_group_is_preserved_for_user_systemd(monkeypatch):
    from types import SimpleNamespace

    from ai2apps.spark_cli import _docker_systemd_group

    monkeypatch.setattr("ai2apps.spark_cli.sys.platform", "linux")
    monkeypatch.setattr("grp.getgrnam", lambda _name: SimpleNamespace(gr_gid=988))
    monkeypatch.setattr("ai2apps.spark_cli.os.getgroups", lambda: [1000, 988])

    assert _docker_systemd_group(False) == ""
    assert _docker_systemd_group(True) == "SupplementaryGroups=docker\n"


def test_spark_models_command_registers_loopback_openai_runtime(tmp_path: Path):
    from ai2apps.model_manager import ModelManagerStore
    from ai2apps.spark_cli import _models

    result = _models(
        [
            "add-openai",
            "--id",
            "local-test",
            "--base-url",
            "http://127.0.0.1:8766/v1",
            "--model",
            "local/model",
            "--base-path",
            str(tmp_path),
        ]
    )
    assert result == 0
    resolved = ModelManagerStore(tmp_path).resolve_cloud_model(
        "cloud/local-test/local/model"
    )
    assert resolved is not None
    assert resolved["base_url"] == "http://127.0.0.1:8766/v1"
    assert resolved["model_id"] == "local/model"


def test_spark_models_command_rejects_non_loopback_by_default(tmp_path: Path):
    import pytest

    from ai2apps.spark_cli import _models

    with pytest.raises(SystemExit):
        _models(
            [
                "add-openai",
                "--id",
                "remote-test",
                "--base-url",
                "https://example.com/v1",
                "--model",
                "remote/model",
                "--base-path",
                str(tmp_path),
            ]
        )
