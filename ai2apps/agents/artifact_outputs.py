"""Bounded, metadata-only projection of successful durable Tool outputs.

References are evidence, never authority: consumers recheck Session ownership.
No remote URL, raw path, arbitrary nested result or model prose is interpreted.
"""
import re
from ai2apps.core import RepositoryError

_PATH = re.compile(r'/v1/platform/sessions/([A-Za-z0-9_-]{1,256})/artifacts/([A-Za-z0-9_-]{1,256})/download')


def artifact_reference(url):
    match = _PATH.fullmatch(url) if isinstance(url, str) else None
    return match.groups() if match else None


def output_artifacts(steps, workspace, session_id, *, allow_session=None):
    if workspace is None:
        return []
    found = {}
    for step in steps:
        if step.kind != 'tool' or step.status.value != 'completed' or not isinstance(step.output, dict):
            continue
        output = step.output
        # The settled host form envelope is the only supported result wrapper.
        if isinstance(output.get('result'), dict) and output['result'].get('executed_in_app') is True:
            output = output['result']
        candidates = []
        if isinstance(output.get('artifact'), dict):
            candidates.append(output['artifact'].get('download_url'))
        if isinstance(output.get('files'), list):
            candidates.extend(f.get('url') for f in output['files'][:64] if isinstance(f, dict))
        # Older owner adapters published this standard Studio reference.
        if not any(isinstance(url, str) for url in candidates):
            candidates.append(output.get('downloadUrl'))
        for url in candidates:
            ref = artifact_reference(url)
            if ref is None or ref in found:
                continue
            sid, aid = ref
            if sid != session_id and (allow_session is None or not allow_session(sid)):
                continue
            try:
                asset = workspace.get_artifact(sid, aid)
            except RepositoryError:
                continue
            found[ref] = dict(session_id=sid, artifact_id=aid, filename=asset.name,
                media_type=asset.media_type, size_bytes=asset.size_bytes, url=url)
            if len(found) >= 64:
                return list(found.values())
    return list(found.values())


def bind_output_materials(runtime, principal, session_id, schema, values):
    """Copy an explicitly referenced prior output of this same Chat, once.

    Current owner access and recorded provenance are both required. No arbitrary
    owned Session search, paths, name matching, or semantic parameter aliases.
    """
    from copy import deepcopy
    from fnmatch import fnmatchcase
    def allowed(sid):
        try:
            session=runtime.extension_manager.sessions.get(sid)
            runtime.extension_manager.require_instance_access(session.app_instance_id,principal)
            return True
        except Exception:
            return False
    if not allowed(session_id):raise ValueError('Target material Session unavailable')
    result=deepcopy(values);outputs=None
    for key,rule in schema.get('properties',{}).items():
        asset=rule.get('x-ai2apps-asset') or (rule.get('items') or {}).get('x-ai2apps-asset')
        if not isinstance(asset,dict) or asset.get('storage')!='artifact' or key not in result:continue
        raw=result[key];ids=raw if isinstance(raw,list) else [raw];bound=[]
        for aid in ids:
            if not isinstance(aid,str) or not aid.startswith('art_'):bound.append(aid);continue
            try:runtime.workspace.get_artifact(session_id,aid);bound.append(aid);continue
            except RepositoryError:pass
            if outputs is None:
                with runtime.database.transaction() as db:
                    runs=db.execute('SELECT id FROM agent_runs WHERE session_id=? ORDER BY created_at DESC LIMIT 128',(session_id,)).fetchall()
                outputs=[f for r in runs for f in output_artifacts(runtime.agents.list_steps(r['id']),runtime.workspace,session_id,allow_session=allowed)]
            observed=next((f for f in outputs if f['artifact_id']==aid),None)
            if observed is None:bound.append(aid);continue
            accepts=[s.strip() for s in asset.get('accept','*/*').split(',')]
            if not any(fnmatchcase(observed['media_type'],m) for m in accepts):raise ValueError('Recorded output does not match the declared material type')
            # Recheck source authority immediately before resolving and copying.
            if not allowed(observed['session_id']):raise ValueError('Source material access changed')
            original=runtime.workspace.get_artifact(observed['session_id'],aid)
            copied=runtime.workspace.import_artifact(session_id,runtime.workspace.artifact_path(original),name=original.name,media_type=original.media_type,
                metadata={'source_session_id':observed['session_id'],'source_artifact_id':aid})
            bound.append(copied.id)
        result[key]=bound if isinstance(raw,list) else bound[0]
    return result
