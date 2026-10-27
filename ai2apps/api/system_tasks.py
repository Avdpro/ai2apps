"""Owner-scoped Task controls shared by Todo Desktop and Mobile."""
from fastapi import Depends, HTTPException
from pydantic import BaseModel


class CancelSystemTask(BaseModel):
    force: bool = False


def install_system_task_routes(router, runtime_provider, principal_provider, *, prefix=''):
    dep=Depends(principal_provider)

    def service(principal):
        from ai2apps.apps.access import has_app_capability
        if not has_app_capability(principal,'app.use'):
            raise HTTPException(403,'Todo access required')
        value=getattr(runtime_provider(),'system_tasks',None)
        if value is None:raise HTTPException(503,'System Task service is not ready')
        return value

    def checked(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except KeyError:raise HTTPException(404,'System Task not found') from None
        except ValueError as error:raise HTTPException(409,str(error)) from None

    @router.get(prefix+'/system-tasks')
    def snapshot(principal=dep):
        return service(principal).snapshot(principal.actor_user_id)

    @router.get(prefix+'/system-tasks/{id}')
    def detail(id: str, principal=dep):
        s=service(principal);owner=principal.actor_user_id
        task=checked(s.get,owner,id)
        root=task['progress'].get('root_id') or ('collection:'+task['checkpoint']['run_id'] if task['checkpoint'].get('run_id') else None)
        with s.database.transaction() as db:
            children=[dict(row) for row in db.execute('SELECT id,parent_id,name,kind,status FROM task_nodes WHERE owner=? AND root_id=? ORDER BY created_at LIMIT 200',(owner,root))] if root else []
        for key in ('payload','checkpoint','result'):task.pop(key)
        return {'task':task,'attempts':s.attempts(owner,id),'children':children}

    @router.post(prefix+'/system-tasks/{id}/start')
    def start(id: str,principal=dep):
        task=checked(service(principal).start,principal.actor_user_id,id)
        return {'id':task['id'],'status':task['status']}

    @router.post(prefix+'/system-tasks/{id}/cancel')
    def cancel(id: str,body: CancelSystemTask,principal=dep):
        task=checked(service(principal).cancel,principal.actor_user_id,id,force=body.force)
        return {'id':task['id'],'status':task['status']}

    @router.post(prefix+'/system-schedules/{id}/start')
    def start_schedule(id: str,principal=dep):
        task=checked(service(principal).start_schedule,principal.actor_user_id,id)
        return {'id':task['id'],'status':task['status']}
