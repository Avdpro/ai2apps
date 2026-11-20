"""Bot mention resolution and existing collaboration admission, using fixtures."""
import json
import pytest

from ai2apps.messager.bot_references import resolve
from test_app_interactions import runtime, wait
from test_bot_capability_discovery import setup, P
from test_app_chat_durable import bind_identity, response
from test_bot_delegation import until
from ai2apps.messager.delegation import DELEGATE


def test_named_ids_legacy_names_duplicates_and_renames(runtime):
    source, sid, _, _ = setup(runtime)
    directory = runtime.messager_bots
    target = directory.create('local', '情报总结', 'Summarize requested information')
    access = runtime.messager_bot_access
    expected = [{'id': target['id'], 'name': target['name']}]
    for text in (f"使用/@情报总结(`{target['id']}`)",
                 f"/@情报总结（`{target['id']}`）", f"/@{target['id']}", '/@情报总结'):
        assert resolve(directory, access, 'local', source['id'], text) == expected
    assert resolve(directory, access, 'local', source['id'],
                   f"/@情报总结(`{target['id']}`) 再问 /@{target['id']}") == expected
    directory.create('local', '情报总结', 'Another specialist')
    with pytest.raises(ValueError, match='同名'):
        resolve(directory, access, 'local', source['id'], '/@情报总结')
    directory.update('local', target['id'], 'New name', target['duty'])
    assert resolve(directory, access, 'local', source['id'],
                   f"/@旧名称(`{target['id']}`)") == [{'id': target['id'], 'name': 'New name'}]
    with pytest.raises(ValueError, match='不可用'):
        resolve(directory, access, 'local', source['id'], '/@New name(`missing-id`)')
    quoted = directory.create('local', 'Bot (special) / "A"', 'Quoted label')
    mention = '/@' + json.dumps(quoted['name']) + '(`' + quoted['id'] + '`)'
    assert resolve(directory, access, 'local', source['id'], mention)[0]['id'] == quoted['id']
    # Resolution is durable per submitted turn, and does not create a use grant.
    run = runtime.messager_dialogue.submit(P(), source['id'], sid, 'mention', mention, 'fixture', [])
    assert runtime.agents.get_run(run).input['owner_context']['message_bot_references'][0]['id'] == quoted['id']
    assert not access.link('local', source['id'], quoted['id'])['enabled']
    assert runtime.messager_dialogue.submit(P(), source['id'], sid, 'mention', mention, 'fixture', []) == run
    fresh = runtime.messager_dialogue.submit(P(), source['id'], sid, 'new-topic', 'Hello', 'fixture', [])
    assert runtime.agents.get_run(fresh).input['owner_context']['message_bot_references'] == []


def test_code_foreign_deleted_private_and_reference_limit(runtime):
    source, sid, _, _ = setup(runtime)
    directory, access = runtime.messager_bots, runtime.messager_bot_access
    target = directory.create('local', 'Target', 'Help')
    ref = '/@Target(`' + target['id'] + '`)'
    assert resolve(directory, access, 'local', source['id'], '`/@missing` ```\n' + ref + '\n```') == []
    foreign = directory.create('other', 'Other owner', 'Help')
    for text in ('/@' + foreign['id'], '/@missing'):
        with pytest.raises(ValueError, match='不可用'):
            runtime.messager_dialogue.submit(P(), source['id'], sid, text, text, 'fixture', [])
    for text in ('/@', '/@Target(``)', '/@Target(`bad.id`)', '/@Target(`incomplete'):
        with pytest.raises(ValueError, match='格式'):
            resolve(directory, access, 'local', source['id'], text)
    with pytest.raises(ValueError, match='8'):
        resolve(directory, access, 'local', source['id'], ' '.join([ref] * 9))
    access.set_mode('local', target['id'], 'private', access.catalog('local', target['id'])['revision'])
    with pytest.raises(ValueError, match='尚未'):
        resolve(directory, access, 'local', source['id'], ref)
    access.set_link('local', source['id'], target['id'], True, access.catalog('local', source['id'])['revision'])
    assert resolve(directory, access, 'local', source['id'], ref)[0]['id'] == target['id']
    with runtime.database.transaction(write=True) as db:
        db.execute('INSERT INTO messager_bot_archive(bot_id,actor,deleted) VALUES(?,?,1)', (target['id'], 'local'))
    with pytest.raises(ValueError, match='不可用'):
        resolve(directory, access, 'local', source['id'], ref)


@pytest.mark.asyncio
async def test_reference_reaches_worker_and_existing_delegation_review(runtime):
    source, sid, calls, _ = setup(runtime)
    target = runtime.messager_bots.create('local', 'Information specialist', 'Summarize information')
    expected = [{'id': target['id'], 'name': target['name']}]
    observed = []

    async def model(request):
        text = '\n'.join(str(m.get('content', '')) for m in request['messages'])
        assert 'message_bot_references' in text
        assert target['id'] in text and target['name'] in text
        if 'Decide quickly' in request['messages'][0]['content']:
            assert '/@Name(`ID`)' in text
            return response(text=json.dumps({'kind': 'task', 'text': 'Queued', 'title': 'Consult specialist'}))
        observed.append(request)
        return response(DELEGATE, {'target_bot_id': target['id'], 'title': 'Specialist summary',
                                   'instructions': 'Summarize the requested fixture information'})

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        prompt = '/@Information specialist(`' + target['id'] + '`) summarize the requested information'
        rid = runtime.messager_dialogue.submit(P(), source['id'], sid, 'mention-delegation', prompt, 'fixture', [])
        assert runtime.agents.get_run(rid).input['owner_context']['message_bot_references'] == expected
        await wait(runtime, rid, 'completed')
        card = await until(lambda: next(iter(runtime.messager_bot_delegation.work('local', source['id'])), None))
        assert card['status'] == 'pending'
        row = runtime.messager_bot_delegation.row(card['id'])
        assert row['target_bot'] == target['id'] and observed
        assert not calls
        assert not runtime.messager_bot_access.link('local', source['id'], target['id'])['enabled']
    finally:
        await runtime.stop_background_tasks()
