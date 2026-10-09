from types import SimpleNamespace as NS
import pytest
from ai2apps.intelligence import site_agents
from ai2apps.intelligence.collector import IntelligenceCollector
from ai2apps.intelligence.models import SourceInput
from ai2apps.agent_builder.compiler import COMPILER_VERSION


def test_selection_checks_owner_status_and_type(monkeypatch):
    generation = NS(id='version', draft_id='agent', status=NS(value='active'), compiler_version=COMPILER_VERSION, ir={})
    draft = NS(id='agent', agent_type=NS(value='web'))
    class Repo:
        def __init__(self, db): pass
        def get_generation(self, id, owner):
            assert (id, owner) == ('version', 'alice')
            return generation
        def get_draft(self, id, owner):
            assert (id, owner) == ('agent', 'alice')
            return draft
    monkeypatch.setattr(site_agents, 'AgentBuilderRepository', Repo)
    runtime = NS(database=None)
    assert site_agents.selected_agent(runtime, 'alice', 'version')['explicit']
    generation.status.value = 'inactive'
    with pytest.raises(ValueError): site_agents.selected_agent(runtime, 'alice', 'version')
    generation.status.value = 'active'
    generation.ir = {'capability_exports': [{}, {}]}
    with pytest.raises(ValueError): site_agents.selected_agent(runtime, 'alice', 'version')
    generation.ir = {}
    draft.agent_type.value = 'python'
    with pytest.raises(ValueError): site_agents.selected_agent(runtime, 'alice', 'version')


def test_explicit_recipe_precedes_automatic_and_propagates_failure(monkeypatch):
    collector = object.__new__(IntelligenceCollector)
    collector.runtime = object()
    source = {'list_agent_generation_id': 'chosen'}
    monkeypatch.setattr(site_agents, 'selected_agent', lambda runtime, owner, id: {'generation_id': id})
    assert collector.recipe('alice', source, 'list') == {'generation_id': 'chosen'}
    def failed(*args): raise ValueError('unavailable')
    monkeypatch.setattr(site_agents, 'selected_agent', failed)
    with pytest.raises(ValueError): collector.recipe('alice', source, 'list')


def test_source_defaults_and_independent_bindings():
    source = SourceInput(name='site', url='https://example.com')
    assert source.list_agent_generation_id == source.article_agent_generation_id == ''
    source = SourceInput(name='site', url='https://example.com', list_agent_generation_id='list-v', article_agent_generation_id='body-v')
    assert source.model_dump()['article_agent_generation_id'] == 'body-v'
