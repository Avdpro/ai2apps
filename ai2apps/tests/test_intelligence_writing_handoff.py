import json
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from ai2apps.doc_studio.repository import Repository
from ai2apps.intelligence import doc_studio_pack, writing_handoff
from ai2apps.storage.database import PlatformDatabase
from ai2apps.tests.test_intelligence_api import client
from ai2apps.tests.test_intelligence_transfer import seed


@pytest.fixture
def handoff(tmp_path):
    store, channel, article = seed(tmp_path / 'intelligence')
    database = PlatformDatabase(tmp_path / 'platform.sqlite')
    database.initialize()
    runtime = SimpleNamespace(database=database, events=None,
                              config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)))
    return runtime, store, channel, article


def test_scoped_pack_preserves_original_and_image_anchor(handoff):
    runtime, store, channel, article = handoff
    article['original_content'] = {'title': 'Original', 'body': 'Original text'}
    source_url = article['sources'][0]['url']
    with store.connect() as db:
        db.execute('UPDATE articles SET data=? WHERE id=?', (json.dumps(article), article['id']))
        db.execute('INSERT INTO pages VALUES(?,?,?,?,?)', (
            'alice', channel['id'], source_url, 'page-hash', json.dumps({'text': 'Cached source text'}),
        ))
    selection = writing_handoff.Selection(scope='article', scope_id=article['id'])
    summary = writing_handoff.prepare(runtime, store, 'alice', channel['id'], selection)
    assert summary['articles'] == [{'title': 'Watch', 'images': 1}]
    assert writing_handoff.prepare(runtime, store, 'alice', channel['id'], selection)['id'] == summary['id']
    repo = Repository(runtime.database)
    entry = repo.pack('alice', summary['id'])['entries'][0]
    assert entry['original_content']['body'] == 'Original text'
    assert entry['source_originals'][0]['body'] == 'Cached source text'
    assert entry['images'][0]['anchor'] == entry['paragraphs'][0]['id']
    with pytest.raises(KeyError):
        repo.pack('bob', summary['id'])
    with pytest.raises(KeyError):
        writing_handoff.prepare(runtime, store, 'bob', channel['id'], selection)
    with pytest.raises(ValueError):
        writing_handoff.prepare(runtime, store, 'alice', channel['id'],
                                writing_handoff.Selection(scope='article', scope_id='unknown'))


@pytest.mark.asyncio
async def test_gallery_saves_actual_archive_and_deduplicates_identical_retry(handoff, monkeypatch):
    runtime, store, channel, article = handoff
    summary = writing_handoff.prepare(
        runtime, store, 'alice', channel['id'], writing_handoff.Selection(scope='channel'),
    )
    monkeypatch.setattr(doc_studio_pack, 'load_image', lambda *_: (b'fixture', 'image/jpeg'))
    first = await writing_handoff.save_gallery(runtime, store, 'alice', summary['id'])
    second = await writing_handoff.save_gallery(runtime, store, 'alice', summary['id'])
    assert first['created'] and not second['created']
    assert first['asset']['id'] == second['asset']['id']
    assert first['missing_images'] == 0
    gallery = writing_handoff.GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / 'gallery')
    path = gallery.asset_path('alice', first['asset']['id'])[1]
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['entries'][0]['source_id'] == article['id']
        assert archive.read(next(iter(manifest['attachments'].values()))) == b'fixture'
    with pytest.raises(KeyError):
        await writing_handoff.save_gallery(runtime, store, 'bob', summary['id'])


@pytest.mark.asyncio
async def test_missing_image_keeps_source_and_is_reported(handoff, monkeypatch):
    runtime, store, channel, _ = handoff
    summary = writing_handoff.prepare(runtime, store, 'alice', channel['id'],
                                     writing_handoff.Selection(scope='channel'))

    def unavailable(*_):
        raise TimeoutError

    monkeypatch.setattr(doc_studio_pack, 'load_image', unavailable)
    pack = Repository(runtime.database).pack('alice', summary['id'])
    stream, missing = await writing_handoff._gallery_archive(store, 'alice', pack)
    with ZipFile(stream) as archive:
        manifest = json.loads(archive.read('manifest.json'))
    assert missing == 1
    assert manifest['entries'][0]['body']
    assert list(manifest['unembedded_images']) == [pack['entries'][0]['images'][0]['url']]


