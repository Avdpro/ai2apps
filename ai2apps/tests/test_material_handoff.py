"""Actual owner adapters and artifact storage with fixture sources."""
from io import BytesIO
import json

import pytest

from ai2apps.core import ResourceNotFoundError
from ai2apps.agents.general import _tool_alias
from ai2apps.identity import RequestPrincipal
from ai2apps.intelligence.aaat import store
from ai2apps.messager.bots import REGISTRATION, install
from ai2apps.services.builtin_apps import gallery
from ai2apps.system_tasks.sessions import execution_session
from test_app_interactions import runtime, wait
from test_app_chat_durable import bind_identity, response


async def invoke(runtime, session, name, ids):
    scope = runtime.tools.context_for_session(caller_id='material-handoff-test', session_id=session)
    return (await runtime.tools.execute(name, {'source_ids': ids}, context=scope)).output


@pytest.mark.asyncio
async def test_owner_material_handoff(runtime, monkeypatch):
    repo = gallery(runtime)
    types = {'photo.png': 'image/png', 'clip.mp4': 'video/mp4',
             'voice.wav': 'audio/wav', 'notes.md': 'text/markdown',
             'data.pdf': 'application/pdf', 'archive.zip': 'application/zip'}
    assets = {
        repo.import_stream('local', BytesIO(name.encode()), name=name, media_type=mime)[0]['id']: (name, mime)
        for name, mime in types.items()
    }
    private = repo.import_stream('other', BytesIO(b'private'), name='private.txt')[0]
    session = execution_session(runtime, 'local', 'ai2apps.messager')
    gallery_result = await invoke(runtime, session, 'gallery.import_materials', [*assets, private['id']])
    assert gallery_result['status'] == 'partial'
    assert gallery_result['unavailable'] == [{'source_id': private['id'], 'reason': 'unavailable'}]
    assert [(f['filename'], f['media_type']) for f in gallery_result['materials']] == list(assets.values())
    repeat = await invoke(runtime, session, 'gallery.import_materials', list(assets))
    assert repeat['materials'] == gallery_result['materials']

    database = store(runtime)
    with database.connect() as connection:
        connection.executemany('INSERT INTO articles VALUES(?,?,?,?)', [
            ('public', 'local', 'channel', '{"title":"Public"}'),
            ('hidden', 'other', 'channel', '{"title":"Private"}'),
        ])
    fetches = []

    async def fetch_thumbnail(article):
        fetches.append(article['title'])
        return b'cover preview', 'image/jpeg'

    monkeypatch.setattr('ai2apps.intelligence.materials.load_article_thumbnail', fetch_thumbnail)
    intel_result = await invoke(runtime, session, 'intelligence.import_materials', ['public', 'hidden'])
    assert fetches == ['Public']
    assert intel_result['unavailable'] == [{'source_id': 'hidden', 'reason': 'unavailable'}]
    assert intel_result['status'] == 'partial'
    assert intel_result['materials'][0]['media_type'] == 'image/jpeg'

    other_session = execution_session(runtime, 'local', 'ai2apps.gallery')
    for file in gallery_result['materials'] + intel_result['materials']:
        artifact = runtime.workspace.get_artifact(session, file['artifact_id'])
        assert file['url'] == f'/v1/platform/sessions/{session}/artifacts/{artifact.id}/download'
        expected = b'cover preview' if file['source_id'] == 'public' else file['filename'].encode()
        assert runtime.workspace.artifact_path(artifact).read_bytes() == expected
        with pytest.raises(ResourceNotFoundError):
            runtime.workspace.get_artifact(other_session, artifact.id)

    notes = next(file for file in gallery_result['materials'] if file['media_type'] == 'text/markdown')
    scope = runtime.tools.context_for_session(caller_id='material-handoff-test', session_id=session)
    preview = await runtime.tools.execute('artifact.preview', {'artifact_id': notes['artifact_id'], 'limit': 5}, context=scope)
    assert preview.output['content'] == 'notes'
    assert preview.output['truncated'] is True


@pytest.mark.asyncio
async def test_material_handoff_skips_over_budget_file(runtime, monkeypatch):
    monkeypatch.setattr('ai2apps.workspace.materials.MAX_BATCH_BYTES', 5)
    repo = gallery(runtime)
    large = repo.import_stream('local', BytesIO(b'123456'), name='large.txt')[0]
    small = repo.import_stream('local', BytesIO(b'12'), name='small.txt')[0]
    session = execution_session(runtime, 'local', 'ai2apps.messager')
    result = await invoke(runtime, session, 'gallery.import_materials', [large['id'], small['id']])
    assert result['unavailable'] == [{'source_id': large['id'], 'reason': 'size_limit'}]
    assert [file['source_id'] for file in result['materials']] == [small['id']]


