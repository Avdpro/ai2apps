"""Read-only compatibility adapter for Desktop's saved local project metadata.

This is not an App Server API. Never write Desktop state or return other settings.
"""
import json
import os
from pathlib import Path


def saved_projects(home=None):
    root = Path(home) if home is not None else Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
    try:
        with (root / '.codex-global-state.json').open('rb') as stream:
            raw = stream.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024: return []
        state = json.loads(raw)
    except (OSError, ValueError):
        return []
    if not isinstance(state, dict): return []
    result = []
    projects = state.get('local-projects')
    if isinstance(projects, dict):
        for project in projects.values():
            if not isinstance(project, dict): continue
            roots = project.get('rootPaths')
            if not isinstance(roots, list) or not roots: continue
            path = roots[0]
            if not isinstance(path, str) or not Path(path).is_absolute(): continue
            name = project.get('name')
            result.append({'path':path, 'name':name if isinstance(name, str) and name else Path(path).name,
                           'source':'desktop'})
        # An explicitly empty modern project list must not revive removed legacy roots.
        return result
    roots = state.get('electron-saved-workspace-roots', [])
    labels = state.get('electron-workspace-root-labels', {})
    if not isinstance(roots, list): return []
    if not isinstance(labels, dict): labels = {}
    for path in roots:
        if isinstance(path, str) and Path(path).is_absolute():
            name = labels.get(path)
            result.append({'path':path, 'name':name if isinstance(name, str) else Path(path).name, 'source':'desktop'})
    return result
