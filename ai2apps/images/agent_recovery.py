"""Imagine-owned projection of verified legacy Session outputs, never regeneration."""
import threading
from ai2apps.api.ownership import authorize_app_instance, authorize_agent_run
from ai2apps.core import SessionKind, SessionRetention, SessionVisibility
from ai2apps.storage.repositories import SessionRepository
from ai2apps.studio.repository import StudioRepository

STUDIO='ai2apps.imagine-studio'
_RECOVERY_LOCK=threading.RLock()

def recover_session_results(runtime,principal,app_instance_id):
    with _RECOVERY_LOCK:
        return _recover(runtime,principal,app_instance_id)

def _recover(runtime,principal,app_instance_id):
    authorize_app_instance(runtime,principal,app_instance_id)
    entry=runtime.extension_manager.instance_entry(app_instance_id,principal=principal)
    if entry['app_key']!=STUDIO:raise ValueError('Imagine Studio instance required')
    scope=dict(actor_id=principal.actor_user_id,installation_id=principal.installation_id,app_instance_id=app_instance_id,studio_id=STUDIO)
    repo=StudioRepository(runtime.database);count=0
    with runtime.database.transaction() as db:
        rows=db.execute("""SELECT a.id,a.session_id,a.run_id,a.created_at FROM artifacts a
            JOIN agent_runs r ON r.id=a.run_id WHERE a.status='active' AND r.status='completed'
            AND json_extract(a.metadata_json,'$.generator')='ai2apps.images'
            AND a.media_type IN ('image/png','image/jpeg','image/webp') ORDER BY a.created_at DESC LIMIT 100""").fetchall()
    for row in rows:
        try:authorize_agent_run(runtime,principal,row['run_id'])
        except Exception as error:
            from fastapi import HTTPException
            if isinstance(error,HTTPException) and error.status_code in (403,404):continue
            raise
        run=runtime.agents.get_run(row['run_id']);source=runtime.workspace.get_artifact(row['session_id'],row['id'])
        expected=f'/v1/platform/sessions/{run.session_id}/artifacts/{source.id}/download'
        parts=(run.output or {}).get('content',[])
        if not isinstance(parts,list) or not any(isinstance(p,dict) and p.get('type')=='image_url' and isinstance(p.get('image_url'),dict) and p['image_url'].get('artifact_id')==source.id and p['image_url'].get('url')==expected for p in parts):continue
        source_id='session-image:'+source.id
        with runtime.database.transaction() as db:
            if db.execute('SELECT 1 FROM studio_artifacts a JOIN studio_runs r ON r.id=a.run_id WHERE a.source_id=? AND r.actor_id=? AND r.installation_id=? AND r.app_instance_id=? AND r.studio_id=?',
                (source_id,principal.actor_user_id,principal.installation_id,app_instance_id,STUDIO)).fetchone():continue
            home=db.execute("SELECT id FROM sessions WHERE app_instance_id=? AND is_home=1 AND status='active' LIMIT 1",(app_instance_id,)).fetchone()
            previous=db.execute("SELECT a.id,a.session_id,a.status FROM artifacts a JOIN sessions s ON s.id=a.session_id WHERE s.app_instance_id=? AND json_extract(a.metadata_json,'$.recoveredAgentArtifactId')=? LIMIT 1",(app_instance_id,source.id)).fetchone()
        # Retired copies are a deletion marker. Never resurrect a removed Studio result.
        if previous and previous['status']!='active':continue
        from ai2apps.images.history import ImagineStudioHistoryRepository
        if source.size_bytes>64*1024*1024:continue
        ImagineStudioHistoryRepository._image(runtime.workspace.artifact_path(source).read_bytes())
        sessions=SessionRepository(runtime.database)
        session=sessions.get(home['id']) if home else sessions.create(app_instance_id=app_instance_id,title=STUDIO,is_home=True,session_kind=SessionKind.APP,visibility=SessionVisibility.UNLISTED,retention=SessionRetention.DURABLE)
        # Reuse an interrupted import, and keep deletion ownership separate from Chat.
        copy=runtime.workspace.get_artifact(previous['session_id'],previous['id']) if previous else runtime.workspace.import_artifact(session.id,runtime.workspace.artifact_path(source),name=source.id+'-'+source.name,media_type=source.media_type,metadata={'recoveredAgentArtifactId':source.id,'agentRunId':run.id})
        url=f'/v1/platform/sessions/{session.id}/artifacts/{copy.id}/download'
        repo.import_legacy_artifact(**scope,mini_app_id='ai2apps.imagine.text-to-image',mini_app_version='1.0.0',title=source.name,
            input_data={'agentRunId':run.id,'sourceSessionId':source.session_id,'recovered':True,'model':source.metadata.get('model')},
            source_id=source_id,name=source.name,media_type=copy.media_type,preview_url=url,download_url=url,created_at=row['created_at'],
            metadata={'workspaceSessionId':session.id,'workspaceArtifactId':copy.id,'sourceAgentArtifactId':source.id,'agentRunId':run.id,'modelId':source.metadata.get('model')})
        count+=1
    return {'recovered':count}