@pytest.mark.asyncio
async def test_http_handoff_to_new_and_existing_projects(client):
    import asyncio

    from ai2apps.api.doc_studio import create_doc_studio_router
    from ai2apps.identity import RequestPrincipal
    from ai2apps.intelligence.models import ChannelInput

    runtime = client.app.state.runtime
    principal = RequestPrincipal.legacy_local()
    owner = principal.actor_user_id
    client.app.include_router(create_doc_studio_router(lambda: runtime, lambda: principal))
    store = runtime.intelligence_collector.store
    channel = store.save_channel(owner, ChannelInput(name='Watches', interests='Watches').model_dump())
    articles = [
        store.import_article(owner, channel['id'], {
            'title': title, 'summary': title, 'body': title, 'images': [],
            'sources': [{'url': f'https://example.org/{index}', 'title': title}],
        }, f'https://example.org/{index}')
        for index, title in enumerate(['First', 'Second'])
    ]

    project_id = None
    for index, article in enumerate(articles):
        response = client.post(f"/intelligence/channels/{channel['id']}/material-packs",
                               json={'scope': 'selection', 'article_ids': [article['id']]})
        assert response.status_code == 200, response.text
        data = {'pack_id': response.json()['id'], 'project_id': project_id, 'request_id': f'import-{index}'}
        response = client.post('/doc-studio/imports', json=data)
        assert response.status_code == 202, response.text
        task = response.json()
        assert client.post('/doc-studio/imports', json=data).json()['id'] == task['id']
        await runtime.system_tasks.tick()
        await asyncio.gather(*runtime.system_tasks.jobs.values())
        result = client.get(f"/doc-studio/tasks/{task['id']}").json()
        assert result['status'] == 'completed', result
        project_id = result['result']['project_id']

    projects = client.get('/doc-studio/projects').json()
    assert [project['id'] for project in projects] == [project_id]
    project = client.get('/doc-studio/projects/' + project_id).json()
    assert {item['title'] for item in project['materials']} == {'First', 'Second'}


@pytest.mark.asyncio
async def test_mobile_gateway_can_save_a_pack_to_gallery(handoff, monkeypatch):
    import base64

    from ai2apps.identity import RequestPrincipal
    from ai2apps.web import mobile_app_gateway

    runtime, _, _, _ = handoff
    principal = RequestPrincipal.legacy_local()
    monkeypatch.setattr(doc_studio_pack, 'load_image', lambda *_: (b'fixture', 'image/jpeg'))
    from ai2apps.intelligence.models import ChannelInput
    from ai2apps.intelligence.store import IntelligenceStore

    data = IntelligenceStore(runtime.config.paths.artifacts_path / 'intelligence')
    owner = principal.actor_user_id
    channel = data.save_channel(owner, ChannelInput(name='News', interests='News').model_dump())
    url = 'https://example.org/story'
    data.import_article(owner, channel['id'], {
        'title': 'Story', 'summary': 'Summary', 'body': 'Body', 'sources': [{'url': url, 'title': 'Source'}],
        'images': [{'url': 'https://example.org/cover.jpg'}],
    }, url)
    prefix = '/v1/platform/intelligence'
    spec = {'api': {'module': 'intelligence', 'factory': 'create_intelligence_router', 'prefix': prefix}}

    async def post(path, body=None):
        return await mobile_app_gateway.api_response(runtime, principal, spec, {
            'verb': 'POST', 'path': prefix + path, 'headers': {'content-type': 'application/json'},
            'body': base64.b64encode(json.dumps(body).encode()).decode() if body else '',
        })

    response = await post(f"/channels/{channel['id']}/material-packs", {'scope': 'channel'})
    assert response.status_code == 200, response.text
    result = await post(f"/material-packs/{response.json()['id']}/gallery")
    assert result.status_code == 200, result.text
    assert result.json()['created']
