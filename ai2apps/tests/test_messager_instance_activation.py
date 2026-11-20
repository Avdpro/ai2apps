"""Messager's production availability matches its actual Runtime registration gate."""
import pytest
from ai2apps.apps.system import _messager_launcher_status, SYSTEM_APP_MANIFESTS


@pytest.mark.parametrize('instance', ['default', 'main', 'test', 'dev', 'app-dev', ''])
@pytest.mark.parametrize('supervised', ['helper', ''])
def test_instance_activation(monkeypatch, instance, supervised):
    monkeypatch.setenv('AI2APPS_INSTANCE_ID', instance)
    monkeypatch.setenv('AI2APPS_SUPERVISED', supervised)
    monkeypatch.delenv('AI2APPS_DEVELOPMENT_SOURCE_ROOT', raising=False)
    assert _messager_launcher_status() == 'active'


def test_primary_manifest():
    apps = {app['id']: app for app in SYSTEM_APP_MANIFESTS}
    nav = apps['ai2apps.messager']['navigation']
    assert nav['status'] == 'active'
    assert nav['pinned_default']
    assert nav['order'] == min(app['navigation']['order'] for app in apps.values())
    assert apps['ai2apps.general-chat']['navigation']['order'] > apps['ai2apps.ai-browser']['navigation']['order']
