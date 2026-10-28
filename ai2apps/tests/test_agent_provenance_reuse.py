from concurrent.futures import ThreadPoolExecutor

from ai2apps.agent_builder.repository import AgentBuilderRepository
from ai2apps.storage import PlatformDatabase


def test_atomic_provenance_reuse_is_owner_key_and_lifecycle_bound(tmp_path):
    db = PlatformDatabase(tmp_path / 'platform.sqlite3')
    db.initialize()
    repo = AgentBuilderRepository(db)

    def create(owner='alice', identity='source-a'):
        return repo.create_draft(owner_user_id=owner, name='Observed candidate',
            description='', site_scope=['https://arbitrary.example/**'],
            source={'provenance': {'arbitrary_owner_key': identity}},
            reuse_provenance_key='arbitrary_owner_key')

    with ThreadPoolExecutor(max_workers=4) as pool:
        drafts = list(pool.map(lambda _: create(), range(8)))
    assert len({d.id for d in drafts}) == 1
    first = repo.get_draft(drafts[0].id, 'alice')
    assert first.revision == 8
    assert create('bob').id != first.id
    assert create(identity='source-b').id != first.id
    repo.archive_draft(first.id, 'alice', expected_revision=first.revision)
    assert create().id != first.id
