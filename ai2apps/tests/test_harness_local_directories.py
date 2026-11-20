"""Real files and SQLite; model decisions are fixtures, no external model calls."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from ai2apps.app_chat.service import AppChatOwner
from ai2apps.processes.local_directories import LocalDirectories, requested_roots
from ai2apps.services.capability_routing import CapabilityInvocationError
from test_app_chat_durable import P, bind_identity, response
from test_app_interactions import runtime, wait
from test_bot_dialogue import job_wait


def test_literal_directory_resolution_does_not_grant_home_or_siblings(tmp_path):
    roots = requested_roots(['我的桌面有个Comic目录，你把里面的漫画翻译成英文'], tmp_path)
    assert roots == {str(tmp_path / 'Desktop/Comic')}
    assert requested_roots(['Read the Comic folder on my Desktop'], tmp_path) == roots
    assert str(tmp_path) not in requested_roots(['Use ~'], tmp_path)
    assert not requested_roots(['Read ~/Desktop/../private'], tmp_path)


@pytest.mark.parametrize('text,location,child', [
    ('帮我把桌面下Comic目录里的漫画翻译成英文', 'Desktop', 'Comic'),
    ('读取桌面下面的「Pages」文件夹', 'Desktop', 'Pages'),
    ('整理文稿下方的Reports目录', 'Documents', 'Reports'),
    ('列出下载下边有个Receipts目录', 'Downloads', 'Receipts'),
])
def test_named_standard_folder_location_phrasings(text, location, child, tmp_path):
    assert requested_roots([text], tmp_path) == {str(tmp_path/location/child)}


@pytest.mark.parametrize('app', ['ai2apps.knowledge', 'ai2apps.gallery'])
@pytest.mark.asyncio
async def test_scoped_host_import_isolated_by_owner_and_session(runtime, tmp_path, app):
    root = tmp_path / 'Desktop/Pages';root.mkdir(parents=True)
    (root / 'page.png').write_bytes(b'actual-source-page')
    (root / 'sub').mkdir();(root / 'sub/two.png').write_bytes(b'second-page')
    outside = tmp_path / 'private.png';outside.write_bytes(b'not-authorized')
    (root / 'escape.png').symlink_to(outside)
    registration = app + '.directory-fixture'
    owner = AppChatOwner(registration, app, '1', (), lambda actor, scope:scope, lambda *args:None,
        {'type':'object'}, exports=lambda scope:(), source_user_requests=lambda actor, scope, run:[f'Read "{root}"'])
    runtime.app_chat.register(owner)
    sid = runtime.app_chat.open(P(), registration, {}, {})
    run = runtime.agents.create_run(session_id=sid, agent_key='ai2apps.app-chat-agent',
        input={'prompt':'fixture', 'model':'fixture'})[0]
    context = replace(runtime.tools.context_for_session(caller_id='fixture', session_id=sid), trace_id=run.id)
    service = LocalDirectories(runtime, home=tmp_path)
    args = {'root':str(root)}
    await service.prepare(args, context)
    listing = service.list(args, context)
    assert {x['path'] for x in listing['items']} == {'sub','page.png','escape.png'}
    assert not next(x for x in listing['items'] if x['kind']=='symlink')['readable']
    result = service.import_files({**args,'files':['page.png','sub/two.png']}, context)
    assert len(result['files']) == 2
    asset = runtime.workspace.get_artifact(sid, result['files'][0]['artifact_id'])
    assert runtime.workspace.artifact_path(asset).read_bytes() == b'actual-source-page'
    again = service.import_files({**args,'files':['page.png']}, context)
    assert again['files'][0]['artifact_id'] == asset.id
    assert (root / 'page.png').read_bytes() == b'actual-source-page'
    for bad in ({'root':str(tmp_path)}, {**args,'files':['../private.png']}):
        with pytest.raises(CapabilityInvocationError) as failure:await service.prepare(bad, context)
        assert failure.value.details['submitted'] is False
    with pytest.raises(OSError):service.import_files({**args,'files':['escape.png']}, context)
    (root / 'link').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):service.list({**args,'path':'link'}, context)
    alias = tmp_path / 'alias';alias.symlink_to(root, target_is_directory=True)
    runtime.app_chat.owners[registration] = replace(owner,
        source_user_requests=lambda actor, scope, run:[f'Read "{alias}"'])
    with pytest.raises(OSError):service.list({'root':str(alias)}, context)
    runtime.app_chat.owners[registration] = owner
    with pytest.raises(PermissionError):runtime.app_chat.source_user_requests(run.id, 'foreign-session')
    runtime.app_chat.owners[registration] = replace(owner, source_user_requests=None)
    with pytest.raises(PermissionError):service.list(args, context)


@pytest.mark.asyncio
async def test_import_limits_publish_no_partial_inputs(runtime, tmp_path, monkeypatch):
    import ai2apps.processes.local_directories as module
    root = tmp_path/'bounded';root.mkdir()
    (root/'one.png').write_bytes(b'1234');(root/'two.png').write_bytes(b'5678')
    service = LocalDirectories(runtime)
    monkeypatch.setattr(service, 'root', lambda args, context:root)
    class Context:
        session_id = 'not-published'
        trace_id = 'not-published'
    monkeypatch.setattr(module, 'MAX_BATCH', 6)
    with pytest.raises(ValueError, match='bounded size'):
        service.import_files({'files':['one.png','two.png']}, Context())
    monkeypatch.setattr(module, 'MAX_FILE', 3)
    with pytest.raises(ValueError, match='regular files'):
        service.import_files({'files':['one.png']}, Context())
    assert (root/'one.png').read_bytes() == b'1234'


@pytest.mark.asyncio
@pytest.mark.parametrize('prompt', [
    '我的桌面有个Comic目录，你把里面的漫画翻译成英文',
    '帮我把桌面下Comic目录里的漫画翻译成英文',
])
async def test_bot_uses_harness_access_and_original_request_not_model_materials(runtime, tmp_path, monkeypatch, prompt):
    from ai2apps.messager.bots import REGISTRATION
    import ai2apps.processes.local_directories as module
    home = tmp_path / 'home';root=home/'Desktop/Comic';root.mkdir(parents=True)
    (root/'page.png').write_bytes(b'fixture comic page')
    monkeypatch.setattr(module.Path, 'home', classmethod(lambda cls: home))
    runtime.harness_local_directories.home = home
    bot=runtime.messager_bots.create('local','Directory task','Use tools to inspect named directories')
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    seen=[]
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:
            return response(text=json.dumps({'kind':'task','title':'排队翻译 Comic 漫画','step_label':'正在排队扫描 Comic','text':'Queued'}))
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if result:=next((r for r in results if r.get('files')),None):
            seen.extend(result['files']);return response(text='Imported the actual source file')
        if any(r.get('items') for r in results):return response('host.directory.import',{'root':'~/Desktop/Comic','files':['page.png']})
        if not any(r.get('providers') for r in results):return response('app.describe',{'capability':'host.directory.list'})
        return response('host.directory.list',{'root':'~/Desktop/Comic'})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source=runtime.messager_dialogue.submit(P(),bot['id'],sid,'directory-task',prompt,'fixture',[])
        await wait(runtime,source,'completed');job=await job_wait(runtime,source,'running')
        assert job['title']=='翻译 Comic 漫画'
        assert runtime.messager_dialogue.label(job['id'])=='扫描 Comic'
        worker=job['worker_run'];await wait(runtime,worker,'waiting_capability')
        pending=next(i for i in runtime.agents.list_interactions(worker) if i.status.value=='pending')
        access=runtime.messager_bot_app_access;review=access.request('local',bot['id'],worker,pending.id)
        assert review['app']['app_id']=='ai2apps.harness' and review['task_tree']
        assert not seen
        assert access.allow('local',bot['id'],worker,pending.id,review['request_hash'])['continued']
        await job_wait(runtime,source,'completed')
        assert len(seen)==1
        assert runtime.workspace.artifact_path(runtime.workspace.get_artifact(job['worker_session'],seen[0]['artifact_id'])).read_bytes()==b'fixture comic page'
        assert not access.current('local',bot['id'])[1].get('ai2apps.harness')
        requests=runtime.app_chat.source_user_requests(worker,job['worker_session'])
        assert requests==(prompt,)
    finally:await runtime.stop_background_tasks()


def test_work_names_do_not_copy_queue_status():
    from ai2apps.messager.dialogue import BotDialogue
    for source, expected in [('排队扫描并翻译 Comic 目录漫画','扫描并翻译 Comic 目录漫画'),
                             ('正在排队扫描 Comic','扫描 Comic'), ('Queued for translation','translation'),
                             ('排队算法研究','排队算法研究')]:
        assert BotDialogue.work_label(source)==expected
