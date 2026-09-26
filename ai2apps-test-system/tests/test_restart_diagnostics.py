import plistlib
import subprocess
import pytest
from types import SimpleNamespace
from ai2apps_test.accounts import TestAppAccountSession as Session, TestAccountLoginError as LoginError


def test_launch_failure_records_redacted_stderr(tmp_path, monkeypatch):
    app = tmp_path / 'Test.app'
    (app / 'Contents').mkdir(parents=True)
    (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier':'com.ai2apps.desktop.test', 'AI2AppsInstanceID':'test'}))
    session = Session.__new__(Session)
    session.app = app
    events = []
    session._launch_diagnostic = lambda **fields: events.append(fields)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr='LaunchServices denied token=secret-value'))
    with pytest.raises(LoginError, match='open exit 1') as error:
        session._launch()
    assert 'secret-value' not in str(error.value)
    assert events[-1]['exitCode'] == 1
    assert 'secret-value' not in events[-1]['stderr']
    assert 'LaunchServices denied' in events[-1]['stderr']


def test_restart_local_uses_existing_helper_without_open(tmp_path, monkeypatch):
    from ai2apps_test import pipeline_actions as actions
    session = SimpleNamespace()
    monkeypatch.setattr(actions, 'TestAppAccountSession', lambda *a, **kw: session)
    monkeypatch.setattr(actions, '_local_pid', lambda _: 123)
    calls = []
    client = SimpleNamespace(restart_local=lambda **kw: calls.append(kw))
    monkeypatch.setattr(actions, '_helper_client', lambda *a: client)
    monkeypatch.setattr(actions, '_wait_new_local', lambda s, pid, timeout: calls.append(pid))
    state = {}
    assert actions.execute_pipeline_action(tmp_path, 'restart-local', state)['status'] == 'passed'
    assert calls == [{'actor_user_id': 'ai2apps-test-harness'}, 123]
    assert not any(e['event'] == 'launch_command' for e in state['_actionDiagnostics'])


def test_start_helper_reuses_instance_started_by_login(tmp_path, monkeypatch):
    from ai2apps_test import pipeline_actions as actions
    session = SimpleNamespace()  # No launch method: opening again is a failure.
    monkeypatch.setattr(actions, 'TestAppAccountSession', lambda *a, **kw: session)
    monkeypatch.setattr(actions, '_local_pid', lambda _: 123)
    monkeypatch.setattr(actions, '_process_pid', lambda *a: 456)
    checks = []
    monkeypatch.setattr(actions, '_wait_new_local', lambda *a: checks.append('local'))
    monkeypatch.setattr(actions, '_wait_new_shell', lambda *a: checks.append('shell'))
    assert actions.execute_pipeline_action(tmp_path, 'start-helper', {})['status'] == 'passed'
    assert checks == ['local', 'shell']


def test_reset_does_not_relaunch_before_login(tmp_path, monkeypatch):
    from ai2apps_test import pipeline_actions as actions
    monkeypatch.setattr(actions, 'TestAppAccountSession', lambda *a, **kw: SimpleNamespace())
    calls = []
    monkeypatch.setattr(actions, 'reset_test_instance', lambda *a, **kw: calls.append('reset'))
    assert actions.execute_pipeline_action(tmp_path, 'reset-data', {})['status'] == 'passed'
    assert calls == ['reset']


def test_helper_only_launch_validates_and_targets_embedded_helper(tmp_path, monkeypatch):
    session = Session.__new__(Session)
    session.app = tmp_path / 'Test.app'
    helper = session.app / 'Contents/Library/LoginItems/AI2AppsHelper.app'
    (helper / 'Contents').mkdir(parents=True)
    (session.app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': 'com.ai2apps.desktop.test', 'AI2AppsInstanceID': 'test'}))
    info = helper / 'Contents/Info.plist'
    info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.ai2apps.desktop.test.helper'}))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stderr='')
    monkeypatch.setattr(subprocess, 'run', run)
    session._launch(helper_only=True)
    assert calls == [['open', '-g', str(helper)]]
    info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.ai2apps.desktop.helper'}))
    with pytest.raises(LoginError, match='identity'):
        session._launch(helper_only=True)
    assert len(calls) == 1
