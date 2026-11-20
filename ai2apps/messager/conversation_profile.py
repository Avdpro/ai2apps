"""Device-owned Bot conversation model shared by Desktop and Mobile."""
import json

from ai2apps.model_worker.reasoning_capabilities import ReasoningEffortError, adapt_reasoning_effort

_UNSET = object()
_LEVELS = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')


def supported_reasoning_efforts(runtime, model_id):
    """Resolve the actual route, never infer support from a model's name."""
    if not model_id or model_id.startswith(('cloud/ai2apps/', 'fusion/')):
        return []
    required = False
    if model_id.startswith('cloud/'):
        resolve = getattr(getattr(runtime, 'model_manager', None), 'resolve_cloud_model', None)
        provider = resolve(model_id) if resolve else None
        control = ((provider or {}).get('capabilities') or {}).get('reasoningControl')
    else:
        from ai2apps.model_providers import resolve_package_model
        package = resolve_package_model(runtime, model_id)
        reasoning = (package.metadata.get('reasoning') or {}) if package else {}
        if reasoning.get('mode') == 'none':
            return []
        required = reasoning.get('mode') == 'required'
        control = reasoning.get('effort_control')
    if not control or control.get('format') == 'none':
        return []
    # Several generic levels can map to the same wire request. Show one
    # choice for each distinct request, preferring the native level's name.
    aliases = control.get('aliases', {})
    choices = {}
    for level in _LEVELS:
        if level == 'none' and required:
            continue
        if level not in (control.get('efforts') or []) and level not in aliases and not (
            level == 'none' and control.get('can_disable')
        ):
            continue
        try:
            payload = adapt_reasoning_effort({'reasoning_effort': level}, control)
        except ReasoningEffortError:
            continue
        key = json.dumps(payload, sort_keys=True)
        if key not in choices or level == aliases.get(level, level):
            choices[key] = level
    return [level for level in _LEVELS if level in choices.values()]


def reasoning_options_for_run(runtime, actor, bot_id, model_id):
    # A different model/channel must never inherit a saved explicit level.
    with runtime.database.transaction() as db:
        row = db.execute('SELECT model_id,reasoning_effort FROM messager_bot_conversation_models WHERE actor=? AND bot_id=?',
                         (actor, bot_id)).fetchone()
    effort = row['reasoning_effort'] if row and row['model_id'] == model_id else None
    return {'reasoning_effort': effort} if effort and effort in supported_reasoning_efforts(runtime, model_id) else {}


def settings(runtime, actor, bot_id, *, model_id=None, expected_revision=None, reasoning_effort=_UNSET):
    directory=runtime.messager_bots
    directory.scope(actor,{'bot_id':bot_id})
    if model_id is not None:
        if not isinstance(model_id,str) or not 1<=len(model_id)<=300 or model_id!=model_id.strip() or any(ord(c)<32 for c in model_id):raise ValueError('Invalid conversation model')
    supported = supported_reasoning_efforts(runtime, model_id) if model_id is not None else None
    with runtime.database.transaction(write=model_id is not None) as db:
        row=db.execute('SELECT model_id,revision,reasoning_effort FROM messager_bot_conversation_models WHERE actor=? AND bot_id=?',(actor,bot_id)).fetchone()
        revision=row['revision'] if row else 0
        effort=row['reasoning_effort'] if row else None
        if model_id is not None:
            if expected_revision!=revision:raise ValueError('Bot model changed; reload before saving')
            if reasoning_effort is not _UNSET:
                if reasoning_effort is not None and reasoning_effort not in supported:
                    raise ValueError('Thinking level is unavailable for this model and provider')
                effort=reasoning_effort
            elif not row or row['model_id']!=model_id or effort not in supported:
                effort=None
            revision+=1
            db.execute('''INSERT INTO messager_bot_conversation_models(actor,bot_id,model_id,revision,reasoning_effort)
                VALUES(?,?,?,?,?) ON CONFLICT(actor,bot_id) DO UPDATE SET model_id=excluded.model_id,
                revision=excluded.revision,reasoning_effort=excluded.reasoning_effort''',(actor,bot_id,model_id,revision,effort))
            selected=model_id
        else:selected=row['model_id'] if row else None
        # Migrate the last actual foreground dialogue choice for older profiles.
        # Never use another Bot, a worker task model, or browser-global preferences.
        effective=selected
        if not effective:
            row=db.execute('''SELECT r.input_json FROM messager_dialogue_turns t
                JOIN agent_runs r ON r.id=t.run_id WHERE t.actor=? AND t.bot_id=?
                ORDER BY t.rowid DESC LIMIT 1''',(actor,bot_id)).fetchone()
            effective=json.loads(row['input_json']).get('model') if row else None
    manager=getattr(runtime,'model_manager',None)
    if not effective and manager:
        defaults=manager.default_models()
        effective=next((defaults.get(k) for k in ('work_agent','work_standard','work_complex') if defaults.get(k)),None) or manager.resolve_default_model('work_agent')
    if supported is None:
        supported=supported_reasoning_efforts(runtime,effective)
    return {'model_id':selected,'effective_model':effective,'revision':revision,
            'reasoning_effort':effort if effort in supported else None,'supported_reasoning_efforts':supported}
