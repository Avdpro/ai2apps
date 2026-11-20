"""Signed Package Hook declarations: upper bounds only, never user authority."""

SCHEMA='ai2apps.package-event-hooks/v1'
HANDLER='event-inbox/v1'

def declaration(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)-{'schema','handler','event_types','scopes','background','details','actions'}:
        raise ValueError('Invalid Package event_hooks declaration')
    if value.get('schema')!=SCHEMA or value.get('handler')!=HANDLER:
        raise ValueError('Unsupported Package Hook interface or handler')
    events=value.get('event_types');scopes=value.get('scopes',['subjects']);actions=value.get('actions',[])
    if (not isinstance(events,list) or not 1<=len(events)<=32
            or any(not isinstance(x,str) or not 1<=len(x)<=200 or '*' in x for x in events)):
        raise ValueError('Package Hooks require explicit event types')
    if not isinstance(scopes,list) or not scopes or any(not isinstance(x,str) for x in scopes) or set(scopes)-{'subjects','owned_collection'}:raise ValueError('Invalid event scopes')
    if not isinstance(actions,list) or len(actions)>4 or any(not isinstance(x,str) or not 1<=len(x)<=100 for x in actions):raise ValueError('Invalid action declarations')
    if any(type(value.get(k,False)) is not bool for k in ('background','details')):raise ValueError('Hook permissions must be booleans')
    return {'schema':SCHEMA,'handler':HANDLER,'event_types':sorted(set(events)),'scopes':sorted(set(scopes)),
            'background':value.get('background',False),'details':value.get('details',False),'actions':sorted(set(actions))}


def validate_app(app):
    if not isinstance(app,dict):raise ValueError('Invalid App declaration')
    declaration(app.get('event_hooks'))
    minis=app.get('mini_apps',[])
    if not isinstance(minis,list) or any(not isinstance(m,dict) for m in minis):raise ValueError('Invalid Mini-App declarations')
    for mini in minis:
        d=declaration(mini.get('event_hooks'))
        if d:
            requirements=mini.get('requirements') or {}
            if not isinstance(requirements,dict):raise ValueError('Invalid Mini-App requirements')
            caps=requirements.get('capabilities',[])
            if not isinstance(caps,list) or any(not isinstance(x,(str,dict)) for x in caps):raise ValueError('Invalid Mini-App capabilities')
            names=[x if isinstance(x,str) else x.get('capability') for x in caps]
            if 'events.subscribe' not in names or d['background'] and 'events.background' not in names:
                raise ValueError('Mini-App Hook permissions must also be declared in requirements')
