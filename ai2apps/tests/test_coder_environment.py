"""Desktop PATH discovery must support user-selected Node runtimes."""
import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("coder_environment", Path(__file__).parents[1] / "coder/environment.py")
environment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(environment)


def test_user_version_manager_path_and_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "/custom/bin:/usr/bin::.")
    monkeypatch.setattr(environment, "_login_shell_path", lambda: "/home/user/.nvm/versions/node/v22/bin:/usr/bin")
    paths = environment.cli_search_path(tmp_path).split(":")
    assert paths[:3] == [str(tmp_path / "node_modules/.bin"), "/custom/bin", "/usr/bin"]
    assert "/home/user/.nvm/versions/node/v22/bin" in paths
    assert len(paths) == len(set(paths))
    assert "" not in paths and "." not in paths


def test_shell_banner_and_cache(monkeypatch):
    monkeypatch.setattr(environment, "_cached_shell_path", None)
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="welcome\n__AI2APPS_PATH_BEGIN__\n/version/bin:/bin\n__AI2APPS_PATH_END__\nbye")
    monkeypatch.setattr(environment.subprocess, "run", run)
    assert environment._login_shell_path() == "/version/bin:/bin"
    assert environment._login_shell_path() == "/version/bin:/bin"
    assert len(calls) == 1


def test_timeout_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(environment, "_cached_shell_path", None)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("shell", 3)
    monkeypatch.setattr(environment.subprocess, "run", timeout)
    paths = environment.cli_search_path(tmp_path).split(":")
    assert "/usr/local/bin" in paths and "/opt/homebrew/bin" in paths


def test_env_node_shebang_with_discovered_runtime(monkeypatch, tmp_path):
    runtime = tmp_path / "custom-node/bin"
    runtime.mkdir(parents=True)
    node = runtime / "node"
    node.write_text("#!/bin/sh\nprintf 'runtime-ok\\n'\n")
    node.chmod(0o755)
    cli = tmp_path / "cli"
    cli.write_text("#!/usr/bin/env node\n")
    cli.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(environment, "_login_shell_path", lambda: str(runtime))
    result = subprocess.run([str(cli)], env={"PATH": environment.cli_search_path(tmp_path)}, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "runtime-ok"
