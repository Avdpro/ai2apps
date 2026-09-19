from __future__ import annotations

import hashlib
import sqlite3

from scripts.publish_checkpoint_distribution import _browser_session_namespace


def test_browser_session_namespace_reads_newest_cookie_from_wal(tmp_path) -> None:
    security_instance_id = "local_" + "b" * 32
    cookie_name = "ai2apps_cloud_browser_" + hashlib.sha256(
        security_instance_id.encode("ascii")
    ).hexdigest()[:16]
    database = tmp_path / "cookies.sqlite"
    writer = sqlite3.connect(database)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute(
            "CREATE TABLE moz_cookies "
            "(name TEXT NOT NULL, value TEXT NOT NULL, lastAccessed INTEGER NOT NULL)"
        )
        writer.execute(
            "INSERT INTO moz_cookies VALUES (?, ?, ?)",
            (cookie_name, "browser_session_old_1234567890123456", 1),
        )
        writer.commit()
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute(
            "INSERT INTO moz_cookies VALUES (?, ?, ?)",
            (cookie_name, "browser_session_new_1234567890123456", 2),
        )
        writer.commit()

        assert _browser_session_namespace(database, security_instance_id) == (
            "browser:browser_session_new_1234567890123456"
        )
    finally:
        writer.close()
