import json
import pytest
from ai2apps.codex.projects import saved_projects
from ai2apps.codex.manager import CodexManager


def write(home, value):
    path = home / '.codex-global-state.json'
    path.write_text(json.dumps(value))
    return path


def test_modern_names_primary_roots_and_read_only(tmp_path):
    path=write(tmp_path, {'local-projects':{'p':{'name':'Custom name', 'rootPaths':['/project','/other']},
        'bad':{'rootPaths':['relative']}, 'invalid':None}, 'secret':'must not escape'})
    before=path.read_bytes()
    assert saved_projects(tmp_path)==[{'name':'Custom name','path':'/project','source':'desktop'}]
    assert path.read_bytes()==before


def test_legacy_and_empty_modern(tmp_path):
    write(tmp_path, {'electron-saved-workspace-roots':['/project', 3],
                     'electron-workspace-root-labels':{'/project':'Legacy'}})
    assert saved_projects(tmp_path)[0]['name']=='Legacy'
    write(tmp_path, {'local-projects':{}, 'electron-saved-workspace-roots':['/deleted']})
    assert saved_projects(tmp_path)==[]


def test_missing_corrupt_and_invalid_state(tmp_path):
    assert saved_projects(tmp_path)==[]
    path=write(tmp_path, [])
    assert saved_projects(tmp_path)==[]
    path.write_text('{')
    assert saved_projects(tmp_path)==[]


@pytest.mark.asyncio
async def test_saved_projects_do_not_need_app_server(monkeypatch):
    expected=[{'name':'No sessions yet','path':'/project','source':'desktop'}]
    monkeypatch.setattr('ai2apps.codex.projects.saved_projects',lambda:expected)
    def forbidden(): raise AssertionError('Must not start App Server for saved projects')
    monkeypatch.setattr('ai2apps.codex.manager.CodexDesktop',forbidden)
    assert (await CodexManager().projects())['data']==expected
