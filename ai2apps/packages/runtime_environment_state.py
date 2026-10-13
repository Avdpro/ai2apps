"""Transactional state primitives for the draft managed Runtime installer.

All writes require the caller's existing PlatformDatabase write transaction.
Schema is deliberately NOT registered in production migrations yet. Filesystem
materialization, signature/probe verification and process leases must be wired
by the Host; this module never treats a bare directory as a ready environment.
"""
import re
import sqlite3

from .runtime_install_descriptor import DescriptorError

SCHEMA_SQL = (
    "CREATE TABLE runtime_environment_candidates (digest TEXT PRIMARY KEY, state TEXT NOT NULL CHECK(state IN ('building','ready','failed','deleting')), receipt_digest TEXT)",
    "CREATE TABLE runtime_environment_bindings (model TEXT PRIMARY KEY, current_digest TEXT NOT NULL REFERENCES runtime_environment_candidates(digest), previous_digest TEXT REFERENCES runtime_environment_candidates(digest), revision INTEGER NOT NULL)",
    "CREATE TABLE runtime_environment_dependencies (owner TEXT NOT NULL REFERENCES runtime_environment_candidates(digest), dependency TEXT NOT NULL REFERENCES runtime_environment_candidates(digest), PRIMARY KEY(owner,dependency), CHECK(owner != dependency))",
    "CREATE TABLE runtime_environment_leases (lease TEXT PRIMARY KEY, digest TEXT NOT NULL REFERENCES runtime_environment_candidates(digest))",
)


def _digest(value):
    if not isinstance(value, str) or re.fullmatch('[a-f0-9]{64}', value) is None:
        raise DescriptorError('invalid environment/receipt digest')


def _write(connection):
    if not connection.in_transaction:
        raise DescriptorError('explicit Host write transaction required')


def reserve(connection: sqlite3.Connection, digest: str, *, dependencies: tuple[str, ...] = ()) -> bool:
    """Claim a build and immutable ready bases together in the Host transaction.

    Bases must already be ready. This construction order prevents cycles; a
    building or deleting base cannot be attached to a new model environment.
    """
    _write(connection); _digest(digest)
    if not isinstance(dependencies, tuple) or len(set(dependencies)) != len(dependencies):
        raise DescriptorError('expected unique dependency digests')
    for dependency in dependencies:
        _digest(dependency)
        if dependency == digest:
            raise DescriptorError('self dependency')
    existing = connection.execute('SELECT state FROM runtime_environment_candidates WHERE digest=?', (digest,)).fetchone()
    if existing:
        recorded = {row[0] for row in connection.execute('SELECT dependency FROM runtime_environment_dependencies WHERE owner=?', (digest,))}
        if recorded != set(dependencies):
            raise DescriptorError('immutable dependency graph mismatch')
        return False
    for dependency in dependencies:
        _ready(connection, dependency)
    connection.execute('INSERT INTO runtime_environment_candidates VALUES (?, ?, NULL)', (digest, 'building'))
    connection.executemany('INSERT INTO runtime_environment_dependencies VALUES (?,?)', ((digest, dependency) for dependency in dependencies))
    return True


def finish(connection, digest: str, *, receipt_digest: str, passed: bool):
    """Host calls only after storing immutable validation evidence durably."""
    _write(connection); _digest(digest); _digest(receipt_digest)
    if type(passed) is not bool:
        raise DescriptorError('validation result must be boolean')
    if connection.execute(
        "UPDATE runtime_environment_candidates SET state=?,receipt_digest=? WHERE digest=? AND state='building'",
        ('ready' if passed else 'failed', receipt_digest, digest)).rowcount != 1:
        raise DescriptorError('candidate not building')


def _ready(connection, digest):
    _digest(digest)
    row = connection.execute('SELECT state,receipt_digest FROM runtime_environment_candidates WHERE digest=?', (digest,)).fetchone()
    if not row or row[0] != 'ready' or row[1] is None:
        raise DescriptorError('environment not verified ready')


def activate(connection, model: str, digest: str, *, expected_revision: int):
    """CAS activation; retain previous binding for rollback in the same commit."""
    _write(connection); _ready(connection, digest)
    if not isinstance(model, str) or not model or type(expected_revision) is not int or expected_revision < 0:
        raise DescriptorError('invalid model/revision')
    row = connection.execute('SELECT current_digest,previous_digest,revision FROM runtime_environment_bindings WHERE model=?', (model,)).fetchone()
    if (row[2] if row else 0) != expected_revision:
        raise DescriptorError('activation revision conflict')
    if row and row[0] == digest:
        return row[2]
    revision = expected_revision + 1
    if row:
        connection.execute('UPDATE runtime_environment_bindings SET current_digest=?,previous_digest=?,revision=? WHERE model=?', (digest,row[0],revision,model))
    else:
        connection.execute('INSERT INTO runtime_environment_bindings VALUES (?,?,NULL,?)', (model,digest,revision))
    return revision


def rollback(connection, model: str, *, expected_revision: int):
    _write(connection)
    row = connection.execute('SELECT previous_digest,revision FROM runtime_environment_bindings WHERE model=?', (model,)).fetchone()
    if not row or row[0] is None or row[1] != expected_revision:
        raise DescriptorError('rollback unavailable/revision conflict')
    return activate(connection, model, row[0], expected_revision=expected_revision)


def acquire_lease(connection, model: str, lease: str) -> str:
    """Bind the Worker to the exact environment selected in this transaction."""
    _write(connection)
    if not isinstance(lease, str) or not lease:
        raise DescriptorError('invalid lease')
    row = connection.execute('SELECT current_digest FROM runtime_environment_bindings WHERE model=?', (model,)).fetchone()
    if not row:
        raise DescriptorError('model has no active environment')
    _ready(connection,row[0])
    connection.execute('INSERT INTO runtime_environment_leases VALUES (?,?)', (lease,row[0]))
    return row[0]


def release_lease(connection, lease: str):
    """Caller must verify Worker and children have exited; no TTL auto-expiry."""
    _write(connection)
    connection.execute('DELETE FROM runtime_environment_leases WHERE lease=?', (lease,))


def claim_collection(connection, digest: str) -> bool:
    """Prevent future activation before filesystem GC, without deleting files.

    All active and rollback bindings and process leases protect their roots.
    Building environments need explicit abandoned-transaction recovery first.
    """
    _write(connection); _digest(digest)
    return connection.execute('''UPDATE runtime_environment_candidates SET state='deleting'
        WHERE digest=? AND state IN ('ready','failed')
        AND NOT EXISTS (SELECT 1 FROM runtime_environment_bindings WHERE current_digest=? OR previous_digest=?)
        AND NOT EXISTS (SELECT 1 FROM runtime_environment_leases WHERE digest=?)
        AND NOT EXISTS (SELECT 1 FROM runtime_environment_dependencies WHERE dependency=?)''',
        (digest,digest,digest,digest,digest)).rowcount == 1


def complete_collection(connection, digest: str):
    """Called only after confirmed removal of the claimed environment tree.

    Keep bases protected while filesystem deletion is pending or interrupted.
    Filesystem ownership and deletion are materializer duties, not SQL effects.
    """
    _write(connection); _digest(digest)
    row = connection.execute('SELECT state FROM runtime_environment_candidates WHERE digest=?', (digest,)).fetchone()
    if not row or row[0] != 'deleting':
        raise DescriptorError('environment not claimed for collection')
    connection.execute('DELETE FROM runtime_environment_dependencies WHERE owner=?', (digest,))
    connection.execute('DELETE FROM runtime_environment_candidates WHERE digest=?', (digest,))
