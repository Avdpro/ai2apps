"""Configured Bot creation is atomic, owner-scoped and idempotent."""
import pytest
from pydantic import ValidationError
from fastapi import FastAPI
import httpx
from ai2apps.messager.creation import BotCreateDraft,create,options
from ai2apps.messager.conversation_profile import settings
from ai2apps.api.messager_mobile import create_messager_mobile_router
from test_app_interactions import runtime
from test_bot_capability_discovery import setup,P
from dataclasses import replace


def draft(r,**updates):
 value={'request_id':'creation-fixture-001','name':'New Bot','duty':'Fixture role','model_id':'fixture','avatar':{'kind':'preset','preset':'owl','color':'#2563eb'},'apps':[], 'access_review_hash':options(r)['access']['review_hash']}
 return BotCreateDraft.model_validate({**value,**updates})


def test_configured_creation_persists_all_initial_settings_once(runtime):
 setup(runtime)
 catalog=options(runtime)['access'];target=next(a for a in catalog['items'] if a['available'])
 body=draft(runtime,apps=[{'app_id':target['app_id'],'enabled':True}])
 before=len(runtime.messager_bots.list('local'));bot=create(runtime,'local',body)
 assert create(runtime,'local',body)==bot
 assert len(runtime.messager_bots.list('local'))==before+1
 assert bot['avatar']['preset']=='owl'
 assert settings(runtime,'local',bot['id'])['model_id']=='fixture'
 grants=runtime.messager_bot_app_access.current('local',bot['id'])[1]
 assert set(grants)=={target['app_id']} and grants[target['app_id']]['enabled']
 assert runtime.messager_bot_permissions.current('local',bot['id'])[1]=={}
 with pytest.raises(ValueError):create(runtime,'local',body.model_copy(update={'name':'Changed'}))
 assert not any(b['id']==bot['id'] for b in runtime.messager_bots.list('foreign'))


def test_rejected_drafts_never_leave_a_bot_or_grants(runtime):
 setup(runtime);before=len(runtime.messager_bots.list('local'))
 for changes in ({'name':'  '},{'apps':[{'app_id':'foreign-or-unknown','enabled':True}]},{'access_review_hash':'0'*64}):
  with pytest.raises(ValueError):create(runtime,'local',draft(runtime,**changes))
  assert len(runtime.messager_bots.list('local'))==before
 with pytest.raises(ValidationError):draft(runtime,bot_type='flash')
 # Request keys are actor-scoped; one user's retry cannot return another user's Bot.
 first=create(runtime,'local',draft(runtime));second=create(runtime,'foreign',draft(runtime))
 assert first['id']!=second['id']

@pytest.mark.asyncio
async def test_mobile_creation_uses_owner_adapter_and_cancellation_needs_no_server_draft(runtime):
 setup(runtime);owner=replace(P(),authentication_type='owner_home_lease',client_scope='owner-home')
 principal=[owner];app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,lambda:principal[0]))
 before=len(runtime.messager_bots.list('local'))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
  assert (await c.get('/messager-mobile/creation/options')).status_code==200
  assert len(runtime.messager_bots.list('local'))==before
  value=draft(runtime).model_dump();first=await c.post('/messager-mobile/creation',json=value)
  assert first.status_code==201,first.text
  assert (await c.post('/messager-mobile/creation',json=value)).json()==first.json()
  assert first.json()['definition']['execution_mode']=='agent'
  value['bot_type']='mirror';assert (await c.post('/messager-mobile/creation',json=value)).status_code==422
  principal[0]=P();assert (await c.get('/messager-mobile/creation/options')).status_code==403


