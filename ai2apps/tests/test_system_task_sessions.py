from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from fastapi import HTTPException

from ai2apps.api.ownership import authorize_session
from ai2apps.apps import ensure_system_apps
from ai2apps.browser.invocation import WebAgentInvocation
from ai2apps.chat.repository import ChatRepository
from ai2apps.events import EventStore
from ai2apps.extensions.manager import InteractivePackageManager
from ai2apps.identity import IdentityRepository, OrganizationType, MemberRole
from ai2apps.storage import PlatformDatabase
from ai2apps.storage.repositories import SessionRepository
from ai2apps.system_tasks.sessions import execution_session

OWNER = 'b8696bee-d730-46b6-848c-e41f1f96a0b4'
OTHER = '9df2aa2a-b029-4d10-a9e1-805db637e595'


@pytest.fixture
def runtime(tmp_path):
    db = PlatformDatabase(tmp_path / 'platform.sqlite3')
    db.initialize()
    events = EventStore(db)
    ensure_system_apps(db, events)
    identities = IdentityRepository(db)
    identities.bind_installation(
        installation_id='b657d60d-2a38-4a66-bf21-20d7bb1bb13f',
        cloud_device_id='35f29378-4912-4a76-a99d-197361226ca7',
        organization_id='c10c7a58-b338-4194-a6a2-693bf1d54c9e',
        organization_type=OrganizationType.HOUSEHOLD, core_user_id=OWNER,
        billing_account_id='71c8e42b-f8a6-49f1-b618-76b9e20c0510',
        access_epoch=7, core_membership_epoch=2)
    identities.upsert_membership(cloud_user_id=OTHER, role=MemberRole.MEMBER,
                                 status='active', membership_epoch=1)
    # Exercise the real ownership guard without starting browser/network services.
    manager = object.__new__(InteractivePackageManager)
    manager.database = db
    manager.sessions = SessionRepository(db, events)
    return NS(database=db, events=events, extension_manager=manager)


def test_mobile_chat_scope_is_still_denied_but_background_webagent_can_submit(runtime):
    local = IdentityRepository(runtime.database).local_principal_for(OWNER)
    mobile = replace(local, client_scope='owner-home', authentication_type='owner_home_lease')
    chats = ChatRepository(runtime.database, runtime.events, principal=mobile)
    thread, _ = chats.create_thread(title='Mobile conversation')
    authorize_session(runtime, mobile, thread.session.id)
    with pytest.raises(HTTPException) as error:
        authorize_session(runtime, local, thread.session.id)
    assert error.value.detail['code'] == 'app_instance_not_found'

    session = execution_session(runtime, OWNER, 'ai2apps.intelligence')
    assert session != thread.session.id
    authorize_session(runtime, local, session)
    task = WebAgentInvocation(runtime).submit(
        owner=OWNER, session_id=session, name='Read list', key='test-read',
        caller_app_id='ai2apps.intelligence', source={'agent_type': 'web', 'steps': [{
            'name': 'read', 'operation': 'read_page', 'desc': 'Read page',
            'arguments': {'url': 'https://example.com/'},
            'on': {'success': 'done', 'failed': 'failed'}}]})
    assert task['status'] == 'queued'
    assert execution_session(runtime, OWNER, 'ai2apps.intelligence') == session
    with runtime.database.transaction() as db:
        row = db.execute('SELECT * FROM sessions WHERE id=?', (session,)).fetchone()
        instance = db.execute('SELECT owner_user_id FROM app_instances WHERE id=?', (row['app_instance_id'],)).fetchone()
        assert row['visibility'] == 'unlisted' and row['session_kind'] == 'app'
        assert instance['owner_user_id'] == OWNER
        assert not db.execute('SELECT 1 FROM chat_thread_entries WHERE session_id=?', (session,)).fetchone()


def test_owner_and_app_isolation_and_session_recovery(runtime):
    session = execution_session(runtime, OWNER, 'ai2apps.intelligence')
    other = execution_session(runtime, OTHER, 'ai2apps.intelligence')
    assert other != session
    with pytest.raises(HTTPException):
        authorize_session(runtime, IdentityRepository(runtime.database).local_principal_for(OTHER), session)
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE sessions SET status='archived' WHERE id=?", (session,))
    replacement = execution_session(runtime, OWNER, 'ai2apps.intelligence')
    assert replacement != session
    assert execution_session(runtime, OWNER, 'ai2apps.todo') != replacement
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE app_instances SET status='suspended' WHERE id=(SELECT app_instance_id FROM sessions WHERE id=?)", (replacement,))
    assert execution_session(runtime, OWNER, 'ai2apps.intelligence') == replacement


def test_revoked_owner_or_unavailable_app_cannot_get_background_context(runtime):
    with pytest.raises(ValueError):
        execution_session(runtime, OWNER, 'unknown.app')
    IdentityRepository(runtime.database).upsert_membership(
        cloud_user_id=OTHER, role=MemberRole.MEMBER, status='revoked', membership_epoch=2)
    with pytest.raises(Exception, match='active installation member'):
        execution_session(runtime, OTHER, 'ai2apps.intelligence')
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE app_definitions SET status='disabled' WHERE package_id='ai2apps.intelligence'")
    with pytest.raises(ValueError, match='not available'):
        execution_session(runtime, OWNER, 'ai2apps.intelligence')


def test_parallel_submissions_reuse_one_background_session(runtime):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        sessions = list(pool.map(lambda _: execution_session(runtime, OWNER, 'ai2apps.intelligence'), range(8)))
    assert len(set(sessions)) == 1
