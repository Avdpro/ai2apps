"""C4.1.2 owner grants; discovery and actual consultation admission."""
from dataclasses import replace
import pytest
from test_app_interactions import runtime
from test_app_chat_durable import bind_identity
from test_bot_communication import fixture,P


def test_remove_access_hides_entry_but_retains_permission_epoch(runtime):
    a,b,*_=fixture(runtime);s=runtime.messager_bot_access
    s.set_link('local',a['id'],b['id'],True,s.catalog('local',a['id'])['revision'])
    epoch=s.link('local',a['id'],b['id'])['revision']
    revision=s.catalog('local',a['id'])['revision']
    s.remove_link('local',a['id'],b['id'],revision)
    assert not s.catalog('local',a['id'])['outgoing']
    assert b['id'] in {x['id'] for x in s.catalog('local',a['id'])['candidates']}
    assert not s.link('local',a['id'],b['id'])['enabled']
    with pytest.raises(ValueError,match='reload'):
        s.set_link('local',a['id'],b['id'],True,revision)
    s.set_link('local',a['id'],b['id'],True,s.catalog('local',a['id'])['revision'])
    assert s.catalog('local',a['id'])['outgoing'][0]['enabled']
    assert s.link('local',a['id'],b['id'])['revision']>epoch


def test_private_discovery_management_and_both_views_share_one_directional_grant(runtime):
    a,b,sid,rid,ctx,comm=fixture(runtime);s=runtime.messager_bot_access
    assert s.mode('local',b['id'])=='public'
    assert b['id'] in {x['id'] for x in comm.targets('local',a['id'])}
    s.set_mode('local',b['id'],'private',s.catalog('local',b['id'])['revision'])
    assert b['id'] not in {x['id'] for x in comm.targets('local',a['id'])}
    with pytest.raises(PermissionError,match='Target unavailable'):comm.propose({'target_bot_id':b['id'],'question':'known private ID'},ctx)
    assert b['id'] in {x['id'] for x in s.catalog('local',a['id'])['candidates']}
    rev=s.catalog('local',a['id'])['revision'];s.set_link('local',a['id'],b['id'],True,rev)
    assert s.catalog('local',b['id'])['incoming'][0]['id']==a['id']
    assert s.catalog('local',a['id'])['outgoing'][0]['enabled']
    assert not s.link('local',b['id'],a['id'])['enabled']
    with pytest.raises(ValueError,match='reload'):s.set_link('local',a['id'],b['id'],False,rev)
    s.set_link('local',a['id'],b['id'],False,s.catalog('local',b['id'])['revision'])
    assert not s.catalog('local',b['id'])['incoming']
    assert not s.catalog('local',a['id'])['outgoing'][0]['enabled']
    assert not s.visible('local',a['id'],b['id'])
    s.set_mode('local',b['id'],'public',s.catalog('local',b['id'])['revision'])
    assert s.visible('local',a['id'],b['id']) and not s.link('local',a['id'],b['id'])['enabled']


def test_first_contact_approval_grants_use_and_second_consultation_is_admitted_without_review(runtime):
    a,b,sid,rid,ctx,comm=fixture(runtime);s=runtime.messager_bot_access
    result=comm.propose({'target_bot_id':b['id'],'question':'First supplied question'},ctx)
    row=comm.get('local',a['id'],result['request_id']);assert row['status']=='pending' and row['run_id'] is None
    accepted=comm.decide('local',a['id'],row['id'],row['review_hash'],'approve')
    assert accepted['run_id'] and s.link('local',a['id'],b['id'])['enabled']
    next_result=comm.propose({'target_bot_id':b['id'],'question':'Second supplied question'},replace(ctx,invocation_id='second-contact'))
    assert next_result['sent'] and comm.get('local',a['id'],next_result['request_id'])['run_id']
    s.set_mode('local',b['id'],'private',s.catalog('local',b['id'])['revision'])
    assert s.visible('local',a['id'],b['id'])
    s.set_link('local',a['id'],b['id'],True,s.catalog('local',a['id'])['revision'])
    assert not runtime.agents.get_run(accepted['run_id']).cancel_requested
    s.set_link('local',a['id'],b['id'],False,s.catalog('local',a['id'])['revision'])
    assert runtime.agents.get_run(accepted['run_id']).cancel_requested
    s.set_link('local',a['id'],b['id'],True,s.catalog('local',a['id'])['revision'])
    with pytest.raises(PermissionError,match='revoked'):s.validate('consultation',row['id'],'local',a['id'],b['id'])
    assert runtime.agents.get_run(accepted['run_id']).cancel_requested
    from ai2apps.messager.bot_access import BotUseAccess
    restored=BotUseAccess(runtime,runtime.messager_bots)
    assert restored.mode('local',b['id'])=='private' and restored.link('local',a['id'],b['id'])['enabled']
    with pytest.raises(PermissionError):restored.validate('consultation',row['id'],'local',a['id'],b['id'])


