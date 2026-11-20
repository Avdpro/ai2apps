"""Bounded, host-owned model defaults; preferences never grant model access.

Owners capture the snapshot. Consumers supply their current compatible catalog
and normal system default, preserving their own validation and execution policy.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

from ai2apps.model_manager import DEFAULT_MODEL_PURPOSES

_current = ContextVar('ai2apps_model_preferences', default=None)
_profile = ContextVar('ai2apps_model_preference_profile', default='normal')


def scoped_profile():
    return _profile.get()


def validate(snapshot):
    if snapshot is None:
        return None
    if not isinstance(snapshot, dict) or set(snapshot) - {'schema', 'routes'}:
        raise ValueError('Invalid model preference snapshot')
    if snapshot.get('schema') != 'ai2apps.model-preferences/v1':
        raise ValueError('Unknown model preference snapshot')
    routes = snapshot.get('routes')
    if not isinstance(routes, list) or len(routes) > len(DEFAULT_MODEL_PURPOSES) * 2:
        raise ValueError('Model preference snapshot exceeds routing bounds')
    keys = set()
    for route in routes:
        if not isinstance(route, dict) or set(route) - {'purpose', 'profile', 'model', 'memory_id', 'revision', 'bot_id', 'available'}:
            raise ValueError('Invalid model preference route')
        if route.get('purpose') not in DEFAULT_MODEL_PURPOSES or route.get('profile') not in ('normal', 'privacy'):
            raise ValueError('Unknown model purpose or profile')
        if not isinstance(route.get('model'), str) or not 1 <= len(route['model']) <= 512:
            raise ValueError('Invalid preferred model')
        for key in ('memory_id', 'bot_id'):
            if not isinstance(route.get(key), str) or not 1 <= len(route[key]) <= 256:
                raise ValueError('Invalid preference provenance')
        if type(route.get('revision')) is not int or route['revision'] < 1:
            raise ValueError('Invalid preference revision')
        key = (route['purpose'], route['profile'])
        if key in keys:
            raise ValueError('Duplicate model preference route')
        keys.add(key)
        if 'available' in route and type(route['available']) is not bool:
            raise ValueError('Invalid preference availability')
    return deepcopy(snapshot)


@contextmanager
def scope(snapshot, *, profile='normal'):
    if profile not in ('normal', 'privacy'):
        raise ValueError('Unknown model profile')
    token = _current.set(validate(snapshot))
    profile_token = _profile.set(profile)
    try:
        yield
    finally:
        _current.reset(token)
        _profile.reset(profile_token)


def choose(runtime, purpose, default=None, *, explicit=None, choices=None, profile='normal'):
    """Resolve one operation's default against its current owner catalog.

    Explicit arguments are retained for the consumer's normal checks. An invalid
    preference falls back within the same effective profile, never to normal.
    """
    from ai2apps.task_llm import effective_profile
    effective = effective_profile(runtime, profile, _profile.get())
    if explicit:
        return explicit, {'source': 'explicit', 'purpose': purpose, 'profile': effective}
    snapshot = _current.get() or {}
    route = next((r for r in snapshot.get('routes', [])
                  if r['purpose'] == purpose and r['profile'] == effective), None)
    available = None if choices is None else {m['id'] for m in choices if m.get('ready', True)}
    if route and route.get('available', True) and (available is None or route['model'] in available):
        return route['model'], {'source': 'model_memory', **deepcopy(route)}
    result = {'source': 'system_default', 'purpose': purpose, 'profile': effective}
    if route:
        result['fallback_reason'] = 'preferred_model_unavailable_or_incompatible'
        result['preference'] = deepcopy(route)
    return default, result
