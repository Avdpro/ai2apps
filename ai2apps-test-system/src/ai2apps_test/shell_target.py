"""Resolve only the current, embedded Test Shell, never archived applications."""
import plistlib
from pathlib import Path


def test_shell_path(repo_root: Path) -> str:
    outer = repo_root / "apps/ai2apps-acefox/.build/AI2Apps-test.app"
    if outer.is_symlink():
        raise ValueError("Test App must not be a symlink")
    with (outer / "Contents/Info.plist").open("rb") as stream:
        if plistlib.load(stream).get("CFBundleIdentifier") != "com.ai2apps.desktop.test":
            raise ValueError("Invalid Test App identity")
    matches = []
    for candidate in (outer / "Contents/Applications").glob("*.app"):
        if candidate.is_symlink() or not candidate.resolve().is_relative_to(outer.resolve()):
            continue
        with (candidate / "Contents/Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        if info.get("CFBundleIdentifier") == "com.ai2apps.desktop.test.shell":
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError("Current Test App must contain exactly one Test Shell")
    return str(matches[0].resolve())
