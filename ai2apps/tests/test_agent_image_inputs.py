import base64
import io
import json
import pytest
from PIL import Image
from ai2apps.chat import ChatRepository
from ai2apps.agents.image_inputs import project_uploaded_images, PREVIEW_BYTES
from ai2apps.agents.context import bound_request
from test_app_interactions import runtime


def test_large_uploads_become_owned_originals_and_bounded_previews(runtime):
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='uploads')[0].session.id
    data=io.BytesIO();Image.effect_noise((1800,1800),100).convert('RGB').save(data,format='PNG')
    raw=data.getvalue()
    url='data:image/png;base64,'+base64.b64encode(raw).decode()
    messages=[{'role':'user','content':[{'type':'image_url','image_url':{'url':url}},{'type':'image_url','image_url':{'url':url}},{'type':'text','text':'合影'}]}]
    assert len(json.dumps(messages)) > 524288
    converted=project_uploaded_images(messages,runtime.workspace,session)
    assert messages[0]['content'][0]['image_url']['url']==url
    assert converted==project_uploaded_images(messages,runtime.workspace,session)
    content=converted[0]['content'];artifact_id=content[0]['text'].split('artifact_id=')[1].split('.')[0]
    artifact=runtime.workspace.get_artifact(session,artifact_id)
    assert runtime.workspace.artifact_path(artifact).read_bytes()==raw
    other=ChatRepository(runtime.database,runtime.events).create_thread(title='other')[0].session.id
    with pytest.raises(Exception):runtime.workspace.get_artifact(other,artifact_id)
    assert len(base64.b64decode(content[1]['image_url']['url'].split(',')[1])) <= PREVIEW_BYTES
    bound_request({'messages':converted},base_count=1,max_bytes=524288)


def test_bad_image_is_rejected_and_urls_not_fetched(runtime):
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='bad')[0].session.id
    messages=[{'role':'user','content':[{'type':'image_url','image_url':{'url':'https://example.invalid/private.png'}}]}]
    assert project_uploaded_images(messages,runtime.workspace,session)==messages
    messages[0]['content'][0]['image_url']['url']='data:image/png;base64,aW52YWxpZA=='
    with pytest.raises((ValueError,OSError)):project_uploaded_images(messages,runtime.workspace,session)


def test_memory_pressure_and_summary_use_model_image_projection(runtime, monkeypatch):
    from types import SimpleNamespace
    from ai2apps.agents.general import GeneralAgentExecutor
    from ai2apps.agents.session_memory import SessionMemory
    from ai2apps.context_engine import Node, Surface

    session = ChatRepository(runtime.database, runtime.events).create_thread(title='memory images')[0].session.id
    data = io.BytesIO()
    Image.effect_noise((900, 900), 100).convert('RGB').save(data, format='PNG')
    original_url = 'data:image/png;base64,' + base64.b64encode(data.getvalue()).decode()
    messages = [
        {'role': 'user', 'content': 'draw panda'},
        {'role': 'assistant', 'content': [{'type': 'image_url', 'image_url': {
            'url': '/v1/platform/sessions/' + session + '/artifacts/art_panda/download', 'artifact_id': 'art_panda'}}]},
        {'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': original_url}}]},
        {'role': 'assistant', 'content': 'photo received'},
        {'role': 'user', 'content': 'make a group photo'},
        {'role': 'assistant', 'content': 'ready'},
    ]
    surface = Surface(session, tuple(Node.message(str(i), m) for i, m in enumerate(messages)))
    executor = object.__new__(GeneralAgentExecutor)
    executor.workspace = runtime.workspace
    memory = SessionMemory(runtime.database, runtime.events, None, project=executor._project_model_messages)
    monkeypatch.setattr(memory, '_snapshot', lambda *args: surface)
    context = SimpleNamespace(run=SimpleNamespace(id='projection-test', session_id=session, input={}), steps=[])
    request = {'model': 'test', 'messages': executor._project_model_messages(messages, session)}
    assert len(json.dumps(messages)) > 524288
    assert len(json.dumps(request)) < 100000
    # A few turns with a large original must not trigger automatic compression.
    assert memory.action(context, None, request) is None
    action = memory.action(context, None, request, force=True)
    assert action is not None
    payload = json.dumps(action.request['messages'])
    assert '/v1/platform/sessions/' not in payload
    assert 'art_panda' in payload
    assert original_url not in payload
    assert messages[2]['content'][0]['image_url']['url'] == original_url
    # Transaction source remains byte-identical to original historical records.
    from ai2apps.agents.session_memory import START
    with runtime.database.transaction() as db:
        pending = memory._events(db, session, (START,))[-1]
    assert any(original_url in item['body_json'] for item in pending['source'])
    assert 'art_panda' in pending['material_artifact_ids']
    assert any(identifier != 'art_panda' for identifier in pending['material_artifact_ids'])


def test_compaction_keeps_artifact_ids_when_model_summary_omits_them():
    from types import SimpleNamespace
    from ai2apps.agents.compaction import artifact_references, _memory
    sources = [{'role': 'tool', 'content': {'artifact': {'id': 'art_output123'}}},
               {'role': 'assistant', 'content': 'Uploaded image artifact_id=art_upload456. Use original.'},
               {'role': 'assistant', 'content': '{"material_artifact_ids":["art_previous789"]}'}]
    ids = artifact_references(sources)
    assert ids == ['art_output123', 'art_previous789', 'art_upload456']
    memory = _memory(SimpleNamespace(id='step1'), {}, 'reader', [], ids)
    assert json.loads(memory['content'])['material_artifact_ids'] == ids