@pytest.mark.asyncio
async def test_bot_keeps_session_material_controls_but_excludes_unowned_tools(runtime):
    original = runtime.services.get_tool('gallery.search')
    for name in ('fixture.unowned', 'another.unowned'):
        runtime.services.ensure_tool(
            service_id=original.service_id, qualified_name=name, display_name=name,
            description='Tool with no App approval target', input_schema={'type': 'object'},
            output_schema={'type': 'object'}, effects=('network',), timeout_ms=1000,
        )
    install(runtime)
    principal = RequestPrincipal.legacy_local()
    bot = runtime.messager_bots.create('local', 'Fixture Bot', 'Use owned materials')
    session = runtime.app_chat.open(principal, REGISTRATION, {'bot_id': bot['id']}, {})
    asset = gallery(runtime).import_stream('local', BytesIO(b'Actual document text'), name='brief.txt')[0]

    async def model(request):
        names = {tool['function']['name'] for tool in request.get('tools', [])}
        assert _tool_alias('fixture.unowned') not in names
        assert _tool_alias('another.unowned') not in names
        results = [json.loads(msg['content']) for msg in request['messages'] if msg['role'] == 'tool']
        for result in reversed(results):
            if result.get('encoding') == 'utf-8':
                return response(text=result['content'])
            if result.get('materials'):
                return response('artifact.preview', {'artifact_id': result['materials'][0]['artifact_id']})
        return response('gallery.import_materials', {'source_ids': [asset['id']]})

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run = runtime.app_chat.submit(principal, session, 'material-controls', 'Read materials', 'fixture')
        completed = await wait(runtime, run, 'completed')
        assert completed.output['content'] == 'Actual document text'
        assert completed.output.get('artifacts', []) == []
        assert not runtime.agents.list_interactions(run)
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
@pytest.mark.parametrize('name,mime', [('image.png','image/png'), ('clip.mp4','video/mp4'),
                                      ('notes.md','text/markdown')])
async def test_save_session_material_to_gallery_recent(runtime,tmp_path,name,mime):
    session=execution_session(runtime,'local','ai2apps.messager')
    source=tmp_path/name;source.write_bytes(b'fixture material '+name.encode())
    artifact=runtime.workspace.import_artifact(session,source,name=name,media_type=mime)
    scope=runtime.tools.context_for_session(caller_id='save-material-test',session_id=session)
    result=await runtime.tools.execute('gallery.save_material',{'artifact_id':artifact.id},context=scope)
    assert result.output['status']=='completed' and result.output['created'] is True
    asset=result.output['asset'];assert asset['name']==name and asset['media_type']==mime
    repeat=await runtime.tools.execute('gallery.save_material',{'artifact_id':artifact.id},context=scope)
    assert repeat.output['asset']['id']==asset['id'] and repeat.output['created'] is False
    recent=gallery(runtime).list_assets('local',collection_id='recent')
    assert asset['id'] in {a['id'] for a in recent}
    other=execution_session(runtime,'local','ai2apps.gallery')
    foreign_scope=runtime.tools.context_for_session(caller_id='save-material-test',session_id=other)
    from ai2apps.services.models import ToolGatewayError
    with pytest.raises(ToolGatewayError,match='artifact not found'):
        await runtime.tools.execute('gallery.save_material',{'artifact_id':artifact.id},context=foreign_scope)


@pytest.mark.asyncio
async def test_gallery_save_name_description_and_edit(runtime, tmp_path):
    session = execution_session(runtime, 'local', 'ai2apps.messager')
    source = tmp_path / 'source.png'
    source.write_bytes(b'fixture image')
    artifact = runtime.workspace.import_artifact(session, source, name='source.png', media_type='image/png')
    scope = runtime.tools.context_for_session(caller_id='description-test', session_id=session)
    args = {'artifact_id': artifact.id, 'name': '熊猫.png', 'description': '竹林里\n戴帽子的熊猫'}
    result = (await runtime.tools.execute('gallery.save_material', args, context=scope)).output
    asset = result['asset']
    assert asset['name'] == args['name'] and asset['description'] == args['description']
    repo = gallery(runtime)
    assert repo.get_asset('local', asset['id'])['description'] == args['description']
    assert asset['id'] in {a['id'] for a in repo.list_assets('local', search='戴帽子')}
    found = (await runtime.tools.execute('gallery.search', {'query': '戴帽子'}, context=scope)).output
    assert found['assets'][0]['description'] == args['description']
    fetched = (await runtime.tools.execute('gallery.get', {'asset_id': asset['id']}, context=scope)).output
    assert fetched['asset']['description'] == args['description']
    updated = repo.update_asset('local', asset['id'], description='新说明')
    assert updated['name'] == args['name']
    assert updated['metadata']['artifact_id'] == artifact.id
    repeated = (await runtime.tools.execute('gallery.save_material', args, context=scope)).output
    assert not repeated['created'] and repeated['asset']['description'] == '新说明'
    assert repo.rename_asset('local', asset['id'], 'new.png')['description'] == '新说明'
    assert repo.update_asset('local', asset['id'], description='')['description'] == ''
    from ai2apps.gallery import GalleryError
    with pytest.raises(GalleryError):
        repo.update_asset('local', asset['id'], description='x' * 4001)
    with pytest.raises(ResourceNotFoundError):
        repo.update_asset('other-owner', asset['id'], description='forbidden')
    from ai2apps.services.models import ToolGatewayError
    for invalid in ({'name': ''}, {'description': 'x' * 4001}):
        with pytest.raises(ToolGatewayError):
            await runtime.tools.execute('gallery.save_material', {**args, **invalid}, context=scope)
