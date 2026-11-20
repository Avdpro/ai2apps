"""ASC-Bot captures portable configuration and never creates Agent work."""
import json
from dataclasses import replace
import pytest,httpx
from fastapi import FastAPI
from ai2apps.api.app_shortcuts import create_app_shortcuts_router
from ai2apps.messager.shortcuts import service
from ai2apps.messager.creation import BotCreateDraft,create,options
from test_app_interactions import runtime
from test_bot_capability_discovery import setup,P
from ai2apps.apps.app_state import StateError

@pytest.fixture
def shortcut(runtime):
 setup(runtime);p=P();instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=p)
 packet={'schema':'ai2apps.app-state/v1','target':{'app_id':'ai2apps.imagine-studio','mini_app_id':'ai2apps.imagine.style-transfer','contract_version':1},'values':{'model_id':'cloud/fixture/image','style_id':'ghibli','width':1024,'height':1024,'quality':'high','format':'png'}}
 return runtime,p,instance,packet

@pytest.mark.asyncio
async def test_capture_launch_instance_binding_and_no_execution(shortcut):
 r,p,i,packet=shortcut;principal=[p];app=FastAPI();app.include_router(create_app_shortcuts_router(lambda:r,lambda:principal[0]))
 with r.database.transaction() as db:before=db.execute('SELECT count(*) FROM agent_runs').fetchone()[0]
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
  body={'source_instance_id':i.id,'packet':packet,'name':'Ghibli','avatar':{'kind':'preset','preset':'cat','color':'#112233'},'request_id':'capture-shortcut-1'}
  result=await c.post('/app-shortcuts/bots',json=body);assert result.status_code==201,result.text
  bot=result.json();assert bot['definition']['preset']=='asc' and bot['avatar']['preset']=='cat'
  assert (await c.post('/app-shortcuts/bots',json=body)).json()==bot
  launch=await c.post('/app-shortcuts/bots/'+bot['id']+'/launch',json={'request_id':'launch-shortcut-1'});assert launch.status_code==201,launch.text
  value=launch.json();assert value['target']==packet['target']
  assert (await c.post('/app-shortcuts/bots/'+bot['id']+'/launch',json={'request_id':'launch-shortcut-1'})).json()==value
  claim=await c.post('/app-shortcuts/launches/'+value['id']+'/claim',json={'instance_id':i.id});assert claim.status_code==200,claim.text
  assert claim.json()['packet']==packet
  other,_,_=r.extension_manager.launch_app('ai2apps.imagine-studio',principal=p)
  # A different instance of this App cannot steal an admitted handoff.
  if other.id!=i.id:assert (await c.post('/app-shortcuts/launches/'+value['id']+'/claim',json={'instance_id':other.id})).status_code==404
  wrong,_,_=r.extension_manager.launch_app('ai2apps.gallery',principal=p)
  assert (await c.post('/app-shortcuts/launches/'+value['id']+'/claim',json={'instance_id':wrong.id})).status_code==404
  principal[0]=replace(p,actor_user_id='foreign')
  assert (await c.get('/app-shortcuts/launches/'+value['id'])).status_code==404
 with r.database.transaction() as db:assert db.execute('SELECT count(*) FROM agent_runs').fetchone()[0]==before
 assert r.messager_bot_app_access.current(p.actor_user_id,bot['id'])[1]=={}
 with pytest.raises(PermissionError):r.messager_bots.agent_identity(p.actor_user_id,{'bot_id':bot['id']})

@pytest.mark.asyncio
async def test_capture_rejects_private_fields_and_mismatched_source(shortcut):
 r,p,i,packet=shortcut;app=FastAPI();app.include_router(create_app_shortcuts_router(lambda:r,lambda:p))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
  body={'source_instance_id':i.id,'packet':{**packet,'values':{**packet['values'],'prompt':'PRIVATE'}},'name':'Invalid','request_id':'bad-shortcut-1'}
  assert (await c.post('/app-shortcuts/bots',json=body)).status_code==409
  body['packet']={**packet,'target':{**packet['target'],'app_id':'ai2apps.gallery'}}
  assert (await c.post('/app-shortcuts/bots',json=body)).status_code==404
  assert not any(b['name']=='Invalid' for b in r.messager_bots.list(p.actor_user_id))

