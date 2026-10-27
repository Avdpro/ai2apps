"""Fast ordinary startup still checks metadata; migrations scan all pages."""

from ai2apps.storage import PlatformDatabase


class TracedDatabase(PlatformDatabase):
    def __init__(self, path):
        super().__init__(path)
        self.statements = []

    def connect(self):
        connection = super().connect()
        connection.set_trace_callback(self.statements.append)
        return connection


def test_existing_schema_avoids_full_data_scan(tmp_path):
    path = tmp_path / "platform.sqlite3"
    database = TracedDatabase(path)
    database.initialize()
    assert "PRAGMA quick_check" in database.statements

    database.statements.clear()
    database.initialize()
    assert "PRAGMA quick_check('sqlite_schema')" in database.statements
    assert "PRAGMA quick_check" not in database.statements

