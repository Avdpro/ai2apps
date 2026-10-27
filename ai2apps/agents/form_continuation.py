"""Trusted adapters for continuing a parameter interaction inside its owning App."""
import json
from dataclasses import dataclass
from typing import Callable
from datetime import datetime, UTC
from ai2apps.core import ResourceConflictError, ResourceNotFoundError
from .parameter_forms import FORMS

@dataclass(frozen=True)
class ContinuationAdapter:
    begin: Callable
    link: Callable
    complete: Callable

ADAPTERS = {}

def selected_form(database, item):
    base=FORMS.get(item.ui_hints.get('provider') or item.request.get('capability'))
    if not base or base.version!=item.request.get('version') or (base.app_id,base.mini_app_id)!=(item.ui_hints.get('app_id'),item.ui_hints.get('mini_app_id')):
        raise ResourceConflictError('Original form adapter changed')
    if item.ui_hints.get('provider_version') and item.ui_hints['provider_version']!=base.provider_version:raise ResourceConflictError('Original Provider version changed')
    with database.transaction() as db:
        row=db.execute('SELECT * FROM agent_parameter_choices WHERE interaction_id=?',(item.id,)).fetchone()
    if not row:return base
    form=FORMS.get(row['provider'])
    if not form or (form.version,form.app_id,form.mini_app_id,form.provider_version)!=(row['version'],row['app_id'],row['mini_app_id'],row['provider_version']):
        raise ResourceConflictError('Selected form adapter changed')
    return form

def handoff_view(runtime, run_id, interaction_id):
    run=runtime.agents.get_run(run_id)
    item=next((i for i in runtime.agents.list_interactions(run_id) if i.id==interaction_id),None)
    if not item or item.request.get('control')!='parameter_form':raise ResourceNotFoundError('parameter_form',interaction_id)
    form=selected_form(runtime.database,item)
    with runtime.database.transaction() as db:
        row=db.execute('SELECT * FROM agent_parameter_handoffs WHERE interaction_id=?',(item.id,)).fetchone()
        origin=db.execute('''SELECT s.id session_id,i.id instance_id,d.package_id app_id FROM sessions s
            JOIN app_instances i ON i.id=s.app_instance_id JOIN app_definitions d ON d.id=i.app_definition_id
            WHERE s.id=?''',(run.session_id,)).fetchone()
    if not row or row['provider']!=form.key or form.continuation not in ADAPTERS:raise ResourceConflictError('No active App continuation')
    if item.status.value=='pending' and (run.status.value!='waiting_input' or item.deadline_at<=datetime.now(UTC)):
        raise ResourceConflictError('App continuation expired or origin is not waiting')
    return {'run_id':run.id,'interaction_id':item.id,'status':item.status.value,
        'target':{'app_id':form.app_id,'mini_app_id':form.mini_app_id},'origin':dict(origin),
        'parameters':json.loads(row['payload_json']),'response':item.response,'studio_run_id':row['studio_run_id']}
