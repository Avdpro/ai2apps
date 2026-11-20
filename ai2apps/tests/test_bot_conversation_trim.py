"""Real SQLite/files: trim does not control execution, memory or Access."""
import pytest
from ai2apps.core import MessageRole, RepositoryError
from ai2apps.storage.models import MessagePartInput
from ai2apps.storage.repositories import MessageRepository
from test_app_interactions import runtime
from test_app_chat_durable import bind_identity
from test_bot_capability_discovery import setup,P


def append(r,sid,role,text,metadata=None,key=None):
    return MessageRepository(r.database).append(session_id=sid,role=MessageRole(role),
        parts=[MessagePartInput(kind='text',content={'text':text})],metadata=metadata,idempotency_key=key).value.message


def test_trim_preserves_anchor_policy_memory_tasks_and_removes_owned_materials(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);service=runtime.messager_bots.history.conversation_trim()
    note=runtime.messager_bots.memory.save('local',bot['id'],'Keep this memory')
    authority=runtime.messager_bot_permissions.current('local',bot['id'])
    anchor=append(runtime,sid,'assistant','Keep me')
    attachment=runtime.documents.create(sid,filename='remove.txt',media_type='text/plain',data=b'trim input')
    original=tmp_path/'selected.txt';original.write_text('user original must stay')
    reference=runtime.documents.create_reference(sid,original)
    output=tmp_path/'output.txt';output.write_text('trim output')
    asset=runtime.workspace.import_artifact(sid,output,name='output.txt',media_type='text/plain')
    removed=append(runtime,sid,'user',attachment.id+' '+reference.id,key='old-user')
    append(runtime,sid,'assistant',asset.id,{'artifacts':[{'session_id':sid,'artifact_id':asset.id}]})
    run=runtime.messager_dialogue.submit(P(),bot['id'],sid,'task-to-preserve','A task','fixture',[])
    review=service.review('local',bot['id'],sid,anchor.id)
    assert review['deleted_materials']==3
    result=service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])
    assert result['cleanup_pending']==0 and result['conversation_revision']==1
    assert [m['content'] for m in runtime.app_chat.message_page(P(),sid)['items']]==['已记住 / Memory saved：Keep this memory','Keep me']
    assert runtime.agents.get_run(run).status.value=='queued'
    assert runtime.messager_bot_permissions.current('local',bot['id'])==authority
    assert runtime.messager_bots.memory.list('local',bot['id'])['items'][0]['id']==note['id']
    assert original.exists()
    for ref in (attachment,reference):
        with pytest.raises(RepositoryError):runtime.documents.get(sid,ref.id)
    with pytest.raises(RepositoryError):runtime.workspace.get_artifact(sid,asset.id)
    assert service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])==result
    repeated=MessageRepository(runtime.database).append(session_id=sid,role=MessageRole.USER,
        parts=[MessagePartInput(kind='text',content={'text':attachment.id+' '+reference.id})],idempotency_key='old-user')
    assert not repeated.created and repeated.value.message.id==removed.id
    from ai2apps.core import IdempotencyConflictError
    with pytest.raises(IdempotencyConflictError):
        append(runtime,sid,'user','Changed input',key='old-user')
    newest=append(runtime,sid,'user','New conversation');assert newest.sequence>removed.sequence
    assert runtime.app_chat.message_page(P(),sid)['items'][-1]['content']=='New conversation'


def test_scope_stale_confirmation_and_shared_materials(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);service=runtime.messager_bots.history.conversation_trim()
    source=tmp_path/'shared.txt';source.write_text('shared output')
    a=runtime.workspace.import_artifact(sid,source,name='shared.txt')
    anchor=append(runtime,sid,'assistant','Keep '+a.id);append(runtime,sid,'assistant','Remove '+a.id)
    review=service.review('local',bot['id'],sid,anchor.id)
    assert review['deleted_materials']==0 and review['shared_materials']==1
    append(runtime,sid,'user','Arrived after review')
    with pytest.raises(ValueError,match='changed'):service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])
    with pytest.raises(PermissionError):service.review('other',bot['id'],sid,anchor.id)
    other=runtime.messager_bots.create('local','Other','Help')
    with pytest.raises(PermissionError):service.review('local',other['id'],sid,anchor.id)
    user=append(runtime,sid,'user','Not a Bot anchor')
    with pytest.raises(ValueError):service.review('local',bot['id'],sid,user.id)
    review=service.review('local',bot['id'],sid,anchor.id);service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])
    assert runtime.workspace.artifact_path(runtime.workspace.get_artifact(sid,a.id)).exists()