def test_private_switch_cancels_unapproved_public_contact_and_self_remains_available(runtime):
    a,b,sid,rid,ctx,comm=fixture(runtime);s=runtime.messager_bot_access
    pending=comm.propose({'target_bot_id':b['id'],'question':'Wait for approval'},ctx)
    s.set_mode('local',b['id'],'private',s.catalog('local',b['id'])['revision'])
    row=comm.get('local',a['id'],pending['request_id']);assert row['status']=='cancelled' and row['run_id'] is None
    assert comm.decide('local',a['id'],row['id'],row['review_hash'],'approve')['status']=='cancelled'
    assert not s.link('local',a['id'],b['id'])['enabled']
    assert s.visible('local',b['id'],b['id']) and s.link('local',b['id'],b['id'])['implicit']
    with pytest.raises(PermissionError):s.catalog('someone-else',b['id'])


@pytest.mark.asyncio
async def test_authorized_private_delegation_skips_contact_review_but_keeps_sensitive_approval_and_revoke(runtime):
    from test_bot_delegation import start,until
    r=runtime
    try:
        a,b,sid,calls,provider,card,parent=await start(r,special=True,bot_use=True)
        s=r.messager_bot_delegation;access=r.messager_bot_access
        row=await until(lambda:(value if (value:=s.row(card['id']))['child_job'] else None))
        child=await until(lambda:(job if (job:=r.messager_dialogue.row(row['child_job']))['worker_run'] else None))
        def pending():
            actual=r.agents.get_run(child['worker_run'])
            assert actual.status.value not in ('failed','cancelled','interrupted','completed'),(actual.status.value,actual.error,actual.output)
            return bool(r.agents.list_interactions(actual.id))
        await until(pending)
        assert row['status']=='running' and not calls
        access.validate('delegation',row['id'],'local',a['id'],b['id'])
        root=s.graph.edge(row['id'])['root']
        access.set_link('local',a['id'],b['id'],False,access.catalog('local',b['id'])['revision'])
        assert s.graph.root(root)['status']=='stopped' and r.agents.get_run(child['worker_run']).cancel_requested
        assert access.catalog('local',a['id'])['outgoing'][0]['enabled'] is False
        assert not access.visible('local',a['id'],b['id']) and not calls
        access.set_link('local',a['id'],b['id'],True,access.catalog('local',a['id'])['revision'])
        assert s.graph.root(root)['status']=='stopped' and not calls
        with pytest.raises(PermissionError):access.validate('delegation',row['id'],'local',a['id'],b['id'])
    finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_owner_api_mutations_require_origin_and_target_caller_endpoints_are_one_relation(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    a,b,sid,rid,ctx,comm=fixture(runtime)
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        base='/messager/bots/'
        catalog=(await client.get(base+a['id']+'/bot-access')).json()
        path=base+a['id']+'/bot-access/targets/'+b['id']
        body={'revision':catalog['revision'],'enabled':True}
        assert (await client.put(path,json=body)).status_code==403
        response=await client.put(path,json=body,headers={'Origin':'http://test'});assert response.status_code==200,response.text
        inbound=(await client.get(base+b['id']+'/bot-access')).json();assert inbound['incoming'][0]['id']==a['id']
        response=await client.put(base+b['id']+'/bot-access/callers/'+a['id'],json={'revision':inbound['revision'],'enabled':False},headers={'Origin':'http://test'})
        assert response.status_code==200 and not response.json()['incoming']
        outbound=(await client.get(base+a['id']+'/bot-access')).json();assert outbound['outgoing'][0]['enabled'] is False


def test_old_once_scoped_review_cannot_silently_create_persistent_use(runtime):
    import json
    a,b,sid,rid,ctx,comm=fixture(runtime)
    result=comm.propose({'target_bot_id':b['id'],'question':'Original once-scoped request'},ctx)
    row=comm.get('local',a['id'],result['request_id']);value=json.loads(row['value_json']);value.pop('bot_use_revision')
    with runtime.database.transaction(write=True) as db:db.execute('UPDATE messager_bot_consultations SET value_json=? WHERE id=?',(json.dumps(value),row['id']))
    with pytest.raises(PermissionError,match='new review'):comm.decide('local',a['id'],row['id'],row['review_hash'],'approve')
    assert not runtime.messager_bot_access.link('local',a['id'],b['id'])['enabled']