def test_mid_transaction_failure_rolls_back_identity_and_permissions(runtime):
 import sqlite3
 setup(runtime);before=len(runtime.messager_bots.list('local'))
 with runtime.database.transaction() as db:before_definitions=db.execute('SELECT count(*) FROM messager_bot_definitions').fetchone()[0]
 with runtime.database.transaction(write=True) as db:
  db.execute("CREATE TRIGGER creation_fixture_failure BEFORE INSERT ON messager_bot_avatars BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
 try:
  with pytest.raises(sqlite3.IntegrityError):create(runtime,'local',draft(runtime))
  assert len(runtime.messager_bots.list('local'))==before
  with runtime.database.transaction() as db:
   assert db.execute('SELECT count(*) FROM messager_bot_creations').fetchone()[0]==0
   assert db.execute('SELECT count(*) FROM messager_bot_definitions').fetchone()[0]==before_definitions
 finally:
  with runtime.database.transaction(write=True) as db:db.execute('DROP TRIGGER creation_fixture_failure')


def test_group_rename_and_creation_preserve_membership_and_reject_stale_targets(runtime):
    setup(runtime)
    directory = runtime.messager_bots
    groups = directory.groups
    group_id = groups.create('local', 'Before')
    initial = next(g for g in groups.list('local') if g['id'] == group_id)
    body = draft(runtime, group_id=group_id)
    created = create(runtime, 'local', body)

    groups.update('local', group_id, initial['revision'], name=' After ')
    renamed = next(g for g in groups.list('local') if g['id'] == group_id)
    assert renamed['name'] == 'After'
    assert renamed['revision'] == initial['revision'] + 1
    assert create(runtime, 'local', body) == created
    assert next(b for b in directory.list('local') if b['id'] == created['id'])['group_id'] == group_id
    with pytest.raises(ValueError):
        groups.update('local', group_id, initial['revision'], name='Stale')
    with pytest.raises(ValueError):
        groups.update('local', 'quick', 1, name='Renamed Quick Bots')

    groups.update('local', group_id, renamed['revision'], delete=True)
    foreign_id = groups.create('foreign', 'Foreign')
    before = directory.list('local')
    for unavailable in (group_id, foreign_id):
        with pytest.raises(PermissionError):
            create(runtime, 'local', draft(runtime, request_id='new-group-fixture', group_id=unavailable))
    assert directory.list('local') == before


def test_research_template_seeds_once_and_custom_copies_keep_their_own_access(runtime):
    from ai2apps.messager.creation import ensure_research
    from ai2apps.messager.templates import BROWSER, RESEARCH_TARGETS

    setup(runtime)
    directory = runtime.messager_bots
    standard = directory.ensure_default('local')
    ensure_research(runtime, 'local', 'zh')
    built_in, = [b for b in directory.list('local') if b['template_id'] == 'research']
    assert built_in['id'] != standard
    assert built_in['name'] == '研究 Bot'
    assert '精确型号' not in built_in['duty']
    catalog = options(runtime)
    template, = catalog['templates']
    assert set(template['app_ids']) == set(RESEARCH_TARGETS)
    access = runtime.messager_bot_app_access
    assert {p.capability for p in access.exported('local', built_in['id'])} >= {
        'web.search', 'web.fetch', 'browser.complete_goal',
    }

    directory.update('local', built_in['id'], 'My Research', 'My revised role')
    saved = access.catalog('local', built_in['id'])
    access.save('local', built_in['id'], saved['revision'], saved['review_hash'], [])
    ensure_research(runtime, 'local', 'en')
    assert directory.identity('local', {'bot_id': built_in['id']}) == {'name': 'My Research', 'duty': 'My revised role'}
    assert access.current('local', built_in['id'])[1] == {}

    body = draft(runtime, template_id='research', name='Recipe research', duty='Compare public recipes',
                 apps=[{'app_id': BROWSER, 'enabled': True}])
    copy = create(runtime, 'local', body)
    assert create(runtime, 'local', body) == copy
    assert copy['id'] != built_in['id']
    assert copy['template_id'] == 'research'
    assert set(access.current('local', copy['id'])[1]) == {BROWSER}

    with runtime.database.transaction(write=True) as db:
        db.execute('INSERT INTO messager_bot_archive(bot_id,actor,deleted) VALUES(?,?,1)', (built_in['id'], 'local'))
    ensure_research(runtime, 'local', 'en')
    assert [b['id'] for b in directory.list('local') if b['template_id'] == 'research'] == [copy['id']]
    ensure_research(runtime, 'other', 'en')
    other, = directory.list('other')
    assert other['name'] == 'Research Bot'
    with pytest.raises(PermissionError):
        directory.update('other', copy['id'], 'Foreign name', 'Foreign role')


@pytest.mark.asyncio
async def test_research_bot_is_shared_between_desktop_and_mobile(runtime):
    from ai2apps.api.messager import create_messager_router

    setup(runtime)
    mobile = replace(P(), authentication_type='owner_home_lease', client_scope='owner-home')
    app = FastAPI()
    app.include_router(create_messager_router(lambda: runtime, P))
    app.include_router(create_messager_mobile_router(lambda: runtime, lambda: mobile))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as c:
        desktop = await c.get('/messager/bots?language=zh')
        phone = await c.get('/messager-mobile/bots?language=en')
        assert desktop.status_code == phone.status_code == 200
        assert desktop.json()['items'] == phone.json()['items']
        research, = [bot for bot in phone.json()['items'] if bot['template_id'] == 'research']
        assert research['name'] == '研究 Bot'
        assert not research['is_default']
