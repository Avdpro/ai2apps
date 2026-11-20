"""Read the real snapshot protocol in deterministic model fixtures.

Formatting, historical text and JSON whitespace are not execution state.
This helper reconstructs data only; it never supplies execution authority.
"""
from copy import deepcopy
import json


def current_state(request):
    state = None
    for message in request['messages']:
        content = message.get('content')
        if message.get('role') != 'user' or not isinstance(content, str):
            continue
        if not content.startswith('Current UI snapshot'):
            continue
        payload = json.loads(content[content.index('{'):])
        if content.startswith('Current UI snapshot delta'):
            if state is None or not isinstance(payload.get('base_snapshot'), str):
                raise AssertionError('Snapshot delta requires its earlier base')
            for change in payload['changes']:
                path = change['path']
                if not path:
                    if change['op'] == 'set':
                        state = deepcopy(change['value'])
                        continue
                    target = state
                else:
                    target = state
                    for part in path[:-1]:
                        target = target[part]
                if change['op'] == 'set':
                    target[path[-1]] = deepcopy(change['value'])
                elif change['op'] == 'remove':
                    del target[path[-1]]
                elif change['op'] == 'splice':
                    if path:
                        target = target[path[-1]]
                    start = change['start']
                    target[start:start + change['delete']] = deepcopy(change['items'])
                else:
                    raise AssertionError('Unknown snapshot operation')
        else:
            state = payload
    return state or {}


def owner_context(request):
    return current_state(request).get('owner_context', {})
