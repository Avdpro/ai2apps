"""Imagine-owned mapping and trusted results for a Chat parameter handoff."""
from datetime import datetime
from fastapi import HTTPException
from ai2apps.agents.form_continuation import ADAPTERS, ContinuationAdapter
from ai2apps.studio.repository import StudioRepository, TERMINAL_RUN_STATUSES
from .mini_parameters import WORKFLOWS, compose

KEY='ai2apps.imagine-studio/v1'

def switch_values(runtime,run,source,target,values):
    result=dict(values)
    refs=values.get('person_artifact_ids') or values.get('artifact_ids') or ([values['artifact_id']] if values.get('artifact_id') else [])
    refs=list(dict.fromkeys(refs+([values['background_artifact_id']] if values.get('background_artifact_id') else [])))
    for key in ('artifact_id','artifact_ids','person_artifact_ids','background_artifact_id'):result.pop(key,None)
    capability=target.capability or target.key
    if capability=='image.group_photo':result['person_artifact_ids']=refs
    elif capability=='image.edit':
        if refs:result['artifact_id']=refs[0]
        if len(refs)>1:raise HTTPException(422,'Single-image editing cannot carry multiple reference images')
    else:result['artifact_ids']=refs
    if not result.get('prompt'):result['prompt']=run.input.get('prompt','')
    return result

def begin(runtime,principal,run,item,form,values):
    refs=[]
    if form.capability=='image.group_photo':
        if len(values.get('person_artifact_ids',[]))>3:raise HTTPException(422,'Group photo supports at most three subject references')
        refs=[(index,identifier) for index,identifier in enumerate(values.get('person_artifact_ids',[]))]
        if values.get('background_artifact_id'):refs.append((3,values['background_artifact_id']))
    else:
        ids=values.get('artifact_ids') or ([values['artifact_id']] if values.get('artifact_id') else [])
        refs=list(enumerate(ids))
    references=[]
    for index,identifier in refs:
        artifact=runtime.workspace.get_artifact(run.session_id,identifier)
        if not artifact.media_type.startswith('image/'):raise HTTPException(422,'Expected an owned image reference')
        references.append({'slot':index,'artifact_id':artifact.id,'session_id':run.session_id,'name':artifact.name,
            'media_type':artifact.media_type})
    return {'values':values,'references':references,'capability':form.capability,'provider':form.key}

def owned_run(runtime,principal,form,record,studio_run_id,app_instance_id):
    with runtime.database.transaction() as db:
        row=db.execute('SELECT * FROM studio_runs WHERE id=?',(studio_run_id,)).fetchone()
    if not row or (row['actor_id'],row['installation_id'],row['app_instance_id'],row['studio_id'],row['mini_app_id'])!=(principal.actor_user_id,principal.installation_id,app_instance_id,form.app_id,form.mini_app_id):
        raise HTTPException(404,'Matching Mini-App result not found')
    if datetime.fromisoformat(row['created_at'].replace('Z','+00:00'))<datetime.fromisoformat(record['created_at'].replace('Z','+00:00')):
        raise HTTPException(409,'The result predates this App continuation')
    return StudioRepository(runtime.database).get_run(studio_run_id,actor_id=principal.actor_user_id,
        installation_id=principal.installation_id,app_instance_id=app_instance_id,studio_id=form.app_id)

def link(runtime,principal,run,item,form,record,body):
    value=owned_run(runtime,principal,form,record,body.studio_run_id,body.app_instance_id)
    if value['input'].get('parameterHandoffInteractionId')!=item.id:raise HTTPException(409,'Task is not linked to this continuation')
    if record['studio_run_id'] and record['studio_run_id']!=body.studio_run_id:
        old=owned_run(runtime,principal,form,record,record['studio_run_id'],record['app_instance_id'])
        if old['status'] not in TERMINAL_RUN_STATUSES:raise HTTPException(409,'The previous task is still running')
    return {'studio_run_id':body.studio_run_id,'app_instance_id':body.app_instance_id}

def complete(runtime,principal,run,item,form,record):
    if not record['studio_run_id']:raise HTTPException(409,'No task has been created in the target Mini-App yet')
    value=owned_run(runtime,principal,form,record,record['studio_run_id'],record['app_instance_id'])
    if value['status']!='succeeded':raise HTTPException(409,'Mini-App task is not successful yet: '+value['status'])
    artifacts=[]
    for output in value['artifacts']:
        metadata=output.get('metadata',{})
        if not metadata.get('workspaceArtifactId') or not metadata.get('workspaceSessionId'):continue
        from ai2apps.api.ownership import authorize_session
        authorize_session(runtime,principal,metadata['workspaceSessionId'])
        original=runtime.workspace.get_artifact(metadata['workspaceSessionId'],metadata['workspaceArtifactId'])
        artifact=runtime.workspace.import_artifact(run.session_id,runtime.workspace.artifact_path(original),name=original.name,
            media_type=original.media_type,metadata={'studioRunId':value['id'],'appParameterInteractionId':item.id,'miniAppId':form.mini_app_id})
        artifacts.append({'id':artifact.id,'name':artifact.name,'media_type':artifact.media_type,'size_bytes':artifact.size_bytes,
            'download_url':f'/v1/platform/sessions/{run.session_id}/artifacts/{artifact.id}/download'})
    if not artifacts:raise HTTPException(409,'No durable output is available from the successful task')
    return {'capability':form.capability,'provider':form.key,'app_id':form.app_id,'mini_app_id':form.mini_app_id,
        'studio_run_id':value['id'],'artifact':artifacts[0],'artifacts':artifacts,'executed_in_app':True,'configure_only':False,
        'app_parameters':value['input'],'model':value['input'].get('modelId') or value['input'].get('model')}

ADAPTERS[KEY]=ContinuationAdapter(begin,link,complete)
