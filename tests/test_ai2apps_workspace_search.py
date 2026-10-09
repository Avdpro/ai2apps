"""Bounded filesystem discovery and Unicode literal/regex searches."""

import pytest
from test_ai2apps_workspace import _runtime, _session

from ai2apps.workspace import search as scanner
from ai2apps.workspace.models import WorkspaceError


def test_glob_regex_context_and_hidden_files(tmp_path):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    w = runtime.workspace
    for name, text in {
        "main.py": "before\nValue = 42\nafter\n",
        "src/nested/a.py": "value = 10\n",
        "src/a.txt": "Value = 7",
        ".env": "value=secret",
    }.items():
        w.write(session, name, text)
    assert {m["path"] for m in w.glob(session, "**/*.py")["matches"]} == {
        "main.py",
        "src/nested/a.py",
    }
    assert w.glob(session, "src/*.py")["matches"] == []
    assert w.glob(session, ".env")["matches"] == []
    assert w.glob(session, ".env", include_hidden=True)["matches"] == [{"path": ".env"}]
    found = w.search(
        session,
        r"Value\s*=\s*\d+",
        mode="regex",
        include="*.py",
        case_sensitive=True,
        context_lines=1,
    )
    assert len(found["matches"]) == 1
    assert found["matches"][0]["line"] == 2
    assert [c["text"] for c in found["matches"][0]["context"]] == [
        "before",
        "Value = 42",
        "after",
    ]
    assert not found["truncated"]
    assert len(w.search(session, "VALUE", include="*.py")["matches"]) == 2
    with pytest.raises(WorkspaceError):
        w.search(session, "[", mode="regex")
    with pytest.raises(WorkspaceError):
        w.glob(session, "../*")
    runtime.stop()


def test_search_does_not_follow_symlinks_or_cross_sessions(tmp_path):
    runtime = _runtime(tmp_path)
    first, second = _session(runtime), _session(runtime)
    w = runtime.workspace
    w.write(first, "visible.txt", "first")
    w.write(second, "secret.txt", "private")
    (w._root(first) / "foreign").symlink_to(w._root(second), target_is_directory=True)
    (w._root(first) / "foreign.txt").symlink_to(w._root(second) / "secret.txt")
    assert w.search(first, "private")["matches"] == []
    assert w.glob(first, "*")["matches"] == [{"path": "visible.txt"}]
    with pytest.raises(WorkspaceError):
        w.search(first, "private", path="foreign/secret.txt")
    runtime.stop()


def test_search_reports_limits_and_regex_timeout(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path)
    session = _session(runtime)
    w = runtime.workspace
    w.write(session, "many.txt", "hit\nhit\nhit\n")
    limited = w.search(session, "hit", limit=2)
    assert len(limited["matches"]) == 2
    assert limited["incomplete_reasons"] == ["result_limit"]
    exact = w.search(session, "hit", limit=3)
    assert not exact["truncated"]
    w.write(session, "regex.txt", "a" * 200 + "!")
    assert (
        "regex_timeout"
        in w.search(session, "(a|aa)+$", path="regex.txt", mode="regex")[
            "incomplete_reasons"
        ]
    )
    monkeypatch.setattr(scanner, "MAX_FILE_BYTES", 5)
    assert (
        "large_file_skipped"
        in w.search(session, "hit", path="many.txt")["incomplete_reasons"]
    )
    monkeypatch.setattr(scanner, "MAX_ENTRIES", 1)
    assert "entry_limit" in w.glob(session, "*")["incomplete_reasons"]
    runtime.stop()
