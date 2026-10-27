"""Shared LLM routing policy for Mini-App foreground and durable Task calls.

Execution ownership stays with the caller: a mount may cancel foreground work,
whereas durable Tasks survive the UI disconnecting.
"""
from ai2apps.model_worker.reasoning_capabilities import validate_reasoning_effort

TIERS = ('simple', 'standard', 'complex')
PROFILES = ('normal', 'privacy')


def effective_profile(runtime, requested='normal', declared='normal'):
    if requested not in PROFILES or declared not in PROFILES:
        raise ValueError('Unknown model profile')
    return 'privacy' if ('privacy' in (requested, declared) or
        getattr(runtime, 'privacy_mode', False) is True) else 'normal'


def resolve_task_model(runtime, complexity, profile='normal', *, declared='normal',
                       pinned_routes=None):
    if complexity not in TIERS:
        raise ValueError('Unknown task complexity')
    effective = effective_profile(runtime, profile, declared)
    # A system privacy upgrade must never reuse routes pinned in normal mode.
    if pinned_routes and effective == profile and pinned_routes.get(complexity):
        return pinned_routes[complexity]
    manager = getattr(runtime, 'model_manager', None)
    if manager is None:
        return None
    purpose = 'work_' + complexity
    return (manager.resolve_default_model(purpose, profile='privacy')
            if effective == 'privacy' else manager.resolve_default_model(purpose))


def task_payload(model_id, messages, complexity, *, max_tokens=2000, reasoning_effort=None):
    """Common request defaults; schemas and durable replay remain caller-owned."""
    if complexity not in TIERS:
        raise ValueError('Unknown task complexity')
    payload = {'model': model_id, 'messages': messages, 'max_tokens': max_tokens}
    if reasoning_effort is not None:
        payload['reasoning_effort'] = validate_reasoning_effort(reasoning_effort)
    if complexity != 'simple':
        payload['temperature'] = 0
    return payload


def prepare_task_request(runtime, request):
    """Recheck server privacy immediately before a durable model invocation."""
    validate_reasoning_effort(request.get('reasoning_effort'))
    route = request.get('_ai2apps_task_route')
    if route is None:
        return request
    payload = {key: value for key, value in request.items() if key != '_ai2apps_task_route'}
    profile = route['profile']
    tier = route['complexity']
    model = resolve_task_model(runtime, tier, profile,
        pinned_routes={tier: payload.get('model')})
    if not model:
        raise RuntimeError('No task model configured for ' + effective_profile(runtime, profile) + ' profile')
    payload['model'] = model
    return payload
