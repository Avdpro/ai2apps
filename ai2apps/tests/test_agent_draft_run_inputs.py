from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest
from jsonschema.exceptions import ValidationError
from ai2apps.agent_builder.service import create_ir_run
from ai2apps.api import agent_builder as api


def test_draft_test_run_forwards_form_input(tmp_path, monkeypatch):
    helpers = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tests/test_ai2apps_agent_builder.py'))
    runtime = helpers['_runtime'](tmp_path)
    client = helpers['_client'](runtime, helpers['_principal']('run-input-owner'))
    source = helpers['_source']()
    source['inputs'] = {'type': 'object', 'properties': {'url': {'type': 'string'}}}
    draft = client.post('/v1/platform/agent-drafts', json={'name': 'Inputs', 'source': source, 'site_scope': source['site_scope']}).json()
    captured = {}
    def create(_runtime, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id='run_test_inputs', session_id=kwargs['session_id'], status=SimpleNamespace(value='queued'))
    monkeypatch.setattr(api, 'create_ir_run', create)
    result = client.post(f"/v1/platform/agent-drafts/{draft['id']}/runs", json={'input': {'url': 'https://www.fratellowatches.com/archives/'}})
    assert result.status_code == 202, result.text
    assert captured['invocation_input'] == {'url': 'https://www.fratellowatches.com/archives/'}


def test_run_defaults_are_applied_before_execution_and_explicit_values_win():
    captured = []
    def create_run(**kwargs):
        captured.append(kwargs['input']['parameters']['invocation_input'])
        return SimpleNamespace(id='run_inputs'), None
    runtime = SimpleNamespace(agents=SimpleNamespace(create_run=create_run), agent_runtime=SimpleNamespace(wake=lambda: None))
    ir = {'inputs': {'type': 'object', 'properties': {'url': {'type': 'string', 'default': 'https://example.com/default'}}, 'required': ['url']}, 'steps': []}
    create_ir_run(runtime, session_id='session', ir=ir, invocation_input={})
    create_ir_run(runtime, session_id='session', ir=ir, invocation_input={'url': 'https://example.com/custom'})
    assert captured == [{'url': 'https://example.com/default'}, {'url': 'https://example.com/custom'}]
    with pytest.raises(ValidationError):
        create_ir_run(runtime, session_id='session', ir=ir, invocation_input={'url': None})
    assert len(captured) == 2
