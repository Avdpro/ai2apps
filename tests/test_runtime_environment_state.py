import sqlite3
import pytest
from ai2apps.packages import runtime_environment_state as state
from ai2apps.packages.runtime_install_descriptor import DescriptorError

A='a'*64; B='b'*64; C='c'*64; RECEIPT='d'*64

@pytest.fixture
def db(tmp_path):
    c=sqlite3.connect(tmp_path/'state.sqlite', isolation_level=None)
    c.execute('PRAGMA foreign_keys=ON')
    for sql in state.SCHEMA_SQL:c.execute(sql)
    c.execute('BEGIN IMMEDIATE')
    yield c
    c.close()


def ready(c,d):
    assert state.reserve(c,d)
    state.finish(c,d,receipt_digest=RECEIPT,passed=True)


def test_ready_gate_failed_build_and_claim_once(db):
    assert state.reserve(db,A)
    assert not state.reserve(db,A)
    with pytest.raises(DescriptorError,match='not verified'):state.activate(db,'m',A,expected_revision=0)
    state.finish(db,A,receipt_digest=RECEIPT,passed=False)
    with pytest.raises(DescriptorError,match='not verified'):state.activate(db,'m',A,expected_revision=0)
    assert state.claim_collection(db,A)


def test_activation_rollback_and_old_worker_lease(db):
    for d in (A,B,C):ready(db,d)
    assert state.activate(db,'model',A,expected_revision=0)==1
    assert state.acquire_lease(db,'model','worker1')==A
    assert state.activate(db,'model',B,expected_revision=1)==2
    assert not state.claim_collection(db,A) # rollback protects A
    assert state.activate(db,'model',C,expected_revision=2)==3
    assert not state.claim_collection(db,A) # lease still protects A
    state.release_lease(db,'worker1')
    assert state.claim_collection(db,A)
    with pytest.raises(DescriptorError):state.activate(db,'other',A,expected_revision=0)
    assert state.rollback(db,'model',expected_revision=3)==4
    assert state.acquire_lease(db,'model','worker2')==B


def test_stale_revision_cannot_override_new_binding(db):
    ready(db,A);ready(db,B)
    state.activate(db,'m',A,expected_revision=0)
    with pytest.raises(DescriptorError,match='revision'):state.activate(db,'m',B,expected_revision=0)
    assert state.acquire_lease(db,'m','worker')==A


def test_database_rollback_does_not_activate_half_transaction(db):
    ready(db,A);ready(db,B)
    state.activate(db,'m',A,expected_revision=0);db.commit()
    db.execute('BEGIN IMMEDIATE')
    state.activate(db,'m',B,expected_revision=1);db.rollback()
    db.execute('BEGIN IMMEDIATE')
    assert state.acquire_lease(db,'m','after-crash')==A


def test_shared_environment_protected_by_second_model(db):
    ready(db,A);ready(db,B);ready(db,C)
    state.activate(db,'one',A,expected_revision=0)
    state.activate(db,'two',A,expected_revision=0)
    state.activate(db,'one',B,expected_revision=1)
    state.activate(db,'one',C,expected_revision=2)
    assert not state.claim_collection(db,A)


def test_transactions_mandatory(db):
    db.commit()
    with pytest.raises(DescriptorError,match='transaction'):state.reserve(db,A)


def test_independent_connections_serialize_and_reopen(tmp_path):
    path=tmp_path/'concurrent.sqlite'
    first=sqlite3.connect(path,isolation_level=None,timeout=0.01)
    second=sqlite3.connect(path,isolation_level=None,timeout=0.01)
    try:
        for sql in state.SCHEMA_SQL:first.execute(sql)
        first.execute('BEGIN IMMEDIATE');ready(first,A)
        with pytest.raises(sqlite3.OperationalError,match='locked'):
            second.execute('BEGIN IMMEDIATE')
        state.activate(first,'m',A,expected_revision=0);first.commit()
        second.execute('BEGIN IMMEDIATE')
        assert not state.reserve(second,A)
        assert state.acquire_lease(second,'m','persisted')==A
        second.commit()
    finally:first.close();second.close()
    reopened=sqlite3.connect(path,isolation_level=None)
    try:
        reopened.execute('BEGIN IMMEDIATE')
        assert not state.claim_collection(reopened,A)
        assert reopened.execute('SELECT digest FROM runtime_environment_leases WHERE lease=?',('persisted',)).fetchone()==(A,)
    finally:reopened.close()


def test_building_model_pins_base_until_filesystem_collection_complete(db):
    ready(db,A)
    assert state.reserve(db,B,dependencies=(A,))
    assert not state.claim_collection(db,A)
    state.finish(db,B,receipt_digest=RECEIPT,passed=False)
    assert state.claim_collection(db,B)
    assert not state.claim_collection(db,A) # interrupted filesystem removal
    state.complete_collection(db,B)
    assert state.claim_collection(db,A)


def test_transitive_shared_bases_and_second_owner(db):
    ready(db,A)
    state.reserve(db,B,dependencies=(A,));state.finish(db,B,receipt_digest=RECEIPT,passed=True)
    state.reserve(db,C,dependencies=(B,));state.finish(db,C,receipt_digest=RECEIPT,passed=True)
    other='e'*64
    state.reserve(db,other,dependencies=(A,));state.finish(db,other,receipt_digest=RECEIPT,passed=True)
    assert not state.claim_collection(db,A)
    assert not state.claim_collection(db,B)
    assert state.claim_collection(db,C);state.complete_collection(db,C)
    assert state.claim_collection(db,B);state.complete_collection(db,B)
    assert not state.claim_collection(db,A) # other model still references it


def test_base_graph_is_immutable_and_ready_only(db):
    state.reserve(db,A)
    with pytest.raises(DescriptorError,match='not verified'):state.reserve(db,B,dependencies=(A,))
    state.finish(db,A,receipt_digest=RECEIPT,passed=True)
    assert state.reserve(db,B,dependencies=(A,))
    assert not state.reserve(db,B,dependencies=(A,))
    with pytest.raises(DescriptorError,match='immutable'):state.reserve(db,B)
    with pytest.raises(DescriptorError,match='self'):state.reserve(db,C,dependencies=(C,))
    with pytest.raises(DescriptorError,match='claimed'):state.complete_collection(db,A)


def test_collected_base_cannot_race_new_owner(db):
    ready(db,A);assert state.claim_collection(db,A)
    with pytest.raises(DescriptorError,match='not verified'):state.reserve(db,B,dependencies=(A,))
    assert db.execute('SELECT digest FROM runtime_environment_candidates WHERE digest=?',(B,)).fetchone() is None
