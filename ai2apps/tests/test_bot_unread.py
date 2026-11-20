"""Display cursor isolation and monotonic read acknowledgements."""
from dataclasses import replace
import pytest
from ai2apps.core import MessageRole
from ai2apps.storage.models import MessagePartInput
from ai2apps.storage.repositories import MessageRepository
from test_bot_capability_discovery import setup,P
from test_app_interactions import runtime


def append(r,sid,role):
    return MessageRepository(r.database,r.events).append(session_id=sid,role=role,parts=[MessagePartInput(kind='text',content={'text':'fixture'})])


def test_counts_cursor_and_scope(runtime):
    bot,sid,_,_=setup(runtime);d=runtime.messager_bots;u=d.unread
    for role in (MessageRole.USER,MessageRole.ASSISTANT,MessageRole.TOOL,MessageRole.ASSISTANT):append(runtime,sid,role)
    state=u.state('local',bot['id'],sid)
    assert state['unread_count']==2 and state['first_unread_sequence']==2
    assert next(b for b in d.list('local') if b['id']==bot['id'])['unread_count']==2
    assert u.state('local',bot['id'],sid,2)['unread_count']==1
    assert u.state('local',bot['id'],sid,1)['read_sequence']==2
    append(runtime,sid,MessageRole.ASSISTANT)
    assert u.state('local',bot['id'],sid,4)['unread_count']==1
    with pytest.raises(ValueError):u.state('local',bot['id'],sid,100)
    with pytest.raises(PermissionError):u.state('foreign',bot['id'],sid,5)
    sibling=d.create('local','Sibling','Separate')
    with pytest.raises(PermissionError):u.state('local',sibling['id'],sid,5)
    assert u.state('local',bot['id'],sid,5)['unread_count']==0
    assert not u.counts('foreign')


def test_first_migration_baselines_once_and_archive_is_rejected(runtime):
    from ai2apps.messager.unread import BotUnread
    bot,sid,_,_=setup(runtime);append(runtime,sid,MessageRole.ASSISTANT)
    with runtime.database.transaction(write=True) as db:db.execute('DROP TABLE messager_bot_read_cursors')
    u=BotUnread(runtime.messager_bots)
    assert u.state('local',bot['id'],sid)['unread_count']==0
    append(runtime,sid,MessageRole.ASSISTANT);u=BotUnread(runtime.messager_bots)
    assert u.state('local',bot['id'],sid)['unread_count']==1
    with runtime.database.transaction(write=True) as db:db.execute("UPDATE app_chat_sessions SET registration='archived' WHERE session_id=?",(sid,))
    assert u.counts('local')=={}
    with pytest.raises(PermissionError):u.state('local',bot['id'],sid,2)


@pytest.mark.asyncio
async def test_read_api_rejects_foreign_and_future_cursor(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    bot,sid,_,_=setup(runtime);append(runtime,sid,MessageRole.ASSISTANT)
    principal=[P()];app=FastAPI();app.include_router(create_messager_router(lambda:runtime,lambda:principal[0]))
    base='/messager/bots/'+bot['id']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        assert (await c.get(base+'/unread',params={'session_id':sid})).json()['unread_count']==1
        assert (await c.post(base+'/read',json={'session_id':sid,'through_sequence':50})).status_code==422
        assert (await c.post(base+'/read',json={'session_id':sid,'through_sequence':True})).status_code==422
        principal[0]=replace(P(),actor_user_id='foreign')
        assert (await c.post(base+'/read',json={'session_id':sid,'through_sequence':1})).status_code==404
        principal[0]=P()
        assert (await c.post(base+'/read',json={'session_id':sid,'through_sequence':1})).json()['unread_count']==0


def test_sidebar_counts_only_visible_main_conversation(runtime):
    import json
    from ai2apps.messager.bots import REGISTRATION
    bot,sid,_,_=setup(runtime)
    other=runtime.messager_bots.create('local','Internal fixture','Worker')
    worker=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':other['id']},{})
    append(runtime,worker,MessageRole.ASSISTANT)
    with runtime.database.transaction(write=True) as db:
        db.execute('UPDATE app_chat_sessions SET scope_json=? WHERE session_id=?',
                   (json.dumps({'bot_id':bot['id'],'dialogue_job':'fixture-job'}),worker))
    u=runtime.messager_bots.unread
    assert u.counts('local')=={}
    with pytest.raises(PermissionError):u.state('local',bot['id'],worker)
    append(runtime,sid,MessageRole.ASSISTANT)
    assert u.counts('local')=={bot['id']:1}
    assert u.state('local',bot['id'],sid,1)['unread_count']==0
    assert u.counts('local')=={}
    with runtime.database.transaction(write=True) as db:
        db.execute('UPDATE app_chat_sessions SET scope_json=? WHERE session_id=?',
                   (json.dumps({'bot_id':bot['id'],'archive_id':'fixture-archive'}),worker))
    assert u.counts('local')=={}
