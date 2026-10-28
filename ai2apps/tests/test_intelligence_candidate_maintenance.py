import json
import sqlite3
import pytest
from ai2apps.agent_builder.repository import AgentBuilderRepository
from ai2apps.storage import PlatformDatabase
from ai2apps.intelligence.candidate_maintenance import archive_plan, apply_plan


def test_archive_retains_references_active_and_latest_without_deleting_history(tmp_path):
    db = PlatformDatabase(tmp_path / 'platform.sqlite3'); db.initialize()
    repo = AgentBuilderRepository(db)
    def draft(owner='alice'):
        return repo.create_draft(owner_user_id=owner,name='Rule',description='',
            site_scope=['https://example.org/**'],
            source={'provenance':{'intelligence_recipe_key':'https://example.org/|list'}})
    unused, referenced, active, latest = [draft() for _ in range(4)]
    version_referenced = draft()
    generation = repo.create_generation(version_referenced, source_digest='fixture',
        compiler_version='fixture', policy_version='fixture', ir={}, report={}, valid=True)
    foreign = draft('bob')
    refs = sqlite3.connect(':memory:')
    refs.execute('CREATE TABLE source(data TEXT)')
    refs.execute('INSERT INTO source VALUES (?)',(json.dumps({'draft_id': referenced.id}),))
    refs.execute('INSERT INTO source VALUES (?)',(json.dumps({'generation_id': generation.id}),))
    with db.transaction(write=True) as c:
        c.execute("UPDATE agent_drafts SET status='active',active_generation_id='retained-version' WHERE id=?",(active.id,))
        c.execute("UPDATE agent_drafts SET updated_at='2099-01-01T00:00:00Z' WHERE id=?",(latest.id,))
        plan = archive_plan(c, [('intelligence',refs)])
        assert [r['id'] for r in plan['archive']] == [unused.id]
        apply_plan(c,plan,'2100-01-01T00:00:00Z')
    assert repo.get_draft(unused.id,'alice').status.value == 'archived'
    assert repo.get_draft(referenced.id,'alice').status.value != 'archived'
    assert repo.get_draft(version_referenced.id,'alice').status.value != 'archived'
    assert repo.get_generation(generation.id,'alice').status.value == 'validated'
    assert repo.get_draft(foreign.id,'bob').status.value != 'archived'
    assert repo.get_draft(active.id,'alice').active_generation_id == 'retained-version'
    with db.transaction(write=True) as c:
        with pytest.raises(RuntimeError): apply_plan(c,plan,'2101-01-01T00:00:00Z')
