"""Declared image-input support for the exact execution route, never name hints."""
from __future__ import annotations


def vision_declaration(model):
    raw=model.get('capabilities') if isinstance(model,dict) else getattr(model,'capabilities',None)
    keys=('imageInput','image_input','image_recognition','vision','multimodal')
    if isinstance(raw,dict):
        for key in keys:
            if isinstance(raw.get(key),bool):return 'supported' if raw[key] else 'unsupported'
    elif isinstance(raw,(list,tuple,set,frozenset)):
        if set(raw)&set(keys):return 'supported'
    return 'undeclared'


async def resolve_vision(runtime,model_id,actor_user_id):
    """Query under the same actor/route as invocation; return bounded diagnostics."""
    def result(status,source):
        return {'status':status,'source':source,'model':model_id,
            'reason':None if status=='supported' else 'current_model_vision_'+status}
    if not model_id:return result('not_found','unresolved')
    manager=getattr(runtime,'model_manager',None)
    source='unresolved'
    try:
        source=(manager.model_source(model_id) if manager and hasattr(manager,'model_source') else
                'ai2apps_cloud' if model_id.startswith('cloud/ai2apps/') else
                'local_byok' if model_id.startswith('cloud/') else 'local_runtime')
        if source=='ai2apps_cloud':
            from ai2apps.identity import IdentityRepository,RequestPrincipal
            principal=RequestPrincipal.legacy_local() if actor_user_id=='local' else IdentityRepository(runtime.database).local_principal_for(actor_user_id)
            headers=runtime.cloud_ai_authorization_headers(principal)
            response=await runtime.cloud.request('GET','/v1/ai/models',headers=headers)
            try:
                if response.status_code!=200:return result('lookup_failed',source)
                payload=response.json()
            finally:await response.aclose()
            items=payload.get('items') if isinstance(payload,dict) else None
            if not isinstance(items,list):return result('lookup_failed',source)
            identifier=model_id.removeprefix('cloud/').removeprefix('ai2apps/')
            model=next((m for m in items if isinstance(m,dict) and m.get('id')==identifier),None)
        elif source=='local_byok':
            model=None
            for provider in manager.list_cloud():
                for item in provider.get('models',[]):
                    if 'cloud/'+provider['id']+'/'+item['id']==model_id:
                        if provider.get('enabled') is False or item.get('enabled') is not True:return result('disabled',source)
                        model=item
        else:model=runtime.model_invocations.model(model_id)
        if model is None:return result('not_found',source)
        if isinstance(model,dict) and model.get('enabled') is False:return result('disabled',source)
        return result(vision_declaration(model),source)
    except Exception:
        # Never turn access/network/catalog failures into a negative capability claim.
        return result('lookup_failed',source)
