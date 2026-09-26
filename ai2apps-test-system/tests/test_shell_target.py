import plistlib

import pytest

from ai2apps_test.shell_target import test_shell_path as resolve_shell


def bundle(path, identifier):
    (path / "Contents").mkdir(parents=True)
    (path / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": identifier}))


def test_only_current_embedded_shell(tmp_path):
    outer = tmp_path / "apps/ai2apps-acefox/.build/AI2Apps-test.app"
    bundle(outer, "com.ai2apps.desktop.test")
    shell = outer / "Contents/Applications/AI2Apps.app"
    bundle(shell, "com.ai2apps.desktop.test.shell")
    bundle(outer.parent / "archive/old.app", "com.ai2apps.desktop.test.shell")
    assert resolve_shell(tmp_path) == str(shell)


def test_reject_wrong_identity_and_symlink(tmp_path):
    outer = tmp_path / "apps/ai2apps-acefox/.build/AI2Apps-test.app"
    bundle(outer, "com.ai2apps.desktop.test")
    shell = outer / "Contents/Applications/AI2Apps.app"
    bundle(shell, "com.ai2apps.desktop.appdev.shell")
    with pytest.raises(ValueError):
        resolve_shell(tmp_path)
    archive = outer.parent / "archive/old.app"
    bundle(archive, "com.ai2apps.desktop.test.shell")
    (shell.parent / "linked.app").symlink_to(archive)
    with pytest.raises(ValueError):
        resolve_shell(tmp_path)
