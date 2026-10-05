import sqlite3
from contextlib import contextmanager

from ai2apps.app_development.service import _migrate_builtin_executor


def test_migration_is_owned_scoped_and_idempotent():
    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE agent_definitions (agent_key, source, executor_key, revision)')
    rows = [
        ('ai2apps.app-developer', 'builtin', 'builtin:general-agent', 1),
        ('ai2apps.app-developer', 'package', 'builtin:general-agent', 1),
        ('other', 'builtin', 'builtin:general-agent', 1),
        ('ai2apps.app-developer', 'builtin', 'custom', 1),
    ]
    connection.executemany('INSERT INTO agent_definitions VALUES (?, ?, ?, ?)', rows)

    class Database:
        @contextmanager
        def transaction(self, *, write):
            assert write
            with connection:
                yield connection

    _migrate_builtin_executor(Database())
    _migrate_builtin_executor(Database())
    result = connection.execute('SELECT * FROM agent_definitions').fetchall()
    assert result == [
        ('ai2apps.app-developer', 'builtin', 'builtin:coding-parent', 2),
        *rows[1:],
    ]