def test_old_launch_rejected_after_definition_change_and_expiry(shortcut):
 from ai2apps.api.app_shortcuts import Capture
 r,p,i,packet=shortcut;s=service(r);bot=s.create(p,Capture(source_instance_id=i.id,packet=packet,name='View',request_id='capture-view-1'))
 launch=s.launch(p,bot['id'],'launch-view-1')
 with r.database.transaction(write=True) as db:db.execute('UPDATE messager_shortcut_launches SET expires=0 WHERE id=?',(launch['id'],))
 with pytest.raises(StateError):s.get(p,launch['id'])
 launch=s.launch(p,bot['id'],'launch-view-2')
 with r.database.transaction(write=True) as db:db.execute('UPDATE messager_bot_definitions SET revision=revision+1 WHERE bot_id=?',(bot['id'],))
 with pytest.raises(StateError):s.claim(p,launch['id'],i.id)

def test_ordinary_creation_route_cannot_bypass_source_capture(shortcut):
 r,p,i,packet=shortcut
 body=BotCreateDraft(request_id='manual-asc-1',bot_type='asc',definition={'execution_mode':'app_shortcut','config':{'state':packet}},name='Forged',duty='Open',access_review_hash=options(r)['access']['review_hash'])
 with pytest.raises(PermissionError):create(r,p.actor_user_id,body)


def test_shortcut_cannot_open_agent_session_or_admit_a_task(shortcut):
 from ai2apps.api.app_shortcuts import Capture
 r,p,i,packet=shortcut;s=service(r);bot=s.create(p,Capture(source_instance_id=i.id,packet=packet,name='View',request_id='capture-no-agent'))
 with pytest.raises(PermissionError):r.messager_dialogue.scope(p.actor_user_id,{'bot_id':bot['id']})
 with pytest.raises(PermissionError):r.messager_dialogue.admit(p.actor_user_id,{'bot_id':bot['id']},'forged','do work',None)
 with pytest.raises(PermissionError):r.messager_dialogue.submit(p,bot['id'],'forged','forged','work',None,[])


def test_comic_shortcut_restores_settings_without_capturing_contents(shortcut):
    from ai2apps.api.app_shortcuts import Capture

    runtime, principal, instance, packet = shortcut
    packet['target']['mini_app_id'] = 'ai2apps.imagine.comic-translation'
    packet['values'] = {'language': 'ja', 'direction': 'vertical', 'model_id': 'mock/model',
                        'profile': 'Recurring characters', 'auto_crop': False, 'page_context': True}
    shortcuts = service(runtime)
    bot = shortcuts.create(principal, Capture(
        source_instance_id=instance.id, packet=packet, name='Japanese comic', request_id='capture-comic-1'))
    launch = shortcuts.launch(principal, bot['id'], 'launch-comic-1')
    assert shortcuts.claim(principal, launch['id'], instance.id)['packet'] == packet
    bad = {**packet, 'values': {**packet['values'], 'pages': ['art_unexpected']}}
    with pytest.raises(StateError):
        shortcuts.create(principal, Capture(
            source_instance_id=instance.id, packet=bad, name='Invalid', request_id='capture-comic-2'))


@pytest.mark.asyncio
async def test_archived_shortcut_can_be_restored_without_recapturing_state(shortcut):
    from ai2apps.api.app_shortcuts import Capture

    runtime, principal, instance, packet = shortcut
    shortcuts = service(runtime)
    actor = principal.actor_user_id
    bot = shortcuts.create(principal, Capture(
        source_instance_id=instance.id, packet=packet, name='Recoverable', request_id='capture-archive-1',
    ))
    lifecycle = runtime.messager_bot_lifecycle
    bot_id = bot['id']
    await lifecycle.apply(actor, bot_id, 'archive', lifecycle.review(actor, bot_id)['review_hash'])
    assert bot_id not in {entry['id'] for entry in runtime.messager_bots.list(actor)}
    with pytest.raises(PermissionError):
        shortcuts.launch(principal, bot_id, 'launch-archived-1')
    archived = next(entry for entry in lifecycle.archived(actor)['items'] if entry['id'] == bot_id)
    lifecycle.restore(actor, bot_id, archived['revision'])
    assert shortcuts.definition(principal, bot_id)['config']['state'] == packet
