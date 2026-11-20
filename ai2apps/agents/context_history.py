"""Opt-in, creation-time Task history projection. No business identities."""
import json

PROFILE_KEY = 'agent_context_history'
PROFILE = 'stable-references/v1'
VIEW = 'agent.context.history.view'
PRELUDE = 'agent.context.history.prelude'


def enabled(connection, session_id):
    row = connection.execute('SELECT metadata_json FROM sessions WHERE id=?', (session_id,)).fetchone()
    return bool(row and json.loads(row['metadata_json'] or '{}').get(PROFILE_KEY) == PROFILE)


def snapshot_changes(previous, current, path=()):
    """Lossless data-only operations; array splices retain unchanged neighbours."""
    if previous == current:
        return []
    if isinstance(previous, dict) and isinstance(current, dict):
        changes = []
        for key in sorted(previous.keys() - current.keys()):
            changes.append({'op': 'remove', 'path': [*path, key]})
        for key, value in current.items():
            if key not in previous:
                changes.append({'op': 'set', 'path': [*path, key], 'value': value})
            else:
                changes.extend(snapshot_changes(previous[key], value, (*path, key)))
        return changes
    if isinstance(previous, list) and isinstance(current, list):
        if len(previous) == len(current):
            changes = []
            for index, value in enumerate(current):
                changes.extend(snapshot_changes(previous[index], value, (*path, index)))
            return changes
        prefix = 0
        while prefix < min(len(previous), len(current)) and previous[prefix] == current[prefix]:
            prefix += 1
        suffix = 0
        while suffix < min(len(previous), len(current)) - prefix and previous[-suffix-1] == current[-suffix-1]:
            suffix += 1
        return [{'op': 'splice', 'path': list(path), 'start': prefix,
                 'delete': len(previous)-prefix-suffix,
                 'items': current[prefix:len(current)-suffix if suffix else len(current)]}]
    return [{'op': 'set', 'path': list(path), 'value': current}]
