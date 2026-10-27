"""Shopping-owned cache selection. References never confer execution authority."""
from ai2apps.core.errors import RepositoryError
from fastapi import HTTPException
from ai2apps.studio.capability_broker import StudioCapabilityError


def iter_tasks(broker, mounted, principal, *, profile=None, session_id=None, limit=12, history_only=False):
    from .tasks import BrowserTaskRepository
    repository=BrowserTaskRepository(broker.runtime.database,broker.runtime.events)
    with broker.runtime.database.transaction() as db:
        rows=db.execute('SELECT t.id FROM browser_tasks t JOIN browser_task_programs p ON p.task_id=t.id AND p.owner=t.owner WHERE t.owner=? AND p.caller_app_id=? AND (? IS NULL OR t.profile_key=?) AND (? IS NULL OR t.session_id=?) AND (?=0 OR t.capability IN (\'history\',\'refresh_list\')) ORDER BY t.created_at DESC,t.id DESC LIMIT 200',
            (principal.actor_user_id,broker.caller(mounted),profile,profile,session_id,session_id,int(history_only))).fetchall()
    count=0
    for row in rows:
        try:
            task=repository.get(principal.actor_user_id,row['id'])
            if task.get('session_id'):
                from ai2apps.api.ownership import authorize_session
                authorize_session(broker.runtime,principal,task['session_id'])
            yield broker.task_declared(mounted,principal,row['id'])
            count+=1
        except (RepositoryError,HTTPException,StudioCapabilityError,KeyError):continue
        if count>=limit:break


def latest_history(broker,mounted,principal,profile):
    for task in iter_tasks(broker,mounted,principal,profile=profile,limit=200,history_only=True):
        if task['capability'] in ('history','refresh_list') and (task['status']=='completed' or task.get('history_checkpoint')):
            result=task.get('result') or {}
            history=(result.get('assigned') or {}).get('shopping_report',{}).get('history',result)
            # An observed empty history is a valid cache, but deleted/redacted results are not.
            if isinstance(history.get('items'),list) and history.get('synced_at'):
                return task
    return None


def recent_tasks(broker,mounted,principal,**kwargs):
    return list(iter_tasks(broker,mounted,principal,**kwargs))


def discovery_mount(broker,principal,session_id):
    """Read an existing authorized instance; discovery never launches an App."""
    from .shopping_aaat import APP, MINI
    from ai2apps.api.ownership import authorize_session
    from ai2apps.studio.capability_broker import MountedMiniApp
    authorize_session(broker.runtime,principal,session_id)
    definition,declaration=broker.runtime.extension_manager._studio_mini_app_definition(APP,MINI,principal)
    with broker.runtime.database.transaction() as db:
        rows=db.execute("SELECT i.id FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id WHERE d.package_id=? AND i.status='active' ORDER BY i.updated_at DESC",(definition['package_id'],)).fetchall()
    for row in rows:
        try:broker.runtime.extension_manager.require_instance_access(row['id'],principal)
        except (RepositoryError,RuntimeError):continue
        return MountedMiniApp(mount={'app_instance_id':row['id'],'app_key':definition['package_id'],
            'effective_digest':definition['effective_digest'],'interaction_session_id':session_id},declaration=declaration,capabilities=frozenset())
    return None