def test_attachment_blob_sharing_and_active_task_inputs(runtime):
    bot,sid,_,_=setup(runtime);service=runtime.messager_bots.history.conversation_trim()
    other=runtime.messager_bots.create('local','Other','Help')
    other_sid=runtime.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':other['id']},{})
    a=runtime.documents.create(sid,filename='shared.txt',media_type='text/plain',data=b'same bytes')
    b=runtime.documents.create(other_sid,filename='other.txt',media_type='text/plain',data=b'same bytes')
    anchor=append(runtime,sid,'assistant','Anchor');append(runtime,sid,'user',a.id)
    review=service.review('local',bot['id'],sid,anchor.id);service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])
    assert runtime.documents.source_path(other_sid,b.id).read_bytes()==b'same bytes'
    active=runtime.documents.create(sid,filename='task.txt',media_type='text/plain',data=b'queued task')
    runtime.messager_dialogue.submit(P(),bot['id'],sid,'queued-with-file','Read the attachment','fixture',[active.id])
    review=service.review('local',bot['id'],sid,anchor.id);assert review['shared_materials']>=1
    service.apply('local',bot['id'],sid,anchor.id,review['review_hash']);assert runtime.documents.get(sid,active.id)


def test_cleanup_retry_does_not_delete_new_messages(runtime,monkeypatch):
    bot,sid,_,_=setup(runtime);service=runtime.messager_bots.history.conversation_trim()
    anchor=append(runtime,sid,'assistant','Anchor');a=runtime.documents.create(sid,filename='a.txt',media_type='text/plain',data=b'input')
    append(runtime,sid,'user',a.id);review=service.review('local',bot['id'],sid,anchor.id)
    retire=runtime.documents.retire
    def fail(*args):raise OSError('fixture file busy')
    monkeypatch.setattr(runtime.documents,'retire',fail)
    assert service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])['cleanup_pending']==1
    append(runtime,sid,'user','Do not delete on retry '+a.id);monkeypatch.setattr(runtime.documents,'retire',retire)
    assert service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])['cleanup_pending']==0
    assert runtime.app_chat.message_page(P(),sid)['items'][-1]['content']=='Do not delete on retry '+a.id
    assert runtime.documents.get(sid,a.id)
    assert service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])['deleted_materials']==0

@pytest.mark.asyncio
async def test_desktop_and_mobile_share_owner_review_but_keep_origin_and_mount_checks(runtime):
    from dataclasses import replace
    from fastapi import FastAPI
    import httpx
    from ai2apps.api.messager import create_messager_router
    from ai2apps.api.messager_mobile import create_messager_mobile_router
    bot,sid,_,_=setup(runtime);anchor=append(runtime,sid,'assistant','Keep');append(runtime,sid,'user','Remove')
    principal=[replace(P(),client_scope='desktop')]
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,lambda:principal[0]))
    app.include_router(create_messager_mobile_router(lambda:runtime,lambda:principal[0]))
    body={'session_id':sid,'message_id':anchor.id}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        base='/messager/bots/'+bot['id']+'/conversation-trim/'
        assert (await c.post(base+'review',json=body)).status_code==403
        result=await c.post(base+'review',json=body,headers={'origin':'http://test'})
        assert result.status_code==200,result.text
        review=result.json()
        principal[0]=replace(P(),authentication_type='owner_home_lease',client_scope='owner-home')
        mobile='/messager-mobile/bots/'+bot['id']+'/conversation-trim/'
        assert (await c.post(mobile+'review',json=body)).json()==review
        foreign=runtime.messager_bots.create('local','Separate','Help')
        assert (await c.post(mobile.replace(bot['id'],foreign['id'])+'apply',json={**body,'review_hash':review['review_hash']})).status_code==404
        response=await c.post(mobile+'apply',json={**body,'review_hash':review['review_hash']})
        assert response.status_code==200,response.text
        principal[0]=P()
        assert (await c.post(mobile+'apply',json={**body,'review_hash':review['review_hash']})).status_code==403


@pytest.mark.asyncio
async def test_queued_dialogue_can_finish_after_its_input_is_trimmed(runtime):
    import json
    from test_app_chat_durable import response
    from test_app_interactions import wait
    bot,sid,_,_=setup(runtime);service=runtime.messager_bots.history.conversation_trim()
    anchor=append(runtime,sid,'assistant','Keep')
    rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'queued-trim','Finish this queued work','fixture',[])
    review=service.review('local',bot['id'],sid,anchor.id)
    result=service.apply('local',bot['id'],sid,anchor.id,review['review_hash'])
    assert result['retired_request_ids']==['queued-trim']
    async def model(request):
        return response(text=json.dumps({'kind':'reply','text':'Queued work finished'}))
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        await wait(runtime,rid,'completed')
        messages=runtime.app_chat.message_page(P(),sid)['items']
        assert [m['content'] for m in messages]==['Keep','Queued work finished']
    finally:
        await runtime.agent_runtime.stop()
