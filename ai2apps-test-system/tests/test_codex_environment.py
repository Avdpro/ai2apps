import os

import pytest

from ai2apps_test import codex_driver


def test_gui_path_resolves_codex_and_node(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin:.:relative")
    monkeypatch.setattr(codex_driver.Path, "home", lambda: tmp_path)
    binary = tmp_path / ".local/bin/codex"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/usr/bin/env node\n")
    binary.chmod(0o755)
    node = binary.with_name("node")
    node.write_text("#!/bin/sh\n")
    node.chmod(0o755)
    executable, environment = codex_driver.codex_environment()
    assert executable == str(binary)
    assert str(binary.parent) in environment["PATH"].split(os.pathsep)
    assert "." not in environment["PATH"].split(os.pathsep)
    assert os.environ["PATH"] == "/usr/bin:/bin:.:relative"


def test_missing_node_has_specific_error(tmp_path, monkeypatch):
    binary = tmp_path / "codex"
    binary.write_text("#!/usr/bin/env node\n")
    monkeypatch.setattr(codex_driver.shutil, "which", lambda name, **kw: str(binary) if name == "codex" else None)
    with pytest.raises(codex_driver.CodexDriverError, match="Node.js"):
        codex_driver.codex_environment()


def test_missing_codex_has_specific_error(monkeypatch):
    monkeypatch.setattr(codex_driver.shutil, "which", lambda *args, **kw: None)
    with pytest.raises(codex_driver.CodexDriverError, match="找不到 Codex"):
        codex_driver.codex_environment()
