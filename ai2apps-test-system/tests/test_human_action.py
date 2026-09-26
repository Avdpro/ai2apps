import threading
import time
import pytest
from ai2apps_test import human_action as human
from ai2apps_test.state import atomic_write_json
from ai2apps_test.catalog_validation import validate_pipeline


def setup_run(path):
    atomic_write_json(path / 'state.json', {'status':'running', 'currentCaseId':'manual'})
    return {'id':'manual', 'humanInstructions':'请测试麦克风', 'confirmTimeoutSeconds':1}


def test_validation():
    value = {'id':'test', 'name':'Test', 'steps':[{'id':'one', 'type':'action', 'action':'human-test', 'humanInstructions':'test', 'confirmTimeoutSeconds':10}]}
    assert validate_pipeline(value) == []
    value['steps'][0]['confirmTimeoutSeconds'] = True
    assert validate_pipeline(value)


def test_timeout_skips(tmp_path, monkeypatch):
    case = setup_run(tmp_path)
    case['confirmTimeoutSeconds'] = 0
    result = human.execute(tmp_path, case, lambda:False)
    assert result['status'] == 'skipped'
    assert '超时' in result['summary']


def test_confirm_and_reason_and_single_submission(tmp_path, monkeypatch):
    case = setup_run(tmp_path)
    monkeypatch.setattr(human.subprocess, 'Popen', lambda *a, **kw: None)
    result = []
    worker = threading.Thread(target=lambda: result.append(human.execute(tmp_path, case, lambda:False)))
    worker.start()
    try:
        deadline = time.monotonic() + 2
        while not human.current(tmp_path) and time.monotonic() < deadline:
            time.sleep(.01)
        value = human.current(tmp_path)
        with pytest.raises(ValueError):
            human.submit(tmp_path, {'id':value['id'], 'action':'passed'})
        human.submit(tmp_path, {'id':value['id'], 'action':'mute'})
        human.submit(tmp_path, {'id':value['id'], 'action':'start'})
        with pytest.raises(ValueError):
            human.submit(tmp_path, {'id':value['id'], 'action':'failed', 'reason':' '})
        human.submit(tmp_path, {'id':value['id'], 'action':'blocked', 'reason':'设备缺失'})
        with pytest.raises(ValueError):
            human.submit(tmp_path, {'id':value['id'], 'action':'passed'})
    finally:
        worker.join(3)
    assert not worker.is_alive()
    assert result[0]['status'] == 'blocked'
    assert result[0]['details']['source'] == 'human'


def test_cancel_and_stale_submission(tmp_path):
    case = setup_run(tmp_path)
    assert human.execute(tmp_path, case, lambda:True)['status'] == 'skipped'
    with pytest.raises(ValueError):
        human.submit(tmp_path, {'id':'stale', 'action':'start'})


def test_finalize_refuses_pending_human_without_releasing_account(tmp_path, monkeypatch):
    from ai2apps_test.runner import finalize_run
    atomic_write_json(tmp_path / 'state.json', {'status':'awaiting_agent', 'results':{},
        'plan':{'pipeline':{'id':'test'}, 'cases':[{'id':'human', 'action':'human-test'}]}})
    monkeypatch.setattr('ai2apps_test.runner.find_run', lambda *args: tmp_path)
    def forbidden(*args):
        raise AssertionError('must not release the account')
    monkeypatch.setattr('ai2apps_test.runner.release_for_run', forbidden)
    with pytest.raises(ValueError, match='pending human'):
        finalize_run(tmp_path, 'run')
    assert human.read_json(tmp_path / 'state.json')['results'] == {}
