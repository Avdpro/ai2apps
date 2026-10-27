"""Host-only execution Sessions, independent of UI/remote client scopes."""
from __future__ import annotations

import json
from threading import RLock

from ai2apps.apps.access import can_access_app
from ai2apps.core import ResourceConflictError, SessionKind, SessionRetention, SessionVisibility
from ai2apps.identity import IdentityRepository, user_singleton_key
from ai2apps.storage.repositories import AppRepository, SessionRepository

_lock = RLock()


def execution_principal(runtime, owner):
    if owner == 'local':
        principal = runtime.legacy_api_key_principal()
    else:
        principal = IdentityRepository(runtime.database).local_principal_for(owner)
    if principal.actor_user_id != owner or principal.client_scope != 'desktop':
        raise ValueError('Background Task owner is not available in Local scope')
    return principal


def execution_session(runtime, owner, app_id):
    """Resolve a durable, unlisted Session under the authorized business App.

    Never accept a caller's AppInstance, client scope or Session as authority.
    Callers must additionally authorize their own business resource. The lock
    serializes concurrent sync API submissions in the single owning Local.
    """
    with _lock:
        principal = execution_principal(runtime, owner)
        singleton = user_singleton_key(app_id, owner)
        with runtime.database.transaction() as db:
            definition = db.execute("""SELECT * FROM app_definitions WHERE package_id=?
                AND source='builtin' ORDER BY created_at DESC LIMIT 1""",
                (app_id,)).fetchone()
            instance = db.execute('SELECT * FROM app_instances WHERE singleton_key=?', (singleton,)).fetchone()
        if (definition is None or definition['status'] != 'enabled' or definition['instance_mode'] != 'singleton'
                or definition['singleton_scope'] != 'user'
                or not can_access_app(principal, json.loads(definition['manifest_json']))):
            raise ValueError('Background Task App is not available to this owner')
        if instance is None:
            try:
                instance_id = AppRepository(runtime.database, runtime.events).create_instance(
                    app_definition_id=definition['id'], singleton_key=singleton, owner_user_id=owner).id
            except ResourceConflictError:
                # The Shell can create the same canonical instance concurrently.
                with runtime.database.transaction() as db:
                    existing = db.execute('SELECT id FROM app_instances WHERE singleton_key=?', (singleton,)).fetchone()
                if existing is None:
                    raise
                instance_id = existing['id']
        else:
            instance_id = instance['id']
            # UI focus/suspend/close must not stop an admitted background job.
            # Definition enablement, owner and capability remain authoritative.
        runtime.extension_manager.require_instance_access(instance_id, principal)
        with runtime.database.transaction() as db:
            row = db.execute("""SELECT id FROM sessions WHERE app_instance_id=?
                AND status='active' AND session_kind='app' AND visibility='unlisted'
                AND retention='durable' AND json_extract(metadata_json,'$.surface')='system_task'
                ORDER BY created_at LIMIT 1""", (instance_id,)).fetchone()
        if row:
            return row['id']
        return SessionRepository(runtime.database, runtime.events).create(
            app_instance_id=instance_id, title=app_id, session_kind=SessionKind.APP,
            visibility=SessionVisibility.UNLISTED, retention=SessionRetention.DURABLE,
            metadata={'surface': 'system_task', 'app_id': app_id}).id
